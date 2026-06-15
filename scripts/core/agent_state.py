#!/usr/bin/env python3
"""
Agent 状态与事件管理系统
========================
提供实时状态推送、成本追踪、错误分类等功能

核心功能：
1. 事件总线 - 发布/订阅模式
2. Agent状态管理 - 实时状态追踪
3. 成本追踪 - Token消耗统计
4. 错误分类 - 错误分类与重试
5. Human-in-the-Loop - 人工审核队列
"""

from __future__ import annotations

__all__ = [
    "AgentStatus",
    "EventType",
    "ErrorType",
    "AgentState",
    "Event",
    "CostRecord",
    "HITLRequest",
    "EventBus",
    "AgentStateManager",
    "CostTracker",
    "ErrorClassifier",
    "HITLManager",
    "event_bus",
    "agent_state_manager",
    "cost_tracker",
    "hitl_manager",
    "get_fleet_status",
    "get_total_cost",
    "get_pending_hitl",
    "record_api_call",
]

import logging
import queue
import threading
import time
import uuid

logger = logging.getLogger(__name__)
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════════════════════

class AgentStatus(Enum):
    """Agent运行状态"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 运行中
    WAITING = "waiting"     # 等待人工审核
    SUCCEEDED = "succeeded" # 成功
    FAILED = "failed"       # 失败
    RETRYING = "retrying"   # 重试中

class EventType(Enum):
    """事件类型"""
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"
    AGENT_RETRY = "agent_retry"
    TASK_CREATE = "task_create"
    TASK_COMPLETE = "task_complete"
    HITL_REQUEST = "hitl_request"      # 人工审核请求
    HITL_APPROVE = "hitl_approve"      # 人工审核通过
    HITL_REJECT = "hitl_reject"        # 人工审核拒绝
    COST_UPDATE = "cost_update"         # 成本更新
    STATE_CHANGE = "state_change"       # 状态变更

class ErrorType(Enum):
    """错误类型"""
    API_ERROR = "api_error"           # API错误
    TIMEOUT = "timeout"               # 超时
    RATE_LIMIT = "rate_limit"         # 频率限制
    AUTH_ERROR = "auth_error"         # 认证错误
    PARSE_ERROR = "parse_error"       # 解析错误
    VALIDATION_ERROR = "validation_error"  # 验证错误
    UNKNOWN = "unknown"               # 未知错误


# ═══════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AgentState:
    """Agent状态"""
    agent_id: str
    name: str
    status: AgentStatus
    current_task: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    error_count: int = 0
    last_error: str | None = None
    metadata: dict = field(default_factory=dict)

@dataclass
class Event:
    """事件"""
    event_id: str
    event_type: EventType
    agent_id: str | None
    timestamp: float
    data: dict
    duration_ms: float | None = None

@dataclass
class CostRecord:
    """成本记录"""
    record_id: str
    agent_id: str
    timestamp: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    task_id: str | None = None

@dataclass
class HITLRequest:
    """人工审核请求"""
    request_id: str
    agent_id: str
    task_id: str
    decision_point: str
    context: dict
    created_at: float
    status: str = "pending"  # pending, approved, rejected
    reviewed_at: float | None = None
    reviewer_comment: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# 事件总线
# ═══════════════════════════════════════════════════════════════════════════

class EventBus:
    """事件总线 - 发布/订阅模式"""

    _instance: EventBus | None = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._subscribers: dict[EventType, list[Callable]] = defaultdict(list)
            self._all_subscribers: list[Callable] = []
            self._event_queue: queue.Queue = queue.Queue()
            self._running = False
            self._thread: threading.Thread | None = None
            self._initialized = True

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """订阅特定事件类型"""
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[Event], None]):
        """订阅所有事件"""
        self._all_subscribers.append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """取消订阅"""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def publish(self, event: Event):
        """发布事件"""
        self._event_queue.put(event)

    def _process_events(self):
        """Event processing thread — deduplicates notifications."""
        while self._running:
            try:
                event = self._event_queue.get(timeout=0.1)

                notified: set[Callable] = set()

                # Notify type-specific subscribers
                for callback in self._subscribers.get(event.event_type, []):
                    try:
                        callback(event)
                        notified.add(callback)
                    except Exception as e:
                        print(f"事件处理错误: {e}")

                # Notify all-subscribers, skipping any already notified
                for callback in self._all_subscribers:
                    if callback in notified:
                        continue
                    try:
                        callback(event)
                    except Exception as e:
                        print(f"事件处理错误: {e}")

            except queue.Empty:
                continue

    def start(self):
        """启动事件处理"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._process_events, daemon=True)
        self._thread.start()

    def stop(self):
        """停止事件处理"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)


# ═══════════════════════════════════════════════════════════════════════════
# Agent状态管理器
# ═══════════════════════════════════════════════════════════════════════════

class AgentStateManager:
    """Agent状态管理器"""

    _instance: AgentStateManager | None = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._agents: dict[str, AgentState] = {}
            self._history: list[Event] = []
            self._lock = threading.Lock()
            self._event_bus = _get_shared_eventbus()
            self._event_bus.start()
            self._initialized = True

    def register_agent(self, agent_id: str, name: str, metadata: dict = None) -> AgentState:
        """注册Agent"""
        with self._lock:
            state = AgentState(
                agent_id=agent_id,
                name=name,
                status=AgentStatus.IDLE,
                metadata=metadata or {}
            )
            self._agents[agent_id] = state

            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.STATE_CHANGE,
                agent_id=agent_id,
                timestamp=time.time(),
                data={"status": "registered", "name": name}
            )
            self._event_bus.publish(event)

            return state

    def start_agent(self, agent_id: str, task: str = None) -> bool:
        """启动Agent"""
        with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]
            agent.status = AgentStatus.RUNNING
            agent.current_task = task
            agent.start_time = time.time()
            agent.end_time = None

            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.AGENT_START,
                agent_id=agent_id,
                timestamp=time.time(),
                data={"task": task}
            )
            self._event_bus.publish(event)

            self._history.append(event)
            return True

    def end_agent(self, agent_id: str, success: bool = True, error: str = None) -> bool:
        """结束Agent"""
        with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]
            agent.status = AgentStatus.SUCCEEDED if success else AgentStatus.FAILED
            agent.end_time = time.time()
            if error:
                agent.last_error = error
                agent.error_count += 1

            duration_ms = (agent.end_time - agent.start_time) * 1000 if agent.start_time else None

            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.AGENT_END,
                agent_id=agent_id,
                timestamp=time.time(),
                data={"success": success, "error": error},
                duration_ms=duration_ms
            )
            self._event_bus.publish(event)

            self._history.append(event)
            return True

    def set_waiting(self, agent_id: str, reason: str = None) -> bool:
        """设置Agent等待人工审核"""
        with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]
            agent.status = AgentStatus.WAITING

            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.HITL_REQUEST,
                agent_id=agent_id,
                timestamp=time.time(),
                data={"reason": reason}
            )
            self._event_bus.publish(event)
            self._history.append(event)
            return True

    def retry_agent(self, agent_id: str) -> bool:
        """重试Agent"""
        with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]
            agent.status = AgentStatus.RETRYING

            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.AGENT_RETRY,
                agent_id=agent_id,
                timestamp=time.time(),
                data={"retry_count": agent.error_count}
            )
            self._event_bus.publish(event)
            self._history.append(event)
            return True

    def get_agent(self, agent_id: str) -> AgentState | None:
        """获取Agent状态"""
        return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentState]:
        """获取所有Agent状态"""
        return list(self._agents.values())

    def get_history(self, limit: int = 100) -> list[Event]:
        """获取事件历史"""
        return self._history[-limit:]

    def get_fleet_status(self) -> dict:
        """获取舰队状态概览"""
        agents = self.get_all_agents()

        status_counts = defaultdict(int)
        for agent in agents:
            status_counts[agent.status.value] += 1

        return {
            "total_agents": len(agents),
            "status_breakdown": dict(status_counts),
            "running_count": status_counts["running"],
            "failed_count": status_counts["failed"],
            "idle_count": status_counts["idle"],
            "waiting_count": status_counts["waiting"],
        }


# ═══════════════════════════════════════════════════════════════════════════
# 成本追踪器
# ═══════════════════════════════════════════════════════════════════════════

class CostTracker:
    """成本追踪器"""

    _instance: CostTracker | None = None
    _init_lock = threading.Lock()

    # Token定价（每1M token的美元价格）
    # 键名必须与 build_model_pool() 中 ModelConfig.model_id 严格一致
    PRICING: dict[str, dict[str, float]] = {
        # DeepSeek 直连
        "deepseek-v4-flash": {"input": 0.14,  "output": 0.28},   # DeepSeek V4 Flash
        "deepseek-v4-pro":   {"input": 0.50,  "output": 2.00},   # DeepSeek V4 Pro
        "deepseek-r1":       {"input": 0.55,  "output": 2.20},   # DeepSeek R1
        # Relay — GPT 系列
        "gpt-4o-mini":      {"input": 0.15,  "output": 0.60},   # GPT-4o-Mini
        # Relay — Claude 系列
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},  # Claude Sonnet
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00}, # Claude 3.5 Sonnet
        # Relay — 其他
        "glm-4-plus":        {"input": 0.10,  "output": 0.30},   # GLM-4-Plus
        "moonshot-v1-8k":    {"input": 0.10,  "output": 0.30},   # Kimi K2.5
        # 本地
        "llama3.2":          {"input": 0.00,  "output": 0.00},   # Ollama 本地模型（免费）
        # 旧别名兼容（fallback，指向实际 model_id）
        "deepseek-chat":     {"input": 0.14,  "output": 0.28},   # 旧名 → deepseek-v4-flash
        "deepseek-v3":       {"input": 0.50,  "output": 2.00},   # 旧名 → deepseek-v4-pro
        "gpt-4o":           {"input": 5.00,  "output": 15.00},  # 旧名 fallback
        "gpt-4o-mini":      {"input": 0.15,  "output": 0.60},   # 旧名 fallback
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._records: list[CostRecord] = []
            self._agent_costs: dict[str, dict] = defaultdict(lambda: {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "call_count": 0
            })
            self._lock = threading.Lock()
            self._event_bus = _get_shared_eventbus()
            self._pricing: dict[str, dict[str, float]] = {}
            self._initialized = True
        self._load_pricing_from_config()

    def _load_pricing_from_config(self, config_path: str | None = None) -> bool:
        """
        Load token pricing from config file, overlaying defaults.

        Config format (JSON):
            {"model_pricing": {"gpt-4o": {"input": 5.0, "output": 15.0}}}

        Supports paths relative to the project root or absolute paths.
        """
        import json
        if config_path is None:
            candidates = [
                Path("config/model_pricing.json"),
                Path("config/llm_config.json"),
                Path(".cache/model_pricing.json"),
            ]
            for candidate in candidates:
                expanded = candidate.expanduser()
                if not expanded.is_absolute():
                    expanded = Path(__file__).parent.parent.parent / candidate
                if expanded.exists():
                    config_path = str(expanded)
                    break

        if config_path is None:
            return False

        try:
            with open(config_path, encoding="utf-8") as fh:
                data = json.load(fh)

            pricing_data = (
                data.get("model_pricing")
                or data.get("pricing")
                or data.get("models", {}).get("pricing", {})
            )

            loaded = 0
            for model_id, cost_info in pricing_data.items():
                if isinstance(cost_info, dict) and "input" in cost_info and "output" in cost_info:
                    self._pricing[model_id] = {
                        "input": float(cost_info["input"]),
                        "output": float(cost_info["output"]),
                    }
                    loaded += 1

            if loaded > 0:
                logger.info("[CostTracker] Loaded %d pricing entries from %s", loaded, config_path)
            return loaded > 0
        except Exception as exc:
            logger.debug("[CostTracker] Could not load pricing config from %s: %s", config_path, exc)
            return False

    def get_pricing(self, model: str) -> dict[str, float]:
        """Return pricing for a model, checking instance config then class defaults."""
        if model in self._pricing:
            return self._pricing[model]
        return self.PRICING.get(model, {"input": 1.0, "output": 2.0})

    def record(
        self,
        agent_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        task_id: str = None
    ) -> CostRecord:
        """记录一次API调用"""
        # 计算成本
        pricing = self.get_pricing(model)
        cost = (input_tokens / 1_000_000) * pricing["input"] + \
               (output_tokens / 1_000_000) * pricing["output"]

        record = CostRecord(
            record_id=str(uuid.uuid4()),
            agent_id=agent_id,
            timestamp=time.time(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=model,
            task_id=task_id
        )

        with self._lock:
            self._records.append(record)
            self._agent_costs[agent_id]["total_input_tokens"] += input_tokens
            self._agent_costs[agent_id]["total_output_tokens"] += output_tokens
            self._agent_costs[agent_id]["total_cost"] += cost
            self._agent_costs[agent_id]["call_count"] += 1

        # 发布事件
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.COST_UPDATE,
            agent_id=agent_id,
            timestamp=time.time(),
            data={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
                "model": model
            }
        )
        self._event_bus.publish(event)

        return record

    def get_agent_cost(self, agent_id: str) -> dict:
        """获取Agent成本汇总"""
        with self._lock:
            return dict(self._agent_costs.get(agent_id, {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "call_count": 0
            }))

    def get_total_cost(self) -> dict:
        """获取总成本"""
        with self._lock:
            total_input = sum(r.input_tokens for r in self._records)
            total_output = sum(r.output_tokens for r in self._records)
            total_cost = sum(r.cost_usd for r in self._records)

            return {
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cost_usd": total_cost,
                "total_calls": len(self._records),
                "cost_per_call": total_cost / len(self._records) if self._records else 0
            }

    def get_cost_by_agent(self) -> dict:
        """获取按Agent分解的成本"""
        with self._lock:
            return {
                agent_id: dict(stats)
                for agent_id, stats in self._agent_costs.items()
            }

    def get_cost_timeline(self, hours: int = 24) -> list[dict]:
        """获取成本时间线"""
        cutoff = time.time() - hours * 3600

        with self._lock:
            timeline = []
            for record in self._records:
                if record.timestamp >= cutoff:
                    timeline.append({
                        "timestamp": record.timestamp,
                        "agent_id": record.agent_id,
                        "cost_usd": record.cost_usd,
                        "input_tokens": record.input_tokens,
                        "output_tokens": record.output_tokens
                    })

            return timeline

    def get_recent_records(self, limit: int = 50) -> list[CostRecord]:
        """获取最近的调用记录"""
        with self._lock:
            return self._records[-limit:]


# ═══════════════════════════════════════════════════════════════════════════
# 错误分类器
# ═══════════════════════════════════════════════════════════════════════════

class ErrorClassifier:
    """错误分类器"""

    # 错误关键词映射
    ERROR_PATTERNS = {
        ErrorType.API_ERROR: [
            "api error", "api_key", "invalid request", "bad request",
            "internal server error", "service unavailable"
        ],
        ErrorType.TIMEOUT: [
            "timeout", "timed out", "request timeout", "connection timeout"
        ],
        ErrorType.RATE_LIMIT: [
            "rate limit", "too many requests", "quota exceeded",
            "rate_limit_exceeded", "429"
        ],
        ErrorType.AUTH_ERROR: [
            "authentication", "unauthorized", "forbidden", "401", "403",
            "invalid api key", "expired token"
        ],
        ErrorType.PARSE_ERROR: [
            "parse", "json decode", "invalid json", "unexpected token"
        ],
        ErrorType.VALIDATION_ERROR: [
            "validation", "invalid parameter", "missing required",
            "constraint violation"
        ]
    }

    @classmethod
    def classify(cls, error_message: str) -> ErrorType:
        """分类错误"""
        error_lower = error_message.lower()

        for error_type, patterns in cls.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern in error_lower:
                    return error_type

        return ErrorType.UNKNOWN

    @classmethod
    def get_retry_strategy(cls, error_type: ErrorType) -> dict:
        """获取重试策略"""
        strategies = {
            ErrorType.API_ERROR: {"max_retries": 3, "backoff": "exponential"},
            ErrorType.TIMEOUT: {"max_retries": 2, "backoff": "linear"},
            ErrorType.RATE_LIMIT: {"max_retries": 5, "backoff": "exponential", "wait": 60},
            ErrorType.AUTH_ERROR: {"max_retries": 0, "backoff": None},
            ErrorType.PARSE_ERROR: {"max_retries": 1, "backoff": "linear"},
            ErrorType.VALIDATION_ERROR: {"max_retries": 0, "backoff": None},
            ErrorType.UNKNOWN: {"max_retries": 2, "backoff": "exponential"},
        }
        return strategies.get(error_type, strategies[ErrorType.UNKNOWN])


# ═══════════════════════════════════════════════════════════════════════════
# Human-in-the-Loop 审核队列
# ═══════════════════════════════════════════════════════════════════════════

class HITLManager:
    """人工审核管理器

    Features:
        - Thread-safe singleton via double-check locking
        - Timeout enforcement: pending requests auto-reject after configurable seconds
        - Shared EventBus for all HITL events
        - Rich query API: pending, history, by agent, by stage
    """

    _instance: HITLManager | None = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(
        self,
        default_timeout_seconds: float | None = 600.0,
    ):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._requests: dict[str, HITLRequest] = {}
            self._lock = threading.Lock()
            self._event_bus = _get_shared_eventbus()
            self.default_timeout_seconds = default_timeout_seconds
            self._initialized = True

    def create_request(
        self,
        agent_id: str,
        task_id: str,
        decision_point: str,
        context: dict
    ) -> HITLRequest:
        """创建审核请求"""
        request = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id=agent_id,
            task_id=task_id,
            decision_point=decision_point,
            context=context,
            created_at=time.time()
        )

        with self._lock:
            self._requests[request.request_id] = request

        # 发布事件
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.HITL_REQUEST,
            agent_id=agent_id,
            timestamp=time.time(),
            data={
                "request_id": request.request_id,
                "decision_point": decision_point,
                "task_id": task_id
            }
        )
        self._event_bus.publish(event)

        return request

    def approve(self, request_id: str, comment: str = None) -> bool:
        """批准请求"""
        with self._lock:
            if request_id not in self._requests:
                return False

            request = self._requests[request_id]
            request.status = "approved"
            request.reviewed_at = time.time()
            request.reviewer_comment = comment

        # 发布事件
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.HITL_APPROVE,
            agent_id=request.agent_id,
            timestamp=time.time(),
            data={"request_id": request_id, "comment": comment}
        )
        self._event_bus.publish(event)

        return True

    def reject(self, request_id: str, comment: str = None) -> bool:
        """拒绝请求"""
        with self._lock:
            if request_id not in self._requests:
                return False

            request = self._requests[request_id]
            request.status = "rejected"
            request.reviewed_at = time.time()
            request.reviewer_comment = comment

        # 发布事件
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.HITL_REJECT,
            agent_id=request.agent_id,
            timestamp=time.time(),
            data={"request_id": request_id, "comment": comment}
        )
        self._event_bus.publish(event)

        return True

    def check_timeouts(self, timeout_seconds: float | None = None) -> list[HITLRequest]:
        """
        Check all pending requests for timeout and auto-reject expired ones.

        Parameters
        ----------
        timeout_seconds : float | None
            Override the default timeout. None uses self.default_timeout_seconds.

        Returns
        -------
        list[HITLRequest]
            List of requests that were auto-rejected due to timeout.
        """
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        if timeout is None:
            return []

        now = time.time()
        expired: list[HITLRequest] = []

        with self._lock:
            for req in list(self._requests.values()):
                if req.status == "pending" and (now - req.created_at) > timeout:
                    req.status = "rejected"
                    req.reviewed_at = now
                    req.reviewer_comment = f"自动超时回退（>{timeout}s 无响应）"
                    expired.append(req)

                    event = Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.HITL_REJECT,
                        agent_id=req.agent_id,
                        timestamp=now,
                        data={
                            "request_id": req.request_id,
                            "comment": req.reviewer_comment,
                            "auto_rejected": True,
                            "elapsed_seconds": now - req.created_at,
                        }
                    )
                    self._event_bus.publish(event)

        return expired

    def get_pending(self) -> list[HITLRequest]:
        """获取待审核请求（仅返回真正 pending 状态的）"""
        with self._lock:
            return [
                req for req in self._requests.values()
                if req.status == "pending"
            ]

    def get_pending_with_elapsed(self) -> list[dict]:
        """获取待审核请求，含已等待时间和超时预警。"""
        timeout = self.default_timeout_seconds
        now = time.time()
        with self._lock:
            result = []
            for req in self._requests.values():
                if req.status == "pending":
                    elapsed = now - req.created_at
                    result.append({
                        "request": req,
                        "elapsed_seconds": elapsed,
                        "timeout_warning": timeout is not None and elapsed > timeout * 0.8,
                        "is_expired": timeout is not None and elapsed > timeout,
                    })
            return result

    def get_request(self, request_id: str) -> HITLRequest | None:
        """获取请求详情"""
        return self._requests.get(request_id)

    def get_all(self) -> list[HITLRequest]:
        """获取所有请求"""
        return list(self._requests.values())

    def restore_from_checkpoint(self, hitl_state: dict | None) -> int:
        """
        从 checkpoint 中恢复 HITL 请求状态。

        仅恢复 pending 状态的请求（用户可能还在等待审批）。
        已被批准/拒绝的请求不会被重新激活。

        Parameters
        ----------
        hitl_state : dict | None
            checkpoint 中保存的 HITL 状态，格式：
            {
                "pending_requests": [
                    {"request_id": "...", "agent_name": "...",
                     "task_id": "...", "step_name": "...", "created_at": ...},
                    ...
                ],
                "collected_at": ...
            }

        Returns
        -------
        int
            恢复的 pending 请求数量。
        """
        if not hitl_state or "pending_requests" not in hitl_state:
            return 0

        restored = 0
        now = time.time()
        preserved_statuses = {"pending"}

        with self._lock:
            for req_data in hitl_state["pending_requests"]:
                request_id = req_data["request_id"]
                # 如果请求已存在于当前状态，跳过
                if request_id in self._requests:
                    continue

                # 重建请求（使用新 request_id 避免与新请求冲突）
                # 原始 created_at 保留以便计算等待时间
                original_created_at = req_data.get("created_at", now)
                new_request_id = str(uuid.uuid4())

                request = HITLRequest(
                    request_id=new_request_id,
                    agent_id=req_data.get("agent_name", "unknown"),
                    task_id=req_data.get("task_id", "unknown"),
                    decision_point=req_data.get("step_name", "checkpoint_resume"),
                    # Restore context from serialized summary if full context unavailable
                    context=req_data.get("context", req_data.get("context_summary", {})),
                    created_at=original_created_at,
                    # 状态设为 pending，等待用户确认是否恢复
                    status="pending",
                )

                self._requests[new_request_id] = request

                # 发布事件以便监听器知道有恢复的请求
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.HITL_REQUEST,
                    agent_id=request.agent_id,
                    timestamp=now,
                    data={
                        "request_id": new_request_id,
                        "restored_from": request_id,
                        "step_name": req_data.get("step_name", ""),
                        "task_id": req_data.get("task_id", ""),
                        "restored_at": now,
                        "waiting_since": original_created_at,
                    },
                )
                self._event_bus.publish(event)
                restored += 1

        if restored > 0:
            logger.warning(
                "[HITLManager] Restored %d pending HITL requests from checkpoint. "
                "These will require re-approval after resume.",
                restored,
            )
        return restored


# ═══════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════

# Shared EventBus: one bus instance used by all singletons.
_shared_eventbus: EventBus | None = None
_shared_bus_lock = threading.Lock()


def _get_shared_eventbus() -> EventBus:
    """Return the shared EventBus instance (lazy, thread-safe)."""
    global _shared_eventbus
    with _shared_bus_lock:
        if _shared_eventbus is None:
            _shared_eventbus = EventBus()
        return _shared_eventbus


# Create global singleton instances (all share the same EventBus via _get_shared_eventbus)
event_bus = _get_shared_eventbus()
agent_state_manager = AgentStateManager()
cost_tracker = CostTracker()
hitl_manager = HITLManager()


# ═══════════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════════

def get_fleet_status() -> dict:
    """获取舰队状态"""
    return agent_state_manager.get_fleet_status()

def get_total_cost() -> dict:
    """获取总成本"""
    return cost_tracker.get_total_cost()

def get_pending_hitl() -> list[HITLRequest]:
    """获取待审核请求"""
    return hitl_manager.get_pending()

def record_api_call(
    agent_id: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    task_id: str = None
):
    """记录API调用"""
    return cost_tracker.record(agent_id, input_tokens, output_tokens, model, task_id)
