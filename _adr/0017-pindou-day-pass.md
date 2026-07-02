# ADR-0017 拼豆「包天套餐」（全天单复用逐格配额 + 名额 cap + 店员当下自主分座）

- 日期：2026-07-02
- 状态：Accepted
- 决策人：Kevin（甲方新诉求；主线程 brainstorm + 探索现模型 + 落地）
- 关联 ticket：GZ-BEAN-042（后端 submitDayPass + 名额 cap + config 加字段 / admin 配置 + 标识 / mp 模式切换）
- 依赖与保留关系：
  - **建立在 ADR-0016 之上**（下单选桌型档 + 逐格配额防超卖 + 核销时店员现场分座）——包天单对系统而言就是「时间范围 = 整天」的一条 booking，复用 0016 的全部机制。
  - **保留 ADR-0015 §5**（看板放座 / 延时 / `actual_end_slot` 止界）——包天单早退放座正是靠它释放剩余格。
  - **保留 ADR-0007**（status × pay_status 正交双状态机），不动。

---

## Context

甲方（店主）要给拼豆自习室加「包天套餐」：**老师买了包天后，那张座位当天所有时段被买断，其他座位照常按小时预约**；后台可按桌型配置**开放几个包天名额**（如单人桌 3 / 双人桌 5 / 四人桌 4）。

现模型（ADR-0016）= 下单选桌型档 + 逐格配额防超卖 + 核销时店员现场分座。包天与小时的本质差异：小时单只需自己那一格，而包天单需要**同一张座位横跨全天所有格**。核销时才分座的现模型对小时单没问题（每单只占自己那格），但对包天单有「碎片化」隐患：不同格可能空在不同座位，导致没有单一座位全天空闲。

## Decision

### 1. 包天单 = 一条全天范围 booking（`is_day_pass=1`）

包天单存成 `slot_start = 当日开店 / slot_end = 当日闭店` 的整天范围 booking（营业窗口来自 `gz_bean_time_slot_template`，取该日首格起 .. 末格止；该日无营业窗口 → `SLOT_RANGE_INVALID` 不静默）。`seat_id = NULL`（核销分座才写）、`is_free = 0`、`coupon_id = NULL`、`amount_cent = config.day_pass_price_cent`（固定价，非逐格求和）。新增 `gz_bean_booking.is_day_pass`、`gz_bean_seat_type_config.day_pass_quota / day_pass_price_cent` 三列。

### 2. 防超卖：复用逐格配额 + 新增名额 cap

- **小时可约量自动收缩，零改动**：现有 `countActiveCoveringSlotForUpdate` 计数条件 `slot_start <= gi AND COALESCE(actual_end_slot, slot_end) > gi`，一条全天单被营业窗口内每个 1h 格自动计入 → 小时侧不改任何代码，卖出包天即减小时可约量。
- **名额 cap（唯一新增防超卖）**：下单事务内 `countActiveDayPassForUpdate(tenant, store, config, date)`（`is_day_pass=1 AND status IN(pending,used) AND pay_status IN(paying,paid)`，`FOR UPDATE`）`≥ day_pass_quota` → `DAY_PASS_FULL(4024)`。走新窄索引 `idx_gz_bean_booking_daypass`，RR 下间隙锁串行化并发包天下单（命中 0 行也锁区段），与逐格 count 同前提；**cap 检查放逐格 count 之前**统一加锁顺序，与小时单只做逐格无交叉死锁。
- **总量不超卖**：包天下单同样跑全天每营业格的逐格配额检查（含已售包天单）→ 保证包天 + 小时总占用 ≤ `slotCapacity`。
- **config 铁律**：`day_pass_quota ≤ slotCapacity`（whole=quantity / seat=quantity×capacity），CRUD 强制校验（超界无意义：包天卖光即占满所有格）。

### 3. 座位：店员核销时现场分配（同小时单），当下自主

包天单不在下单绑座，具体物理座位由**店员**经现有「待分座区 / 核销分座」流程分配（`assignSeatAtVerify`），一旦分配该座当天买断。

**店员当下自主分座 —— 判「当下物理占用」而非区间/配额**（关键，GZ-BEAN-043）：核销分座能不能把某座给刚到的客人，取决于**这张椅子此刻空不空**，与该座早场被谁用过、与逐格配额账无关。故分座冲突判定（`assignSeatAtVerify` / 候选列表 `selectAssignableSeats`）走**当下物理占用**查询 `selectSeatOccupiedNowForUpdate` / `selectSeatOccupiedNowIds`：

> 当下占用 = `status='used'（已到店核销）AND actual_end_time IS NULL（未放座）AND slot_end > now（计划未到点）`。命中 → 有人在坐拒分；空 → 当下空闲可分。

- **分钟精度、放座即空**：不再沿用 `COALESCE(actual_end_slot, slot_end)`（放座向上取整整点是**逐格配额**的止界，卖出的整点格不可回收）。若拿它判物理占用，14:00-15:00 单坐到 14:30 放座后 `actual_end_slot=15:00` 会把椅子锁到 15:00，店员分不出去 = 「限制太死」。改用 `actual_end_time`（真实放座时刻）/ `slot_end`：**放座或到点即视为空出**。
- **落实「只要座位当下空闲就能分」**：早上用过又放座、或早场单已到点的座，当下重回可分（含分给整天/包天单）。碎片化基本消解（开店即分几无占用；午后到店只需一张当下空闲座）。
- **只看 `used`**：本模型座位仅核销时绑定，`pending` 单 `seat_id=NULL` 不占具体座；`cancelled/no_show/pay_closed/refunded` 全释放。
- **改派（`reassignSeat`）同口径**：改派整条续坐链到新座也判「当下物理占用」（新座此刻空即可，放座即空），与核销分座一致——刚放座 / 早场用过现已空的座也能改派过去。链成员均 `used` 各自覆盖时段 + 新座 Redis 锁 + `FOR UPDATE` → 未来时段不会被并发核销抢走（`used` 需已到点），故「当下空」= 剩余整链可安全占，不拆链。
- **并发不变**：Redis 座位锁（`tryLock`，第二个店员直接 SEAT_TAKEN）+ `FOR UPDATE` 串行化并发分座/改派，防两店员分同座 → 物理超卖。**逐格配额防超卖（下单侧 `countActiveCoveringSlotForUpdate` 用 `actual_end_slot`）完全不动**——物理分座与配额账分家。
- **仅延时（`extendSlotEnd`）+ seat-map 预览用区间查询**：延时是把已有单往后展（检查**未来新增格**是否被占，`selectActiveSeatOverlapExcludingForUpdate`）、seat-map 预览按下单区间展示占用（`selectOccupiedSeatIds`），两者保持区间/配额语义。

**下单不限「一人一座」（GZ-BEAN-044）**：同一用户可同门店同桌型同时段下多单（如家长给多个小孩各定一座）—— 已移除 `DUPLICATE_USER_BOOKING` 幂等拦截。防误连点仅靠用户提交锁（Redis 5s + `dedupClientToken` 合并 key，同一次点击的网络重试幂等；mp `onShow` 每次进页重生 token）；超卖由逐格配额 / 包天 cap 独立保证，与下单人身份无关。

### 4. 早退放座：允许（不加守卫）

老师订全天只坐半天 → 店员放座，走现有 release-seat 逻辑（`actual_end_slot` 已 clamp ≤ slot_end）→ 后续格 `COALESCE` 自动释放、该座后续可再约/再分。这是期望行为，**不加禁用守卫**。已售包天仍计名额 cap（当日已卖，早退不还名额）。

### 5. 定价 / 券 / 促销

- **定价 = 后台每桌型配固定包天价** `day_pass_price_cent`（分），非逐格求和、非折扣。
- **包天不可用券、不参与前 N 名免费**（`is_free=0`, `coupon_id=null`, `discount=0`），金额全额计入 GMV。

### 6. 幂等（默认）

同用户同日同桌型只允许 1 张活跃包天（复用 `countActiveUserOverlapByConfig`，全天范围天然拦重复）。如需放开「一人买多张（帮学生）」= 放宽该判断，一行改动。

## Consequences

- **好**：复用 0016 全部机制，后端新增面极小（1 迁移 + 3 列 + 1 cap mapper + 1 submit 方法 + 1 只读端点 + 分座起算点微调）；小时侧零改动；无新菜单/权限（复用 `gz:bean:seatTypeConfig:*` + `gz:bean:booking:*`）。
- **代价**：包天午后晚到 + 座位已被小时单严重打散的极端情形，可分座可能偏少（店员用现有改派腾座兜底）；不做「下单即自动锁座」（甲方明确要店员分配）。
- **端**：admin 桌型配置加「包天名额 / 包天价」；预约列表 + 看板待分座区加「包天」标识。mp 拼豆页加「按小时 / 包天」模式切换（包天模式选桌型 + 日期，固定价，不选时段/不用券）；详情/我的列表显「包天·全天」。
