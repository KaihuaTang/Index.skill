---
keyword: DiffusionAcceleration
category: 事实性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# DiffusionAcceleration

---

### Fast3Dcache — Training-free 3D Diffusion几何感知加速框架
**概要**: Fast3Dcache是首个针对3D diffusion模型（TRELLIS系列）的几何感知caching加速框架。核心发现：3D去噪中体素占据场呈三阶段稳定模式。PCSC按对数线性衰减模型动态分配每步cache预算上限，SSC用速度+加速度联合评分选择可安全缓存的token。在TRELLIS上实现27%加速、55% FLOPs削减，Chamfer Distance仅增2.48%、F-Score仅降1.95%。与EasyCache组合可达10.3x加速。发表于CVPR 2026。
**来源**: [[2026-04-06_paper_002|Fast3Dcache: 3D Geometry Synthesis Acceleration]]
**添加时间**: 2026-04-06
