# GZ-BEAN-042 拼豆包天套餐（Day-Pass）

> 决策权威：[ADR-0017](../../../_adr/0017-pindou-day-pass.md)。全栈（后端 + admin + mp）。

## What

老师买「包天套餐」= 当天该座位全天买断，其余座位照常按小时预约；后台按桌型配开放几个包天名额（如单人桌 3 / 双人桌 5 / 四人桌 4）。包天单 = 一条全天范围 booking，复用 ADR-0016 逐格配额 + 核销分座；名额 cap 单独防超卖；固定包天价；不用券、不参与免费促销、全额计入 GMV。座位由店员核销时现场分配（当下空闲即可分）；早退可放座释放剩余格。

## AC

- **AC1（config 配置）**：admin 桌型配置可配 `day_pass_quota`（0=不开放）+ 固定包天价；校验 `quota ≤ slotCapacity`、price ≥ 0。
- **AC2（下单防超卖）**：mp 包天模式选桌型 + 日期 → 提交。名额满 → `DAY_PASS_FULL(4024)`；未开放 → `DAY_PASS_NOT_OPEN(4025)`；总量满 → `QUOTA_FULL(4011)`；当日无营业时段 → `SLOT_RANGE_INVALID(4016)`。cap + 全天逐格 count 均 `FOR UPDATE` + `REPEATABLE_READ`。
- **AC3（减小时可约量）**：卖出 1 包天后，该桌型每个 1h 格的小时可约量 −1（现有 `countActiveCoveringSlotForUpdate` 自动逐格计入，小时侧零改动）。
- **AC4（全天买断 + 当下自主分座）**：包天单核销分座后未放座前，同座任一小时单核销分该座 → `SEAT_TAKEN(4002)`；分座互斥起算点 = `max(slot_start, floorToHour(now))`，午后到店可分「早上用过、现在已空」的座。
- **AC5（早退放座）**：包天单坐半天放座后，其后续格 `countActiveCoveringSlot` 归零、该座后续格可再分/再约。
- **AC6（定价 / 券 / 促销）**：`amount_cent == day_pass_price_cent`（固定价）；`is_free=0`、`coupon_id=null`、`discount=0`，全额进 GMV。
- **AC7(a)（mp 模拟器可达）**：kevin-qa 用 run.mjs 程序化导航到拼豆页，切「包天套餐」模式、选桌型、断言固定价渲染 + 提交流。
- **AC8（admin E2E）**：桌型配置表单配 quota + 价、预约列表 / 看板待分座区包天标识。

## 关联

- 权威蓝图：ADR-0017 / ADR-0016（下单选桌型 + 核销分座）/ ADR-0015 §5（放座止界）
- 权限：复用 `gz:bean:seatTypeConfig:*` + `gz:bean:booking:*`（无新菜单/权限迁移）
- 迁移：`V202607050004__GZ-BEAN-042-day-pass.sql`

## §revision（节点触发残留人验回填）

### 2026-07-02 — 核销分座「限制太死」（GZ-BEAN-043，ADR-0017 §3 修订）

**现象**：A 定 3-6 点、B 定 3-4 点，店员给 B 分 S2；4 点 B 离场、A 才到，店员想把 S2 分给 A → 报 SEAT_TAKEN。「不要限制那么死，只要座位当下空闲就应能分」。

**根因**：核销分座的占用判定沿用**逐格配额**口径——起算点 `floorToHour(now)` + 占用止界 `COALESCE(actual_end_slot, slot_end)`（放座向上取整整点，卖出的格不可回收）。于是 B 放座后 `actual_end_slot` 仍锁到整点，S2 到点前分不出去；物理在座与配额账被耦合。

**修**：核销分座改判**当下物理占用**（`used + actual_end_time IS NULL + slot_end > now`，分钟精度、放座即空），与配额账分家。新增 `selectSeatOccupiedNowForUpdate` / `selectSeatOccupiedNowIds`，重接 `assignSeatAtVerify` + `selectAssignableSeats`；延时/改派（查未来区间）与 seat-map 预览不动；逐格防超卖不动；并发靠 Redis 座位锁 + FOR UPDATE 不变。详见 ADR-0017 §3。

**验证**：gz-bean 单测 207 全绿（+1 present-moment 回归锁）；scratch-DB 旧/新逐座对比（放座座 old=卡到整点 / new=即空）；真机端到端（建 A+B → 核销 B→S1 → A 候选剔除 S1 → 放座 B → S1 重回候选 → 核销 A→S1 成功，非 SEAT_TAKEN）。

### 2026-07-02 — 放开「一人一座」+ 改派对齐当下语义（GZ-BEAN-044，ADR-0017 §3）

**现象/需求**：① 店主要求一个用户可同时段订同桌型多个座位（给小孩各定一座）—— 现拦 `DUPLICATE_USER_BOOKING(4003)`；② 上条把核销分座改判「当下物理占用」后，改派（`reassignSeat`）仍用旧区间/配额查询，刚放座的座改派不过去（同「限制太死」）。全流程限制审计（59 条）后，Kevin 决策：A 跨桌型分座**保持同型** / B 取消 20min 窗口**保持** / C 改派**对齐当下语义** / D 其他域暂不查。

**改**：
- **① 删 `DUPLICATE_USER_BOOKING` 幂等拦截**（小时单 + 包天单），删死掉的 `countActiveUserOverlap`/`ByConfig` mapper。防误连点仅靠 5s 用户提交锁 + `dedupClientToken`；超卖由逐格配额 / 包天 cap 独立保证。
- **② 改派改判当下物理占用**：`assignChainToSeat` 用 `selectSeatOccupiedNowForUpdate`（放座即空）替代 `selectActiveSeatOverlapForUpdate`（区间/配额），关闭规则起算点 clamp 到当下；保留新座 Redis 锁 + `FOR UPDATE` 防拆链。

**验证**：gz-bean 单测 206 全绿（新增「同用户第二单放行」+ 改派 present-moment 回归锁）；真机端到端：① 同手机号同时段 2 单均 200（旧第 2 单 4003）；② B 当前小时槽核销后**槽内放座**（`actual_end_slot` ceil 到整点 > now，旧区间必判占）→ 改派 A→放座座 **200 + seat_id 落位**。
