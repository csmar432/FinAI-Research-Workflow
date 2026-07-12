# Literature Review — [TITLE]

> **阶段**: Stage 2 (literature review)
> **文献源**: OpenAlex / Semantic Scholar / ArXiv / NBER
> **预期文献数**: 30-50 篇 (含 5-10 篇顶刊)

---

## 1. Search Strategy

### 1.1 关键词
- Primary: [keyword 1], [keyword 2]
- Secondary: [keyword 3], [keyword 4]

### 1.2 数据库
- OpenAlex (免费, 2亿+): https://openalex.org
- Semantic Scholar: https://api.semanticscholar.org
- NBER Working Papers: https://www.nber.org/papers
- ArXiv: https://arxiv.org

### 1.3 时间窗口
- 主文献: 2015-2026 (近 10 年顶刊)
- 经典文献: 不限

---

## 2. Citation Network (引文网络)

```
[Author 1, Year] ──── [Author 2, Year]
       │                    │
       ↓                    ↓
[Author 3, Year] ──── [Author 4, Year]
       │
       ↓
   [本文]
```

---

## 3. 主题分类 (Topic Clusters)

### 3.1 [Cluster 1: 主题 A]
- [Author 1, Year, Journal]: 主要发现
- [Author 2, Year, Journal]: 主要发现

### 3.2 [Cluster 2: 主题 B]
- [Author 1, Year]: 主要发现

### 3.3 [Cluster 3: 方法论]
- DID: [Callaway & Sant'Anna 2021 QJE], [Sun & Abraham 2021 REStud]
- IV: [Stock & Yogo 2005]

---

## 4. 研究缺口 (Research Gap)

| 维度 | 现有文献 | 缺口 |
|---|---|---|
| 数据 | [Country / Period] | [Period / Country gap] |
| 方法 | [Method] | [Method gap] |
| 内生性 | [Treatment] | [Treatment gap] |

---

## 5. 本文定位 (Positioning)

本文填补 [具体 gap]，使用 [data/method] 识别 [research question]。

---

## 6. 引用 BibTeX (示例)

```bibtex
@article{callaway2021difference,
  title={Difference-in-differences with multiple time periods},
  author={Callaway, Brantly and Sant'Anna, Pedro HC},
  journal={Journal of Econometrics},
  volume={225},
  number={2},
  pages={200--230},
  year={2021}
}
```