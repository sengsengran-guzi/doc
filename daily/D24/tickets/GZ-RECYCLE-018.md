# GZ-RECYCLE-018 — 修：卖过一次的老顾客永久约不了第二单

**优先级**: P0（线上正在生效的顾客侧阻断）
**复杂度**: S（2 行状态字面量）
**关联拆解**: N/A（GZ-RECYCLE-017 实施中查证发现）
**关联 ADR**: 无新决策（修的是客户 7.15 现金结算改造的遗留漏改）
**依赖**: 无

---

## 问题

「一人一单」守卫（客户 7.24，错误码 4127）的进行中态集合含 `confirmed_onsite`：

```java
USER_ACTIVE_STATUSES = List.of("submitted", "confirmed_onsite", "paying", "payout_failed");
```

但**客户 7.15 把回收改成店内现金结算后，`confirmed_onsite` 就是终态** —— `verifyAndPayout` 在
auto-payout 关闭（prod 默认）时核对确认即 `return`，不再进 `paying/paid`。顾客当场拿了现金，交易已了结。

**后果：任何成功卖过一次东西的老顾客，永远约不了第二单**（恒撞 4127「您已有进行中的回收预约，
完成或取消后再约」）。dev 库实证：user 14 只有一张 `confirmed_onsite` 单，已被永久锁死。

## 这不是有意设计

常量注释自己写着「排除 `paid / cancelled / no_show` 三终态（**拿到钱或结束即可再约**）」——
意图明确是「交易结束即可再约」。只是 7.15 切现金模式时漏改了这个列表：打款模式下 `paid` 才是终态，
现金模式下 `confirmed_onsite` 就是终态。

## auto-payout 开启时是否安全？—— 是

实施前专门核查过（否则无脑删会在另一条路径上出事）：

1. `verifyAndPayout` 整体 `@Transactional(rollbackFor = Exception.class)` → 打款发起抛异常会连
   `markConfirmedOnsite` 一起回滚，单子退回 `submitted`，**不会卡在 `confirmed_onsite`**。
2. 唯一能停在该态的是 `markPaying` 返 0，但前一句 UPDATE 已持有行锁到提交，并发改不进来，实际不可能。
3. **真正资金在途的 `paying / payout_failed` 仍在集合内**，拦截能力不减。

## What

`confirmed_onsite` 从「一人一单」进行中态移除（**两份物理拷贝同步**）。

## AC

- [x] AC 1：`USER_ACTIVE_STATUSES` = `submitted / paying / payout_failed`
- [x] AC 2：`countActiveByUserForUpdate` 的 `@Select` 内联字面量同步（MyBatis 注解引用不了 Java 常量）
- [x] AC 3：`GzRecycleActiveStatusConsistencyTest` 守住两份拷贝一致 —— 并**实际验证过守卫会红**
      （故意只改一处，测试如实报 `Java=[3] SQL=[4]`）
- [x] AC 4：新增回归测试钉死本决策 + 理由，防后人「顺手补齐」加回去
- [x] AC 5：`paying / payout_failed / submitted` 仍拦（资金守卫不被削弱）
- [x] AC 6：读路径 `/active` 与写路径守卫**全 7 状态口径一致**（分叉 = 前端显示可约但提交被拒）

## 影响面

- **无迁移、无表结构变更、无数据订正**：存量 `confirmed_onsite` 单不动，只是不再计入「进行中」。
- mp「你有进行中的回收预约」横幅：持 `confirmed_onsite` 的顾客不再看到（正确 —— 那单已完成）。
