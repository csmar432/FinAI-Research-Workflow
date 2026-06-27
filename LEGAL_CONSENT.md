# LEGAL_CONSENT.md — 学术研究 MCP 服务器法律风险说明

> **生效日期**: 2026-06-28
> **适用范围**: `user-cnki` / `user-wanfang` / `user-chinese-literature` 三个 MCP 服务器

## 1. 概述

本项目默认提供 28 个**完全免费、无 API Key、无法律风险**的 MCP 数据源（详见 [README.md](README.md) MCP 数据源章节）。本项目**可选**集成 3 个**涉及学术网站爬取**的 MCP 服务器，**默认禁用**，需要用户明确 opt-in。

| 服务器 | 状态 | 数据源 | 主要法律风险 |
|---|---|---|---|
| `user-cnki` | opt-in | CNKI scholar.cnki.net | robots.txt 禁止爬取 |
| `user-wanfang` | opt-in | 万方数据 wanfangdata.com.cn | robots.txt 禁止爬取 |
| `user-chinese-literature` | opt-in | 百度学术（部分）、OpenAlex、Crossref | 百度学术可能违反 ToS |

## 2. 为什么 opt-in?

CNKI、万方、百度学术等中国学术平台的 `robots.txt` 明确禁止自动化爬虫。CNKI 2023 年发布声明禁止第三方爬取。本项目为学术研究便利提供 MCP 集成，但**不在用户默认配置中启用**——必须由用户**明确同意**法律风险后单独启用。

## 3. opt-in 方式

### 3.1 临时启用（推荐）

```bash
export CLI_ACCEPT_RISK="cnki,wanfang,chinese-literature"
python scripts/agent_pipeline.py --topic "..."
```

### 3.2 持久启用

写入 `~/.bashrc` 或 `.env.local`：

```bash
CLI_ACCEPT_RISK=cnki,wanfang,chinese-literature
```

### 3.3 单独启用（精细控制）

```bash
# 只启用 CNKI
export CLI_ACCEPT_RISK="cnki"

# 启用 CNKI + 万方（不含 chinese-literature）
export CLI_ACCEPT_RISK="cnki,wanfang"
```

## 4. 法律条款

您启用上述服务器**即表示同意**以下条款：

1. **使用责任**：您有责任确保使用方式符合所有适用法律（著作权法、计算机信息系统安全保护条例等）及数据源平台的服务条款（ToS）。
2. **非商业使用**：建议仅用于学术研究、教育、个人学习；商业使用需获得数据源平台授权。
3. **频率控制**：默认请求间隔 ≥2 秒；高频访问可能触发平台风控（IP 封禁、验证码、账号封停等）。
4. **数据版权**：下载的论文版权归原作者及出版商所有；引用须遵守学术规范（合理使用 + 引用标注）；批量下载可能违反著作权法。
5. **机构账号**：建议通过机构订阅 CNKI/万方账号获取合法访问权限；MCP 服务器仅作为补充工具。
6. **robots.txt**：本服务器**尽可能**遵守 robots.txt，但遵守 robots.txt 不构成爬取的法律授权。
7. **免责**：本项目作者及维护者对使用 opt-in 服务器产生的任何法律后果（民事/刑事/学术处分）**不承担任何责任**。风险由用户自行承担。

## 5. 学术合理使用指南

参考 [SSRN 使用条款](https://hq.ssrn.com/abstract=3758848) 及多所大学图书馆指南：

- ✅ 允许：单篇下载、引用标注、综述分析
- ✅ 允许：批量下载用于系统综述、文献计量分析（**仅学术研究用途**）
- ❌ 禁止：未授权的商业再分发
- ❌ 禁止：完整数据库镜像

## 6. 风险监测

- 2026-06-28 审计：本声明已就位
- 历史投诉：0 起（项目自 2024 年 11 月发布）
- 学术机构使用：5+ 所（详见 [使用指南.md](使用指南.md)）

## 7. 推荐替代

对于**不需** CNKI/万方独有文献的研究，推荐使用：

- **OpenAlex** (`user-openalex`) — 2 亿+ 学术论文，**完全免费 + 完全合法**
- **Semantic Scholar** (`user-semantic-scholar`) — API 免费层足够大多数研究
- **ArXiv** (`user-arxiv`) — 预印本全文
- **NBER** (`user-nber-wp`) — NBER 工作论文
- **Crossref** (`user-context7` 包含) — DOI 元数据

大多数现代学术研究可由这 4 个免费服务器完成，无需启用 opt-in 风险服务器。

---

**最后更新**: 2026-06-28 | **下次审查**: 2026-09-30
**维护者**: csmar432 | **问题反馈**: GitHub Issues