# GZ-BEAN-054 — 拼豆临时桌型（看板可见 / 小程序不可订）

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md §M3 拼豆预约
**关联拆解**: doc/02-需求拆解.md §3.2 GZ-BEAN
**关联 mockup**: N/A（admin 走 ruoyi/Element Plus 默认审美，不引 mockup）
**关联 ADR**: doc/_adr/0023-pindou-internal-temp-seat-type.md（本 ticket 产出）· ADR-0016（核销现场分座）· ADR-0018 §2（排位）
**依赖**: 无

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md §3 拼豆预约全流程（下单选桌型 / 核销分座 / 看板）
- **字段表**：doc/11-字段权威表.md §3.4 `gz_bean_seat_type_config` + §3.5 `gz_bean_booking` + §3.12 店内计时看板
- **UI 参考**：N/A（admin 不评判视觉，只评判功能）

## What

给 `gz_bean_seat_type_config` 加 `mp_visible` 列，把「是否存在」（`enabled`）与「是否对小程序开放」（`mp_visible`）拆成两个正交轴。`mp_visible=0` 的桌型 = **临时桌**：看板有格、可 walk-in 计时、可承接线上单现场分座；小程序不展示不可订。同时放开 5 处「桌型严格匹配」闸，允许把线上单分座到临时桌。

## AC（验收标准）

### A. 数据模型

- [ ] AC1：迁移 `V<ts>__GZ-BEAN-054-seat-type-config-mp-visible.sql` 加列 `mp_visible TINYINT NOT NULL DEFAULT 1`（`AFTER enabled`）。**无新菜单 / 无新权限 / 无新索引**。
- [ ] AC2：**存量零行为变化** —— 迁移后不建任何临时桌时，`/app/gz/bean/booking/type-slots`、`/day-pass-options`、`/system/gz/bean/booking/board`、实时余量表 detail、营业额聚合的返回与迁移前逐字节一致（DEFAULT 1 保证）。

### B. 小程序侧过滤（6 处，全部必须加 `mp_visible=1`）

- [ ] AC3：`selectTypeSlotAvailability`（`GET /app/gz/bean/booking/type-slots`）wrapper 加 `.eq(GzBeanSeatTypeConfig::getMpVisible, 1)`。`curl` 断言临时桌不在返回里。`.active(TRUE)` 保持不动。
- [ ] AC4：`selectDayPassOptions`（`/day-pass-options`）同样过滤。
- [ ] AC5：`selectSeatMap` 的 `continue` 条件补 `|| mpVisible != 1`（防临时桌编号外泄）。
- [ ] AC6：`submitPaid` / `submitPaidGroup` / `submitDayPass` 三处在 `enabled` 检查后补 `mpVisible` 检查，**复用 `SEAT_TYPE_DISABLED=4013`**（这些路径只可能因竞态到达），日志用独立前缀 `[bean-*] seat type not mp-visible configId=` 区分。

### C. 内部面绝对不过滤（加了功能就白做）

- [ ] AC7：`selectBoard` 只保留 `cfg.enabled==1` 门槛 —— 临时桌座位**必须**出现在看板。
- [ ] AC8：`walkInCreate` / `adminCreateBooking` / `GzBeanSeatServiceImpl.resolveConfigs` / `batchGenerate` / 核销分座 / 排位 / 改派 / 放座 / 延时 / 座位 CRUD / admin `seatTypeConfig` list·listByStore·detail —— **全部不加过滤**。
- [ ] AC9：mp「我的预约」/ 详情按 booking 快照渲染，历史单仍能显示桌型名（不受过滤影响）。

### D. 判断项

- [ ] AC10：**实时余量表 `selectTypeSlotAvailabilityDetail` 加过滤排除临时桌**（这张表语义是「小程序可订多少 / 关几个不让订」，而 walk-in 故意绕过配额闸 → 给临时桌摆配额关闭 stepper 是拨了不生效的假开关）。同步 `GzBeanSlotQuotaCloseServiceImpl.upsert` 加防呆：`mp_visible=0` → 抛「临时桌不参与小程序配额关闭」。
- [ ] AC11：**营业额聚合 `GzBeanRevenueServiceImpl` 不加过滤** —— 临时桌上的现金 walk-in 是真钱，过滤掉是对账事故。断言：临时桌 walk-in 单出现在 `/aggregate` 拆分表里、金额正确。

### E. 放开线上单分座到临时桌（5 处）

- [ ] AC12：服务端 3 处强校验（`assignSeatAtVerify` / `preAssignSeat` / 改派 helper）从「同桌型」放宽为「**同桌型 ∪ 本店 `mp_visible=0` 的临时桌**」，其余情况仍抛 `SEAT_TYPE_MISMATCH=4022`。
- [ ] AC13：候选座 2 处查询（`selectAssignableSeats` / `selectPreAssignCandidates`）返回「同桌型 ∪ 本店临时桌」，**正常桌型在前、临时桌垫底**；`GzBeanSeatVO` 加派生 `temp: boolean`。
- [ ] AC14：**booking 的 `seat_type_config_id` / `seat_type_snapshot` 快照不变** —— 分到临时桌后营业额仍算在客人买的桌型上（curl 断言）。

### F. 后端其余

- [ ] AC15：entity / VO / BO / QueryBo 加 `mpVisible`；`GzBeanBoardRowVO` 加 `mpVisible`（`selectBoard` 与 `toBoardRow` **各回填一次**）；`GzBeanSeatVO` 加 `temp`。
- [ ] AC16：⚠️ `GzBeanSeatTypeConfigServiceImpl.toEntity` 是**手写字段拷贝**，必须补 `e.setMpVisible(bo.getMpVisible() == null ? 1 : bo.getMpVisible())` —— 漏改会静默丢失。`buildWrapper` 加条件式 `eq`。
- [ ] AC17：新增 `validateMpVisible`：`mpVisible==0 && dayPassQuota>0` → 抛「临时桌不支持包天套餐」（包天是纯 mp 概念）。
- [ ] AC18：`batchGenerate` 返回值从 `int` 升为 `{created, skipped, skippedSeatNos}`（`upsertSeatUnit` 命中已存在正常座会幂等跳过返 0，前缀撞号时店员会「点了生成但什么都没多」）。

### G. plus-ui

- [ ] AC19：`seat-type-config/index.vue` 表单在 `bookMode` 后插「用途」`el-radio-group`（1=小程序可订 / 0=仅后台临时桌）+ hint；`mpVisible===0` 时 `dayPassQuota`/`dayPassPriceYuan` 禁用并归 0、「按星期价格」按钮隐藏。
- [ ] AC20：列表加「渠道」列 —— **只对临时桌渲 `el-tag warning`「临时桌」，正常行留空**（保持表格安静）；查询条加渠道下拉（纯前端 computed 过滤，后端零改动）。
- [ ] AC21：保存成功且 `mpVisible===0 && quantity>0` → `ElMessageBox.prompt`「是否立即生成 N 个计时格？编号前缀：」（默认 `T`+序号）→ 直调 `batchGenerateGzBeanSeat`；`skipped>0` 时 warning 列出被跳过的 seatNo。
- [ ] AC22：数量字段 hint 补「数量 × 每桌座位数 = 看板上会生成几个计时格」+「营业额报表按桌型名拆分，请用可读名称（如：临时四人桌）」。
- [ ] AC23：`board/index.vue` 的 `BoardGroup` 加 `temp`；`groupedRows` 里 `temp: r.mpVisible === 0` 且**排序让临时组垫底**（店员肌肉记忆不能因周末加桌错位）；组头加 `el-tag warning` + `.board-zone.is-temp` 虚线左边框 + 极浅底。顶部 metric **不排除**临时桌。
- [ ] AC24：分座 / 改派弹窗里临时桌选项打「临时」标且排在后面。
- [ ] AC25：`seat/index.vue` typeName 后加同款 tag，批量生成下拉 label 加「（临时）」后缀（零后端改动）。
- [ ] AC26：`slot-availability/index.vue` alert 文案补「仅统计对小程序开放的桌型」。

### H. 质量闸

- [ ] AC27：新增可见文案全部走 `t('...')`，`zh_CN.ts` + `en_US.ts` **同 key 同步**；模板内无硬编码中文。
- [ ] AC28：`pnpm type-check` + eslint 通过，无 `any`。
- [ ] AC29：Tier 1B Playwright：建临时桌（含一键生格）→ 看板出现该组且垫底带 tag → walk-in 开台 → 放座/延时/改派可用 → 线上四人桌单能分座到临时四人桌 → console 0 error。
- [ ] 纯 admin + 后端 ticket，无 mp AC N（CLAUDE.md §8.2）。

## Tech

| 文件 | 动作 |
|---|---|
| `ruoyi-admin/.../db/migration/V<ts>__GZ-BEAN-054-seat-type-config-mp-visible.sql` | 新增 |
| `ruoyi-gz-bean/.../service/impl/GzBeanBookingServiceImpl.java` | 6 处 mp 过滤 + 3 处分座闸放开 + 2 处候选查询 + 余量表 detail 过滤 + 看板 VO 回填 |
| `ruoyi-gz-bean/.../service/impl/GzBeanSeatTypeConfigServiceImpl.java` | `toEntity` 补字段（**手写拷贝易漏**）+ `buildWrapper` + `validateMpVisible` |
| `ruoyi-gz-bean/.../service/impl/GzBeanSeatServiceImpl.java` | `batchGenerate` 返回结构升级 |
| `ruoyi-gz-bean/.../service/impl/GzBeanSlotQuotaCloseServiceImpl.java` | `upsert` 防呆 |
| `ruoyi-gz-bean/.../domain/{entity,vo,bo}/` | `GzBeanSeatTypeConfig` / VO / Bo / QueryBo 加 `mpVisible`；`GzBeanBoardRowVO` 加 `mpVisible`；`GzBeanSeatVO` 加 `temp`；新增 `GzBeanSeatBatchGenerateResultVO` |
| `plus-ui/src/views/gz-bean/{seat-type-config,board,seat,slot-availability}/index.vue` | 见 AC19-26 |
| `plus-ui/src/api/gz-bean/{seatTypeConfig,seat,board}.ts` | 类型同步 |
| `plus-ui/src/lang/{zh_CN,en_US}.ts` | `gzBeanSeatTypeConfig` / `gzBeanBoard` / `gzBeanSeat` / `gzBeanSlotAvailability` 段 |

## 备注

- 命名取 `mp_visible` 而不是 `is_temp`：不变量只有「不进小程序」，`is_temp` 会承诺一个不存在的时间语义。**UI 上仍叫「临时桌」**（甲方的词），DB/API 用机制名。
- 甲方「不用就不填就行了」= 临时桌平时 `enabled=1` 空着（看板几个 idle 格），不需要每周切开关。
- `GzBeanBookingServiceImpl` 里有一条既有注释（「客人 mp 买双人桌、实际坐四人桌…桌型/座位对不上无法 assignSeatAtVerify」）—— 桌型严格是有意决策，本次放开是**受控例外**（临时桌本来就没有线上对应），要写进 ADR-0023。
- **交付说明必须写**：店员在临时桌勾「免费」的 walk-in 单**照常吃掉当期前 N 名免费名额**（既有行为，非本次引入）。
- 改 gz-bean 模块后必须 `mvn clean install`（非 clean 既不重打 jar 也不重编译测试，exit 0 骗人）。

---

## §revision（Kevin 节点触发残留人验不过时填，初始空）
