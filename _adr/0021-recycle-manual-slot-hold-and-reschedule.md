# ADR-0021 回收手动占用时段（代客预约 + 临时关闭合一）+ 预约改期 + 看板周视图

- **状态**：已决（待实施）
- **日期**：2026-08-15
- **关联**：ADR-0012（回收单份多选 + 去估价 + 到店核销码）/ ADR-0018 §2（拼豆排位，店员侧物理化的同类范式）/ doc/10 §13 / doc/11 §12

## 背景

甲方微信原话：「回收业务的部分需要后台可以自己关闭时间」，并要求放到「回收看板」上，「类似拼豆的排位，让店员直观看到怎么排的，有时候还需要给老师调整，比如老师申请了周一下午，通过联系改成了周二上午」。

拆出来是三个能力：

1. **代客预约** —— 店员替线下 / 电话来的老师占住一个到店时段；
2. **预约改期** —— 已提交的单子，店员电话沟通后挪到别的日期 / 时段；
3. **看板周视图** —— 回收看板从「今日到店概览」升为「当前周未完成预订」，占用与调整都在看板上直接做。

第一轮调研（拼豆 `walkInCreate` 完整实现 + 回收域现有模型）抛了 11 个开放问题，甲方 / Kevin 这轮给了决定性简化：

- 代客预约**只需要暂住时间格 + 一句备注**，店员自行规划 —— 不要顾客手机号 / 账号关联、不要点数档、不要金额、不要照片、不要「核销 / 排位」二选一；
- **暂不自动打款**，店员线下先收 / 付款 —— 手动占用类记录完全不进打款流程；
- **「关闭时间」本意就是临时关闭这个时段，本质与代客预约同一件事**，区别只在备注写什么，系统不需要区分；
- 看板做在 **plus-ui admin（电脑后台）**，不做 mp 店员端镜像；
- 代客预约不拍照。

因此本 ADR 的核心动作是**做减法**：把「代客预约」和「临时关闭时段」收敛成同一个底层机制 —— **手动占用时段（manual hold）**。

---

## 决策 §1：手动占用时段 = 代客预约 + 临时关闭的唯一机制

### 语义

一条手动占用 = 「**某门店 × 某日期 × 某到店时段格**被店员占住」+ 一句**备注**。系统不区分它是「给老师留的」还是「今天这个点不接单」—— 两者对系统的效果完全一致：**该格不再可被 mp 顾客选中**，看板上显示为已占并带备注。

### 输入 / 输出

- 入参：`storeId` + `apptDate` + `timeSlotId[]`（可一次选多格）+ `remark`（**必填**）。
- 无：客户身份 / 手机号 / 点数档 / 金额 / 照片 / 核销码 / 打款。
- 出参：每格一条独立记录（N 格 = N 行，同一事务 all-or-nothing）。
- 释放：店员在看板对**单个格**释放 → 该行 `cancelled`，格立即可约。

**`remark` 必填**：手动占用没有客户身份、没有点数档，备注是这条记录**唯一的辨识信息**。允许空备注 = 看板上出现一堆分不清用途的灰格，店员第二天自己也不知道当初为什么占。

**多格 = 多行，不建组 id**：跨格的整体性对业务没有意义（店员按格释放才是真实动线），加 `group_no` 只会让释放 / 看板多一层分支。

### 落库：复用 `gz_recycle_appointment` 单表 + `source` 列区分

**结论：不建独立 `gz_recycle_slot_hold` 表，手动占用就是同一张预约表里少填几个字段的一行**，靠 `source`（`mp` / `manual`）+ `status='manual_hold'` 区分。

理由：

- 「某格是否被占」在系统里是**一条查询**（`countActiveHoldingSlotForUpdate`，mp 下单防超卖 / mp 时段可用性 / 看板三处共用）。拆两张表 → 这条查询要变 UNION，而它的正确性根基是 `FOR UPDATE` 间隙锁 + REPEATABLE_READ，**跨两表的间隙锁串行化远比单表难保证**（防超卖是回收域最贵的资产，不能为建模洁癖赔进去）。
- 回收单模型本身已经很轻（无物理座位、无分钟区间、无支付态列），手动占用与顾客单的差别只是「少了几个字段」，不是「另一种实体」。
- 看板要在同一个格里并排显示「顾客单」和「手动占用」，同表天然同构。

### 状态：新增独立状态 `manual_hold`，不复用 `submitted`

`manual_hold` 是手动占用的**唯一活跃态**，终态为 `cancelled`（店员释放）。

为什么不复用 `submitted`（这是本 ADR 收益最大的一条）：现有所有下游守卫都写死 `status='submitted'`，用新状态可让手动占用记录**零改动地被全部下游天然排除**：

| 下游 | 守卫 | 手动占用记录的结果 |
|---|---|---|
| 店员核对 + 触发打款 `verifyAndPayout` | `status='submitted'` 否则 `4105` | 天然拒绝，**不进打款** |
| no_show 凌晨任务 `selectExpiredSubmittedIds` | `status='submitted'` | 天然不扫 → 过期占用不会变成 `no_show` 脏数据 |
| 打款查单收敛 `selectSyncablePayoutIds` | `status IN ('paying','payout_failed')` | 天然不扫 |
| 核销码签发 `getVerifyCode` | `status ∈ {submitted, confirmed_onsite}` | 天然 `4109`（手动占用无码可取，也没有顾客来取） |
| 一人一单守卫 `USER_ACTIVE_STATUSES` | 不含 `manual_hold` | 天然不影响顾客可约性 |

而占用侧只需**加一个常量值**：`ACTIVE_HOLD_STATUSES` 增加 `manual_hold` → mp 防超卖 + mp 时段可用性两处同时生效（同源常量）。

### 为什么不照搬拼豆 `walkInCreate`

拼豆代客预约（`walkInCreate`，约 200 行）背着：具体物理座位 + 分钟精度区间 + immediate/future 双分支 + 未放座 / 超时赖座互斥 + 金额与免费促销 + 「核销 / 排位」二选一 + 共享「线下散客」占位用户（`resolveProxyBookingUserId`）。这套在回收上**逐条不成立**：

1. **一人一单守卫会撞车**：回收有 `countActiveByUserForUpdate`（错误码 `4127`），拼豆没有。照抄「共享线下散客占位账号」 → 第 2 条手动占用就会被自己的守卫挡死（同一个占位账号已有进行中单）。绕过它要么污染守卫口径（对真顾客失效），要么给占位账号开后门（守卫形同虚设）。**正解是根本不关联用户**：`user_id` 置 NULL。
2. **打款脏单风险**：回收单的下游是**真实资金出账**。任何带 `receiver_openid` 的假单都是资金事故的入口。`receiver_openid` 置 NULL + `status='manual_hold'` 双重保证手动记录永远够不到 `initiatePayout`。
3. **模型本来就简单**：回收没有座位、没有分钟精度 —— 占用单位就是 admin 已配好的「到店时段格」（`gz_recycle_time_slot`），格是离散的、天然互斥的，不需要区间重叠算法。
4. **甲方明确要的就是「占住格子 + 一句备注」**，多做一分都是净负债。

> ⚠️ 附带排掉的雷：`verifyAndPayout` 里 `receiverOpenid` 非空校验（`4106`）发生在自动打款开关（`gz.recycle.auto_payout.enabled`，默认关）判断**之前**。既然手动记录永不进这条路径，本 ADR 不动这个顺序；但**若将来放开手动记录走核对流，必须先把开关判断提到 openid 校验之前**，否则「现金结算模式 + 无 openid 记录」会被 4106 无谓卡死。

---

## 决策 §2：预约改期 = 原地 UPDATE（不取消重建）

### 适用范围

- `submitted` 的顾客单（老师电话改期，甲方原话场景）；
- `manual_hold` 的手动占用（店员挪格）。

`confirmed_onsite` / `paying` / `paid` / `cancelled` / `no_show` **一律拒绝**（`4128 RESCHEDULE_NOT_ALLOWED`）—— 已核对即已发生实物交割，改期无意义且会污染资金链路。

### 动作

在**同一行**上 UPDATE：`appt_date` / `time_slot_id` / `slot_start` / `slot_end` / `spill_time_slot_id`。`id`、`appointment_no`、`user_id`、`product_snapshot_json`、点数档全部不动。

### 为什么是原地 UPDATE 而不是「取消 + 重建」

**核销码 payload 不含日期 / 时段**：格式为 `RC|{appointmentNo}|{appointmentId}|{expireEpochSec}|{verifyCode}`，签名因子 = `appointmentNo + appointmentId + expireEpochSec`（`RecycleQrSigner`）。因此：

- 原地 UPDATE → **顾客手机里已经生成的核销码改期后依然有效**，不需要通知顾客重新取码，到店照扫。
- 取消 + 重建 → `appointment_no` 与 `id` 都变，旧码指向一张 `cancelled` 单（扫出 `4105`），顾客到店扫码失败；且单据链断成两截，日后追溯 / 打款对账要跨单拼。

附带好处：改期次数、原单历史、打款关联全部留在一行上，admin 详情不需要「前身单」跳转。

### 三条硬约束（实施必守）

1. **容量校验必须排除自身**：改期目标格的占用判定不能直接用 `countActiveHoldingSlotForUpdate` —— 该查询会把**本单自己**算成占用者。典型翻车：同店同日「10:00 档 → 15:00 档」，若本单是大单、原本 spill 占了 15:00，自己会把自己挡回 `4122/4123`。
   → 新增 mapper 变体 `countActiveHoldingSlotExcludingForUpdate(tenantId, storeId, apptDate, slotId, excludeId)`（`AND id <> #{excludeId}`），改期路径**只**用这个变体。
2. **spill 必须按新档位置重算**：`spill_time_slot_id` 的值取决于「新档在该店 enabled 时段有序列表里的**下一档**」，随改期位置变化；改到末档时按 FLAT 规则**必须显式置 NULL**（不能只在非空时更新，否则残留旧 spill 会长期误占一个无关格）。
   ⚠️ **但「占几格」本身必须取提交时的冻结快照，不得活查点数档表**：`product_snapshot_json.occupyNextSlot`（提交时从 `gz_recycle_qty_range.occupy_next_slot` 冻结）。禁用某点数档 / 编辑其 `occupy_next_slot` 都是正常运营动作，若改期时用 `getEnabledByCode` 活查，档一禁用即返 null → 大单的 spill 被算成 false 并显式置 NULL → 溢出格立刻对外放开、与本单实际到店时长物理双占。旧单无快照时退化为「按 code 忽略 `enabled` 查档 → 仍取不到则看本单 `spill_time_slot_id` 是否非空」，口径不确定时一律偏向不放开格。
   手动占用无点数档 → `spill_time_slot_id` 恒 NULL（要占两格就选两格建两行）。
3. **锁只锁目标 `(store, 新 date)`**：复用 submit 的 `gz:recycle:lock:slot:{storeId}:{date}` Redis 锁 + `FOR UPDATE` + REPEATABLE_READ。**旧格的释放不需要锁**（释放不会造成超卖），这样也规避了「A: 5/1→5/2 与 B: 5/2→5/1 同时改期」的双锁死锁。

### 其他口径

- **不允许跨门店改期**（`store_id` 不可改）。换门店 = 取消重约。跨店改期会引入跨门店双锁 + 顾客到店门店与快照不符两类麻烦，收益为零（甲方场景是同店换时间）。
- **状态推进用 version 乐观锁**：改期 UPDATE 的 WHERE 带 `status IN ('submitted','manual_hold') AND version = #{version}`，affected=0 视为并发 → 报 `4128`（同 `markConfirmedOnsite` 范式）。
- **不给顾客发通知**：甲方原话即「通过联系改成了周二上午」—— 改期是电话沟通的结果，不是系统触发的事件。不发订阅消息。
- **审计三列**：`reschedule_count` / `last_reschedule_by` / `last_reschedule_time`。**不建改期历史子表**（多次改期的中间态对业务无价值）；「从哪个日期时段改到哪个」写 ruoyi 操作日志（`@Log`），admin 详情显示「已改期 N 次（最后由 X 于 T）」。

---

## 决策 §3：回收看板 = 当前周 × 时段格矩阵（承载面）

现有「回收看板」（menu 13002，`gz-recycle/appointment/index`）= 今日到店概览 + 可筛选回收记录。改为**周视图**，§1 / §2 的全部动作挂在格上。

- **视图**：选门店（沿用页内 storeOptions）+ 选周（默认本周，可翻周）→ **7 天 × 该店 enabled 到店时段** 的矩阵。
- **格的四种状态**：空闲 / 顾客单（手机尾号 + 点数档 + 状态 tag）/ 手动占用（备注）/ 被大单溢出占用（标注属于哪一单，不可再操作，需操作源单）。
- **格上动作**：空格 → 手动占用（可多选后一次提交）；手动占用格 → 改期 / 释放；顾客单格 → 改期 / 核销（跳现有核对流）/ 取消。
- **「当前周未完成预订」口径** = 活跃占用态（`submitted` / `confirmed_onsite` / `paying` / `paid` / `payout_failed` / `manual_hold`），与防超卖同源常量。
- **不跨店混排**（各店时段配置不同，混排无法对齐列）。
- 下方「回收记录」筛选列表保留不动。
- **不做 mp 店员端镜像**（甲方定：看板在电脑后台）。

---

## 明确澄清：与现有「回收时段全局开关」并存，不替代

`gz_recycle_time_slot.enabled`（admin「回收配置」→「回收时段」tab）是**门店级永久开关**：关掉的档对**所有日期**生效，mp 不展示、看板不出这一列。这个开关**继续保留，本 ADR 不动它**。

本 ADR 新增的是**按日期维度的临时占用**（数据行级，只影响所选那一天那一格）。两者是**不同粒度、串联生效**：

```
先按 time_slot.enabled 过滤出该店有哪些时段列  →  再看该(日期,格)是否存在活跃占用行
   （永久 / 全日期 / 配置）                          （临时 / 单日 / 数据）
```

甲方说的「后台可以自己关闭时间」= 后者（临时关闭某天某档），不是去改前者。

---

## 数据模型

一张表 `gz_recycle_appointment` 承载两类记录，差异全部由 `source` + `status` 表达：

| 列 | 顾客单（`source='mp'`）| 手动占用（`source='manual'`）|
|---|---|---|
| `user_id` | 提交用户 | **NULL** |
| `receiver_openid` | openid 快照 | **NULL** |
| `product_snapshot_json` | 点数档对象 | **NULL** |
| `mobile_snapshot` | 手机号快照 | NULL |
| `matched_duration_minutes` / `total_qty` / `estimated_amount_cent` | 桶映射 / 0 | 0（DB 默认，不写） |
| `submit_image_ids` | NULL（已停采集） | NULL |
| `time_slot_id` / `slot_start` / `slot_end` / `appt_date` / `store_id` | 有 | **有**（占用的就是这个格） |
| `spill_time_slot_id` | 大单有 | 恒 NULL |
| `remark` | 顾客下单备注 | **店员备注（必填，唯一辨识信息）** |
| `status` | `submitted` → … | `manual_hold` → `cancelled` |
| `final_amount_cent` / `verify_*` / `out_payout_no` | 核对 / 打款时写 | 恒 NULL |
| 操作人 | — | `create_by`（admin 会话自动填，**不加新列**） |

### 迁移（append-only 新文件，时间戳取 `date +V%Y%m%d%H%M`）

1. **放宽三列 NOT NULL**（手动占用行没有客户身份）：`user_id` / `receiver_openid` / `product_snapshot_json` → `NULL`。
   （`total_qty` / `matched_duration_minutes` / `estimated_amount_cent` 是 `NOT NULL DEFAULT 0`，MP 的 `NOT_NULL` 字段策略会把 null 字段排除出 INSERT → 落 DB 默认 0，**无需改**。）
2. **新增列**：
   - `source VARCHAR(16) NOT NULL DEFAULT 'mp'` —— `mp`（顾客自助）/ `manual`（店员手动占用）；索引进 `(tenant_id, store_id, appt_date)` 一族的查询即可，不单独建索引。
   - `reschedule_count INT NOT NULL DEFAULT 0`
   - `last_reschedule_by VARCHAR(64) NULL`
   - `last_reschedule_time DATETIME(3) NULL`
3. **字典**：`gz_recycle_status` 增 `manual_hold` = 「手动占用」。
4. **菜单 / 权限**：挂在现有回收看板 13002 下，新增两个按钮节点（13xxx 段空号 **13015 / 13016**）：
   - `gz:recycle:appointment:hold` —— 手动占用 / 释放占用
   - `gz:recycle:appointment:reschedule` —— 改期
   （新角色授权只授 `menu_type='F'` 节点、不授父 `'C'`；改权限后 admin 需重登。）

### 错误码（回收域 412x 段续）

| code | 常量 | 文案 |
|---|---|---|
| 4128 | `RESCHEDULE_NOT_ALLOWED` | 该预约当前状态不可改期 |
| 4129 | `HOLD_RELEASE_NOT_ALLOWED` | 仅手动占用记录可在看板释放 |
| 4130 | `RESCHEDULE_DATE_PAST` | 顾客预约不能改到已过去的日期（手动占用豁免，见坑位 13）|

占用冲突复用现有：`4122 SLOT_TAKEN` / `4123 SLOT_SPILL_BLOCKED` / `4124 SLOT_INVALID` / `4126 SLOT_LOCK_BUSY`。备注必填走 BO `@NotBlank`（参数校验，不占业务码）。

---

## 关键实现坑位（实施必读，漏一条就是线上事故）

1. **手动占用绝不能走 `submit()`**：那条路径会依次撞 一人一单守卫（`4127`）、openid 必填（`4103`）、手机号必填（`4125`）、点数档必填（`4107`）。必须写独立 `manualHold()`，只走「时段合法性 + 容量校验 + INSERT」三步。
2. **`ACTIVE_HOLD_STATUSES` 必须加 `manual_hold`**，否则手动占用不挡 mp 下单 —— 整个功能等于白做（顾客照样能约进被「关闭」的时段）。改这一个常量同时生效于 `countActiveHoldingSlotForUpdate`（防超卖，SQL 内联字面量）与 `getSlotAvailability`（mp 灰格）**两处**；⚠️ mapper 里的状态集是 `@Select` 内联字面量、无法引用 Java 常量，**两处必须同步改**，改一处 = 防超卖与 UI 口径分叉。
3. **`USER_ACTIVE_STATUSES`（一人一单）不加 `manual_hold`**：手动记录 `user_id` 为 NULL 本就不匹配，但要显式声明口径，防止后人「顺手补齐」把顾客可约性搞坏。
4. **改期容量校验必须用 `...ExcludingForUpdate` 变体**（排除自身 id），否则同店同日改到相邻档会被自己的旧占用挡住（大单 spill 场景必现）。
5. **改期后 spill 显式重算并允许置 NULL**（见 §2 约束 2）。
6. **手动记录不得进打款**：不放宽 `verifyAndPayout` 的 `status='submitted'` 守卫；`receiver_openid` 恒 NULL 是第二道闸。这两条任一被「优化」掉都可能造成对空 openid 发起真实转账。
7. **mp 店员当日列表 `listStaffByDate` 是全状态查询** → 手动记录会出现在里面。**收口为后端查询加 `source <> 'manual'` 过滤，直接排除**（不做 mp 端渲染分支——看板是手动占用的唯一承载面，mp 因此零代码改动）。若日后店员反馈"占了但 mp 看不到"，再评估要不要开 mp ticket 做占用条目渲染。
8. **mp「我的回收」不受影响**：`selectMyList` 按 `user_id` 等值查，NULL 行天然不命中 —— 但不要「顺手」给手动记录填占位 user_id（见 §1 为什么不照搬拼豆）。
9. **no_show cron 不扫 `manual_hold`**（守卫 `status='submitted'`）：过期的手动占用就静静躺着，因为占用判定按 `appt_date` 过滤，历史日期不影响任何未来格。**不需要**给它加清理任务。
10. **迁移 append-only 铁律**：新建文件，绝不改已应用迁移；时间戳用 `date +V%Y%m%d%H%M` 当下真实时间。
11. **回收站注册表**（`RecycleEntityRegistry`，gz-common）当前**未注册** `gz_recycle_appointment` → 本次列变更无跨模块耦合风险；若日后注册，注意 `source`/NULL 列的展示列取值。
12. **改期重算 spill 只读提交时的冻结快照**（`product_snapshot_json.occupyNextSlot`），**不活查点数档表** —— 见 §2 约束 2 的 ⚠️。活查是超卖入口：禁用一个点数档（正常运营）就会让此后任何对该档既有大单的改期静默丢掉溢出格。提交链路则**必须**继续用 `getEnabledByCode`（禁用档必须 `4107`）—— 两条路径的查询方法**刻意不同**，不要「统一」。
13. **顾客单不得改到过去日期**（`4130`）：`markExpiredNoShow` 的 SQL 是 `status='submitted' AND appt_date < CURDATE()`，一旦被误改到过去，顾客的有效预约下次扫描即被判 `no_show`。**手动占用刻意豁免**：`manual_hold` 不被任何 cron 扫、历史日期不影响未来格，店员回填昨天的台账是真实动线（也让本周多为过去日期的看板 E2E 能正常跑改期）。

---

## 影响面

- **后端**（`ruoyi-gz-recycle`）：新增 `manualHold` / `releaseHold` / `reschedule` / `weekBoard` 四个 service 方法 + 对应 admin 端点（`/system/gz/recycle/appointment/*`）；新增 1 个 mapper 查询变体 + 1 个周区间批量查询；`ACTIVE_HOLD_STATUSES` 加值（Java 常量 + mapper 内联两处）；2 个错误码。
- **Admin**（plus-ui）：`gz-recycle/appointment/index.vue` 顶部看板由「今日分组」改「周矩阵」+ 手动占用弹窗 + 改期弹窗；下方记录列表不动。
- **mp**：**零改动**（`getSlotAvailability` 自动继承新占用态）。
- **合同**：属现有回收功能的运营优化（不新增业务线、不改分成口径），在 4% 分成对价内的「小幅迭代」，**不触发 §8.5**。

### 测试红线

- 手动占用后 mp 同格下单必被拒（`4122`）—— **真 DB 连续两步集成**，mock 照不出。
- 手动占用记录走不到核对 / 打款（`verifyAndPayout` 返 `4105`；`selectSyncablePayoutIds` 扫不到）。
- 一人一单守卫在建了 N 条手动占用后对真实顾客**依然只挡 1 单**（不被污染）。
- 改期到「自己 spill 占着的相邻档」必须成功（排除自身），改期到末档后 `spill_time_slot_id` 必须为 NULL。
- 并发改期同一目标格：只有一条成功，另一条 `4122`（真 DB 双线程）。

## 不做的事（边界）

- 手动占用不关联顾客账号 / 不记手机号 / 不记金额 / 不拍照 / 不发核销码。
- 不做 mp 店员端看板镜像。
- 不做改期历史子表、不做改期通知顾客。
- 不动 `gz_recycle_time_slot.enabled` 全局开关的语义。
- 不开自动打款（`gz.recycle.auto_payout.enabled` 保持默认关，店内现金结算）。
