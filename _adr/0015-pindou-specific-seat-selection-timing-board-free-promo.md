# ADR-0015 拼豆预约「回归具体座位 + 影院式自选 + 店内计时看板 + 前 N 名免费促销」（取代 ADR-0008 容量池模型）

- 日期：2026-06-29
- 状态：Accepted
- 决策人：Kevin（甲方运营三点新诉求；主线程 brainstorming + 评估 + 落地）
- 关联 ticket：GZ-BEAN-022（DDL：座位单元表复活 + booking 加列 + 促销表）/ 023（座位单元 CRUD + 自动生成）/ 024（影院选座可用性 + 锁具体座位下单）/ 025（前 N 名免费促销）/ 026（店内计时看板 + 提前放座）/ 027（admin 座位单元 + 促销配置）/ 028（admin 计时看板）/ 029（mp 影院选座）/ 030（mp 免费 banner）/ 031（mp 店员端看板，fast-follow）
- 依赖与取代关系：
  - **取代 ADR-0008**（座位类型配额模型「无具体座位、纯容量池」段）——甲方明确要回到具体座位 + 用户自选座。
  - **取代 ADR-0014 §2 + ADR-0011 §3**（「防超卖按 `slotCapacity` 逐格配额计数」段）——计数维度从「类型配额计数」改为「具体座位区间占用互斥」。
  - **保留 ADR-0007**（付费双状态机 `status` × `pay_status` 正交，不动）。
  - **保留 ADR-0011 §1/§2**（营业窗口整点切 1h 格 + 一行 booking 存连续区间，不动）。
  - **保留 ADR-0014 §1/§3**（座位类型去字典化自定义 `gz_bean_seat_type_config` + 按星期价格覆盖 `gz_bean_seat_type_price`，不动）——`seat_type_config` 现在是「桌型/分区定义」，其下挂具体座位单元。

---

## Context

ADR-0008 当初**主动**把拼豆从「具体座位 A1-A10」推倒成「无具体座位的容量池」（按桌型配额计数），理由是「用户不在乎坐哪张具体桌、admin 维护座位图负担重」。落地后叠加 ADR-0011（1h 区间）+ ADR-0014（桌型自定义 + book_mode 整桌/按座 + 按星期价）+ ADR-0007（付费双状态机）形成当前模型：

- 用户选**桌型**（config 行）+ 连续 1h 区间，不选具体座位；
- 防超卖 = 逐格 `COUNT(活跃 booking) FOR UPDATE` vs `slotCapacity`（`book_mode='seat' ? quantity×capacity : quantity`）；
- mp 只显「可约 / 已满」两态，不下发余量数字。

甲方在 2026-06-29 提出三点新诉求，现模型无法表达：

1. **每个座位有编号 + 到店核销后计时 + 店内看板看临近结束 + 放开座位继续预定**：座位要有身份（编号），店员要能在店内实时看到「哪个座位还有多久结束」以便提前准备 / 告知，并能在客人离场后立即放开该座位供再约。这要求座位是**有身份的具体单元**，且要有「以核销为起点的实时占用视图」。
2. **影院式自助选座**：把单人桌 / 双人桌 / 四人桌的座位**画成座位图**，用户像选电影座位一样自己点具体座位。这直接要求用户选「具体座位」，而非「桌型」。
3. **前 N 名免费促销**：每个可配周期（每天 / 每周 / 每 N 天）内，拼豆预约的前 N 个免费，mp 上显眼提示「还剩 X 名免费」；名额用尽后显示真实价格。用于前期宣传引流。

诉求 1、2 共同要求**反转 ADR-0008**：回到具体座位 + 用户自选。叠加诉求 1 的「核销后计时 / 放座」要求一个**店内计时看板**，诉求 3 要求一个**促销发放层**。

**Kevin 拍板（brainstorming，2026-06-29）**：
- 座位模型：**回到具体座位 + 自选座（推翻 0008）**。
- 时间模型：**两者都要** —— 预约时锁定时段（沿用 1h 区间），店员看板以核销为起点显实际占用，可手动提前放座 / 延时。
- 免费名额：**admin 可配周期**（不限每天，可每周 / 每 N 天）+ 名额 N + 促销起止。
- 排期：三点**一批做**。

**核心设计问题**：
- (Q1) 具体座位怎么落库才能既支持「编号 + 影院布局」又复用现有 `seat_type_config`（桌型/价格/book_mode）？
- (Q2) 防超卖从「类型配额计数」怎么改成「具体座位互斥」，且仍兼容 ADR-0011 的区间模型？
- (Q3) 「核销后计时 + 放座」与「提前选时段格」两套时间语义如何并存？
- (Q4) 「前 N 名免费」名额发放怎么做到周期可配 + 并发不超发？

---

## Decision

### 1. 复活 `gz_bean_seat` 为「座位单元表」，挂在 `gz_bean_seat_type_config` 之下，编号规则由 `book_mode` 决定

`gz_bean_seat_type_config`（ADR-0014）保持为**桌型 / 分区定义**（`name` / `book_mode` / `capacity` / `price_cent` + 按星期价 / `enabled` / `sort_no`）。其下挂**具体可订座位单元**——复活 `gz_bean_seat`（V1.2 起停用、保留未 DROP 的表），结构升级：

新增 / 复用列：

| 列 | 类型 | 含义 |
|---|---|---|
| `seat_type_config_id` | BIGINT UNSIGNED NOT NULL | **新增** FK → `gz_bean_seat_type_config.id`，继承该桌型的 `book_mode` / `capacity` / 价格 |
| `seat_no` | VARCHAR(16) NOT NULL | 复用，座位/桌编号（显示标签）；**编号规则见下** |
| `table_no` | VARCHAR(16) NULL | **新增** 同桌聚合标识：`seat` 模式下把同一张物理桌的多个座位单元聚成一组，供影院图聚合渲染（如四人桌「T1」下挂 T1-1..T1-4）；`whole` 模式可空 |
| `zone` | VARCHAR(16) NULL | **新增** 分区标签（如「靠窗区」「大厅」），影院图分区渲染用 |
| `row_label` / `col_index` | 复用 | 影院图行列定位（可选，自动生成时按桌型顺序填）|
| `enabled` | TINYINT NOT NULL DEFAULT 1 | 复用，停用（坏了 / 撤桌）不影响已有预约 |
| `sort_no` | INT NOT NULL DEFAULT 0 | 复用，店内 / 同桌内排序 |

**编号规则（= `book_mode` 的自然映射，对齐想法 ①）**：
- `whole` 整桌订（如双人桌）→ **一张桌 = 一个座位单元，按桌编号**（如「D1」「D2」）。订该单元 = 占整张桌。`capacity` 仅展示用（标「2 人桌」）。
- `seat` 按座订（如四人桌拼桌、单人位）→ **一个座位 = 一个座位单元，按座编号**（如「Q1」「Q2」或同桌聚合「T1-1」「T1-2」）。一笔预约占 1 个座位单元。

> `seat` 模式下不把多个座位单元硬绑到同一张物理桌做约束——沿用 ADR-0008「店员现场安排落座」哲学，`table_no` 仅用于影院图聚合渲染（视觉上把 4 个座位画在一张桌周围），不参与防超卖逻辑。

**座位单元生成（降低 admin 维护负担，回应 ADR-0008 的原始顾虑）**：admin **不逐个手画座位**。座位类型配置页提供「按桌型批量生成座位单元」：填桌型 + 桌数（`quantity`），系统按 `book_mode` 自动生成带编号的座位单元行（`whole` 生成 `quantity` 个桌单元；`seat` 生成 `quantity × capacity` 个座位单元，按 `table_no` 分组）。生成后可单独停用 / 调编号 / 调分区。`gz_bean_seat_type_config.quantity` 语义从「每格配额上限」**降级为「批量生成座位单元时的桌数提示」**（列保留，不再用于防超卖计数——见 §2）。

### 2. 防超卖：从「类型配额计数」改为「具体座位区间占用互斥」

一个**具体座位单元 `seat_id`** 在任一 1h 格最多被 1 笔活跃 booking 占用。下单事务内：

```sql
-- 锁住该座位当日的活跃 booking，判断请求区间是否与任一已占区间重叠
SELECT id FROM gz_bean_booking
 WHERE store_id=? AND seat_id=? AND sess_date=?
   AND slot_start < ? AND COALESCE(actual_end_slot, slot_end) > ?   -- 区间重叠：reqStart < occEnd AND occStart < reqEnd
   AND status IN('pending','used') AND pay_status IN('paying','paid') AND del_flag='0'
 FOR UPDATE;
-- 命中任一行（区间重叠）→ 该座已被占，整笔回滚拒单（业务码 4002 SEAT_TAKEN）
-- 无命中 → 放行，INSERT 一行区间 booking（seat_id + seat_no_snapshot 写入）
```

- **占用结束边界 = `COALESCE(actual_end_slot, slot_end)`**：未提前放座的活跃单按计划 `slot_end` 占用；已提前放座（§5）的 `used` 单按 `actual_end_slot`（放座时刻向上取整到格）占用——放座后该座剩余格立即可被再约（回应想法 ① 「放开座位继续预定」）。
- **活跃口径不变**（ADR-0007 / ADR-0011 沿用，双状态机）：`status IN('pending','used') AND pay_status IN('paying','paid')` 占座——`pending`（待到店）占计划区间，`used`（已核销、在店使用中 / 未放座）在其有效占用区间内仍占座；`cancelled` / `no_show` 或 `pay_status IN('pay_closed','refunded')` 释放。核销只推 `status: pending→used`，`pay_status` 停 `paid`（ADR-0007，不引入 `verified` 落库值）。
- **加锁 / 防死锁**：锁维度从「(store, seat_type_config_id, 日期, 逐格)」收敛为「(store, seat_id, 日期)」单维度悲观锁——比逐格配额计数**更简单**（一个座位的活跃单本就少，单次 `FOR UPDATE` + 区间重叠判断即可，无需逐格循环加锁）。Redis 抢锁 key 复活 `gz:bean:lock:seat:{store_id}:{seat_id}:{sess_date}`（ADR-0011 时废弃的 seat 锁回归），废弃 `gz:bean:lock:quota:*`。
- **`seat_type_config_id` 仍写入 booking**：作为计价 / 容量 / book_mode 快照来源（取价、取 book_mode_snapshot），但**不再是防超卖计数维度**。

### 3. 下单流：选门店 → 选日期 + 连续 1h 区间 → 简单座位列表 → 点具体座位 → 计价 → 付款 / 免费 → 核销码

mp 下单顺序「先选场次（区间），再选座」：

1. 选门店（沿用 `BizStoreSelector` 全局门店态）。
2. 选日期 + **连续 1h 区间**（沿用 ADR-0011 的 1h 格连续多选，`BizSlotGrid`；此步只定区间，不绑桌型）。
3. **简单座位列表 / 网格**（`BizSeatList` 风格，**不做影院图**——门店仅十余张桌，量小，影院式可视化是过度设计，甲方 2026-06-29 明确否掉）：列出所有启用座位单元（按桌型 / 分区轻分组即可），对所选区间逐座算 `full`（该座区间内任一格被占即灰显不可点），可订座高亮。座位标编号 + 桌型名 + 该区间总价。
4. 点选**一个具体座位单元** → 计价见 §3.1（区间逐格求和）。
5. （可选）选券 → 采手机号 / 微信号 → 付款（或免费，§4）→ 核销码。

**可用性接口**（座位单元维度，取代 ADR-0014 的「类型 × 格」VO）：`GET /app/gz/bean/booking/seat-map?storeId&sessDate&slotStart&slotEnd` 返回按桌型 / 分区分组的座位单元列表，每座 `{ seatId, seatNo, tableNo, zone, seatTypeConfigId, typeName, bookMode, priceCent（= 该座所选区间总价，§3.1 逐格求和；区间未选则 null/预览）, full（该座在 [slotStart,slotEnd) 内是否被占）}`。

> **`full` 布尔无余量泄漏**：具体座位是离散身份，列表天然显「该座可订 / 已占」（布尔），不涉及「余量数字」。

### 3.1 计价：桌型 × 星期 × 每个 1h 格定价，区间逐格求和（甲方 2026-06-29 诉求，细化 ADR-0014 §3）

甲方要求**每个星期、每个不同的时间（1h 格）都可单独配价，没配则回退默认**。`gz_bean_seat_type_price`（ADR-0014）从「(桌型 × 星期) 单价」升级为「(桌型 × 星期 × 1h 格) 价」：

- 加列 `slot_start TIME NULL`：**`NULL` = 该「桌型 × 星期」整天默认价**（向后兼容 ADR-0014 已有按星期行）；**`HH:00:00` = 该「桌型 × 星期 × 该 1h 格」覆盖价**。`UNIQUE(tenant_id, seat_type_config_id, weekday, slot_start)`。
- **生效价 3 级回退**：某 `(weekday, 小时 h)` 的格价 = `price(weekday, h)` ?? `price(weekday, NULL 整天默认)` ?? `config.price_cent`（基础价）。
- **区间金额 = 逐格求和**：`amount_cent = Σ_{格 gi ∈ [slot_start, slot_end)} 格价(weekday, gi 起整点)`。**取代** ADR-0014/0011 的「单价 × N 小时」（各小时可不同价，不能再用单一单价乘 N）。seat-map 的 `priceCent` = 该座所选区间的这个求和总价。
- admin「按星期价格」弹窗升级为「**星期 × 1h 格价格网格**」：每星期可逐格配价 + 一个「整天默认」（NULL 格）；空格回退。覆盖式保存。

### 4. 前 N 名免费促销：`gz_bean_free_promo` 配置表 + 下单事务内原子发放

新建 `gz_bean_free_promo`（每门店一行，DDL 走 Flyway，强约束 #2/#3）：

| 列 | 类型 | 含义 |
|---|---|---|
| `store_id` | BIGINT UNSIGNED NOT NULL | FK → `gz_bean_store.id`；`UNIQUE(tenant_id, store_id)` |
| `period_type` | VARCHAR(8) NOT NULL DEFAULT `'day'` | 周期类型：`day`（每天）/ `week`（每周，自然周一起）/ `days`（每 N 天滚动）|
| `period_days` | INT NOT NULL DEFAULT 1 | `period_type='days'` 时的 N（滚动周期天数）；其余类型忽略 |
| `anchor_date` | DATE NULL | `days` 滚动周期的锚点起算日（计算当前周期桶用）|
| `free_count` | INT NOT NULL DEFAULT 0 | 每周期免费名额 N |
| `start_date` / `end_date` | DATE NULL | 促销活动窗口（可空 = 不限）；超出窗口促销失效 |
| `enabled` | TINYINT NOT NULL DEFAULT 0 | 总开关 |

**周期桶（period bucket）**：把「促销名额」按周期切桶——`day` 桶 = 下单当天日期；`week` 桶 = 下单日所在自然周（ISO 周一起）；`days` 桶 = `floor((下单日 − anchor_date) / period_days)`。「前 N 名」= 同一桶内**按下单时间先后**前 N 笔。

**发放（下单事务内，原子，不超发）**：
1. 命中促销（`enabled=1` + 当天在 `[start_date, end_date]` 窗口内）→ 取当前周期桶。
2. Redis 锁 `gz:bean:lock:free_promo:{store_id}:{bucket}`（5s）串行化 → 桶内 `COUNT(*) FROM gz_bean_booking WHERE store_id=? AND is_free=1 AND <桶时间范围（按 create_time）> AND del_flag='0'` 比对 `free_count`（**不加 status 过滤 = 含 cancelled/no_show 的 is_free 单，已发即占名额、不回收**，见下）。
3. 未满（`已发 < free_count`）→ 本单 `is_free=1`，`amount_cent=0`（**免费覆盖一切桌型价 / 区间小时数**），实付 0 → 复用现有「实付≤0 直接 `pay_status='paid'`、不建支付单、即时生成核销码」逻辑（后端已有）。
4. 已满或未命中 → 正常计价付款。

> **取消回收名额？** —— **不回收**。免费名额按「下单先后」发放，取消后**不把名额还回桶**（防刷：下单占免费 → 取消 → 再下单刷免费）。桶内计数口径用 `status NOT IN('cancelled')` 时要谨慎：为防回收，改为「**桶内曾发放的免费单计数**」即 `is_free=1 AND del_flag='0'`（含 cancelled，已发即占名额）。`no_show` / `cancelled` 的免费单仍计入「已发」，名额一次性消耗。

**mp 促销提示**：`GET /app/gz/bean/free-promo/status?storeId` 返回 `{ enabled, freeCount, remaining（= free_count − 桶内已发，下限 0）, periodLabel（「本周期」/「今日」/「本周」）}`。`remaining>0` → 首页 / 拼豆页显眼 banner「本店前 N 名免费，还剩 X 名」+ 选座页价格区标「本单免费」；`remaining<=0` 或促销关 → 不显 banner、显真实价格。**此处显示「还剩 X 名」是促销话术，与 §3 座位 `full` 布尔无关、不违反余量铁律**（促销名额本就是引流用的紧迫感数字）。

**GMV / 分成**：`is_free=1` 单 `amount_cent=0`、实付 0，**不计入 4% 分成的 GMV 流水**（与合同 §4.1「实际到账流水」口径一致，免费单本就不产生到账）。

### 5. 店内计时看板（想法 ①，「两者都要」时间模型）

**时间语义并存**：
- **预约时（线上）**：锁定计划时段 `[slot_start, slot_end)`（沿用 ADR-0011 区间），防超卖按 §2 具体座位互斥。
- **到店后（店内实时）**：核销（`verify_time`）= **入座 / 计时起点**；看板以核销为起点显实际占用与倒计时。

新增 booking 列：
- `actual_end_time` DATETIME(3) NULL —— 实际离场 / 放座时刻（提前放座或延时后写）。
- `actual_end_slot` TIME NULL —— `actual_end_time` 向上取整到整点格的占用止界（供 §2 区间重叠判断 `COALESCE(actual_end_slot, slot_end)`）。

**计时看板（admin / 店员）**：`GET /app/gz/bean/board?storeId&sessDate` 返回当日各座位单元的实时状态行：
| 状态 | 判定 |
|---|---|
| 空闲 | 当前时刻无活跃 booking 覆盖 |
| 已约未到 | 有 `pending`+`paid` 活跃单覆盖当前 / 未来格，未核销（`verify_time` NULL）|
| 使用中 | 已核销（`status='used'`，`verify_time` 有值），当前时刻 < 计划 `slot_end`；返 `remainingMinutes`（到 `slot_end` 倒计时）|
| 临近结束 | 使用中且 `remainingMinutes ≤ 阈值`（`gz.bean.board.near_end_minutes`，sys_config，默认 15）→ 高亮 |
| 已超时 | 已核销且当前时刻 > `slot_end` 且未放座 |

**店内操作**（看板上对某座当前单）：
- **提前放座**：写 `actual_end_time=now` + `actual_end_slot=ceil(now→整点)` → 该座 `actual_end_slot` 之后的格立即可再约（§2 重叠判断收紧到 `actual_end_slot`）。不改 `status`（仍 `used`，是已用记录）。
- **延时**（可选，operational）：把 `slot_end` 往后推 K 个整点格 → 先按 §2 校验该座新增格未被别人占（占了则拒绝延时）→ 通过则 `UPDATE slot_end`。**V1 延时不走线上补付**（差额线下结算或免费延时由门店定，避免引入超时计费的资金口径复杂度）；线上超时补付列入 V2。
- 看板数据 admin（plus-ui，owner / 店员）+ mp 店员端（`bean/staff-board.vue` 扩展 / 新 `bean/timing-board.vue`，fast-follow，ADR-0004 mp 管理端地基）。

### 6. booking 字段变更汇总

| 列 | 变更 | 说明 |
|---|---|---|
| `seat_id` | **复活写入** | 具体座位单元 FK → `gz_bean_seat.id`（V1.2 停写，本 ADR 起重新 NOT NULL 写入；旧迁移期单保留 NULL）|
| `seat_no_snapshot` | **复活写入** | 下单时座位编号快照 |
| `seat_type_config_id` | 保留写入 | 计价 / book_mode / 容量快照来源；不再是防超卖维度 |
| `seat_type_snapshot` / `book_mode_snapshot` | 保留写入 | 桌型名 + 订法快照（`seat_type_snapshot` = config.name + seat_no 组合显示）|
| `actual_end_time` | **新增** | 实际离场 / 放座时刻 |
| `actual_end_slot` | **新增** | 占用止界整点格（防超卖重叠判断用）|
| `is_free` | **新增** | TINYINT，前 N 名免费标记（`1`=免费单，`amount_cent=0`）|
| `verify_code` 签名因子 | 调整 | V1.2.x 因子含 `seat_type`；本 ADR 起核销码生成因子改回含 `seat_id`（`HmacSHA256(booking_no + sess_date + seat_id)`）——具体座位回归后 seat_id 是稳定身份。一段区间仍 1 个码（不含 slot）|

---

## 取舍记录

### 取舍 A：座位单元独立成行 vs 由 config + 桌数派生
**选定：座位单元独立成行**（复活 `gz_bean_seat`，每座一行带稳定 id + 编号 + 布局）。
**被否：纯派生**（config 存桌数，运行时算「第 i 桌第 j 座」）。
- 影院选座要求每座有**稳定身份**（booking FK 到具体座、看板按座显状态、停用单座）；派生方案的座位身份是「序号位置」，停用 / 调编号 / 历史 booking 反查都脆弱。
- 独立成行的「维护负担」用「按桌型批量自动生成」化解（§1），admin 仍只填桌数，不逐个画——既得稳定身份又不重蹈 ADR-0008 抱怨的座位图维护负担。

### 取舍 B：轻量结构化布局 vs 自由拖拽画布
**选定：轻量结构化布局**（`zone` + `table_no` + `row/col` + 自动编号，影院图按分组渲染网格）。
**被否：自由拖拽画布**（admin 像画 CAD 一样摆座位坐标）。
- 影院式选座只需「分区 + 网格 + 占用态」，不需要像素级平面图；自由画布开发成本高、甲方维护更重，正是 ADR-0008 抱怨的放大版。
- 结构化布局够支撑影院图视觉（按桌型 / 分区分块，每块网格排座），且自动生成即可用。

### 取舍 C：具体座位互斥 vs 保留类型配额计数
**选定：具体座位区间互斥**（§2，单维度 `(store, seat_id, date)` 悲观锁 + 区间重叠判断）。
**被否：保留 ADR-0014 的逐格 `slotCapacity` 配额计数**。
- 用户选了具体座位，防超卖语义天然是「这个座位这段时间有没有被占」，与配额计数（数同类型还剩几个）不是一回事；继续用配额计数无法防「两人选同一个具体座位」。
- 具体座位互斥比逐格配额计数**更简单**：无需按格循环加锁，单座活跃单少，一次 `FOR UPDATE` + 重叠判断即可。

---

## Consequences

- ✅ 满足甲方三点诉求：座位有编号身份 + 影院自选 + 店内计时看板 + 前 N 名免费引流。
- ✅ 复用现有骨架：`gz_bean_booking.seat_id`/`seat_no_snapshot` 列还在（V1.2 只是停写）、`gz_bean_seat` 表未 DROP、旧 `dedup_token` / seat 锁思路可复活、免费单（实付≤0）后端逻辑已存在、mp `BizSeatList`/`BizSlotGrid`/`bean/staff-board.vue` 可复用——反转 0008 是「接回骨架 + 叠加」，非从零重建。
- ✅ 防超卖更简单（具体座位互斥单维度锁 < 逐格配额计数）。
- ⚠️ **重新引入 admin 座位维护**（ADR-0008 原始顾虑）：用「按桌型批量自动生成座位单元」把负担压到「填桌数」级别，不逐个画。
- ⚠️ **mp 下单流重构**：选桌型 → 选具体座位（影院图）；步骤顺序改为「选区间 → 选座」。
- ⚠️ **后端改造面**：`submitPaid` 防超卖维度 `seat_type_config_id` → `seat_id` 重叠；可用性接口 `type-slots` → `seat-map`；`verify_code` 签名因子改回 `seat_id`；新增座位单元 CRUD / 看板 / 促销三套 service。
- ⚠️ **`seat_type_config.quantity` 语义降级**为「批量生成桌数提示」，不再用于防超卖（列保留，doc/11 §3.4 备注更新）。
- ⚠️ **ADR-0014 §2「slotCapacity 逐格计数」与 ADR-0011 §3「逐格 quantity 比对」段失效**：被本 ADR §2 具体座位互斥取代；两 ADR 其余段（去字典自定义 / 按星期价 / 整点切格 / 一行存区间）保留。doc/11 §3.6 / §3.4 计数口径段按本 ADR 重写。
- ⚠️ **迁移 append-only**：新建迁移复活 `gz_bean_seat` 列升级 + booking 加列 + 促销表 + 重叠索引 + demo 座位单元 seed；旧 10 条 A1-A5/B1-B5 legacy 座位（仅 CD001，无 config 关联）保留不动（V1.0 历史，停用），新单只用新生成的带 config 座位单元。

---

## 待澄清 / 边界

| # | 问题 | 默认裁定 |
|---|---|---|
| F15.1 | 延时是否线上补付？ | **V1 不补付**（operational 延时，差额线下 / 门店政策）；线上超时计费列 V2 |
| F15.2 | 免费名额取消后是否回收？ | **不回收**（防刷，已发即占名额，桶计数含 cancelled 的 is_free 单）|
| F15.3 | 免费单是否仍要核销？ | **要**（免费单 `status='pending'`+`pay_status='paid'`，到店扫码核销同付费单）|
| F15.4 | 影院图是否要平面坐标？ | **不要**（结构化分区 + 网格，取舍 B）；像素级平面图列 V2 |
| F15.5 | 看板「临近结束」阈值 | sys_config `gz.bean.board.near_end_minutes`，默认 15 分钟，门店可调 |
| F15.6 | 旧 10 条 A1-A5/B1-B5 legacy 座位（仅 CD001）是否迁到新 config？ | **不迁**（V1.0 历史无 config 关联，停用保留）；新 demo 座位按 seed config 重新生成 |
| F15.7 | 同一用户能否同时段订同桌型多个座（如帮朋友订）？ | **能**（影院模型）。同用户幂等校验维度 = `seat_id`（非桌型）：仅防同一用户重复提交**同一个具体座位**（幂等返原单），不限制订多个不同空座。`countActiveUserOverlap` 按 `seat_id` 计数 |
