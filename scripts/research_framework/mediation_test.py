"""
mediation_test.py — Causal Mediation Analysis (Baron-Kenny / Sobel / Bootstrap CI)

Implements:
- Baron-Kenny three-step mediation test (Baron & Kenny 1986)
- Sobel standard error approximation (Sobel 1982)
- Joint significance test (MacKinnon et al. 2002)
- Bootstrap confidence intervals (Preacher & Hayes 2008)

References:
- Baron, R. M., & Kenny, D. A. (1986). JPSP
- Sobel, M. E. (1982). Sociological Methods & Research
- MacKinnon, D. P., et al. (2002). Psych Methods
- Preacher, K. J., & Hayes, A. F. (2008). BRM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy import stats

_log = logging.getLogger("mediation")

__all__ = ["MediationTest", "MediationResult"]


class OLS2DResult(NamedTuple):
    """Result of a two-dimensional OLS regression y = b1*x1 + b2*x2 + a + e."""
    b1: float   # slope of x1 (mediator)
    b2: float   # slope of x2 (treatment / other control)
    se1: float  # standard error of b1
    se2: float  # standard error of b2
    t1: float   # t-statistic of b1
    p1: float   # p-value of b1


@dataclass
class MediationResult:
    """Results of a mediation analysis."""
    method: str                          # "Baron-Kenny", "Sobel", "Bootstrap CI", "Joint Significance"
    alpha: float                        # Total effect (X -> Y), path c
    beta: float                        # Effect of X on mediator (X -> M), path a
    gamma: float                       # Effect of M on Y controlling X (M -> Y|X), path b
    delta: float                       # Direct effect of X on Y controlling M (X -> Y|M), path c'
    indirect_effect: float             # Indirect effect = beta * gamma
    indirect_se: float | None         # Sobel SE (None for Bootstrap/JointSig)
    indirect_pvalue: float | None      # P-value
    proportion_mediated: float | None  # |indirect| / |alpha|
    ci_lower: float | None            # Bootstrap CI lower bound
    ci_upper: float | None            # Bootstrap CI upper bound
    n_bootstrap: int                 # Number of bootstrap replications
    conclusions: dict[str, bool]      # {method_name: is_significant}

    def is_significant(self, method: str | None = None, alpha_level: float = 0.05) -> bool:
        """Check if the indirect effect is significant under the named test."""
        key = method if method else self.method
        return self.conclusions.get(key, False)

    def summary(self) -> str:
        """Generate a publication-ready summary string."""
        lines = [
            f"Mediation Analysis ({self.method})",
            f"{'='*50}",
            f"Total Effect (X->Y, c):        {self.alpha:.4f}",
            f"Path a (X->M):                {self.beta:.4f}",
            f"Path b (M->Y|X):              {self.gamma:.4f}",
            f"Direct Effect (X->Y|M, c'):   {self.delta:.4f}",
            f"Indirect Effect (a*b):         {self.indirect_effect:.4f}",
        ]
        if self.indirect_se is not None:
            z = self.indirect_effect / self.indirect_se
            lines.append(f"Sobel SE:                  {self.indirect_se:.4f}")
            lines.append(f"Sobel Z:                  {z:.4f}")
            if self.indirect_pvalue is not None:
                lines.append(f"Sobel P-value:          {self.indirect_pvalue:.4f}")
        if self.proportion_mediated is not None:
            lines.append(f"Proportion Mediated:      {self.proportion_mediated:.1%}")
        if self.ci_lower is not None and self.ci_upper is not None:
            lines.append(f"Bootstrap 95% CI:         [{self.ci_lower:.4f}, {self.ci_upper:.4f}]")
        conclusions_str = ", ".join(
            f"{k}: {'Significant' if v else 'NS'}"
            for k, v in self.conclusions.items()
        )
        lines.append(f"Conclusions: {conclusions_str}")
        return "\n".join(lines)


class MediationTest:
    """
    Causal Mediation Analysis supporting four methods.

    Parameters
    ----------
    data : pd.DataFrame
        Input data frame.
    x_var : str
        Name of the treatment / independent variable.
    y_var : str
        Name of the outcome variable.
    m_var : str
        Name of the mediator variable.
    cluster_var : str, optional
        If provided, bootstrap resamples are clustered by this variable.

    Examples
    --------
    >>> mt = MediationTest(df, "policy", "innovation", "rd_expenditure")
    >>> results = mt.run_all(n_bootstrap=5000)
    >>> print(results["Sobel"].summary())
    """

    def __init__(
        self,
        data: pd.DataFrame,
        x_var: str,
        y_var: str,
        m_var: str,
        cluster_var: str | None = None,
    ):
        self.data = data.dropna(subset=[x_var, y_var, m_var]).copy()
        self.x = self.data[x_var].values.astype(float)
        self.y = self.data[y_var].values.astype(float)
        self.m = self.data[m_var].values.astype(float)
        self.cluster: np.ndarray | None = (
            self.data[cluster_var].values if cluster_var else None
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def baron_kenny(self) -> MediationResult:
        """
        Baron-Kenny three-step mediation test (1986).

        Step 1: X -> Y significant (total effect c = alpha)
        Step 2: X -> M significant (path a = beta)
        Step 3: M -> Y significant (path b = gamma) AND
                X -> Y reduced (direct effect delta = c' < c in magnitude)

        Returns
        -------
        MediationResult
        """
        alpha = self._regress_ols(self.y, self.x)[0]
        beta = self._regress_ols(self.m, self.x)[0]

        ols2d = self._regress_ols_2d(self.y, self.m, self.x)
        gamma = ols2d.b1   # M -> Y|X (path b)
        delta = ols2d.b2   # X -> Y|M (path c')

        indirect = beta * gamma
        prop: float | None = self._prop_mediated(alpha, indirect)

        conclusions = {
            "Baron-Kenny": abs(gamma) > 0 and abs(delta) < abs(alpha),
        }
        return MediationResult(
            method="Baron-Kenny",
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta=delta,
            indirect_effect=indirect,
            indirect_se=None,
            indirect_pvalue=None,
            proportion_mediated=prop,
            ci_lower=None,
            ci_upper=None,
            n_bootstrap=0,
            conclusions=conclusions,
        )

    def sobel(self) -> MediationResult:
        """
        Sobel standard error approximation (1982).

        SE(ab) = sqrt(a^2 * SE(b)^2 + b^2 * SE(a)^2)
        Z      = ab / SE(ab)
        P-value from standard normal two-tailed test.

        Returns
        -------
        MediationResult
        """
        # X -> M: path a = beta
        beta_res = self._regress_ols(self.m, self.x)
        beta = beta_res[0]
        beta_se = beta_res[1]

        # M -> Y|X and X -> Y|M (path b and c')
        ols2d = self._regress_ols_2d(self.y, self.m, self.x)
        gamma = ols2d.b1    # path b
        gamma_se = ols2d.se1
        delta = ols2d.b2    # direct effect

        alpha = self._regress_ols(self.y, self.x)[0]
        indirect = beta * gamma
        indirect_se = float(np.sqrt(beta**2 * gamma_se**2 + gamma**2 * beta_se**2))
        z_stat = indirect / indirect_se if indirect_se > 1e-12 else 0.0
        p_value = float(2 * (1 - stats.norm.cdf(abs(z_stat))))
        prop: float | None = self._prop_mediated(alpha, indirect)

        return MediationResult(
            method="Sobel",
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta=delta,
            indirect_effect=indirect,
            indirect_se=indirect_se,
            indirect_pvalue=p_value,
            proportion_mediated=prop,
            ci_lower=None,
            ci_upper=None,
            n_bootstrap=0,
            conclusions={"Sobel": p_value < 0.05},
        )

    def bootstrap_ci(
        self,
        n_bootstrap: int = 5000,
        seed: int = 42,
        ci_level: float = 0.95,
    ) -> MediationResult:
        """
        Bootstrap confidence intervals for the indirect effect (Preacher & Hayes 2008).

        Uses the percentile bootstrap method on the product ab = a_hat * b_hat.

        Parameters
        ----------
        n_bootstrap : int
            Number of bootstrap resamples.
        seed : int
            Random seed for reproducibility.
        ci_level : float
            Confidence level (default 0.95 for 95% CI).

        Returns
        -------
        MediationResult
        """
        rng = np.random.default_rng(seed)
        alpha, beta, gamma, delta = self._get_coefs()

        ab_boots = self._bootstrap_ab(rng, n_bootstrap)

        indirect = beta * gamma
        tail = (1 - ci_level) / 2
        ci_lower = float(np.percentile(ab_boots, tail * 100))
        ci_upper = float(np.percentile(ab_boots, (1 - tail) * 100))
        # P-value: if CI excludes 0, p < (1 - ci_level); else p >= (1 - ci_level)
        p_value = 1 - ci_level if (ci_lower > 0 or ci_upper < 0) else ci_level
        prop: float | None = self._prop_mediated(alpha, indirect)

        return MediationResult(
            method="Bootstrap CI",
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta=delta,
            indirect_effect=indirect,
            indirect_se=None,
            indirect_pvalue=p_value,
            proportion_mediated=prop,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_bootstrap=n_bootstrap,
            conclusions={"Bootstrap": ci_lower > 0 or ci_upper < 0},
        )

    def joint_significance_test(self) -> MediationResult:
        """
        Joint significance test (MacKinnon et al. 2002).

        Test H0: a = 0 OR b = 0 by checking that both paths a and b
        are individually significant. This is the most powerful test among
        the Baron-Kenny family.

        Returns
        -------
        MediationResult
        """
        # X -> M: path a
        beta_res = self._regress_ols(self.m, self.x)
        beta = beta_res[0]
        beta_p = beta_res[3]

        # M -> Y|X: path b
        ols2d = self._regress_ols_2d(self.y, self.m, self.x)
        gamma = ols2d.b1
        gamma_p = ols2d.p1
        delta = ols2d.b2

        alpha = self._regress_ols(self.y, self.x)[0]
        indirect = beta * gamma
        prop: float | None = self._prop_mediated(alpha, indirect)
        is_significant = bool(beta_p < 0.05 and gamma_p < 0.05)

        return MediationResult(
            method="Joint Significance",
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta=delta,
            indirect_effect=indirect,
            indirect_se=None,
            indirect_pvalue=None,
            proportion_mediated=prop,
            ci_lower=None,
            ci_upper=None,
            n_bootstrap=0,
            conclusions={"Joint Sig": is_significant},
        )

    def run_all(self, n_bootstrap: int = 5000) -> dict[str, MediationResult]:
        """
        Run all four mediation tests and return a dict keyed by method name.

        Parameters
        ----------
        n_bootstrap : int
            Number of bootstrap replications for the Bootstrap CI method.

        Returns
        -------
        dict[str, MediationResult]
        """
        return {
            "Baron-Kenny": self.baron_kenny(),
            "Sobel": self.sobel(),
            "Bootstrap CI": self.bootstrap_ci(n_bootstrap=n_bootstrap),
            "Joint Significance": self.joint_significance_test(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _regress_ols(
        self, y: np.ndarray, x: np.ndarray
    ) -> tuple[float, float, float, float]:
        """
        Simple OLS: y = a * x + b + e.

        Returns
        -------
        slope : float
        slope_se : float
        t_stat : float
        p_value : float
        """
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        X = np.column_stack([np.ones(len(x_arr)), x_arr])
        beta, *_ = np.linalg.lstsq(X, y_arr, rcond=None)
        resid = y_arr - X @ beta
        n, k = X.shape
        sigma2 = float(np.sum(resid**2) / max(n - k, 1))
        var_beta = float(sigma2) * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(var_beta))
        t = beta / se
        df = max(n - k, 1)
        p = 2 * (1 - stats.t.cdf(np.abs(t), df=df))
        return float(beta[1]), float(se[1]), float(t[1]), float(p[1])

    def _regress_ols_2d(
        self, y: np.ndarray, x1: np.ndarray, x2: np.ndarray
    ) -> OLS2DResult:
        """
        Multiple OLS: y = b1*x1 + b2*x2 + a + e.

        Returns OLS2DResult(b1, b2, se1, se2, t1, p1).
        """
        y_arr = np.asarray(y, dtype=float)
        x1_arr = np.asarray(x1, dtype=float)
        x2_arr = np.asarray(x2, dtype=float)
        X = np.column_stack([np.ones(len(y_arr)), x1_arr, x2_arr])
        beta, *_ = np.linalg.lstsq(X, y_arr, rcond=None)
        resid = y_arr - X @ beta
        n, k = X.shape
        sigma2 = float(np.sum(resid**2) / max(n - k, 1))
        var_beta = float(sigma2) * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(var_beta))
        t = beta / se
        df = max(n - k, 1)
        p = 2 * (1 - stats.t.cdf(np.abs(t), df=df))
        return OLS2DResult(
            b1=float(beta[1]),
            b2=float(beta[2]),
            se1=float(se[1]),
            se2=float(se[2]),
            t1=float(t[1]),
            p1=float(p[1]),
        )

    def _get_coefs(self) -> tuple[float, float, float, float]:
        """Return (alpha, beta, gamma, delta) from OLS regressions."""
        alpha = self._regress_ols(self.y, self.x)[0]
        beta = self._regress_ols(self.m, self.x)[0]
        ols2d = self._regress_ols_2d(self.y, self.m, self.x)
        return alpha, beta, ols2d.b1, ols2d.b2

    def _prop_mediated(self, alpha: float, indirect: float) -> float | None:
        """Compute proportion mediated, or None if invalid."""
        if alpha == 0:
            return None
        prop = abs(indirect) / abs(alpha)
        return prop if 0 <= prop <= 1 else None

    def _bootstrap_ab(
        self, rng: np.random.Generator, n_bootstrap: int
    ) -> np.ndarray:
        """
        Compute bootstrap distribution of the indirect effect ab.

        When cluster_var is set, resamples by cluster; otherwise resamples
        individual observations.
        """
        ab_boots = np.empty(n_bootstrap)
        if self.cluster is not None:
            unique_clusters = np.unique(self.cluster)
            for i in range(n_bootstrap):
                boot_clusters = rng.choice(
                    unique_clusters, size=len(unique_clusters), replace=True
                )
                mask = np.isin(self.cluster, boot_clusters)
                a_hat = self._regress_ols(self.m[mask], self.x[mask])[0]
                b_hat = self._regress_ols_2d(
                    self.y[mask], self.m[mask], self.x[mask]
                ).b1
                ab_boots[i] = a_hat * b_hat
        else:
            for i in range(n_bootstrap):
                idx = rng.integers(0, len(self.x), size=len(self.x))
                a_hat = self._regress_ols(self.m[idx], self.x[idx])[0]
                b_hat = self._regress_ols_2d(
                    self.y[idx], self.m[idx], self.x[idx]
                ).b1
                ab_boots[i] = a_hat * b_hat
        return ab_boots
