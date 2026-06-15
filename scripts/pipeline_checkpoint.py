"""
Pipeline Checkpoint — 强制用户交互模块
论文-研报工作流 · FinResearch Agent

【设计原则】
1. 每个阶段完成后，必须停下来等待用户确认
2. 禁止自动继续，必须用户明确选择下一步
3. 模拟数据使用必须有硬中断
4. 每个checkpoint展示当前状态和可选操作

【用法】
    from scripts.pipeline_checkpoint import (
        InteractivePipelineCheckpoint, StageResult, Stage, DecisionOption
    )

    # 创建checkpoint
    cp = InteractivePipelineCheckpoint()

    # 阶段1完成，进入checkpoint
    cp.wait_at_checkpoint(
        stage=Stage.DATA_ACQUISITION,
        summary="数据获取完成",
        details={
            "使用数据源": ["tushare", "akshare"],
            "样本量": "3,200家上市公司",
            "时间范围": "2016-2023",
            "模拟数据": "否"
        },
        risks=["CSMAR海关数据不可用，关税暴露强度数据缺失"],
        next_options=[
            DecisionOption("run_regression", "运行实证回归", "使用当前数据直接跑DID回归"),
            DecisionOption("fix_data", "补充数据后继续", "获取CSMAR数据后再跑回归"),
            DecisionOption("use_synthetic", "授权使用模拟关税数据", "仅演示用，不能发表"),
            DecisionOption("stop", "暂停，等待我确认", "查看报告后再决定"),
        ],
        # 当用户选择需要授权的操作时（模拟数据）
        requires_authorization=False,
        authorization_message=None,
    )

    # 根据用户选择继续
    if cp.last_choice == "fix_data":
        # 引导用户获取数据...
    elif cp.last_choice == "use_synthetic":
        # 需要再次授权检查...
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── ANSI Colors ──────────────────────────────────────────────────────────────

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


# ── 阶段枚举 ────────────────────────────────────────────────────────────────

class Stage(str, Enum):
    IDEA_GENERATION = "想法生成"
    LITERATURE_REVIEW = "文献综述"
    NOVELTY_CHECK = "新颖性验证"
    EXPERIMENT_DESIGN = "实证设计"
    DATA_ACQUISITION = "数据获取"
    PAPER_OUTLINE = "论文大纲"
    PAPER_DRAFT = "论文写作"
    EMPIRICAL_ANALYSIS = "实证分析"
    REVIEW_LOOP = "Review循环"
    SUBMISSION_CHECK = "投稿检查"
    CUSTOM = "自定义"


# ── 阶段中文名称 ───────────────────────────────────────────────────────────

_STAGE_LABELS: dict[Stage, str] = {
    Stage.IDEA_GENERATION: "阶段1：想法生成",
    Stage.LITERATURE_REVIEW: "阶段2：文献综述",
    Stage.NOVELTY_CHECK: "阶段3：新颖性验证",
    Stage.EXPERIMENT_DESIGN: "阶段4：实证设计",
    Stage.DATA_ACQUISITION: "阶段5：数据获取",
    Stage.PAPER_OUTLINE: "阶段6：论文大纲",
    Stage.PAPER_DRAFT: "阶段7：论文写作",
    Stage.EMPIRICAL_ANALYSIS: "阶段8：实证分析",
    Stage.REVIEW_LOOP: "阶段9：Review循环",
    Stage.SUBMISSION_CHECK: "阶段10：投稿检查",
    Stage.CUSTOM: "检查点",
}


# ── 决策选项 ──────────────────────────────────────────────────────────────

@dataclass
class DecisionOption:
    option_id: str           # 唯一标识符
    label: str              # 用户可见的简短标签
    description: str        # 详细说明
    is_destructive: bool = False  # 是否为破坏性操作
    requires_authorization: bool = False  # 是否需要授权（如模拟数据）


@dataclass
class StageResult:
    """阶段执行结果"""
    stage: Stage
    success: bool
    output_files: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    used_synthetic_data: bool = False  # 关键标记


# ── 核心Checkpoint ─────────────────────────────────────────────────────────

class InteractivePipelineCheckpoint:
    """
    强制交互式Checkpoint（区别于 scripts/core/checkpoint.py 中的 PipelineCheckpoint）

    每次调用 wait_at_checkpoint() 都会：
    1. 打印当前阶段的完整状态报告
    2. 展示可选的下一步操作
    3. 读取用户输入
    4. 验证用户选择（拒绝无效输入）
    5. 返回用户选择

    【强制规则】
    - 绝不能跳过用户输入
    - 模拟数据使用必须通过 AskQuestion 询问
    - 无效输入必须重新提示
    """

    def __init__(self):
        self.last_choice: Optional[str] = None
        self.last_stage: Optional[Stage] = None
        self.history: list[dict] = []
        self._authorized_synthetic: bool = False  # 用户是否授权了模拟数据

    def wait_at_checkpoint(
        self,
        stage: Stage,
        summary: str,
        details: Optional[dict] = None,
        risks: Optional[list[str]] = None,
        next_options: Optional[list[DecisionOption]] = None,
        output_files: Optional[list[str]] = None,
        stage_result: Optional[StageResult] = None,
        auto_options: bool = True,
    ) -> str:
        """
        进入交互式checkpoint，等待用户选择下一步。

        Args:
            stage: 当前阶段
            summary: 一句话总结当前状态
            details: 详细状态（dict）
            risks: 潜在风险列表
            next_options: 用户可选操作列表（若None则自动生成）
            output_files: 生成的输出文件
            stage_result: 阶段执行结果（用于自动判断）
            auto_options: 是否自动生成选项（True=自动生成，False=只用传入的options）

        Returns:
            用户选择的 option_id
        """
        self.last_stage = stage

        details = details or {}
        risks = risks or []
        output_files = output_files or []
        stage_label = _STAGE_LABELS.get(stage, stage.value)

        # ── 打印状态报告 ────────────────────────────────────────────────

        print()
        print(c("═" * 64, CYAN))
        stage_line = f"  {stage_label} 完成 — 等待您的确认  "
        print(c("║", CYAN) + c(stage_line.center(58)) + c(" ║", CYAN))
        print(c("═" * 64, CYAN))
        print()

        # 成功状态
        if stage_result and stage_result.success:
            print(f"  {c('✅ ' + summary, GREEN)}")
        else:
            print(f"  {c('⚠️  ' + summary, YELLOW)}")

        print()

        # 详细信息
        if details:
            print(f"  {c('当前状态:', BOLD)}")
            for key, val in details.items():
                val_str = str(val)
                if "模拟" in key or "synthetic" in key.lower() or val_str.lower() == "true":
                    # 模拟数据相关项用黄色警示
                    print(f"    • {key}: {c(val_str, YELLOW)}")
                else:
                    print(f"    • {key}: {val_str}")
            print()

        # 风险提示
        if risks:
            print(f"  {c('⚠️  注意事项:', YELLOW)}")
            for risk in risks:
                print(f"    ⚡ {risk}")
            print()

        # 输出文件
        if output_files:
            print(f"  {c('生成文件:', BOLD)}")
            for f in output_files:
                print(f"    📄 {f}")
            print()

        # 模拟数据警告
        if stage_result and stage_result.used_synthetic_data:
            print(c("  🔴 警告：本阶段使用了模拟数据", RED))
            print(c("     研究结果不能用于发表", RED))
            print(c("     必须替换为真实数据后才能投稿", RED))
            print()

        print(c("─" * 64, CYAN))
        print()

        # ── 生成或验证选项 ─────────────────────────────────────────────

        # 诊断阶段结果，生成风险相关选项
        implicit_options: list[DecisionOption] = []

        if stage_result and stage_result.used_synthetic_data:
            implicit_options.append(DecisionOption(
                "synthetic_confirmed",
                "已确认使用模拟数据（仅演示用）",
                "模拟数据已确认仅用于演示，论文不能发表",
                requires_authorization=False,  # 已经在wait中提示了
            ))

        if stage_result and stage_result.issues:
            implicit_options.append(DecisionOption(
                "view_issues",
                "查看问题详情",
                f"当前有 {len(stage_result.issues)} 个问题需要关注",
            ))

        if next_options:
            all_options = next_options + implicit_options
        else:
            # 自动生成默认选项
            all_options = self._default_options_for_stage(stage, stage_result) + implicit_options

        # 去重（按option_id）
        seen_ids = set()
        final_options: list[DecisionOption] = []
        for opt in all_options:
            if opt.option_id not in seen_ids:
                seen_ids.add(opt.option_id)
                final_options.append(opt)

        # ── 打印选项 ────────────────────────────────────────────────────

        print(f"  {c('请选择下一步操作:', BOLD)}")
        print()
        for i, opt in enumerate(final_options, 1):
            auth_marker = c(" [需授权]", RED) if opt.requires_authorization else ""
            danger_marker = c(" ⚠️", RED) if opt.is_destructive else ""
            print(f"    ({i}) {opt.label}{auth_marker}{danger_marker}")
            print(f"        {opt.description}")
            print()

        # ── 读取用户输入（强制）───────────────────────────────────────

        while True:
            try:
                raw = input(f"  {c('请输入选项编号 (1-{})：', BOLD)}".format(len(final_options))).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                print(c("已退出。请重启对话继续。", YELLOW))
                sys.exit(0)

            if not raw:
                print(f"  {c('请输入有效选项（1-{}）'.format(len(final_options)), RED)}")
                continue

            try:
                idx = int(raw) - 1
                if 0 <= idx < len(final_options):
                    chosen = final_options[idx]
                    break
                else:
                    print(f"  {c('无效选项，请输入 1-{}'.format(len(final_options)), RED)}")
                    continue
            except ValueError:
                # 用户可能输入了option_id而非数字
                matched = [o for o in final_options if o.option_id == raw]
                if matched:
                    chosen = matched[0]
                    break
                print(f"  {c('无效输入，请输入数字 1-{} 或选项ID'.format(len(final_options)), RED)}")
                continue

        self.last_choice = chosen.option_id

        # 记录历史
        self.history.append({
            "stage": stage.value,
            "summary": summary,
            "choice": chosen.option_id,
            "chosen_label": chosen.label,
        })

        print(f"\n  {c('→ 已选择: ' + chosen.label, GREEN)}")
        print(c("─" * 64, CYAN))
        print()

        return chosen.option_id

    def _default_options_for_stage(
        self,
        stage: Stage,
        stage_result: Optional[StageResult] = None,
    ) -> list[DecisionOption]:
        """根据阶段自动生成默认选项"""
        base_options: list[DecisionOption] = []

        if stage == Stage.DATA_ACQUISITION:
            base_options = [
                DecisionOption(
                    "proceed_regression",
                    "运行实证回归",
                    "基于已有数据继续下一步（阶段8：实证分析）",
                ),
                DecisionOption(
                    "improve_data",
                    "补充数据后继续",
                    "获取更多数据（如CSMAR海关数据）后再跑回归",
                ),
                DecisionOption(
                    "view_data_status",
                    "查看数据状态报告",
                    "查看 DATA_MANIFEST.md 了解当前数据缺口",
                ),
                DecisionOption(
                    "stop_for_confirmation",
                    "暂停，等待确认",
                    "我先查看报告，确认无误后再继续",
                ),
            ]

        elif stage == Stage.PAPER_OUTLINE:
            base_options = [
                DecisionOption(
                    "proceed_writing",
                    "开始论文写作",
                    "基于大纲生成论文正文（阶段7）",
                ),
                DecisionOption(
                    "revise_outline",
                    "修改大纲",
                    "调整论文结构和内容安排",
                ),
                DecisionOption(
                    "stop_for_confirmation",
                    "暂停，等待确认",
                    "我先查看大纲，确认后再说",
                ),
            ]

        elif stage == Stage.EMPIRICAL_ANALYSIS:
            base_options = [
                DecisionOption(
                    "proceed_writing",
                    "开始论文写作",
                    "基于实证结果撰写论文正文",
                ),
                DecisionOption(
                    "additional_tests",
                    "补充更多检验",
                    "做更多稳健性/异质性分析",
                ),
                DecisionOption(
                    "stop_for_confirmation",
                    "暂停，等待确认",
                    "我先查看回归结果，确认后再继续",
                ),
            ]

        else:
            # 通用选项
            base_options = [
                DecisionOption(
                    "continue",
                    "继续下一阶段",
                    "进入下一研究阶段",
                ),
                DecisionOption(
                    "stop_for_confirmation",
                    "暂停，等待确认",
                    "我先查看当前结果，确认后再继续",
                ),
            ]

        return base_options

    # ── 模拟数据授权检查 ─────────────────────────────────────────────────

    def authorize_synthetic_or_stop(self, purpose: str) -> bool:
        """
        模拟数据授权检查。

        如果用户未授权，返回 False，调用方必须：
        - 停止当前流程
        - 向用户展示获取真实数据的方法

        Returns:
            True = 用户已授权使用模拟数据
            False = 用户拒绝或未授权，必须停止
        """
        print()
        print(c("═" * 64, YELLOW))
        print(c("🔴 重要：需要使用模拟数据", YELLOW))
        print(c("═" * 64, YELLOW))
        print()
        print(f"  您选择的任务需要以下数据，但当前没有可用来源：")
        print(f"  {purpose}")
        print()
        print(f"  {c('模拟数据仅用于：', BOLD)}")
        print(f"    • 演示完整研究流程")
        print(f"    • 验证分析代码和框架")
        print(f"    • 论文不能发表")
        print()
        print(f"  {c('真实数据获取途径：', BOLD)}")
        print(f"    • Tushare Pro: https://tushare.pro/register")
        print(f"    • CSMAR: 通过学校图书馆VPN访问")
        print(f"    • 将数据文件放入 data/ 目录")
        print()
        print(c("═" * 64, YELLOW))
        print(f"  {c('请选择：', BOLD)}")
        print()
        print(f"    (1) 我已了解，授权使用模拟数据（仅演示用）")
        print(f"    (2) 暂停，我先去获取真实数据")
        print(f"    (3) 更换研究方向（选择数据更易获取的主题）")
        print()
        print(c("═" * 64, YELLOW))
        print()

        while True:
            try:
                raw = input(f"  {c('请输入选项 (1/2/3)：', BOLD)}").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit(0)

            if raw == "1":
                self._authorized_synthetic = True
                print(f"\n  {c('✅ 已授权使用模拟数据（仅演示用）', GREEN)}")
                print(c("─" * 64, CYAN))
                return True
            elif raw == "2":
                print(f"\n  {c('⏸️  流程暂停。请先获取真实数据。', YELLOW)}")
                print(f"  参考: output/fin-experiments/DATA_MANIFEST.md")
                print(c("─" * 64, CYAN))
                return False
            elif raw == "3":
                print(f"\n  {c('⏸️  流程暂停。请描述新的研究方向。', YELLOW)}")
                print(c("─" * 64, CYAN))
                return False
            else:
                print(f"  {c('无效输入，请输入 1、2 或 3', RED)}")

    @property
    def is_synthetic_authorized(self) -> bool:
        """返回用户是否已授权使用模拟数据"""
        return self._authorized_synthetic

    def reset_authorization(self) -> None:
        """重置模拟数据授权状态"""
        self._authorized_synthetic = False

    # ── 工具方法 ──────────────────────────────────────────────────────────

    def print_history(self) -> None:
        """打印所有历史选择"""
        print()
        print(c("Pipeline 交互历史:", BOLD))
        for entry in self.history:
            print(f"  [{entry['stage']}] {entry['summary']}")
            print(f"    → {entry['chosen_label']}")
        print()

    def confirm_proceed(self, message: str = "确认继续？") -> bool:
        """
        简单确认提示。
        返回 True=继续，False=停止。
        """
        print()
        print(f"  {c(message, BOLD)}")
        print(f"    (y) 确认继续")
        print(f"    (n) 停止")
        print()

        while True:
            try:
                raw = input(f"  请输入 (y/n)：").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

            if raw in ("y", "yes", "是", "确认"):
                return True
            elif raw in ("n", "no", "否", "停止"):
                return False
            else:
                print(f"  {c('请输入 y 或 n', RED)}")
