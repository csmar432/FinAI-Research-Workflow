# FinResearch Agent 文档

> 经济金融领域 AI 学术研究工作流 — 从研究想法到可投稿论文。

## 快速链接

| 文档 | 说明 |
|------|------|
| [快速入门](01-quickstart.md) | 5 分钟配置并运行第一个研究流程 |
| [使用指南](../../USAGE_GUIDE.md) | 完整使用说明 |
| [MCP 市场](04-mcp-marketplace.md) | 43 个数据服务器的安装与使用 |
| [API 参考](../api_reference.md) | Python API 文档 |

## 核心能力

- **43 个 MCP 数据服务器** — A股 / 宏观 / 美股 / 学术 / ESG / 加密货币，无需 API Key
- **49 种计量方法** — DID / IV / RDD / 合成控制 / Panel GMM，顶刊标准
- **17 个 Skills** — 从文献综述到论文投稿完整覆盖
- **41 个期刊模板** — JF / JFE / RFS / 经济研究 / 金融研究等

## 目录结构

```
论文-研报工作流/
├── scripts/
│   ├── core/              # Agent 核心模块
│   └── research_framework/  # 计量方法实现
├── mcp_servers/           # 43 个 MCP 数据服务器
├── .cursor/skills/        # 17 个自动化 Skills
├── docs/                  # 本文档
├── data/                  # 数据文件
└── tests/                 # 测试套件
```
