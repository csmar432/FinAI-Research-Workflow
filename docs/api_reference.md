# API 参考

> 每个 Python 模块都包含完整的 docstring 和类型注解。本页提供模块级总览。

## 核心入口脚本

| 脚本 | 功能 |
|------|------|
| `scripts/agent_pipeline.py` | 端到端流水线（主题 → 论文草稿）|
| `scripts/health_check.py` | 系统健康检查（每次启动前运行）|
| `scripts/setup_wizard.py` | 交互式配置向导 |
| `scripts/register_mcp_servers.py` | 一键注册 43 个 MCP 服务器 |
| `scripts/research_framework/pipeline.py` | 研究执行层 |
| `scripts/journal_template.py` | 45 种期刊模板 |

## Agent 编排层（`scripts/core/`）

| 模块 | 功能 |
|------|------|
| `llm_gateway.py` | LLM 统一网关（DeepSeek/GPT/Claude）|
| `llm_reviewer.py` | 对抗性 paper reviewer |
| `agent_state.py` | Agent 状态管理 |
| `checkpoint.py` | 断点续传 + Pipeline Telemetry |
| `event_monitor.py` | 宏观事件监控（NFP/CPI/FOMC）|
| `mcp_tool_market.py` | MCP 工具市场 |
| `provenance.py` | 数据溯源追踪 |
| `quality_gates.py` | 质量门禁 |
| `auto_review_rules.py` | 自动评分规则 |
| `reviewer_calibrator.py` | Reviewer 偏见校准 |

## 研究执行层（`scripts/research_framework/`）

| 类别 | 模块 |
|------|------|
| **DID** | `modern_did.py` — CS/SunAb/Borusyak/GB/dCdH |
| **合成控制** | `synthetic_control.py`, `synthetic_did.py` |
| **RDD** | `rdd.py` |
| **IV/GMM** | `iv_panel.py`, `panel_var.py` |
| **其他方法** | `spatial_regression.py`, `panel_quantile_regression.py`, `interactive_fixed_effects.py`, `local_projections_did.py`, `triple_diff_did.py` |
| **数据** | `data_fetcher.py` — 7 层 fallback |
| **图表** | `fin_charts.py` — 20 种专业金融图表 |
| **输出** | `report_generator.py` — LaTeX/Word |
| **稳健性** | `robustness_runner.py` — 18 类检验 |

## MCP 服务器（`mcp_servers/`）

43 个 MCP 数据服务器，详见 [MCP 市场](tutorials/04-mcp-marketplace.md)。

## CLI 命令

```bash
# 安装后可用
finai                    # 主入口
finai-pipeline --topic "..."   # 流水线
finai-health             # 健康检查
finai-data               # 数据获取
finai-lit-review         # 文献综述
finai-test               # 运行测试
```
