---
keyword: TrainingFree
category: 元认知记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 2
---

# TrainingFree

---

### Training-free算法作为研究范式
**概要**: Training-free方法不修改模型权重，通过概率推断、统计方法或结构化启发式实现目标功能，优势是即插即用、无需额外训练数据和GPU计算。在TTA领域，BayesMM用贝叶斯分布学习替代传统需要反向传播的适应方法；在推理加速领域，也有类似的无训练caching策略。此类方法的核心设计模式是：找到任务中的结构化先验或统计规律，用闭式/解析方法替代学习过程。关注此类方法作为重要研究方向。
**来源**: [[2026-04-06_paper_001|BayesMM: Multimodal Bayesian Distribution Learning]]
**添加时间**: 2026-04-06

---

### Diffusion推理加速中的Training-free几何感知策略
**概要**: Fast3Dcache展示了Training-free方法在diffusion推理加速领域的又一成功案例。其核心设计模式与BayesMM一致：找到任务中的结构化先验（体素占据场的三阶段稳定模式），用解析方法（对数线性衰减预测+速度-加速度评分）替代学习过程。与BayesMM的贝叶斯分布学习形成互补案例——前者利用统计充分性，后者利用物理稳定性规律。两者共同印证：高质量的领域先验分析 + 闭式/启发式方法 = 免训练即插即用的实用方案。
**来源**: [[2026-04-06_paper_002|Fast3Dcache: 3D Geometry Synthesis Acceleration]]
**添加时间**: 2026-04-06
