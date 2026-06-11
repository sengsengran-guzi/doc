# D<N> — Progress

> 今日 ticket 状态表。Kevin testing-human 后更新。

---

| Ticket | 标题 | AI 自测 | testing-human | revision 轮次 | 状态 |
|---|---|---|---|---|---|
| GZ-ADMIN-105 ⭐ | 对账中心（4% 分成核心） | ✅ Tier1A（编译+13单测+AC9三层误差=0+install+build:prod） | N/A（纯 admin/后端，无人验） | 0 | ✅ done（待 admin Playwright E2E 可选补） |
| GZ-ADMIN-108 | 软删恢复回收站 | ✅ 编译+5单测+DDL验证+build:prod | N/A（纯 admin/后端，无人验） | 0 | ✅ done |
| GZ-ADMIN-106 | 数据看板扩展（复用105） | ✅ 编译+3单测+DDL验证+build:prod | N/A（纯 admin/后端，无人验） | 0 | ✅ done |
| GZ-ADMIN-104 | 物流2态推进（mp店员+owner） | ✅ 编译+11单测+DDL验证+plus-ui build+mp type-check+vitest 374 | ⬜ 待批量人验：mp 店员端真机物流推进 happy path | 0 | ai-✅ / mp 待人验 |
| GZ-ADMIN-107 | 火花券店 | — | — | — | 🚫 deferred (v2，Kevin C3 已裁定，未实施代码) |

> **人验列**：仅 GZ-ADMIN-104 mp 店员端进人验（其余纯 admin/后端 AI ✅ 即终态）。Kevin 批量人验路径见 testing-human.md §6。

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

**revision 轮次说明**：每次 Kevin 在 ticket 任务卡 `§revision` 写新一批问题 → AI 闭环修一轮 → +1。
revision 轮次 ≥ 3 时应停下来想：是不是 ticket 边界没切对，还是 AC 写得太模糊。

---

## 阻塞 / 风险

（如有：D<N> 跑到一半发现什么阻塞）

## 已挪到明日的 ticket

（如有：今日没干完的 → 写到 D<N+1>/README.md ticket 清单）
