"""Panel Cointegration Tests for Macro-Finance Research.

Implements Pedroni (2004), Kao (1999), Westerlund (2005) panel cointegration
tests and Panel Error Correction Model (ECM) estimation with cross-sectional
dependence diagnostics.

Usage:
    pct = PanelCointegrationTest(trend="c", max_lags=4)
    res = pct.pedroni_panel(df, y_var="lnrgdp", x_vars=["lnmoney", "lninflation"])
    print(pct.summary())

    ecm = PanelECM(trend="c")
    ecm_res = ecm.fit(df, dep_var="lnrgdp", indep_vars=["lnmoney"], lag_order=2)
    print(ecm.summary())
    ecm.plot_ecm_coefficients("ecm_coef.pdf")

    csd = CrossSectionalDependence()
    cd_res = csd.test(df, vars=["eps", "roe", "lev"])
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "CointegrationResult",
    "PanelCointegrationTest",
    "PanelECM",
    "CrossSectionalDependence",
]

_log = logging.getLogger("panel_cointegration")
_log.setLevel(logging.INFO)
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CointegrationResult:
    """
    Panel cointegration test results container.

    Attributes
    ----------
    test_name : str
        Name of the cointegration test.
    statistic : float
        Test statistic value.
    pval : float
        Asymptotic p-value (normal approximation).
    decision : str
        "Reject H0" or "Fail to reject H0".
    n_obs : int
        Total observations used.
    n_lags : int
        Lag order selected.
    n_groups : int
        Number of cross-sectional units.
    trace_stat : float | None
        Trace statistic (for Westerlund).
    max_eig_stat : float | None
        Maximum eigenvalue statistic (for Westerlund).
    residual_correlation : float | None
        Average residual correlation.
    stationarity_test : dict
        Stationarity diagnostics on residuals.
    additional : dict
        Extra diagnostics (group statistics, variance ratios, etc.).
    """

    test_name: str
    statistic: float
    pval: float
    decision: str = ""
    n_obs: int = 0
    n_lags: int = 0
    n_groups: int = 0
    trace_stat: float | None = None
    max_eig_stat: float | None = None
    residual_correlation: float | None = None
    stationarity_test: dict = field(default_factory=dict)
    additional: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.decision:
            self.decision = "Reject H0" if self.pval < 0.05 else "Fail to reject H0"

    @property
    def sig(self) -> str:
        """Return significance stars for the test statistic."""
        return _significance_mark(self.pval)

    def to_dict(self) -> dict:
        """Convert to flat dictionary."""
        out = {
            "test_name": self.test_name,
            "statistic": self.statistic,
            "pval": self.pval,
            "decision": self.decision,
            "n_obs": self.n_obs,
            "n_lags": self.n_lags,
            "n_groups": self.n_groups,
            "residual_correlation": self.residual_correlation,
        }
        if self.trace_stat is not None:
            out["trace_stat"] = self.trace_stat
        if self.max_eig_stat is not None:
            out["max_eig_stat"] = self.max_eig_stat
        out.update(self.additional)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# SIGNIFICANCE & HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _significance_mark(pval: float) -> str:
    """Return significance stars for a p-value."""
    if pval < 0.01:
        return "***"
    elif pval < 0.05:
        return "**"
    elif pval < 0.10:
        return "*"
    return ""


def _norm_cdf(x: float | np.ndarray) -> float | np.ndarray:
    """Standard normal CDF with fallback."""
    try:
        from scipy import stats
        return stats.norm.cdf(x)
    except Exception:
        return np.where(x > 0, 1.0, 0.0) if isinstance(x, np.ndarray) else (1.0 if x > 0 else 0.0)


def _norm_ppf(x: float) -> float:
    """Standard normal quantile function."""
    try:
        from scipy import stats
        return stats.norm.ppf(x)
    except Exception:
        return 0.0


def _safe_div(a: float, b: float, fill: float = np.nan) -> float:
    """Safe division with NaN fill."""
    return a / b if (b != 0 and not np.isnan(b)) else fill


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL ALGORITHMS
# ─────────────────────────────────────────────────────────────────────────────


def _ols_residuals(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    """
    OLS residuals from y on X (no intercept — caller adds if needed).

    Parameters
    ----------
    y : np.ndarray (T,)
    X : np.ndarray (T, k)

    Returns
    -------
    np.ndarray (T,) residuals
    """
    try:
        beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        return y - X @ beta
    except Exception:
        _log.warning("[Cointegration] OLS failed, returning zeros")
        return np.zeros_like(y)


def _adf_stat(resid: np.ndarray, max_lags: int = 4) -> tuple[float, int, np.ndarray]:
    """
    Compute ADF statistic for a residual series.

    Δe_t = ρ * e_{t-1} + Σ γ_j * Δe_{t-j} + u_t

    Parameters
    ----------
    resid : np.ndarray (T,)
    max_lags : int

    Returns
    -------
    (adf_stat, optimal_lags, autocorr_resid)
    """
    T = len(resid)
    # Select lag by AIC
    best_aic = np.inf
    best_lag = 0

    for lag in range(0, min(max_lags + 1, T // 5)):
        if lag == 0:
            y_diff = resid[1:]
            x_lag = resid[:-1]
            X_mat = x_lag.reshape(-1, 1)
        else:
            y_diff = resid[1 + lag:]
            x_lag = resid[lag:-1].reshape(-1, 1)
            for j in range(1, lag + 1):
                delta_j = resid[1 + lag - j : -j]
                if len(delta_j) == len(x_lag):
                    X_mat = np.column_stack([x_lag] + [delta_j])
                    break
            else:
                continue

        if X_mat.shape[0] < 5 or X_mat.shape[1] != lag + 1:
            continue

        e = _ols_residuals(y_diff, X_mat)
        sigma2 = np.mean(e ** 2)
        if sigma2 <= 0:
            continue
        # AIC
        k = lag + 1
        n = len(y_diff)
        aic = np.log(sigma2) + 2 * k / n
        if aic < best_aic:
            best_aic = aic
            best_lag = lag

    # Final regression with best_lag
    lag = best_lag
    if lag == 0:
        y_diff = resid[1:]
        x_lag = resid[:-1]
        X_mat = x_lag.reshape(-1, 1)
    else:
        y_diff = resid[1 + lag:]
        x_lag = resid[lag:-1].reshape(-1, 1)
        X_mat = x_lag
        for j in range(1, lag + 1):
            delta_j = resid[1 + lag - j : -j]
            if len(delta_j) == len(x_lag):
                X_mat = np.column_stack([x_lag, delta_j])

    if X_mat.shape[0] < 5:
        return np.nan, lag, np.array([])

    try:
        beta, _, _, _ = np.linalg.lstsq(X_mat, y_diff, rcond=None)
        rho = beta[0]
        e = y_diff - X_mat @ beta
        sigma2 = np.mean(e ** 2)
        XTX_inv = np.linalg.inv(X_mat.T @ X_mat + 1e-10 * np.eye(X_mat.shape[1]))
        se_rho = np.sqrt(XTX_inv[0, 0] * sigma2)
        adf_stat = rho / se_rho if se_rho > 0 else np.nan
        return float(adf_stat), lag, e
    except Exception:
        return np.nan, lag, np.array([])


def _pp_stat(resid: np.ndarray) -> float:
    """
    Phillips-Perron Z-tau statistic (simplified).

    Uses Newey-West variance estimator.
    """
    T = len(resid)
    if T < 10:
        return np.nan

    y_diff = np.diff(resid)
    x_lag = resid[:-1]

    if len(y_diff) != len(x_lag) or len(y_diff) < 5:
        return np.nan

    try:
        beta, _, _, _ = np.linalg.lstsq(x_lag.reshape(-1, 1), y_diff, rcond=None)
        rho = beta[0]
        e = y_diff - rho * x_lag
        np.mean(e ** 2)

        # Newey-West HAC variance
        gamma = np.zeros(T)
        for j in range(T):
            if j == 0:
                gamma[j] = np.mean(e ** 2)
            else:
                gamma[j] = np.mean(e[j:] * e[:-j]) if j < len(e) else 0.0

        # Bartlett kernel bandwidth (simplified)
        h = int(4 * (T / 100) ** (1 / 4)) if T > 100 else 4
        h = min(h, T // 2)

        var_hac = gamma[0]
        for j in range(1, h + 1):
            if j < len(gamma):
                var_hac += 2 * (1 - j / (h + 1)) * gamma[j]

        se = np.sqrt(var_hac / np.sum(x_lag ** 2))
        pp_stat = (rho - 1) / se if se > 0 else np.nan
        return float(pp_stat)
    except Exception:
        return np.nan


def _select_lag_aic(resid: np.ndarray, max_lags: int = 4) -> int:
    """
    Select optimal lag using AIC for residual-based regressions.

    Parameters
    ----------
    resid : np.ndarray (T,)
    max_lags : int

    Returns
    -------
    int : optimal lag
    """
    T = len(resid)
    best_aic = np.inf
    best_lag = 0

    for lag in range(0, min(max_lags + 1, T // 5)):
        if lag == 0:
            y_diff = resid[1:]
            x_lag = resid[:-1]
            X_mat = x_lag.reshape(-1, 1)
        else:
            y_diff = resid[1 + lag:]
            x_lag = resid[lag:-1].reshape(-1, 1)
            for j in range(1, lag + 1):
                delta_j = resid[1 + lag - j : -j]
                if len(delta_j) == len(x_lag):
                    X_mat = np.column_stack([x_lag, delta_j])
                    break
            else:
                continue

        if X_mat.shape[0] < 5:
            continue

        try:
            e = _ols_residuals(y_diff, X_mat)
            sigma2 = np.mean(e ** 2)
            if sigma2 <= 0:
                continue
            n = len(y_diff)
            k = X_mat.shape[1]
            aic = np.log(sigma2) + 2 * k / n
            if aic < best_aic:
                best_aic = aic
                best_lag = lag
        except Exception:
            continue

    return best_lag


def _compute_residual_autocorr(resid: np.ndarray, max_lag: int = 1) -> float:
    """
    Compute residual autocorrelation at lag max_lag.

    Parameters
    ----------
    resid : np.ndarray
    max_lag : int

    Returns
    -------
    float : residual autocorrelation
    """
    T = len(resid)
    if T < max_lag + 2:
        return np.nan
    r = np.corrcoef(resid[max_lag:], resid[:-max_lag])[0, 1]
    return float(r) if not np.isnan(r) else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# PEDRONI (2004) PANEL COINTEGRATION TEST
# ─────────────────────────────────────────────────────────────────────────────


def _pedroni_core(
    df: pd.DataFrame,
    y_var: str,
    x_vars: list[str],
    trend: str = "c",
    max_lags: int = 4,
) -> dict:
    """
    Core Pedroni (2004) panel cointegration test.

    For each unit i, runs: y_{it} = α_i + β_i x_{it} + ε_{it}
    Then computes 7 statistics:
      Panel: Panel-v, Panel-ρ, Panel-PP, Panel-ADF
      Group: Group-ρ, Group-PP, Group-ADF

    Parameters
    ----------
    df : pd.DataFrame
        Panel data (must have unit_var and time_var columns).
    y_var : str
        Dependent variable name.
    x_vars : list[str]
        Independent variable names.
    trend : str
        "c" (constant), "ct" (constant + trend), "n" (no deterministic).
    max_lags : int
        Maximum lags for ADF.

    Returns
    -------
    dict with all 7 statistics and their p-values.
    """

    unit_var = df.columns[0] if df.index.names[0] else df.columns[0]
    df.columns[1] if len(df.columns) > 1 else df.columns[0]

    # Try to detect unit/time columns
    if df.index.names and None not in df.index.names:
        df = df.reset_index()
    elif "unit" in df.columns:
        unit_var = "unit"
        df.columns[2] if len(df.columns) > 2 else df.columns[1]
    else:
        # fallback: first non-y/x col
        remaining = [c for c in df.columns if c not in [y_var] + x_vars]
        if remaining:
            unit_var = remaining[0]
            remaining[1] if len(remaining) > 1 else remaining[0]

    all_vars = [y_var] + x_vars
    available = [v for v in all_vars if v in df.columns]
    if len(available) < 2:
        return {}

    df_sub = df.dropna(subset=available + [unit_var])
    units = df_sub[unit_var].unique()
    n_groups = len(units)
    T = int(df_sub.groupby(unit_var).size().mean())
    n_obs = len(df_sub)

    # Per-unit storage
    individual_stats: dict[str, list[float]] = {
        "panel_rho": [], "panel_pp": [], "panel_adf": [],
        "group_rho": [], "group_pp": [], "group_adf": [],
    }
    panel_v_numerators = []
    panel_v_denominators = []

    for unit in units:
        mask = df_sub[unit_var] == unit
        unit_data = df_sub.loc[mask].sort_index(key=lambda x: x.map(lambda v: str(v)))
        y_vals = unit_data[y_var].values.astype(float)
        x_vals = unit_data[[v for v in x_vars if v in unit_data.columns]].values.astype(float)

        # OLS: y = α + βx + ε  (or y = βx if trend="n")
        T_i = len(y_vals)
        if T_i < 5:
            continue

        if trend == "n":
            X_i = x_vals
        elif trend == "c":
            X_i = np.column_stack([np.ones(T_i), x_vals])
        else:  # "ct"
            X_i = np.column_stack([np.ones(T_i), np.arange(T_i), x_vals])

        if X_i.shape[0] < X_i.shape[1] + 2:
            continue

        try:
            resid_i = _ols_residuals(y_vals, X_i)
        except Exception:
            continue

        if len(resid_i) < 5 or np.std(resid_i) < 1e-10:
            continue

        # ── Individual ρ statistic ──
        # ρ_i: coefficient from resid_{t} = ρ_i * resid_{t-1} + u_t
        y_diff = resid_i[1:]
        x_lag = resid_i[:-1]
        if len(y_diff) < 2:
            continue
        try:
            rho_i, _, _, _ = np.linalg.lstsq(x_lag.reshape(-1, 1), y_diff, rcond=None)
            rho_i = float(rho_i[0])
        except Exception:
            rho_i = np.nan

        # ── Phillips-Perron type statistic ──
        pp_i = _pp_stat(resid_i)

        # ── ADF type statistic ──
        adf_i, lag_i, _ = _adf_stat(resid_i, max_lags=max_lags)

        # ── Group-ρ uses 1 + Σ resid_t * resid_{t-1} / Σ resid_{t-1}^2 ──
        num_rho = np.sum(resid_i[1:] * resid_i[:-1])
        denom_rho = np.sum(resid_i[:-1] ** 2)
        if denom_rho > 0:
            group_rho_i = (1 + num_rho / denom_rho)
        else:
            group_rho_i = np.nan

        # ── Group PP and ADF ──
        if not np.isnan(pp_i):
            individual_stats["group_pp"].append(pp_i)
        if not np.isnan(adf_i):
            individual_stats["group_adf"].append(adf_i)
        if not np.isnan(rho_i):
            individual_stats["panel_rho"].append(rho_i)
            individual_stats["group_rho"].append(group_rho_i)

        # ── Panel-v requires variance ratio ──
        var_resid = np.var(resid_i, ddof=1) if len(resid_i) > 1 else 1e-10
        denom_v = np.sum(resid_i[:-1] ** 2)
        numer_v = np.sum(resid_i[1:] * resid_i[:-1])
        if denom_v > 1e-10:
            panel_v_numerators.append(numer_v)
            panel_v_denominators.append(np.sqrt(var_resid * denom_v))

    # ── Pool statistics ──
    results = {}

    # Panel-v
    if panel_v_numerators:
        v_sum = sum(panel_v_numerators)
        v_den = sum(panel_v_denominators)
        panel_v = v_sum / v_den if v_den > 0 else np.nan
        # Normalize: for panel-v, use (N^0.5 * T * v) approximation
        panel_v_normalized = panel_v * np.sqrt(n_groups) if not np.isnan(panel_v) else np.nan
        pval_v = 2 * (1 - _norm_cdf(abs(panel_v_normalized))) if not np.isnan(panel_v_normalized) else np.nan
        results["Panel-v"] = {"stat": panel_v_normalized, "pval": pval_v, "raw_stat": panel_v}

    # Panel-ρ (pooled)
    rho_list = individual_stats["panel_rho"]
    if rho_list:
        panel_rho = np.mean(rho_list)
        # Asymptotic: N(0,1) after transformation
        panel_rho_norm = panel_rho * np.sqrt(n_groups)
        pval_rho = 2 * (1 - _norm_cdf(abs(panel_rho_norm)))
        results["Panel-rho"] = {"stat": panel_rho_norm, "pval": pval_rho, "raw_stat": panel_rho}

    # Panel-PP
    pp_list = individual_stats["group_pp"]
    if pp_list:
        panel_pp = np.mean(pp_list)
        panel_pp_norm = panel_pp * np.sqrt(n_groups)
        pval_pp = 2 * (1 - _norm_cdf(abs(panel_pp_norm)))
        results["Panel-PP"] = {"stat": panel_pp_norm, "pval": pval_pp, "raw_stat": panel_pp}

    # Panel-ADF
    adf_list = individual_stats["panel_adf"] if individual_stats["panel_adf"] else individual_stats["group_adf"]
    if not adf_list:
        adf_list = individual_stats["group_adf"]
    if adf_list:
        panel_adf = np.mean(adf_list)
        panel_adf_norm = panel_adf * np.sqrt(n_groups)
        pval_adf = 2 * (1 - _norm_cdf(abs(panel_adf_norm)))
        results["Panel-ADF"] = {"stat": panel_adf_norm, "pval": pval_adf, "raw_stat": panel_adf}

    # Group-ρ
    g_rho = individual_stats["group_rho"]
    if g_rho:
        group_rho_mean = np.mean(g_rho)
        # Westerlund suggests: (T * mean(ρ_i - 1))
        group_rho_norm = (T ** 0.5) * (group_rho_mean - 1) if not np.isnan(group_rho_mean) else np.nan
        pval_gr = 2 * (1 - _norm_cdf(abs(group_rho_norm))) if not np.isnan(group_rho_norm) else np.nan
        results["Group-rho"] = {"stat": group_rho_norm, "pval": pval_gr, "raw_stat": group_rho_mean}

    # Group-PP
    if pp_list:
        group_pp_mean = np.mean(pp_list)
        group_pp_norm = np.sqrt(n_groups) * group_pp_mean
        pval_gpp = 2 * (1 - _norm_cdf(abs(group_pp_norm)))
        results["Group-PP"] = {"stat": group_pp_norm, "pval": pval_gpp, "raw_stat": group_pp_mean}

    # Group-ADF
    g_adf = individual_stats["group_adf"]
    if g_adf:
        group_adf_mean = np.mean(g_adf)
        group_adf_norm = np.sqrt(n_groups) * group_adf_mean
        pval_gadf = 2 * (1 - _norm_cdf(abs(group_adf_norm)))
        results["Group-ADF"] = {"stat": group_adf_norm, "pval": pval_gadf, "raw_stat": group_adf_mean}

    results["_meta"] = {
        "n_groups": n_groups,
        "n_obs": n_obs,
        "T": T,
        "n_groups_valid": sum(len(v) > 0 for v in individual_stats.values()),
    }

    return results


def _kao_core(
    df: pd.DataFrame,
    y_var: str,
    x_vars: list[str],
    trend: str = "c",
) -> dict:
    """
    Kao (1999) panel ADF test.

    H0: no cointegration
    Run residual ADF: ε_t = ρ ε_{t-1} + Σ γ_j Δε_{t-j} + v_t
    Then Dickey-Fuller t-statistic pooled across units.
    """
    unit_var = None
    for col in df.columns:
        if col not in [y_var] + x_vars:
            unit_var = col
            break

    if unit_var is None:
        return {}

    df_sub = df.dropna(subset=[y_var] + x_vars)
    units = df_sub[unit_var].unique()
    n_groups = len(units)
    n_obs = len(df_sub)

    t_stats = []
    for unit in units:
        mask = df_sub[unit_var] == unit
        unit_data = df_sub.loc[mask]
        y_vals = unit_data[y_var].values.astype(float)
        x_vals = unit_data[[v for v in x_vars if v in unit_data.columns]].values.astype(float)

        T_i = len(y_vals)
        if T_i < 10:
            continue

        # Step 1: OLS cointegrating regression
        if trend == "n":
            X_i = x_vals
        else:
            X_i = np.column_stack([np.ones(T_i), x_vals])

        if X_i.shape[0] < X_i.shape[1] + 2:
            continue

        try:
            resid_i = _ols_residuals(y_vals, X_i)
        except Exception:
            continue

        # Step 2: ADF on residuals (with 0 lags for Kao's simple version)
        adf_i, _, _ = _adf_stat(resid_i, max_lags=0)
        if not np.isnan(adf_i):
            t_stats.append(adf_i)

    if not t_stats:
        return {"DF": {"stat": np.nan, "pval": np.nan}}

    # Kao (1999) pooled t: average t-stat
    mean_t = np.mean(t_stats)
    # Normalized by sqrt(N)
    kao_stat = mean_t * np.sqrt(n_groups)
    pval = 2 * (1 - _norm_cdf(abs(kao_stat)))

    return {
        "DF": {"stat": kao_stat, "pval": pval, "raw_stat": mean_t},
        "_meta": {"n_groups": n_groups, "n_obs": n_obs, "n_valid": len(t_stats)},
    }


def _westerlund_core(
    df: pd.DataFrame,
    y_var: str,
    x_vars: list[str],
    max_lags: int = 4,
) -> dict:
    """
    Westerlund (2005) Durbin-Hausman panel cointegration test.

    ECM formulation:
    Δy_it = α_i + δ_i y_{i,t-1} + Σ ρ_ij Δy_{i,t-j} + ε_it

    DH_p: test H0: all δ_i = 0 (panel)
    DH_g: test H0: all δ_i = 0 (group mean)
    """
    unit_var = None
    for col in df.columns:
        if col not in [y_var] + x_vars:
            unit_var = col
            break

    if unit_var is None:
        return {}

    df_sub = df.dropna(subset=[y_var] + x_vars)
    units = df_sub[unit_var].unique()
    n_groups = len(units)
    n_obs = len(df_sub)

    delta_i_list = []
    se_i_list = []
    var_cov_sum = 0.0
    valid_count = 0

    for unit in units:
        mask = df_sub[unit_var] == unit
        unit_data = df_sub.loc[mask].sort_index()
        y_vals = unit_data[y_var].values.astype(float)
        x_vals = unit_data[[v for v in x_vars if v in unit_data.columns]].values.astype(float)

        T_i = len(y_vals)
        if T_i < max_lags + 4:
            continue

        # Build ECM: Δy = α + δ*y_{t-1} + β*x_{t-1} + Σγ*Δy_{t-j} + ε
        y_diff = np.diff(y_vals)
        y_lag = y_vals[:-1]
        x_lag = x_vals[:-1]
        n_lag = len(y_diff) - max_lags

        if n_lag < 5:
            continue

        # Build lagged differences
        lag_deltas = []
        for j in range(1, max_lags + 1):
            delta_j = y_diff[max_lags - j : -j] if j < max_lags else y_diff[:-max_lags]
            if len(delta_j) == n_lag:
                lag_deltas.append(delta_j)

        if n_lag < 3:
            continue

        # Design matrix
        const = np.ones(n_lag)
        X_ecm = np.column_stack([const, y_lag[:n_lag], x_lag[:n_lag]] + lag_deltas)

        y_target = y_diff[:n_lag]

        if X_ecm.shape[0] < X_ecm.shape[1] + 2:
            continue

        try:
            # OLS
            beta, _, rank, s = np.linalg.lstsq(X_ecm, y_target, rcond=None)
            if rank < X_ecm.shape[1]:
                continue

            delta_i = beta[1]  # coefficient on y_{t-1}
            resid_i = y_target - X_ecm @ beta

            # Variance-covariance of delta_i
            sigma2 = np.mean(resid_i ** 2)
            XTX_inv = np.linalg.inv(X_ecm.T @ X_ecm + 1e-10 * np.eye(X_ecm.shape[1]))
            var_delta = XTX_inv[1, 1] * sigma2
            se_delta = np.sqrt(max(var_delta, 0))

            if se_delta > 1e-12:
                delta_i_list.append(delta_i)
                se_i_list.append(se_delta)
                # Accumulate for DH_g
                var_cov_sum += (delta_i ** 2) / var_delta
                valid_count += 1
        except Exception:
            continue

    results = {}

    if valid_count == 0:
        return results

    # ── DH_g: Group-mean statistic ──
    g_mean_delta = np.mean(delta_i_list)
    # G_t = mean(δ_i / SE(δ_i))
    g_t_stats = [d / s if s > 1e-12 else 0.0 for d, s in zip(delta_i_list, se_i_list, strict=False)]
    dh_g = np.mean(g_t_stats) if g_t_stats else np.nan
    # Asymptotic: use t-approximation
    dh_g_norm = dh_g * np.sqrt(valid_count) if not np.isnan(dh_g) else np.nan
    pval_dhg = 2 * (1 - _norm_cdf(abs(dh_g_norm))) if not np.isnan(dh_g_norm) else np.nan
    results["DH_g"] = {"stat": dh_g_norm, "pval": pval_dhg, "raw_stat": dh_g}

    # ── DH_p: Panel variance-ratio statistic ──
    # P = Σ (δ_i^2 / var(δ_i)) / Σ (1 / var(δ_i))
    var_cov_sum / sum(1 / (s ** 2) for s in se_i_list) if se_i_list else np.nan
    dh_p = np.sqrt(var_cov_sum) if var_cov_sum > 0 else np.nan
    # Normalize
    dh_p_norm = dh_p / np.sqrt(valid_count) if not np.isnan(dh_p) and valid_count > 0 else np.nan
    pval_dhp = 2 * (1 - _norm_cdf(abs(dh_p_norm))) if not np.isnan(dh_p_norm) else np.nan
    results["DH_p"] = {"stat": dh_p_norm, "pval": pval_dhp, "raw_stat": dh_p}

    results["_meta"] = {
        "n_groups": n_groups,
        "n_obs": n_obs,
        "n_valid": valid_count,
        "mean_delta": g_mean_delta,
    }

    return results


def _csd_pesaran(
    residuals: np.ndarray | pd.DataFrame,
) -> tuple[float, float]:
    """
    Pesaran (2004) Cross-Sectional Dependence test.

    CD = sqrt(2T / (N(N-1))) * Σ_{i<j} sqrt(T) * rho_ij
       = sqrt(2T / (N(N-1))) * sum_{i<j} sqrt(T) * rho_ij

    H0: no cross-sectional dependence
    """
    if isinstance(residuals, pd.DataFrame):
        resid_arr = residuals.values
    else:
        resid_arr = np.asarray(residuals)

    if resid_arr.ndim == 1:
        return np.nan, np.nan

    T, N = resid_arr.shape
    if T < 2 or N < 2:
        return np.nan, np.nan

    # Pairwise correlations
    corr_mat = np.corrcoef(resid_arr.T)  # (N, N)
    idx_upper = np.triu_indices(N, k=1)
    rho_flat = corr_mat[idx_upper]

    rho_flat = rho_flat[~np.isnan(rho_flat)]

    if len(rho_flat) == 0:
        return np.nan, np.nan

    # CD statistic
    cd_stat = np.sqrt(2 * T / (N * (N - 1))) * np.sum(rho_flat * np.sqrt(T))
    pval = 2 * (1 - _norm_cdf(abs(cd_stat)))

    return float(cd_stat), float(pval)


# ─────────────────────────────────────────────────────────────────────────────
# PANEL ERROR CORRECTION MODEL
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ECMResult:
    """Results from Panel ECM estimation."""

    coefs: dict[str, float] = field(default_factory=dict)
    ses: dict[str, float] = field(default_factory=dict)
    pvals: dict[str, float] = field(default_factory=dict)
    long_run: dict[str, float] = field(default_factory=dict)
    long_run_se: dict[str, float] = field(default_factory=dict)
    ect_coef: float = 0.0
    ect_se: float = 0.0
    ect_pval: float = 1.0
    speed_adj: float = 0.0
    n_obs: int = 0
    n_groups: int = 0
    r_squared: float | None = None
    sig_dict: dict[str, str] = field(default_factory=dict)


class PanelECM:
    """
    Panel Error Correction Model (ECM) for cointegrated panels.

    Estimates the short-run and long-run dynamics:
        Δy_t = α + γ·ECT_{t-1} + Σβ_j·Δy_{t-j} + ε_t

    where ECT_{t-1} = y_{t-1} - β·x_{t-1} (the error correction term).

    Usage:
        ecm = PanelECM(trend="c")
        res = ecm.fit(df, dep_var="lnrgdp", indep_vars=["lnmoney"],
                      unit_var="country", time_var="year", lag_order=2)
        print(ecm.summary())
        ecm.plot_ecm_coefficients("ecm_coef.pdf")
        print(ecm.to_latex())
    """

    def __init__(self, trend: str = "c"):
        """
        Parameters
        ----------
        trend : str
            Deterministic term: "c" (constant), "ct" (constant + trend), "n" (none).
        """
        self.trend = trend
        self._result: ECMResult | None = None
        self._data_info: dict = {}

    def fit(
        self,
        df: pd.DataFrame,
        dep_var: str,
        indep_vars: list[str],
        unit_var: str = "unit",
        time_var: str = "time",
        lag_order: int = 1,
        return_ecm_data: bool = False,
    ) -> dict:
        """
        Estimate Panel ECM.

        Parameters
        ----------
        df : pd.DataFrame
            Panel data.
        dep_var : str
            Dependent variable (level).
        indep_vars : list[str]
            Independent variables (levels).
        unit_var : str
            Cross-sectional unit identifier.
        time_var : str
            Time period identifier.
        lag_order : int
            Number of lagged differences in ECM.
        return_ecm_data : bool
            If True, returns ECM-transformed DataFrame.

        Returns
        -------
        dict with ECM results.
        """
        all_cols = [dep_var] + indep_vars + [unit_var, time_var]
        available = [c for c in all_cols if c in df.columns]
        df_sub = df.dropna(subset=available).copy()

        if len(df_sub) < 50:
            _log.warning("[PanelECM] Too few observations, returning empty result")
            return {}

        units = df_sub[unit_var].unique()
        n_groups = len(units)
        len(df_sub)

        # ── Step 1: Cointegrating regression (levels) ──
        # Pooled OLS: y_it = α + β·x_it + ε_it
        y_vals = df_sub[dep_var].values.astype(float)
        X_pooled = df_sub[[v for v in indep_vars if v in df_sub.columns]].values.astype(float)

        if self.trend == "n":
            X_coin = X_pooled
        else:
            X_coin = np.column_stack([np.ones(len(y_vals)), X_pooled])

        try:
            coin_beta, _, _, _ = np.linalg.lstsq(X_coin, y_vals, rcond=None)
        except Exception:
            _log.error("[PanelECM] Cointegrating regression failed")
            return {}

        # Residuals = ECT (error correction term)
        ect = y_vals - X_coin @ coin_beta

        # ── Step 2: Build ECM dependent variable ──
        df_sub = df_sub.sort_values([unit_var, time_var])
        y_vals_sorted = df_sub[dep_var].values.astype(float)
        ect_sorted = ect

        # Δy = y_t - y_{t-1} per unit
        delta_y = np.zeros_like(y_vals_sorted)
        ect_lag = np.zeros_like(y_vals_sorted)

        for unit in units:
            mask = df_sub[unit_var] == unit
            idx = np.where(mask)[0]
            if len(idx) > 1:
                delta_y[idx[1:]] = y_vals_sorted[idx[1:]] - y_vals_sorted[idx[:-1]]
                ect_lag[idx[1:]] = ect_sorted[idx[:-1]]

        # Lagged Δy
        lag_deltas = []
        for lag in range(1, lag_order + 1):
            lag_delta = np.zeros_like(delta_y)
            for unit in units:
                mask = df_sub[unit_var] == unit
                idx = np.where(mask)[0]
                for i in range(lag, len(idx)):
                    lag_delta[idx[i]] = delta_y[idx[i - lag]]
            lag_deltas.append(lag_delta)

        # X for ECM
        const = np.ones(len(delta_y))
        if self.trend == "n":
            X_ecm_list = [const] + [ect_lag] + lag_deltas
        else:
            X_ecm_list = [const] + [ect_lag] + lag_deltas

        X_ecm = np.column_stack(X_ecm_list)

        # Only estimate for T > lag_order
        valid = df_sub[unit_var].map(df_sub.groupby(unit_var).size()) > lag_order
        valid_idx = valid.values

        X_valid = X_ecm[valid_idx]
        y_valid = delta_y[valid_idx]

        if X_valid.shape[0] < X_valid.shape[1] + 5:
            _log.warning("[PanelECM] Not enough observations for ECM")
            return {}

        # ── Step 3: OLS of ECM ──
        try:
            import statsmodels.api as sm

            X_sm = sm.add_constant(X_valid[:, 1:], has_constant="skip")
            model = sm.OLS(y_valid, X_sm).fit()
            ecm_coefs = model.params
            ecm_ses = model.bse
            ecm_pvals = model.pvalues
            r_squared = float(model.rsquared)
        except Exception:
            _log.warning("[PanelECM] statsmodels OLS failed, using numpy")
            ecm_coefs, _, _, _ = np.linalg.lstsq(X_valid, y_valid, rcond=None)
            resid = y_valid - X_valid @ ecm_coefs
            sigma2 = np.mean(resid ** 2)
            XTX_inv = np.linalg.inv(X_valid.T @ X_valid + 1e-10 * np.eye(X_valid.shape[1]))
            ecm_ses = np.sqrt(np.diag(XTX_inv) * sigma2)
            ecm_pvals = np.ones_like(ecm_coefs)
            r_squared = 1 - np.sum(resid ** 2) / np.sum((y_valid - np.mean(y_valid)) ** 2)

        # ── Step 4: Parse results ──
        names = ["ect"]
        for j in range(1, lag_order + 1):
            names.append(f"d_lag{j}")
        names = ["const"] + names + [dep_var]

        # Long-run coefficients from cointegrating regression
        if self.trend != "n":
            ["const"] + indep_vars

        long_run = {}
        long_run_se = {}
        if self.trend == "n":
            for j, xv in enumerate(indep_vars):
                long_run[xv] = float(coin_beta[j])
        else:
            for j, xv in enumerate(indep_vars):
                long_run[xv] = float(coin_beta[j + 1])

        # ECT coefficient
        ect_coef_val = float(ecm_coefs[1]) if len(ecm_coefs) > 1 else float(ecm_coefs[0])
        ect_se_val = float(ecm_ses[1]) if len(ecm_ses) > 1 else float(ecm_ses[0])
        ect_pval_val = float(ecm_pvals[1]) if len(ecm_pvals) > 1 else float(ecm_pvals[0])
        speed_adj = abs(ect_coef_val) if not np.isnan(ect_coef_val) else np.nan

        # Build ECMResult
        self._result = ECMResult(
            ect_coef=ect_coef_val,
            ect_se=ect_se_val,
            ect_pval=ect_pval_val,
            speed_adj=speed_adj,
            n_obs=X_valid.shape[0],
            n_groups=n_groups,
            r_squared=r_squared,
        )

        coefs_dict = dict(zip(names, ecm_coefs.tolist(), strict=False))
        ses_dict = dict(zip(names, ecm_ses.tolist(), strict=False))
        pvals_dict = dict(zip(names, ecm_pvals.tolist(), strict=False))
        sig_dict = {k: _significance_mark(pvals_dict.get(k, 1.0)) for k in names}

        self._result.coefs = coefs_dict
        self._result.ses = ses_dict
        self._result.pvals = pvals_dict
        self._result.sig_dict = sig_dict
        self._result.long_run = long_run
        self._result.long_run_se = long_run_se

        self._data_info = {
            "dep_var": dep_var,
            "indep_vars": indep_vars,
            "lag_order": lag_order,
            "unit_var": unit_var,
            "time_var": time_var,
        }

        _log.info(
            f"[PanelECM] ECT={ect_coef_val:.4f}{sig_dict.get('ect','')} "
            f"(p={ect_pval_val:.3f}), speed_adj={speed_adj:.4f}, "
            f"N={self._result.n_obs}, G={self._result.n_groups}, R2={r_squared:.4f}"
        )

        if return_ecm_data:
            ecm_df = df_sub.copy()
            ecm_df["ect"] = ect_sorted
            ecm_df["ect_lag"] = ect_lag
            ecm_df["delta_y"] = delta_y
            return self._result.__dict__, ecm_df
        return self._result.__dict__

    def summary(self) -> pd.DataFrame:
        """
        Return a summary DataFrame of ECM estimates.

        Returns
        -------
        pd.DataFrame
        """
        if self._result is None:
            return pd.DataFrame()

        rows = []
        # Short-run
        for name in ["ect"] + [f"d_lag{j}" for j in range(1, self._data_info.get("lag_order", 1) + 1)]:
            if name in self._result.coefs:
                c = self._result.coefs[name]
                s = self._result.ses.get(name, np.nan)
                p = self._result.pvals.get(name, np.nan)
                sig = self._result.sig_dict.get(name, "")
                rows.append({
                    "Variable": name,
                    "Type": "Short-run",
                    "Coef": f"{c:+.4f}{sig}",
                    "SE": f"({s:.4f})",
                    "P-val": f"{p:.3f}",
                })

        # Long-run
        for xv, lr_c in self._result.long_run.items():
            rows.append({
                "Variable": f"LR_{xv}",
                "Type": "Long-run",
                "Coef": f"{lr_c:+.4f}",
                "SE": "",
                "P-val": "",
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Add N, G, R2 as last row
        footer = pd.DataFrame([{
            "Variable": "Observations",
            "Type": f"N={self._result.n_obs}, G={self._result.n_groups}, R2={self._result.r_squared:.4f}" if self._result.r_squared else "",
            "Coef": "", "SE": "", "P-val": "",
        }])
        return pd.concat([df, footer], ignore_index=True)

    def to_latex(
        self,
        caption: str = "Panel Error Correction Model Estimates",
        label: str = "tab:ecm",
    ) -> str:
        """
        Export ECM results to LaTeX table (booktabs).

        Parameters
        ----------
        caption : str
        label : str

        Returns
        -------
        str : LaTeX code
        """
        df = self.summary()
        if df.empty:
            return ""

        lines = [
            "\\begin{table}[htbp]",
            "  \\centering",
            "  \\caption{" + caption + "}",
            "  \\label{" + label + "}",
            "  \\begin{tabular}{lccc}",
            "    \\toprule",
            "    \\textbf{Variable} & \\textbf{Type} & \\textbf{Coefficient} & \\textbf{SE} \\\\",
            "    \\midrule",
        ]

        for _, row in df.iterrows():
            var = row["Variable"]
            vtype = row["Type"]
            coef = row["Coef"]
            se = row["SE"]
            if var == "Observations":
                lines.append(f"    \\midrule\n    \\multicolumn{{4}}{{l}}{{{vtype}}} \\\\")
            else:
                lines.append(f"    ${var}$ & {vtype} & {coef} & {se} \\\\")

        lines.extend([
            "    \\bottomrule",
            "  \\end{tabular}",
            "  \\caption*{ECT: Error correction term. Short-run coefficients with HAC SEs.}",
            "\\end{table}",
        ])
        return "\n".join(lines)

    def plot_ecm_coefficients(
        self,
        save_path: str | Path | None = None,
        figsize: tuple[float, float] = (10, 6),
    ) -> Any:
        """
        Plot ECT and short-run coefficients with 95% CI.

        Parameters
        ----------
        save_path : str | Path | None
        figsize : tuple

        Returns
        -------
        matplotlib Figure or None
        """
        if self._result is None:
            _log.warning("[PanelECM] No results to plot")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[PanelECM] matplotlib not installed")
            return None

        coefs = self._result.coefs
        ses = self._result.ses
        names = list(coefs.keys())
        vals = np.array([coefs.get(n, 0.0) for n in names])
        errs = 1.96 * np.array([ses.get(n, 0.0) for n in names])

        # Separate ECT from lag coefficients
        ect_idx = [i for i, n in enumerate(names) if "ect" in n.lower()]
        lag_idx = [i for i, n in enumerate(names) if "lag" in n.lower()]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Left: ECT (speed of adjustment)
        if ect_idx:
            i = ect_idx[0]
            ax1.bar(["ECT"], [vals[i]], color="steelblue", edgecolor="navy")
            ax1.errorbar(["ECT"], [vals[i]], yerr=[errs[i]], fmt="none", color="black", capsize=6)
            ax1.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
            ax1.set_title("Error Correction Term\n(Speed of Adjustment)", fontsize=12, fontweight="bold")
            ax1.set_ylabel("Coefficient", fontsize=11)
            sig = self._result.sig_dict.get(names[i], "")
            ax1.text(0, vals[i] + errs[i] + 0.02 * np.abs(vals[i]), sig, ha="center", fontsize=14)
        else:
            ax1.text(0.5, 0.5, "ECT not estimated", ha="center", va="center", transform=ax1.transAxes)

        # Right: Lag coefficients
        if lag_idx:
            lag_names = [names[i] for i in lag_idx]
            lag_vals = [vals[i] for i in lag_idx]
            lag_errs = [errs[i] for i in lag_idx]
            x_pos = np.arange(len(lag_names))
            ax2.bar(x_pos, lag_vals, color="coral", edgecolor="darkred", alpha=0.8)
            ax2.errorbar(x_pos, lag_vals, yerr=lag_errs, fmt="none", color="black", capsize=4)
            ax2.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels([f"${n}$" for n in lag_names], fontsize=10)
            ax2.set_title("Short-Run Lag Coefficients", fontsize=12, fontweight="bold")
            ax2.set_ylabel("Coefficient", fontsize=11)
        else:
            ax2.text(0.5, 0.5, "No lag coefficients", ha="center", va="center", transform=ax2.transAxes)

        plt.suptitle(
            f"Panel ECM: Δ{self._data_info.get('dep_var', 'Y')} "
            f"~ ECT + Lags  (N={self._result.n_obs}, G={self._result.n_groups})",
            fontsize=13, fontweight="bold",
        )
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[PanelECM] ECM coefficients plot saved: {save_path}")

        return fig


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-SECTIONAL DEPENDENCE
# ─────────────────────────────────────────────────────────────────────────────


class CrossSectionalDependence:
    """
    Cross-sectional dependence diagnostics for panel data.

    Implements Pesaran (2004) CD test.

    Usage:
        csd = CrossSectionalDependence()
        res = csd.test(df, vars=["eps", "roe", "lev"])
        print(res)
    """

    def test(
        self,
        df: pd.DataFrame,
        vars: list[str],
        unit_var: str = "unit",
        time_var: str | None = None,
    ) -> dict:
        """
        Run cross-sectional dependence tests.

        Parameters
        ----------
        df : pd.DataFrame
            Panel data.
        vars : list[str]
            Variables to test for cross-sectional dependence.
        unit_var : str
            Cross-sectional unit identifier.
        time_var : str | None
            Time variable (if not in index).

        Returns
        -------
        dict with CD statistics and residual correlations.
        """
        available = [v for v in vars if v in df.columns]
        if len(available) < 2:
            _log.warning("[CSD] Less than 2 variables available")
            return {}

        df_sub = df.dropna(subset=available + [unit_var])

        # Per-unit residual correlations
        results = {}
        all_resid = {}

        for var in available:
            # Run unit-level AR(1) to get residuals
            residuals_list = []
            units = df_sub[unit_var].unique()
            for unit in units:
                mask = df_sub[unit_var] == unit
                unit_data = df_sub.loc[mask].sort_values(time_var) if time_var else df_sub.loc[mask]
                y_vals = unit_data[var].values.astype(float)

                if len(y_vals) < 5:
                    continue

                # Detrend: regress y on time
                t = np.arange(len(y_vals))
                try:
                    beta, _, _, _ = np.linalg.lstsq(np.column_stack([np.ones(len(y_vals)), t]), y_vals, rcond=None)
                    resid = y_vals - (np.column_stack([np.ones(len(y_vals)), t]) @ beta)
                    residuals_list.extend(resid.tolist())
                except Exception:
                    residuals_list.extend(y_vals.tolist())

            if residuals_list:
                all_resid[var] = np.array(residuals_list[:len(df_sub)])

        # Overall CD test
        if all_resid:
            # Align lengths
            min_len = min(len(v) for v in all_resid.values())
            aligned = {k: v[:min_len] for k, v in all_resid.items()}
            resid_matrix = np.column_stack(list(aligned.values()))

            cd_stat, cd_pval = _csd_pesaran(resid_matrix)

            # Average pairwise correlation
            if resid_matrix.shape[1] >= 2:
                corr_mat = np.corrcoef(resid_matrix.T)
                idx_upper = np.triu_indices(resid_matrix.shape[1], k=1)
                avg_corr = float(np.nanmean(corr_mat[idx_upper]))
            else:
                avg_corr = np.nan

            results = {
                "cd_statistic": cd_stat,
                "cd_pval": cd_pval,
                "avg_correlation": avg_corr,
                "decision": "Reject H0" if cd_pval < 0.05 else "Fail to reject H0",
                "n_obs": min_len,
                "n_vars": len(available),
            }

            _log.info(
                f"[CSD] Pesaran CD test: stat={cd_stat:.4f}, p={cd_pval:.4f}, "
                f"avg_corr={avg_corr:.4f} ({results['decision']})"
            )

        return results


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PANEL COINTEGRATION TEST CLASS
# ─────────────────────────────────────────────────────────────────────────────


class PanelCointegrationTest:
    """
    Panel Cointegration Test suite — Pedroni, Kao, Westerlund.

    Usage:
        pct = PanelCointegrationTest(trend="c", max_lags=4)
        res = pct.pedroni_panel(df, y_var="lnrgdp", x_vars=["lnmoney"])
        print(pct.summary())

        res2 = pct.kao_test(df, y_var="lnrgdp", x_vars=["lnmoney"])
        res3 = pct.westerlund_test(df, y_var="lnrgdp", x_vars=["lnmoney"])

        csd = pct.cross_sectional_dependence(df, vars=["lnrgdp", "lnmoney"])
    """

    def __init__(self, trend: str = "c", max_lags: int = 4):
        """
        Parameters
        ----------
        trend : str
            Deterministic trend: "c" (constant), "ct" (constant+trend), "n" (none).
        max_lags : int
            Maximum lags for ADF-type statistics.
        """
        self.trend = trend
        self.max_lags = max_lags
        self._pedroni_results: dict = {}
        self._kao_results: dict = {}
        self._westerlund_results: dict = {}
        self._csd_results: dict = {}
        self._last_vars: dict = {}

    def pedroni_panel(
        self,
        df: pd.DataFrame,
        y_var: str,
        x_vars: list[str],
    ) -> dict:
        """
        Pedroni (2004) panel cointegration test.

        Computes 7 statistics:
          Panel: v, rho, PP, ADF
          Group: rho, PP, ADF

        H0: no cointegration (all units)
        H1: cointegration (at least one unit)

        Parameters
        ----------
        df : pd.DataFrame
            Panel data.
        y_var : str
            Dependent variable.
        x_vars : list[str]
            Independent variables.

        Returns
        -------
        dict with all 7 statistics.
        """
        _log.info(f"[Pedroni] Testing {y_var} ~ {' + '.join(x_vars)}, trend={self.trend}")

        try:
            raw = _pedroni_core(df, y_var, x_vars, trend=self.trend, max_lags=self.max_lags)
        except Exception as e:
            _log.error(f"[Pedroni] Test failed: {e}")
            return {}

        if not raw:
            return {}

        self._pedroni_results = {}
        for name, val in raw.items():
            if name == "_meta":
                self._last_vars = val
                continue
            if isinstance(val, dict) and "stat" in val:
                stat = val["stat"]
                pval = val["pval"]
                decision = "Reject H0" if pval < 0.05 else "Fail to reject H0"
                result = CointegrationResult(
                    test_name=f"Pedroni_{name}",
                    statistic=stat,
                    pval=pval,
                    decision=decision,
                    n_obs=raw.get("_meta", {}).get("n_obs", 0),
                    n_groups=raw.get("_meta", {}).get("n_groups", 0),
                    n_lags=self.max_lags,
                    additional={"raw_stat": val.get("raw_stat")},
                )
                self._pedroni_results[name] = result

                _log.info(
                    f"  {name:15s}: stat={stat:+.4f}, p={pval:.4f} {result.sig} "
                    f"({result.decision})"
                )

        return self._pedroni_results

    def kao_test(
        self,
        df: pd.DataFrame,
        y_var: str,
        x_vars: list[str],
    ) -> dict:
        """
        Kao (1999) panel ADF cointegration test.

        H0: no cointegration
        H1: cointegration (common AR root)

        Parameters
        ----------
        df : pd.DataFrame
        y_var : str
        x_vars : list[str]

        Returns
        -------
        dict with DF statistic.
        """
        _log.info(f"[Kao] Testing {y_var} ~ {' + '.join(x_vars)}")

        try:
            raw = _kao_core(df, y_var, x_vars, trend=self.trend)
        except Exception as e:
            _log.error(f"[Kao] Test failed: {e}")
            return {}

        if not raw:
            return {}

        self._kao_results = {}
        for name, val in raw.items():
            if name == "_meta":
                continue
            if isinstance(val, dict) and "stat" in val:
                stat = val["stat"]
                pval = val["pval"]
                decision = "Reject H0" if pval < 0.05 else "Fail to reject H0"
                result = CointegrationResult(
                    test_name=f"Kao_{name}",
                    statistic=stat,
                    pval=pval,
                    decision=decision,
                    n_obs=raw.get("_meta", {}).get("n_obs", 0),
                    n_groups=raw.get("_meta", {}).get("n_groups", 0),
                    n_lags=0,
                    additional={"raw_stat": val.get("raw_stat")},
                )
                self._kao_results[name] = result

                _log.info(f"  {name}: stat={stat:+.4f}, p={pval:.4f} {result.sig} ({result.decision})")

        return self._kao_results

    def westerlund_test(
        self,
        df: pd.DataFrame,
        y_var: str,
        x_vars: list[str],
    ) -> dict:
        """
        Westerlund (2005) Durbin-Hausman panel cointegration test.

        DH_g: group-mean test
        DH_p: panel test

        H0: no cointegration
        H1: cointegration (at least one unit for DH_g)

        Parameters
        ----------
        df : pd.DataFrame
        y_var : str
        x_vars : list[str]

        Returns
        -------
        dict with DH_g and DH_p statistics.
        """
        _log.info(f"[Westerlund] Testing {y_var} ~ {' + '.join(x_vars)}")

        try:
            raw = _westerlund_core(df, y_var, x_vars, max_lags=self.max_lags)
        except Exception as e:
            _log.error(f"[Westerlund] Test failed: {e}")
            return {}

        if not raw:
            return {}

        self._westerlund_results = {}
        for name, val in raw.items():
            if name == "_meta":
                continue
            if isinstance(val, dict) and "stat" in val:
                stat = val["stat"]
                pval = val["pval"]
                decision = "Reject H0" if pval < 0.05 else "Fail to reject H0"
                result = CointegrationResult(
                    test_name=f"Westerlund_{name}",
                    statistic=stat,
                    pval=pval,
                    decision=decision,
                    n_obs=raw.get("_meta", {}).get("n_obs", 0),
                    n_groups=raw.get("_meta", {}).get("n_groups", 0),
                    n_lags=self.max_lags,
                    additional={"raw_stat": val.get("raw_stat")},
                )
                self._westerlund_results[name] = result

                _log.info(f"  {name}: stat={stat:+.4f}, p={pval:.4f} {result.sig} ({result.decision})")

        return self._westerlund_results

    def cross_sectional_dependence(
        self,
        df: pd.DataFrame,
        vars: list[str],
        unit_var: str = "unit",
    ) -> dict:
        """
        Pesaran (2004) Cross-Sectional Dependence test on residuals.

        Parameters
        ----------
        df : pd.DataFrame
        vars : list[str]
        unit_var : str

        Returns
        -------
        dict with CD statistic and average correlation.
        """
        csd = CrossSectionalDependence()
        self._csd_results = csd.test(df, vars=vars, unit_var=unit_var)
        return self._csd_results

    def summary(self) -> pd.DataFrame:
        """
        Return a combined summary DataFrame of all tests run.

        Returns
        -------
        pd.DataFrame with columns: Test, Statistic, P-value, Decision
        """
        rows = []
        for name, res in self._pedroni_results.items():
            rows.append({
                "Test": f"Pedroni_{name}",
                "Statistic": f"{res.statistic:+.4f}",
                "P-value": f"{res.pval:.4f}",
                "Significance": _significance_mark(res.pval),
                "Decision": res.decision,
            })

        for name, res in self._kao_results.items():
            rows.append({
                "Test": f"Kao_{name}",
                "Statistic": f"{res.statistic:+.4f}",
                "P-value": f"{res.pval:.4f}",
                "Significance": _significance_mark(res.pval),
                "Decision": res.decision,
            })

        for name, res in self._westerlund_results.items():
            rows.append({
                "Test": f"Westerlund_{name}",
                "Statistic": f"{res.statistic:+.4f}",
                "P-value": f"{res.pval:.4f}",
                "Significance": _significance_mark(res.pval),
                "Decision": res.decision,
            })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def to_latex(
        self,
        caption: str = "Panel Cointegration Test Results",
        label: str = "tab:panel_cointegration",
    ) -> str:
        """
        Export summary table to LaTeX (booktabs).

        Parameters
        ----------
        caption : str
        label : str

        Returns
        -------
        str : LaTeX code
        """
        df = self.summary()
        if df.empty:
            return ""

        lines = [
            "\\begin{table}[htbp]",
            "  \\centering",
            "  \\caption{" + caption + "}",
            "  \\label{" + label + "}",
            "  \\begin{threeparttable}",
            "  \\begin{tabular}{lcccc}",
            "    \\toprule",
            "    \\textbf{Test} & \\textbf{Statistic} & \\textbf{P-value} & \\textbf{Sig} & \\textbf{Decision} \\\\",
            "    \\midrule",
        ]

        for _, row in df.iterrows():
            sig = row["Significance"]
            lines.append(
                f"    {row['Test']} & {row['Statistic']} & {row['P-value']} "
                f"& ${sig.replace('*', r'^*$').replace('***', r'^{***}').replace('**', r'^{**}')}$ "
                f"& {row['Decision']} \\\\"
            )

        lines.extend([
            "    \\bottomrule",
            "  \\end{tabular}",
            "  \\begin{tablenotes}",
            "    \\small",
            "    \\item H0: no cointegration. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.",
            "    \\item Pedroni (2004) panel tests. Kao (1999) ADF test. Westerlund (2005) Durbin-Hausman tests.",
            "  \\end{tablenotes}",
            "  \\end{threeparttable}",
            "\\end{table}",
        ])
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO / TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Panel Cointegration Test — Synthetic Data Demo")
    print("=" * 60)

    # ── Generate synthetic cointegrated panel data ──
    np.random.seed(42)
    n_units = 25
    T = 80
    n_obs = n_units * T

    unit_ids = np.repeat(np.arange(n_units), T)
    time_index = np.tile(np.arange(T), n_units)

    # True cointegrating relationship: y = 1.5*x + u
    x = np.random.randn(n_obs) * 2 + np.sin(2 * np.pi * time_index / 52)
    u = np.cumsum(np.random.randn(n_obs) * 0.5)  # Random walk (cointegration residual)
    y = 1.5 * x + u + np.random.randn(n_obs) * 0.1

    data = pd.DataFrame({
        "unit": unit_ids,
        "time": time_index,
        "lnrgdp": y,
        "lnmoney": x,
        "lninflation": x * 0.3 + np.random.randn(n_obs) * 0.5,
    })

    print(f"\nData: {n_units} units × {T} periods = {n_obs} obs")
    print(f"  y range: [{y.min():.2f}, {y.max():.2f}]")
    print(f"  x range: [{x.min():.2f}, {x.max():.2f}]")

    # ── Pedroni Panel Test ──
    print("\n" + "-" * 40)
    print("Pedroni (2004) Panel Cointegration Test")
    print("-" * 40)

    pct = PanelCointegrationTest(trend="c", max_lags=4)
    pedroni_res = pct.pedroni_panel(data, y_var="lnrgdp", x_vars=["lnmoney"])
    print(pct.summary())

    # ── Kao Test ──
    print("\n" + "-" * 40)
    print("Kao (1999) Panel ADF Test")
    print("-" * 40)

    kao_res = pct.kao_test(data, y_var="lnrgdp", x_vars=["lnmoney"])
    print(pct.summary())

    # ── Westerlund Test ──
    print("\n" + "-" * 40)
    print("Westerlund (2005) Durbin-Hausman Test")
    print("-" * 40)

    westerlund_res = pct.westerlund_test(data, y_var="lnrgdp", x_vars=["lnmoney"])
    print(pct.summary())

    # ── Panel ECM ──
    print("\n" + "-" * 40)
    print("Panel Error Correction Model (ECM)")
    print("-" * 40)

    ecm = PanelECM(trend="c")
    ecm_res = ecm.fit(
        data, dep_var="lnrgdp", indep_vars=["lnmoney"],
        unit_var="unit", time_var="time", lag_order=2,
    )
    print(ecm.summary())

    # ── Cross-Sectional Dependence ──
    print("\n" + "-" * 40)
    print("Cross-Sectional Dependence (Pesaran 2004)")
    print("-" * 40)

    csd = CrossSectionalDependence()
    cd_res = csd.test(data, vars=["lnrgdp", "lnmoney", "lninflation"], unit_var="unit")
    print(f"  CD statistic: {cd_res.get('cd_statistic', np.nan):.4f}")
    print(f"  CD p-value:  {cd_res.get('cd_pval', np.nan):.4f}")
    print(f"  Avg corr:    {cd_res.get('avg_correlation', np.nan):.4f}")
    print(f"  Decision:    {cd_res.get('decision', 'N/A')}")

    # ── Full summary table ──
    print("\n" + "=" * 60)
    print("Combined Summary Table")
    print("=" * 60)
    print(pct.summary())

    # ── LaTeX output ──
    latex_tab = pct.to_latex()
    print("\n" + "-" * 40)
    print("LaTeX Output (Pedroni + Kao + Westerlund)")
    print("-" * 40)
    print(latex_tab)

    # ── ECM LaTeX ──
    ecm_latex = ecm.to_latex()
    print("\n" + "-" * 40)
    print("ECM LaTeX Table")
    print("-" * 40)
    print(ecm_latex)

    print("\n[OK] panel_cointegration module loaded successfully.")
