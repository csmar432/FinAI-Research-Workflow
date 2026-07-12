# Data Sample Fixtures (data/sample/)

> **目的**: 让用户在没有外部数据源 (Tushare Pro / IBES / TRACE) 的情况下，
> 也能跑通 paper pipeline 的核心测试。所有数据是 **synthetic** (numpy RNG, seed=42)，
> 不代表任何真实公司或专利。

---

## 📁 文件清单

| 文件 | 行数 / 大小 | 内容 | 用法 |
|---|---|---|---|
| `esg_panel_demo.csv` | 250 obs | 50 firms × 5 years (2018-2022), ESG treated vs control, DID setup | `ModernDiDEngine`, `RegressionEngine` |
| `did_synthetic_panel.csv` | 300 obs | 30 firms × 10 years (2010-2019), staggered treatment | CS / Sun-Abraham / BJS estimators |
| `references_demo.bib` | 5 entries | 5 篇顶刊 DID 方法论文献 (Callaway, Sun-Abraham, BJS, Abadie, Roth-Sant'Anna) | BibTeX compilation |

---

## 🔄 Reproducibility

所有数据由 `numpy.random.default_rng(seed=42)` 生成，可完全复现。

```python
import pandas as pd
df = pd.read_csv("data/sample/esg_panel_demo.csv")
print(df.head())
#   firm_id ticker  year esg_tier  esg_high  post  did       lev  ltd_ratio  cost_debt  ln_assets       roa  tangibility        mb  cash_ratio
# 0  F000  TEST000  2018     low         0     0    0  0.4123     0.2541     0.0512     7.892  0.0512       0.3012  1.5234      0.1456
# ...
```

---

## ⚠️ Disclaimer

**These are SYNTHETIC fixtures for testing only. Do NOT use for empirical analysis.**

For real research:
- A-share financial: `user-tushare` (TUSHARE_TOKEN required)
- US equity: `user-yfinance` (free)
- ESG ratings: MSCI / Sustainalytics (commercial)
- Macro: `user-financial` / `user-fed-data` / `user-wb-data` (free)

See `docs/external_data_sources.md` (26891 bytes) for full data source guide.