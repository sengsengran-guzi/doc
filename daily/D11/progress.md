# D11 — Progress

> V1.2 快赢 + 拼豆地基 + 资料/登录态地基。今日 ticket 状态表，Kevin 批量人验后更新「人验」列。4 个 ticket 全并行，互不依赖。

---

| Ticket | 标题 | 端 | AI 自测(1A+1B) | 人验(Tier2) | revision 轮次 | 状态 |
|---|---|---|---|---|---|---|
| GZ-ORD-110 | 预购下线（屏蔽 admin + mp 入口，保留代码） | admin+be+mp | ⏳ | ⬜ 待批（入口消失验证） | 0 | pending |
| GZ-USER-005 | gz_user.wechat_id 字段 + mp 资料页录入 | be+admin+mp | ⏳ | ⬜ 待批 | 0 | pending |
| GZ-USER-006 | 微信资料完善（chooseAvatar+nickname 持久化）+ 登录态保持 | be+mp | ⏳ | ⬜ 待批（头像昵称持久化 + 登录态续期） | 0 | pending |
| GZ-BEAN-013 | 座位类型配额配置（admin 配数量/单价 + 废弃 A1-A10） | be+admin | ⏳ | — 无 | 0 | pending |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done（AI Tier 1A+1B 全 ✅ 即此态，解锁下游）/ 🚫 blocked

**close 口径**（CLAUDE.md §8.2）：
- 纯 admin（GZ-BEAN-013）→ Tier 1A+1B 全 ✅ 即终态 **done**，无人验
- mp（GZ-ORD-110 入口消失 / GZ-USER-005 资料页录入 / GZ-USER-006 头像昵称持久化 + 登录态续期）→ Tier 1A+1B ✅ 已 close 解锁下游，同时进**人验列待 Kevin 批量人验**（⬜）

**「人验(Tier2)」列**：`—` 不需人验（纯 admin/数据 ticket）｜ ⬜ 待集中验（mp ticket）｜ ✅ 已验 ｜ 🔁 回修（批量人验发现问题，已回填 §revision）

**revision 轮次说明**：每次 Kevin 在 ticket 任务卡 `§revision` 写新一批问题 → AI 闭环修一轮 → +1。revision 轮次 ≥ 3 时应停下来想：是不是 ticket 边界没切对，还是 AC 写得太模糊。

---

## 阻塞 / 风险

（如有：D11 跑到一半发现什么阻塞）

- **GZ-ORD-110 勿误藏扭蛋**：改 menu visible 前必须 `SELECT` 逐行确认 preorder vs gacha 项（订单聚合 admin 11007-11009 两类共存），误藏 gacha 会与扭蛋 V1.2「保留做活」（GZ-GACHA-111 D14 入口迁移 + 做活回归）冲突 → 跑到该步留意。
- **GZ-USER-006 getUserProfile 禁用 + 头像存 COS**：chooseAvatar + nickname input 一次性采集（getUserProfile 已废弃），头像必须上传 COS 存 avatar_image_id 不存裸 url；登录态静默续期不踢用户（ADR-0009）。

## 已挪到明日的 ticket

（如有：今日没干完的 → 写到 D12/README.md ticket 清单）

D12 预告（不在本日）：拼豆付费核心 GZ-BEAN-014（←GZ-BEAN-013 + GZ-USER-005 + GZ-PAY-101，**单笔单时段**付费列 + seat_type ALTER + 余量查询接口 + 按 booking 计数防超卖 + 旧数据迁移 + 激活 PayBusinessType.PINDOU，**无子表**，参 ADR-0007/0008）∥ 优惠券地基 GZ-COUPON-001（模板 + 用户券 + 发放策略 SPI + manual 实现 + 预留 register_window/event，menu 12000 段）。
