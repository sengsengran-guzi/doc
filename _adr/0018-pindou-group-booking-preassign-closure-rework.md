# ADR-0018 拼豆 7.05 批改：组单预订 / 排位 / 关闭重做

- **状态**：已决 + 已实现（§1/§2/§3 落地并真 DB 验证；§1 mp 流程「桌型→人数→时间按 N 动态灰」+ §3 seat_closure 从余量/下单闸退休 于 2026-07-07 补齐）
- **日期**：2026-07-06（7-07 补实现）
- **关联**：ADR-0016（下单选桌型档 + 核销现场分座）/ ADR-0017（包天）/ doc/11 §3

## 背景

甲方 7.05 三条修改建议：

1. 一个家长带 5 个孩子下单，如何最优上桌；
2. 排位——把待核销单提前排到座位框下、显「待核销」；客人到店后上层放座、下层核销自动落座；「未核销列表」改名「未排位客人」；看板一眼看清谁该坐哪、谁催收尾、谁可续；
3. 「关闭座位」功能太复杂、难用。

三条本质都是**店员侧物理座位化**：mp 顾客侧（选桌型档、不见座位号，ADR-0016）只有 §1 组单需要动，§2/§3 全在 admin 店员侧。**§2 排位是锚点**——做了它，§1 的整组排位与 §3 的座位视角都顺。这不推翻 ADR-0016 的「顾客选桌型」——那是顾客侧；店员侧一直是物理座位思维（核销时现场分座），本 ADR 只把店员分座**提前**并在看板上**可见**。

---

## 决策 §1：组单预订 = 拆 N 条子单 + 组聚合表（非「一单带 quantity」）

### 下单流（mp）
选门店 → 选日期 → 选桌型 → **选数量 N** → 选时间段：

- **N 上限 = 该桌型每格配置总量**（whole 取 `quantity`；seat 取 `quantity × capacity`，即现有逐格配额分母）。
- **时段按 N 变灰**：已选桌型 + 数量 N 后，区间内任一 1h 格「剩余 < N」→ 该格灰、不可选（剩余 = 配置总量 − 活跃单 − 关闭数）。
- 价 = N × 区间逐格求和价。

### 后端建模
- 一次提交在**一个事务**里生成 **N 条子单**，每条 = 1 单位 = 1 座，复用现有单模型；共享 `group_no`。
- 新表 **`gz_bean_booking_group`**（`group_no` / `out_trade_no` / `total_amount_cent` / `pay_status` / `user_id` / `store_id`）承载**支付与退款聚合**；子单各记 per-unit `amount_cent`（GMV 报表口径不变），`pay_status` 由组驱动。`out_trade_no` 唯一约束落在组上，不破坏单级唯一。
- **防超卖**：组提交原子扣 N 份逐格配额，区间每格都够才成单（all-or-nothing）。

**为什么不是「一条单带 quantity=N」**：看板 / 核销 / 放座 / 延时 / 改派 / 占用互斥 / 退款全是「按单按座」。一单 N 座会把每个下游都改成「一单多座」，爆炸半径最大。拆子单让这些机器零改动，复杂度集中在下单 + 支付聚合。

### 优惠口径
- **组单不可用券**（甲方 7.05 定）。
- **组单不参与前 N 名免费促销**（与「不可用券」同口径：组单全价。本 ADR 锁定；如需放开说一声）。

### 店员侧
- N 条子单在「未排位客人」列表带**组标签**（组 · N 人 · 手机尾号）。
- **整组排位**：一次把组内 N 条排到店员选定的 N 个相邻座（= §2 preAssign 的批量）。
- **整组核销**：客人整组到店，一次核销全组（子单各自核销码复用，admin 一个动作核销全组）。
- 退款走**整组**；组内单人 no_show 按**子单**标记，不触发整组退款（部分退款不在本版范围）。
- mp「我的」把一组显示为一笔订单 · N 个单位。

### 商业边界（合同）
组单 = 新增下单 / 支付 / 退款聚合模块，明显超「小幅迭代」→ **触发合同 §8.5**，就工时 / 排期 / 费用书面另议。§2 排位 / §3 关闭重做属现有功能优化，在 4% 分成对价内、不另计。

---

## 决策 §2：排位 = 提前写 seat_id，激活休眠的 reserved 看板态

### 现状
座位只在**核销那刻**写 `seat_id`（现场分座）；未核销单 `seat_id` 恒空，只躺顶部「待分座」卡片列表，挂不到任何座位。看板早已定义 `reserved`（已约未到）态，但因 pending 单 `seat_id` 恒空、永不挂座 → 该状态**休眠**。

### 决策
- 复用 `gz_bean_booking.seat_id`，新增**排位**动作 `preAssignSeat(bookingId, seatId)`：给 pending+paid 单**提前写 seat_id、状态仍 pending** → 激活 `reserved`。
- 反向 `unassignSeat(bookingId)` 清 seat_id → 回「未排位客人」列表。
- **物理占用互斥校验**从「只数 used」扩到「也数 reserved（pending + 已排位）」，防两单排到同座且区间重叠。
- 看板：
  - 「待分座」列表查询已是 `seat_id IS NULL AND status=pending AND pay_status=paid` → 排位后**自动离开列表**（零查询改动）；仅改标题为「**未排位客人**」。
  - 座位取当前单从「每座一张」（`pickCurrentBooking`）改为返 **current（在座 used）+ next（待核销 reserved）**两层：座位框上层放座、下层核销。
  - 核销用该单**已排的座**、不再弹选座弹窗。
- `no_show` cron 过期时**一并清 seat_id**（否则排了没来的座永卡 reserved）。

### 效果
店员在客人到店前把单排到座位，看板一眼看清：谁在座（倒计时 / 临近结束 → 催收尾）、谁待核销（下一位坐哪）、谁可续（`canExtend`）。

### 座位格 UI = 分层双栏格（4 套并行方案评审定稿，GZ-BEAN-048）
座位格已背 6~9 条信息，再叠「下一位·待核销」一层易糊。4 套布局并行设计经 3 评委（店员动线 / 信息可视化 / Element Plus 落地）打分，**一致选「分层双栏格」**（评审留档 `design/mockup/_review/gz-bean-board-cell-compare.html`）：

- **每格固定切上下两栏**：上栏 = 在座（`in_use/near_end/overtime`），下栏 = 已排到本座的待核销（`reserved`）。
- **动作按栏归属直接上格**：上栏底排「放座（主）+ 延时 / 改派（次）」；下栏底排「核销（主）+ 取消排位（次）」。放座在上、核销在下，对应客户原话「上面放座、下面核销自动接位」的竖直物理动线。
- **两处糅合**（补方案1「固定两栏浪费一半高度」的软肋）：① **空栏坍缩**——单层态时空的那栏收成细条，只有真两层才撑满，找回一屏座位数；② **左侧状态色棒 + 右上状态图标**——远距离扫墙秒辨。
- 配色：上栏随剩余时间 绿(在座)→黄(临近)→红(超时)，下栏恒蓝(待核销)；修饰信息（免费 / 续坐 / 组·N人 / 备注）降为小 chip 挂各自栏内。

---

## 决策 §3：关闭 = 去掉两套旧关闭，重做「桌型 × 某天 × 自由时段 × 关闭数量」引导式

### 现状（两套都嫌复杂，一并去掉）
- `gz_bean_seat_closure`：按**具体座位 × 每周星期 × 时段**，多选三维表单（甲方点名「复杂」）。
- `gz_bean_slot_quota_close`：按**桌型 × 某天 × 逐个 1h 格 × 关闭数量**，余量表格逐格设。

### 决策
- **退休按座位的 `seat_closure`**（页 + 配额查询不再消费它）；「某座永久坏」= **删掉该座位**（`gz_bean_seat` 软删 `del_flag='1'`）。<br>（原文写「用座位管理里现成的 `seat.enabled=0`」—— 该列已由 **ADR-0024（2026-09-26）** 删除，理由：它对顾客侧无效果、只挡店员分座；口径统一为「坏了就删座位」，不再有"半存在"的座位态。）
- **保留 `gz_bean_slot_quota_close` 作存储**，前端换成**引导式一把设**：
  1. 选桌型；
  2. 选某天（**默认今天**）；
  3. **自由选时间段**（跨多个 1h 格，非单格）；
  4. 展示该时段内**各小时的当前预约数量**（booked / 配置总量 / 已关）；
  5. 输入**关闭数量 N** → 对区间每个 1h 格 upsert `closeCount = N`。
- **可选「设为每周循环」开关**：`slot_quota_close` 加 `weekday`（可空）+ `sess_date` 可空；填日期 = 临时一次，开循环 = 按 `weekday` 每周生效；配额查询判 `(sess_date = 当天) OR (weekday = 当天星期)`。（本开关是次要项，默认关=仅当天；如嫌多可砍。）
- 配额可用量 = 配置总量 − 活跃单 − `closeCount`；与 §1 的「N 变灰」同源。

**为什么引导式 + 显示预约数量**：店员关闭前先看到「这个时段各小时已经订了几个」，再决定关几个，避免误关已订满的格。把「关闭」从抽象规则变成「看着实际占用做决定」。

---

## 影响面 / 迁移

- **新增**：`gz_bean_booking_group` 表；`gz_bean_booking` 加 `group_no` 列；`gz_bean_slot_quota_close` 加 `weekday` 列 + `sess_date` 改可空。
- **退休**：`seat_closure` 页 + 相关 menu 软下线（数据表按 Flyway append-only 铁律保留不删；配额查询停止消费）。
- **Flyway**：新迁移 append-only、时间戳取 `date +V%Y%m%d%H%M` 当下真实时间（新表 + alter add column）。
- **menu / 权限**：组单 / 排位复用 `gz:bean:booking:verify`（不新建 menu）；关闭重做复用现有 gz-bean 关闭权限段。
- **测试红线**（沿用 §8）：组单防超卖并发扣 N（真 DB 连续两组集成，mock 照不出）；排位物理占用含 reserved 的互斥；关闭 closeCount 生效于配额可用量。

---

## 实现补记（2026-07-07 补齐 §1 流程 + §3 退休）

甲方 7.06 走查两问 → 补齐两处此前只写进 ADR 未落地的实现（Kevin AskUserQuestion 拍板）：

- **§1 mp 流程按本 ADR §1 落地**：人数上移为独立步骤（选桌型 → **选人数** → 时间），时间格按每格 `remaining < N` 动态灰（此前 053 把人数塞在计价面板、上限写死 10、无动态灰）。为支持动态灰，mp `type-slots` VO 加 `remaining`（**仅逻辑用、UI 仍只渲染可约/已满两态、不显数字**——阈值随 N 移动，不破「不暴露余量数字」铁律）；`slotFitsN`/`maxUnitsForType` 纯逻辑单测覆盖。组单不支持包天（isGroup 时包天 chip 灰）。
- **§3 seat_closure 从余量/下单闸退休**（此前只隐藏了管理入口、数据仍泄漏）：`selectTypeSlotAvailability`（mp）/`selectTypeSlotAvailabilityDetail`（admin）/`submitPaid`/`submitPaidGroup`/`submitDayPass`/`adminCreateBooking` 六处**不再减 `closedSeat`**，余量/有效配额一律 `= 配置总量 − 活跃单 − quotaClose`；admin 余量表「座位关闭」列删除（VO/TS 去 `closedSeat` 字段）；dev 26 行遗留 seat_closure 软禁用。**保留** `findClosedSeatIds` 的核销分座 guard（座坏了不可分是另一轴）。根因：seat_closure 是物理座数（0..8），配置配额是数量制（单人=1），拿座数减配额 = 牛头不对马嘴 → 单人被压成约满。
- **踩坑**：① 增量 `test-compile` 不重编依赖变更的测试 → 假绿；`mvn clean install` 才逮出测试引用已删的 `getClosedSeat()`（CLAUDE.md「改 gz 必 clean install」再次应验）。② clean build 顺带逮出 §2 两层看板遗留过时断言：纯 reserved 座（无人在座）身份在**下栏 `nextBookingNo`**、上栏 `bookingNo` 为 null，旧单测仍断言 `getBookingNo()` → 修正为 `getNextBookingNo()`。**真 DB 验证全绿**：单人今日 remaining 恢复 1（原 0/约满）、type-slots remaining 下发、组单 N=3 于四人桌原子扣减 8→5。

## 补记二（2026-07-07 甲方走查三项：步进器 / 排位候选座 / 组单详情）

- **①「一起几人」步进器**（mp bean）：`wd-input-number` 无 size 属性、mp 难穿透其内部样式 → 换**自定义大按钮步进器**（`.qty-step` 76rpx 方块 +/− + 居中数字），一并解决「按钮太小」+「数字不居中」。
- **② 排位弹窗只列整天 idle 座 → 被占座凭空消失**（甲方「D4 去哪了」）：`board/index.vue` `assignSeatOptions` 三模式共用「board `idle`（整天空）」过滤，排位（未到店单）却该用**目标 slot 区间重叠**（对齐后端 preAssign）。**修**：新端点 `GET /system/gz/bean/booking/{id}/preassign-candidates`（`selectPreAssignCandidates`，复用 `selectActiveBookingsForBoard` 内存按区间重叠算 + 排除本单）返回**同桌型全部启用座 + 每座 `assignable` / `occupiedUntil`**；`GzBeanSeatVO` 加两字段；前端排位模式改用它，被占座**显示但置灰标「占用至 HH:mm」**，可排座正常选。**verify / reassign 分支逐字不动**（present-moment 口径本就对，不回归）。真 DB 验证：BK..0005(双人 12:00-13:00) 候选 D1-D4——D4(被 11:14-12:14 占) `assignable=false occupiedUntil=12:14`、D3(09:16-11:10 不重叠) `assignable=true`。
- **③ 组单支付后跳「预约不存在」**：mp 拿**组 PK** 当**子单 PK** 查 `/pages/bean/detail` → 查不到。**修（A 档，甲方选）= 组显示为一笔、逐子单核销不变**（真「一次核销」B 档待定）：新端点 `GET /app/gz/bean/booking/group/{groupId}`（`selectGroupDetailVo`：组头 + 门店/桌型 enrich + N 子单聚合状态）；mp 新 `group-detail.vue`（一笔订单 + N 子单各「查看核销码」跳子单详情）；`settleAndGoDetail(vo, isGroup)` 组单跳组详情 + 组级 `closeUnpaidGroup`；「我的」`foldGroups` 客户端把同 `groupId` 子单折叠成一张「N 人」卡（`groupId` 加进 mp `BookingDetailVO`）。真 DB 验证：group-detail 返回一笔(2人·双人·¥56) + 2 子单。
- **验证**：gz-bean 236 单测绿；mp vitest 109（含 foldGroups 4 例）绿；前后端 eslint 净；两新端点真 DB 全绿。**B 档「组一个码一次核销」（组级 verify_code + verify-group 端点 + admin 整组核销 UI + DDL）待 Kevin 拍板启动**。

## 补记三（2026-07-07 店内计时看板视觉重设：对齐 §2 c1「分层双栏格」mockup）

甲方走查「看板 UI 和最初定的差别太大」→ 按 [design/mockup/_review/gz-bean-board-cell-compare.html](../../design/mockup/_review/gz-bean-board-cell-compare.html) 的 **c1「分层双栏格」（评委首选 8.5）** 把 `plus-ui board/index.vue` 从简版补齐到 mockup 视觉：**统计条**（5 计数卡：已排位待核销/在座中/临近结束/已超时/空闲，颜色语义）+ **图例 + 动线说明**；座位格 **上栏在座**（底色随剩余时间 绿→黄→红 + 大数字倒计时「剩/超 MM:SS」+「HH:mm 起」+ 续坐/免费 chip + 放座/延时/改派）/ **下栏待核销**（蓝底 + 核销/取消排位）；**空态占位文字**（当前无人在座 / 暂无下一位 / 无排位）+ 空闲格「代客预约」；新增 **超时倒计时「超 MM:SS」**（原止于「即将结束」）。kevin-qa Playwright 验收：**0 JS error**，D4 超时双栏格样本渲染正确，统计条/图例/空闲格全到位。**未做（c1 rec 的可选糅合，非 blocker）**：空栏坍缩（c1 mockup 本身也是保留占位不坍缩，故不做即对齐 mockup；座位数 30+ 需密度时再加）。**左侧状态色棒（糅合②）已应甲方要求去掉**——状态靠右上胶囊 + 上栏底色 + 超时红框表达，卡片左边不再有加粗色条。纯 plus-ui 前端 + i18n，eslint 净。
