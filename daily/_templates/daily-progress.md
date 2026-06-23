# D<N> — Progress

> 今日 ticket 状态表。「状态」在 AI Tier 1A+1B 全 ✅ 时即 close（解锁下游）；「人验」列由 Kevin 节点触发残留人验后更新（无固定周期）。

---

| Ticket | 标题 | AI 自测 | 人验(节点) | revision 轮次 | 状态 |
|---|---|---|---|---|---|
| GZ-XXX-001 | ... | ⏳ | - | 0 | pending |
| GZ-XXX-002 | ... | - | - | 0 | pending |

**状态枚举**：pending / in-progress / ai-testing / revision-X / ✅ done / 🚫 blocked。`✅ done` 由 AI Tier 1A+1B 全 ✅ 达成（Tier 1B 含 mp 模拟器 E2E：run.mjs 导航可达 / 渲染 / 表单打真后端 / wxMOCK 登录 / 截图），即此态解锁下游。**mp 功能流 ticket 也经 AI gate 到 done**，无需等人验；真机微信原生残留是 out-of-band 节点触发残留人验，不 reopen ticket（发现问题走 §revision 回填，不退回 done 态）。

**「人验(节点)」列**（只剩真机原生 + 首版视觉两类残留）：
- `—` 不需人验：纯 admin / 后端 ticket，**或 mp 无真机原生能力（AI 模拟器 E2E 已 gate）** —— 同 admin，AI gate close 即终态
- ⬜ 待节点验：仅碰真机微信原生（支付 / getPhoneNumber / 客服 / 真机扫码 / 登录头像昵称授权 / 真机性能）或新页首版视觉拍板的 mp ticket
- ✅ 已验 ｜ 🔁 回修（残留人验发现问题，已回填 §revision）

**revision 轮次说明**：每次 Kevin 在 ticket 任务卡 `§revision` 写新一批问题 → AI 闭环修一轮 → +1。
revision 轮次 ≥ 3 时应停下来想：是不是 ticket 边界没切对，还是 AC 写得太模糊。

---

## 阻塞 / 风险

（如有：D<N> 跑到一半发现什么阻塞）

## 已挪到明日的 ticket

（如有：今日没干完的 → 写到 D<N+1>/README.md ticket 清单）
