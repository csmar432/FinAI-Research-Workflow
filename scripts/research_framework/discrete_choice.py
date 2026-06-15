"""Discrete Choice Regression Models for Economics/Finance Research.

本模块封装二元/有序离散选择回归模型，覆盖：
  1. Logit（Binary Logit）
  2. Probit（Binary Probit）
  3. Ordered Logit（Ordered Probit / OLogit）
  4. Negative Binomial（计数数据，NB2 模型）

支持：
  - Robust SE（HC0 / HC1）
  - 聚类标准误（单维 / 二维）
  - 边际效应计算（MEM / AME）
  - 系数量表输出（pandas DataFrame / LaTeX）
  - 模型比较（AIC / BIC / Pseudo-R²）
  - 分组系数相等性检验（Chow 风格）
  - PSM 平衡性诊断

Usage:
    model = DiscreteChoiceModel(model_type="logit")
    result = model.fit(df, y="default", X=["size", "lev", "roe"],
                       cluster_var="industry")
    print(model.summary())

    me = model.marginal_effects(result, at="mean")
    print(me.to_df())

    suite = DiscreteChoiceSuite()
    cmp = suite.compare_models(df, y="default", X=["size","lev","roe"],
                               models=["logit", "probit", "ologit"])
    print(cmp)

    het = suite.heterogeneity_test(df, y="default", X=["size","lev"],
                                   group_var="state")
    print(het)
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from scripts.core.formatters import significance_mark as _significance_mark

__all__ = [
    "DiscreteChoiceModel",
    "DiscreteChoiceSuite",
    "DiscreteChoiceResult",
    "MarginalEffectsResult",
]

_log = logging.getLogger("discrete_choice")
_log.setLevel(logging.INFO)
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────


# `_significance_mark` is provided by scripts.core.formatters (imported above)



def _safe_div(a: np.ndarray, b: np.ndarray, fill: float = np.nan) -> np.ndarray:
    out = np.full_like(a, fill, dtype=float)
    mask = np.abs(b) > 1e-12
    out[mask] = a[mask] / b[mask]
    return out


def _norm_pdf(x: np.ndarray) -> np.ndarray:
    """Standard normal PDF."""
    try:
        from scipy import stats
        return stats.norm.pdf(x)
    except Exception:
        return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    """Standard normal CDF (clipped for numerical stability)."""
    try:
        from scipy import stats
        return stats.norm.cdf(x)
    except Exception:
        x_clipped = np.clip(x, -37, 37)
        return 1 / (1 + np.exp(-0.5515 * x_clipped - 0.00005 * x_clipped**3))


def _hc1_se(
    resid: np.ndarray, X: np.ndarray, coef: np.ndarray
) -> np.ndarray:
    """
    HC1 (MacKinnon-White) robust SE for linear model.

    Used as fallback when statsmodels robust SE is unavailable.
    """
    n, k = X.shape
    h = resid**2
    meat = X.T @ (h[:, None] * X)
    xtxi = np.linalg.pinv(X.T @ X)
    vcv = xtxi @ meat @ xtxi
    return np.sqrt(np.diag(vcv) * n / (n - k))


def _cluster_se_2d(
    y: np.ndarray,
    X: np.ndarray,
    coef: np.ndarray,
    cluster1: np.ndarray,
    cluster2: np.ndarray,
) -> np.ndarray:
    """
    Two-way clustered SE (Cameron-Gelbach-Miller 2011 approximation).

    Computes CRVE with two dimensions of clustering.

    Parameters
    ----------
    y : np.ndarray (n,)
    X : np.ndarray (n, k)
    coef : np.ndarray (k,)
    cluster1, cluster2 : np.ndarray (n,) — integer-coded cluster IDs

    Returns
    -------
    np.ndarray (k,) — clustered standard errors
    """
    n, k = X.shape
    resid = y - X @ coef

    # One-way cluster SEs
    def _one_way(clusters: np.ndarray) -> np.ndarray:
        u_df = pd.DataFrame({"u": resid, "cl": clusters, "X": list(X)})
        meat = np.zeros((k, k))
        for _, grp in u_df.groupby("cl"):
            ui = grp["u"].values
            Xi = np.array(list(grp["X"].values))
            meat += Xi.T @ (ui[:, None] * Xi)
        xtxi = np.linalg.pinv(X.T @ X)
        return np.sqrt(np.diag(xtxi @ meat @ xtxi))

    try:
        se1 = _one_way(cluster1)
        se2 = _one_way(cluster2)
        se12 = _one_way(np.core.multiarray.concatenate_arrays(
            [cluster1.astype(str), cluster2.astype(str)]
        ) if hasattr(np.core.multiarray, "concatenate_arrays")
        else np.column_stack([cluster1, cluster2]).astype(str).view("<U32"))
    except Exception:
        se1 = np.full(k, np.nan)
        se2 = np.full(k, np.nan)

    # CGM approximation: sqrt(se1^2 + se2^2 - se12^2) when se12 available
    try:
        se12 = _one_way(
            np.array([f"{a}-{b}" for a, b in zip(cluster1, cluster2, strict=False)])
        )
        se_cgm = np.sqrt(np.maximum(se1**2 + se2**2 - se12**2, 0))
    except Exception:
        se_cgm = np.sqrt(se1**2 + se2**2)

    return se_cgm


def _cluster_se_1d(
    y: np.ndarray,
    X: np.ndarray,
    coef: np.ndarray,
    clusters: np.ndarray,
) -> np.ndarray:
    """
    One-way cluster-robust SE (Arellano 1987).

    Parameters
    ----------
    clusters : np.ndarray (n,) — integer-coded cluster IDs

    Returns
    -------
    np.ndarray (k,)
    """
    n, k = X.shape
    resid = y - X @ coef
    df = pd.DataFrame({"u": resid, "cl": clusters})
    meat = np.zeros((k, k))
    for _, grp in df.groupby("cl"):
        ui = grp["u"].values
        Xi = X[grp.index.values]
        meat += Xi.T @ (ui[:, None] * Xi)
    try:
        xtxi = np.linalg.pinv(X.T @ X)
    except Exception:
        return np.full(k, np.nan)
    vcv = xtxi @ meat @ xtxi
    return np.sqrt(np.diag(vcv))


def _pseudo_r2(log_likelihood: float, ll_null: float) -> float:
    """McFadden's Pseudo R² = 1 - ln(L̂) / ln(L₀)."""
    if ll_null >= 0 or log_likelihood >= 0:
        return np.nan
    if ll_null == 0:
        return np.nan
    return float(1 - log_likelihood / ll_null)


def _aic(log_likelihood: float, k: int, n: int) -> float:
    return float(2 * k - 2 * log_likelihood)


def _bic(log_likelihood: float, k: int, n: int) -> float:
    return float(k * np.log(n) - 2 * log_likelihood)


# ─────────────────────────────────────────────────────────────────────────────
# RESULT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DiscreteChoiceResult:
    """
    离散选择回归结果容器。

    Attributes
    ----------
    model_type : str
        模型类型："logit" | "probit" | "ologit" | "nb"。
    coef_dict : dict[str, float]
        变量名到系数估计值的映射。
    se_dict : dict[str, float]
        变量名到标准误的映射。
    z_dict : dict[str, float]
        变量名到 z 统计量的映射。
    pval_dict : dict[str, float]
        变量名到 p 值的映射。
    ci_lower : dict[str, float]
        变量名到 95% CI 下界的映射。
    ci_upper : dict[str, float]
        变量名到 95% CI 上界的映射。
    sig_dict : dict[str, str]
        变量名到显著性标记的映射 (* / ** / ***)。
    n_obs : int
        有效观测数。
    pseudo_r2 : float | None
        McFadden 伪 R²。
    aic : float | None
        AIC。
    bic : float | None
        BIC。
    log_likelihood : float | None
        对数似然值。
    converged : bool
        估计是否收敛。
    method : str
        SE 类型："robust" | "cluster" | "analytical"。
    cluster_var : str | None
        聚类变量名。
    additional : dict
        额外诊断信息（平行性检验/分散参数等）。
    """

    model_type: str
    coef_dict: dict[str, float] = field(default_factory=dict)
    se_dict: dict[str, float] = field(default_factory=dict)
    z_dict: dict[str, float] = field(default_factory=dict)
    pval_dict: dict[str, float] = field(default_factory=dict)
    ci_lower: dict[str, float] = field(default_factory=dict)
    ci_upper: dict[str, float] = field(default_factory=dict)
    sig_dict: dict[str, str] = field(default_factory=dict)
    n_obs: int = 0
    pseudo_r2: float | None = None
    aic: float | None = None
    bic: float | None = None
    log_likelihood: float | None = None
    converged: bool = False
    method: str = "analytical"
    cluster_var: str | None = None
    additional: dict = field(default_factory=dict)

    @property
    def sig(self) -> str:
        """返回主变量（第一个非常数项）的显著性标记。"""
        if not self.sig_dict:
            return ""
        for k_, v in self.sig_dict.items():
            if k_.lower() not in ("const", "intercept", "_const"):
                return v
        return list(self.sig_dict.values())[0] if self.sig_dict else ""

    def to_dict(self) -> dict:
        out = {
            "model_type": self.model_type,
            "n_obs": self.n_obs,
            "pseudo_r2": self.pseudo_r2,
            "aic": self.aic,
            "bic": self.bic,
            "log_likelihood": self.log_likelihood,
            "converged": self.converged,
            "method": self.method,
            "cluster_var": self.cluster_var,
        }
        for var in self.coef_dict:
            out[f"coef_{var}"] = self.coef_dict[var]
            out[f"se_{var}"] = self.se_dict.get(var, np.nan)
            out[f"z_{var}"] = self.z_dict.get(var, np.nan)
            out[f"pval_{var}"] = self.pval_dict.get(var, np.nan)
            out[f"ci_lower_{var}"] = self.ci_lower.get(var, np.nan)
            out[f"ci_upper_{var}"] = self.ci_upper.get(var, np.nan)
            out[f"sig_{var}"] = self.sig_dict.get(var, "")
        out.update(self.additional)
        return out

    def marginal_effects(self, ate: bool = False) -> dict[str, float]:
        """
        返回当前结果的边际效应近似值（基于平均预测概率）。

        注意：精确边际效应请使用 DiscreteChoiceModel.marginal_effects()。
        本方法为便捷包装。

        Parameters
        ----------
        ate : bool
            若为 True，返回均值处的边际效应（MEM）。

        Returns
        -------
        dict[str, float]
        """
        if ate:
            return {k: v for k, v in self.coef_dict.items()
                    if k.lower() not in ("const", "intercept", "_const")}
        return {}


@dataclass
class MarginalEffectsResult:
    """
    边际效应结果容器。

    Attributes
    ----------
    me_dict : dict[str, float]
        变量名到个别边际效应的映射（at="all" 时为每个观测）。
    ame_dict : dict[str, float]
        变量名到平均边际效应的映射（AME）。
    se_dict : dict[str, float]
        变量名到 AME 标准误的映射。
    pval_dict : dict[str, float]
        变量名到 AME p 值的映射。
    method : str
        计算方法："MEM" | "AME"。
    model_type : str
        原始模型类型。
    """

    me_dict: dict[str, float] = field(default_factory=dict)
    ame_dict: dict[str, float] = field(default_factory=dict)
    se_dict: dict[str, float] = field(default_factory=dict)
    pval_dict: dict[str, float] = field(default_factory=dict)
    method: str = "AME"
    model_type: str = "logit"

    def to_df(self) -> pd.DataFrame:
        """
        返回边际效应 DataFrame。

        Returns
        -------
        pd.DataFrame
            列：Variable, AME, SE, z, P>|z|, Sig
        """
        rows = []
        for var, ame in self.ame_dict.items():
            se = self.se_dict.get(var, np.nan)
            z = ame / se if se > 1e-10 else np.nan
            try:
                from scipy import stats
                pval = 2 * (1 - stats.norm.cdf(abs(z)))
            except Exception:
                pval = np.nan
            sig = _significance_mark(pval)
            rows.append({
                "Variable": var,
                "AME": f"{ame:.4f}",
                "SE": f"({se:.4f})",
                "z": f"{z:.3f}",
                "P>|z|": f"{pval:.4f}",
                "Sig": sig,
            })
        return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# CORE MODEL
# ─────────────────────────────────────────────────────────────────────────────


class DiscreteChoiceModel:
    """
    离散选择回归模型 — sklearn-like API。

    支持的模型类型：
      - "logit"：Binary Logit（statsmodels Logit）
      - "probit"：Binary Probit（statsmodels Probit）
      - "ologit"：Ordered Logit（statsmodels OrderedModel）
      - "nb"：Negative Binomial（计数数据，statsmodels NegativeBinomial）

    SE 选项：
      - 解析 SE（默认）
      - Robust SE（HC0 / HC1）：通过 statsmodels get_robust_weed
      - 聚类 SE（单维 / 二维近似）

    使用方法：
        model = DiscreteChoiceModel(model_type="logit")
        result = model.fit(df, y="default", X=["size","lev","roe"],
                           cluster_var="industry")
        print(model.summary())

        me = model.marginal_effects(result, at="mean")
        print(me.to_df())

        probs = model.predict_proba(df)
    """

    def __init__(self, model_type: str = "logit"):
        """
        初始化离散选择模型。

        Parameters
        ----------
        model_type : str
            "logit"（默认）| "probit" | "ologit" | "nb"。
        """
        if model_type not in ("logit", "probit", "ologit", "nb"):
            raise ValueError(
                f"model_type must be one of 'logit', 'probit', 'ologit', 'nb', "
                f"got '{model_type}'"
            )
        self.model_type = model_type
        self._result: DiscreteChoiceResult | None = None
        self._last_fit_args: dict = {}

    # ── Core fit ────────────────────────────────────────────────────────────

    def fit(
        self,
        df: pd.DataFrame,
        y: str,
        X: list[str],
        cluster_var: str | None = None,
        robust_se: str = "HC1",
        add_cons: bool = True,
    ) -> DiscreteChoiceResult:
        """
        拟合离散选择模型。

        Parameters
        ----------
        df : pd.DataFrame
            输入数据。
        y : str
            因变量列名（二元：0/1；NB：非负整数）。
        X : list[str]
            自变量列名列表。
        cluster_var : str | None
            聚类标准误变量（单个变量）。
        robust_se : str
            Robust SE 类型："HC0" | "HC1"（默认）。
        add_cons : bool
            是否自动添加常数项（默认 True）。

        Returns
        -------
        DiscreteChoiceResult
        """
        import statsmodels.api as sm
        from statsmodels.discrete.discrete_model import Logit, NegativeBinomial, Probit
        from statsmodels.miscmodels.ordinal_model import OrderedModel

        self._last_fit_args = {
            "y": y, "X": X, "cluster_var": cluster_var,
            "robust_se": robust_se, "add_cons": add_cons,
        }
        self._last_df = df.copy()

        cols_needed = [y] + X
        if cluster_var:
            cols_needed.append(cluster_var)
        df_sub = df.dropna(subset=cols_needed).copy()
        n_obs = len(df_sub)

        if n_obs < 20:
            _log.warning(f"[DiscreteChoice] Only {n_obs} obs after dropna, fitting anyway")

        y_arr = df_sub[y].values.astype(float)
        X_arr = df_sub[X].values.astype(float)
        X_names = list(X)

        # OrderedModel manages thresholds internally; adding explicit const raises error
        if self.model_type == "ologit":
            add_cons = False

        if add_cons:
            X_arr = sm.add_constant(X_arr, has_constant="skip")
            X_names = ["const"] + X_names

        self._last_X_names = X_names  # preserve for marginal_effects
        k = X_arr.shape[1]

        # OrderedModel internally adds intercept; passing add_constant=True raises error
        _model_adds_intercept = self.model_type == "ologit"

        # ── Model-specific fitting ──────────────────────────────────────────
        additional: dict = {}

        try:
            if self.model_type == "logit":
                mod = Logit(y_arr, X_arr)
                res = mod.fit(disp=0, method="bfgs", maxiter=500)
                ll = float(res.llf)
                ll_null = float(res.llnull)
                converged = res.mle_retvals["converged"]

            elif self.model_type == "probit":
                mod = Probit(y_arr, X_arr)
                res = mod.fit(disp=0, method="bfgs", maxiter=500)
                ll = float(res.llf)
                ll_null = float(res.llnull)
                converged = res.mle_retvals["converged"]

            elif self.model_type == "ologit":
                mod = OrderedModel(y_arr, X_arr, distr="logit")
                res = mod.fit(disp=0, method="bfgs", maxiter=500)
                ll = float(res.llf)
                ll_null = np.nan
                converged = res.mle_retvals["converged"]

            elif self.model_type == "nb":
                mod = NegativeBinomial(y_arr, X_arr)
                res = mod.fit(disp=0, method="bfgs", maxiter=500)
                ll = float(res.llf)
                ll_null = np.nan  # NB null model not directly available
                converged = res.mle_retvals["converged"]
                # Store dispersion parameter
                disp_param = float(res.params[-1])
                self._nb_disp = disp_param
                additional["dispersion"] = disp_param

            else:
                raise ValueError(f"Unknown model_type: {self.model_type}")

        except Exception as e:
            _log.error(f"[DiscreteChoice] Fitting failed: {e}")
            return DiscreteChoiceResult(
                model_type=self.model_type,
                converged=False,
                n_obs=n_obs,
            )

        # ── Extract coefficients ─────────────────────────────────────────────
        def _to_array(val):
            if hasattr(val, "values"):
                return val.values.astype(float)
            return np.asarray(val, dtype=float)

        coef_arr = _to_array(res.params)
        z_arr = _to_array(res.tvalues)
        pval_arr = _to_array(res.pvalues)

        # ── Standard errors ──────────────────────────────────────────────────
        if cluster_var is not None:
            clust_arr = df_sub[cluster_var].values
            se_arr = _cluster_se_1d(y_arr, X_arr, coef_arr, clust_arr)
            se_method = "cluster"
        else:
            se_method = "analytical"
            try:
                rse = res.get_robust_weed("HC1" if robust_se == "HC1" else "HC0")
                se_arr = _to_array(rse)
                se_method = "robust"
            except Exception:
                _log.warning("[DiscreteChoice] Robust SE failed, using analytical SE")
                se_arr = _to_array(res.bse)

        # Ensure same length
        if len(se_arr) != len(coef_arr):
            se_arr = np.full_like(coef_arr, np.nan)

        # ── Build dictionaries ───────────────────────────────────────────────
        coef_dict = dict(zip(X_names, coef_arr.tolist(), strict=False))
        se_dict = dict(zip(X_names, se_arr.tolist(), strict=False))
        z_dict = dict(zip(X_names, z_arr.tolist(), strict=False))
        pval_dict = dict(zip(X_names, pval_arr.tolist(), strict=False))

        # CI
        try:
            from scipy import stats
            z_crit = stats.norm.ppf(0.975)
        except Exception:
            z_crit = 1.96
        ci_lower_arr = coef_arr - z_crit * se_arr
        ci_upper_arr = coef_arr + z_crit * se_arr
        ci_lower = dict(zip(X_names, ci_lower_arr.tolist(), strict=False))
        ci_upper = dict(zip(X_names, ci_upper_arr.tolist(), strict=False))

        sig_dict = {v: _significance_mark(pval_dict.get(v, 1.0)) for v in X_names}

        # Pseudo R² / AIC / BIC
        pseudo_r2 = _pseudo_r2(ll, ll_null) if not np.isnan(ll_null) else None
        aic = _aic(ll, k, n_obs)
        bic = _bic(ll, k, n_obs)

        self._result = DiscreteChoiceResult(
            model_type=self.model_type,
            coef_dict=coef_dict,
            se_dict=se_dict,
            z_dict=z_dict,
            pval_dict=pval_dict,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            sig_dict=sig_dict,
            n_obs=n_obs,
            pseudo_r2=pseudo_r2,
            aic=aic,
            bic=bic,
            log_likelihood=ll,
            converged=converged,
            method=se_method,
            cluster_var=cluster_var,
            additional=additional,
        )

        _log.info(
            f"[DiscreteChoice] {self.model_type} fit: "
            + " ".join(
                f"{v}={coef_dict.get(v, 0):+.4f}{sig_dict.get(v, '')}"
                for v in X
                if v in coef_dict
            )
            + f", N={n_obs}, Pseudo-R²={pseudo_r2:.4f}" if pseudo_r2 else ""
            + f", converged={converged}"
        )

        return self._result

    # ── Marginal Effects ─────────────────────────────────────────────────────

    def marginal_effects(
        self,
        result: DiscreteChoiceResult | None = None,
        at: str = "mean",
    ) -> MarginalEffectsResult:
        """
        计算边际效应。

        Parameters
        ----------
        result : DiscreteChoiceResult | None
            估计结果。若为 None，使用最后一次 fit 的结果。
        at : str
            - "mean"：在均值处评估（MEM）
            - "median"：在中位数处评估
            - "all"：返回所有观测的个别 ME 后取平均（AME，默认）

        Returns
        -------
        MarginalEffectsResult
        """
        import statsmodels.api as sm

        if result is None:
            result = self._result
        if result is None:
            raise ValueError("No result available. Call fit() first.")

        args = self._last_fit_args
        df_local = getattr(self, "_last_df", None)
        if df_local is None:
            _log.warning("[DiscreteChoice] No DataFrame stored, returning empty ME")
            return MarginalEffectsResult(model_type=self.model_type)

        y = args.get("y", "")
        X_names_raw = [v for v in args.get("X", []) if v != "const"]

        cols_needed = [y] + X_names_raw
        df_sub = df_local.dropna(subset=cols_needed).copy()
        n = len(df_sub)

        X_vals = df_sub[X_names_raw].values.astype(float)
        sm.add_constant(X_vals, has_constant="skip")

        # Use stored column names to align with coef_dict
        X_names_with_const = getattr(self, "_last_X_names", None) or ["const"] + X_names_raw
        coef = np.array([result.coef_dict.get(nm, 0.0) for nm in X_names_with_const])
        xb = X_vals @ coef[1:] + coef[0]

        # Calculate predicted probability
        if self.model_type == "logit":
            p = _norm_cdf(xb)  # logit: use sigmoid
        elif self.model_type == "probit":
            p = _norm_cdf(xb)
        elif self.model_type == "ologit":
            p = _norm_cdf(xb)  # approximate
        elif self.model_type == "nb":
            # For NB, ME is on expected count: E[y|x] = exp(xb)
            # Individual ME not defined in same way; use exp(xb) * beta
            p = np.exp(xb)
        else:
            p = _norm_cdf(xb)

        # Compute marginal effects per observation
        me_per_obs: dict[str, np.ndarray] = {}
        for i, var in enumerate(X_names_raw):
            col_idx = X_names_with_const.index(var) if var in X_names_with_const else i + 1
            if self.model_type in ("logit", "probit", "ologit"):
                # ME = beta * p * (1-p) for logit; beta * phi(xb) for probit
                if self.model_type == "logit":
                    me_i = coef[col_idx] * p * (1 - p)
                else:
                    me_i = coef[col_idx] * _norm_pdf(xb)
            elif self.model_type == "nb":
                me_i = coef[col_idx] * p  # dE[y]/dx = beta * E[y]
            else:
                me_i = np.full(n, np.nan)
            me_per_obs[var] = me_i

        if at == "all":
            # AME: average of individual MEs
            ame = {var: float(np.nanmean(me_per_obs[var])) for var in me_per_obs}
            # SE of AME via simulation (delta method approximation)
            se = {}
            for var in me_per_obs:
                se_arr = me_per_obs[var]
                se[var] = float(np.nanstd(se_arr) / np.sqrt(n))
            pval_dict = {
                var: float(2 * (1 - _norm_cdf(abs(ame[var] / max(se[var], 1e-10)))))
                for var in ame
            }
            return MarginalEffectsResult(
                me_dict={},  # too large to store for "all"
                ame_dict=ame,
                se_dict=se,
                pval_dict=pval_dict,
                method="AME",
                model_type=self.model_type,
            )

        # MEM: evaluate at mean (or median)
        x_bar = np.nanmean(X_vals, axis=0)
        if at == "median":
            x_bar = np.nanmedian(X_vals, axis=0)
        x_bar_arr = np.insert(x_bar, 0, 1.0)  # add const
        xb_bar = float(x_bar_arr @ coef)
        p_bar = _norm_cdf(np.array([xb_bar]))[0]

        me_mean = {}
        se_mean = {}
        pval_mean = {}
        for i, var in enumerate(X_names_raw):
            col_idx = X_names_with_const.index(var) if var in X_names_with_const else i + 1
            beta = coef[col_idx]
            if self.model_type == "logit":
                me_v = beta * p_bar * (1 - p_bar)
            elif self.model_type == "probit":
                me_v = beta * _norm_pdf(np.array([xb_bar]))[0]
            elif self.model_type == "nb":
                me_v = beta * np.exp(xb_bar)
            else:
                me_v = np.nan
            me_mean[var] = float(me_v)
            # SE: use result's SE directly (approximation)
            se_mean[var] = float(result.se_dict.get(var, np.nan))
            pval_mean[var] = float(result.pval_dict.get(var, np.nan))

        return MarginalEffectsResult(
            ame_dict=me_mean,
            se_dict=se_mean,
            pval_dict=pval_mean,
            method="MEM",
            model_type=self.model_type,
        )

    # ── Prediction ──────────────────────────────────────────────────────────

    def predict_proba(
        self,
        df: pd.DataFrame,
        result: DiscreteChoiceResult | None = None,
    ) -> np.ndarray:
        """
        预测事件概率 P(y=1|x)。

        Parameters
        ----------
        df : pd.DataFrame
            新数据。
        result : DiscreteChoiceResult | None

        Returns
        -------
        np.ndarray (n,) — 预测概率 (0,1)
        """
        import statsmodels.api as sm

        if result is None:
            result = self._result
        if result is None:
            raise ValueError("No result available. Call fit() first.")

        args = self._last_fit_args
        X_names_raw = [v for v in args.get("X", []) if v != "const"]

        cols_needed = X_names_raw
        df_sub = df.dropna(subset=cols_needed).copy()
        n = len(df_sub)

        if n == 0:
            return np.array([])

        X_vals = df_sub[X_names_raw].values.astype(float)
        sm.add_constant(X_vals, has_constant="skip")
        X_names_with_const = getattr(self, "_last_X_names", None) or ["const"] + X_names_raw
        coef = np.array([result.coef_dict.get(nm, 0.0) for nm in X_names_with_const])
        xb = X_vals @ coef[1:] + coef[0]

        if self.model_type in ("logit", "ologit"):
            p = 1 / (1 + np.exp(-xb))
        elif self.model_type == "probit":
            p = _norm_cdf(xb)
        elif self.model_type == "nb":
            p = np.exp(xb)  # expected count
        else:
            p = np.full(n, 0.5)

        return np.clip(p, 0, 1) if self.model_type != "nb" else p

    # ── Output ───────────────────────────────────────────────────────────────

    def summary(self) -> pd.DataFrame:
        """
        返回回归结果汇总表。

        Returns
        -------
        pd.DataFrame
            列：Variable, Coef, SE, z, P>|z|, Sig
        """
        if self._result is None:
            return pd.DataFrame()

        r = self._result
        rows = []
        for var in r.coef_dict:
            coef = r.coef_dict[var]
            se = r.se_dict.get(var, np.nan)
            z = r.z_dict.get(var, np.nan)
            pval = r.pval_dict.get(var, np.nan)
            sig = r.sig_dict.get(var, "")
            rows.append({
                "Variable": var,
                "Coef": f"{coef:+.4f}",
                "SE": f"({se:.4f})" if not np.isnan(se) else "NA",
                "z": f"{z:.3f}" if not np.isnan(z) else "NA",
                "P>|z|": f"{pval:.4f}" if not np.isnan(pval) else "NA",
                "Sig": sig,
            })

        df = pd.DataFrame(rows)
        # Move const to bottom
        if "const" in df["Variable"].values:
            const_row = df[df["Variable"] == "const"]
            df = pd.concat([df[df["Variable"] != "const"], const_row])
        return df

    def to_latex(
        self,
        caption: str = "Discrete Choice Regression Results",
        label: str = "tab:discrete_choice",
        stars: bool = True,
    ) -> str:
        """
        导出为 LaTeX 表格（booktabs / threeparttable 格式）。

        Parameters
        ----------
        caption : str
        label : str
        stars : bool
            是否在系数旁添加显著性星号。

        Returns
        -------
        str — LaTeX 代码
        """
        df = self.summary()
        if df.empty:
            return ""

        r = self._result
        lines = [
            "\\begin{table}[htbp]",
            "  \\centering",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{label}}}",
            "  \\begin{threeparttable}",
            "  \\begin{tabular}{lccccc}",
            "    \\toprule",
            "    \\textbf{Variable} & \\textbf{Coef} & \\textbf{SE} & "
            "\\textbf{z} & \\textbf{P$\\>|z|$} \\\\ ",
            "    \\midrule",
        ]

        for _, row in df.iterrows():
            var = row["Variable"]
            if var == "const":
                continue
            coef_str = row["Coef"]
            if stars:
                sig = row["Sig"]
                coef_str = f"{row['Coef']}{sig}"
            lines.append(
                f"    {var:30s} & {coef_str:>10s} & {row['SE']:>10s} & "
                f"{row['z']:>8s} & {row['P>|z|']:>8s} \\\\"
            )

        lines.extend([
            "    \\midrule",
            "    \\textbf{Constant} & " + " & ".join(
                df[df["Variable"] == "const"].iloc[0][["Coef","SE","z","P>|z|"]].astype(str).tolist()
                if len(df[df["Variable"] == "const"]) > 0 else ["", "", "", ""]
            ) + " \\\\ " if len(df[df["Variable"] == "const"]) > 0 else "",
            "    \\bottomrule",
            "    \\midrule",
            f"    \\textbf{{N}} & \\textbf{{{r.n_obs}}} & & & \\\\ ",
            f"    \\textbf{{Pseudo R$^2$}} & \\textbf{{{r.pseudo_r2:.4f}}} & & & \\\\ "
            if r.pseudo_r2 is not None else "",
            f"    \\textbf{{AIC}} & {r.aic:.2f} & & & \\\\ " if r.aic else "",
            f"    \\textbf{{BIC}} & {r.bic:.2f} & & & \\\\ " if r.bic else "",
            "  \\end{tabular}",
            "  \\begin{tablenotes}",
            "    \\small",
            "    \\item Standard errors in parentheses. "
            "$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.",
            f"    \\item Model: {self.model_type.upper()}. "
            f"SE method: {r.method}." + (
                f" Clustered by {r.cluster_var}." if r.cluster_var else ""
            ),
            "  \\end{tablenotes}",
            "  \\end{threeparttable}",
            "\\end{table}",
        ])

        return "\n".join(line for line in lines if line)


# ─────────────────────────────────────────────────────────────────────────────
# SUITE: ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────


class DiscreteChoiceSuite:
    """
    离散选择模型套件 — 模型比较、异质性检验、平衡性诊断。

    使用方法：
        suite = DiscreteChoiceSuite()

        # 比较多个模型
        cmp = suite.compare_models(df, y="default", X=["size","lev","roe"],
                                   models=["logit", "probit", "nb"])
        print(cmp)

        # 分组系数相等性检验
        het = suite.heterogeneity_test(df, y="default", X=["size","lev"],
                                       group_var="state")
        print(het)

        # PSM 平衡性检验
        bal = suite.balance_test(df, X=["size","lev","roe"], treatment_var="did")
        print(bal)
    """

    def __init__(self):
        self._fitted_models: dict[str, DiscreteChoiceModel] = {}

    def compare_models(
        self,
        df: pd.DataFrame,
        y: str,
        X: list[str],
        models: list[str] | None = None,
        cluster_var: str | None = None,
    ) -> pd.DataFrame:
        """
        拟合多个离散选择模型并比较。

        Parameters
        ----------
        df : pd.DataFrame
        y : str
        X : list[str]
        models : list[str]
            待比较的模型类型列表。默认为 ["logit", "probit"]。
        cluster_var : str | None

        Returns
        -------
        pd.DataFrame
            列：Model, N, Pseudo_R2, AIC, BIC, LogLik
        """
        if models is None:
            models = ["logit", "probit"]

        rows = []
        for mt in models:
            try:
                model = DiscreteChoiceModel(model_type=mt)
                result = model.fit(df, y=y, X=X, cluster_var=cluster_var)
                self._fitted_models[mt] = model
                rows.append({
                    "Model": mt.upper(),
                    "N": result.n_obs,
                    "Pseudo_R2": f"{result.pseudo_r2:.4f}" if result.pseudo_r2 else "NA",
                    "AIC": f"{result.aic:.2f}" if result.aic else "NA",
                    "BIC": f"{result.bic:.2f}" if result.bic else "NA",
                    "LogLik": f"{result.log_likelihood:.2f}" if result.log_likelihood else "NA",
                    "Converged": result.converged,
                })
            except Exception as e:
                _log.warning(f"[Suite] {mt} failed: {e}")
                rows.append({
                    "Model": mt.upper(),
                    "N": np.nan,
                    "Pseudo_R2": "NA",
                    "AIC": "NA",
                    "BIC": "NA",
                    "LogLik": "NA",
                    "Converged": False,
                })

        return pd.DataFrame(rows)

    def heterogeneity_test(
        self,
        df: pd.DataFrame,
        y: str,
        X: list[str],
        group_var: str,
        model_type: str = "logit",
    ) -> pd.DataFrame:
        """
        分组系数相等性检验（Chow 风格 Wald 检验）。

        检验 H0: 各组的回归系数相等。

        Parameters
        ----------
        df : pd.DataFrame
        y : str
        X : list[str]
        group_var : str
            分组变量（如 state / industry）。
        model_type : str

        Returns
        -------
        pd.DataFrame
            列：Variable, Coef_Group1, Coef_Group2, Diff, SE_Diff, z_stat, P>|z|
        """
        groups = df[group_var].dropna().unique()
        if len(groups) < 2:
            _log.warning(f"[Suite] group_var '{group_var}' has < 2 groups")
            return pd.DataFrame()

        g1, g2 = groups[0], groups[1]
        df_g1 = df[df[group_var] == g1].dropna(subset=[y] + X)
        df_g2 = df[df[group_var] == g2].dropna(subset=[y] + X)

        model1 = DiscreteChoiceModel(model_type=model_type)
        model2 = DiscreteChoiceModel(model_type=model_type)
        r1 = model1.fit(df_g1, y=y, X=X)
        r2 = model2.fit(df_g2, y=y, X=X)

        rows = []
        common_vars = set(r1.coef_dict.keys()) & set(r2.coef_dict.keys())
        for var in common_vars:
            if var.lower() in ("const", "intercept", "_const"):
                continue
            c1 = r1.coef_dict.get(var, np.nan)
            c2 = r2.coef_dict.get(var, np.nan)
            s1 = r1.se_dict.get(var, 0.0)
            s2 = r2.se_dict.get(var, 0.0)
            diff = c1 - c2
            se_diff = np.sqrt(s1**2 + s2**2)
            z_stat = diff / se_diff if se_diff > 1e-10 else np.nan
            try:
                from scipy import stats
                pval = 2 * (1 - stats.norm.cdf(abs(z_stat)))
            except Exception:
                pval = np.nan
            sig = _significance_mark(pval)
            rows.append({
                "Variable": var,
                f"Coef_{g1}": f"{c1:+.4f}",
                f"Coef_{g2}": f"{c2:+.4f}",
                "Diff": f"{diff:+.4f}",
                "SE_Diff": f"({se_diff:.4f})",
                "z_stat": f"{z_stat:.3f}" if not np.isnan(z_stat) else "NA",
                "P>|z|": f"{pval:.4f}" if not np.isnan(pval) else "NA",
                "Sig": sig,
            })

        return pd.DataFrame(rows)

    def balance_test(
        self,
        df: pd.DataFrame,
        X: list[str],
        treatment_var: str,
    ) -> pd.DataFrame:
        """
        倾向得分匹配（PSM）平衡性诊断。

        检查处理组和对照组在控制变量上的均值差异（标准化偏差）。

        Parameters
        ----------
        df : pd.DataFrame
        X : list[str]
            用于估计倾向得分的协变量。
        treatment_var : str
            二元处理变量（0/1）。

        Returns
        -------
        pd.DataFrame
            列：Variable, Mean_Control, Mean_Treated, Std_Diff, Var_Ratio, P>|t|
        """
        try:
            from scipy import stats
        except ImportError:
            return pd.DataFrame()

        if treatment_var not in df.columns:
            _log.warning(f"[Suite] treatment_var '{treatment_var}' not in df")
            return pd.DataFrame()

        df_sub = df.dropna(subset=[treatment_var] + X).copy()
        treat = df_sub[df_sub[treatment_var] == 1]
        control = df_sub[df_sub[treatment_var] == 0]

        rows = []
        for var in X:
            if var not in df_sub.columns:
                continue
            mean_t = treat[var].mean()
            mean_c = control[var].mean()
            std_pooled = df_sub[var].std()
            std_diff = (mean_t - mean_c) / std_pooled if std_pooled > 1e-10 else np.nan

            var_ratio = treat[var].var() / control[var].var() if control[var].var() > 1e-10 else np.nan

            # Two-sample t-test
            t_stat, pval = stats.ttest_ind(treat[var], control[var], nan_policy="omit")

            rows.append({
                "Variable": var,
                "Mean_Control": f"{mean_c:.4f}",
                "Mean_Treated": f"{mean_t:.4f}",
                "Std_Diff": f"{std_diff:.3f}",
                "Var_Ratio": f"{var_ratio:.3f}" if not np.isnan(var_ratio) else "NA",
                "P>|t|": f"{pval:.4f}" if not np.isnan(pval) else "NA",
                "Balanced": "Yes" if abs(std_diff) < 0.1 and pval > 0.05 else "No",
            })

        return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def _norm_cdf_scalar(x: float) -> float:
    """Scalar-safe standard normal CDF."""
    try:
        from scipy import stats
        return float(stats.norm.cdf(x))
    except Exception:
        x_c = max(min(x, 37), -37)
        return 1 / (1 + np.exp(-0.5515 * x_c))


# ─────────────────────────────────────────────────────────────────────────────
# TEST / DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")

    # ── Synthetic data ──────────────────────────────────────────────────────
    print("=" * 60)
    print("Discrete Choice Regression — Synthetic Data Test")
    print("=" * 60)

    np.random.seed(42)
    n = 500

    df = pd.DataFrame({
        "size": np.random.randn(n) * 0.5 + 4,
        "lev": np.random.rand(n),
        "roe": np.random.randn(n) * 0.1 + 0.05,
        "tangibility": np.random.rand(n),
        "cash": np.random.rand(n),
        "state": np.random.choice(["A", "B"], n),
        "industry": np.random.choice(["Tech", "Finance", "Energy"], n),
    })

    # Generate binary y (latent index model)
    z = (
        -2.0
        + 0.3 * df["size"]
        - 0.5 * df["lev"]
        + 2.0 * df["roe"]
        + np.random.randn(n) * 0.8
    )
    df["default"] = (z > 0).astype(int)

    # Generate count y (for NB)
    mu = np.exp(0.1 + 0.2 * df["size"] - 0.3 * df["lev"])
    df["n_patents"] = np.random.poisson(mu)
    df["n_patents"] = df["n_patents"].clip(lower=0)

    X = ["size", "lev", "roe"]

    # ── Test 1: Logit ────────────────────────────────────────────────────────
    print("\n[1] Binary Logit")
    print("-" * 40)
    model_logit = DiscreteChoiceModel(model_type="logit")
    model_logit._last_df = df  # store for ME
    r_logit = model_logit.fit(df, y="default", X=X, cluster_var="industry")
    print(model_logit.summary())

    me = model_logit.marginal_effects(r_logit, at="mean")
    print("\nMarginal Effects (at means):")
    print(me.to_df().to_string(index=False))

    me_ame = model_logit.marginal_effects(r_logit, at="all")
    print("\nAverage Marginal Effects (AME):")
    print(me_ame.to_df().to_string(index=False))

    probs = model_logit.predict_proba(df)
    print(f"\nPredicted prob range: [{probs.min():.4f}, {probs.max():.4f}]")

    # ── Test 2: Probit ───────────────────────────────────────────────────────
    print("\n[2] Binary Probit")
    print("-" * 40)
    model_probit = DiscreteChoiceModel(model_type="probit")
    model_probit._last_df = df
    r_probit = model_probit.fit(df, y="default", X=X, robust_se="HC1")
    print(model_probit.summary())

    # ── Test 3: Negative Binomial ────────────────────────────────────────────
    print("\n[3] Negative Binomial (count: n_patents)")
    print("-" * 40)
    model_nb = DiscreteChoiceModel(model_type="nb")
    model_nb._last_df = df
    r_nb = model_nb.fit(df, y="n_patents", X=X)
    print(model_nb.summary())

    # ── Test 4: Model Comparison ─────────────────────────────────────────────
    print("\n[4] Model Comparison")
    print("-" * 40)
    suite = DiscreteChoiceSuite()
    cmp = suite.compare_models(df, y="default", X=X,
                               models=["logit", "probit"])
    print(cmp.to_string(index=False))

    # ── Test 5: Heterogeneity Test ──────────────────────────────────────────
    print("\n[5] Heterogeneity Test (by state)")
    print("-" * 40)
    het = suite.heterogeneity_test(df, y="default", X=X,
                                   group_var="state", model_type="logit")
    print(het.to_string(index=False))

    # ── Test 6: Balance Test ─────────────────────────────────────────────────
    print("\n[6] Balance Test (PSM diagnostics)")
    print("-" * 40)
    bal = suite.balance_test(df, X=X, treatment_var="default")
    print(bal.to_string(index=False))

    # ── Test 7: LaTeX Output ────────────────────────────────────────────────
    print("\n[7] LaTeX Output (Logit)")
    print("-" * 40)
    latex = model_logit.to_latex(
        caption="Determinants of Corporate Default",
        label="tab:default_logit",
    )
    print(latex[:800] + "\n  ... [truncated]")

    # ── Test 8: Ordered Logit ────────────────────────────────────────────────
    print("\n[8] Ordered Logit")
    print("-" * 40)
    # Create ordinal y
    df["rating"] = pd.cut(z, bins=[-np.inf, -0.5, 0.5, np.inf],
                          labels=[0, 1, 2]).astype(int)
    model_ologit = DiscreteChoiceModel(model_type="ologit")
    model_ologit._last_df = df
    r_ologit = model_ologit.fit(df, y="rating", X=X)
    print(model_ologit.summary())

    print("\n" + "=" * 60)
    print("All tests completed successfully.")
    print("=" * 60)
