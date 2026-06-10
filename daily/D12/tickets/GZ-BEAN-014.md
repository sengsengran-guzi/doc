# GZ-BEAN-014 — 单笔单时段付费预约 + 余量查询接口 + 防超卖按 booking 计数 + 旧数据迁移 + 激活 PINDOU

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md M4 §拼豆付费预约（V1.2 推倒 §3 免费 + A1-A10）
**关联拆解**: doc/02-需求拆解.md §3.6 GZ-BEAN-014（付费核心 + 状态机 + 防超卖 + 迁移）
**关联 mockup**: N/A（纯后端，无 admin/mp 页；mp 选座付费页 = D13 GZ-BEAN-015）
**关联 ADR**: **doc/_adr/0007-pindou-paid-booking-state-machine.md（必读全文，双状态机 status×pay_status 正交 + 单笔单时段）** + **doc/_adr/0008-seat-type-quota-model.md（必读全文，座位类型配额 + 按 booking 计数 + 旧数据迁移）**
**依赖**: GZ-BEAN-013（D11，`gz_bean_seat_type_config` 配额 config）+ GZ-USER-005（D11，`gz_user.wechat_id`）+ GZ-PAY-101（已交付，支付通道 + PayBusinessType + PayCallbackHandler）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§11 拼豆付费预约全流程（V1.2 重头，单笔单时段）**（含 N6 付款前采集 wechat_id / N13a unpaid 超时回收）+ §3「已被 §11 推倒」标注
- **字段表**：doc/11-字段权威表.md **§3.5 `gz_bean_booking`（核心表，单笔=1类型+1时段，V1.2 加付费列 — 逐字段对齐）** + **§3.6 配额计数口径（活跃 booking 定义 + COUNT FOR UPDATE）** + **§3.8 状态字段详细口径（status/pay_status 双机正交 + verify_code 签名因子改 sess_date+seat_type）** + **§3.9 Redis Key（quota / user_submit 辅助锁）** + 附录 **A.3（status）** + **A.15（pay_status）** + §3.4（`gz_bean_seat_type_config` 单价/配额源）
- **ADR**：**ADR-0007 全文**（付费双状态机：付费前置 / 免费单兜底 / pay_closed 同步 status→cancelled+释放配额+回滚锁券 / 核销仅 paid+pending）+ **ADR-0008 全文**（§3 预约引 seat_type 不引 seat_id / §5 旧数据迁移在本卡落地）
- **UI 参考**（设计冻结期）：`N/A（纯后端，无页面）`

## What

在 D11 类型配额 config（`gz_bean_seat_type_config`）之上，**原地 ALTER 主表 `gz_bean_booking` 加付费列 + 座位类型列**，落地拼豆付费的后端骨架：单笔单时段付费预约下单事务（建一行 booking + 单价 snapshot + 配额校验 + 建 pindou 支付单）+ 余量查询接口 + 付费双状态机 + 防超卖按活跃 booking 悲观计数 + 旧免费 booking 原地迁移 + 激活 `PayBusinessType.PINDOU` 的 onPaid 回调分发。**单笔单时段、无子表、无累加**。本卡纯后端，mp 选座付费页 = D13 GZ-BEAN-015，券抵扣逻辑 = D13 GZ-COUPON-002（本卡仅留 `coupon_id`/`discount_amount_cent` 字段 + 下单事务 hook 位）。

## AC（验收标准）

- [ ] **AC 1 — ALTER 迁移（原地，无子表）**：新迁移 `V<时间戳 > 202606190631>__GZ-BEAN-014-alter-booking-paid-columns.sql`，对 `gz_bean_booking` **ALTER 加列**（严格对齐 doc/11 §3.5 V1.2 列）：`seat_type` VARCHAR(16) / `seat_type_snapshot` VARCHAR(32) / `wechat_id_snapshot` VARCHAR(64) NULL / `amount_cent` BIGINT NOT NULL DEFAULT 0 / `discount_amount_cent` BIGINT NOT NULL DEFAULT 0 / `coupon_id` BIGINT UNSIGNED NULL / `out_trade_no` VARCHAR(64) NULL / `pay_status` VARCHAR(16) NOT NULL DEFAULT 'unpaid'。**同迁移处理 V1.2 语义迁移**：① `seat_id` / `seat_no_snapshot` 改为 **NULL 允许**（V1.2 起不写，旧值保留）；② **DROP 旧 dedup 唯一索引 `uk_dedup_tenant_store_dedup`** 并将 `dedup_token` 改 NULL（doc/11 §3.5 末段：dedup 唯一约束随具体座位废弃失效，改配额计数保证）；③ 加索引 `(tenant_id, pay_status)` / `(tenant_id, coupon_id)` / **`(tenant_id, store_id, seat_type, sess_date, slot_start)`（配额计数核心索引）** / `(tenant_id, out_trade_no)` UNIQUE（MySQL 多 NULL 不冲突，等价 WHERE NOT NULL）。**确认无 `gz_bean_booking_unit` 子表 DDL**（R7 QA 打回项）。`seat_type` NOT NULL 但存量行先 ALTER 加列允许临时空 → 迁移脚本（AC 6）回填后再视情况。
- [ ] **AC 2 — 单笔单时段下单事务**：`POST` 下单接口（mp 用，path 归 `org.dromara.gz.bean`）建**一行** `gz_bean_booking`：1 用户 × 1 门店 × 1 `seat_type` × 1 时段（`sess_date`/`slot_start`/`slot_end`）；`amount_cent` = `gz_bean_seat_type_config.price_cent`（下单时该类型单价 snapshot，**非累加、无 total_amount_cent**）；`seat_type_snapshot` = 字典 `gz_bean_seat_type` 中文名 snapshot；`wechat_id_snapshot` = 提交时 `gz_user.wechat_id` snapshot；`status='pending'` + `pay_status='unpaid'`；生成 `booking_no`（`BK-yyyyMMdd-6位序号`）。reports 必含「一行 booking，amount_cent=类型单价，无累加无子表」raw output。
- [ ] **AC 3 — 防超卖配额计数（ADR-0008 / doc/11 §3.6 逐字落地）**：下单事务内对该 `(store_id, seat_type, sess_date, slot_start)` 执行 `SELECT COUNT(*) ... WHERE <活跃> FOR UPDATE`（**活跃 = `pay_status IN ('paying','paid')`**，含付款中暂占；`cancelled`/`no_show`/`pay_closed`/`refunded` 释放）比对 `gz_bean_seat_type_config.quantity`，`COUNT < quantity` 才放行 INSERT，满则**拒单（事务回滚 + 明确业务异常）**。单笔单时段一笔只占一个名额 → **无部分成交**。辅助：`gz:bean:lock:user_submit:{user_id}`（5s 防连点）+ 可选 `gz:bean:lock:quota:*`（5s，非主防护）；**不引 Redis 座位锁做主防护**。reports 必含并发压测 raw output（并发约同一档最后名额 → 仅一单成功，其余拒单）。
- [ ] **AC 4 — 余量查询接口**：mp GET 某门店某日各 `(seat_type, 时段)` 剩余可约数 = `gz_bean_seat_type_config.quantity − COUNT(活跃 booking WHERE store+seat_type+date+slot)`；返每档「还剩 N」（N>0）/「已满」（N≤0）。供 D13 BEAN-015 选座显余量。reports 必含该接口 raw output（quantity − 活跃计数 = 还剩 N / 已满）。
- [ ] **AC 5 — 付费双状态机 + 激活 PINDOU（ADR-0007）**：`status`（pending/used/cancelled/no_show）与 `pay_status`（unpaid/paying/paid/pay_closed/refunded）**正交并行不互相覆盖**。① 实付 > 0：建 booking 后建 `gz_pay_transaction(business_type='pindou', out_trade_no='PINDOU-...', amount_cent=实付)` → `pay_status='paying'`；激活 `PayBusinessType.PINDOU`；`PayCallbackHandler` onPaid 分发到拼豆：推 `pay_status='paid'` + 生成 `verify_code`（`HmacSHA256(booking_no + sess_date + seat_type, secret)` 截 32，**不再用废弃 seat_id**）+ 写 `gz_bean_booking_log`。② 免费单兜底：门店该类型 `price_cent=0` 且无券 → 实付 0 → 不建支付单，`pay_status` 直接 `paid`（`out_trade_no` NULL），`status='pending'`。③ pay_closed（超时/放弃）：`pay_status→'pay_closed'` + `status→'cancelled'` + 释放配额（+ 回滚锁券 hook 位，券逻辑 D13）。④ 核销前置：仅 `pay_status='paid'` 的 pending 单可核销（`status→'used'`，pay_status 不变）。
- [ ] **AC 6 — 旧数据迁移（原地补字段，无子表迁移）**：旧免费 booking（本就单类型单时段）原地补 `seat_type`（取旧座位类型映射，缺则兜底 `single`）+ `seat_type_snapshot` + `amount_cent=0` + 付费列；`pay_status` 旧已核销/pending 单置 `paid`（历史「已付 0 元」）+ `status` 保留原值；逐单校验 + 失败留痕（写日志/清单，不静默吞）。reports **必含迁移前后 count 比对 raw output**（误差 = 0 或人工清单）。迁移可走独立迁移文件或 service 脚本，幂等。
- [ ] **AC 7 — 单测 ≥ 80%**（CLAUDE.md §8.1，拼豆配额并发 + 付费状态机流转）：① 并发约同一 `(类型,日期,时段)` 最后名额 → 仅一单成功其余拒单（无部分成交）；② 双状态机各流转边（unpaid→paying→paid / 免费单直 paid / paying→pay_closed 同步 status→cancelled+释放配额 / 核销仅 paid+pending）；③ 余量计数（活跃定义 + 释放态不占）；④ 旧数据迁移幂等 + count 一致。
- [ ] **AC 8 — SnailJob（如本日落地）**：unpaid 占配额超时回收（默认 15 分钟，doc/10 §11.N13a）+ no_show 凌晨任务 → `@Component + @JobExecutor` 薄壳 + 可单测 service；模块 pom 显式加 `ruoyi-common-job`；**禁止 Quartz / Flyway INSERT sys_job**（启动 hard-fail）；任务名 + CRON 写进 reports 由人在 SnailJob 控制台注册。

> 纯后端 ticket，**跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2 — Tech 段无 mp 页 + AC 无微信原生能力，AI Tier 1A+1B 全 ✅ 即终态）。mp 选座付费 = D13 GZ-BEAN-015。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`（包名 `org.dromara.gz.bean.*`）
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V<时间戳 > 202606190631，建议 202606200000+>__GZ-BEAN-014-alter-booking-paid-columns.sql`（ALTER 主表 + 索引 + 旧索引 DROP）；旧数据迁移如走 SQL 则 `V<时间戳+1>__GZ-BEAN-014-migrate-legacy-booking.sql`（或 service 脚本，二选一，幂等）
  - `domain/GzBeanBooking.java` 加付费列字段（`@Version` 已有，`@TableLogic` 已有）；下单 Bo/Vo + 余量查询 DTO
  - `service` 下单事务（配额 COUNT FOR UPDATE + 建单 + 建支付单 / 免费单兜底）+ 余量查询 + 状态推进（onPaid / pay_closed / 核销）
  - 支付链路复用 `org.dromara.gz.common.pay.*`：激活 `PayBusinessType.PINDOU` + `PayCallbackHandler` 拼豆分发（onPaid → pay_status=paid + verify_code）
  - SnailJob executor（AC 8，如落地）
  - 模块 pom：如用 SnailJob 加 `ruoyi-common-job`；改 ruoyi-gz-* 后 `mvn install -am`（CLAUDE.md §5）
- **Admin / 小程序**：不动（无新增菜单，预约管理沿用 6000 现有）
- **测试**：单测（AC 7）+ kevin-qa Tier 1B（后端集成 + API 契约 + mock 全链路 onPaid）

## 备注

### 强约束（每条复核）

1. **必读 ADR-0007 + ADR-0008 全文**（双 ADR 是决策权威）。
2. **单笔单时段、无子表、无累加**（ADR-0007/0008 钉死）：一笔 = 一行 booking = 1 类型 1 时段，`amount_cent`=该类型单价 snapshot。**禁止建 `gz_bean_booking_unit` 子表**、禁止 `total_amount_cent`（R7 QA 打回项；§0 grep `booking_unit` 应空）。
3. **字段严格对齐 doc/11 §3.5**（V1.2 列含 `wechat_id_snapshot`）；偏离回改 doc/11 源头不在卡内 patch（§9.5）。
4. **防超卖按活跃 booking 计数**（§3.6 活跃定义逐字）+ `FOR UPDATE` 悲观锁；V1 单店小量不引 Redis 座位锁主防护。
5. **核销前置**：仅 `pay_status='paid'` 的 pending 单可核销；**付费前置**：paid 后才正式占名额/可核销。
6. **DDL 命名 `V<yyyyMMddHHmm>__GZ-BEAN-014-<desc>.sql`**，时间戳 > 202606190631；**已应用迁移不可改**，本卡走新文件 ALTER（不改 D11/V1.0 旧文件）；`gz_bean_seat` 表保留不 DROP。
7. **金额 `_cent`**（不用 `_fen`）；snapshot 用 `*_snapshot` 后缀；业务码 `BK-`/`PINDOU-` 全局唯一 DB 约束；`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋，自动填充；UNIQUE 必含 tenant_id）；`version` 乐观锁；`del_flag` 2 值。
8. **SnailJob 非 Quartz**（memory [[scheduler-is-snailjob]]）：禁止 Flyway INSERT sys_job（hard-fail）；任务名 + CRON 写 reports 人工注册。
9. **不动 ruoyi 自带模块源码**；不优化 ruoyi 代码。
10. **券逻辑不在本卡**：仅留 `coupon_id`/`discount_amount_cent` 字段 + 下单事务回滚锁券 hook 位（注释标 D13 COUPON-002 接）；**券面额不计 GMV**（doc/11 §11.3）。
11. **拼豆是否计 4% 分成 GMV 未定** → 本卡仅 business_type=pindou 接入支付链路，**不碰对账中心**（doc/11 §4.6 补注：甲方确认前不计 pindou 进 A/B）。
12. **mock 全链路自测**：`gz.pay.client.mode=mock` 下 mock 产生支付/回调，onPaid → pay_status=paid 在 mock 数据闭环（推进姿态，README §推进姿态）。

### 关键技术决策（承接 ADR-0007/0008）

| # | 决策 | 理由 |
|---|---|---|
| D1 | 原地 ALTER `gz_bean_booking` 加付费列，无子表 | ADR-0008 §4 + 单笔单时段：一笔=一行，改动面可控，单一 booking 真源 |
| D2 | DROP 旧 dedup 唯一索引 + dedup_token 改 NULL | doc/11 §3.5 末段：dedup 随具体座位废弃失效；不可超约由配额计数（§3.6）保证 |
| D3 | seat_id / seat_no_snapshot 改 NULL（不 DROP） | V1.2 起不写但旧数据保留原值（ADR-0008 §3） |
| D4 | 防超卖按活跃 booking `COUNT FOR UPDATE` 悲观锁 | V1 单店小量足够，不引 Redis 座位锁主防护（§3 座位锁废弃） |
| D5 | 双状态机正交（status × pay_status） | ADR-0007：业务态与付费态不互相覆盖；付费前置 + 核销前置 |
| D6 | verify_code 签名因子改 booking_no+sess_date+seat_type | doc/11 §3.8：单笔单时段不再用废弃 seat_id |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | 防超卖并发漏判 → 超约 | §3.6 活跃定义逐字 + `COUNT(活跃) FOR UPDATE` + 单测并发约最后名额（仅一单成功） |
| R2 ⭐ | 双状态机边界混淆（付费前置漏判 / 核销未校验 paid） | ADR-0007 钉死：核销仅 paid+pending；pay_closed 同步 status→cancelled+释放配额；单测覆盖各边 |
| R3 ⭐ | 旧 booking 迁移丢数据 / count 不一致 | 原地补 seat_type（兜底 single）+ 付费列无子表迁移，逐单校验 + 失败留痕；reports 含前后 count（误差 0） |
| R7 ⚠️ | 误建 `gz_bean_booking_unit` 子表 | ADR-0007/0008 钉死单笔单时段无子表；§0 grep `booking_unit` 应空（QA 打回项） |
| R4 | 拼豆是否计 4% GMV 未定 | 仅接入支付链路不碰对账；D15 ADMIN-105 定 |
| R8 | ALTER 大表锁 / seat_type NOT NULL 存量空 | dev 小量可接受；seat_type 先允许加列后由迁移回填，或加列即 NOT NULL DEFAULT 后迁移覆盖 |

---

## §revision（Kevin 批量人验后填，初始空 —— 本卡纯后端 AI 终态，通常无人验）

<!--
- 问题 1：<现象> / 期望：<期望>
AI 修完追加"已修 / 改了 <文件>"。
-->
