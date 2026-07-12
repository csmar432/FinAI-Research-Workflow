# 文档审计 + 手动任务清单 (audit_fix_2026_07_12)

> **审计者**: FinResearch Agent
> **时间**: 2026-07-12 13:00 (UTC+8)
> **范围**: `docs/` 全部 51 个文档 + `MANUAL_TASKS.md` (root) + `docs/archive/` + `pyproject.toml` 引用

---

## A. 仍然需要手动完成的事项 (5 大类, ~3 小时)

### 🟡 A1. 录制 Demo GIF (30 min)

**来源**: `docs/DEMO_GIF_README.md` (117 行, **执行人: 待用户授权**)
**现状**: 仅有 SVG 终端动画 (`docs/assets/demo-terminal.svg`, 4.4KB) 和静态 PNG (`docs/assets/quickstart.png`).
**待做**:
- 选择 A/B/C 方案之一 (asciinema+agg / Kap / svg-term+gifski)
- 录制 ≤ 15 秒 demo, 主题示例: `python scripts/start_research.py --topic "carbon trading innovation" --stage idea-discovery`
- 输出 `docs/assets/demo.gif`, ≤ 2 MB, ≤ 800 px 宽, 15-20 fps
- 嵌入 README 顶部

**阻塞原因**: 需用户授权选方案 + GUI 录制 (Kap 需 macOS, asciinema/gifski 可脚本化).

---

### 🟡 A2. 上传 GitHub Social Preview (5 min)

**来源**: `MANUAL_TASKS.md` 任务 4 + `docs/DEMO_GIF_README.md` 提及
**现状**: 图片已生成 (`.github/social-preview.png` 1280×640, 64KB), 但 GitHub API 限制无法直接上传.
**待做**:
- 进入 https://github.com/csmar432/finai-research/settings
- 滚到 "Social preview" → 上传 `.github/social-preview.png` (1280×640)

**阻塞原因**: GitHub UI 操作, 无 API 等价物.

---

### 🟡 A3. 发社媒/社区 PR (2 小时, 9 项)

**来源**: `docs/manual/social_media/README.md` + `MANUAL_TASKS.md` 任务 6-8

#### A3.1. 7 个 awesome-list PR (90 min)

**已自动 (4/7)**: PR-02 ~ PR-05 已 DRAFT, 需用户 web 提交
**已撤回 (1/7)**: PR-06 (wong2/awesome-mcp) — 仓库禁 PR
**待办 (2/7)**:

| # | 文件 | 状态 | 操作 |
|---|---|---|---|
| 1 | `PR-01-antontarasenko-awesome-economics.md` | WITHDRAWN (仓库禁 PR) | 跳过 |
| 2 | `PR-02-matteocourthoud-awesome-causal-inference.md` | DRAFT | 用户提交 |
| 3 | `PR-03-wilsonfreitas-awesome-quant.md` | DRAFT | 用户提交 |
| 4 | `PR-04-academic-awesome-datascience.md` | DRAFT | 用户提交 |
| 5 | `PR-05-emptymalei-awesome-research.md` | DRAFT | 用户提交 |
| 6 | `PR-06-WITHDRAWN-wong2-awesome-mcp-servers.md` | WITHDRAWN | 跳过 |
| 7 | `PR-07-DEFERRED-vinta-awesome-python.md` | DEFERRED (排名靠后) | 延后 |

**修正建议**: `MANUAL_TASKS_RUNBOOK.md` §3 仍写 "发 awesome list PR (×7)" — 已过时, 实际是 **2 已撤回 + 4 DRAFT + 1 DEFERRED = 4 真待办**.

#### A3.2. HN + Reddit (3 个 subreddit) (30 min)

**文件**: `01-hackernews.md`, `02-reddit-machinelearning.md`, `03-reddit-python.md`
**待做**: 复制粘贴已备好的文案到 HN/Reddit web 表单
**阻塞原因**: 需账号登录 + 防 spam (建议先合并 PR 再发)

#### A3.3. 中文社媒 (3 项, 40 min)

**文件**: `04-zhihu.md`, `05-weibo.md`, `06-x-com.md`
**待做**: 知乎专栏文章 (编辑器不完美支持 MD, 需手动调整), 微博短文, X.com 推文
**阻塞原因**: 账号登录 + 中文平台编辑器

---

### 🟢 A4. PyPI 发布 (5 min, 待 token)

**来源**: `MANUAL_TASKS.md` 任务 9 + `docs/manual/RELEASE_NOTES_v0.2.0-alpha2.md` DRAFT
**现状**: 包已构建 (`pyproject.toml version = "0.2.0-alpha"`), 需 PyPI token.
**待做**: `pip install twine && twine upload dist/*` (需用户提供 token)
**Release Notes 状态**: DRAFT — 需 maintainer 签字 (注: 文件 0 引用, 也可考虑放 CHANGELOG.md)

---

### 🟢 A5. mcpservers.org 收录 (10 min)

**来源**: `MANUAL_TASKS.md` 任务 3 + `social_media/README.md` 任务 3
**待做**: web form 提交 + 邮件验证 (无 API 等价物)

---

## B. 文档清理清单 (11 项, 按优先级)

### 🔴 B1. 应删除的过时/无用文档 (6 项)

| # | 文件 | 行数 | 理由 |
|---|---|---|---|
| 1 | `docs/tutorials/TUTORIALS_README.md` | 30 | **完全重复** `docs/tutorials/README.md` (Jun 4 vs Jul 9), 旧版本被新 README 完整替代 |
| 2 | `docs/MANUAL_TASKS_RUNBOOK.md` | 564 | **过时**: 仍写 2026-06-16 的 PR/任务, 实际**全部已自动完成或已在 root `MANUAL_TASKS.md` 更新**. 文档 L2 "合并 PR" 提及 commit `0480ce6` 已合并, 但任务清单 (HN/Reddit/awesome-list) 仍用旧版本, 用户已转移到 root 文件 |
| 3 | `docs/archive/scripts-deprecated/research_workflow.py` | ~1200 | **完全无用**: 顶部明确标 "DEPRECATED", 0 引用, 已被 `agent_pipeline.py` 完全替代. 在 `docs/archive/` 无人引用 |
| 4 | `docs/archive/scripts-deprecated/research_workflow_v2.py` | ~1200 | 同上, v1 vs v2 内容近乎相同 (diff 头部 30 行完全相同). 保留 1 个即可 (建议保留 v2) |
| 5 | `docs/archive/scripts-deprecated/__init__.py` | 0 | **空文件**, 无作用 |
| 6 | `docs/audit/audit-2026-06-27.md` | 245 | **过时**: 6 月 27 日试运行问题清单, 已被 `audit-2026-07-04.md` + 多次修复迭代超越. 0 引用 |

### 🟡 B2. 应大幅更新的过时文档 (5 项)

| # | 文件 | 问题 | 修复 |
|---|---|---|---|
| 1 | `docs/api_reference.md` | (a) 头部日期 2026-06-28, 仍在 P1-5 修正前; (b) `TripleDiffDID` 类名错, 实际是 `TripleDiffDIDEngine`; (c) 表格引用 49 期刊模板 (CLAUDE.md 是 30) | 重写 §0 角色澄清, 修正类名, 统一计数 |
| 2 | `docs/ARCHITECTURE.md` | 引用 `scripts/orchestrator.py` + `scripts/multi_agent.py`, **两个文件都不存在**. 实际入口是 `agent.py` / `agent_pipeline.py`. 头部 "Last Updated: 2026-06-20" | 重命名 `orchestrator.py` → `agent.py` / `agent_pipeline.py`, 更新图示 |
| 3 | `docs/CITATION_GUIDE.md` | (a) `version 0.1.0` 应为 `0.2.0-alpha`; (b) `doi 10.5281/zenodo.PENDING` 仍占位; (c) `44 MCP / 42 methods / 44 期刊模板` 数字过时 (实际 43 / 47 / 30) | 一次性重写 4 个引用块 |
| 4 | `docs/index.md` | (a) 数字 "42 方法"过时; (b) 链接 `github.com/YOUR_USERNAME/finai-research-workflow` 是占位符, 实际是 `csmar432/finai-research` | 更新数字 + 链接 |
| 5 | `docs/audit-workflow.md` | "8 critical claims" 已过时 (实际 17 checks). 但作为 **方法论** 文档仍有用 | 更新数字, 加 "audit 演进时间线" 小节 |

### 🟢 B3. 小修 (2 项)

| # | 文件 | 问题 | 修复 |
|---|---|---|---|
| 1 | `pyproject.toml` L285 / L309 | 引用 `docs/TASKS_RUNBOOK.md`, **文件不存在**. 实际文件是 `docs/MANUAL_TASKS_RUNBOOK.md` (并且要删除) | 改成 `MANUAL_TASKS.md` (root) 或删除该注释 |
| 2 | `docs/mkdocs.yml` L65 / L80 | 引用 `../使用指南.md` (root, gitignored) 和 `论文写作工作流使用指南.md` (实际不存在) | 改用 `index.md` 或删除导航条目 |

---

## C. 仍然有用但需小更新的文档 (4 项)

| 文件 | 状态 |
|---|---|
| `docs/IMPROVEMENT_ROADMAP.md` | ✅ 已本轮更新 (commit `9779cf9`) |
| `docs/MCP_SERVER_TIERING.md` | ✅ 当前, 数字一致 (43 MCP), 保留 |
| `docs/MOCK_DATA_POLICY.md` | ✅ 当前 (2026-06-28), 仍为 5 个 MCP 风险列表, 保留 |
| `docs/external_data_sources.md` | ✅ 578 行数据源指南, 实用 |
| `docs/audit-workflow.md` | 🟡 需更新 "8 → 17 checks" 但方法论核心不变 |
| `docs/DOCKER_INSTALL.md` | ✅ 当前, 5 Dockerfile + start_all.sh 引用都真实存在 |
| `docs/DISCUSSION_TEMPLATES.md` | ✅ 已启用, 保留 |
| `docs/adr/ADR-{001,002,003}-*.md` + `ADR_INDEX.md` | ✅ 决策记录, 保留 (注: ADR_INDEX 自身过时, 6 月未更新, 但 ADR 内容仍准确) |
| `docs/audit/P2-2-EVALUATION-2026-07-12.md` | ✅ 本轮新建, 1 引用 |
| `docs/audit/audit-2026-07-04.md` | ✅ 2 引用 (CLAUDE.md), 保留 |
| `docs/audit/GITHUB_STAR_AUDIT_2026-07-09.md` | ✅ 3 引用 (MCP_TIERING, DEMO_GIF, DISCUSSION_TEMPLATES), 保留 |
| `docs/audit/BIB_DOI_AUDIT.md` / `OPENSSF_AUDIT.md` / `RELATED_STARS_AUDIT.md` | ✅ 历史审计, 保留 |
| `docs/audit/REJECTED_ITEMS_2026-06-27.md` | ✅ 27 项 P0-P2 拒绝清单, 0 引用但作历史记录有用 |
| `docs/blog/BLOG_OUTLINES.md` | ✅ 5 篇博客大纲, 占位 (博客本身未写) |
| `docs/manual/awesome_list_prs/*.md` (×7) | ✅ PR 草稿, 5 真待办 (DRAFT) |
| `docs/manual/social_media/*.md` (×6) | ✅ 6 平台提交包, 4 真待办 (HN/Reddit/知乎/X.com) |
| `docs/tutorials/{01..05}*.md` + `README.md` | ✅ 当前 |

---

## D. 决策建议

### 🟢 **建议立即执行 (本期)**

1. **删除 B1 的 6 个过时文档** (清理死代码, ~5 min):
   ```
   docs/tutorials/TUTORIALS_README.md
   docs/MANUAL_TASKS_RUNBOOK.md
   docs/archive/scripts-deprecated/research_workflow.py
   docs/archive/scripts-deprecated/research_workflow_v2.py
   docs/archive/scripts-deprecated/__init__.py
   docs/audit/audit-2026-06-27.md
   ```

2. **更新 pyproject.toml 注释** (引用不存在的文件, ~2 min)

3. **更新 mkdocs.yml 导航** (移除 `../使用指南.md` 链接, ~2 min)

### 🟡 **建议下一轮 (本周末)**

4. **重写 `docs/api_reference.md`** (§0 + 类名修正 + 数字统一, ~30 min)
5. **重写 `docs/ARCHITECTURE.md`** (改名 orchestrator → agent_pipeline, ~30 min)
6. **修正 `docs/CITATION_GUIDE.md`** 数字 + DOI 占位符 (~15 min)
7. **修正 `docs/index.md`** 占位符链接 + 数字 (~5 min)
8. **更新 `docs/audit-workflow.md`** "8 → 17 checks" (~5 min)

### 🟢 **可选 (用户自行决定)**

9. Demo GIF 录制 (A1)
10. Social Preview 上传 (A2)
11. awesome-list PR 提交 (A3.1, 4 真待办)
12. HN/Reddit/知乎 (A3.2 + A3.3)

---

## E. 总结数字

| 类别 | 数量 | 时长 |
|---|---|---|
| 🔴 真待办手动任务 | 5 大类 / 9 小项 | ~3 小时 |
| 🔴 应删除过时文档 | 6 文件 | 5 min |
| 🟡 应重写过时文档 | 5 文件 | ~1.5 小时 |
| 🟢 应小修 | 2 文件 | 5 min |
| 🟢 仍有用 | 30+ 文件 | — |
| 📊 docs/ 总文件数 | 51 | — |

---

## F. 请示

1. **B1 删除清单是否执行?** (我建议: 是, 6 文件全删)
2. **B2 重写 5 文件是否本轮做?** (我建议: 是, 1.5h)
3. **A 类手动任务 (社媒/Demo/PyPI) 是否需要我协助准备更多内容?** (我建议: 不需要, 文案已就绪, 用户手动)
4. **`docs/archive/` 是否整目录删除?** (我建议: 是, 全部 0 引用, 留作 git history)

---

**报告完整**: `docs/audit/DOCS-AUDIT-2026-07-12.md` (本次输出)