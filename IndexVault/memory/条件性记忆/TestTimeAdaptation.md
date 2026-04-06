---
keyword: TestTimeAdaptation
category: 条件性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# TestTimeAdaptation

---

### 分布存储 vs Cache存储的权衡
**概要**: Cache-based TTA用固定大小缓冲区存最近样本特征，有两个结构性缺陷：(1)容量有限导致渐进信息丢失；(2)cache logits与zero-shot logits的融合依赖手调超参$\lambda,\gamma$，跨域不稳定。分布存储（维护每类均值+协方差）是充分统计量方案：零信息损失、内存恒定（不随样本数增长）、可通过贝叶斯框架自然融合无需超参。BayesMM在1156类(O-LVIS)场景下内存仅增~4MB，而cache方案增~18MB。适用于需要长期在线适应且类数大的场景。
**来源**: [[2026-04-06_paper_001|BayesMM: Multimodal Bayesian Distribution Learning]]
**添加时间**: 2026-04-06
