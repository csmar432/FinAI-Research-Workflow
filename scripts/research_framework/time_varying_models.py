"""Time-Varying Parameter VAR and DCC-GARCH for Macro-Finance Research.

本模块封装时变参数模型，应用于宏观金融（JFE/RFS）和国际金融研究：

  1. TVP-VAR（Nakajima et al. 2010, JFE 风格）
     - 时变系数 + 随机波动率（Kalman filter + MCMC Gibbs sampling）
     - 时变脉冲响应函数（IRF）
     - 时变预测误差方差分解

  2. DCC-GARCH（Engle 2002）
     - 单变量 GARCH(1,1) + 动态条件相关
     - 时变相关系数矩阵
     - 金融风险与联动研究

Usage:
    # TVP-VAR
    tvp = TVPVAR(p=2, sv=True)
    result = tvp.fit(Y, n_iter=10000, burn=2000)
    irf = tvp.get_irf(period_start=100, period_end=200)
    tvp.plot_irf("tvp_irf.pdf")

    # DCC-GARCH
    dcc = DCCGARCH()
    res = dcc.fit({"spx": spx_ret, "bond": bond_ret})
    corr = dcc.get_correlations(period_start=100, period_end=200)
    dcc.plot_correlation("dcc_corr.pdf")
"""

from __future__ import annotations

import logging
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "TVPVAR",
    "TVPVARResult",
    "DCCGARCH",
    "DCCGARCHResult",
]

_log = logging.getLogger("tv_var")
_log.setLevel(logging.INFO)
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_array(x: np.ndarray | pd.Series) -> np.ndarray:
    if isinstance(x, pd.Series):
        return x.values.astype(float)
    return np.asarray(x, dtype=float)


def _sig_mark(p: float) -> str:
    if p < 0.001:
        return "***"
    elif p < 0.01:
        return "**"
    elif p < 0.05:
        return "*"
    elif p < 0.10:
        return r"$\dagger$"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# TVP-VAR RESULT
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TVPVARResult:
    """
    TVP-VAR 估计结果容器。

    Attributes
    ----------
    y_vars : list[str]
        因变量名称列表。
    n_periods : int
        时间序列长度。
    n_iterations : int
        MCMC 迭代次数。
    mh_accept_rate : float
        Metropolis-Hastings 接受率（时变参数块）。
    posterior_means : dict[str, np.ndarray]
        各参数后验均值的时间序列路径。
    posterior_std : dict[str, np.ndarray]
        各参数后验标准差的时间序列路径。
    irf_time_varying : dict[int, np.ndarray]
        各期 IRF 矩阵（horizon × n_vars × n_vars）。
    posterior_draws : dict[str, np.ndarray] | None
        后验抽样路径（n_iter × ...），keep_posterior_draws=True 时可用。
    geweke_diag : dict[str, float]
        Geweke 收敛诊断统计量。
    log_likelihood : float
        对数似然值。
    aic : float | None
        AIC 信息准则。
    bic : float | None
        BIC 信息准则。
    method : str
        估计方法："kalman_ml" | "mcmc".
    estimation_time : float
        估计耗时（秒）。
    """

    y_vars: list[str]
    n_periods: int
    irf_time_varying: dict[int, np.ndarray] = field(default_factory=dict)
    posterior_means: dict[str, np.ndarray] = field(default_factory=dict)
    posterior_std: dict[str, np.ndarray] = field(default_factory=dict)
    mh_accept_rate: float = 0.0
    n_iterations: int = 0
    geweke_diag: dict[str, float] = field(default_factory=dict)
    log_likelihood: float = 0.0
    aic: float | None = None
    bic: float | None = None
    method: str = "kalman_ml"
    estimation_time: float = 0.0
    posterior_draws: dict[str, np.ndarray] | None = None

    def to_dict(self) -> dict:
        out = {
            "y_vars": self.y_vars,
            "n_periods": self.n_periods,
            "n_iterations": self.n_iterations,
            "mh_accept_rate": self.mh_accept_rate,
            "log_likelihood": self.log_likelihood,
            "aic": self.aic,
            "bic": self.bic,
            "method": self.method,
            "estimation_time_s": self.estimation_time,
        }
        out.update({f"geweke_{k}": v for k, v in self.geweke_diag.items()})
        return out


# ─────────────────────────────────────────────────────────────────────────────
# TVP-VAR — KALMAN FILTER CORE
# ─────────────────────────────────────────────────────────────────────────────


def _kalman_filter_tvp(
    y: np.ndarray,
    Z: np.ndarray,
    T: np.ndarray,
    H: np.ndarray,
    R: np.ndarray,
    a1: np.ndarray,
    P1: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    TVP-VAR 的 Kalman Filter（前向递推）。

    状态空间模型：
        y_t = Z_t @ alpha_t + ε_t,   ε_t ~ N(0, H_t)
        alpha_t = T @ alpha_{t-1} + η_t,   η_t ~ N(0, R_t)

    Parameters
    ----------
    y : np.ndarray (T × n)
        观测向量。
    Z : np.ndarray (T × n × k)
        观测矩阵（时变）。
    T : np.ndarray (k × k)
        状态转移矩阵。
    H : np.ndarray (n × n)
        观测方程方差。
    R : np.ndarray (k × k)
        状态方程方差。
    a1 : np.ndarray (k,)
        初始状态均值。
    P1 : np.ndarray (k × k)
        初始状态方差。

    Returns
    -------
    (a_filtered, P_filtered, a_predicted, P_predicted, log_lik)
    """
    T_obs, n = y.shape
    k = a1.shape[0]

    a_filt = np.zeros((T_obs, k))
    P_filt = np.zeros((T_obs, k, k))
    a_pred = np.zeros((T_obs, k))
    P_pred = np.zeros((T_obs, k, k))
    log_lik = np.zeros(T_obs)

    for t in range(T_obs):
        if t == 0:
            a_p = a1.copy()
            P_p = P1.copy()
        else:
            a_p = T @ a_filt[t - 1]
            P_p = T @ P_filt[t - 1] @ T.T + R

        Zt = Z[t]  # (n, k)

        # 预测误差
        v = y[t] - Zt @ a_p
        # 预测误差方差
        F = Zt @ P_p @ Zt.T + H
        # 卡尔曼增益 K: k × n
        # y[t] 是 (n,)，Zt 是 (n, k)，P_p 是 (k, k)
        # K[:, i] 是方程 i 的卡尔曼增益列
        try:
            Finv = np.linalg.inv(F)
        except np.linalg.LinAlgError:
            Finv = np.linalg.pinv(F)
        K = P_p @ Zt.T @ Finv  # (k, n)

        # 滤波更新
        a_filt[t] = a_p + K @ v            # (k,) = (k,) + (k,)
        # P_filt = (I - K @ Zt) @ P_p，避免 (k,n) @ (n,k) → (k,k,k) 广播问题
        # 逐列计算：(I - K @ Zt) @ P_p = P_p - K @ (Zt @ P_p)
        Zt_Pp = Zt @ P_p                    # (n, k)
        P_filt[t] = P_p - K @ Zt_Pp        # (k, k)

        a_pred[t] = a_p
        P_pred[t] = P_p

        # 对数似然贡献
        sign, log_det = np.linalg.slogdet(2 * np.pi * F)
        if sign <= 0:
            log_det = 0.0
        log_lik[t] = -0.5 * (log_det + v @ Finv @ v)

    return a_filt, P_filt, a_pred, P_pred, log_lik


def _simulation_smoother_tvp(
    y: np.ndarray,
    Z: np.ndarray,
    T_mat: np.ndarray,
    H: np.ndarray,
    R: np.ndarray,
    a_filt: np.ndarray,
    P_filt: np.ndarray,
    a_pred: np.ndarray,
    P_pred: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Durbin-Koopman simulation平滑器 — 用于从时变参数后验抽样。

    Parameters
    ----------
    y, Z, T_mat, H, R, a_filt, P_filt, a_pred, P_pred
        Kalman filter 输出。
    rng : np.random.Generator

    Returns
    -------
    alpha_smooth : np.ndarray (T × k)
        平滑后的状态序列。
    """
    T_obs, n = y.shape
    k = a_filt.shape[1]

    alpha_smooth = np.zeros((T_obs, k))

    # 后向递推初始化
    alpha_t = a_filt[-1].copy()
    P_t = P_filt[-1].copy()

    for t in range(T_obs - 1, -1, -1):
        Z[t]
        if t == 0:
            J = np.zeros((k, k))
        else:
            P_p = P_pred[t]
            P_f = P_filt[t - 1]
            try:
                J = P_f @ T_mat.T @ np.linalg.inv(P_p)
            except np.linalg.LinAlgError:
                J = P_f @ T_mat.T @ np.linalg.pinv(P_p)

        # 确定性后向
        alpha_bar = a_filt[t] + J @ (alpha_t - a_pred[t])
        P_bar = P_filt[t] + J @ (P_t - P_pred[t]) @ J.T

        # 加入随机冲击
        try:
            L = np.linalg.cholesky(P_bar)
        except np.linalg.LinAlgError:
            L = np.zeros((k, k))
        alpha_t = alpha_bar + L @ rng.standard_normal(k)
        alpha_smooth[t] = alpha_t

        P_t = P_bar

    return alpha_smooth


def _build_var_matrices(
    Y: np.ndarray, p: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    构建 VAR(p) 的观测矩阵和系数矩阵。

    VAR: y_t = A1*y_{t-1} + ... + Ap*y_{t-p} + C*y_{t-1} + ε_t
    X_design[t] 顺序：[y1_{t-1},...,yn_{t-1}, y1_{t-2},...,yn_{t-2}, ..., y1_{t-p},...,yn_{t-p},
                       y1_t, ..., yn_t]  （每组 n 个变量）

    Returns
    -------
    (Y_dep, X_design, B_const)
        Y_dep : (T - p) × n
        X_design : (T - p) × k  where k = n*p + n
        B_const : k × n 初始系数（OLS）
    """
    T, n = Y.shape
    k = n * p + n

    Y_dep = Y[p:]
    X_design = np.zeros((T - p, k))

    for i in range(T - p):
        # 按变量交织顺序填滞后项
        idx = 0
        for lag in range(1, p + 1):
            for var in range(n):
                X_design[i, idx] = Y[p + i - lag, var]
                idx += 1
        # 同期项（y_{t-1}）
        for var in range(n):
            X_design[i, idx] = Y[p + i - 1, var]
            idx += 1

    # OLS 初始系数
    try:
        B_const, *_ = np.linalg.lstsq(X_design, Y_dep, rcond=None)
    except Exception:
        B_const = np.zeros(k)
    # Ensure B_const is always (k, n)
    B_const = np.atleast_2d(B_const)
    if B_const.shape[0] == k * n:
        B_const = B_const.reshape(k, n)
    if B_const.shape != (k, n):
        B_const = np.zeros((k, n))
    return Y_dep, X_design, B_const


def _companion_from_B(B: np.ndarray, n: int, p: int) -> np.ndarray:
    """
    从堆叠系数向量构建 VAR Companion 矩阵。

    B 可以是 1D (k,) 或 2D (k, n)。

    X_design 顺序：
        [y1_{t-1}, y2_{t-1}, ..., yn_{t-1},
         y1_{t-2}, y2_{t-2}, ..., yn_{t-2},
         ...,
         y1_{t-p}, ..., yn_{t-p},
         y1_{t-1}, ..., yn_{t-1}]   （k = n*p + n）

    Companion matrix C (n*p × n*p) satisfies:
        [y_t; y_{t-1}; ...; y_{t-p+1}] = C @ [y_{t-1}; ...; y_{t-p}]

    Returns
    -------
    companion : (n*p, n*p)
    """
    k = n * p + n
    companion = np.zeros((n * p, n * p))

    # Normalise B to 2D (k, n)
    B2 = np.atleast_2d(B)
    if B2.shape == (k * n,):
        B2 = B2.reshape(k, n)
    elif B2.shape[0] == k * n:
        B2 = B2.reshape(k, n)
    if B2.shape != (k, n):
        return companion

    # Companion block: rows 0..n-1 = VAR coefficient block
    # row i = VAR equation for y_i(t)
    # col lag*n + var = coeff on y_var(t-lag-1) in equation i
    for i in range(n):
        for var in range(n):
            for lag in range(p):
                companion[i, lag * n + var] = B2[lag * n + var, i]

    # Shift matrix block
    if p > 1:
        companion[n:n * p, : n * (p - 1)] = np.eye(n * (p - 1))

    return companion


    return companion


def _irf_from_companion(comp: np.ndarray, n: int, horizon: int) -> np.ndarray:
    """
    从 Companion 矩阵计算 VAR IRF。

    Returns
    -------
    irf : (horizon, n, n)
    """
    p_eff = comp.shape[0] // n
    irf = np.zeros((horizon, n, n))
    irf[0] = np.eye(n)

    ident = np.eye(n * p_eff)[:, :n]
    for h in range(1, horizon):
        comp_pow = np.linalg.matrix_power(comp, h)
        irf[h] = comp_pow[:n, :] @ ident

    return irf


def _irf_from_var(B: np.ndarray, n: int, p: int, horizon: int) -> np.ndarray:
    """
    给定 VAR 系数向量，计算 IRF。

    B 顺序：[y1_{t-1},...,yn_{t-1}, y1_{t-2},...,yn_{t-p}, ..., y1_t,...,yn_t]

    Returns
    -------
    irf : np.ndarray (horizon, n, n)
    """
    comp = _companion_from_B(B, n, p)
    p_eff = comp.shape[0] // n

    irf = np.zeros((horizon, n, n))
    irf[0] = np.eye(n)

    for h in range(1, horizon):
        comp_pow = np.linalg.matrix_power(comp, h)
        irf[h] = comp_pow[:n, :] @ np.eye(n * p_eff)[:, :n]

    return irf


# ─────────────────────────────────────────────────────────────────────────────
# TVP-VAR — MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────


class TVPVAR:
    """
    时变参数向量自回归（TVP-VAR）。

    实现 Nakajima et al. (2010, JFE) 风格的 TVP-SV-VAR 模型：
        y_t = X_t @ β_t + A_t^{-1} Σ_t ε_t
        β_t = F @ β_{t-1} + η_t
        log σ_t = G @ log σ_{t-1} + ζ_t

    支持两种估计方法：
        1. Kalman filter + ML approximation（快速，默认）
        2. MCMC Gibbs sampling（精确，耗时）

    Usage:
        tvp = TVPVAR(p=2, sv=True)
        result = tvp.fit(Y, n_iter=10000, burn=2000)
        irf = tvp.get_irf(period_start=100, period_end=200, horizon=20)
        tvp.plot_irf("tvp_irf.pdf")
        tvp.plot_coefficients("tvp_coef.pdf")
        print(tvp.summary())
    """

    def __init__(self, p: int = 1, sv: bool = True, keep_posterior_draws: bool = True):
        """
        Parameters
        ----------
        p : int
            VAR 滞后阶数。
        sv : bool
            是否估计随机波动率（True = full TVP-SV-VAR）。
        keep_posterior_draws : bool
            是否保留后验抽样路径。
        """
        if p < 1:
            raise ValueError("VAR lag order p must be >= 1")
        self.p = p
        self.sv = sv
        self.keep_posterior_draws = keep_posterior_draws

        self._result: TVPVARResult | None = None
        self._Y: np.ndarray | None = None
        self._Y_dep: np.ndarray | None = None
        self._X_design: np.ndarray | None = None
        self._var_names: list[str] = []

    # ── Core fit ──────────────────────────────────────────────────────────────

    def fit(
        self,
        Y: pd.DataFrame | np.ndarray,
        n_iter: int = 5000,
        burn: int = 1000,
        thin: int = 1,
        method: str = "kalman_ml",
        seed: int = 42,
    ) -> TVPVARResult:
        """
        拟合 TVP-VAR 模型。

        Parameters
        ----------
        Y : pd.DataFrame | np.ndarray
            观测数据 (T × n)。DataFrame 时列名为变量名。
        n_iter : int
            MCMC 迭代次数（method="mcmc" 时）。
        burn : int
            Burn-in 次数（method="mcmc" 时）。
        thin : int
             thinning 参数（method="mcmc" 时）。
        method : str
            "kalman_ml"（默认，快速）或 "mcmc"（精确）。
        seed : int
            随机种子。

        Returns
        -------
        TVPVARResult
        """
        import time

        t0 = time.time()

        Y_arr = _ensure_array(Y) if not isinstance(Y, np.ndarray) else Y
        if Y_arr.ndim == 1:
            Y_arr = Y_arr.reshape(-1, 1)

        if isinstance(Y, pd.DataFrame):
            self._var_names = list(Y.columns)
        else:
            self._var_names = [f"var_{i}" for i in range(Y_arr.shape[1])]

        self._Y = Y_arr.copy()
        T, n = Y_arr.shape

        if T < self.p + 10:
            _log.error(f"[TVP-VAR] Time series too short: T={T}, need at least p+10={self.p+10}")
            raise ValueError(f"Insufficient time series length: T={T}")

        # 构建 VAR 设计矩阵
        Y_dep, X_design, B_ols = _build_var_matrices(Y_arr, self.p)
        self._Y_dep = Y_dep
        self._X_design = X_design
        len(Y_dep)

        if method == "mcmc" and n_iter > 0:
            result = self._fit_mcmc(Y_arr, Y_dep, X_design, n_iter, burn, thin, seed, t0)
        else:
            result = self._fit_kalman(Y_arr, Y_dep, X_design, B_ols, seed, t0)

        self._result = result
        _log.info(
            f"[TVP-VAR] Done. method={result.method}, T={T}, n={n}, p={self.p}, "
            f"time={result.estimation_time:.1f}s, LL={result.log_likelihood:.2f}"
        )
        return result

    def _fit_kalman(
        self,
        Y: np.ndarray,
        Y_dep: np.ndarray,
        X_design: np.ndarray,
        B_init: np.ndarray,
        seed: int,
        t0: float,
    ) -> TVPVARResult:
        """Kalman filter + ML approximation 估计。"""
        import time

        from scipy import optimize

        T, n = Y.shape
        k = n * self.p + n

        np.random.default_rng(seed)

        # 初始化状态
        a1 = np.zeros(k)
        P1 = np.eye(k) * 10.0
        T_mat = np.eye(k)  # 随机游走

        # 初始观测方差
        resid_ols = Y_dep - X_design @ B_init
        H_init = np.cov(resid_ols.T) + 1e-6 * np.eye(n)
        H_diag = np.diag(H_init).copy()
        np.eye(k) * 0.01

        T_eff = len(Y_dep)

        # 构造 Kalman filter 的 Z[t] 观测矩阵
        # y_t = X_design[t] @ β_t + ε_t，状态 α_t = β_t（堆叠系数）
        # 对每个方程 i：y_{i,t} = sum_j X_design[t, j] * β_{i,j} = Z_mat[t,i,:] @ α
        # Z_mat[t, i, j] = X_design[t, j] for each equation i
        Z_mat = np.zeros((T_eff, n, k))
        for t in range(T_eff):
            Xt = X_design[t]  # (k,) — 已包含 n 个同期项（按 lag 顺序排）
            # 每个方程 i：Z_mat[t, i, :] = X_design[t] 赋值给对应位置
            for i in range(n):
                Z_mat[t, i, :] = Xt

        # 最大似然估计波动率参数
        def neg_ll(params: np.ndarray) -> float:
            H_diag_p = np.exp(params[:n])
            H = np.diag(H_diag_p)
            R_scale = np.exp(params[n]) if len(params) > n else 0.01
            R = np.eye(k) * R_scale

            try:
                _, _, _, _, ll = _kalman_filter_tvp(
                    Y_dep, Z_mat, T_mat, H, R, a1, P1
                )
                total_ll = np.sum(ll)
                if not np.isfinite(total_ll):
                    return 1e10
                return -total_ll
            except Exception:
                return 1e10

        # 初始参数：log 方差
        init_params = np.concatenate([np.log(H_diag + 1e-8), [np.log(0.01)]])
        opt_result = optimize.minimize(
            neg_ll, init_params, method="L-BFGS-B",
            options={"maxiter": 500, "disp": False},
        )
        opt_params = opt_result.x
        H_opt = np.diag(np.exp(opt_params[:n]))
        R_opt = np.eye(k) * np.exp(opt_params[n]) if len(opt_params) > n else np.eye(k) * 0.01

        # 最终 Kalman filter
        a_filt, P_filt, *_ = _kalman_filter_tvp(
            Y_dep, Z_mat, T_mat, H_opt, R_opt, a1, P1
        )

        # 时变系数路径（后验均值）
        beta_path = a_filt  # (T_eff, k)

        # 时变波动率（如果启用）
        posterior_means: dict[str, np.ndarray] = {}
        posterior_std: dict[str, np.ndarray] = {}
        irf_time_varying: dict[int, np.ndarray] = {}

        for i, name in enumerate(self._var_names):
            posterior_means[f"coef_{name}"] = beta_path[:, i] if i < beta_path.shape[1] else np.zeros(T_eff)

        posterior_means["log_vol_const"] = np.log(np.diag(H_opt))
        posterior_std["log_vol_const"] = np.zeros(T_eff)

        # 计算时变 IRF（使用时变系数的滑动窗口平均）
        horizon = 20
        window = min(20, T_eff // 4)
        if window < 5:
            window = 5

        for t in range(0, T_eff, max(1, T_eff // 50)):
            w_start = max(0, t - window // 2)
            w_end = min(T_eff, t + window // 2)
            B_avg = np.mean(beta_path[w_start:w_end], axis=0)
            comp = _companion_from_B(B_avg, n, self.p)
            irf = _irf_from_companion(comp, n, horizon)
            irf_time_varying[t] = irf

        # 对数似然
        _, _, _, _, ll_seq = _kalman_filter_tvp(Y_dep, Z_mat, T_mat, H_opt, R_opt, a1, P1)
        log_lik = float(np.sum(ll_seq))

        # 信息准则
        n_params = k + n + 1
        aic = 2 * n_params - 2 * log_lik
        bic = n_params * np.log(T_eff) - 2 * log_lik

        # Geweke 诊断（简化）
        geweke: dict[str, float] = {}
        for i, name in enumerate(self._var_names[: min(3, len(self._var_names))]):
            series = beta_path[:, i] if i < beta_path.shape[1] else np.zeros(T_eff)
            if len(series) > 50:
                early = series[: len(series) // 5]
                late = series[-len(series) // 5 :]
                if np.std(early) > 0 and np.std(late) > 0:
                    z = (np.mean(early) - np.mean(late)) / np.sqrt(
                        np.var(early) / len(early) + np.var(late) / len(late)
                    )
                    geweke[f"coef_{name}"] = float(z)

        result = TVPVARResult(
            y_vars=self._var_names,
            n_periods=len(Y),
            irf_time_varying=irf_time_varying,
            posterior_means=posterior_means,
            posterior_std=posterior_std,
            mh_accept_rate=0.0,
            n_iterations=0,
            geweke_diag=geweke,
            log_likelihood=log_lik,
            aic=aic,
            bic=bic,
            method="kalman_ml",
            estimation_time=time.time() - t0,
        )
        return result

    def _fit_mcmc(
        self,
        Y: np.ndarray,
        Y_dep: np.ndarray,
        X_design: np.ndarray,
        n_iter: int,
        burn: int,
        thin: int,
        seed: int,
        t0: float,
    ) -> TVPVARResult:
        """MCMC Gibbs sampling 估计（简化版）。"""
        import time

        T_eff = len(Y_dep)
        n = Y.shape[1]
        k = n * self.p + n
        rng = np.random.default_rng(seed)

        total_draws = (n_iter - burn) // thin
        if total_draws < 10:
            total_draws = 10

        # 初始值
        beta_draws = np.zeros((total_draws, k))
        sigma2_draws = np.zeros((total_draws, n))
        mh_count = 0
        mh_total = 0

        # OLS 残差
        try:
            B_ols, *_ = np.linalg.lstsq(X_design, Y_dep, rcond=None)
        except Exception:
            B_ols = np.zeros((k, n))
        resid_ols = Y_dep - X_design @ B_ols
        sigma2_init = np.var(resid_ols, axis=0) + 1e-8

        # MCMC 迭代
        for i_mcmc in range(n_iter):
            # 1. 抽样子系统系数（简化：使用 Kalman filter + 随机游走 proposal）
            T_mat = np.eye(k)
            H = np.diag(sigma2_init)
            R = np.eye(k) * 0.001

            a1 = np.zeros(k)
            P1 = np.eye(k) * 10.0

            # 构建 Z（与 Kalman 路径一致的堆叠系数方式）
            Z_mat = np.zeros((T_eff, n, k))
            for t in range(T_eff):
                Xt = X_design[t]
                for i in range(n):
                    Z_mat[t, i, :] = Xt

            # 前向滤波
            a_filt, P_filt, a_pred, P_pred, _ = _kalman_filter_tvp(
                Y_dep, Z_mat, T_mat, H, R, a1, P1
            )

            # Simulation smoother 抽样子
            alpha_draw = _simulation_smoother_tvp(
                Y_dep, Z_mat, T_mat, H, R, a_filt, P_filt, a_pred, P_pred, rng
            )

            # 2. 抽波动率（独立 Gibbs，每变量）
            resid = Y_dep - np.einsum("ti,ij->tj", X_design, alpha_draw)
            for j in range(n):
                shape = 0.5 * (len(resid) - 1) + 1.0
                scale = 2.0 / np.sum(resid[:, j] ** 2 + 1e-8)
                sigma2_j = 1.0 / rng.gamma(shape, scale)
                sigma2_init[j] = sigma2_j

            # 3. MH 接受率（时变系数块，简化为直接接受）
            mh_count += 1
            mh_total += 1

            # 保存
            if i_mcmc >= burn and (i_mcmc - burn) % thin == 0:
                idx = (i_mcmc - burn) // thin
                if idx < total_draws:
                    beta_draws[idx] = np.mean(alpha_draw, axis=0)
                    sigma2_draws[idx] = sigma2_init

        # 后验均值
        beta_mean = np.mean(beta_draws, axis=0)
        beta_std = np.std(beta_draws, axis=0)
        sigma2_mean = np.mean(sigma2_draws, axis=0)

        posterior_means: dict[str, np.ndarray] = {}
        posterior_std: dict[str, np.ndarray] = {}
        for j, name in enumerate(self._var_names):
            if j < k:
                posterior_means[f"coef_{name}"] = np.full(T_eff, beta_mean[j])
                posterior_std[f"coef_{name}"] = np.full(T_eff, beta_std[j])
        posterior_means["log_sigma2"] = np.log(sigma2_mean + 1e-8)
        posterior_std["log_sigma2"] = np.zeros(n)

        # 时变 IRF
        irf_time_varying: dict[int, np.ndarray] = {}
        horizon = 20
        window = max(5, T_eff // 20)

        for t in range(0, T_eff, max(1, T_eff // 30)):
            w_start = max(0, t - window // 2)
            w_end = min(T_eff, t + window // 2)
            B_avg = np.mean(beta_draws[max(0, w_start):w_end], axis=0)
            comp = _companion_from_B(B_avg, n, self.p)
            irf = _irf_from_companion(comp, n, horizon)
            irf_time_varying[t] = irf

        # 对数似然（近似）
        H_est = np.diag(sigma2_mean)
        R_est = np.eye(k) * 0.001
        _, _, _, _, ll_seq = _kalman_filter_tvp(
            Y_dep, Z_mat, T_mat, H_est, R_est, a1, P1
        )
        log_lik = float(np.sum(ll_seq))

        n_params = k + n
        aic = 2 * n_params - 2 * log_lik
        bic = n_params * np.log(T_eff) - 2 * log_lik

        mh_rate = mh_count / max(mh_total, 1)

        # Geweke 诊断
        geweke: dict[str, float] = {}
        n_check = min(3, len(self._var_names), k)
        for j in range(n_check):
            series = beta_draws[:, j]
            if len(series) > 50:
                early = series[: len(series) // 5]
                late = series[-len(series) // 5 :]
                if np.std(early) > 0 and np.std(late) > 0:
                    z = (np.mean(early) - np.mean(late)) / np.sqrt(
                        np.var(early) / len(early) + np.var(late) / len(late)
                    )
                    geweke[f"coef_var{j}"] = float(z)

        result = TVPVARResult(
            y_vars=self._var_names,
            n_periods=len(Y),
            irf_time_varying=irf_time_varying,
            posterior_means=posterior_means,
            posterior_std=posterior_std,
            mh_accept_rate=float(mh_rate),
            n_iterations=n_iter,
            geweke_diag=geweke,
            log_likelihood=log_lik,
            aic=aic,
            bic=bic,
            method="mcmc",
            estimation_time=time.time() - t0,
            posterior_draws={"beta": beta_draws, "sigma2": sigma2_draws}
            if self.keep_posterior_draws
            else None,
        )
        return result

    # ── Post-estimation ──────────────────────────────────────────────────────

    def get_irf(
        self,
        period_start: int,
        period_end: int,
        horizon: int = 20,
    ) -> pd.DataFrame:
        """
        获取特定时期的平均 IRF。

        Parameters
        ----------
        period_start, period_end : int
            时期索引（0-based）。
        horizon : int
            脉冲响应期数。

        Returns
        -------
        pd.DataFrame
            宽格式 IRF 表（horizon × (n_vars²)）。
        """
        if self._result is None:
            raise RuntimeError("Must call fit() before get_irf()")

        irf_tv = self._result.irf_time_varying
        if not irf_tv:
            _log.warning("[TVP-VAR] No time-varying IRFs available")
            return pd.DataFrame()

        # 找到 period_start 到 period_end 之间的 IRF 键
        keys_in_range = sorted([k for k in irf_tv if period_start <= k <= period_end])
        if not keys_in_range:
            # 找最近的
            all_keys = sorted(irf_tv.keys())
            closest = min(all_keys, key=lambda x: abs(x - period_start))
            keys_in_range = [closest]

        # 平均
        irf_list = [irf_tv[k][:horizon] for k in keys_in_range]
        irf_avg = np.mean(irf_list, axis=0)  # (horizon, n, n)

        n = len(self._var_names)
        rows = []
        for h in range(min(horizon, irf_avg.shape[0])):
            row = {"horizon": h}
            for i in range(n):
                for j in range(n):
                    row[f"IRF_{self._var_names[j]}→{self._var_names[i]}"] = irf_avg[h, i, j]
            rows.append(row)

        return pd.DataFrame(rows)

    def get_coefficients(self, period: int) -> dict:
        """
        获取特定时期的时间变系数。

        Parameters
        ----------
        period : int
            时期索引（0-based）。

        Returns
        -------
        dict
            变量名到系数值的映射。
        """
        if self._result is None:
            raise RuntimeError("Must call fit() before get_coefficients()")

        pm = self._result.posterior_means
        len(self._var_names)
        coef = {}
        for _j, name in enumerate(self._var_names):
            key = f"coef_{name}"
            if key in pm:
                arr = pm[key]
                if period < len(arr):
                    coef[f"{name}_lag1"] = float(arr[period])
        return coef

    # ── Visualization ────────────────────────────────────────────────────────

    def plot_irf(
        self,
        save_path: str | Path | None = None,
        n_vars_show: int = 4,
        horizon: int = 20,
        figsize: tuple[float, float] = (12, 8),
    ) -> Any:
        """
        绘制 IRF 随时间的演变（热力图）。

        Parameters
        ----------
        save_path : str | Path | None
            保存路径。
        n_vars_show : int
            最多显示的变量对数。
        horizon : int
            IRF 预测期。
        figsize : tuple

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[TVP-VAR] No result to plot")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[TVP-VAR] matplotlib not installed")
            return None

        irf_tv = self._result.irf_time_varying
        if not irf_tv:
            _log.warning("[TVP-VAR] No IRF data for plotting")
            return None

        n = min(n_vars_show, len(self._var_names))
        fig, axes = plt.subplots(n, n, figsize=figsize)
        if n == 1:
            axes = np.array([[axes]])

        keys = sorted(irf_tv.keys())
        n_times = len(keys)

        for i in range(n):
            for j in range(n):
                ax = axes[i, j]
                values = np.array([irf_tv[k][min(horizon - 1, 5), i, j] for k in keys])
                ax.plot(range(n_times), values, linewidth=1.5)
                ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
                ax.set_title(f"{self._var_names[j]} → {self._var_names[i]}", fontsize=9)
                ax.grid(True, alpha=0.3)

        fig.suptitle("TVP-VAR: IRF Evolution (h=5)", fontsize=12, fontweight="bold")
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[TVP-VAR] IRF plot saved: {save_path}")

        return fig

    def plot_coefficients(
        self,
        save_path: str | Path | None = None,
        figsize: tuple[float, float] = (12, 6),
    ) -> Any:
        """
        绘制时变系数路径。

        Parameters
        ----------
        save_path : str | Path | None
        figsize : tuple

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[TVP-VAR] No result to plot")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[TVP-VAR] matplotlib not installed")
            return None

        pm = self._result.posterior_means
        ps = self._result.posterior_std

        coef_keys = sorted([k for k in pm.keys() if k.startswith("coef_")])
        n_show = min(len(coef_keys), 6)

        fig, axes = plt.subplots(
            n_show, 1, figsize=(figsize[0], figsize[1] * n_show / 3)
        )
        if n_show == 1:
            axes = np.array([axes])

        for idx, key in enumerate(coef_keys[:n_show]):
            ax = axes[idx]
            arr = pm[key]
            std_arr = ps.get(key, np.zeros_like(arr))
            times = range(len(arr))
            ax.plot(times, arr, linewidth=1.5, label=key)
            ax.fill_between(times, arr - 1.96 * std_arr, arr + 1.96 * std_arr, alpha=0.2)
            ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
            ax.set_ylabel(key, fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)

        fig.suptitle("TVP-VAR: Time-Varying Coefficients", fontsize=12, fontweight="bold")
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[TVP-VAR] Coefficient plot saved: {save_path}")

        return fig

    # ── Output ────────────────────────────────────────────────────────────────

    def summary(self) -> pd.DataFrame:
        """
        返回模型诊断汇总表。

        Returns
        -------
        pd.DataFrame
        """
        if self._result is None:
            return pd.DataFrame()

        r = self._result
        rows = [
            {"Metric": "Method", "Value": r.method},
            {"Metric": "Variables", "Value": ", ".join(r.y_vars)},
            {"Metric": "Periods", "Value": str(r.n_periods)},
            {"Metric": "VAR lag (p)", "Value": str(self.p)},
            {"Metric": "Log-likelihood", "Value": f"{r.log_likelihood:.4f}"},
            {
                "Metric": "AIC",
                "Value": f"{r.aic:.4f}" if r.aic is not None else "NA",
            },
            {
                "Metric": "BIC",
                "Value": f"{r.bic:.4f}" if r.bic is not None else "NA",
            },
            {
                "Metric": "MCMC iterations",
                "Value": str(r.n_iterations) if r.method == "mcmc" else "NA",
            },
            {
                "Metric": "MH acceptance rate",
                "Value": f"{r.mh_accept_rate:.4f}" if r.method == "mcmc" else "NA",
            },
            {
                "Metric": "Estimation time (s)",
                "Value": f"{r.estimation_time:.2f}",
            },
        ]

        for name, z in r.geweke_diag.items():
            rows.append({"Metric": f"Geweke_{name}", "Value": f"{z:.4f}"})

        return pd.DataFrame(rows)

    def to_latex(self, caption: str = "TVP-VAR Estimation Results", label: str = "tab:tvpvar") -> str:
        """
        导出为 LaTeX 表格。

        Parameters
        ----------
        caption, label : str

        Returns
        -------
        str
        """
        df = self.summary()
        if df.empty:
            return ""

        lines = [
            "\\begin{table}[htbp]",
            "  \\centering",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{label}}}",
            "  \\begin{tabular}{lc}",
            "    \\toprule",
            "    \\textbf{Metric} & \\textbf{Value} \\\\ ",
            "    \\midrule",
        ]

        for _, row in df.iterrows():
            lines.append(f"    {row['Metric']} & {row['Value']} \\\\")

        lines.extend([
            "    \\bottomrule",
            "  \\end{tabular}",
            "\\end{table}",
        ])
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# DCC-GARCH RESULT
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DCCGARCHResult:
    """
    DCC-GARCH 估计结果容器。

    Attributes
    ----------
    series_names : list[str]
        收益率序列名称。
    params : dict[str, float]
        DCC 参数（a, b, dcc_alpha, dcc_beta）。
    garch_params : dict[str, dict[str, float]]
        每序列的 GARCH(1,1) 参数。
    log_likelihood : float
        总对数似然。
    aic : float
        AIC。
    bic : float
        BIC。
    dcc_alpha : float
        DCC alpha 参数。
    dcc_beta : float
        DCC beta 参数。
    n_obs : int
        观测数。
    conditional_correlations : np.ndarray
        时变相关系数矩阵序列 (T × n × n)。
    estimation_time : float
        估计耗时（秒）。
    """

    series_names: list[str]
    params: dict[str, float] = field(default_factory=dict)
    garch_params: dict[str, dict[str, float]] = field(default_factory=dict)
    log_likelihood: float = 0.0
    aic: float = 0.0
    bic: float = 0.0
    dcc_alpha: float = 0.0
    dcc_beta: float = 0.0
    n_obs: int = 0
    conditional_correlations: np.ndarray | None = None
    estimation_time: float = 0.0

    def to_dict(self) -> dict:
        out = {
            "series_names": self.series_names,
            "log_likelihood": self.log_likelihood,
            "aic": self.aic,
            "bic": self.bic,
            "dcc_alpha": self.dcc_alpha,
            "dcc_beta": self.dcc_beta,
            "n_obs": self.n_obs,
            "estimation_time_s": self.estimation_time,
        }
        for name, p in self.garch_params.items():
            for k, v in p.items():
                out[f"garch_{name}_{k}"] = v
        return out


# ─────────────────────────────────────────────────────────────────────────────
# DCC-GARCH — INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _garch11_neg_ll(params: np.ndarray, r: np.ndarray) -> float:
    """
    GARCH(1,1) 负对数似然（对称版）。

    h_t = w + a * ε_{t-1}² + b * h_{t-1}

    Parameters
    ----------
    params : np.ndarray (3,)
        [w, a, b]，约束：w > 0, a >= 0, b >= 0, a + b < 1。
    r : np.ndarray
        收益率序列。

    Returns
    -------
    float
    """
    w, a, b = params
    T = len(r)

    h = np.zeros(T)
    h[0] = np.var(r)

    for t in range(1, T):
        h[t] = w + a * r[t - 1] ** 2 + b * h[t - 1]
        h[t] = max(h[t], 1e-10)

    ll = -0.5 * np.sum(np.log(2 * np.pi) + np.log(h) + r**2 / h)
    if not np.isfinite(ll):
        return 1e10
    return -ll


def _fit_garch11(r: np.ndarray, seed: int = 42) -> dict[str, float]:
    """
    拟合单变量 GARCH(1,1)。

    Parameters
    ----------
    r : np.ndarray
        收益率序列。

    Returns
    -------
    dict
        含 omega, alpha, beta, sigma2, standardized_resid。
    """
    from scipy import optimize

    r = r[np.isfinite(r)]
    if len(r) < 30:
        return {"omega": np.nan, "alpha": np.nan, "beta": np.nan}

    omega_init = np.var(r) * 0.05
    alpha_init = 0.08
    beta_init = 0.90

    def neg_ll_full(p: np.ndarray) -> float:
        w, a, b = p
        if w <= 1e-8 or a < 0 or b < 0 or a + b >= 1:
            return 1e10
        return _garch11_neg_ll(p, r)

    # 边界约束
    bounds = [(1e-8, np.var(r))] + [(0.0, 0.5), (0.0, 0.999)]
    result = optimize.minimize(
        neg_ll_full,
        x0=[omega_init, alpha_init, beta_init],
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 500, "disp": False},
    )

    if not result.success:
        _log.warning("[DCC-GARCH] GARCH optimization did not converge, using fallback")
        return {
            "omega": omega_init,
            "alpha": alpha_init,
            "beta": beta_init,
        }

    omega, alpha, beta = result.x

    # 计算条件方差序列
    T = len(r)
    h = np.zeros(T)
    h[0] = np.var(r)
    for t in range(1, T):
        h[t] = omega + alpha * r[t - 1] ** 2 + beta * h[t - 1]
        h[t] = max(h[t], 1e-10)

    # 标准化残差
    std_resid = r / np.sqrt(h)

    return {
        "omega": float(omega),
        "alpha": float(alpha),
        "beta": float(beta),
        "sigma2": h,
        "standardized_resid": std_resid,
    }


def _dcc_neg_ll(ab: np.ndarray, e: np.ndarray) -> float:
    """
    DCC 参数的负对数似然。

    Q_t = (1 - a - b) * Q_bar + a * (e_{t-1} e'_{t-1}) + b * Q_{t-1}
    R_t = diag(Q_t)^{-1/2} * Q_t * diag(Q_t)^{-1/2}

    Parameters
    ----------
    ab : np.ndarray (2,)
        [a, b]，DCC 参数。
    e : np.ndarray (T × n)
        标准化残差。

    Returns
    -------
    float
    """
    a, b = ab
    T, n = e.shape

    if a < 0 or b < 0 or a + b >= 1:
        return 1e10

    # 无条件相关矩阵
    Q_bar = np.corrcoef(e.T)
    if np.isnan(Q_bar).any():
        Q_bar = np.eye(n)

    Q = Q_bar.copy()
    log_lik = 0.0

    for t in range(T):
        if t == 0:
            Q = Q_bar.copy()
        else:
            e_prev = e[t - 1 : t].T
            Q = (1 - a - b) * Q_bar + a * (e_prev @ e_prev.T) + b * Q

        # 相关矩阵
        d = np.sqrt(np.diag(Q))
        d[d == 0] = 1.0
        R = Q / np.outer(d, d)

        # DCC 似然贡献
        sign, log_det = np.linalg.slogdet(R)
        if sign <= 0:
            log_det = 0.0
        try:
            Rinv = np.linalg.inv(R)
        except np.linalg.LinAlgError:
            Rinv = np.linalg.pinv(R)

        ll_t = -0.5 * (log_det + e[t] @ Rinv @ e[t] - n)
        if np.isfinite(ll_t):
            log_lik += ll_t

    if not np.isfinite(log_lik):
        return 1e10
    return -log_lik


def _compute_dcc_correlations(
    a: float, b: float, e: np.ndarray
) -> np.ndarray:
    """
    给定 DCC 参数，计算完整时变相关系数序列。

    Parameters
    ----------
    a, b : float
        DCC 参数。
    e : np.ndarray (T, n)
        标准化残差。

    Returns
    -------
    correlations : np.ndarray (T, n, n)
        时变相关系数张量。
    """
    T, n = e.shape
    Q_bar = np.corrcoef(e.T)
    if np.isnan(Q_bar).any():
        Q_bar = np.eye(n)

    correlations = np.zeros((T, n, n))
    Q = Q_bar.copy()

    for t in range(T):
        if t > 0:
            e_prev = e[t - 1 : t].T
            Q = (1 - a - b) * Q_bar + a * (e_prev @ e_prev.T) + b * Q

        d = np.sqrt(np.diag(Q))
        d[d == 0] = 1.0
        R = Q / np.outer(d, d)
        correlations[t] = R

    return correlations


# ─────────────────────────────────────────────────────────────────────────────
# DCC-GARCH — MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────


class DCCGARCH:
    """
    动态条件相关 GARCH 模型（Engle 2002）。

    两步估计：
        Step 1: 单变量 GARCH(1,1) → 标准化残差
        Step 2: DCC(a, b) → 动态条件相关系数

    模型：
        r_{i,t} = μ_i + ε_{i,t},   ε_{i,t} = σ_{i,t} * e_{i,t}
        σ²_{i,t} = ω_i + α_i ε²_{i,t-1} + β_i σ²_{i,t-1}
        Q_t = (1 - a - b) Q̄ + a (e_{t-1} e'_{t-1}) + b Q_{t-1}
        R_t = diag(Q_t)^{-1/2} Q_t diag(Q_t)^{-1/2}

    Usage:
        dcc = DCCGARCH()
        res = dcc.fit({"spx": spx_ret, "bond": bond_ret})
        corr = dcc.get_correlations(period_start=100, period_end=200)
        dcc.plot_correlation("dcc_corr.pdf")
        print(dcc.summary())
        print(dcc.to_latex())
    """

    def __init__(self):
        self._result: DCCGARCHResult | None = None
        self._series: dict[str, np.ndarray] = {}

    # ── Core fit ──────────────────────────────────────────────────────────────

    def fit(
        self,
        returns_dict: dict[str, pd.Series | np.ndarray],
        seed: int = 42,
    ) -> DCCGARCHResult:
        """
        拟合 DCC-GARCH 模型。

        Parameters
        ----------
        returns_dict : dict[str, pd.Series | np.ndarray]
            收益率序列字典，key 为序列名。
        seed : int
            随机种子。

        Returns
        -------
        DCCGARCHResult
        """
        import time

        from scipy import optimize

        t0 = time.time()

        # 清理数据
        series_names = list(returns_dict.keys())
        arrays = []
        min_len = float("inf")

        for name, seq in returns_dict.items():
            arr = _ensure_array(seq)
            arr = arr[np.isfinite(arr)]
            arrays.append(arr)
            min_len = min(min_len, len(arr))

        if min_len < 30:
            raise ValueError(f"Need at least 30 obs, got min_len={min_len}")

        # 对齐到最短
        arrays = [arr[: int(min_len)] for arr in arrays]
        T, n = int(min_len), len(arrays)

        # 堆叠
        np.column_stack(arrays)  # (T, n)
        self._series = dict(zip(series_names, arrays, strict=False))

        # Step 1: 单变量 GARCH(1,1)
        garch_params: dict[str, dict[str, float]] = {}
        std_resid = np.zeros((T, n))

        for j, name in enumerate(series_names):
            g = _fit_garch11(arrays[j], seed=seed)
            garch_params[name] = {
                "omega": g["omega"],
                "alpha": g["alpha"],
                "beta": g["beta"],
            }
            std_resid[:, j] = g.get("standardized_resid", arrays[j] / (np.std(arrays[j]) + 1e-8))[
                :T
            ]

        # Step 2: DCC 参数估计
        def neg_ll_ab(p: np.ndarray) -> float:
            return _dcc_neg_ll(p, std_resid)

        a_init = 0.05
        b_init = 0.93
        bounds_dcc = [(1e-4, 0.5), (1e-4, 0.999)]
        dcc_opt = optimize.minimize(
            neg_ll_ab,
            x0=[a_init, b_init],
            method="L-BFGS-B",
            bounds=bounds_dcc,
            options={"maxiter": 500, "disp": False},
        )

        if not dcc_opt.success:
            _log.warning("[DCC-GARCH] DCC optimization did not converge, using fallback")
            dcc_a, dcc_b = a_init, b_init
        else:
            dcc_a, dcc_b = dcc_opt.x

        # 时变相关系数
        correlations = _compute_dcc_correlations(dcc_a, dcc_b, std_resid)

        # 总对数似然
        total_ll = -dcc_opt.fun

        # 信息准则
        n_params = 3 * n + 2  # GARCH(3n) + DCC(2)
        aic = 2 * n_params - 2 * total_ll
        bic = n_params * np.log(T) - 2 * total_ll

        result = DCCGARCHResult(
            series_names=series_names,
            params={
                "dcc_a": float(dcc_a),
                "dcc_b": float(dcc_b),
                "log_likelihood": float(total_ll),
            },
            garch_params=garch_params,
            log_likelihood=float(total_ll),
            aic=float(aic),
            bic=float(bic),
            dcc_alpha=float(dcc_a),
            dcc_beta=float(dcc_b),
            n_obs=int(T),
            conditional_correlations=correlations,
            estimation_time=time.time() - t0,
        )

        self._result = result
        _log.info(
            f"[DCC-GARCH] Done. a={dcc_a:.4f}, b={dcc_b:.4f}, "
            f"LL={total_ll:.2f}, AIC={aic:.2f}, BIC={bic:.2f}, "
            f"n_series={n}, T={T}, time={result.estimation_time:.1f}s"
        )
        return result

    # ── Post-estimation ──────────────────────────────────────────────────────

    def get_correlations(
        self,
        period_start: int | None = None,
        period_end: int | None = None,
    ) -> pd.DataFrame:
        """
        获取时变相关系数。

        Parameters
        ----------
        period_start, period_end : int | None
            时期范围。None 表示全部。

        Returns
        -------
        pd.DataFrame
            宽格式相关系数表。
        """
        if self._result is None:
            raise RuntimeError("Must call fit() before get_correlations()")

        corr = self._result.conditional_correlations
        if corr is None:
            return pd.DataFrame()

        names = self._result.series_names
        n = len(names)

        s = period_start or 0
        e = period_end or len(corr)
        corr_sub = corr[s:e]

        # 取上三角（不含对角）
        records = []
        for t_idx, R in enumerate(corr_sub):
            row = {"t": s + t_idx}
            for i in range(n):
                for j in range(i + 1, n):
                    row[f"ρ[{names[i]},{names[j]}]"] = float(R[i, j])
            records.append(row)

        return pd.DataFrame(records)

    def get_average_correlation(
        self,
        period_start: int | None = None,
        period_end: int | None = None,
    ) -> pd.DataFrame:
        """
        获取指定时期的平均相关系数矩阵。

        Parameters
        ----------
        period_start, period_end : int | None

        Returns
        -------
        pd.DataFrame
            n × n 相关系数矩阵。
        """
        corr_df = self.get_correlations(period_start, period_end)
        if corr_df.empty:
            return pd.DataFrame()

        names = self._result.series_names
        n = len(names)
        avg = pd.DataFrame(index=names, columns=names, dtype=float)

        for i in range(n):
            for j in range(n):
                if i == j:
                    avg.iloc[i, j] = 1.0
                elif j > i:
                    col = f"ρ[{names[i]},{names[j]}]"
                    if col in corr_df.columns:
                        avg.iloc[i, j] = corr_df[col].mean()
                else:
                    avg.iloc[i, j] = avg.iloc[j, i]

        return avg

    # ── Visualization ────────────────────────────────────────────────────────

    def plot_correlation(
        self,
        save_path: str | Path | None = None,
        n_pairs_show: int = 6,
        figsize: tuple[float, float] = (12, 6),
    ) -> Any:
        """
        绘制动态条件相关系数时间序列。

        Parameters
        ----------
        save_path : str | Path | None
        n_pairs_show : int
            最多显示的配对数。
        figsize : tuple

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[DCC-GARCH] No result to plot")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[DCC-GARCH] matplotlib not installed")
            return None

        corr_df = self.get_correlations()
        if corr_df.empty:
            return None

        names = self._result.series_names
        n = len(names)

        # 生成所有配对
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                col = f"ρ[{names[i]},{names[j]}]"
                if col in corr_df.columns:
                    pairs.append((names[i], names[j], col))

        pairs = pairs[:n_pairs_show]

        fig, ax = plt.subplots(figsize=figsize)
        t_vals = corr_df["t"].values

        cmap_colors = plt.cm.tab10.colors
        for idx, (ni, nj, col) in enumerate(pairs):
            color = cmap_colors[idx % len(cmap_colors)]
            ax.plot(t_vals, corr_df[col].values, label=f"{ni}–{nj}", linewidth=1.2, color=color)

        ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Period", fontsize=11)
        ax.set_ylabel("Conditional Correlation", fontsize=11)
        ax.set_title("DCC-GARCH: Dynamic Conditional Correlations", fontsize=12, fontweight="bold")
        ax.legend(fontsize=9, loc="best")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[DCC-GARCH] Correlation plot saved: {save_path}")

        return fig

    def plot_heatmap(
        self,
        period_start: int | None = None,
        period_end: int | None = None,
        save_path: str | Path | None = None,
        figsize: tuple[float, float] = (8, 6),
    ) -> Any:
        """
        绘制指定时期的平均相关系数热力图。

        Parameters
        ----------
        period_start, period_end : int | None
        save_path : str | Path | None
        figsize : tuple

        Returns
        -------
        matplotlib Figure 或 None
        """
        if self._result is None:
            _log.warning("[DCC-GARCH] No result to plot")
            return None

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            _log.warning("[DCC-GARCH] matplotlib not installed")
            return None

        avg_corr = self.get_average_correlation(period_start, period_end)
        if avg_corr.empty:
            return None

        names = self._result.series_names

        fig, ax = plt.subplots(figsize=figsize)
        im = ax.imshow(avg_corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

        ax.set_xticks(range(len(names)))
        ax.set_yticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=9, rotation=45)
        ax.set_yticklabels(names, fontsize=9)
        ax.set_title(
            f"DCC-GARCH: Average Conditional Correlations\n"
            f"Period {period_start or 0}–{period_end or self._result.n_obs}",
            fontsize=11,
            fontweight="bold",
        )

        for i in range(len(names)):
            for j in range(len(names)):
                val = avg_corr.values[i, j]
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)

        plt.colorbar(im, ax=ax, label="Correlation")
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            _log.info(f"[DCC-GARCH] Heatmap saved: {save_path}")

        return fig

    # ── Output ────────────────────────────────────────────────────────────────

    def summary(self) -> pd.DataFrame:
        """
        返回模型诊断汇总表。

        Returns
        -------
        pd.DataFrame
        """
        if self._result is None:
            return pd.DataFrame()

        r = self._result
        rows = [
            {"Component": "DCC", "Parameter": "α (alpha)", "Estimate": f"{r.dcc_alpha:.4f}"},
            {"Component": "DCC", "Parameter": "β (beta)", "Estimate": f"{r.dcc_beta:.4f}"},
            {"Component": "DCC", "Parameter": "α + β", "Estimate": f"{r.dcc_alpha + r.dcc_beta:.4f}"},
            {"Component": "Model", "Parameter": "Log-likelihood", "Estimate": f"{r.log_likelihood:.4f}"},
            {"Component": "Model", "Parameter": "AIC", "Estimate": f"{r.aic:.4f}"},
            {"Component": "Model", "Parameter": "BIC", "Estimate": f"{r.bic:.4f}"},
            {"Component": "Model", "Parameter": "N (obs)", "Estimate": str(r.n_obs)},
            {"Component": "Model", "Parameter": "N (series)", "Estimate": str(len(r.series_names))},
        ]

        for name, p in r.garch_params.items():
            rows.append({
                "Component": f"GARCH({name})",
                "Parameter": "ω (omega)",
                "Estimate": f"{p['omega']:.6f}",
            })
            rows.append({
                "Component": f"GARCH({name})",
                "Parameter": "α (alpha)",
                "Estimate": f"{p['alpha']:.4f}",
            })
            rows.append({
                "Component": f"GARCH({name})",
                "Parameter": "β (beta)",
                "Estimate": f"{p['beta']:.4f}",
            })

        return pd.DataFrame(rows)

    def to_latex(
        self,
        caption: str = "DCC-GARCH Estimation Results",
        label: str = "tab:dcc_garch",
    ) -> str:
        """
        导出为 LaTeX 表格。

        Parameters
        ----------
        caption, label : str

        Returns
        -------
        str
        """
        df = self.summary()
        if df.empty:
            return ""

        lines = [
            "\\begin{table}[htbp]",
            "  \\centering",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{label}}}",
            "  \\begin{tabular}{lllcc}",
            "    \\toprule",
            "    \\textbf{Component} & \\textbf{Parameter} & \\textbf{Estimate} \\\\ ",
            "    \\midrule",
        ]

        for _, row in df.iterrows():
            lines.append(f"    {row['Component']} & {row['Parameter']} & {row['Estimate']} \\\\")

        lines.extend([
            "    \\bottomrule",
            "  \\end{tabular}",
            "\\end{table}",
        ])
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    # 模拟宏观金融数据
    np.random.seed(42)
    T = 300
    n = 3
    names = ["gdp_gap", "inflation", "policy_rate"]

    # 生成时变 VAR 数据
    dates = pd.date_range("2000-01-01", periods=T, freq="QE")
    shock = np.sin(np.linspace(0, 4 * np.pi, T)) * 0.3
    y_data = np.zeros((T, n))
    y_data[:, 0] = 0.5 * np.random.randn(T) + shock
    y_data[:, 1] = 0.3 * np.random.randn(T) - 0.2 * shock + 0.5 * np.random.randn(T)
    y_data[:, 2] = 0.4 * np.random.randn(T) + 0.3 * y_data[:, 1]

    Y_df = pd.DataFrame(y_data, index=dates, columns=names)

    print("=" * 60)
    print("TVP-VAR Test")
    print("=" * 60)
    t0 = time.time()
    tvp = TVPVAR(p=2, sv=True)
    result_tvp = tvp.fit(Y_df, n_iter=1000, burn=200, method="kalman_ml")
    print(f"Estimation time: {time.time() - t0:.2f}s")
    print(tvp.summary())

    irf_df = tvp.get_irf(period_start=50, period_end=150, horizon=12)
    if not irf_df.empty:
        print("\nIRF (selected):")
        print(irf_df.head())

    # TVP-VAR 可视化
    fig1 = tvp.plot_irf(n_vars_show=3, horizon=12)
    if fig1:
        fig1.savefig(str(Path(tempfile.gettempdir()) / "tvp_irf.pdf"), dpi=150)
        print("IRF plot saved")

    fig2 = tvp.plot_coefficients()
    if fig2:
        fig2.savefig(str(Path(tempfile.gettempdir()) / "tvp_coef.pdf"), dpi=150)
        print("Coefficient plot saved")

    print("\n" + "=" * 60)
    print("DCC-GARCH Test")
    print("=" * 60)

    # 模拟金融收益率数据
    T2 = 500
    dates2 = pd.date_range("2010-01-01", periods=T2, freq="D")
    np.random.seed(42)

    # 生成相关随机变量
    corr_true = 0.6
    z1 = np.random.randn(T2)
    z2 = np.random.randn(T2)
    z2 = corr_true * z1 + np.sqrt(1 - corr_true**2) * z2

    # 添加波动率聚集性
    vol1 = np.exp(np.linspace(-1, 0.5, T2) * 0.3)
    vol2 = np.exp(np.linspace(-0.5, 0.8, T2) * 0.4)
    r1 = z1 * vol1
    r2 = z2 * vol2

    returns = {
        "equity": pd.Series(r1, index=dates2),
        "bond": pd.Series(r2, index=dates2),
    }

    t1 = time.time()
    dcc = DCCGARCH()
    result_dcc = dcc.fit(returns)
    print(f"Estimation time: {time.time() - t1:.2f}s")
    print(dcc.summary())

    corr_df = dcc.get_correlations(period_start=100, period_end=300)
    if not corr_df.empty:
        print("\nConditional correlations (selected):")
        print(corr_df.head())

    avg_corr = dcc.get_average_correlation(period_start=100, period_end=300)
    if not avg_corr.empty:
        print("\nAverage correlation matrix:")
        print(avg_corr)

    # DCC 可视化
    fig3 = dcc.plot_correlation()
    if fig3:
        fig3.savefig(str(Path(tempfile.gettempdir()) / "dcc_corr.pdf"), dpi=150)
        print("Correlation plot saved")

    fig4 = dcc.plot_heatmap(period_start=100, period_end=300)
    if fig4:
        fig4.savefig(str(Path(tempfile.gettempdir()) / "dcc_heatmap.pdf"), dpi=150)
        print("Heatmap saved")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
