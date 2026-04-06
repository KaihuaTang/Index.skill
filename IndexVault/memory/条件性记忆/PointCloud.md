---
keyword: PointCloud
category: 条件性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# PointCloud

---

### 点云域偏移下的TTA方法选择
**概要**: 多模态3D模型(ULIP/OpenShape/Uni3D)在分布偏移下（噪声、遮挡、跨域）性能显著下降。BayesMM的贝叶斯分布学习在4个backbone上一致有效：弱backbone(ULIP)提升最大(+10.8%)，强backbone(Uni3D)提升较小(+3.6%)。文本模态在偏移下比视觉模态更稳定，始终获得更高的贝叶斯权重。方法保持97%+推理速度，且为training-free即插即用。适用场景：3D点云模型部署后遇到域偏移需在线适应，尤其基础能力较弱的模型收益更大。
**来源**: [[2026-04-06_paper_001|BayesMM: Multimodal Bayesian Distribution Learning]]
**添加时间**: 2026-04-06
