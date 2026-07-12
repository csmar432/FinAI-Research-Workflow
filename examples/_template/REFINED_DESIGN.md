# Refined Research Design — [TITLE]

> **阶段**: Stage 4 (empirical design before data acquisition)
> **识别策略**: [DID / IV / RDD / Synthetic Control / Panel GMM]
> **样本**: [N firms × T years]

---

## 1. 样本 (Sample)

### 1.1 入选筛选

| 步骤 | 筛选条件 | 预期剔除 |
|---|---|---|
| 1 | [Initial universe] | 100% |
| 2 | [Filter 1: e.g. 上市状态] | -X% |
| 3 | [Filter 2: e.g. 财务数据可得] | -Y% |
| 4 | [Outlier winsorize 1%/99%] | <1% |
| **最终** | — | ~[N] firm-years |

### 1.2 时间窗口

- 起始: [YYYY, e.g. 2015]
- 结束: [YYYY, e.g. 2024]
- **T_post = [N]** ← 必须 ≥ 5 (Roth & Sant'Anna 2023)
- 若 T_post < 5: 必须声明短面板 bias + 标注 illustrative

---

## 2. 变量定义 (Variables)

### 2.1 因变量 (Y)

| 变量名 | 定义 | 数据源 | 单位 |
|---|---|---|---|
| Y1 | [Definition] | [source] | [unit] |
| Y2 | [Definition] | [source] | [unit] |

### 2.2 核心自变量 (Treatment)

| 变量名 | 定义 | 类型 | 构造方法 |
|---|---|---|---|
| D | [Treatment] | Binary / Continuous / Multivalued | [Method] |
| Post | [Post-period indicator] | Binary | 1 if year ≥ [YYYY] |

### 2.3 控制变量 (X)

| 变量名 | 定义 | 数据源 | 预期符号 |
|---|---|---|---|
| X1 | [Definition] | [source] | + / - |
| X2 | [Definition] | [source] | + / - |

---

## 3. 识别策略 (Identification)

### 3.1 主回归

$$
Y_{it} = \alpha + \beta \cdot D_i \times \text{Post}_t + \gamma X_{it} + \mu_i + \lambda_t + \epsilon_{it}
$$

- $\beta$ 为目标系数 (DID estimator)
- 标准误: 在 [unit level] 聚类
- 固定效应: firm + year

### 3.2 平行趋势检验

- 事件研究图: pre-period coefficients should be near zero
- F-test for joint significance of pre-period interactions

### 3.3 内生性处理

- **反向因果**: [e.g. 用 IV, IV = ...]
- **遗漏变量**: [e.g. 加入更多 controls, 高维 FE]
- **测量误差**: [e.g. alternative Y definition]

---

## 4. 稳健性检验 (Robustness, 至少 5 项)

| # | 检验 | 目的 |
|---|---|---|
| 1 | 平行趋势图 + F-test | pre-trend validity |
| 2 | Bacon decomposition | TWFE bias |
| 3 | Alternative cluster level | SE robustness |
| 4 | Winsorize at 5%/95% | extreme values |
| 5 | Placebo test (fake shock) | spurious correlation |
| 6 | Alternative Y | measurement error |
| 7 | Subsample by [X] | heterogeneity |

---

## 5. 异质性分析 (Heterogeneity)

| 维度 | 预期差异 |
|---|---|
| [Industry] | High-X firms respond more |
| [Size] | Small firms respond more |

---

## 6. 机制检验 (Mechanism, 可选)

**重要**: 机制变量必须是真实来源 (IBES / TRACE / S&P)，**不可**用真实变量线性函数构造。
若使用 proxy，必须标注 "heuristic, NOT for publication" 并在论文中说明。

---

## 7. 已知局限 (Limitations)

- [Limitation 1: e.g. T_post < 5]
- [Limitation 2: e.g. 仅 14 firms × 7 years]
- [Limitation 3: e.g. ESG 评级来源争议]

---

## 8. 数据获取清单 (Data Acquisition Checklist)

- [ ] A 股财务 (Tushare Pro, 需 token)
- [ ] 美股财务 (yfinance, 免费)
- [ ] 宏观指标 (FRED / World Bank / IMF)
- [ ] ESG 评级 (MSCI / Sustainalytics, 商业数据库)
- [ ] 学术文献 (OpenAlex / Semantic Scholar, 免费)
- [ ] Patent (CN SIPO / USPTO, 可选)