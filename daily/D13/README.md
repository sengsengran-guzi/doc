# D13 — 拼豆付费 mp（单笔单时段+显余量）+ 优惠券抵扣/选券 + 回收地基 + 反向打款链路（mock）

> 阶段：**V1.2 调整批次**（D11-D14 封顶；原 V1.1 收官 ADMIN-104/105/106/108 重排到末尾 D15）
> 主题：**拼豆付费 mp 落地**（GZ-BEAN-015：选 1 类型 1 时段 + 显余量）**+ 优惠券抵扣链路 + mp 选券**（GZ-COUPON-002 → 003）**+ 反向打款链路 mock 跑通**（GZ-PAY-105，独立）**+ 回收价目表地基**（GZ-RECYCLE-001，独立）
> 上一日：[D12](../D12/README.md)（拼豆付费核心 BEAN-014 单笔单时段 + 优惠券地基 COUPON-001 发放策略 SPI）｜ 下一日：[D14](../D14/README.md)（回收完成 RECYCLE-002/003 + tabbar 重构 SYS-010 + 扭蛋收尾 GACHA-111）
>
> **本批次起点真相**（主线程 §0 自检 **grep migration 目录实际验证，不假设上游已建**）：BEAN-015 依赖 D12 已建的 `gz_bean_booking` 付费列 + 座位类型列（`seat_type` / `sess_date` / `slot_start/end` / `amount_cent` / `pay_status`，**单笔单时段无子表**）+ 余量查询接口 + 激活的 `PayBusinessType.PINDOU`；COUPON-002 依赖 D12 `gz_coupon_template` / `gz_user_coupon` 两表 + BEAN-014 下单事务 hook（`gz_bean_booking.coupon_id` / `discount_amount_cent` 字段已建）；PAY-105 的 `gz_pay_payout_transaction` / `gz_pay_payout_callback_log` 应**全部不存在 = 本日从零建**；RECYCLE-001 的 `gz_recycle_price_rule` 应不存在 = 本日从零建。

---

## 今日目标

V1.2 拼豆付费链路**端到端打通到 mp** + 优惠券**抵扣闭环** + 回收与反向打款的**地基/能力就位**（四条链并行，含 2 个 mp 人验 + 2 个后端 mock AI 终态）：

- **主线 1（拼豆 mp 付费页 — GZ-BEAN-015，mp 人验）**：在 D12 后端核心之上落 mp 端（C 日漫海报浓墨，**单笔单时段**）：
  - bean/index 单页：选 **1 个座位类型 + 1 个时段**（单选）→ 每个 `(类型,日期,时段)` **实时显余量**「还剩 N 个单人座」/「已满」灰显（调 D12 BEAN-014 余量查询接口 = quantity − 活跃 booking 计数）→ 金额 = 该类型单价（单笔，无累加）。
  - 选优惠券模块（仅 unused + 适用拼豆 + 未过期，依赖 COUPON-003）→ 展示实付 = 单笔金额 − 券面额（下限 0）。
  - **付款前采集**：`gz_user.mobile` 空 → 原生 `getPhoneNumber`（沿用 §1.N8）；`gz_user.wechat_id` 空 → 表单**手动填微信号**（GZ-USER-005）；两者都采集成功才能提交。
  - 提交 → 下单事务（BEAN-014，一行 booking）→ `wx.requestPayment`（JSAPI）→ onPaid → 跳预约详情（门店 / 类型 / 时段 / 实付 / 核销码二维码 / pay_status）；如需多类型/多时段 = 再下一笔（多次预约）。
- **主线 2（优惠券抵扣 + mp 选券 — GZ-COUPON-002 → 003）**：
  - **COUPON-002（后端，AI 终态）**：拼豆下单券锁定/核销/回滚 + 过期 SnailJob。`unused → locked`（下单事务，写 `gz_bean_booking.coupon_id`）→ `locked → used`（onPaid，写 `related_pay_out_trade_no`，**实付 = 单笔金额 − 券面额，amount_cent = 实付，券面额不计 GMV**）→ `locked → unused`（取消/支付关闭回滚）；过期 SnailJob 扫 `unused` 且 `expire_time` 已过 → `expired`。
  - **COUPON-003（mp 人验）**：「我的优惠券」列表（unused/used/expired tab，入口在「我的」）+ 拼豆付款页选券模块（被 BEAN-015 消费）。
- **主线 3（反向打款链路 mock — GZ-PAY-105，独立，AI 终态）**：`IWechatPayClient` 扩 `transferToUserWallet` + `queryTransferByOutNo`；建 `gz_pay_payout_transaction`（独立 PayoutStatus）+ `gz_pay_payout_callback_log`；查单 SnailJob 轮询 `processing → success/failed`；`out_payout_no` + `batch_id` 双重幂等。**mock 跑通 created→processing→success + failed 分支单测**（仿 ADR-0003/0006）。
- **主线 4（回收价目表地基 — GZ-RECYCLE-001，独立，AI 终态）**：`gz_recycle_price_rule`（品类 × 数量区间 → 单价 + 时长）+ admin 价目表配置页 + 区间不重叠校验 + 字典 `gz_recycle_category`。

完工后：
- 甲方/Kevin 真机：mp 拼豆选 1 类型 1 时段（看余量「还剩 N / 已满」）→ （可选）选券 → 采手机/微信号 → mock 支付成功 → 看到预约详情 + 核销码；在「我的优惠券」看券列表三态。
- 后端：反向打款在 mock 下 created→processing→success 全跑通 + failed 可重试不重复转账；owner 在 admin 配回收价目表（品类×数量→单价+时长）+ 反向打款单挂 5100 段。

## Ticket 清单（5 个 / 2 mp 人验 + 3 后端·admin AI 终态）

| Ticket | 标题 | 端 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| GZ-BEAN-015 | mp 拼豆付费页（选 1 类型 1 时段 + 显余量 → 采手机/微信号 → JSAPI，单笔金额）| mp + be | M | GZ-BEAN-014（D12）+ GZ-COUPON-003 + GZ-USER-005（D11）| pending |
| GZ-COUPON-002 | 拼豆抵扣计算（锁定/核销/回滚）+ 过期 SnailJob | be | M | GZ-COUPON-001（D12）+ GZ-BEAN-014（D12）| pending |
| GZ-COUPON-003 | mp 选券 + 我的券列表 | mp + be | S | GZ-COUPON-002 | pending |
| GZ-PAY-105 | 反向打款链路 + mock + payout 表 + 查单 SnailJob | be | **L** | GZ-PAY-001（IWechatPayClient）；**transferbatch SDK 待 Kevin 批准** | pending |
| GZ-RECYCLE-001 | 回收价目表 + 时长规则（admin）| be + admin | M | GZ-ADMIN-001 / GZ-SYS-005（字典）| pending |

ticket 任务卡随本日 closing 细化。mp ticket（BEAN-015 / COUPON-003）**需 Tier 2 可达 + 进 progress.md「人验」列**。

**依赖图**：

```
D12 ✅ BEAN-014（单笔单时段配额下单事务 + 余量接口 + pay_status + PINDOU）
D12 ✅ COUPON-001（gz_coupon_template / gz_user_coupon）
        │
        ├──────────────┐
        ▼              ▼
   COUPON-002 ───→ COUPON-003 ───┐  (抵扣后端 → mp 选券)
   (←001,014)      (←002)        ▼
                            GZ-BEAN-015  (mp 拼豆付费页，←014 + COUPON-003 选券 + USER-005)
                                  │ (mp 人验)
                                  ▼

GZ-PAY-105 ━━━━━━━━━━━━━━━┓  (反向打款链路 mock，独立链，不依赖拼豆/优惠券)
GZ-RECYCLE-001 ━━━━━━━━━━┛  (回收价目表地基，独立链)
   （二者 AI 终态 mock；为 D14 RECYCLE-002/003 铺路）
```

- **PAY-105 ∥ RECYCLE-001 与拼豆/优惠券链完全独立并行**（互无依赖）。
- **拼豆/优惠券链内部串行**：COUPON-002（后端抵扣）→ COUPON-003（mp 选券）→ BEAN-015 消费选券模块。COUPON-002 同时依赖 D12 的 COUPON-001（表）+ BEAN-014（下单事务）。
- BEAN-015 是 mp 付费页，依赖 BEAN-014 后端 + COUPON-003 选券模块 + USER-005 微信号采集；建议在 COUPON-003 完工后起。

## 派单方式

```
开始 d13
```

主线程动作：
1. 读 D13/README.md + 依赖图，做 §0 自检（grep migration 确认 `gz_bean_booking.seat_type/sess_date/amount_cent/coupon_id/discount_amount_cent/pay_status`（BEAN-014，**单笔单时段无子表**）+ `gz_coupon_template`/`gz_user_coupon`（COUPON-001）+ `gz_user.wechat_id`（USER-005）已建；`gz_pay_payout_transaction` / `gz_recycle_price_rule` 应不存在 = 从零建）。
2. **⚠️ PAY-105 开工前确认 transferbatch SDK Kevin 已批准**（铁律 #8）：未批准则 PAY-105 **仅落 mock 实现 + 抽象方法 + payout 表**（real 实现接 V3 `/v3/transfer/batches` 部分留 hook 注释，标 `待 SDK 批准`），不私引 `com.wechat.pay.java...transferbatch` 依赖。
3. **第一波并行 spawn**：PAY-105 + RECYCLE-001（两条独立链）+ COUPON-002（拼豆/优惠券链起点）同时起，各自 Tier 1A。
4. COUPON-002 ✅ → spawn COUPON-003 → COUPON-003 ✅ → spawn BEAN-015。
5. kevin-coder 每卡完工后 → 全完工时**一个 kevin-qa 串行整批 Tier 1B**：
   - 纯后端/admin（COUPON-002 / PAY-105 / RECYCLE-001）→ AI Tier 1A + 1B 全 ✅ 即终态，**无人验**
   - mp（BEAN-015 / COUPON-003）→ 进 progress.md「人验」列待 Kevin 批量验（kevin-qa Tier 1B 显式检查 mp 可达性 + vitest unit）
6. 任一 AI 测试 ❌ → 闭环回 kevin-coder 修。
7. 5 卡 AI 全 ✅ → 日终 closing + 写 D14/README.md。

> 编排沿用 D10/D11 模式：主线程 §0 grep migration 自检 → 按依赖 spawn kevin-coder（各自 Tier 1A）→ 全完工后一个 kevin-qa 串行整批 Tier 1B（见 memory [[tier1b-qa-dispatch-by-mainthread]] + [[dev-infra-run-recipe]] + [[mp-build-devtools-hang]]）。

## 今日特殊约束 ⭐

### GZ-PAY-105 反向打款链路（ADR-0006 必读全文 + transferbatch SDK 待 Kevin 批准 ⚠️）

> **doc/10 §14（反向打款时序）+ doc/11 §4.8/§4.9/§4.10（payout 单 / 回调流水 / 待澄清）+ 附录 A.16（PayoutStatus）是唯一权威。ADR-0006（mock 降级 / out_payout_no 幂等 / 主动查单优先）是决策权威，实施前必读全文。**

- **⚠️ 新依赖待批准（铁律 #8，doc/11 §4.10 F4.6）**：`com.wechat.pay.java...transferbatch` SDK **未经 Kevin 批准不得引入**。本日落地策略 = **mock 跑通**（`gz.pay.client.mode=mock`，仿 ADR-0003）：
  - `IWechatPayClient` 扩抽象方法 `transferToUserWallet(req)` + `queryTransferByOutNo(outNo)`（承接 ADR-0003 抽象）。
  - **mock 实现**完整落地（created→processing→success + failed 分支可单测）；**real 实现**接 V3 `/v3/transfer/batches` 的部分如 SDK 未批准则留 hook + 注释 `// 待 transferbatch SDK 批准（ADR-0006 / 铁律 8）`，不私引依赖。
  - 商户「商家转账」权限到位 + SDK 批准后切真实（外部前置 gate，不阻塞本日 mock 闭环）。
- **独立 PayoutStatus 枚举（doc/11 §4.8 / 附录 A.16）**：`created` → `processing` → `success`；旁路 `failed`（可重试，重置 `created`）/ `cancelled`。**不复用**正向支付 `gz_pay_transaction.status`。
- **主动查单优先（ADR-0006，doc/11 §4.10 F4.7）**：商家转账回调到达性弱，**以主动查单为准**（`processing` 态 SnailJob 周期 `queryTransferByOutNo` 确认 success/failed）；`gz_pay_payout_callback_log` 仅存档备查。
- **双重幂等（doc/11 §4.8）**：`out_payout_no`（`PAYOUT-yyyyMMdd-6位序号`，UNIQUE）+ `batch_id`（UNIQUE WHERE NOT NULL）防同一回收单重复转账；`version` 乐观锁兜底。
- **业务字段（doc/11 §4.8）**：`business_type='recycle'`（V1.2 唯一反向出账）/ `business_order_no = appointment_no`（D14 RECYCLE-003 触发时回填）/ `receiver_openid`（从回收单快照）/ `amount_cent = final_amount_cent`。**本日 PAY-105 仅建链路 + mock；回收业务触发在 D14 RECYCLE-003**（PAY-105 提供能力，RECYCLE-003 调用）。
- **回收反向出账独立核算（doc/11 §4.6 补注）**：是平台→用户出账，**不计 GMV、不参与 4% 分成**；不进 §9 对账中心 GMV 口径。
- **SnailJob（非 sys_job）**：查单轮询 = `@Component + @JobExecutor` 薄壳 + 可单测 service；**禁止** Quartz / Flyway INSERT sys_job；模块 pom 显式加 `ruoyi-common-job`；任务名 + CRON 写进 reports 由人在控制台注册。
- **reports 必含**：mock 全链路 raw output（created→processing→success）+ failed 分支单测 raw output + **幂等 raw output**（重复 `out_payout_no` 触发不二次转账）。

### GZ-BEAN-015 拼豆 mp 付费页（C 日漫海报浓墨 + Tier 2 可达 + 付款前采集）

> **doc/10 §11（N1-N10 用户端节点 + 计费模型 + 异常 E1-E6，单笔单时段）+ doc/11 §3.5/§3.6 是唯一权威。设计走 doc/tokens.md + doc/13（C 日漫海报浓墨），仅 mp。**

- **C 设计系统纪律（CLAUDE.md §7.5）**：只用 `src/components/biz/Biz*` 原子组件（`BizScreen / BizPanel / BizMangaTitle / BizButton / BizTag / BizFixedCta / BizSlotGrid / BizSeatList` 等）+ `var(--c-*)` token，**不直接撒 `<wd-*>` 标签**；不逐像素还原 mockup（以 c-tokens.scss 的 rpx 为准）；不混 emoji（占位素材现用 `MOCK` 水印）。
- **选座 UI（doc/10 §11.N3/N4，单笔单时段 + 显余量）**：选 **1 个座位类型**（字典 `gz_bean_seat_type` 翻译：单人/双人/四人桌）**+ 1 个时段**（单选，非多选累加）→ 金额 = 该类型单价（单笔）；GET `/api/bean/type-slots?store_id&date`（D12 BEAN-014 余量查询接口）返回各类型×各时段可约状态 + 单价 + **剩余可约数量**；每档**实时显余量**「还剩 N 个单人座」/「已满」灰显不可选（余量 = quantity − 活跃 booking 计数）。门店 V1.0 仅成都一家 → 默认选中，UI 隐藏切换（强约束 #13）。
- **选券模块（doc/10 §11.N5，消费 COUPON-003）**：仅展示 unused + 适用拼豆（applicable_business=pindou）+ 未过期；选中展示实付 = 单笔金额 − 券面额（下限 0，doc/11 §11.3）。
- **付款前采集（doc/10 §11.N6，E2 拦截）**：① `gz_user.mobile` 空 → 原生 `getPhoneNumber`（微信原生能力，留 Kevin 真机人验）；② `gz_user.wechat_id` 空 → 表单手动填微信号（USER-005 已填则预填）；两者都采集成功才能 N7 提交（拒绝/不填 → 拒收 + 提示）。
- **支付（doc/10 §11.N7-N9）**：提交 → 下单事务（BEAN-014，一行 booking，约满拒单 E1 提示「[四人桌/下午] 已约满，请重选类型或时段」）→ `wx.requestPayment`（JSAPI，复用 §6）→ onPaid → 跳预约详情（核销码二维码内嵌 `BK|{booking_no}|{verify_code}`）。多类型/多时段 = 用户再下一笔（多次预约）。
- **Tier 2 可达（CLAUDE.md §8.3，mp 硬约束）**：本日 tabbar 尚未重构（SYS-010 在 D14），拼豆 mp 主线入口未必就绪 → **主动加临时入口**到 `pages/index/index.vue` 或现有首页，注释 `<!-- TODO(Tier2-entry-temp): GZ-BEAN-015, remove when GZ-SYS-010 merged -->`（D14 SYS-010 用真「拼豆」tab 替换）。AC 必含：`Tier 2 可达 — Kevin 从 <现有首页/入口> 点 N 次到达拼豆付费页`。
- **真机人验留项（Tier 2）**：`getPhoneNumber` 原生授权 + `wx.requestPayment` 拉起（mock 模式）+ 选座显余量「还剩 N / 已满」准确 + C 设计系统遵循度（粗墨边 / 硬投影 / 朱红主色 / 报头风）；vitest unit + 可达性检查由 kevin-qa Tier 1B 跑。

### GZ-COUPON-002 拼豆抵扣 + 过期回收（doc/11 §11.2 状态机 + §11.3 GMV 口径）

> **doc/10 §12（券锁定核销流 + 状态机）+ doc/11 §11.2（券态机）/§11.3（抵扣 + GMV 口径，钉死）是唯一权威。**

- **券状态机（doc/11 §11.2，钉死）**：`unused → locked`（拼豆下单事务内锁券，防一券多用，写 `gz_bean_booking.coupon_id`）→ `locked → used`（onPaid 核销，写 `used_time` + `related_pay_out_trade_no`）/ `locked → unused`（订单取消 / 支付关闭 `pay_closed` 回滚解锁）；`unused → expired`（过期 SnailJob）。**`locked` 态券不被过期扫描误伤**（已锁定即在用）。
- **抵扣 + GMV 口径（doc/11 §11.3，单笔）**：实付 = `单笔金额 amount_cent − amount_snapshot_cent`（下限 0，券超单笔金额差额不退不找零）；实付 > 0 才建 `gz_pay_transaction(business_type=pindou)`，实付 = 0 走免费单兜底（ADR-0007）；**`gz_pay_transaction.amount_cent` = 实付，券面额不计 GMV**（让利，非平台收入）。
- **不建独立 use 流水表**：核销以 `gz_user_coupon.status` + `related_pay_out_trade_no` 追溯。
- **过期 SnailJob（非 sys_job）**：`@Component + @JobExecutor` 薄壳 + 可单测 service 扫 `unused` 且 `expire_time < NOW()` → `expired`（`gz.coupon.expire.cron`）；**禁止** Quartz / Flyway INSERT sys_job；任务名 + CRON 写进 reports。
- **与 BEAN-014 事务边界协作**：锁券在 BEAN-014 下单事务内（COUPON-002 提供锁券 service）；核销在 `PayCallbackHandler` onPaid（拼豆分支）内 + 回滚在 `pay_closed`（doc/11 §3.8）。

### GZ-COUPON-003 mp 选券 + 我的券列表（C 系统 + Tier 2 可达）

- **C 设计系统**：「我的优惠券」列表（unused / used / expired tab）入口在「我的」；Biz* 组件 + `var(--c-*)`。
- **选券模块**被 BEAN-015 拼豆付款页消费（仅 unused + 适用拼豆 + 未过期）；过期券二次校验拦截（前端缓存兜底）。
- **Tier 2 可达**：从「我的」点 N 次到达券列表（「我的」tab 已上线）；从拼豆付款页可选券（BEAN-015 集成）。AC 必含可达条目。

### GZ-RECYCLE-001 回收价目表地基（doc/11 §12.1 + 区间校验）

> **doc/11 §12.1（`gz_recycle_price_rule`）+ doc/10 §13（估价口径）+ 附录 A.21（回收品类字典）是唯一权威。**

- **价目表**（doc/11 §12.1）：`category`（字典 `gz_recycle_category`，甲方维护）/ `qty_min` / `qty_max`（NULL=无上界）/ `unit_price_cent` / `duration_minutes`（按数量匹配时长）/ `enabled` / `sort_no`；UNIQUE(tenant_id, category, qty_min)。
- **区间不重叠校验（doc/11 §12.1 末段）**：同一 category 下各 `[qty_min, qty_max]` 区间**不得重叠**（**业务层校验**，admin 保存时 assert；DB 不加复杂 CHECK，跨 MySQL 版本兼容性差）；估价命中唯一区间（`qty_min <= qty AND (qty_max IS NULL OR qty <= qty_max)`）。
- **字典 `gz_recycle_category`**：二次元周边品类（甲方维护，可扩展）。
- **本日仅 admin 价目表 + 字典**（估价计算 + mp 填单在 D14 RECYCLE-002，店员核对在 RECYCLE-003）。menu 13000 段（13000 目录 / 13001 价目表）。

### 全局

- **admin 走 ruoyi/Element Plus 默认审美**：COUPON-002（无 admin）/ RECYCLE-001 价目表配置页 / PAY-105 反向打款单管理（挂 5100 段）全部 plus-ui BizTable + Element Plus 默认，**不调样式、不引 mockup**（admin 不评判视觉）。
- **mp 走 C 日漫海报浓墨**：BEAN-015 / COUPON-003 仅 Biz* 组件 + `var(--c-*)` token，不直接撒 `<wd-*>`；doc/tokens.md + doc/13 为准。
- **menu_id 段（doc/11 §10.3）**：优惠券 12000 段（D12 已占目录/模板/发放）；回收 **13000 段**（13000 目录 / 13001 价目表）；反向打款 admin 挂 **5100 段**（GZ-PAY）。
- **包名（CLAUDE.md §6 #4）**：拼豆 `org.dromara.gz.bean.*`；优惠券 `org.dromara.gz.coupon.*`；回收 `org.dromara.gz.recycle.*`；反向打款复用 `org.dromara.gz.common.pay.*`（IWechatPayClient / PayoutTransaction）。
- **字段/命名硬约束（每卡复核）**：金额 `_cent` / snapshot `*_snapshot` / 业务码 `域大写-yyyyMMdd-6位序号`（`PAYOUT-` / `RCY-` 由 D14 用 / `UC-`）/ JSON 列不散列（`product_snapshot_json`，D14 用）/ 图片 `image_id`·`*_image_ids`（FK gz_file_object，不存裸 url，D14 用）/ 业务线统一 `business_type`（payout 域 `recycle`）/ 乐观锁 `version` / `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` / `del_flag` 2 值。
- **SnailJob（非 sys_job）**：COUPON-002 过期回收 + PAY-105 查单轮询均 `@Component + @JobExecutor` 薄壳 + 可单测 service；任务名/CRON 写 reports + testing-human；**禁止** Flyway INSERT sys_job；模块 pom 加 `ruoyi-common-job`。
- **DDL 命名 `V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`**（时间戳 > 已有最大版本；已应用迁移不可改）；**不动 ruoyi 自带模块**。
- **不要 commit**：5 卡全完工 + AI 测试全 ✅ 后统一 commit；mp 部分（BEAN-015 / COUPON-003）进人验列待 Kevin 批量验，不阻塞 commit（AI ✅ 即解锁下游）。

## 推进姿态 = Mock 全链路自测

- 拼豆付费（BEAN-015 拉起支付）+ 反向打款（PAY-105）均在 `gz.pay.client.mode=mock` 下闭环；BEAN-015 真机 `wx.requestPayment` 拉起留 Kevin 批量人验（mock 模式）。
- 真实商户号 / 0.01 元端到端 / 商家转账真实权限 + transferbatch SDK 列为【外部前置风险】（doc/11 §4.10 F4.6 + ADR-0006），权限+SDK 到位后小额真实回归；不当默认就绪。

## 与昨日 reports 对账（D12）

D12 完工后应交付（**主线程 §0 自检 grep migration 目录实际验证，不假设**）：
- GZ-BEAN-014 → `gz_bean_booking` 付费列 + 座位类型列（seat_type / sess_date / slot / amount_cent / pay_status / out_trade_no / coupon_id / discount_amount_cent，**单笔单时段无子表**，含配额计数核心索引）+ 余量查询接口 + 下单事务（单笔配额校验 + 约满拒单）+ 激活 `PayBusinessType.PINDOU` + onPaid 分发 hook + 旧数据迁移完成（原地补 seat_type + 付费列）。BEAN-015 调它下单（一行 booking）+ 余量接口显余量 + 拉起支付；COUPON-002 在它的下单事务内锁券 + onPaid 核销。
- GZ-COUPON-001 → `gz_coupon_template` / `gz_user_coupon` 两表 + admin 批量发放（产 unused 券）。COUPON-002 消费券态机做锁定/核销/回滚。
- D12 summary.md「对下游 ticket 的提示」段（onPaid 拼豆分支 hook 签名 / 锁券事务边界 / coupon_id 写入时机 / verify_code 签名因子）在 COUPON-002 + BEAN-015 实施前主线程逐条对齐。

进 D13 前主线程 §0 自检校验（**grep 实际存在的表/列，不假设**）：
```bash
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'GZ-BEAN-014|GZ-COUPON-001|gz_coupon'
grep -rl 'seat_type\|coupon_id\|gz_user_coupon\|PayBusinessType' code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-bean code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common 2>/dev/null
# ⚠️ gz_bean_booking_unit 不应存在（单笔单时段无子表）：
grep -rl 'gz_bean_booking_unit' code/main/RuoYi-Vue-Plus/ruoyi-modules 2>/dev/null && echo "⚠️ 异常：单笔单时段不应有子表" || echo "无 booking_unit = 正常"
# gz_pay_payout_transaction / gz_recycle_price_rule 应当查不到（= 本日从零建，正常）
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'payout|gz_recycle|GZ-PAY-105|GZ-RECYCLE-001' || echo "本日产物不存在 = 正常，从零建"
```
上游表/列齐 → 开工；缺则 STOP 报 Kevin（先回 D12 收尾）。

## 完成判定（DoD）

- [ ] 5 个 ticket 任务卡 §revision 段空（BEAN-015 / COUPON-002 / COUPON-003 / PAY-105 / RECYCLE-001）
- [ ] 5 个 reports/<T>.md 写完（含 §0 自检 grep migration raw output + §N 完工 + ≥ 3 个代码 block raw output + 关联 ADR 已读摘录：PAY-105 引 ADR-0006 / BEAN-015 引 ADR-0007+0008）
- [ ] **PAY-105 reports 必含**：mock 全链路 raw output（created→processing→success）+ failed 分支单测 + 幂等 raw output（重复 out_payout_no 不二次转账）+ **transferbatch SDK 批准状态记录**（已批准 / 待批准走 mock）
- [ ] **COUPON-002 reports 必含**：券锁定/核销/回滚 raw output（unused→locked→used + locked→unused 回滚）+ 抵扣后实付 = 单笔金额 − 券面额（下限 0，amount_cent 不含券面额）+ 过期 SnailJob 扫描 raw output
- [ ] RECYCLE-001 reports 含区间不重叠校验 raw output（重叠区间 admin 保存被拦截）+ 估价命中唯一区间
- [ ] mvn install（ruoyi-gz-bean / coupon / recycle / common -am）+ plus-ui build:prod 全绿（COUPON-002 后端 / RECYCLE-001 含 admin / PAY-105 后端）；mp 部分（BEAN-015 / COUPON-003）miniapp build:mp-weixin 绿（注意 [[mp-build-devtools-hang]]：尾部唤 devtools cli 假挂起，dist 已生成则 pkill cli -o）
- [ ] PAY-105 查单 SnailJob + COUPON-002 过期 SnailJob 任务名 + CRON 写进 reports + testing-human；**确认无 Flyway INSERT sys_job**
- [ ] Tier 1A + 1B 全 ✅：
  - 纯后端/admin（COUPON-002 / PAY-105 / RECYCLE-001）→ AI ✅ 即终态，**无人验**
  - mp（BEAN-015 / COUPON-003）→ kevin-qa Tier 1B 显式检查可达性（grep `Tier2-entry-temp` 临时入口存在）+ vitest unit；进 progress.md「人验」列待 Kevin 批量验
- [ ] 单测覆盖：COUPON-002 券态流转 + 抵扣口径 ≥ 80%；PAY-105 mock 状态机 + 幂等 ≥ 80%（扭蛋/拼豆事务级目标，CLAUDE.md §8.1）
- [ ] testing-human.md 预填（mp happy path + 可达路径，仅 BEAN-015 / COUPON-003）：
  - 拼豆：现有首页/临时入口 → 拼豆付费页 → 选 1 个「四人桌+下午」（看余量「还剩 N / 已满」单选）→ 金额 = 该类型单价（无累加）→ 选券看实付 → 采手机号（getPhoneNumber）+ 填微信号 → 提交（一笔）→ mock 支付成功 → 看预约详情 + 核销码二维码；可再约一笔（多次预约）
  - 券：「我的」→「我的优惠券」→ 看 unused/used/expired 三 tab
- [ ] V1.2 menu 段无冲突（12000 优惠券 D12 已占 / 13000 回收目录+价目表 / 5100 反向打款 admin）

## 已知风险 ⭐

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⚠️ | PAY-105 私引未批准 transferbatch SDK（违铁律 #8）| 开工前确认 Kevin 批准；未批准 → 仅 mock 实现 + 抽象方法 + payout 表，real 部分留 hook 注释 `待 SDK 批准`，不引依赖（ADR-0006）|
| R2 ⭐ | 反向打款重复转账（幂等失效 → 多打钱给用户）| `out_payout_no` + `batch_id` 双重 UNIQUE 幂等 + version 乐观锁；reports 必含重复触发不二次转账 raw output；主动查单优先（ADR-0006）|
| R3 ⭐ | 券锁定/回滚边界漏 case（一券多用 / 取消未回滚 / locked 被过期误伤）| doc/11 §11.2 状态机钉死：locked 防一券多用、pay_closed 回滚 locked→unused、过期扫描跳过 locked；单测覆盖各流转边 |
| R4 | BEAN-015 付款前采集被跳过（手机/微信号缺失下单）| doc/10 §11.N6 + E2：两者都采集成功才能提交；后端兜底校验（拒收无联系方式的下单）|
| R5 | BEAN-015 mp 不可达（tabbar 未重构，Kevin 测不了）| Tier 2 临时入口 `TODO(Tier2-entry-temp): GZ-BEAN-015`（D14 SYS-010 用真拼豆 tab 替换）；kevin-qa Tier 1B 显式验可达性 |
| R6 | 抵扣后券面额误计入 GMV → 4% 分成虚高 | doc/11 §11.3 钉死：amount_cent = 实付（不含券面额）；单测断言 gz_pay_transaction.amount_cent = total − discount |
| R7 | RECYCLE-001 价目表区间重叠 → 估价命中多区间报错 | 业务层区间不重叠校验（admin 保存 assert，doc/11 §12.1）；估价命中 0/多区间分别提示「无报价规则」/「配置有误」|
| R8 | SnailJob 误用 Quartz / Flyway INSERT sys_job → 启动 hard-fail | COUPON-002 + PAY-105 SnailJob = `@Component + @JobExecutor` 薄壳 + 可单测 service；模块 pom 加 `ruoyi-common-job`；任务名/CRON 写 reports 由人在控制台注册；**禁止** sys_job INSERT |

---

## 日终 closing 命令

```bash
cd doc/daily/D13
cat reports/*.md > summary.md
git add -A && git commit -m "D13: 拼豆 mp BEAN-015（单笔单时段+显余量）+ 优惠券抵扣 COUPON-002/选券 003 + 反向打款 mock PAY-105 + 回收价目表 RECYCLE-001"
# 然后写 D14/README.md（已存在则核对 ticket 清单/依赖与本日 reports「对下游提示」一致）
```
