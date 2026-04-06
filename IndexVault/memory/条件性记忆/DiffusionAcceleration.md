---
keyword: DiffusionAcceleration
category: 条件性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# DiffusionAcceleration

---

### 2D vs 3D caching加速的关键差异
**概要**: 2D图像/视频diffusion中，cache引入的微小数值误差最多导致纹理模糊，感知上可容忍。但3D体素表示具有拓扑敏感性——微小误差在迭代中累积，直接导致表面孔洞、几何扭曲、非流形网格等结构性破坏。实验证据：朴素固定比例caching(RAS 25%)在TRELLIS上F-Score下降27%，而几何感知的Fast3Dcache仅降2%。因此将2D caching方法直接迁移到3D是不可行的，必须设计几何感知策略（如按体素稳定化趋势动态调整cache预算）。
**来源**: [[2026-04-06_paper_002|Fast3Dcache: 3D Geometry Synthesis Acceleration]]
**添加时间**: 2026-04-06
