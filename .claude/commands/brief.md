# brief — 生成研究简报

description: 通过交互问卷收集研究需求，生成 FIN_BRIEF.md

# arguments

- `<topic>` (可选): 初步研究主题

# 描述

交互式收集研究需求，生成 `FIN_BRIEF.md`（研究简报），包含：

- 研究主题和领域
- 目标期刊
- 数据来源
- 研究方法偏好
- 行为控制标志（AUTO_PROCEED / HUMAN_CHECKPOINT 等）

# 工作方式

1. AI Agent 提问，用户逐步回答
2. 有 `FIN_BRIEF.md` 时优先读取并确认
3. 生成简报后询问是否启动研究流程

# 示例

```
/brief
/brief 碳排放权交易对企业创新的影响
```
