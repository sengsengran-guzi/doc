# D12 — 拼豆付费核心（单笔单时段配额 + 双状态机 + 防超卖 + 旧数据迁移）+ 优惠券地基

> 阶段：**V1.2 调整批次**（D11-D14 封顶；原 V1.1 收官 ADMIN-104/105/106/108 重排到末尾 D15）
> 主题：**拼豆付费后端核心**（GZ-BEAN-014：单笔单时段付费预约 + 余量查询接口 + 付费状态机 pay_status + 防超卖按活跃 booking 悲观计数 + 旧数据迁移 + 激活 `PayBusinessType.PINDOU`）**∥ 优惠券地基**（GZ-COUPON-001：券模板 + 用户券 + 发放策略 SPI + admin 批量发放）
> 上一日：[D11](../D11/README.md)（快赢 ORD-110 + 拼豆地基 BEAN-013 类型配额 config + 用户字段/登录态 USER-005 wechat_id / USER-006 资料完善）｜ 下一日：[D13](../D13/README.md)（拼豆 mp + 优惠券抵扣 + 回收地基 + 反向打款）
>
> **本批次起点真相**（主线程 §0 自检 **grep migration 目录实际验证，不假设上游已建**）：BEAN-014 依赖 D11 已建的 `gz_bean_seat_type_config`（类型配额 config，GZ-BEAN-013）+ `gz_user.wechat_id`（GZ-USER-005）；`gz_bean_booking` 付费列 + 座位类型列（`seat_type` / `seat_type_snapshot` / `sess_date` / `slot_start` / `slot_end` / `amount_cent` / `pay_status` / `out_trade_no` / `coupon_id` / `discount_amount_cent`）应**全部不存在 = 本日从零建（原地 ALTER 主表，无子表）**。优惠券两表 `gz_coupon_template` / `gz_user_coupon` 应不存在 = 本日从零建。

---

## 今日目标

V1.2 拼豆付费的**后端骨架立起来** + 优惠券的**数据地基 + 发放能力就位**（两条独立链并行，全 admin/后端，无 mp，本日 AI 终态）：

- **主线 1（拼豆付费核心 ⭐ — GZ-BEAN-014）**：在 D11 类型配额 config 之上，原地 ALTER 主表加付费列 + 座位类型 + 付费双状态机 + 余量查询接口 + 防超卖计数 + 旧数据迁移（**单笔单时段，无子表**）：
  - **单笔单时段模型（ADR-0007/0008 钉死）**：一笔预约 = **一行 `gz_bean_booking` = 1 座位类型 + 1 时段**，单笔金额 = 该类型单价。用户多类型 / 多时段 = **多次预约（多行 booking）**，**不引入 `gz_bean_booking_unit` 子表**。
  - **`gz_bean_booking` 原地 ALTER**（doc/11 §3.5）：加 `seat_type`（座位类型，**不再是 seat_id**）/ `seat_type_snapshot`（下单时类型名快照）/ `sess_date` / `slot_start` / `slot_end`（单时段直接挂主表）/ `amount_cent`（该类型单价快照 = 本笔金额，**非累加**）/ `pay_status` / `out_trade_no` / `coupon_id` / `discount_amount_cent`；旧 `seat_id` V1.2 起不再写，旧数据保留原值。
  - **付费双状态机（ADR-0007）**：`status`（pending/used/cancelled/no_show）与 `pay_status`（unpaid/paying/paid/pay_closed/refunded）**正交并行**；付费前置 —— 支付成功（pay_status=paid）后预约才正式占名额/可核销。免费单（price_cent=0 无券）兜底直接 paid。
  - **余量查询接口**：mp 查某门店某日各 `(类型, 时段)` 剩余可约数量 = `gz_bean_seat_type_config.quantity − COUNT(活跃 booking WHERE store+seat_type+date+slot)`；返每档「还剩 N / 已满」供 D13 BEAN-015 选座显余量。
  - **防超卖（ADR-0008 配额并发口径，按活跃 booking 计数）**：下单事务内对该 `(store, seat_type, sess_date, slot_start)` `COUNT 活跃 booking FOR UPDATE` 比对 `gz_bean_seat_type_config.quantity`，满则**拒单**（事务回滚）。单笔单时段一笔只占一个名额 → **无「部分成交」问题**。V1 单店小量，悲观计数足够，**不引 Redis 座位锁**（§3 座位锁废弃）。
  - **旧数据迁移（原地 ALTER 补字段，无子表迁移）**：旧 §3 免费 booking（本就单类型单时段）原地补 `seat_type`（兜底 `single`）+ 付费列（标历史「已付 0 元」），失败留痕人工处理。
  - **激活 `PayBusinessType.PINDOU`**：拼豆走 §6 业务支付链路（`out_trade_no` 前缀 `PINDOU-`，复用 `gz_pay_transaction` business_type=pindou，amount_cent=实付）；后端建支付单 + onPaid 分发 hook（mp 拉起留 D13 BEAN-015）。
- **主线 2（优惠券地基 — GZ-COUPON-001）**：代金券模板 + 用户券 + 发放策略 SPI + admin 批量发放（独立链，与 BEAN-014 互不阻塞）：
  - **`gz_coupon_template`**（doc/11 §11.1）：template_no(`CPN-`) / name / discount_type(`cash` V1.2 唯一) / amount_cent / applicable_business(`pindou`) / valid_days / total_quota / issued_count(乐观锁防超发) / **issue_strategy**(`manual`/`register_window`/`event`，V1.2 仅 manual) / **issue_config_json**(策略参数 JSON，manual 可空) / status(active/paused/archived)。
  - **`gz_user_coupon`**（doc/11 §11.2）：coupon_no(`UC-`) / template_id / user_id / amount_snapshot_cent / status(unused/locked/used/expired) / gained_time / expire_time(`= gained_time + valid_days`) / used_time / related_pay_out_trade_no。
  - **发放策略 SPI**（doc/11 §11，ICouponIssuanceStrategy）：**V1.2 实现 `ManualIssuanceStrategy`**（admin 选用户列表 / 上传名单 + 选模板 → 每用户生成一张 unused 券，发放事务内乐观锁校验 `issued_count + N <= total_quota`，配额耗尽拦截 + 写操作日志）；**预留**（留接口 + 不实现）`RegisterWindowStrategy`（按 register_time 区间）+ `EventIssuanceStrategy`（业务事件触发，**含 D14 回收完成发 `CouponIssuanceEvent` 钩子**）。V1.2 只跑 manual，其余留接口 + 事件钩子，甲方填策略不返工。
  - **admin 模板 CRUD**：含 issue_strategy 选择（V1.2 仅 manual 可选）+ 暂停/归档。

完工后（本日全后端/admin，AI 终态）：
- 后端具备「下单 → 单笔配额校验 → 建一行 booking + 建 pindou 支付单 → onPaid 推 paid 占名额」的完整事务能力 + 余量查询接口（mp 调用留 D13）。
- owner 在 admin 可建代金券模板（manual 策略）、批量发券给指定用户/名单，发放配额受 `total_quota` 乐观锁保护；register_window/event 策略接口预留可编译。
- 旧免费 booking 已原地迁移补 seat_type + 付费列（无子表），历史单只读展示不丢信息。

## Ticket 清单（2 个 / 全后端·admin AI 终态）

| Ticket | 标题 | 端 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| **GZ-BEAN-014 ⭐** | 单笔单时段付费预约 + 余量查询接口 + 防超卖按 booking 计数 + 旧数据迁移 + 激活 PINDOU | be | **L** | GZ-BEAN-013（D11）+ GZ-USER-005（D11）+ GZ-PAY-101（已交付）| pending |
| GZ-COUPON-001 | 券模板 + 用户券 + 发放策略 SPI（manual 实现 + 预留 register_window/event）+ admin 批量发放 | be + admin | M | GZ-SYS-003（用户表）+ GZ-ADMIN-001 | pending |

ticket 任务卡随本日 closing 细化（`tickets/<TICKET-ID>.md`）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图**：

```
D11 ✅ BEAN-013（gz_bean_seat_type_config 配额 config）
D11 ✅ USER-005（gz_user.wechat_id）
        │
        ▼
GZ-BEAN-014 ⭐ ━━━━━━━━━━━━━━━┓  (拼豆付费后端核心，独立链)
                              ┃
GZ-COUPON-001 ━━━━━━━━━━━━━━━┛  (优惠券地基，独立链，不依赖 BEAN-014)
                              ▼
                         （D13 接：BEAN-015 mp + COUPON-002 抵扣）
```

- **BEAN-014 ∥ COUPON-001 完全并行**：COUPON-001 仅建表 + admin 发放，**不依赖** BEAN-014 的下单事务（抵扣逻辑在 D13 COUPON-002 才接 BEAN-014）。
- BEAN-014 依赖 D11 的 BEAN-013（配额 config）+ USER-005（wechat_id）；主线程 §0 grep migration 实际校验上游表/列已建。

## 派单方式

```
开始 d12
```

主线程动作：
1. 读 D12/README.md + 依赖图，做 §0 自检（grep migration 目录确认 `gz_bean_seat_type_config`（BEAN-013）+ `gz_user.wechat_id`（USER-005）已建；`gz_bean_booking` 付费列/seat_type / `gz_coupon_template` / `gz_user_coupon` 应不存在 = 从零建；**`gz_bean_booking_unit` 不应建 = 单笔单时段无子表**）。
2. **第一波并行 spawn**：BEAN-014 ⭐ + COUPON-001 两条独立链同时起，各自 kevin-coder Tier 1A。
3. 两卡全完工后 → **一个 kevin-qa 串行整批 Tier 1B**（后端集成 + 单测 + API 契约；纯后端/admin，AI ✅ 即终态，**无人验**）。
4. 任一 AI 测试 ❌ → 闭环回 kevin-coder 修（不打扰 Kevin）。
5. 两卡全 ✅ → 日终 closing + 写 D13/README.md。

> 编排沿用 D10/D11 模式：主线程 §0 grep migration 自检 → 按依赖 spawn kevin-coder（各自 Tier 1A）→ 全完工后一个 kevin-qa 串行整批 Tier 1B（见 memory [[tier1b-qa-dispatch-by-mainthread]] + [[dev-infra-run-recipe]]）。

## 今日特殊约束 ⭐

### GZ-BEAN-014 拼豆付费核心（ADR-0007 + ADR-0008 双 ADR 必读全文）

> **doc/10 §11（拼豆付费预约全流程，单笔单时段）+ doc/11 §3.4/§3.5/§3.6/§3.8（座位类型 config / 主单付费列+座位类型 / 余量按 booking 计数 / 双状态机口径）是唯一权威，AI 实施前必读全文。ADR-0007（双状态机 status×pay_status 正交，单笔单时段）+ ADR-0008（座位类型配额模型 + 按 booking 计数 + 旧数据迁移）是决策权威。**
>
> **⚠️ 单笔单时段（ADR-0007/0008 钉死）**：一笔预约 = **一行 `gz_bean_booking` = 1 座位类型 + 1 时段**，单笔金额 = `amount_cent`（该类型单价快照）。用户多类型 / 多时段 = 多次预约（多行 booking），**不引入 `gz_bean_booking_unit` 子表**、无 `total_amount_cent` 累加。`seat_type` / `sess_date` / `slot_start` / `slot_end` 直接挂主表。

- **双状态机正交（ADR-0007 钉死）**：
  - `status`（业务态，doc/11 §3.8）：`pending` / `used` / `cancelled` / `no_show`；与 `pay_status` 正交并行，**不互相覆盖**。
  - `pay_status`（付费态，doc/11 §3.8 + 附录 A.15）：`unpaid` → `paying` → `paid`；旁路 `pay_closed`（超时/放弃，主单 status 同步 → cancelled，释放配额 + 回滚锁券）/ `refunded`（admin 人工特例，未来 ticket）。
  - **付费前置**：提交预约 → 校验配额 → 锁券（如选）→ 建主单 `status='pending'` + `pay_status='unpaid'` → 发起支付 `pay_status='paying'`；**支付成功 `pay_status='paid'` 后该 booking 才正式占名额/可核销**。
  - **免费单兜底**：门店该类型 `price_cent=0` 且无券需求 → 实付 0 → 不建支付单，`pay_status` 直接置 `paid`（`out_trade_no` 留 NULL），`status='pending'`。
  - **核销前置**：仅 `pay_status='paid'` 的 pending 单可被店员核销（`status → 'used'`，pay_status 不变）。
- **防超卖配额计数（ADR-0008，doc/11 §3.6 末段「活跃 booking 定义」逐字落地，按主表活跃 booking 行计数）**：
  - 「活跃」= `gz_bean_booking` 处于占位态（`pay_status IN ('paying','paid')`，含付款中暂占）；`cancelled` / `no_show` / `pay_closed` / `refunded` 释放配额。
  - 下单事务内对该单元 `SELECT COUNT(*) FROM gz_bean_booking WHERE store_id=? AND seat_type=? AND sess_date=? AND slot_start=? AND <活跃> FOR UPDATE` 比对 `gz_bean_seat_type_config.quantity`，`< quantity` 才放行；满则**拒单**（事务回滚）。单笔单时段一笔只占一个名额 → **无「部分成交」问题**，约满直接拒单。
  - 核心索引：`gz_bean_booking (tenant_id, store_id, seat_type, sess_date, slot_start)`（doc/11 §3.6）。
  - V1 单店小量，**悲观计数足够，不引 Redis 座位锁**（§3 座位锁废弃；doc/11 §3.9 仅保留 `gz:bean:lock:quota:*` + `user_submit` 防连点辅助锁，非主防护）。
  - unpaid 占配额超时回收 = doc/10 §11.N13a（默认 15 分钟 SnailJob，Q11.2）。
- **余量查询接口（供 D13 BEAN-015 选座显余量）**：mp GET 某门店某日各 `(类型, 时段)` 剩余可约数 = `quantity − COUNT(活跃 booking WHERE store+seat_type+date+slot)`；返每档「还剩 N / 已满」。
- **金额 / 实付口径（doc/11 §3.5 / §11.3，单笔）**：`amount_cent`（该座位类型单价下单 snapshot = 本笔金额，**非累加**）；`discount_amount_cent = 命中券 amount_snapshot_cent`（下限不超 amount）；`gz_pay_transaction.amount_cent = amount − discount`（实付，下限 0）。**券面额不计 GMV**（本日仅留 `coupon_id` / `discount_amount_cent` 字段 + 下单事务 hook，券锁定/核销逻辑由 D13 COUPON-002 落地）。
- **激活 PINDOU（doc/10 §11 前置 + doc/11 §3.5）**：`PayBusinessType.PINDOU` 接入 §6 业务支付链路；`out_trade_no` 前缀 `PINDOU-`；`gz_pay_transaction(business_type='pindou')`；onPaid 回调分发到拼豆（`PayCallbackHandler` 推 `pay_status=paid` + 生成核销码 `verify_code`，签名因子用主表 `sess_date` + `seat_type`，doc/11 §3.8，**不再用废弃 seat_id**）。
- **旧数据迁移（ADR-0008，原地 ALTER 补字段，无子表迁移）**：旧免费 booking（本就单类型单时段）原地补 `seat_type`（取旧座位类型，缺则兜底 `single`）+ `sess_date`/`slot` 取主单旧值 + `amount_cent=0` + 付费列；`pay_status` 旧已核销单置 `paid` + `status` 保留；迁移脚本逐单校验 + 失败留痕。**reports 必含迁移前后 count 比对 raw output**。
- **V1.2 唯一约束语义迁移（doc/11 §3.5 末段）**：V1.0 基于具体 seat_id 的「同座位×同时段不可重复 pending」dedup 唯一索引**已随具体座位废弃而失效**；改配额模型后由 §3.6 配额计数保证不可超约，**不再依赖 booking 主单 dedup 唯一索引**。

### GZ-COUPON-001 优惠券地基（doc/11 §11 + 抵扣口径）

> **doc/11 §11.1/§11.2/§11.3（券模板 / 用户券 / 抵扣 + GMV 口径）+ 附录 A.17/A.18/A.19（券态 / 模板态 / 折扣类型字典）是唯一权威。doc/10 §12（优惠券流）是业务流权威。**

- **代金券（V1.2 唯一形态）**：`discount_type='cash'`（固定抵扣额，预留 `full_reduce`/`percent`）；`applicable_business='pindou'`（V1 仅拼豆抵扣，预留扩展）。
- **发放策略 SPI（钉死，doc/11 §11）**：发放方式做成可插拔策略 `ICouponIssuanceStrategy` + `gz_coupon_template.issue_strategy`（`manual`/`register_window`/`event`）+ `issue_config_json`（策略参数）。**V1.2 仅实现 `ManualIssuanceStrategy`**（admin 选用户 / 上传名单）；**预留** `RegisterWindowStrategy`（按 `gz_user.register_time` 区间）+ `EventIssuanceStrategy`（业务事件触发，**含 D14 回收完成发 `CouponIssuanceEvent` 钩子** = RECYCLE-003 paid → 监听器按模板 config 发券）。V1.2 只跑 manual，其余**留接口 + 事件钩子（不实现）**，甲方填策略不返工。reports 验 register_window/event 接口存在可编译 + event 监听钩子留位。
- **抵扣 / GMV 口径（doc/11 §11.3，钉死，单笔）**：拼豆实付 `= 单笔金额 amount_cent − amount_snapshot_cent`，**下限 0**（券面额超单笔金额时实付 0，差额不退不找零）；**券面额（amount_snapshot_cent）不计 GMV**（不是平台收入，是让利）。本日仅建表 + 发放，**抵扣计算 + 锁定/核销/回滚在 D13 COUPON-002 落地**（依赖 BEAN-014 下单事务）。
- **发放配额防超发**：`gz_coupon_template.issued_count` 乐观锁（version）；admin 批量发放事务内校验 `issued_count + N <= total_quota`（NULL = 不限），耗尽拦截（doc/11 §11.4 F11.4）。
- **券态机（doc/11 §11.2，本日只产 unused）**：发放生成 `unused` 券，`expire_time = gained_time + template.valid_days`；`unused→locked→used` / `locked→unused` / `unused→expired` 流转由 D13 COUPON-002 落地（本日只建表 + 字段 + 发放）。
- **不建独立 use 流水表**：核销以 `gz_user_coupon.status` + `related_pay_out_trade_no` 追溯（doc/11 §11 引言）。

### 全局

- **admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统）**：COUPON-001 admin 模板 CRUD + 发放页全部 plus-ui BizTable + Element Plus 默认 + ruoyi 自带组件，**不调样式、不引 mockup 像素**（admin 不评判视觉）。
- **本日无 mp ticket → 无 Tier 2 可达约束、无人验**（BEAN-014 纯后端，COUPON-001 后端+admin）；mp 拼豆付费页是 D13 BEAN-015 / mp 选券是 D13 COUPON-003。
- **menu_id 段（doc/11 §10.3）**：优惠券 → **12000 段**（12000 目录 / 12001 模板 / 12002 发放记录）；拼豆复用 **6000 段**（BEAN-014 无新增 admin 菜单，预约管理沿用 6000 现有）。
- **包名（CLAUDE.md §6 #4）**：拼豆 `org.dromara.gz.bean.*`；优惠券独立域 `org.dromara.gz.coupon.*`；支付链路复用 `org.dromara.gz.common.pay.*`（PayBusinessType / PayCallbackHandler）。
- **字段/命名硬约束（每卡复核）**：金额 `_cent`（不用 `_fen`）/ snapshot 用 `*_snapshot` 后缀（`amount_snapshot_cent` / `seat_type_snapshot`）/ 业务码 `域大写-yyyyMMdd-6位序号`（`BK-` / `CPN-` / `UC-` / `PINDOU-`，全局唯一 DB 约束）/ 乐观锁 `version`（issued_count 防超发 + booking 状态推进）/ `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋，走自动填充；UNIQUE 必含 tenant_id）/ `del_flag` 2 值。
- **SnailJob（非 sys_job）**：BEAN-014 的 unpaid 超时回收 + no_show 凌晨任务如本日落地 → `@Component + @JobExecutor` 薄壳 + 可单测 service；**禁止** Quartz / Flyway INSERT sys_job（启动 hard-fail）；模块 pom 显式加 `ruoyi-common-job`；任务名 + CRON 写进 reports 由人在 SnailJob 控制台注册。（COUPON 过期 SnailJob 在 D13 COUPON-002。）
- **DDL 命名 `V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`**（时间戳 > 已有最大版本；**已应用迁移不可改**，改 schema 新建更大时间戳文件）；`gz_bean_booking` 加付费列走 ALTER 新迁移文件（不改 D11/V1.0 旧文件）；**不动 ruoyi 自带模块**。
- **不要 commit**：2 卡全完工 + AI 测试全 ✅ 后再统一 commit（本日无人验，AI ✅ 即终态）。

## 推进姿态 = Mock 全链路自测

- 拼豆付费支付源是 `gz_pay_transaction`（business_type=pindou），在 `gz.pay.client.mode=mock` 下由支付通道 mock 全链路产生支付/回调，BEAN-014 的 onPaid → pay_status=paid 在 mock 数据上闭环。
- 真实商户号 / 0.01 元端到端 / 拼豆是否计 4% 分成 GMV 列为【外部前置 / D15 待定】（doc/11 §4.6 补注：甲方书面确认前对账中心默认不计 pindou 进 A/B 流水）；不当默认就绪。

## 与昨日 reports 对账（D11）

D11 完工后应交付（**主线程 §0 自检 grep migration 目录实际验证，不假设**）：
- GZ-BEAN-013 → `gz_bean_seat_type_config`（store_id / seat_type / quantity / price_cent / enabled / sort_no，UNIQUE(tenant_id, store_id, seat_type)）+ admin 配数量/单价页 + 废弃 `gz_bean_seat` 预约用途（表保留不 DROP）。BEAN-014 的 `amount_cent` 单价 snapshot 源 + 配额计数对照源（quantity）全靠它。
- GZ-USER-005 → `gz_user.wechat_id VARCHAR(64) NULL`（手动填）+ mp 资料页录入。BEAN-014 的 `wechat_id_snapshot` 取它（付款前采集，doc/10 §11.N6）。
- 字典 `gz_bean_seat_type`（single/double/quad）已录（BEAN-013）。

进 D12 前主线程 §0 自检校验（**grep 实际存在的表/列，不假设**）：
```bash
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'GZ-BEAN-013|GZ-USER-005|seat_type_config'
grep -rl 'gz_bean_seat_type_config\|wechat_id' code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
# gz_bean_booking 付费列/seat_type / gz_coupon_template / gz_user_coupon 应当查不到（= 本日从零建，正常）
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'gz_coupon|GZ-BEAN-014|GZ-COUPON-001' || echo "本日产物不存在 = 正常，从零建"
# ⚠️ gz_bean_booking_unit 不应出现（单笔单时段无子表）：
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep 'booking_unit' && echo "⚠️ 异常：单笔单时段不应有子表" || echo "无 booking_unit = 正常（单笔单时段无子表）"
```
上游表/列齐 → 开工；缺则 STOP 报 Kevin（先回 D11 收尾）。D11 summary.md「对下游 ticket 的提示」段（seat_type 枚举 / price_cent 单位 / wechat_id 采集时机）在 BEAN-014 实施前主线程逐条对齐。

## 完成判定（DoD）

- [ ] 2 个 ticket 任务卡 §revision 段空（BEAN-014 / COUPON-001）
- [ ] 2 个 reports/<T>.md 写完（含 §0 自检 grep migration raw output + §N 完工 + ≥ 3 个代码 block raw output + ADR-0007/0008 已读摘录）
- [ ] **BEAN-014 ⭐ reports 必含**：① 单笔单时段下单事务 raw output（一行 booking，amount_cent = 类型单价，无累加无子表）；② 余量查询接口 raw output（quantity − 活跃 booking 计数 = 还剩 N / 已满）；③ 防超卖并发压测 raw output（构造并发约同一 `(类型,日期,时段)` 最后名额 → 仅一单成功，其余拒单，无部分成交）；④ 旧 booking 迁移前后 count 比对 raw output（原地补 seat_type + 付费列，迁移前后 count 一致，失败留痕 0 或人工清单）；⑤ `git diff`/迁移文件确认**无 `gz_bean_booking_unit` 子表**
- [ ] COUPON-001 reports 含：批量发放乐观锁 raw output（`issued_count + N > total_quota` 时拦截，不超发）+ **发放策略 SPI**（manual 发放生效 + register_window/event 接口存在可编译 + event 监听钩子留位）
- [ ] mvn install（ruoyi-gz-bean / ruoyi-gz-coupon / ruoyi-gz-common -am）+ plus-ui build:prod 全绿（COUPON-001 含 admin）
- [ ] BEAN-014 SnailJob（unpaid 超时回收 / no_show 凌晨任务，若本日落地）任务名 + CRON 写进 reports；**确认无 Flyway INSERT sys_job**
- [ ] Tier 1A + 1B（kevin-coder 自测 + kevin-qa：后端集成 + 单测 + COUPON admin Playwright E2E）全 ✅ → **AI ✅ 即终态，本日无人验**（无 mp ticket）
- [ ] 单测覆盖：BEAN-014 拼豆配额并发 + 付费状态机流转 ≥ 80%（CLAUDE.md §8.1）；COUPON-001 发放乐观锁 + manual 策略 happy path
- [ ] `gz_bean_booking` 付费列 + seat_type 走 ALTER 新迁移文件（未改 D11/V1.0 旧迁移，**原地 ALTER 无子表**）；`gz_bean_seat` 表保留未 DROP（仅停用预约用途）

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | BEAN-014 防超卖并发漏判 → 同一 `(类型,日期,时段)` 超约 | doc/11 §3.6 活跃 booking 定义逐字落地 + `COUNT(活跃 booking) ... FOR UPDATE` 悲观锁 + 单测覆盖并发约最后名额（仅一单成功，其余拒单，单笔单时段无部分成交） |
| R2 ⭐ | 双状态机 status/pay_status 边界混淆（付费前置漏判 / 核销未校验 paid）| ADR-0007 钉死：核销仅 `pay_status='paid'` 的 pending 单；pay_closed 同步 status→cancelled + 释放配额 + 回滚锁券；单测覆盖各流转边 |
| R3 ⭐ | 旧免费 booking 迁移丢数据 / count 不一致 | ADR-0008 迁移：旧单**原地补 seat_type（兜底 single）+ 付费列（amount_cent=0）无子表迁移**，逐单校验 + 失败留痕；reports 必含迁移前后 count 比对（误差 = 0） |
| R7 ⚠️ | 误建 `gz_bean_booking_unit` 子表（沿用旧多单元框架）| ADR-0007/0008 钉死单笔单时段：一笔 = 一行 booking，无子表；§0 自检 grep `booking_unit` 应为空；QA 打回项 |
| R4 | 拼豆是否计 4% 分成 GMV 未定 → 对账归属悬空 | 本日仅 business_type=pindou 接入支付链路（不碰对账）；GMV 口径 D15 ADMIN-105 定（doc/11 §4.6 补注：甲方确认前不计 pindou 进 A/B） |
| R5 | COUPON-001 批量发放超发（并发发券击穿 total_quota）| `issued_count` 乐观锁 version + 事务内 `issued_count + N <= total_quota` 校验；单测覆盖并发发券 |
| R6 | menu 段冲突（12000 优惠券与已有段重叠）| §0 自检 grep 现有 sys_menu INSERT 确认 12000 段空闲（doc/11 §10.3 已规划）；拼豆复用 6000 不新增菜单 |

---

## 日终 closing 命令

```bash
cd doc/daily/D12
cat reports/*.md > summary.md
git add -A && git commit -m "D12: 拼豆付费核心 BEAN-014（单笔单时段配额+余量接口+双状态机+防超卖按 booking 计数+旧数据迁移+激活 PINDOU）+ 优惠券地基 COUPON-001（发放策略 SPI+manual）"
# 然后写 D13/README.md（已存在则核对 ticket 清单 / 依赖与本日 reports「对下游提示」一致）
```
