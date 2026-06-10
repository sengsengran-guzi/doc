# D13 — Progress

> 今日 ticket 状态表。Kevin testing-human 后更新。

---

| Ticket | 标题 | AI 自测 | testing-human | revision 轮次 | 状态 |
|---|---|---|---|---|---|
| GZ-PAY-105 | 反向打款 mock + payout 表 + 查单 SnailJob | ✅ Tier1A+1B | N/A（纯后端） | 0 | ✅ done |
| GZ-COUPON-002 | 拼豆抵扣锁定/核销/回滚 + 过期 SnailJob | ✅ Tier1A+1B | N/A（纯后端） | 0 | ✅ done |
| GZ-RECYCLE-001 | 回收价目表 + 区间校验 + 估价 | ✅ Tier1A+1B | N/A（纯后端/admin） | 0 | ✅ done |
| GZ-COUPON-003 | mp 选券 + 我的券列表 | ✅ Tier1A+1B | ⬜ 待批量验 | 0 | human-testing |
| GZ-BEAN-015 | mp 拼豆付费页（选类型+时段余量+采集+JSAPI） | ✅ Tier1A+1B | ⬜ 待批量验 | 0 | human-testing |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

---

## 阻塞 / 风险
- **subagent 崩溃率 5/7**（D13 实战，`tool call could not be parsed`）→ RECYCLE-001 / COUPON-003 / BEAN-015 主线程接管完成（见 memory `subagent-crash-mainthread-fallback`）。后续 daily 编排建议主线程为主。
- **PAY-105 transferbatch SDK 走 mock**（未批准）；real 上线待 Kevin × 甲方确认商户「商家转账到零钱」权限 + SDK 批准。

## Tier 1B 集成验证（主线程整批，2026-06-10）
App `Started in 10.958s`（Bean 装配无环）+ Flyway 6 迁移应用（now at v202606210201）+ 5 新路由 curl 200。8080 已释放。

## 人验（mp 卡，Kevin 批量真机）
- GZ-BEAN-015 + GZ-COUPON-003 → 见 [testing-human.md](testing-human.md)；**前置：admin 先给测试用户发券**（COUPON-001 发放页），否则券列表/选券为空。

## 已挪到明日的 ticket
（无 — D13 5 卡全完成）
