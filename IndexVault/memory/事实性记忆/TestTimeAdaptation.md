---
keyword: TestTimeAdaptation
category: 事实性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# TestTimeAdaptation

---

### BayesMM — 无训练贝叶斯多模态分布学习TTA框架
**概要**: BayesMM将测试时自适应(TTA)形式化为动态多模态分布学习问题。将每个类的文本先验和视觉特征分别建模为高斯分布，文本参数从LLM扩写的多样化prompt中估计（静态），视觉参数随测试流在线贝叶斯递推更新（动态）。通过贝叶斯模型平均自动加权两模态后验预测，在ULIP/ULIP-2/OpenShape/Uni3D四个3D backbone上平均提升4%+准确率，无需任何训练。发表于CVPR 2026。
**来源**: [[2026-04-06_paper_001|BayesMM: Multimodal Bayesian Distribution Learning]]
**添加时间**: 2026-04-06
