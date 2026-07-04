"""Mock Data Governance — 模拟数据策略执行（占位 stub）。

P0 修复 2026-06-28: 此模块之前在 user_data_merger.py 中被 try-import 但不存在，
导致 MockDataPolicy / MockDataRegistry 永远为 None，MockDataRegistry.set_policy
等关键保护代码从未生效（软失败掩盖）。

本模块提供:
- MockDataPolicy enum: ALLOW / CONFIRM / DENY
- MockDataRegistry: 集中管理哪些 MCP/数据源可返回 mock/合成数据
- 与 docs/MOCK_DATA_POLICY.md 描述的策略对齐：
  - 默认 DENY：所有 mock MCP 返回错误（生产研究、论文写作）
  - CONFIRM: 要求 LLM 请求中含确认关键词
  - ALLOW: 直接放行（仅用于演示、单元测试、教学）
- 环境变量 MCP_MOCK_MODE 控制全局默认策略
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Set

logger = logging.getLogger(__name__)


class MockDataPolicy(Enum):
    """模拟数据使用策略。"""
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


class MockDataRegistry:
    """模拟数据注册表 — 集中管理 mock 数据源。

    与 docs/MOCK_DATA_POLICY.md 对齐：
    - 默认 policy 为 DENY（生产研究安全）
    - 已知有 mock 风险的 5 个 MCP 列入 registry
    - 调用 is_allowed() 检查请求是否合规
    - 支持 authorize(var, reason) 显式授权合成变量
    """

    KNOWN_MOCK_MCPS: Set[str] = {
        "user-nber-wp",
        "user-bea-data",
        "user-csmar",
        "user-wuhan-stats",
        "user-macro-datas",
    }

    def __init__(self) -> None:
        # 默认策略：从 MCP_MOCK_MODE 环境变量读取，默认 deny
        mode = os.environ.get("MCP_MOCK_MODE", "deny").lower()
        try:
            self._policy = MockDataPolicy(mode)
        except ValueError:
            logger.warning(
                "Invalid MCP_MOCK_MODE=%r, defaulting to DENY", mode
            )
            self._policy = MockDataPolicy.DENY

        # 显式授权记录：var_name -> {reason, authorized_at}
        self._authorizations: dict = {}

    # ── Policy ────────────────────────────────────────────────────────────

    @property
    def policy(self) -> MockDataPolicy:
        """当前 mock 策略（公开属性，与测试期望一致）。"""
        return self._policy

    def set_policy(self, policy: MockDataPolicy) -> None:
        """设置全局 mock 策略。"""
        self._policy = policy
        logger.info("MockDataRegistry policy set to %s", policy.value)

    def get_policy(self) -> MockDataPolicy:
        """获取当前 mock 策略。"""
        return self._policy

    # ── Mock source checks ─────────────────────────────────────────────────

    def is_mock_source(self, server: str) -> bool:
        """判断给定 MCP server 是否已知有 mock 数据风险。"""
        return server in self.KNOWN_MOCK_MCPS

    def is_allowed(self, server: str, confirm_keyword: str = "") -> bool:
        """判断对给定 MCP 的 mock 数据调用是否被允许。

        Args:
            server: MCP server 标识
            confirm_keyword: 当 policy=CONFIRM 时，调用方提供的确认关键词

        Returns:
            True: 允许返回 mock 数据
            False: 拒绝（应返回错误/空）
        """
        if not self.is_mock_source(server):
            return True

        if self._policy == MockDataPolicy.ALLOW:
            return True
        if self._policy == MockDataPolicy.DENY:
            return False
        if self._policy == MockDataPolicy.CONFIRM:
            return confirm_keyword.lower() in {"confirm", "确认", "yes", "approve"}

        return False

    # ── Per-variable authorization (for UserDataMerger synthetic data) ──────

    def authorize(self, var_name: str, reason: str = "") -> bool:
        """显式授权某个变量使用合成/mock 数据。

        P0 修复 2026-06-28: 与 UserDataMerger.authorize_synthetic_variable 配套。

        Args:
            var_name: 变量名（如 "lev", "roa_imputed"）
            reason: 授权原因（必填，用于审计追踪）

        Returns:
            True: 授权成功
            False: 授权失败（policy=DENY 且 reason 为空）
        """
        import datetime as _dt

        if self._policy == MockDataPolicy.DENY and not reason:
            logger.warning(
                "Cannot authorize '%s' without reason under DENY policy", var_name
            )
            return False

        self._authorizations[var_name] = {
            "reason": reason,
            "authorized_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "policy_at_auth": self._policy.value,
        }
        logger.info(
            "MockDataRegistry authorized '%s' (reason=%r, policy=%s)",
            var_name, reason, self._policy.value,
        )
        return True

    def check_authorization(self, var_name: str) -> bool:
        """检查变量是否已被显式授权使用 mock 数据。

        Args:
            var_name: 变量名

        Returns:
            True: 已授权
            False: 未授权
        """
        return var_name in self._authorizations

    def get_authorization_details(self, var_name: str) -> Optional[dict]:
        """获取变量的授权详情。

        Args:
            var_name: 变量名

        Returns:
            dict 包含 reason / authorized_at / policy_at_auth；未授权返回 None
        """
        return self._authorizations.get(var_name)

    def revoke_authorization(self, var_name: str) -> bool:
        """撤销某个变量的 mock 数据授权。

        Returns:
            True: 撤销成功
            False: 变量未被授权
        """
        if var_name in self._authorizations:
            del self._authorizations[var_name]
            return True
        return False


__all__ = ["MockDataPolicy", "MockDataRegistry"]