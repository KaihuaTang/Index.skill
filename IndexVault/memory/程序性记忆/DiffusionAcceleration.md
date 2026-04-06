---
keyword: DiffusionAcceleration
category: 程序性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# DiffusionAcceleration

---

### Fast3Dcache的三阶段几何感知caching流程
**概要**: Phase 1（全量计算）：直到锚点步$\lceil T \times \rho_a \rceil$为止执行完整推理，因早期体素变化剧烈不适合cache；锚点步记录初始变化量$\sigma$用于校准。Phase 2（动态caching）：PCSC用$\Delta\hat{s}_t = \sigma \cdot e^{\mu(t - \text{anchor})}$预测每步cache预算，SSC按$C_i(t) = \omega \cdot \text{norm}(A_i) + (1-\omega) \cdot \text{norm}(V_i)$评分选token（$\omega=0.7$最优），每$\tau$步强制全量计算消除累积误差。Phase 3（激进caching）：CFG关闭后用固定比例$\xi$的cache预算+周期校正$f_{\text{corr}}$。
**来源**: [[2026-04-06_paper_002|Fast3Dcache: 3D Geometry Synthesis Acceleration]]
**添加时间**: 2026-04-06
