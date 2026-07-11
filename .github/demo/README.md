# Demo Assets

This directory contains visual assets for the project README and documentation.

## 🎬 Quick Demo GIFs (用于 README Quick Start)

| Demo | File | Size | Frames | Duration | 内容 |
|------|------|------|--------|----------|------|
| **v1** | `demo.gif` | 860×608, 60 KB | 30 | 6.0 s | 仅 `python3 scripts/cli.py health` |
| **v1 source** | `demo.cast` | asciicast v2, 2.1 KB | – | – | asciinema 终端录制源 |
| **v1 backup** | `demo_v1_health.gif` | (与 demo.gif 相同) | – | – | – |
| **v1 backup** | `demo_v1_health.cast` | (与 demo.cast 相同) | – | – | – |
| **v3 (推荐)** | `demo_full_pipeline.gif` | 900×224, 283 KB | 24 | 34 s | **8 阶段完整研究流水线** |

### v3 Demo 内容（demo_full_pipeline.gif）

完整呈现 8 阶段经济金融研究流程（覆盖 CLAUDE.md 8-stage pipeline）：

| Stage | 标题 | 演示内容 |
|-------|------|---------|
| 0 | 健康检查 | `python3 scripts/cli.py health` 7 项检查 |
| 0.5 | 资产盘点 | `python3 scripts/count_assets.py --markdown` 43 MCP / 47 methods / 30 journals |
| 1 | 想法生成 | `lit-review --topic "carbon trading and green innovation"` |
| 2 | 文献综述 | `literature_download.py --query ... --limit 5` |
| 3 | 新颖性验证 | `novelty_check.py --topic ...` |
| 4 | 实证设计 | DID 设计 (ESG × Post, 14 firms × 3 yrs) |
| 5 | 数据获取 | yfinance MCP 14 个能源企业 × 2022–2024 |
| 6 | 实证估计 | DID 表格（Coef / SE / t-stat / p-value）|
| 7 | 论文写作 | LaTeX 文件 + papers/us_esg_financing/ |
| 8 | Review + Audit | audit_guard 16/16 ✓ |

**中文支持**：使用 macOS STHeiti Medium / Hiragino Sans GB 字体，完美渲染中文
（"经济金融领域 AI 学术研究工作流"、"研究想法生成"、"异质性分析" 等）。

### 重新生成 Demo

```bash
# 1. 跑完整 8 阶段 demo session 并捕获到文件
bash scripts/demo/record_full_pipeline_v3.sh > /tmp/demo_raw.txt 2>&1

# 2. 渲染成 GIF（默认 900×224, 24 frames × 1.4s）
python scripts/demo/render_demo_gif_v3.py \
    /tmp/demo_raw.txt \
    .github/demo/demo_full_pipeline.gif \
    900 0.7 24

# 自定义参数:
#   width=1200  → 更大视图
#   fps=1.0     → 每帧 1s（更快）
#   frames=48   → 更多帧（更细致滚动）
```

### 关于 v2 demo (deprecated)

`.github/demo/demo_v1_health.*` 是 **v1** 的备份；之前的 `demo_full_pipeline.gif`
第一版（800×600, 5 帧）已被替换为 **v3**（900×224, 24 帧，覆盖完整 8 阶段）。

---

## 🏛 5 张互补架构图 (5 Complementary Diagrams)

| # | 文件 | 一句话 | 视角 |
|---|---|---|---|
| 1 | `01-architecture-overview.svg/png` | 5 层端到端架构 (用户→接口→核心→技能→数据) | 高层鸟瞰 |
| 2 | `02-skill-system-map.svg/png` | 17 个 skill 完整体系 (4 阶段) | 技能层 |
| 3 | `03-mcp-ecosystem-map.svg/png` | 44 个 MCP server 生态 (8 类别 + 中心) | 数据层 |
| 4 | `04-research-pipeline.svg/png` | 8 步研究流水线 (想法→论文) | 流程层 |
| 5 | `05-deployment-data-flow.svg/png` | 部署/数据流 + 3 层安全边界 | 运维层 |

**设计原则**：每张图只讲一个故事，互不重叠。统一暗色背景 16:10 比例。

**自动生成**：
```bash
python scripts/gen_architecture_diagrams.py
# 输出 → .github/demo/0[1-5]-*.{svg,png}
```

**转换 PNG**（需要 rsvg-convert）：
```bash
brew install librsvg
for f in .github/demo/0[1-5]-*.svg; do
  rsvg-convert -w 1600 -h 1000 "$f" -o "${f%.svg}.png"
done
```

2. Save it in this directory
3. Update the README.md image link to point to your file
4. Commit and push to GitHub
