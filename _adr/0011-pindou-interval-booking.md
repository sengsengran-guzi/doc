# ADR-0011 拼豆预约改为「1h 区间连续多选」（一行 booking 存区间 · 逐格防超卖 · 单价 × 连续小时数计费）

- 日期：2026-06-23
- 状态：Accepted
- 决策人：Kevin（甲方 2026-06-23 沟通反馈点 4「拼豆连选 N 个 1h 格 = 单价 × N 小时」；kevin-product 评估，kevin-coder 落地）
- 关联 ticket：D18 T3（拼豆 1h 连续多选 + 计费 + 防超卖 + 落库）；设计稿 doc/15 §2 + §0 锁定口径
- 依赖：ADR-0008（座位类型配额模型，本 ADR 沿用 `gz_bean_seat_type_config` 单价 + quantity）/ ADR-0007（付费双状态机，本 ADR 沿用 `status` × `pay_status` 正交，不改状态边）/ ADR-0003（支付通道）

---

## Context

V1.2 的拼豆预约（ADR-0007 + ADR-0008）口径是**单笔单时段**：

- 时段是 admin 配的 2-3h **命名大块**（seed 10–12 / 14–17 / 19–22），mp 端**单选**一个时段块（`selectedSlotStart` 单 ref）。
- 一笔预约 = 1 座位类型 + 1 个时段块 = **一行 booking**，金额 = 该座位类型单价（`gz_bean_booking.amount_cent` = `config.price_cent`，无累加）。
- 防超卖：在 `(store, seat_type, sess_date, slot_start)` 单组合上 `COUNT(活跃) FOR UPDATE` 比对 `quantity`（ADR-0008 §3 + ADR-0007 §2），用 `slot_start` 作为时段块的唯一标识。

甲方在 2026-06-23 反馈（设计稿 doc/15 §2）要求改成**按 1 小时格连续多选**：

- 最小粒度 1 小时；用户可一次选**连续若干个 1h 格**（如 14:00–17:00 = 3 格），不能跳选。
- 计费按连续小时数：选 3 格付 3 份（**单价 × 连续小时数**），不再是「一个时段块一份」。
- 满格灰显不可点；只显「可约 / 已满」两态，去掉「还剩 N 个」数字（与甲方习惯相反，doc/15 §2）。

这推翻了 ADR-0007/0008 关于「单笔单时段 + 按 booking 在单一 `slot_start` 计数」的两段假设：

- **粒度变了**：时段从「admin 命名大块」变成「按 1h 切的格」，admin 配的不再是直接预约单位，而是「营业窗口」。
- **一笔预约横跨多格**：金额随小时数累加，配额占用从「一个 `slot_start` 占 1」变成「区间内每个 1h 格各占 1」。

核心设计问题三个：**(1) 一个跨 N 格的预约落库成「一行区间」还是「N 行单格」？(2) 防超卖在哪个维度比对配额？(3) 计费口径？**

---

## Decision

### 1. 粒度真源：admin 配「营业时段窗口」（整点边界），系统按 1h 切格

- admin 在 `gz_bean_time_slot_template` 配的是**营业时段窗口**，不再是直接预约单位。一个门店一天的营业可由**一个或多个窗口**表达；**午休断档用多个窗口**表达（如 10:00–13:00 + 14:00–22:00）。
- **整点边界硬约束**：窗口的 `start_time` / `end_time` 必须落在整点（分钟 = 0、秒 = 0）。**非整点窗口在 admin 表单 + 后端保存时校验拦截**（既有 `end > start` 校验之外新增整点校验），不允许保存 10:30 这类边界。
- 系统在余量查询时把每个启用窗口按 1h **切成格序列**：窗口 `[s, e)` → 格 `[s, s+1h)`, `[s+1h, s+2h)`, …, `[e-1h, e)`。每格是一个独立的可约单位（`slot_start` = 格起整点，`slot_end` = 格止整点 = 格起 + 1h）。
- 跨窗口不连续：两个窗口之间的 gap（午休）天然断开，切格只在窗口内进行，午休那一格根本不生成 → 物理不可约（见 §5 连续性定义）。

> **为什么整点边界**：1h 切格要求窗口长度是整小时、起止落整点，否则会切出残格（如 10:30–13:00 切出 0.5h 尾格）。整点约束让切格无歧义，admin 校验拦截把复杂度挡在配置侧，预约侧只见干净的整点格。

### 2. 落库形态：一笔预约 = 一行 booking 存区间（slot_start..slot_end 跨 N 格）

**选定**：一个跨 N 格的连续预约落成**一行 `gz_bean_booking`**，用现有 `slot_start`（区间起整点）+ `slot_end`（区间止整点）承载整个区间。例：选 14:00–17:00（3 格）→ 一行，`slot_start=14:00:00`，`slot_end=17:00:00`。

- **单核销码**：整段一个 `verify_code`（onPaid 时生成，签名因子沿用 `seat_type`，ADR-0007 / doc/11 §3.8），店员扫一次核销整段。
- **单支付**：整段一笔 `gz_pay_transaction`（business_type=pindou），`amount_cent` = 区间总价（§4）。
- **取消即整段取消**：`cancel` / 超时关单 / no_show 对整行操作，整段释放所有占用的格配额（条件 UPDATE 改 `status`，逐格释放是计数侧的自然结果——活跃行消失，所有它覆盖的格计数同步 −1）。

**被否方案：拆 N 笔单格 booking**（一个 3 格预约 = 3 行 `gz_bean_booking`，各自 `slot_start`/`slot_end` = 1 格）。否决原因：

| 维度 | 一行区间（选定） | 拆 N 笔（否决） |
|---|---|---|
| 核销码 | ✅ 一段一个码，店员扫一次 | ❌ N 个码 / 或要额外「主单」聚合，店员扫 N 次 |
| 支付 | ✅ 一笔支付一个 out_trade_no | ❌ N 笔支付 or 一笔付款跨 N 行回写（onPaid 定位复杂） |
| 取消 | ✅ 一行整段取消，原子 | ❌ 取消要保证 N 行同时取消，部分失败留残段 |
| mp「我的预约」 | ✅ 一张卡 = 一次到店 | ❌ 一次到店裂成 N 张卡，UX 差 |
| 落库改动面 | ✅ 复用现有 slot_start/slot_end 两列，零新列 | ❌ 要引「主单 → 子格」父子结构或聚合字段 |

一行区间在「单码 / 单支付 / 整段取消原子性 / UX / 改动面」上全面占优；拆 N 笔只在「防超卖查询能直接复用单格计数」上略省，但那点便利被 N 单 N 码的 UX 与一致性代价彻底盖过，不取。

### 3. 防超卖：区间内每个 1h 格逐格 FOR UPDATE 比对 quantity，每格独立占 1 配额

`quantity`（`gz_bean_seat_type_config.quantity`）的语义钉死为 **「每个 1h 格的独立配额上限」**——不是「整个营业日的配额」，也不是「一个时段块的配额」。一行区间预约对它覆盖的**每一个 1h 格各占用 1 个该格配额**。

下单防超卖事务内：

1. 把本笔预约区间 `[slot_start, slot_end)` 在 service 层按 1h 展开成格序列 `g1, g2, …, gN`（每格起整点）。
2. **逐格** `FOR UPDATE` 比对：对每个格 `gi` 执行 `COUNT(覆盖 gi 的活跃 booking) FOR UPDATE`，与 `quantity` 比对；**任一格 `活跃计数 >= quantity` → 拒单、整笔事务回滚**（部分格满即整笔失败，无部分成交）。
3. 全部格通过 → INSERT 一行区间 booking（`pay_status=paying` 或免费单 `paid`，沿用 ADR-0007 §1）。

> **「覆盖 gi 的活跃 booking」= 区间重叠，不是 `slot_start` 相等**：现有 `countActiveByTypeSlotForUpdate` 用 `slot_start = #{slotStart}` 精确匹配，**在区间模型下错**（一个 14:00–17:00 的活跃单不会被 `slot_start=15:00` 的查询计入，但它确实占了 15:00 这格）。新查询的计数条件改为**区间重叠**：`booking.slot_start <= gi AND booking.slot_end > gi`（gi 为格起整点），对 `(store, seat_type, sess_date)` + 该重叠条件 `COUNT(活跃) FOR UPDATE`。活跃定义沿用 ADR-0007 / doc/11 §3.6 不变：`status='pending' AND pay_status IN ('paying','paid')`。

- **逐格锁的并发口径**：每格一条 `FOR UPDATE`，N 格 N 条（建议按格 `slot_start` 升序逐格锁，固定加锁顺序避免两个交叠区间互等死锁）。V1 单店量级无虞；高并发升级路径同 ADR-0007 §Consequences（Redis 预占），不在本批。
- **≥80% 覆盖率并发单测**（CLAUDE.md §8.1 拼豆座位锁红线）：必须覆盖「两个交叠区间抢同一格最后名额、只成一笔」「相邻不交叠区间各自成功」「部分格满整笔回滚」。

### 4. 计费：实付 = 类型单价 × 连续小时数

- 区间总价 `amount_cent` = `config.price_cent`（该座位类型单价）× **连续小时数 N**（= `(slot_end − slot_start)` 的小时数 = 格数）。选 3 格 → `price_cent × 3`。
- 写进一笔 `gz_pay_transaction`（`business_type=pindou`，沿用 ADR-0007 §1 的 PINDOU 链路），`business_order_no = booking_no`。优惠券抵扣沿用既有：`pay_amount_cent = max(0, amount_cent − 券面额)`（ADR-0007 §对账口径 / doc/11 §11.3）。
- **拼豆不进 recon、不影响 4% 分成**（设计稿 doc/15 §0 + ADR-0007 §对账口径不变）：本 ADR 只把单笔金额从「单价」改成「单价 × 小时数」，资金流向 / recon 口径不动。

### 5. 连续性定义：可约格序列里物理相邻的连续段，午休 gap 断开不可桥接

- 用户选中的格集合必须是**可约格序列里物理相邻的连续段**（同一营业窗口内、整点逐格相接），**不允许跳选**（选了 14:00 与 16:00 却跳过 15:00 = 非法）。
- **午休 gap 不可跨窗口桥接**：13:00–14:00 若不在任何营业窗口（午休），则它把 10:00–13:00 窗口与 14:00–22:00 窗口断成两段，用户不能选出一个横跨 13:00 的区间（如 12:00–15:00 非法），最多选到窗口边界（12:00–13:00 或 14:00–15:00）。
- 前端只允许在已选区间的**相邻处扩展 / 收缩**（贴着区间头尾加减格），保证选中集合恒为连续段；后端**逐格校验**入参区间内每格均为该日可约格（落在某启用窗口内、未满），任一格不可约 → 拒单（前后端双校验，后端是真源）。

---

## 数据结构判断：现有列够不够承载区间？

**结论：`gz_bean_booking` 现有 `slot_start` / `slot_end` 两列足以承载区间，无需新表、无需新业务列。**

- `gz_bean_booking.slot_start`（`TIME`）/ `slot_end`（`TIME`）本就是区间字段（实体 `GzBeanBooking` 已有 `LocalTime slotStart/slotEnd`）。单时段模型下它们恰好等于一个时段块的起止；区间模型下直接存「区间起整点 .. 区间止整点」，语义自然延展，**零结构改动**。
- `amount_cent`（`BIGINT`）承载区间总价（单价 × 小时数），列不变，只是写入值的算法变。
- 无父子单元子表（一行自洽，§2）。

**唯一需要的索引/约束草案（留给 backend ticket 实施，本 ADR 不建表、不写迁移）：**

逐格重叠计数 `WHERE tenant_id=? AND store_id=? AND seat_type=? AND sess_date=? AND slot_start<=? AND slot_end>? AND status='pending' AND pay_status IN('paying','paid') AND del_flag='0'` 的命中效率，建议补一个组合索引（DDL 草案，**backend ticket 落地时按强约束 #5 新建 `V<yyyyMMddHHmm>__<TICKET>-*.sql`，时间戳 > 当前最大 `V202606260001`，从 `V202606270001` 起递增**）：

```sql
-- 草案，留给 D18 T3 backend ticket；本 ADR 不创建
ALTER TABLE gz_bean_booking
  ADD INDEX idx_gz_bean_booking_overlap (tenant_id, store_id, seat_type, sess_date, slot_start, slot_end);
```

- **dedup_token 老唯一约束的处置**：`UNIQUE(tenant_id, store_id, dedup_token)`（方案 C，基于 `seat_id|sessDate|slotStart`）是 V1.0 免费单具体座位时代的防超卖兜底，V1.2 付费区间单 `seat_id=NULL`、`dedup_token` 不写（现 `submitPaid` 已不写 dedup_token），区间模型下也无单一 `slot_start` 可唯一化 → **`dedup_token` 不再用于区间单防超卖**（防超卖完全交逐格 `FOR UPDATE`，§3）。该列 + 唯一约束保留不删（旧免费单数据 + destructive 红线），仅对 V1.2 区间单停用。
- 无需新枚举 / 新状态：`status`（pending/used/cancelled/no_show）× `pay_status`（unpaid/paying/paid/pay_closed/refunded）状态机原样沿用（ADR-0007 不动），区间是「一行单的属性」不是新状态维度。

---

## 取代关系（明确标注被推翻的具体段落）

本 ADR 修订 ADR-0007 与 ADR-0008 中关于「单笔单时段」与「按单一 `slot_start` 计数」的部分；两者其余结论（双状态机正交 / 座位类型配额 / 配置表 / 旧数据迁移 / 单价取自 config）继续有效。

**取代 ADR-0007（拼豆付费双状态机）：**

- §Context「明确预约粒度为**单笔单时段**……一笔预约 = 1 座位类型 + 1 时段……单笔金额 = 该座位类型单价」→ 改为：一笔预约 = 1 座位类型 + **1 个连续 1h 区间（跨 N 格）**，金额 = 单价 × N（本 ADR §2/§4）。
- §Decision 2「配额防超卖：对 (店,类型,日期,时段) COUNT 活跃 booking FOR UPDATE」+「单笔单时段 = 无部分成交问题，一笔只占一个 (类型,时段) 名额」→ 改为：**逐格** FOR UPDATE，区间内每个 1h 格各占 1 配额、任一格满整笔回滚（本 ADR §3）。计数维度从「`slot_start` 精确相等」改为「区间重叠 `slot_start<=gi AND slot_end>gi`」。
- §对账口径「单笔实付 = `amount_cent`（该类型单价）− 券抵扣」→ `amount_cent` 改为**单价 × 小时数** − 券抵扣（本 ADR §4）；recon / 4% 口径不变。
- **不变**：`status` × `pay_status` 双状态机的 7 条边与唯一前置（verified 需 paid）、下单即占配额 + 超时关单、免费单兜底、旧数据迁移——原样沿用。

**取代 ADR-0008（座位类型配额模型）：**

- §Context / §Decision 3「预约粒度甲方明确为**单笔单时段**（一笔预约 = 1 座位类型 + 1 时段）」「`gz_bean_booking` 主表补 …… 单时段直接挂主表」→ 改为区间（一行存跨 N 格区间，复用 slot_start/slot_end，本 ADR §2）。
- §Decision 3「可用量计算 = quantity − 该 (store, seat_type, date, slot) 组合下活跃 booking 计数」「mp 选座实时显示余量『还剩 N 个』」→ 改为：`quantity` = **每 1h 格独立配额**；余量按**逐格**算（本 ADR §3）；mp **去「还剩 N」数字**，只显「可约 / 已满」两态（设计稿 doc/15 §2）。
- **不变**：废弃 `gz_bean_seat` 用于预约（保留不 DROP）、`gz_bean_seat_type_config` 配置表（store × seat_type → quantity + price_cent + enabled，`UNIQUE(tenant_id, store_id, seat_type)`）、座位类型字典 `gz_bean_seat_type`、改现有表而非全新表——原样沿用。`quantity` / `price_cent` 列不变，仅语义（quantity=每格配额）与用法（price 按小时累乘）调整。

---

## Rationale

- **一行区间 = 单一履约单元**：一次到店就是一段连续时间，落成一行天然对齐「一个码 / 一笔款 / 一次取消」，避免拆 N 笔带来的多码、跨行支付回写、部分取消残段。复用现有 `slot_start`/`slot_end` 两列，落库零结构改动。
- **逐格 FOR UPDATE = 正确的防超卖维度**：区间占用是「每格各占一名额」，单一 `slot_start` 计数会漏算被区间覆盖但 `slot_start` 不等的格 → 超卖。逐格重叠计数 + 悲观锁是与「每格独立配额」语义一致的最小正确实现；固定加锁顺序防交叠区间死锁。
- **整点切格 = 把复杂度挡在配置侧**：admin 配整点窗口、系统切格，预约侧只见干净整点格，无残格歧义；午休用多窗口表达，gap 天然断连续性，无需额外「午休字段」。
- **计费 × 小时数 = 贴合甲方真实诉求**：用户按需选连续时长、按时长付费，是拼豆店真实计费模型；改动落在「写入 amount_cent 的算法」一处，资金链路 / recon / 分成口径全不动。
- **沿用 ADR-0007/0008 大半结论 = 改动面可控**：双状态机、配额配置表、字典、旧数据迁移、单价真源全不动，只改「时段粒度 + 计数维度 + 计费乘法」三处，把推翻面收窄到最小。

---

## Consequences

- ✅ 拼豆支持 1h 连续多选，计费随时长线性累加，符合甲方运营与计费习惯。
- ✅ 一行区间承载整段：单码 / 单支付 / 整段取消原子，mp「我的预约」一次到店一张卡。
- ✅ 复用 `gz_bean_booking.slot_start/slot_end` 两列，**无新表、无新业务列、无新状态枚举**；仅 backend ticket 补一个重叠计数组合索引（DDL 草案见上，时间戳从 `V202606270001` 起）。
- ✅ 防超卖维度修正为逐格重叠计数 + 悲观锁，消除「区间覆盖多格但单一 slot_start 计数漏算」的超卖隐患；配 ≥80% 并发单测兜底。
- ⚠️ **现有 `countActiveByTypeSlotForUpdate` / `countActiveByTypeSlot`（`slot_start=#{slotStart}` 精确匹配）必须改为区间重叠条件**，否则区间单防超卖与余量展示都错。backend ticket 改写这两个查询 + service 逐格循环 + `GzBeanPaidBookingSubmitBo` 的 `slotStart/slotEnd` 语义由「单时段块」改「区间起止」+ `GzBeanTypeSlotAvailabilityVO` 改按 1h 格返回（去 remaining 数字保留 full 判定）。
- ⚠️ **逐格 N 条 FOR UPDATE 的并发上限**：交叠区间下锁竞争比单格更宽（一笔锁 N 格），V1 单店量级无虞；多店/大促放量升级 Redis 预占（同 ADR-0007 §Consequences，届时另 raise）。固定按格升序加锁防死锁。
- ⚠️ **admin 时段配置语义变化**：`gz_bean_time_slot_template` 从「命名预约块」改为「整点营业窗口」，admin 表单 + 后端保存新增整点边界校验；现有 seed（10–12 / 14–17 / 19–22）需在 backend/admin ticket 评估是否改为整点窗口（如 10–13 / 14–22）。`slot_name` 命名块语义弱化，mp 不再按块单选。
- ⚠️ **旧单兼容**：V1.0/V1.2 既有单时段单（slot_start/slot_end 为一个时段块）在区间模型下是「区间 = 1 块」的退化形态，原地可读、可核销、可查询，无数据迁移；新单按区间写入。`dedup_token` 唯一约束对 V1.2 区间单停用（防超卖交逐格 FOR UPDATE），列保留不删。
- ⚠️ **mp 交互改造**（D18 T3 mp 段）：座位类型一排三列（设计稿点 1）；时段从单选改连续多选（跳选拦截 / 满格灰 / 去余量数字）；金额随选格数实时 = 单价 × 格数。
