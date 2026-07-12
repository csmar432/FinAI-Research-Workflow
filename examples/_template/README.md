# Example Template · 研究想法 → 论文草稿

> **本目录是示例骨架, 用户可基于此创建自己的研究项目。**
>
> 完整示例 (含真实数据调用): 参见 `examples/01-carbon-did/`, `02-green-credit-psm-did/`, `03-digital-finance-esg/`。
> 注意: 这些示例脚本依赖 `DEEPSEEK_API_KEY` 且质量参差不齐, 默认不上传;
> 详见 `.gitignore:202-203`。

---

## 🚀 5 步创建新研究项目

```bash
# 1. 复制模板
cp -r examples/_template examples/my-research
cd examples/my-research

# 2. 编辑 IDEA_REPORT.md — 描述研究想法
# 3. 编辑 ABSTRACT.md — 论文摘要
# 4. 编辑 REFINED_DESIGN.md — 实证设计 (DID/IV/RDD)
# 5. 编辑 PAPER_OUTLINE.md — 论文大纲
```

---

## 📋 模板文件说明

| 文件 | 用途 | 何时填 |
|---|---|---|
| `IDEA_REPORT.md` | 想法报告（问题、贡献、数据）| Stage 1 |
| `ABSTRACT.md` | 论文摘要（200-300 字）| Stage 6 |
| `REFINED_DESIGN.md` | 实证设计（变量、模型、稳健性）| Stage 4 |
| `PAPER_OUTLINE.md` | 论文大纲（章节结构）| Stage 6 |
| `LIT_REVIEW.md` | 文献综述（可选）| Stage 2 |
| `figures/` | 图表输出目录 | Stage 5+6 |
| `tables/` | 表格输出目录 | Stage 5+6 |

---

## 🎯 模板里每个文件该写什么

### IDEA_REPORT.md

```markdown
# [研究主题]

## 研究问题
- 一句话描述要回答什么问题

## 学术贡献
- 与现有 3-5 篇顶刊文献的区别

## 数据可得性
- A 股 / 美股 / 宏观 / 学术论文来源

## 方法论选择
- DID / IV / RDD / 合成控制 / 面板 GMM
```

### ABSTRACT.md

```markdown
We examine [research question] using [data] from [source]. 
Our identification strategy exploits [shock/policy/instrument]. 
We find that [main finding], with [magnitude and significance]. 
[Contribution]. [Implication].
```

### REFINED_DESIGN.md

```markdown
## 样本
- N firms × T years
- 时间区间
- 入选筛选

## 变量定义
- 因变量: ...
- 核心自变量: ...
- 控制变量: ...

## 识别策略
- DID with [固定效应]
- 工具变量: [IV]
- 稳健性: [list]

## 已知局限
- 样本量限制
- 内生性威胁
```

### PAPER_OUTLINE.md

```markdown
# 论文大纲

## 1. 引言
## 2. 文献综述
## 3. 制度背景 / 数据
## 4. 实证策略
## 5. 主结果
## 6. 稳健性
## 7. 机制 (可选)
## 8. 结论
```

---

## 📚 配套数据与脚本

完整流程从想法到 LaTeX 论文，请使用：

```bash
# 启动完整 pipeline (8 阶段)
python scripts/agent_pipeline.py --topic "[你的研究主题]"

# 或单独跑某阶段
python scripts/research_framework/pipeline.py --idea-file examples/my-research/IDEA_REPORT.md
```

更多参见 `使用指南.md` (1048 行详细手册)。