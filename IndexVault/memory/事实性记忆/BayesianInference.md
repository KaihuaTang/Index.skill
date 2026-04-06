---
keyword: BayesianInference
category: 事实性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# BayesianInference

---

### 高斯-高斯共轭的闭式在线更新
**概要**: 利用高斯分布的共轭先验性质，贝叶斯递推更新有闭式解：$\mu_t = \Sigma_t(\Sigma^{-1}x_t + \Sigma_{t-1}^{-1}\mu_{t-1})$，$\Sigma_t = (\Sigma_{t-1}^{-1} + \Sigma^{-1})^{-1}$。高斯分布的均值和协方差是历史数据的充分统计量，用分布替代cache存储可实现零信息损失且内存恒定（不随样本数增长）。这是BayesMM在TTA场景中替代传统cache机制的理论基础。
**来源**: [[2026-04-06_paper_001|BayesMM: Multimodal Bayesian Distribution Learning]]
**添加时间**: 2026-04-06
