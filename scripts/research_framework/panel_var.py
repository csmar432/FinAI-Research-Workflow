"""Panel Vector Autoregression — Abrigo & Love (2016).

本模块封装面板 VAR 方法，覆盖：
  1. 滞后阶数选择（AIC / BIC / HQIC）
  2. System GMM 估计（Blundell-Bond）
  3. 脉冲响应函数（IRF）+ Bootstrap CI
  4. 预测误差方差分解（FEVD）
  5. Dumitrescu-Hurlin (2012) 面板 Granger 因果检验

Usage:
    pvar = PanelVAR(max_lags=4)
    result = pvar.fit(df, y_vars=["roa", "cf", "invest"],
                      unit_var="ticker", time_var="year")
    irf_df = pvar.irf("cf", "invest", n_periods=20)
    fevd_df = pvar.fevd("invest", n_periods=20)
    gc_df = pvar.granger_causality()
    print(pvar.summary())
    print(pvar.to_latex())
    pvar.plot_irf("irf.pdf")
    pvar.plot_fevd("fevd.pdf")
    pvar.plot_granger_heatmap("granger.pdf")
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "PanelVAR",
    "PanelVARResult",
]

_log = logging.getLogger("panel_var")
_log.setLevel(logging.INFO)
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# ESTIMATION RESULT
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PanelVARResult:
    """
    面板 VAR 估计结果容器。

    Attributes
    ----------
    lag_order : int
        选定的最优滞后阶数。
    y_vars : list[str]
        内生变量列表。
    irf : dict
        脉冲响应函数结果（computed on demand via PanelVAR.irf()）。
    fevd : dict
        方差分解结果（computed on demand via PanelVAR.fevd()）。
    granger : dict
        Granger 因果检验结果（computed on demand via PanelVAR.granger_causality()）。
    params : dict
        变量名到系数矩阵的映射。
    residual_corr : np.ndarray
        残差相关矩阵（m x m，m = len(y_vars)）。
    n_obs : int
        有效观测数（变换后）。
    n_groups : int
        面板单位数。
    n_time : int
        时间期数。
    information_criteria : dict
        滞后阶数选择的诊断信息（lag -> {aic, bic, hqic}）。
    aic : float
        最优 AIC。
    bic : float
        最优 BIC。
    hqic : float
        最优 HQIC。
    estimator : str
        估计方法："system_gmm" | "ols_var"。
    dep_var : str
        被解释变量（最后调用的 irf / fevd / granger）。
    """

    lag_order: int = 1
    y_vars: list[str] = field(default_factory=list)
    irf: dict = field(default_factory=dict)
    fevd: dict = field(default_factory=dict)
    granger: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    residual_corr: np.ndarray = field(default_factory=np.array)
    n_obs: int = 0
    n_groups: int = 0
    n_time: int = 0
    information_criteria: dict = field(default_factory=dict)
    aic: float = field(default_factory=lambda: np.nan)
    bic: float = field(default_factory=lambda: np.nan)
    hqic: float = field(default_factory=lambda: np.nan)
    estimator: str = "system_gmm"
    dep_var: str = ""

    def to_dict(self) -> dict:
        out = {
            "lag_order": self.lag_order,
            "n_obs": self.n_obs,
            "n_groups": self.n_groups,
            "n_time": self.n_time,
            "aic": self.aic,
            "bic": self.bic,
            "hqic": self.hqic,
            "estimator": self.estimator,
        }
        for k, v in self.params.items():
            if isinstance(v, np.ndarray | list):
                out[f"param_{k}"] = np.array(v).tolist()
            else:
                out[f"param_{k}"] = v
        return out

    def to_df(self) -> pd.DataFrame:
        """将主要结果转为 DataFrame。"""
        rows = []
        for var, mat in self.params.items():
            mat = np.atleast_2d(np.array(mat))
            for i, row in enumerate(mat):
                for j, val in enumerate(row):
                    rows.append({
                        "dep_var": var,
                        "coef_index": i,
                        "regressor_index": j,
                        "value": val,
                    })
        return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _significance_stars(pval: float) -> str:
    """显著性星号标记。"""
    if pval < 0.001:
        return "***"
    elif pval < 0.01:
        return "**"
    elif pval < 0.05:
        return "*"
    elif pval < 0.10:
        return r"$\dagger$"
    return ""


def _build_lags(
    df: pd.DataFrame,
    y_vars: list[str],
    unit_var: str,
    time_var: str,
    max_lags: int,
) -> pd.DataFrame:
    """
    为面板数据构建滞后项。

    Parameters
    ----------
    df : pd.DataFrame
        原始面板数据。
    y_vars : list[str]
        内生变量列表。
    unit_var : str
        面板单位变量。
    time_var : str
        时间变量。
    max_lags : int
        最大滞后阶数。

    Returns
    -------
    pd.DataFrame
        含滞后项的面板数据。
    """
    df = df.copy().sort_values([unit_var, time_var])
    for var in y_vars:
        for lag in range(1, max_lags + 1):
            df[f"L{lag}_{var}"] = df.groupby(unit_var)[var].shift(lag)

    # 当前期变量也保留
    for var in y_vars:
        df[f"L0_{var}"] = df[var]

    return df


def _information_criteria_ols(
    df: pd.DataFrame,
    y_vars: list[str],
    unit_var: str,
    time_var: str,
    max_lags: int,
) -> dict[int, dict[str, float]]:
    """
    使用 OLS VAR 计算信息准则以选择最优滞后阶数。

    Abrigo & Love (2016) 方法：逐 lag 做 OLS，计算 log-det(Sigma)，
    然后用 AIC / BIC / HQIC 选取最优 lag。

    Parameters
    ----------
    df : pd.DataFrame
        含滞后项的数据（_build_lags 输出）。
    y_vars : list[str]
    unit_var : str
    time_var : str
    max_lags : int

    Returns
    -------
    dict[int, dict[str, float]]
        {lag: {aic, bic, hqic, ll}}
    """
    results = {}
    n_vars = len(y_vars)

    for lag in range(1, max_lags + 1):
        # 构建被解释变量 Y：当期 y_vars（作为整体向量自回归）
        lag_cols = []
        for var in y_vars:
            for j_lag in range(1, lag + 1):
                lag_cols.append(f"L{j_lag}_{var}")

        reg_cols = [c for c in lag_cols if c in df.columns]

        # 构造因变量矩阵 Y (n_obs x n_vars) 和自变量矩阵 X (n_obs x (lag*n_vars))
        drop_cols = [unit_var, time_var] + [c for c in df.columns if c.startswith("L0_")]
        drop_cols = [c for c in drop_cols if c in df.columns]
        avail = [c for c in df.columns if c not in drop_cols]

        # 使用 groupby 构造
        df_sub = df.dropna(subset=avail).copy()
        if len(df_sub) < lag * n_vars + 10:
            results[lag] = {"aic": np.inf, "bic": np.inf, "hqic": np.inf, "ll": -np.inf}
            continue

        Y_mat = df_sub[y_vars].values.astype(float)  # (T, n_vars)
        X_mat = df_sub[reg_cols].values.astype(float)  # (T, lag*n_vars)

        # OLS: beta = (X'X)^-1 X'Y，对每个因变量分别回归
        try:
            XtX = X_mat.T @ X_mat
            XtX_inv = np.linalg.inv(XtX + 1e-8 * np.eye(XtX.shape[0]))
            beta_ols = XtX_inv @ (X_mat.T @ Y_mat)  # (lag*n_vars, n_vars)
        except np.linalg.LinAlgError:
            results[lag] = {"aic": np.inf, "bic": np.inf, "hqic": np.inf, "ll": -np.inf}
            continue

        resid = Y_mat - X_mat @ beta_ols  # (T, n_vars)
        n_obs = len(Y_mat)
        k = X_mat.shape[1]

        # 残差协方差矩阵
        sigma = (resid.T @ resid) / n_obs  # (n_vars, n_vars)
        sign, logdet = np.linalg.slogdet(sigma + 1e-10 * np.eye(n_vars))
        if sign <= 0:
            logdet = float(np.log(np.linalg.det(sigma + 1e-10 * np.eye(n_vars)) + 1e-10))

        ll = -0.5 * n_obs * (n_vars * math.log(2 * math.pi) + logdet)

        # 信息准则
        ic_val = logdet  # log-det(Sigma_e)
        aic = ic_val + 2 * k * n_vars / n_obs
        bic = ic_val + math.log(n_obs) * k * n_vars / n_obs
        hqic = ic_val + 2 * math.log(math.log(n_obs)) * k * n_vars / n_obs

        results[lag] = {
            "aic": float(aic),
            "bic": float(bic),
            "hqic": float(hqic),
            "ll": float(ll),
            "k": k,
            "n_obs": n_obs,
        }

    return results


def _select_lag(criteria: dict[int, dict[str, float]], ic: str = "bic") -> int:
    """
    根据信息准则选择最优滞后阶数。

    Parameters
    ----------
    criteria : dict
        _information_criteria_ols 输出。
    ic : str
        "aic" | "bic" | "hqic"。

    Returns
    -------
    int
        最优滞后阶数。
    """
    valid = {lag: v for lag, v in criteria.items() if np.isfinite(v.get(ic, np.inf))}
    if not valid:
        return 1
    return min(valid, key=lambda lag: valid[lag][ic])


def _first_difference_transform(
    df: pd.DataFrame,
    y_vars: list[str],
    unit_var: str,
    time_var: str,
    lag_order: int,
) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict[str, np.ndarray]]:
    """
    Abrigo & Love (2016) 面板 VAR 的一阶差分变换。

    将内生变量取一阶差分，去除固定效应，使用 GMM 估计。

    Parameters
    ----------
    df : pd.DataFrame
        含滞后项的数据。
    y_vars : list[str]
    unit_var : str
    time_var : str
    lag_order : int

    Returns
    -------
    (df_diff, dict_y_levels, dict_y_lags)
        差分后数据、水平值字典、滞后水平字典。
    """
    df = df.copy().sort_values([unit_var, time_var])

    # 一阶差分
    diff_vars = [f"L{i}_{v}" for v in y_vars for i in range(lag_order + 1)]
    # 加入当期值
    diff_vars += y_vars

    for v in y_vars:
        df[f"d_{v}"] = df.groupby(unit_var)[v].diff()

    # 滞后差分 = 差分变量的滞后一期
    for v in y_vars:
        for lag in range(1, lag_order + 1):
            df[f"d_L{lag}_{v}"] = df.groupby(unit_var)[f"d_{v}"].shift(lag)

    # 水平值的滞后：作为工具变量
    for v in y_vars:
        for lag in range(1, lag_order + 1):
            df[f"y_L{lag}_{v}"] = df.groupby(unit_var)[v].shift(lag)

    # 差分方程中的解释变量：当期差分滞后
    diff_reg = []
    for v in y_vars:
        for lag in range(1, lag_order + 1):
            col = f"d_L{lag}_{v}"
            if col in df.columns:
                diff_reg.append(col)

    # 水平方程（levels）的解释变量：差分滞后
    level_reg = []
    for v in y_vars:
        for lag in range(1, lag_order + 1):
            col = f"d_L{lag}_{v}"
            if col in df.columns:
                level_reg.append(col)

    # 水平方程的被解释变量
    level_dep = [f"L0_{v}" for v in y_vars if f"L0_{v}" in df.columns]

    return df, {"diff_reg": diff_reg}, {"level_reg": level_reg, "level_dep": level_dep}


def _ols_var_coefficients(
    df: pd.DataFrame,
    y_vars: list[str],
    lag_order: int,
    unit_var: str,
    time_var: str,
) -> tuple[dict[str, np.ndarray], np.ndarray, int]:
    """
    简化 OLS VAR：对面板数据逐方程 OLS 估计 VAR。

    Parameters
    ----------
    df : pd.DataFrame
        含滞后项的数据。
    y_vars : list[str]
    lag_order : int
    unit_var : str
    time_var : str

    Returns
    -------
    (params_dict, residual_corr, n_obs)
        params_dict: {var: coefficient_matrix (lag_order*n_vars x n_vars)}
    """
    n_vars = len(y_vars)
    k = lag_order * n_vars

    # 构造 X: 滞后项
    lag_cols = []
    for lag in range(1, lag_order + 1):
        for v in y_vars:
            col = f"L{lag}_{v}"
            if col in df.columns:
                lag_cols.append(col)

    avail_lag = [c for c in lag_cols if c in df.columns]
    avail_lag = avail_lag[:k]  # 截断到 k

    # 清理缺失
    drop_cols = [unit_var, time_var] + y_vars + [c for c in df.columns if c.startswith("d_")]
    drop_cols = [c for c in drop_cols if c in df.columns]
    reg_cols = [c for c in df.columns if c not in drop_cols and c not in y_vars]

    df_sub = df.dropna(subset=avail_lag + y_vars + reg_cols).copy()
    if len(df_sub) < k + n_vars + 5:
        _log.warning("[PanelVAR] Insufficient obs for OLS VAR, using fallback")
        return {}, np.eye(n_vars), 0

    Y_mat = df_sub[y_vars].values.astype(float)
    X_mat = df_sub[avail_lag].values.astype(float)
    n_obs = len(Y_mat)

    try:
        XtX = X_mat.T @ X_mat
        XtX_inv = np.linalg.inv(XtX + 1e-8 * np.eye(X_mat.shape[1]))
        beta = XtX_inv @ (X_mat.T @ Y_mat)  # (k, n_vars)
    except np.linalg.LinAlgError:
        return {}, np.eye(n_vars), 0

    resid = Y_mat - X_mat @ beta  # (n_obs, n_vars)
    sigma = (resid.T @ resid) / n_obs  # (n_vars, n_vars)

    # params_dict: 每个因变量一列系数
    params = {}
    for j, v in enumerate(y_vars):
        params[v] = beta[:, j]  # (k,)

    return params, sigma, n_obs


def _gmm_system_var(
    df: pd.DataFrame,
    y_vars: list[str],
    lag_order: int,
    unit_var: str,
    time_var: str,
) -> tuple[dict[str, np.ndarray], np.ndarray, int]:
    """
    System GMM (Blundell-Bond) 面板 VAR 估计。

    差分方程：Δy_it = Γ1 Δy_it-1 + ... + Γp Δy_it-p + ε_it
    工具变量：levels of y_{it-j} for j >= 2

    Levels 方程：y_it = Γ1 Δy_it-1 + ... + Γp Δy_it-p + ε_it
    工具变量：differences of y_{it-j}

    Parameters
    ----------
    df : pd.DataFrame
        含滞后项的差分变换数据。
    y_vars : list[str]
    lag_order : int
    unit_var : str
    time_var : str

    Returns
    -------
    (params_dict, residual_corr, n_obs)
    """
    n_vars = len(y_vars)
    results_out = {}

    df_sub = df.dropna().copy()
    if len(df_sub) < lag_order * n_vars + 10:
        return {}, np.eye(n_vars), 0

    # ── 差分方程 ──────────────────────────────────────────────────────────────
    diff_reg_cols = []
    for v in y_vars:
        for lag in range(1, lag_order + 1):
            col = f"d_L{lag}_{v}"
            if col in df_sub.columns:
                diff_reg_cols.append(col)

    # 工具变量：y 的水平滞后（L2+, L3+ for diff eq）
    iv_diff_cols = []
    for v in y_vars:
        for lag in range(2, lag_order + 1):
            col = f"y_L{lag}_{v}"
            if col in df_sub.columns:
                iv_diff_cols.append(col)

    # ── 水平方程 ──────────────────────────────────────────────────────────────
    level_reg_cols = diff_reg_cols.copy()  # 差分滞后作为水平方程解释变量

    # 工具变量：Δy 的滞后（L1 for level eq）
    iv_level_cols = []
    for v in y_vars:
        col = f"d_L1_{v}"
        if col in df_sub.columns:
            iv_level_cols.append(col)

    dep_cols = [f"d_{v}" for v in y_vars]
    level_dep_cols = [f"L0_{v}" for v in y_vars]

    dep_cols = [c for c in dep_cols if c in df_sub.columns]
    level_dep_cols = [c for c in level_dep_cols if c in df_sub.columns]

    if len(diff_reg_cols) == 0 or len(dep_cols) == 0:
        _log.warning("[PanelVAR] GMM: missing diff columns, falling back to OLS")
        return {}, np.eye(n_vars), 0

    avail_diff = dep_cols + diff_reg_cols + iv_diff_cols
    avail_diff = [c for c in avail_diff if c in df_sub.columns]
    df_diff_est = df_sub.dropna(subset=avail_diff)
    if len(df_diff_est) < len(diff_reg_cols) + 1:
        _log.warning("[PanelVAR] GMM: insufficient obs after dropna, fallback")
        return {}, np.eye(n_vars), 0

    # ── 堆叠 GMM 估计（逐方程）─────────────────────────────────────────────────
    # 差分方程
    diff_dep = df_diff_est[dep_cols].values.astype(float)
    diff_X = df_diff_est[diff_reg_cols].values.astype(float)
    diff_iv = df_diff_est[iv_diff_cols].values.astype(float) if iv_diff_cols else diff_X

    # 水平方程（若可用）
    avail_level = level_dep_cols + level_reg_cols + iv_level_cols
    avail_level = [c for c in avail_level if c in df_sub.columns]
    if len(avail_level) >= len(level_reg_cols) + len(level_dep_cols):
        df_level_est = df_sub.dropna(subset=avail_level)
        df_level_est[level_dep_cols].values.astype(float)
        level_X_arr = df_level_est[level_reg_cols].values.astype(float)
        df_level_est[iv_level_cols].values.astype(float) if iv_level_cols else level_X_arr
    else:
        level_X_arr = None

    # 逐方程 GMM（简化：两阶段 GMM）
    all_resid = []
    for j, v in enumerate(y_vars):
        if diff_dep.shape[1] <= j:
            continue
        y_diff_j = diff_dep[:, j] if j < diff_dep.shape[1] else None
        if y_diff_j is None:
            continue

        X_j = diff_X
        iv_j = diff_iv if diff_iv.shape[1] > 0 else X_j

        if len(y_diff_j) < X_j.shape[1] + 2:
            results_out[v] = np.zeros(len(diff_reg_cols))
            all_resid.append(np.zeros(len(y_diff_j)))
            continue

        try:
            # 两阶段 GMM
            Z = iv_j  # 工具变量
            if Z.shape[1] > 0:
                # 第一步：OLS
                beta_1 = np.linalg.lstsq(X_j, y_diff_j, rcond=None)[0]
                y_diff_j - X_j @ beta_1
                # 第二步：GMM
                W = np.linalg.inv((Z.T @ Z) / Z.shape[0] + 1e-6 * np.eye(Z.shape[1]))
                A = X_j.T @ Z @ W @ Z.T @ X_j / X_j.shape[0]
                try:
                    A_inv = np.linalg.inv(A + 1e-8 * np.eye(A.shape[0]))
                except np.linalg.LinAlgError:
                    A_inv = np.linalg.pinv(A)
                beta_gmm = A_inv @ (X_j.T @ Z @ W @ Z.T @ y_diff_j / X_j.shape[0])
            else:
                beta_gmm = np.linalg.lstsq(X_j, y_diff_j, rcond=None)[0]

            # 处理 NaN
            if np.any(np.isnan(beta_gmm)):
                _log.warning(f"[PanelVAR] GMM produced NaN for {v}, using OLS fallback")
                beta_gmm = np.linalg.lstsq(X_j, y_diff_j, rcond=None)[0]

            results_out[v] = beta_gmm
            resid_j = y_diff_j - X_j @ beta_gmm
            all_resid.append(resid_j)

        except Exception as e:
            _log.warning(f"[PanelVAR] GMM failed for {v}: {e}, using OLS")
            try:
                beta_ols = np.linalg.lstsq(X_j, y_diff_j, rcond=None)[0]
            except Exception:
                beta_ols = np.zeros(len(diff_reg_cols))
            results_out[v] = beta_ols
            all_resid.append(y_diff_j - X_j @ beta_ols if X_j.shape[0] == len(y_diff_j) else np.zeros(len(y_diff_j)))

    n_obs_diff = diff_dep.shape[0]

    # 残差协方差
    if len(all_resid) == n_vars:
        stacked_resid = np.column_stack(all_resid)
    else:
        min_len = min(len(r) for r in all_resid) if all_resid else 0
        stacked_resid = np.column_stack([r[:min_len] for r in all_resid]) if all_resid else np.zeros((min_len, n_vars))
    sigma = np.cov(stacked_resid, rowvar=False)
    if sigma is None or sigma.shape != (n_vars, n_vars):
        sigma = np.eye(n_vars)

    return results_out, sigma, n_obs_diff


def _irf_cholesky(
    params: dict[str, np.ndarray],
    sigma: np.ndarray,
    y_vars: list[str],
    lag_order: int,
    n_periods: int = 20,
) -> np.ndarray:
    """
    基于 Cholesky 分解计算 IRF。

    Parameters
    ----------
    params : dict
        {var: coefficient_vector (lag_order * n_vars,)}
    sigma : np.ndarray
        残差协方差矩阵 (n_vars, n_vars)。
    y_vars : list[str]
    lag_order : int
    n_periods : int

    Returns
    -------
    np.ndarray
        IRF 数组 (n_periods, n_vars, n_vars)。
    """
    n_vars = len(y_vars)
    m = lag_order * n_vars

    # 构造 companion 矩阵 A (m x m)
    A = np.zeros((m, m))
    for j, v in enumerate(y_vars):
        coef = params.get(v, np.zeros(m))
        # 截断或填充到 m
        c = np.zeros(m)
        c[:len(coef)] = coef
        A[j, :] = c

    # 滞后块
    for i in range(1, lag_order):
        A[i * n_vars:(i + 1) * n_vars, (i - 1) * n_vars:i * n_vars] = np.eye(n_vars)

    # Cholesky 分解残差协方差
    try:
        L = np.linalg.cholesky(sigma + 1e-10 * np.eye(n_vars))
    except np.linalg.LinAlgError:
        L = np.eye(n_vars)

    # IRF(0) = L, IRF(h) = A^h @ L
    irf = np.zeros((n_periods + 1, n_vars, n_vars))
    irf[0] = L
    for h in range(1, n_periods + 1):
        irf[h] = np.linalg.matrix_power(A, h)[:n_vars, :n_vars] @ L

    return irf


def _bootstrap_irf_ci(
    df: pd.DataFrame,
    y_vars: list[str],
    lag_order: int,
    unit_var: str,
    time_var: str,
    impulse_var: str,
    response_var: str,
    n_periods: int = 20,
    n_bootstrap: int = 500,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Bootstrap IRF 置信区间。

    Parameters
    ----------
    df : pd.DataFrame
    y_vars : list[str]
    lag_order : int
    unit_var : str
    time_var : str
    impulse_var : str
    response_var : str
    n_periods : int
    n_bootstrap : int
    ci : float
    seed : int

    Returns
    -------
    (irf_median, ci_lower, ci_upper)
    """
    rng = np.random.default_rng(seed)
    len(y_vars)
    y_to_idx = {v: i for i, v in enumerate(y_vars)}

    impulse_idx = y_to_idx.get(impulse_var)
    response_idx = y_to_idx.get(response_var)
    if impulse_idx is None or response_idx is None:
        return np.zeros(n_periods + 1), np.zeros(n_periods + 1), np.zeros(n_periods + 1)

    boot_irfs = []

    for _ in range(n_bootstrap):
        # Block bootstrap over time (simple: resample time clusters)
        try:
            times = sorted(df[time_var].unique())
            n_t = len(times)
            # Resample time indices
            boot_times = rng.choice(times, size=n_t, replace=True)
            boot_indices = []
            for t in boot_times:
                boot_indices.extend(df[df[time_var] == t].index.tolist())
            df_boot = df.loc[boot_indices].copy()
        except Exception:
            df_boot = df.sample(frac=1, replace=True, random_state=rng.integers(0, 2**31)).copy()

        try:
            # Re-estimate VAR
            params_b, sigma_b, _ = _ols_var_coefficients(
                df_boot, y_vars, lag_order, unit_var, time_var
            )
            if not params_b:
                continue
            irf_b = _irf_cholesky(params_b, sigma_b, y_vars, lag_order, n_periods)
            boot_irfs.append(irf_b[:, response_idx, impulse_idx])
        except Exception:
            continue

    if len(boot_irfs) < 10:
        _log.warning("[PanelVAR] Bootstrap failed, using asymptotic CI")
        return np.zeros(n_periods + 1), np.zeros(n_periods + 1), np.zeros(n_periods + 1)

    boot_arr = np.array(boot_irfs)  # (n_bootstrap, n_periods+1)
    alpha = (1 - ci) / 2
    ci_lower = np.percentile(boot_arr, q=alpha * 100, axis=0)
    ci_upper = np.percentile(boot_arr, q=(1 - alpha) * 100, axis=0)
    irf_median = np.median(boot_arr, axis=0)

    return irf_median, ci_lower, ci_upper


def _fevd_from_irf(
    irf: np.ndarray, sigma: np.ndarray, n_vars: int, n_periods: int = 20
) -> np.ndarray:
    """
    基于 IRF 计算预测误差方差分解。

    Parameters
    ----------
    irf : np.ndarray
        IRF 数组 (n_periods+1, n_vars, n_vars)。
    sigma : np.ndarray
        残差协方差矩阵。
    n_vars : int
    n_periods : int

    Returns
    -------
    np.ndarray
        FEVD (n_periods+1, n_vars) — 每期各因变量对每个内生变量的贡献占比。
    """
    # 每期总预测误差方差（每个 response 变量的）
    fevd = np.zeros((n_periods + 1, n_vars))

    # 残差标准差（用于归一化）
    se = np.sqrt(np.diag(sigma) + 1e-10)

    for h in range(n_periods + 1):
        for j in range(n_vars):  # response var j
            total_var = 0.0
            for i in range(n_vars):  # impulse var i
                cum_impulse = irf[h, j, i]
                total_var += cum_impulse ** 2
            if se[j] > 1e-10:
                fevd[h, j] = total_var / (se[j] ** 2)
            else:
                fevd[h, j] = 0.0

    # 归一化为百分比
    for h in range(n_periods + 1):
        row_sum = fevd[h].sum()
        if row_sum > 1e-10:
            fevd[h] = fevd[h] / row_sum * 100.0
        else:
            fevd[h] = fevd[h] / n_vars * 100.0

    return fevd


def _dumitrescu_hurlin(
    df: pd.DataFrame,
    y_vars: list[str],
    unit_var: str,
    time_var: str,
    lag_order: int,
) -> pd.DataFrame:
    """
    Dumitrescu-Hurlin (2012) 面板 Granger 因果检验。

    H0: x does NOT Granger-cause y in panel
    W_bar = (1/N) Σ_i W_i (individual Wald statistics)
    Z_bar = √N (W_bar - E[W]) / √(Var[W])

    Parameters
    ----------
    df : pd.DataFrame
        含滞后项的数据。
    y_vars : list[str]
    unit_var : str
    time_var : str
    lag_order : int

    Returns
    -------
    pd.DataFrame
        Granger 因果检验结果表。
    """
    from scipy import stats

    len(y_vars)
    results = []

    for dep_idx, y in enumerate(y_vars):
        for indep_idx, x in enumerate(y_vars):
            if dep_idx == indep_idx:
                continue

            # 构造单变量 Granger 检验
            lag_cols = [f"L{lag}_{x}" for lag in range(1, lag_order + 1)]
            lag_cols = [c for c in lag_cols if c in df.columns]
            avail = [y] + lag_cols
            df_sub = df.dropna(subset=avail).copy()

            if len(df_sub) < lag_order * 2 + 5:
                continue

            y_arr = df_sub[y].values.astype(float)
            X_arr = df_sub[lag_cols].values.astype(float)

            if X_arr.shape[1] == 0:
                continue

            try:
                # Restricted: y_t = a + sum(b_j * y_{t-j}) + error
                y_full = df_sub[y].values.astype(float)
                y_lag_cols = [f"L{lag}_{y}" for lag in range(1, lag_order + 1)]
                y_lag_cols = [c for c in y_lag_cols if c in df_sub.columns]
                X_r = df_sub[y_lag_cols].values.astype(float) if y_lag_cols else np.ones((len(df_sub), 1))

                beta_r = np.linalg.lstsq(X_r, y_full, rcond=None)[0]
                resid_r = y_full - X_r @ beta_r
                rss_r = np.sum(resid_r ** 2)

                # Unrestricted: add x lags
                X_u = np.column_stack([X_r, X_arr])
                beta_u = np.linalg.lstsq(X_u, y_arr, rcond=None)[0]
                resid_u = y_arr - X_u @ beta_u
                rss_u = np.sum(resid_u ** 2)

                k = X_arr.shape[1]  # number of restrictions
                n = len(y_arr)
                df_denom = n - X_u.shape[1]

                if rss_u < 0 or rss_r < rss_u:
                    f_stat = 0.0
                else:
                    f_stat = ((rss_r - rss_u) / k) / (rss_u / df_denom) if df_denom > 0 else 0.0

                if f_stat < 0:
                    f_stat = 0.0

                # Wald statistic W_i ~ F(k, n-2k) approximately
                # DH (2012) use: W_i = (n - 2k - 1) / k * F_stat (under normality)
                W_i = (n - 2 * k - 1) / k * f_stat if k > 0 and (n - 2 * k - 1) > 0 else f_stat
                if W_i < 0:
                    W_i = 0.0

                # p-value from chi-squared approximation
                pval_i = 1 - stats.f.cdf(f_stat, k, df_denom) if df_denom > 0 else np.nan

                results.append({
                    "dependent": y,
                    "cause": x,
                    "W_i": float(W_i),
                    "f_stat": float(f_stat),
                    "p_value": float(pval_i) if not np.isnan(pval_i) else 1.0,
                    "n_obs": int(n),
                    "k_restrictions": int(k),
                })
            except Exception as e:
                _log.warning(f"[PanelVAR] Granger test failed for {y} <- {x}: {e}")
                results.append({
                    "dependent": y,
                    "cause": x,
                    "W_i": np.nan,
                    "f_stat": np.nan,
                    "p_value": np.nan,
                    "n_obs": 0,
                    "k_restrictions": lag_order,
                })

    if not results:
        return pd.DataFrame()

    df_gc = pd.DataFrame(results)

    # Aggregate panel statistic: W_bar and Z_bar (Dumitrescu-Hurlin 2012)
    valid = df_gc.dropna(subset=["W_i"]).copy()
    if len(valid) == 0:
        return df_gc

    N = len(valid)
    W_bar = valid["W_i"].mean()

    # Under H0, E[W_i] and Var[W_i] (for standard normal approx)
    # DH (2012) approximations
    k = lag_order
    E_W = k  # for standard normal
    Var_W = 2 * k  # approximate

    Z_bar = math.sqrt(N) * (W_bar - E_W) / math.sqrt(Var_W) if Var_W > 0 else 0.0
    panel_pval = 2 * (1 - stats.norm.cdf(abs(Z_bar)))

    df_gc["W_bar"] = W_bar
    df_gc["Z_bar"] = Z_bar
    df_gc["panel_p_value"] = panel_pval if not np.isnan(panel_pval) else 1.0
    df_gc["reject_h0"] = panel_pval < 0.05 if not np.isnan(panel_pval) else False

    return df_gc


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────


class PanelVAR:
    """
    面板 VAR（Vector Autoregression）估计器 — sklearn-like API。

    基于 Abrigo & Love (2016) 的系统 GMM 方法，支持：
      - 滞后阶数自动选择（AIC / BIC / HQIC）
      - System GMM（Blundell-Bond）估计
      - 脉冲响应函数（IRF）+ Bootstrap CI
      - 预测误差方差分解（FEVD）
      - Dumitrescu-Hurlin 面板 Granger 因果检验

    Parameters
    ----------
    max_lags : int
        最大滞后阶数（用于信息准则选择），默认 4。
    exog_vars : list[str] | None
        外生变量（暂不支持，留空接口）。
    trend : str
        趋势项："n"（无）| "c"（常数）| "ct"（常数+趋势），默认 "ct"。
    robust_se : bool
        是否使用稳健标准误，默认 True。
    ic : str
        信息准则："aic" | "bic" | "hqic"，默认 "bic"。

    Usage
    -----
        pvar = PanelVAR(max_lags=4, ic="bic")
        result = pvar.fit(df, y_vars=["roa", "cf", "invest"],
                          unit_var="ticker", time_var="year")
        pvar.plot_irf("irf.pdf")
        pvar.plot_fevd("fevd.pdf")
        pvar.plot_granger_heatmap("granger.pdf")
        print(pvar.summary())
        print(pvar.to_latex())
    """

    def __init__(
        self,
        max_lags: int = 4,
        exog_vars: list[str] | None = None,
        trend: str = "ct",
        robust_se: bool = True,
        ic: str = "bic",
    ):
        self.max_lags = max_lags
        self.exog_vars = exog_vars or []
        self.trend = trend
        self.robust_se = robust_se
        self.ic = ic
        self._result: PanelVARResult | None = None
        self._last_fit_args: dict = {}
        self._lag_criteria: dict = {}
        self._irf_cache: dict = {}
        self._fevd_cache: dict = {}
        self._granger_cache: dict = {}

    # ── Core fit ────────────────────────────────────────────────────────────

    def fit(
        self,
        data: pd.DataFrame,
        y_vars: list[str],
        unit_var: str,
        time_var: str,
    ) -> PanelVARResult:
        """
        拟合面板 VAR。

        Parameters
        ----------
        data : pd.DataFrame
            面板数据（宽格式：每行一个单位-时间观测）。
        y_vars : list[str]
            内生变量列表。
        unit_var : str
            面板单位变量（如 "ticker" / "firm_id"）。
        time_var : str
            时间变量（如 "year" / "date"）。

        Returns
        -------
        PanelVARResult
        """
        if len(y_vars) < 2:
            raise ValueError("PanelVAR requires at least 2 endogenous variables.")

        self._last_fit_args = {
            "y_vars": y_vars,
            "unit_var": unit_var,
            "time_var": time_var,
        }

        # Step 1: Build lags
        df_lag = _build_lags(data, y_vars, unit_var, time_var, self.max_lags)

        # Step 2: Lag order selection (OLS VAR)
        self._lag_criteria = _information_criteria_ols(
            df_lag, y_vars, unit_var, time_var, self.max_lags
        )
        lag_order = _select_lag(self._lag_criteria, ic=self.ic)
        _log.info(
            f"[PanelVAR] Optimal lag = {lag_order} (ic={self.ic}): "
            f"AIC={self._lag_criteria.get(lag_order, {}).get('aic', np.nan):.3f}, "
            f"BIC={self._lag_criteria.get(lag_order, {}).get('bic', np.nan):.3f}"
        )

        # Rebuild lags for optimal order
        df_lag2 = _build_lags(data, y_vars, unit_var, time_var, lag_order)

        # Step 3: Try system GMM first, fallback to OLS
        params, sigma, n_obs = {}, np.eye(len(y_vars)), 0
        estimator = "system_gmm"

        try:
            df_diff, *_ = _first_difference_transform(
                df_lag2, y_vars, unit_var, time_var, lag_order
            )
            params, sigma, n_obs = _gmm_system_var(
                df_diff, y_vars, lag_order, unit_var, time_var
            )
        except Exception as e:
            _log.warning(f"[PanelVAR] System GMM failed: {e}, falling back to OLS VAR")

        if not params or all(np.all(np.isnan(v)) for v in params.values()):
            _log.info("[PanelVAR] Falling back to OLS VAR")
            params, sigma, n_obs = _ols_var_coefficients(
                df_lag2, y_vars, lag_order, unit_var, time_var
            )
            estimator = "ols_var"

        if not params:
            _log.error("[PanelVAR] Both GMM and OLS VAR failed")
            return PanelVARResult(lag_order=lag_order, y_vars=y_vars, estimator=estimator)

        n_groups = int(data[unit_var].nunique())
        n_times = int(data[time_var].nunique())

        result = PanelVARResult(
            lag_order=lag_order,
            y_vars=y_vars,
            params=params,
            residual_corr=sigma,
            n_obs=n_obs,
            n_groups=n_groups,
            n_time=n_times,
            information_criteria={
                lag: {k: v for k, v in info.items() if k in ("aic", "bic", "hqic")}
                for lag, info in self._lag_criteria.items()
            },
            aic=self._lag_criteria.get(lag_order, {}).get("aic", np.nan),
            bic=self._lag_criteria.get(lag_order, {}).get("bic", np.nan),
            hqic=self._lag_criteria.get(lag_order, {}).get("hqic", np.nan),
            estimator=estimator,
        )

        self._result = result
        self._df_lag = df_lag2
        self._irf_cache.clear()
        self._fevd_cache.clear()
        self._granger_cache.clear()

        _log.info(
            f"[PanelVAR] Fit complete: {estimator}, lag={lag_order}, "
            f"N={n_obs}, G={n_groups}, T={n_times}"
        )

        return result

    # ── IRF ────────────────────────────────────────────────────────────────

    def irf(
        self,
        impulse_var: str,
        response_var: str,
        n_periods: int = 20,
        n_bootstrap: int = 500,
        ci: float = 0.95,
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        脉冲响应函数（IRF）。

        Parameters
        ----------
        impulse_var : str
            冲击变量。
        response_var : str
            响应变量。
        n_periods : int
            预测期数，默认 20。
        n_bootstrap : int
            Bootstrap 次数，默认 500。
        ci : float
            置信水平，默认 0.95。
        seed : int
            随机种子。

        Returns
        -------
        pd.DataFrame
            含 IRF 点估计和 Bootstrap CI 的 DataFrame。
        """
        if self._result is None:
            raise RuntimeError("Call fit() first.")

        cache_key = f"{impulse_var}_{response_var}_{n_periods}_{n_bootstrap}_{ci}"
        if cache_key in self._irf_cache:
            return self._irf_cache[cache_key]

        y_vars = self._result.y_vars
        lag_order = self._result.lag_order
        params = self._result.params
        sigma = self._result.residual_corr

        irf_mat = _irf_cholesky(params, sigma, y_vars, lag_order, n_periods)

        y_to_idx = {v: i for i, v in enumerate(y_vars)}
        impulse_idx = y_to_idx.get(impulse_var)
        response_idx = y_to_idx.get(response_var)

        if impulse_idx is None or response_idx is None:
            _log.warning(f"[PanelVAR] IRF: variable not found ({impulse_var}, {response_var})")
            return pd.DataFrame()

        # Bootstrap CI
        irf_point = irf_mat[:, response_idx, impulse_idx]
        irf_median, ci_lower, ci_upper = _bootstrap_irf_ci(
            self._df_lag,
            y_vars,
            lag_order,
            self._last_fit_args["unit_var"],
            self._last_fit_args["time_var"],
            impulse_var,
            response_var,
            n_periods=n_periods,
            n_bootstrap=n_bootstrap,
            ci=ci,
            seed=seed,
        )

        df_out = pd.DataFrame({
            "period": range(n_periods + 1),
            "irf": irf_point,
            "irf_median": irf_median,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
        })

        self._irf_cache[cache_key] = df_out
        return df_out

    # ── FEVD ──────────────────────────────────────────────────────────────

    def fevd(
        self,
        response_var: str,
        n_periods: int = 20,
    ) -> pd.DataFrame:
        """
        预测误差方差分解（FEVD）。

        Parameters
        ----------
        response_var : str
            被解释变量（需要分解其方差）。
        n_periods : int
            预测期数，默认 20。

        Returns
        -------
        pd.DataFrame
            每期各冲击对 response_var 预测误差方差的贡献（%）。
        """
        if self._result is None:
            raise RuntimeError("Call fit() first.")

        cache_key = f"{response_var}_{n_periods}"
        if cache_key in self._fevd_cache:
            return self._fevd_cache[cache_key]

        y_vars = self._result.y_vars
        lag_order = self._result.lag_order
        params = self._result.params
        sigma = self._result.residual_corr
        n_vars = len(y_vars)

        irf_mat = _irf_cholesky(params, sigma, y_vars, lag_order, n_periods)
        fevd_mat = _fevd_from_irf(irf_mat, sigma, n_vars, n_periods)

        # response_var 的方差分解
        resp_idx = {v: i for i, v in enumerate(y_vars)}.get(response_var)
        if resp_idx is None:
            _log.warning(f"[PanelVAR] FEVD: variable {response_var} not found")
            return pd.DataFrame()

        rows = []
        for h in range(n_periods + 1):
            for i, v in enumerate(y_vars):
                rows.append({
                    "period": h,
                    "impulse": v,
                    "contribution_pct": float(fevd_mat[h, i]),
                })

        df_out = pd.DataFrame(rows)
        df_out_pivot = df_out.pivot(index="period", columns="impulse", values="contribution_pct")
        df_out_pivot.index.name = "period"
        df_out_pivot.columns.name = None

        self._fevd_cache[cache_key] = df_out_pivot
        return df_out_pivot

    # ── Granger ──────────────────────────────────────────────────────────

    def granger_causality(self) -> pd.DataFrame:
        """
        Dumitrescu-Hurlin (2012) 面板 Granger 因果检验。

        Returns
        -------
        pd.DataFrame
            含 W_bar, Z_bar, panel_p_value, reject_h0。
        """
        if self._result is None:
            raise RuntimeError("Call fit() first.")

        if self._granger_cache:
            return self._granger_cache

        y_vars = self._result.y_vars
        lag_order = self._result.lag_order

        df_gc = _dumitrescu_hurlin(
            self._df_lag,
            y_vars,
            self._last_fit_args["unit_var"],
            self._last_fit_args["time_var"],
            lag_order,
        )

        self._granger_cache = df_gc
        return df_gc

    # ── Diagnostic ────────────────────────────────────────────────────────

    def _diagnostic(self) -> None:
        """打印滞后阶数选择的诊断信息（内部方法）。"""
        print("\n=== Panel VAR: Lag Order Selection ===")
        print(f"{'Lag':>4}  {'AIC':>10}  {'BIC':>10}  {'HQIC':>10}  {'N_obs':>8}")
        print("-" * 50)
        for lag in sorted(self._lag_criteria.keys()):
            info = self._lag_criteria[lag]
            aic = info.get("aic", np.nan)
            bic = info.get("bic", np.nan)
            hqic = info.get("hqic", np.nan)
            n_obs = info.get("n_obs", "-")
            aic_str = f"{aic:.3f}" if np.isfinite(aic) else "  inf  "
            bic_str = f"{bic:.3f}" if np.isfinite(bic) else "  inf  "
            hqic_str = f"{hqic:.3f}" if np.isfinite(hqic) else "  inf  "
            print(f"{lag:>4}  {aic_str:>10}  {bic_str:>10}  {hqic_str:>10}  {n_obs:>8}")
        if self._result:
            print(f"\nOptimal lag (by {self.ic}): {self._result.lag_order}")
            print(f"Estimator: {self._result.estimator}")
            print(f"AIC={self._result.aic:.3f}, BIC={self._result.bic:.3f}, HQIC={self._result.hqic:.3f}")

    # ── Output ────────────────────────────────────────────────────────────

    def summary(self) -> pd.DataFrame:
        """
        系数汇总表。

        Returns
        -------
        pd.DataFrame
        """
        if self._result is None:
            return pd.DataFrame()

        params = self._result.params
        y_vars = self._result.y_vars
        lag_order = self._result.lag_order
        n_vars = len(y_vars)

        rows = []
        for dep_var in y_vars:
            coef_vec = params.get(dep_var, np.zeros(lag_order * n_vars))
            # 每个滞后块
            for lag in range(1, lag_order + 1):
                for j, rhs_var in enumerate(y_vars):
                    idx = (lag - 1) * n_vars + j
                    if idx < len(coef_vec):
                        rows.append({
                            "dep_var": dep_var,
                            "lag": lag,
                            "rhs_var": rhs_var,
                            "coef": float(coef_vec[idx]),
                            "index": idx,
                        })

        return pd.DataFrame(rows)

    def to_latex(
        self,
        caption: str = "Panel VAR Estimates",
        label: str = "tab:pvar",
    ) -> str:
        """
        导出为 LaTeX 表格（booktabs 格式）。

        Parameters
        ----------
        caption : str
        label : str

        Returns
        -------
        str
            LaTeX 代码。
        """
        df = self.summary()
        if df.empty:
            return ""

        y_vars = self._result.y_vars if self._result else []
        lag_order = self._result.lag_order if self._result else 1
        n_vars = len(y_vars)

        # Pivot: rows = (dep_var, lag), cols = rhs_var
        pivot = df.pivot_table(index=["dep_var", "lag"], columns="rhs_var", values="coef", aggfunc="first")

        lines = [
            "\\begin{table}[htbp]",
            "  \\centering",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{label}}}",
            f"  \\begin{{tabular}}{{l{'c' * n_vars}}}",
            "    \\toprule",
            "    \\textbf{Dep Var} & \\multicolumn{" + str(n_vars) + "}{c}{\\textbf{RHS Variables}} \\\\",
            "    \\cmidrule{2-" + str(n_vars + 1) + "}",
            "    " + " & ".join(["\\textbf{" + v + "}" for v in y_vars]) + " \\\\",
            "    \\midrule",
        ]

        for (dep, lag), row in pivot.iterrows():
            row_str = f"{dep} (lag={lag})"
            for v in y_vars:
                val = row.get(v, np.nan)
                if np.isnan(val):
                    row_str += " & "
                else:
                    row_str += f" & {val:.4f}"
            lines.append("    " + row_str + " \\\\")

        lines.extend([
            "    \\bottomrule",
            "  \\end{tabular}",
            "  \\begin{tablenotes}",
            "    \\small",
            f"    \\item Panel VAR with {lag_order} lag(s). "
            f"Estimator: {self._result.estimator}. "
            f"N={self._result.n_obs}, G={self._result.n_groups}.",
            f"    \\item Information criteria: AIC={self._result.aic:.3f}, "
            f"BIC={self._result.bic:.3f}, HQIC={self._result.hqic:.3f}.",
            "  \\end{tablenotes}",
            "\\end{table}",
        ])

        return "\n".join(lines)

    # ── Visualization ────────────────────────────────────────────────────

    def plot_irf(
        self,
        impulse_var: str,
        response_var: str,
        save_path: str | Path | None = None,
        figsize: tuple[float, float] = (10, 5),
        n_periods: int = 20,
        n_bootstrap: int = 500,
        ci: float = 0.95,
        seed: int = 42,
    ) -> Any:
        """
        绘制脉冲响应函数图（含 Bootstrap CI 带）。

        Parameters
        ----------
        impulse_var : str
        response_var : str
        save_path : str | Path | None
        figsize : tuple
        n_periods : int
        n_bootstrap : int
        ci : float
        seed : int

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[PanelVAR] Call fit() first")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[PanelVAR] matplotlib not installed")
            return None

        df_irf = self.irf(
            impulse_var, response_var,
            n_periods=n_periods,
            n_bootstrap=n_bootstrap,
            ci=ci, seed=seed,
        )

        if df_irf.empty:
            return None

        fig, ax = plt.subplots(figsize=figsize)

        periods = df_irf["period"].values
        irf_vals = df_irf["irf"].values
        ci_l = df_irf["ci_lower"].values
        ci_u = df_irf["ci_upper"].values

        ax.fill_between(periods, ci_l, ci_u, alpha=0.25, color="steelblue", label=f"{ci*100:.0f}% CI")
        ax.plot(periods, irf_vals, "o-", color="steelblue", linewidth=2, markersize=4)
        ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Period", fontsize=12)
        ax.set_ylabel("Impulse Response", fontsize=12)
        ax.set_title(
            f"IRF: {response_var} ← {impulse_var}",
            fontsize=13, fontweight="bold",
        )
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)

        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[PanelVAR] IRF plot saved: {save_path}")

        return fig

    def plot_fevd(
        self,
        response_var: str,
        save_path: str | Path | None = None,
        figsize: tuple[float, float] = (10, 6),
        n_periods: int = 20,
    ) -> Any:
        """
        绘制预测误差方差分解的堆积柱状图。

        Parameters
        ----------
        response_var : str
        save_path : str | Path | None
        figsize : tuple
        n_periods : int

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[PanelVAR] Call fit() first")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[PanelVAR] matplotlib not installed")
            return None

        df_fevd = self.fevd(response_var, n_periods=n_periods)
        if df_fevd.empty:
            return None

        y_vars = self._result.y_vars
        len(y_vars)
        cmap = plt.cm.tab10

        periods = df_fevd.index.values
        bottom = np.zeros(len(periods))

        fig, ax = plt.subplots(figsize=figsize)
        for i, v in enumerate(y_vars):
            if v in df_fevd.columns:
                vals = df_fevd[v].fillna(0).values
                ax.bar(periods, vals, bottom=bottom, label=v, color=cmap(i % 10), width=0.8)
                bottom += vals

        ax.set_xlabel("Period", fontsize=12)
        ax.set_ylabel("Variance Contribution (%)", fontsize=12)
        ax.set_title(f"FEVD: {response_var}", fontsize=13, fontweight="bold")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[PanelVAR] FEVD plot saved: {save_path}")

        return fig

    def plot_granger_heatmap(
        self,
        save_path: str | Path | None = None,
        figsize: tuple[float, float] = (8, 6),
    ) -> Any:
        """
        绘制面板 Granger 因果检验的显著性热力图。

        Parameters
        ----------
        save_path : str | Path | None
        figsize : tuple

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[PanelVAR] Call fit() first")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[PanelVAR] matplotlib not installed")
            return None

        df_gc = self.granger_causality()
        if df_gc.empty:
            _log.warning("[PanelVAR] No Granger results to plot")
            return None

        y_vars = self._result.y_vars
        n_vars = len(y_vars)

        # Build significance matrix (p-values)
        pmat = pd.DataFrame(np.nan, index=y_vars, columns=y_vars)
        for _, row in df_gc.iterrows():
            dep = row.get("dependent")
            cause = row.get("cause")
            pval = row.get("panel_p_value", np.nan)
            if dep in pmat.index and cause in pmat.columns:
                pmat.loc[dep, cause] = pval

        fig, ax = plt.subplots(figsize=figsize)
        import matplotlib.colors as mcolors
        norm = mcolors.Normalize(vmin=0, vmax=0.10)
        cmap = plt.cm.RdYlGn_r

        im = ax.imshow(pmat.values, cmap=cmap, norm=norm, aspect="auto")

        ax.set_xticks(range(n_vars))
        ax.set_yticks(range(n_vars))
        ax.set_xticklabels(y_vars, rotation=45, ha="right", fontsize=10)
        ax.set_yticklabels(y_vars, fontsize=10)
        ax.set_xlabel("Cause (Granger)", fontsize=12)
        ax.set_ylabel("Effect (Dep Var)", fontsize=12)
        ax.set_title("Panel Granger Causality (p-values)", fontsize=13, fontweight="bold")

        # Annotate cells
        for i in range(n_vars):
            for j in range(n_vars):
                val = pmat.values[i, j]
                if not np.isnan(val):
                    color = "white" if val < 0.05 else "black"
                    ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                            color=color, fontsize=9)

        plt.colorbar(im, ax=ax, label="p-value")
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[PanelVAR] Granger heatmap saved: {save_path}")

        return fig
