---
keyword: FeatureStability
category: 条件性记忆
created: 2026-04-06
updated: 2026-04-06
entry_count: 1
---

# FeatureStability

---

### 加速度 vs 速度作为token稳定性判据
**概要**: 在diffusion caching中判断token是否可安全复用时，加速度（特征变化的变化率$A_i(t) = \|v_i(t) - v_i(t-1)\|_2$）比速度（特征变化幅值$V_i(t) = \|v_i(t)\|_2$）更有效。Fast3Dcache消融实验显示：单用加速度F-Score 53.54，单用速度反而仅44.96（比随机选择50.99还差），联合使用（$\omega=0.7$加速度权重更高）达最优54.09。直觉：速度大只说明特征在变，但如果变化方向稳定（加速度小），则可安全外推复用；反之速度小但加速度大说明即将突变，不应cache。
**来源**: [[2026-04-06_paper_002|Fast3Dcache: 3D Geometry Synthesis Acceleration]]
**添加时间**: 2026-04-06
