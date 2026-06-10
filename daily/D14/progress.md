# D14 — Progress

> 今日 ticket 状态表。Kevin testing-human 后更新。
> V1.2 调整批次收官日（D11-D14 封顶）。

---

| Ticket | 标题 | AI 自测 | testing-human | revision 轮次 | 状态 |
|---|---|---|---|---|---|
| GZ-RECYCLE-002 | 回收预约单 + 自动估价 + mp 填单页（submit_image_ids 必填） | ✅ Tier1A+1B | ⬜ 待批量验 | 0 | human-testing |
| GZ-RECYCLE-003 | 店员核对 + 拍照 + 触发反向打款 + admin 管理 | ✅ Tier1A+1B | ⬜ 待批量验（mp 店员端）/ admin AI 终态 | 0 | human-testing |
| GZ-SYS-010 | tabbar 重构（去首页 → 拼豆/回收/我的 + 资讯·扭蛋迁我的） | ✅ Tier1A+1B | ⬜ 待批量验 | 0 | human-testing |
| GZ-GACHA-111 | 扭蛋入口迁「我的」+ 端到端做活回归（不改概率/weight） | ✅ Tier1A+1B | ⬜ 待批量验 | 0 | human-testing |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

> 4 卡 AI Tier 1A+1B 全 ✅ → 即 close 解锁下游；mp 卡同时进「人验」列待 Kevin 批量真机验（异步，不阻塞批次封顶）。RECYCLE-003 admin 部分（预约/打款单管理）AI 终态无人验。

---

## Tier 1B 集成验证（主线程整批，2026-06-10）

> 沿用 D13 模式：subagent 不能 spawn 孙 agent + 多 Playwright 撞 8080 → 主线程一次启动 app 整批验（memory [[tier1b-qa-dispatch-by-mainthread]]）。

- **后端**：`mvn install` gz-common + gz-recycle BUILD SUCCESS；app `Started DromaraApplication`（real boot 11.5s）。
- **Flyway**：D14 新 4 迁移全应用 → `now at v202606230101`（202606220100 建表 / 220110 menu / 230100 menu-perm / 230101 status dict）。
- **表 schema 核验**（gz-ord-create-dept 潜伏 bug 教训）：`gz_recycle_appointment` 31 列齐全，含 create_dept/create_by/create_time/update_by/update_time/del_flag/tenant_id(default '1001')——**审计列无遗漏**，不会复现 ORD admin 500。
- **menu/dict seed**：13002 回收预约单 + 13020-13023（list/verify/payout/cancel perms）+ `gz_recycle_status` 7 值 seed 成功。
- **endpoints curl 200**（gz_owner / 租户 1001 / --noproxy）：
  - admin `/system/gz/recycle/appointment/list` → 200（total:0）
  - admin `/system/gz/pay/payout/list` → 200（total:0，PAY-105 复用）
  - mp `/app/gz/recycle/appointment/categories` → 200（dict gz_recycle_category：卡牌/谷子）
  - mp `/app/gz/recycle/appointment/estimate`（多品类）→ 200，**card×3(1500/15)+goods×5(1500/20) = total 3000 / qty 8 / dur 35**（F12.1 累加口径真实命中）；E1 unknown_cat → `hasUnpriced:true` + line nulls（不阻断其余）。
- **mp**：`pnpm type-check` 0 error + `pnpm test` 40 files / **374 tests passed** + `build:mp-weixin` dist 生成（app.json tabBar 3 项 + 启动落地 bean）。
- **8080 已释放**，无 dev server / devtools cli 残留。

## 阻塞 / 风险
- **本批次全 foreground subagent 实施，0 崩溃**（区别 D13 background 5/7 崩溃；memory [[subagent-crash-mainthread-fallback]] 验证：foreground 阻塞派单 + 主线程整批 Tier 1B 最稳）。
- **RECYCLE-003 反向打款走 mock**：真实「商家转账到零钱」权限 + transferbatch SDK 待 Kevin × 甲方（ADR-0006 外部 gate）；mock 全链路单测已覆盖 created→processing→success/failed + 幂等。
- **回收 tab C 风图标 = 占位**（复用 home 图）→ designer 待补（active/inactive 80×80 PNG，drop-in 同名替换不改代码）。

## 人验（mp 卡，Kevin 批量真机）
- RECYCLE-002（用户填单）/ RECYCLE-003（店员核对端）/ SYS-010（导航）/ GACHA-111（扭蛋做活）→ 见 [testing-human.md](testing-human.md)。
- **前置**：RECYCLE-003 店员核对需先有 `submitted` 预约（RECYCLE-002 填单产生）+ 店员账号绑 sys_user（ADR-0004，gz_user.staff_user_id）授 `gz:recycle:appointment:verify`。
- **V1.2 集成回归 checklist**：见 [v1.2-integration-checklist.md](v1.2-integration-checklist.md)（拼豆付费 + 优惠券 + 回收反向打款 + tabbar + 扭蛋做活 全链路）。

## V1.2 调整批次封顶（D11-D14，15 ticket）
ORD-110 / USER-005 / USER-006 / BEAN-013/014/015 / COUPON-001/002/003 / PAY-105 / RECYCLE-001/002/003 / SYS-010 / GACHA-111 全 close（AI ✅）。
**下一日 D15**：原 V1.1 收官 ADMIN-104（物流 2 态推进）/ ADMIN-105 ⭐（对账中心）/ ADMIN-106（看板扩展）/ ADMIN-108（软删回收站）。

## 已挪到明日的 ticket
（无 — D14 4 卡全完成）
