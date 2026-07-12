# Research Idea Report — [TITLE]

> **状态**: ⬜ Draft / ⬜ Review / ⬜ Approved
> **作者**: [Your Name]
> **日期**: [YYYY-MM-DD]
> **目标期刊**: [Journal Name, e.g. JFE / 经济研究 / RFS]

---

## 1. 研究问题 (Research Question)

**一句话核心问题**:
[Describe the central question in one sentence]

**子问题**:
1. [Sub-question 1]
2. [Sub-question 2]
3. [Sub-question 3]

---

## 2. 学术贡献 (Contribution)

### 2.1 与现有文献的区别

| 维度 | 现有文献 (3-5 篇) | 本研究 |
|---|---|---|
| 数据 | [Sample X] | [Sample Y] |
| 方法 | [Method Z] | [Method W] |
| 时期 | [Period A] | [Period B] |
| 地理 | [Country] | [Country] |

### 2.2 主要贡献

1. **理论贡献**: ...
2. **方法贡献**: ...
3. **政策贡献**: ...

---

## 3. 数据可得性 (Data Availability)

### 3.1 主要数据源

| 数据 | 来源 | 期间 | 变量 |
|---|---|---|---|
| [Name] | [MCP server] | [YYYY-YYYY] | [var list] |

### 3.2 关键 MCP 调用

```
server: user-yfinance
tool: get_yf_financials
params: { "ticker": "...", "statement_type": "balance" }
```

### 3.3 已知限制

- 样本量: ~[N] firm-years
- 时间窗口: [T_post] post-period years (note if T_post < 5)
- 数据可获得性: [rating: High/Medium/Low]

---

## 4. 方法论选择 (Methodology)

**主回归**: [DID / IV / RDD / Synthetic Control / Panel GMM]

**理由**:
[Why this method, 1-2 sentences]

**辅助方法**:
- 平行趋势: [Yes/No]
- 稳健性检验: [List]
- 异质性分析: [By X / Y / Z]

---

## 5. 预期产出 (Expected Output)

- 论文: ~25 pages LaTeX, 30-50 references
- 表格: ~5 (descriptive / baseline / robustness / heterogeneity / mechanism)
- 图表: ~5 figures
- 估计运行时间: ~[N] minutes

---

## 6. 风险评估 (Risk)

| 风险 | 严重度 | 缓解措施 |
|---|---|---|
| [Risk 1] | 高/中/低 | [Mitigation] |
| [Risk 2] | 高/中/低 | [Mitigation] |

---

## 7. 决策点 (Decision Points)

- [ ] 与导师讨论后最终确认 idea
- [ ] 数据预跑通
- [ ] 识别策略明确 (特别是 T_post 限制)