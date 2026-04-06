---
keyword: MultimodalFusion
category: 程序性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# MultimodalFusion

---

### 贝叶斯模型平均实现自适应多模态融合
**概要**: 多模态融合时，为每个模态分别计算类后验概率$p(c|x,\Theta)$，然后以各模态的后验证据$p(\Theta|x)$作为权重进行加权平均：$p(c|x) = \sum_m p(c|x,\Theta_m) \cdot p(\Theta_m|x)$。权重由数据自动决定——哪个模态对当前样本后验更集中（更"确信"），就给更大权重。此方法消除了手调融合超参的需求，在分布偏移场景下比启发式加权融合更稳定。BayesMM的实验显示文本模态在偏移下始终获得更高权重。
**来源**: [[2026-04-06_paper_001|BayesMM: Multimodal Bayesian Distribution Learning]]
**添加时间**: 2026-04-06
