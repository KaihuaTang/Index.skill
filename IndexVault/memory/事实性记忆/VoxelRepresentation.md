---
keyword: VoxelRepresentation
category: 事实性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# VoxelRepresentation

---

### 3D去噪中体素占据场的三阶段稳定模式
**概要**: 在TRELLIS等稀疏体素3D diffusion模型的去噪过程中，动态体素数量（相邻步间XOR计算占据状态变化的体素数$\Delta s_t$）呈现明确的三阶段模式：Phase 1剧变期（粗糙形状形成，$\Delta s_t$大）→ Phase 2渐进稳定期（$\Delta s_t$按对数线性衰减）→ Phase 3微调期（$\Delta s_t$骤降，仅细节修正）。这一规律为自适应计算分配提供了物理依据——不同阶段应给不同的caching预算。
**来源**: [[2026-04-06_paper_002|Fast3Dcache: 3D Geometry Synthesis Acceleration]]
**添加时间**: 2026-04-06
