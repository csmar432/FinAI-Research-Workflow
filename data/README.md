# data/ 目录说明

> 所有外部数据文件统一放入 `data/` 目录。系统会从此目录读取用户提供的文件。

---

## 目录结构

```
data/                          ← 外部数据唯一入口
├── README.md                  ← 本说明文件
├── finance/                   ← 【常用】金融数据
│   ├── stock_financials/      │   A股财务（利润表/资产负债表/现金流量表）
│   │   └── .gitkeep
│   ├── market_data/           │   行情数据（日频/月频）
│   │   └── .gitkeep
│   ├── fund_data/             │   基金数据
│   │   └── .gitkeep
│   └── bond_data/             │   债券数据
│       └── .gitkeep
├── customs/                   ← 【关税研究必备】海关进出口
│   ├── company_import.csv      │   企业进口明细（HS编码、金额）
│   ├── company_export.csv      │   企业出口明细（HS编码、金额）
│   └── .gitkeep
├── esg/                      ← ESG评级数据
│   └── .gitkeep
├── macro/                    ← 宏观数据
│   ├── national_province_data_2026.json  # 全国各省科技创新面板
│   └── .gitkeep
├── policy/                   ← 政策实验数据
│   ├── tariff_events.csv     │   关税政策事件（2018年中美贸易战）
│   ├── policy_qualtrics.csv
│   └── .gitkeep
├── alternative_data/          ← 另类数据
│   ├── satellite/             │   卫星图像数据
│   ├── news_sentiment/       │   新闻情绪数据
│   ├── patent_data/          │   专利数据
│   └── .gitkeep
├── user_uploaded/            ← 用户临时上传（不提交git）
│   └── .gitkeep
└── processed/               ← 【自动生成】清洗后的中间数据
    └── .gitkeep
```

---

## 快速上手

### 方式一：放置Excel/CSV文件

将文件放入对应子目录后，在 `FIN_BRIEF.md` 中注明：

```markdown
## 数据来源

| 数据类型 | 文件路径 | 来源 | 字段说明 |
|---------|---------|------|---------|
| A股财务 | data/finance/stock_financials/annual.csv | CSMAR | 资产负债率、ROA |
| 海关出口 | data/customs/company_export.csv | 海关总署 | HS编码、出口额 |
```

### 方式二：让AI Agent自动读取

在 Cursor 中描述数据路径：
```
"我的A股财务数据在 data/finance/stock_financials/annual.csv，帮我用这个数据跑DID回归"
```

### 方式三：MCP自动拉取（无需手动提供）

配置API Key后自动获取：
- **A股数据**：`user-tushare`（需 TUSHARE_TOKEN，https://tushare.pro/register）
- **宏观数据**：`user-financial`（无需Key）
- **美股数据**：`user-yfinance`（无需Key）

---

## 文件命名规范

| 类型 | 命名格式 | 示例 |
|------|---------|------|
| 面板数据 | `{topic}_{freq}_{year_range}.csv` | `a_share_annual_2010_2024.csv` |
| 事件数据 | `{event}_{date}.csv` | `tariff_2018_07.csv` |
| 评级数据 | `{provider}_{type}_{year}.csv` | `msci_esg_2024.csv` |
| 宏观数据 | `{region}_{indicator}_{year_range}.xlsx` | `china_province_gdp_2010_2023.xlsx` |

---

## 当前已有文件

| 文件 | 说明 | 来源 |
|------|------|------|
| `national_province_data_2026.json` | 全国各省科技创新面板数据 | 马克数据网（macrodur.cn）|
| `policy_experiments/policy_database.json` | 政策实验数据库 | — |
| `test_templates/` | 期刊 LaTeX 模板样例（管理世界/经济研究/金融研究）| — |
| `charts/` | 图表输出目录 | — |
| `finance/` | 金融数据目录占位 | — |

> 注：`msci_esg_ratings.json` 和 `national_province_data_2026.xlsx` 已在 git 中删除，如需请重新下载。

---

## 数据来源推荐

### A股上市公司数据

| 来源 | 覆盖 | 成本 |
|------|------|------|
| **Tushare Pro** | 行情、财务、融资融券、龙虎榜 | 免费/付费 |
| **CSMAR** | 最全，国泰安 | 学校授权 |
| **Wind** | 最全，机构版 | 商业授权 |
| **akshare** | 部分数据免费 | 免费 |

### 海关进出口数据

| 来源 | 说明 |
|------|------|
| **CSMAR海关数据库** | 含上市公司HS编码、进出口金额（学校授权）|
| **海关总署官网** | 宏观层面，需手动汇总 |
| **中国统计年鉴** | 省级层面 |

### ESG评级数据

| 来源 | 说明 |
|------|------|
| **MSCI官网** | 需账号 |
| **华证指数** | 免费部分可用 |
| **商道融绿** | 国内ESG数据 |
| **中证ESG** | 需账号 |

---

## 禁止事项

- ❌ 不要将数据文件放入 `scripts/` 或 `mcp_servers/` 目录
- ❌ 不要在 `output/` 目录存放原始数据（output 是输出目录）
- ❌ 不要提交超过 10MB 的数据文件到 git（使用 `.gitignore`）
- ❌ 敏感数据（身份证、账户信息）禁止放入项目目录

---

## Git忽略配置

`data/` 目录已在项目级 `.gitignore` 中配置：

```
# 数据目录（不提交git）
data/
# 但保留以下文件
!data/README.md
!data/.gitkeep
```

如需提交大型数据文件，使用 Git LFS：
```bash
git lfs track "data/**/*.xlsx"
git lfs track "data/**/*.csv"
```
