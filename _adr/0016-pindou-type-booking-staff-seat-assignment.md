# ADR-0016 拼豆预约「下单选桌型 + 核销时店员现场分座 + 配额防超卖」（取代 ADR-0015 §2/§3/§6）

- 日期：2026-06-30
- 状态：Accepted
- 决策人：Kevin（甲方计时系统新诉求；主线程 understand-workflow + 评估 + 落地）
- 关联 ticket：GZ-BEAN-034（后端：防超卖反转回配额 + 核销分座 + verify_code 去 seat_id）/ 035（看板②待分座区 + 排满 canExtend 信号 + 门店级 near_end 阈值）/ 036（admin：看板主动弹窗 + 核销分座 UI + 阈值配置）/ 037（mp：下单页砍自选座改选桌型档）
- 依赖与取代关系：
  - **取代 ADR-0015 §2**（防超卖「具体座位区间互斥」）→ 回到「桌型档逐格配额计数」（复用 ADR-0008/0011/0014 §2 仍在的 `slotCapacity` + `countActiveCoveringSlotForUpdate`）。
  - **取代 ADR-0015 §3**（下单流「选具体座位 + seat-map」）→ 「选桌型档（单/双/四）」，可用性接口回 `type-slots`（已存在）。
  - **取代 ADR-0015 §6**（`verify_code` 签名因子含 `seat_id`）→ 改回含 `seat_type`（`signByType` 已存在）；下单时无具体座位无法用 seat_id 签。
  - **保留 ADR-0015 §1**（`gz_bean_seat` 座位单元目录 + admin 批量生成）——它现在是**店员现场分座的物理座位池**，正是甲方「每个座位有编号」要的目录。
  - **保留 ADR-0015 §4/§5/§3.1**（前 N 名免费 / 看板放座·延时 / 逐格计价），不动。
  - **保留 ADR-0007**（付费双状态机 status × pay_status 正交，不动）。

---

## Context

甲方 2026-06-30 提出「后台计时系统」诉求，核心两点与 ADR-0015 现行模型方向相反：

- **mp 不显示具体座位编号，只显示单人/双人/四人桌型**；
- **客人到店核销时，店员按现场实际情况分配带编号的物理座位，再在后台把座位与预约挂钩**。

ADR-0015 当时为满足「影院式自选座」让用户在 mp 直接选具体座位（`seat_id` 下单即绑定）、防超卖按具体座位区间互斥。甲方现在要的是更贴合门店实际运营的「线上只锁桌型容量、到店由店员灵活落座（可并桌 / 安排 walk-in）」——与餐饮/自习室通行做法一致，且比自选座更简单。

**关键时间窗**：GZ-BEAN-022~033（座位单元 + 看板 + 免费 + 逐格计价）刚落代码、未 commit，此刻反转代价最低（无存量数据迁移；schema 列已具备，主要是 service 逻辑切换 + mp 下单 UI）。

## Decision

### 1. 下单维度：桌型档（不选具体座位）

mp 下单流 = 选门店 → 选日期 + 连续 1h 区间 → **选桌型档（`gz_bean_seat_type_config` 一行：单/双/四）** → 计价（逐格求和，ADR-0015 §3.1 不变）→ 付款/免费 → 核销码。`submitPaid` 入参 `seatId` → **`seatTypeConfigId`**。INSERT 时 `seat_id = NULL`、`seat_no_snapshot = NULL`，`seat_type / seat_type_config_id / book_mode_snapshot` 照写（计价/快照来源）。可用性接口回 `GET /app/gz/bean/booking/type-slots`（`selectTypeSlotAvailability` 已存在）。

### 2. 防超卖：回到桌型档逐格配额计数

下单事务内对区间每个 1h 格 gi（升序），`countActiveCoveringSlotForUpdate(tenant, store, configId, date, gi)` ≥ `slotCapacity(config)`（`book_mode='seat' ? quantity×capacity : quantity`）→ `QUOTA_FULL` 拒单整笔回滚。**具体座位区间互斥不在下单做**——下沉到 §3 核销分座。

**活跃口径（⚠️ 反转后铁律）= `status IN ('pending','used') AND pay_status IN ('paying','paid')`，止界 `COALESCE(actual_end_slot, slot_end)`——与 §3 具体座位互斥同口径**。ADR-0016 下「核销才占物理座」，pending（待到店占计划格）与 used（已核销占走 1 物理座）都必须计配额；若沿用 GZ-BEAN-017 旧 pending-only 口径（那是 ADR-0015「具体座互斥防超卖、配额仅展示」下成立），used 退出配额却仍占物理座 → 下单层超卖（付款后无座可分）。

**并发控制 = 逐格 FOR UPDATE 升序加锁（交叠区间锁顺序一致、无死锁）+ 方法级显式 `@Transactional(isolation=REPEATABLE_READ)`**。RR 下 COUNT...FOR UPDATE 靠间隙锁串行化并发同格 INSERT（COUNT 命中 0 行也锁索引区段）；显式声明 RR 锁死该前提，即便连接默认被切 RC 也不退化为可超发。**不再用 ADR 初稿设想的 `config:{store}:{config}:{date}` Redis 锁**（逐格 FOR UPDATE + RR 已是正确性真源，Redis 锁反而引入「锁被占→拒单」的跨用户误伤 UX）；Redis seat 锁仅 §3 核销分座用。

### 3. 核销分座：店员现场给预约绑定一个空闲物理座位

核销（`doVerify` / 扫码）入参增加 `seatId`（店员从该店该桌型空闲座中挑一个）。核销事务内校验：
1. 座位存在 + 属本店 + `enabled=1` + `seat_type_config_id` = 预约 `seat_type_config_id`（桌型匹配）；
2. **该座该预约区间未被占**：Redis seat 锁 + `selectActiveSeatOverlapForUpdate`（复用 ADR-0015 §2 的互斥逻辑，此处做并发控制，防两店员同时分到同一座）；
3. 通过 → 写 `booking.seat_id / seat_no_snapshot`（`status` 同时 pending→used、`verify_time` 照写）。

**计时窗 = 预约时段 `[slot_start, slot_end]`**（核销激活）。看板倒计时锚点 `slot_end`，**起算点 = `max(now, slot_start)`**：晚到不顺延（`now > slot_start` → 从 now 起算，与 no_show cron / 防超卖区间口径一致）；**早到不超发**（`now < slot_start` → 从 slot_start 起算，剩余永不超过预约时长）。⚠️ 起算点必须钳到 slot_start，否则核销早于时段开始时 `remaining = slot_end − now` 会超过预约时长（实测 09:32 核销、订 14:00–15:00 → 显 327min 的 bug）。

### 4. verify_code 签名因子改回 seat_type

下单时无具体座位 → 不能用 seat_id 签。改 `signByType(booking_no, sess_date, seat_type)`（已存在）。**存量已 paid 单（seat_id 非空、当年用 seat_id 签）核销仍走 `verifyByQrPayload` 既有的「seat_id 非空 → verify(seat_id) / 否则 verifyByType」判别分支**，天然兼容，不破存量（须回归测试守住）。

### 5. 计时看板：分两区（反转必然结果）

反转后「已约未到」付费单核销前**没有物理座位**，看板按物理座位组织会漏掉它们。看板分两区：
- **① 物理座位区**（按 `seat_id` 行）：已核销分座的单（in_use / near_end / overtime）+ 空闲座（idle）+ 放座/延时操作。
- **② 待分座区**（新增，按 booking 列）：已付款未核销单（按桌型 + 时段 + 数量）。店员核销动作 = 从②挑单 → 给它分①里一个空闲座。

### 6. 主动提醒 + 排满收尾 + 门店级阈值

- **门店级 near_end 阈值**：`gz_bean_store` 加列 `near_end_minutes`（默认 30），取代全局单值 `gz.bean.board.near_end_minutes`；admin 门店配置 UI 可改（甲方「店家自己设置 30/40/20」）。
- **排满信号**：`selectBoard` 给①区每个 near_end 行派生 `canExtend`（该座紧邻后续 1 格是否被占，批量算无 N+1）。`canExtend=false` → admin 提示「请客人收尾」，`true` → 「可问是否延时」。
- **admin 主动弹窗**：admin 看板前端轮询（已有 30s）diff 出新进入 near_end 的座 → `ElNotification` + 去重 + 可选声音。**不上 WebSocket**（店员本就盯看板，轮询延迟对 30min 提前量无影响）。
- **客人微信提醒**：订阅消息后置 V1.2（全新子系统 + 微信审核 + 一次性授权到达率有天花板，技术上无法承诺必达；甲方原文「最好」= nice-to-have）。

## 取舍记录

### 取舍 A：核销分座 vs 下单选座
**选定核销分座**。理由：甲方明确要店员现场按实际灵活落座（并桌 / 容纳 walk-in），线上自选座反而绑死。代价 = 防超卖维度反转 + 看板分两区，趁未 commit 做最省。

### 取舍 B：配额防超卖 vs 具体座位互斥
**选定配额计数**（回 ADR-0008/0011 思路）。理由：下单只锁桌型容量，「线上锁量、到店分座」语义天然是配额。具体座位互斥下沉到核销那一刻做（同一桌型的物理座位数 = 配额，保证核销时必有空座可分，见取舍 C）。

### 取舍 C：config.quantity ↔ 物理座位数一致性
`slotCapacity(config)`（= `book_mode='seat' ? quantity×capacity : quantity`）必须 = 该桌型可分物理座位数，否则「配额还有但没空座可分」。**选定：`config.quantity` 是桌数真源，admin「按桌型批量生成座位单元」按它生成等量物理座位（whole=quantity 个 / seat=quantity×capacity 个）→ 防超卖配额 = 物理座位数，构造即一致**，无需额外回写。边界：admin 事后单独停用/删除个别座位降低可分座数时，应同步调小 quantity 或重生成；未同步的兜底 = 核销分座时该桌型无空闲座则店员无法分座（可见、可改派别座），非静默物理超卖（`assignSeatAtVerify` 仍校验座位 enabled + 区间未占）。

## Consequences

- ✅ mp 下单更轻（选桌型档，无选座图）；契约 `seatId` → `seatTypeConfigId`。
- ✅ 店员现场落座灵活；物理座位目录（gz_bean_seat）复用零改。
- ⚠️ **后端改造面**：`submitPaid` 防超卖维度回配额（复活死代码 `countActiveCoveringSlotForUpdate`）+ Redis 锁改 config 维度；`doVerify` 新增分座校验 + 写 seat_id；`verify_code` 签名因子回 seat_type；看板新增②待分座区 + canExtend 派生；`gz_bean_store` 加 near_end_minutes 列。
- ⚠️ **存量已 paid 单核销**靠 `verifyByQrPayload` 既有 seat_id 判别分支兼容，**必须回归测试**。
- ⚠️ **ADR-0015 §2/§3/§6 失效**；§1（座位目录）/§4（免费）/§5（看板放座延时）/§3.1（逐格计价）保留。doc/11 §3.4/§3.6 计数口径段 + doc/10 §3/§11 下单·核销流按本 ADR 重写。
- ⚠️ 客人微信提醒后置 V1.2（已向甲方明确：admin 弹窗本期交付，微信受平台一次性授权规则限制无法承诺必达）。
