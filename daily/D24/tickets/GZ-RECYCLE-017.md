# GZ-RECYCLE-017 — 过期未核销单批量筛选 + 释放

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M10（回收预约）
**关联拆解**: N/A（甲方 8.28 微信新提）
**关联 ADR**: 无新决策（复用 ADR-0022 小时格模型 + 对齐 GZ-BEAN-041 既有解法）
**依赖**: GZ-RECYCLE-012（小时格）/ GZ-RECYCLE-014（取消顾客单，同类释放动作）

---

## 需求原文（甲方微信，2026-08-28）

> 「添加一个功能，admin里，针对一些已过期但是没核销的单子，管理者可以批量筛选并释放」

配图：admin 回收记录列表，3 笔 7/22-7/24 的单仍是「待到店核对」（截图当日 8/28，积压一个多月）。

## 根因（与 GZ-BEAN-041 同源）

回收侧**早就有** `markExpiredNoShow()` 凌晨任务扫过期 submitted 单标 no_show。但 **prod 从未部署 SnailJob**
（25 个 `@JobExecutor` 一个都没跑，见 memory `snailjob-not-deployed-in-prod`），于是这条 cron 从来没生效过，
过期单越积越多。拼豆当初遇到完全一样的问题，Kevin 拍板走「路 B = 不上 SnailJob 基建，给 admin 手动批量口」
（D18 GZ-BEAN-041）。本 ticket 就是把同一解法搬到回收侧。

## ⭐ 真正的危害（实施中查证，比甲方描述的更严重）

甲方的直觉是「脏数据/占格」，但**占格其实不是问题**——过去日期本来就不可约（被 4131 `SLOT_PAST` 挡着）。

真正的危害是**一人一单守卫**：

```sql
-- countActiveByUserForUpdate（写路径守卫，4127 的真源）
SELECT COUNT(*) FROM gz_recycle_appointment
WHERE tenant_id = ? AND user_id = ?
  AND status IN ('submitted','confirmed_onsite','paying','payout_failed') AND del_flag='0'
```

**没有任何日期条件**。所以顾客一张一个月前的爽约单，会让他**永久约不了下一单**（4127「您已有进行中的
回收预约，完成或取消后再约」）。dev 库现场：user 11 挂着 5 张 7 月的 submitted 单 → 彻底约不了。

`no_show` 既不在 `ACTIVE_HOLD_STATUSES`（释放小时格）也不在 `USER_ACTIVE_STATUSES`（解封再约资格），
**一个状态解决两件事** —— 所以「释放」= 标 `no_show` 是正解，不需要新状态。

## What

admin 回收页新增「过期待处理」区（命名对齐拼豆 GZ-BEAN-041）：按门店 + 到店日期范围筛选到店日已过、
仍停在 `submitted` 的顾客单，勾选后批量释放为 `no_show`。

## AC（验收标准）

- [x] AC 1：`GET /system/gz/recycle/appointment/expired-unsettled?storeId=&dateFrom=&dateTo=` 三参数全可选
- [x] AC 2：候选集**只含 `submitted`** —— `confirmed_onsite` 是现金结算完成态（客户 7.15），释放它等于把
      一笔已付钱的交易改成「未到店」= 伪造账目，必须排除
- [x] AC 3：上界后端**硬夹到「昨天」**——当天的单当天仍可到店核对，即便前端传未来日期也不得进候选
- [x] AC 4：`POST /system/gz/recycle/appointment/batch-release-expired` 返回 `{succeeded, skipped, failed}` 三元计数
- [x] AC 5：**逐单独立**，一条失败不中断整批（对齐拼豆 `batchSettle`）
- [x] AC 6：**幂等** —— 重复释放同一单返回 `skipped` 而非 `succeeded`（底层 `markNoShow` 的
      `WHERE status='submitted'` 守卫，并发被店员核对掉也不会误改）
- [x] AC 7：admin UI 显示「已过期 N 天」，二次确认文案点明后果，释放后列表/主列表/周看板一起刷新
- [x] AC 8：复用既有 `gz:recycle:appointment:hold` 权限（与「取消顾客单」同类释放动作），**不新增 menu**
- [x] AC 9：i18n zh/en 同 key 同步

## 技术要点

1. **无迁移、无新表、无新权限、无新状态** —— 纯复用既有 `markNoShow` mapper 方法 + 既有 `no_show` 状态。
2. `ids` 上限 500（`@Size`）：防「全选」一次勾上全部历史积压导致单请求跑太久。
3. 前端 `skipped`/`failed` 不为 0 时用 warning 而非 success 提示 —— 不掩盖并发/异常。
