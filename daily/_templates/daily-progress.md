# D<N> — Progress

> 今日 ticket 状态表。「状态」在 AI Tier 1A+1B 全 ✅ 时即 close（解锁下游）；「人验」列由 Kevin 批量人验后更新（不强求当天）。

---

| Ticket | 标题 | AI 自测 | 人验(集中) | revision 轮次 | 状态 |
|---|---|---|---|---|---|
| GZ-XXX-001 | ... | ⏳ | - | 0 | pending |
| GZ-XXX-002 | ... | - | - | 0 | pending |

**状态枚举**：pending / in-progress / ai-testing / revision-X / ✅ done（AI Tier 1A+1B 全 ✅ 即此态，解锁下游）/ 🚫 blocked

**「人验(集中)」列**：`—` 不需人验（纯 admin / 后端 ticket）｜ ⬜ 待集中验（mp ticket）｜ ✅ 已验 ｜ 🔁 回修（批量人验发现问题，已回填 §revision）

**revision 轮次说明**：每次 Kevin 在 ticket 任务卡 `§revision` 写新一批问题 → AI 闭环修一轮 → +1。
revision 轮次 ≥ 3 时应停下来想：是不是 ticket 边界没切对，还是 AC 写得太模糊。

---

## 阻塞 / 风险

（如有：D<N> 跑到一半发现什么阻塞）

## 已挪到明日的 ticket

（如有：今日没干完的 → 写到 D<N+1>/README.md ticket 清单）
