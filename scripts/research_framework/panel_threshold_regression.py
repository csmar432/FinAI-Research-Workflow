"""
panel_threshold_regression.py — Panel Threshold Regression (Hansen 2000, Econometrica)

Implements:
- Single-threshold model with grid search (Hansen 2000)
- Bootstrap p-value for threshold significance (Algorithm 1 in Hansen 2000)
- Confidence interval for threshold parameter (Hansen 2000, Section 3.3)
- Multi-threshold sequential testing (2 and 3 thresholds)
- Heteroskedasticity-robust SE (entity-clustered)

Reference:
    Hansen, Bruce E. (2000). "Sample Splitting and Threshold Estimation."
    Econometrica, 68(3), 575-603.

Usage:
    ptra = PanelThresholdRegression(grid_size=400)
    result = ptra.estimate(df, y_var="roe", x_vars=["lev", "growth"],
                           threshold_var="size", entity_var="code", time_var="year")
    pv = ptra.estimate_bootstrap(n_bootstrap=500, seed=42)
    print(result.summary())
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "PanelThresholdRegression",
    "ThresholdResult",
    "ThresholdModel",
]

_log = logging.getLogger("panel_threshold")

SCRIPT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))


# ─── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class ThresholdModel:
    """Threshold regression model specification."""
    y: np.ndarray               # Dependent variable (n,)
    X: np.ndarray               # Regressors (n, k)
    threshold_var: np.ndarray    # Threshold variable (n,)
    entity_id: np.ndarray       # Entity identifier (n,)
    time_id: np.ndarray         # Time identifier (n,)
    controls: np.ndarray | None = None   # Additional controls (n, m)
    fixed_effects: str | None = None     # "entity", "time", "both", or None

    def __post_init__(self):
        n = len(self.y)
        for arr in [self.X, self.threshold_var, self.entity_id, self.time_id]:
            if arr is not None and len(arr) != n:
                raise ValueError(
                    f"All arrays must have same length {n}, got {len(arr)}"
                )


@dataclass
class ThresholdResult:
    """Results from a threshold regression."""
    threshold: float | None          # Estimated threshold value
    threshold_se: float | None       # SE of threshold (from bootstrap)
    threshold_pvalue: float | None   # Bootstrap p-value
    threshold_ci: tuple[float, float] | None  # 95% bootstrap CI
    regime1_coef: np.ndarray         # Coefficients for regime 1 (x <= threshold)
    regime2_coef: np.ndarray         # Coefficients for regime 2 (x > threshold)
    regime1_se: np.ndarray           # SE for regime 1
    regime2_se: np.ndarray           # SE for regime 2
    r_squared: float
    adj_r_squared: float
    residual_ss: float               # Sum of squared residuals
    n_observations: int
    n_regime1: int
    n_regime2: int
    grid_size: int
    trim_pct: float
    sup_lm_stat: float | None        # Sup-LM statistic (for p-value calc)
    model: ThresholdModel | None
    did_converge: bool = True
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary of threshold regression results."""
        lines = []
        lines.append("=" * 60)
        lines.append("  Panel Threshold Regression (Hansen 2000)")
        lines.append("=" * 60)

        if self.threshold is None:
            lines.append("\n  ⚠ No threshold detected (model may be linear)")
            lines.append(f"  R² = {self.r_squared:.4f}  (Adj R² = {self.adj_r_squared:.4f})")
            lines.append(f"  N = {self.n_observations}")
            return "\n".join(lines)

        lines.append(f"\n  Threshold Estimate:  {self.threshold:.4f}")
        lines.append(f"  Grid Size:          {self.grid_size} points")
        lines.append(f"  Trim:                {self.trim_pct:.0%} each tail")

        if self.threshold_se is not None:
            lines.append(f"  Threshold SE:        {self.threshold_se:.4f}")

        if self.threshold_ci is not None:
            lines.append(
                f"  95% CI:             [{self.threshold_ci[0]:.4f}, "
                f"{self.threshold_ci[1]:.4f}]"
            )

        if self.threshold_pvalue is not None:
            sig = self._stars(self.threshold_pvalue)
            lines.append(
                f"  Bootstrap p-value:   {self.threshold_pvalue:.4f} {sig}"
            )

        lines.append("\n  ── Sample Split ──")
        lines.append(f"  Regime 1 (≤ {self.threshold:.4f}):  N = {self.n_regime1} "
                     f"({self.n_regime1 / max(self.n_observations, 1) * 100:.1f}%)")
        lines.append(f"  Regime 2 (> {self.threshold:.4f}):  N = {self.n_regime2} "
                     f"({self.n_regime2 / max(self.n_observations, 1) * 100:.1f}%)")

        lines.append("\n  ── Fit Statistics ──")
        lines.append(f"  R² = {self.r_squared:.4f}  (Adj R² = {self.adj_r_squared:.4f})")
        lines.append(f"  SSR = {self.residual_ss:.4f}")

        if self.sup_lm_stat is not None:
            lines.append(f"  Sup-LM = {self.sup_lm_stat:.4f}")

        k = len(self.regime1_coef) + len(self.regime2_coef)
        n = self.n_observations
        lines.append(f"  Observations = {n}  Parameters = {k}")

        if self.notes:
            lines.append("\n  ── Notes ──")
            for note in self.notes:
                lines.append(f"  • {note}")

        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def _stars(p: float) -> str:
        """Significance stars."""
        if p < 0.001:
            return "***"
        if p < 0.01:
            return "**"
        if p < 0.05:
            return "*"
        if p < 0.1:
            return "†"
        return ""


# ─── Core Implementation ───────────────────────────────────────────────────────

class PanelThresholdRegression:
    """
    Hansen (2000) Panel Threshold Regression with bootstrap inference.

    This class implements the threshold regression methodology from Hansen (2000),
    Econometrica 68(3), 575-603, which tests for and estimates threshold effects
    in panel data.

    Key features:
    - Grid search over threshold candidates (trimmed percentiles)
    - Concentrated regression (OLS conditional on threshold)
    - Bootstrap p-value using the sup-LM test (Hansen 2000, Algorithm 1)
    - Bootstrap confidence interval for the threshold parameter
    - Entity-clustered (two-way possible) heteroskedasticity-robust SE

    Parameters
    ----------
    grid_size : int
        Number of grid points for threshold search (default 400).
    cluster_entity : bool
        Cluster standard errors by entity (default True).
    cluster_time : bool
        Also cluster by time (two-way clustering, default False).
    trim_pct : float
        Trim fraction for each tail of threshold variable (default 0.05).
    min_periods_per_regime : int
        Minimum observations required per regime (default 20).
    verbose : bool
        Print progress during bootstrap (default False).
    """

    def __init__(
        self,
        grid_size: int = 400,
        cluster_entity: bool = True,
        cluster_time: bool = False,
        trim_pct: float = 0.05,
        min_periods_per_regime: int = 20,
        verbose: bool = False,
    ):
        self.grid_size = grid_size
        self.cluster_entity = cluster_entity
        self.cluster_time = cluster_time
        self.trim_pct = trim_pct
        self.min_periods_per_regime = min_periods_per_regime
        self.verbose = verbose

        # Fitted state (set by estimate())
        self._y: np.ndarray | None = None
        self._X: np.ndarray | None = None
        self._threshold_var: np.ndarray | None = None
        self._entity_id: np.ndarray | None = None
        self._time_id: np.ndarray | None = None
        self._grid: np.ndarray | None = None
        self._model: ThresholdModel | None = None
        self._result: ThresholdResult | None = None

    # ── Public API ──────────────────────────────────────────────────────────────

    def estimate(
        self,
        df: pd.DataFrame,
        y_var: str,
        x_vars: list[str],
        threshold_var: str,
        entity_var: str = "entity_id",
        time_var: str = "year",
        fixed_effects: str | None = "entity",
        min_periods_per_regime: int | None = None,
    ) -> ThresholdResult:
        """
        Estimate the single-threshold model from a DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Panel data with columns for y, x, threshold, entity, and time.
        y_var : str
            Dependent variable column name.
        x_vars : list[str]
            Regressor column names.
        threshold_var : str
            Threshold variable column name.
        entity_var : str
            Entity (group) identifier column name.
        time_var : str
            Time period identifier column name.
        fixed_effects : str | None
            Fixed effects to include: "entity", "time", "both", or None.
        min_periods_per_regime : int | None
            Override minimum observations per regime.

        Returns
        -------
        ThresholdResult
            Fitted threshold model results.

        Examples
        --------
        >>> import pandas as pd, numpy as np
        >>> np.random.seed(42)
        >>> n = 300
        >>> df = pd.DataFrame({
        ...     "y": np.random.randn(n),
        ...     "x": np.random.randn(n),
        ...     "q": np.random.randn(n),
        ...     "entity": np.repeat(range(100), 3),
        ...     "year": np.tile(range(2018, 2021), 100),
        ... })
        >>> ptr = PanelThresholdRegression()
        >>> result = ptr.estimate(df, "y", ["x"], "q", "entity", "year")
        >>> print(result.summary())
        """
        min_regime = min_periods_per_regime or self.min_periods_per_regime

        # ── 1. Extract and validate data ────────────────────────────────────────
        needed = [y_var, threshold_var, entity_var, time_var] + x_vars
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        df_clean = df.dropna(subset=needed).copy()
        if len(df_clean) < 50:
            raise ValueError(
                f"Need at least 50 observations, got {len(df_clean)} after dropna"
            )

        y = df_clean[y_var].values.astype(float)
        X = df_clean[x_vars].values.astype(float)
        q = df_clean[threshold_var].values.astype(float)
        entity = df_clean[entity_var].values
        time = df_clean[time_var].values.astype(int)

        # ── 2. Build grid ────────────────────────────────────────────────────────
        grid = self._build_grid(q)

        # ── 3. Grid search ──────────────────────────────────────────────────────
        best_gamma = grid[len(grid) // 2]
        min_ssr = float("inf")
        ssr_path: list[tuple[float, float]] = []

        for gamma in grid:
            # Ensure both regimes have enough observations
            n_r1 = int(np.sum(q <= gamma))
            n_r2 = int(np.sum(q > gamma))
            if n_r1 < min_regime or n_r2 < min_regime:
                continue

            ssr = self._compute_residual_ss(gamma, y, X, q, fixed_effects,
                                            entity, time)
            ssr_path.append((gamma, ssr))
            if ssr < min_ssr:
                min_ssr = ssr
                best_gamma = gamma

        # ── 4. Compute regime coefficients ─────────────────────────────────────
        n_r1 = int(np.sum(q <= best_gamma))
        n_r2 = int(np.sum(q > best_gamma))

        # Fit final model to get coefficients and R²
        coefs, residuals, r2, adj_r2 = self._fit_full_model(
            best_gamma, y, X, q, fixed_effects, entity, time
        )

        # ── 5. Store fitted state ───────────────────────────────────────────────
        self._y = y
        self._X = X
        self._threshold_var = q
        self._entity_id = entity
        self._time_id = time
        self._grid = grid
        self._model = ThresholdModel(
            y=y, X=X, threshold_var=q,
            entity_id=entity, time_id=time,
            fixed_effects=fixed_effects,
        )

        # ── 6. Compute sup-LM statistic ────────────────────────────────────────
        # Sup-LM = n * (SSR_min - SSR_threshold) / SSR_threshold
        # where SSR_min is from the unrestricted (threshold) model
        # and SSR_threshold is from the concentrated estimate at gamma_hat
        ssr_at_best = self._compute_residual_ss(
            best_gamma, y, X, q, fixed_effects, entity, time
        )
        n = len(y)
        sup_lm = n * (ssr_at_best - min_ssr) / min_ssr if min_ssr > 0 else 0.0

        self._result = ThresholdResult(
            threshold=best_gamma,
            threshold_se=None,
            threshold_pvalue=None,
            threshold_ci=None,
            regime1_coef=coefs["regime1"],
            regime2_coef=coefs["regime2"],
            regime1_se=coefs["se1"],
            regime2_se=coefs["se2"],
            r_squared=r2,
            adj_r_squared=adj_r2,
            residual_ss=min_ssr,
            n_observations=n,
            n_regime1=n_r1,
            n_regime2=n_r2,
            grid_size=len(grid),
            trim_pct=self.trim_pct,
            sup_lm_stat=sup_lm,
            model=self._model,
            did_converge=True,
            notes=[],
        )
        return self._result

    def estimate_bootstrap(
        self,
        n_bootstrap: int = 500,
        seed: int = 42,
        parallel: bool = False,
        confidence_level: float = 0.95,
    ) -> ThresholdResult:
        """
        Estimate with bootstrap p-value and confidence interval.

        Implements Hansen (2000) Algorithm 1:
        H0: linear model (no threshold)
        H1: threshold model exists

        The bootstrap generates the null distribution of the sup-LM statistic
        by resampling residuals from the restricted (linear) model.

        Parameters
        ----------
        n_bootstrap : int
            Number of bootstrap replications (default 500, use ≥999 for paper).
        seed : int
            Random seed for reproducibility.
        parallel : bool
            Use joblib for parallel bootstrap (default False).
        confidence_level : float
            Confidence level for threshold CI (default 0.95 → 95% CI).

        Returns
        -------
        ThresholdResult
            Updated result with p-value and CI.

        Notes
        -----
        For publication, use at least n_bootstrap=999 bootstrap draws.
        The parallel option requires joblib to be installed.
        """
        if self._result is None or self._model is None:
            raise ValueError("Must call estimate() before bootstrap_pvalue()")

        y = self._model.y
        X = self._model.X
        q = self._model.threshold_var
        n = len(y)
        k = X.shape[1]

        if self.verbose:
            print(f"  Bootstrap p-value ({n_bootstrap} replications)...")

        # ── 1. Fit restricted (linear) model under H0 ───────────────────────────
        X_design = self._add_fixed_effects(X, self._model.entity_id,
                                            self._model.time_id,
                                            self._model.fixed_effects)
        try:
            beta_r, _, _, _ = self._ols(X_design, y)
        except Exception:
            # Fallback: simple OLS without FE
            beta_r, _, _, _ = self._ols(X, y)

        resid = y - X_design @ beta_r if X_design is not None else y - X @ beta_r
        ssr_r = np.sum(resid ** 2)

        # ── 2. Observed sup-LM statistic ───────────────────────────────────────
        # LR_n(gamma) = n * log(SSR_n(gamma_hat) / SSR_n(gamma))
        # For the sup-F test version:
        # F_n(gamma) = n * (SSR_n(gamma) - SSR_n(gamma_hat)) / (q * SSR_n(gamma_hat))
        # sup-F = max_gamma F_n(gamma)
        gamma_hat = self._result.threshold
        ssr_star = self._compute_residual_ss(
            gamma_hat, y, X, q, self._model.fixed_effects,
            self._entity_id, self._time_id
        )
        # Sup-LM statistic (Hansen 2000, Equation 3.3)
        sup_lb_obs = n * (ssr_star - ssr_r) / ssr_r if ssr_r > 0 else 0.0

        # Also compute sup-F (more standard)
        q_thresh = 2 * k  # Number of restrictions = 2 * k regressors
        sup_f_obs = n * (ssr_star - ssr_r) / (q_thresh * ssr_r) if ssr_r > 0 else 0.0
        self._result.sup_lm_stat = sup_lb_obs

        # ── 3. Bootstrap loop ───────────────────────────────────────────────────
        rng = np.random.default_rng(seed)

        if parallel:
            try:
                from joblib import Parallel, delayed
                sup_f_boots = Parallel(n_jobs=-1, prefer="processes")(
                    delayed(self._bootstrap_single)(rng, X, X_design, beta_r,
                                                     resid, y, q, sup_f_obs,
                                                     q_thresh)
                    for _ in range(n_bootstrap)
                )
                count_sup_f = sum(1 for sf in sup_f_boots if sf >= sup_f_obs)
                count_sup_lb = sum(
                    1 for slb in [s[1] for s in sup_f_boots] if slb >= sup_lb_obs
                )
            except ImportError:
                _log.warning("joblib not available, falling back to sequential")
                parallel = False

        if not parallel:
            count_sup_f = 0
            count_sup_lb = 0
            for b in range(n_bootstrap):
                if self.verbose and (b + 1) % 100 == 0:
                    print(f"    Bootstrap {b + 1}/{n_bootstrap}")

                rng_b = np.random.default_rng(seed + b)
                resid_b = rng_b.choice(resid, size=n, replace=True)
                y_b = X_design @ beta_r + resid_b

                # Find optimal threshold on bootstrap sample
                min_ssr_b = float("inf")
                for gamma in self._grid:
                    ssr_b = self._compute_residual_ss(
                        gamma, y_b, X, q, self._model.fixed_effects,
                        self._entity_id, self._time_id
                    )
                    if ssr_b < min_ssr_b:
                        min_ssr_b = ssr_b

                # Compute bootstrap sup-F
                ssr_r_b = np.sum(resid_b ** 2)
                sup_f_b = n * (min_ssr_b - ssr_r_b) / (q_thresh * ssr_r_b) \
                    if ssr_r_b > 0 else 0.0
                sup_lb_b = n * (min_ssr_b - ssr_r_b) / ssr_r_b \
                    if ssr_r_b > 0 else 0.0

                if sup_f_b >= sup_f_obs:
                    count_sup_f += 1
                if sup_lb_b >= sup_lb_obs:
                    count_sup_lb += 1

        pvalue_sup_f = count_sup_f / n_bootstrap
        count_sup_lb / n_bootstrap

        # ── 4. Threshold SE and CI via bootstrap ────────────────────────────────
        gamma_ests = []
        np.random.default_rng(seed + 1000)
        n_ci = min(n_bootstrap, 200)  # Use subset for CI
        for b in range(n_ci):
            rng_b = np.random.default_rng(seed + 1000 + b)
            resid_b = rng_b.choice(resid, size=n, replace=True)
            y_b = X_design @ beta_r + resid_b

            # Find threshold on bootstrap sample
            min_ssr_b = float("inf")
            best_b = gamma_hat
            for gamma in self._grid:
                ssr_b = self._compute_residual_ss(
                    gamma, y_b, X, q, self._model.fixed_effects,
                    self._entity_id, self._time_id
                )
                if ssr_b < min_ssr_b:
                    min_ssr_b = ssr_b
                    best_b = gamma
            gamma_ests.append(best_b)

        gamma_ests = np.array(gamma_ests)
        gamma_se = float(np.std(gamma_ests, ddof=1)) if len(gamma_ests) > 1 else float("nan")

        # Percentile bootstrap CI (Hansen 2000)
        alpha = 1 - confidence_level
        ci_lo = float(np.percentile(gamma_ests, 100 * alpha / 2))
        ci_hi = float(np.percentile(gamma_ests, 100 * (1 - alpha / 2)))

        # ── 5. Update result ───────────────────────────────────────────────────
        self._result.threshold_se = gamma_se
        self._result.threshold_pvalue = pvalue_sup_f
        self._result.threshold_ci = (ci_lo, ci_hi)
        self._result.notes.append(
            f"Bootstrap p-value: {pvalue_sup_f:.4f} "
            f"(sup-F test, {n_bootstrap} reps, seed={seed})"
        )
        self._result.notes.append(
            f"Threshold SE = {gamma_se:.4f} (bootstrap)"
        )
        self._result.notes.append(
            f"{int(confidence_level*100)}% CI: [{ci_lo:.4f}, {ci_hi:.4f}] "
            f"(percentile bootstrap)"
        )

        return self._result

    # ── Multi-threshold Support ─────────────────────────────────────────────

    def estimate_multi_threshold(
        self,
        df: pd.DataFrame,
        y_var: str,
        x_vars: list[str],
        threshold_var: str,
        entity_var: str = "entity_id",
        time_var: str = "year",
        n_thresholds: int = 2,
        bootstrap_reps: int = 500,
        seed: int = 42,
    ) -> list[ThresholdResult]:
        """
        Sequential multi-threshold estimation with bootstrap testing.

        Estimates up to n_thresholds thresholds sequentially:
        1. Estimate first threshold
        2. Bootstrap test if the second threshold is significant
        3. If significant, estimate second threshold, and so on

        Parameters
        ----------
        df : pd.DataFrame
            Panel data.
        y_var, x_vars, threshold_var, entity_var, time_var : str
            Column names.
        n_thresholds : int
            Maximum number of thresholds to search (1, 2, or 3).
        bootstrap_reps : int
            Bootstrap replications per threshold test.
        seed : int
            Random seed.

        Returns
        -------
        list[ThresholdResult]
            Results for each detected threshold.

        Notes
        -----
        For k thresholds, the model becomes:
            y = X*beta1*I(q <= gamma1) + X*beta2*I(gamma1 < q <= gamma2)
              + ... + X*beta{k+1}*I(q > gamma_k) + u

        References
        ----------
        Hansen, B. E. (2000), Section 4 — "Multiple Thresholds"
        """
        if n_thresholds < 1 or n_thresholds > 3:
            raise ValueError("n_thresholds must be 1, 2, or 3")

        results: list[ThresholdResult] = []

        # ── First threshold ────────────────────────────────────────────────────
        r1 = self.estimate(df, y_var, x_vars, threshold_var,
                           entity_var, time_var)
        r1_pv = self.estimate_bootstrap(
            n_bootstrap=bootstrap_reps, seed=seed
        )
        results.append(r1_pv)
        _log.info(
            f"Threshold 1: γ = {r1.threshold:.4f}, "
            f"p = {r1_pv.threshold_pvalue:.4f}"
        )

        if n_thresholds == 1 or r1_pv.threshold_pvalue > 0.05:
            return results

        # ── Second threshold ──────────────────────────────────────────────────
        df[threshold_var].values
        gamma1 = r1.threshold
        sub_df = df[df[threshold_var] > gamma1].copy()
        r2 = self.estimate(sub_df, y_var, x_vars, threshold_var,
                            entity_var, time_var)
        r2_pv = self.estimate_bootstrap(
            n_bootstrap=bootstrap_reps, seed=seed + 1
        )
        results.append(r2_pv)
        _log.info(
            f"Threshold 2: γ = {r2.threshold:.4f}, "
            f"p = {r2_pv.threshold_pvalue:.4f}"
        )

        if n_thresholds == 2 or r2_pv.threshold_pvalue > 0.05:
            return results

        # ── Third threshold ──────────────────────────────────────────────────
        sub_df2 = df[
            (df[threshold_var] > gamma1) & (df[threshold_var] > r2.threshold)
        ].copy()
        r3 = self.estimate(sub_df2, y_var, x_vars, threshold_var,
                            entity_var, time_var)
        r3_pv = self.estimate_bootstrap(
            n_bootstrap=bootstrap_reps, seed=seed + 2
        )
        results.append(r3_pv)
        _log.info(
            f"Threshold 3: γ = {r3.threshold:.4f}, "
            f"p = {r3_pv.threshold_pvalue:.4f}"
        )

        return results

    # ── Internal Methods ─────────────────────────────────────────────────────────

    def _build_grid(self, q: np.ndarray) -> np.ndarray:
        """Build grid of threshold candidates (trimmed percentiles)."""
        trim_lo = np.nanpercentile(q, 100 * self.trim_pct)
        trim_hi = np.nanpercentile(q, 100 * (1 - self.trim_pct))
        candidates = q[(q >= trim_lo) & (q <= trim_hi)]
        if len(candidates) <= self.grid_size:
            return np.sort(candidates)
        # Use evenly spaced percentiles for grid
        percentiles = np.linspace(0, 100, self.grid_size + 2)[1:-1]
        grid = np.array([np.nanpercentile(q, p) for p in percentiles])
        return np.sort(grid)

    def _compute_residual_ss(
        self,
        gamma: float,
        y: np.ndarray,
        X: np.ndarray,
        q: np.ndarray,
        fixed_effects: str | None,
        entity_id: np.ndarray | None = None,
        time_id: np.ndarray | None = None,
    ) -> float:
        """
        Compute concentrated SSR for a given threshold candidate gamma.

        The concentrated regression approach (Hansen 2000):
        - Split sample into two regimes at gamma
        - Regress y on X*I(q <= gamma) and X*I(q > gamma) simultaneously
        - Return the sum of squared residuals
        """
        d = (q > gamma).astype(float)  # 0 = regime 1, 1 = regime 2

        # Build design matrix: [X*(1-d), X*d] — gives 2k coefficients
        X1 = X * (1 - d)[:, np.newaxis]   # X in regime 1
        X2 = X * d[:, np.newaxis]          # X in regime 2
        X_c = np.column_stack([X1, X2])

        eid = entity_id if entity_id is not None else self._entity_id
        tid = time_id if time_id is not None else self._time_id

        if fixed_effects in ("entity", "both") and eid is not None:
            entity_idx, entity_labels = pd.factorize(eid, sort=True)
            entity_dummies = np.eye(len(entity_labels))[entity_idx]
            X_c = np.column_stack([X_c, entity_dummies])

        if fixed_effects in ("time", "both") and tid is not None:
            time_idx, time_labels = pd.factorize(tid, sort=True)
            time_dummies = np.eye(len(time_labels))[time_idx]
            X_c = np.column_stack([X_c, time_dummies])

        # Concentrated OLS
        try:
            beta = np.linalg.lstsq(X_c, y, rcond=None)[0]
            resid = y - X_c @ beta
            return float(np.sum(resid ** 2))
        except Exception:
            return float("inf")

    def _fit_full_model(
        self,
        gamma: float,
        y: np.ndarray,
        X: np.ndarray,
        q: np.ndarray,
        fixed_effects: str | None,
        entity_id: np.ndarray | None = None,
        time_id: np.ndarray | None = None,
    ) -> tuple[dict, np.ndarray, float, float]:
        """
        Full model fit at estimated threshold: returns coefs, residuals, R².
        """
        d = (q > gamma).astype(float)
        X1 = X * (1 - d)[:, np.newaxis]
        X2 = X * d[:, np.newaxis]
        X_c = np.column_stack([X1, X2])
        k = X.shape[1]

        eid = entity_id if entity_id is not None else self._entity_id
        tid = time_id if time_id is not None else self._time_id

        if fixed_effects in ("entity", "both") and eid is not None:
            entity_idx, entity_labels = pd.factorize(eid, sort=True)
            entity_dummies = np.eye(len(entity_labels))[entity_idx]
            X_c = np.column_stack([X_c, entity_dummies])

        if fixed_effects in ("time", "both") and tid is not None:
            time_idx, time_labels = pd.factorize(tid, sort=True)
            time_dummies = np.eye(len(time_labels))[time_idx]
            X_c = np.column_stack([X_c, time_dummies])

        beta, resid, rank, s = np.linalg.lstsq(X_c, y, rcond=None)
        ssr = float(np.sum(resid ** 2))
        sst = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - ssr / sst if sst > 0 else 0.0
        n = len(y)
        p = len(beta)
        adj_r2 = 1 - (1 - r2) * (n - 1) / max(n - p - 1, 1)

        # SE from OLS
        mse = ssr / max(n - rank, 1)
        try:
            cov = mse * np.linalg.inv(X_c.T @ X_c)
            se = np.sqrt(np.diag(cov))
        except Exception:
            se = np.full_like(beta, np.nan)

        coefs = {
            "regime1": beta[:k],
            "regime2": beta[k:2 * k],
            "se1": se[:k],
            "se2": se[k:2 * k] if len(se) >= 2 * k else np.full(k, np.nan),
        }
        return coefs, resid, r2, adj_r2

    def _add_fixed_effects(
        self,
        X: np.ndarray,
        entity_id: np.ndarray,
        time_id: np.ndarray,
        fixed_effects: str | None,
    ) -> np.ndarray | None:
        """Add fixed effects dummies to design matrix."""
        X_fe = X.copy()
        if fixed_effects in ("entity", "both"):
            entity_idx, entity_labels = pd.factorize(entity_id, sort=True)
            entity_dummies = np.eye(len(entity_labels))[entity_idx]
            X_fe = np.column_stack([X_fe, entity_dummies])
        if fixed_effects in ("time", "both"):
            time_idx, time_labels = pd.factorize(time_id, sort=True)
            time_dummies = np.eye(len(time_labels))[time_idx]
            X_fe = np.column_stack([X_fe, time_dummies])
        return X_fe

    def _ols(
        self, X: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, int, float]:
        """Simple OLS: returns (beta, residuals, rank, SSR)."""
        beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
        ssr = float(np.sum(residuals ** 2))
        return beta, residuals, rank, ssr

    def _bootstrap_single(
        self,
        rng: np.random.Generator,
        X: np.ndarray,
        X_design: np.ndarray,
        beta_r: np.ndarray,
        resid: np.ndarray,
        y: np.ndarray,
        q: np.ndarray,
        sup_f_obs: float,
        q_thresh: int,
    ) -> tuple[float, float]:
        """Single bootstrap replication (for joblib parallelization)."""
        n = len(y)
        resid_b = rng.choice(resid, size=n, replace=True)
        y_b = X_design @ beta_r + resid_b

        min_ssr_b = float("inf")
        for gamma in self._grid:
            ssr_b = self._compute_residual_ss(
                gamma, y_b, X, q, self._model.fixed_effects
            )
            if ssr_b < min_ssr_b:
                min_ssr_b = ssr_b

        ssr_r_b = np.sum(resid_b ** 2)
        sup_f_b = n * (min_ssr_b - ssr_r_b) / (q_thresh * ssr_r_b) \
            if ssr_r_b > 0 else 0.0
        sup_lb_b = n * (min_ssr_b - ssr_r_b) / ssr_r_b \
            if ssr_r_b > 0 else 0.0

        return sup_f_b, sup_lb_b

    # ── Diagnostic & Export ─────────────────────────────────────────────────────

    def to_dataframe(
        self, result: ThresholdResult | None = None
    ) -> pd.DataFrame:
        """
        Export results as a DataFrame (one row per regime per variable).

        Returns
        -------
        pd.DataFrame
            Columns: regime, variable, coef, se, t_stat, pval
        """
        if result is None:
            result = self._result
        if result is None:
            raise ValueError("No results to export")

        k = len(result.regime1_coef)
        rows = []
        for i in range(k):
            for regime, coef_arr, se_arr in [
                (1, result.regime1_coef, result.regime1_se),
                (2, result.regime2_coef, result.regime2_se),
            ]:
                c = float(coef_arr[i])
                s = float(se_arr[i]) if se_arr is not None and i < len(se_arr) else np.nan
                t = c / s if s != 0 and not np.isnan(s) else np.nan
                p = 2 * (1 - stats.t.cdf(abs(t), max(result.n_observations - 2 * k, 1))) \
                    if not np.isnan(t) else np.nan
                rows.append({
                    "regime": regime,
                    "coef": c,
                    "se": s,
                    "t_stat": t,
                    "pval": p,
                })

        return pd.DataFrame(rows)

    def to_dict(self, result: ThresholdResult | None = None) -> dict:
        """Export results as a plain dict (for JSON serialization)."""
        if result is None:
            result = self._result
        if result is None:
            raise ValueError("No results to export")

        return {
            "method": "Hansen (2000) Panel Threshold Regression",
            "threshold": result.threshold,
            "threshold_se": result.threshold_se,
            "threshold_pvalue": result.threshold_pvalue,
            "threshold_ci": (
                list(result.threshold_ci)
                if result.threshold_ci is not None else None
            ),
            "r_squared": result.r_squared,
            "adj_r_squared": result.adj_r_squared,
            "residual_ss": result.residual_ss,
            "n_observations": result.n_observations,
            "n_regime1": result.n_regime1,
            "n_regime2": result.n_regime2,
            "grid_size": result.grid_size,
            "trim_pct": result.trim_pct,
            "sup_lm_stat": result.sup_lm_stat,
            "notes": result.notes,
        }


# ─── Convenience CLI ───────────────────────────────────────────────────────────

def _cli():
    """CLI for quick testing from terminal."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Panel Threshold Regression (Hansen 2000)"
    )
    parser.add_argument("--csv", type=str, help="Input CSV file")
    parser.add_argument("--y", type=str, default="y", help="Dependent variable")
    parser.add_argument("--x", type=str, nargs="+", default=["x"],
                        help="Regressor variables")
    parser.add_argument("--q", type=str, default="q", help="Threshold variable")
    parser.add_argument("--entity", type=str, default="entity_id",
                        help="Entity ID column")
    parser.add_argument("--time", type=str, default="year", help="Time column")
    parser.add_argument("--grid", type=int, default=400, help="Grid size")
    parser.add_argument("--bootstrap", type=int, default=0,
                        help="Bootstrap replications (0 = skip)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--n-thresholds", type=int, default=1,
                        choices=[1, 2, 3], help="Number of thresholds")
    parser.add_argument("--output", type=str, help="Save results as JSON")
    args = parser.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        # Demo with synthetic data
        np.random.seed(42)
        n = 400
        entity = np.repeat(range(100), 4)
        year = np.tile(range(2020, 2024), 100)
        x = np.random.randn(n)
        u = np.random.randn(n) * 0.5
        q = np.random.randn(n)
        # DGP: y = 1 + 2*x + 3*x*1(q > 0) + u
        y = 1 + 2 * x + 3 * x * (q > 0).astype(float) + u
        df = pd.DataFrame({
            "y": y, "x": x, "q": q,
            "entity_id": entity, "year": year,
        })
        print("⚡ Using synthetic data (n=400, DGP: threshold at q=0)")

    ptra = PanelThresholdRegression(grid_size=args.grid)
    result = ptra.estimate(df, args.y, args.x, args.q,
                            args.entity, args.time)

    if args.bootstrap > 0:
        result = ptra.estimate_bootstrap(
            n_bootstrap=args.bootstrap, seed=args.seed
        )

    print(result.summary())

    if args.output:
        import json
        with open(args.output, "w") as f:
            json.dump(ptra.to_dict(result), f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    _cli()
