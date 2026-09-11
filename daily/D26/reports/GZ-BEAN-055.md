# GZ-BEAN-055 完工报告 — 配额 ↔ 计时格对齐

## §0 状态自检

| 项 | 结果 |
|---|---|
| 四仓分支 | RuoYi-Vue-Plus / plus-ui 均 `staging`；doc 在 `feat/jp-daigou-requirements` |
| 上游 ticket | GZ-BEAN-054（临时桌）已 merge，`mp_visible` 列在库 |
| 关键类硬检查 | `GzBeanSeatServiceImpl` / `GzBeanSeatTypeConfigServiceImpl` / `selectBoard` 均存在 |
| 迁移 | **本批无 DDL**，无需查空号 |
| ADR 已读 | ADR-0014 §2（配额分母）· ADR-0016 取舍 C（配额 = 可分物理座位数）· ADR-0023（临时桌两轴正交） |
| 编译健康 | `mvn -o compile -pl ruoyi-gz-bean -am` EXIT=0 |

## §1 根因定位（先取证，后动手）

**证据 1 —— 两个计数器在代码里各走各的**

```
GzBeanBookingServiceImpl:1986  slotCapacity(config)      → quantity × capacity   （小程序卖几个）
GzBeanBookingServiceImpl:2625  selectBoard()             → gz_bean_seat 实际行数  （看板几个格）
GzBeanSeatTypeConfigServiceImpl  全文 grep seatMapper / batchGenerate → 0 命中     （改数量不动座位）
GzBeanSeatServiceImpl.upsertSeatUnit  只有 插入 / 复活 / 跳过 三个分支              （只增不减）
seat-type-config/index.vue:726  const justCreatedTemp = isAdd && ...              （编辑不弹窗）
```

**证据 2 —— dev 库当场抓到同款错配（未做任何改动）**

```
configId=1 单人    数量=1  整桌  →  小程序每格卖 1   |  看板 8 格   ← 同款
configId=2 双人    数量=4  整桌  →  小程序每格卖 4   |  看板 4 格   ✓
configId=3 四人桌  2×4     按座  →  小程序每格卖 8   |  看板 8 格   ✓
```

**证据 3 —— 打真接口坐实售卖侧**

```
GET /system/gz/bean/booking/availability/detail?storeId=1&sessDate=<明天>
[{"seatTypeConfigId":"1","name":"单人","slotStart":"10:00","opened":1,"booked":0,"remaining":1}, ...]
```
看板上摆着 8 个「单人」格子，小程序每小时只肯卖 **1** 个。

**证据 4 —— 看板会丢孤儿单（事故级，既有 bug）**

```java
// selectBoard：遍历的是座位，bySeat 里没被消费的 booking 直接丢弃
for (GzBeanSeat seat : seats) { List<GzBeanBooking> seatBookings = bySeat.get(seat.getId()); ... }
return result;
// ②待分座区：只收 seat_id IS NULL 的单
// GzBeanSeatServiceImpl.deleteByIds：裸 baseMapper.deleteByIds(ids)，零守卫
```
→ 移除一个还挂着单的座位，那笔已付款单**①区没座位、②区不收**，从看板上彻底消失。

## §2 改了什么

**后端 `ruoyi-gz-bean`（10 改 + 2 新，452 行）**

| 文件 | 改动 |
|---|---|
| `GzBeanBookingMapper` | 新增 `selectSeatIdsWithActiveBookings`（活跃口径与 `selectActiveBookingsForBoard` 逐字一致 + `sess_date >= 今天`） |
| `GzBeanSeatMapper` | 新增 `countUnitsByConfigIds`（一次 group by 出 `cells`/`units`）+ 内部 `SeatUnitCount` |
| `GzBeanSeatServiceImpl` | `assertSeatsRemovable` 守卫接进 `deleteByIds` / `toggleEnabled(0)`；新增 `syncSeatUnits` + `expectedSeatUnits` + `resolveSyncPrefix` + `longestCommonPrefix`；**修复软删复活判定** |
| `GzBeanSeatTypeConfigServiceImpl` | `fillSeatUnitCounts` 批量回填三个派生字段；新增 `validateBookModeChange` 订法守卫 |
| `GzBeanSeatController` | `POST /sync/{seatTypeConfigId}` + `buildSyncMsg`（含「仍不符」兜底提示） |
| `GzBeanSeatTypeConfigVO` | 加 `expectedCells` / `boardCells` / `disabledCells` |
| `GzBeanSeatSyncResultVO` | 新建 |
| `GzBeanSeat` / `GzBeanSeatMapper` 注释 | 修正 3 处「`del_flag='2'`」的错误说明 |

**plus-ui（5 改，223 行）**：`seat.ts` 加 sync API + VO；`seatTypeConfig.ts` 加三个派生字段；
`seat-type-config/index.vue` 加「计时格」列 + 错配判定/tooltip + 编辑后同步确认 + 列表同步按钮 + 告警样式；
`zh_CN.ts` / `en_US.ts` 各加 14 key（110 = 110 对齐）。

## §3 自测 raw output

### 3.1 后端单测 278/278

```
[INFO] Tests run: 118, Failures: 0 -- GzBeanBookingServiceImplTest
[INFO] Tests run: 25,  Failures: 0 -- GzBeanSeatServiceImplTest
[INFO] Tests run: 14,  Failures: 0 -- GzBeanSeatSyncServiceImplTest       ← 本批新增
[INFO] Tests run: 30,  Failures: 0 -- GzBeanSeatTypeConfigServiceImplTest
[INFO] Tests run: 278, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### 3.2 真库：移除守卫（挂着已付款单的 S8）

```
=== B. 删除守卫：删挂着预约的 S8(id=31) ===
  code=500  msg=删除座位失败：S8 还挂着今天及以后的预约。请先在看板上把这些单改派到其它座位，或等预约结束后再操作。
=== C. 停用守卫：停用同一个座位 ===
  code=500  msg=停用座位失败：S8 还挂着今天及以后的预约。请先在看板上把这些单改派到其它座位，或等预约结束后再操作。
=== D. 对照：删没有预约的 S7(id=30) 应当放行 ===
  code=200  msg=操作成功
```

### 3.3 真库：同步缩减 —— 挂单的座位保留不删

```
=== E. 同步 config 1（单人：数量=1，现有 7 个座，其中 S8 挂着预约）===
  msg: 计时格已对齐：7 → 2（配置应有 1）；移除 5 个（S2、S3、S4、S5、S6）；S8 还挂着预约未移除，请先在看板上改派这些单
  expected=1 before=7 after=2 created=0 pruned=5
  prunedSeatNos = ['S2','S3','S4','S5','S6']
  blockedSeatNos= ['S8']  ← 挂着预约，没删

=== F. 库里核对 ===
| seat_no | del_flag |     S1=0  S2..S7=1  S8=0  ← S8 存活，那笔已付款单不会从看板消失
```

### 3.4 真库：软删复活修复前 / 后对比

```
修复前（判 del_flag=="2"，实际库里是 '1'）：
  msg: 计时格已对齐：2 → 2（配置应有 8）
  expected=8 before=2 after=2 created=0    ← 静默什么都没做，msg 还像成功

修复后（判「非 '0' 即已删」）：
  msg: 计时格已对齐：2 → 8（配置应有 8）；新增 6 个（编号前缀 S）
  expected=8 before=2 after=8 created=6 prefix=S
库里：id 17/21/24/27/29/30 原地复活（del_flag 1→0），没有制造新行、没浪费编号
```

### 3.5 真库：订法守卫 + 最终对齐

```
=== I. 给已有 8 个座位的「单人」改订法 whole → seat ===
  code=500  msg=该桌型已生成 8 个座位单元，不能再改订法（整桌与按座的编号规则不同）。请先到「座位单元」删除这些座位，再改订法。

=== J. 最终状态 ===
  ✓ id=1 单人    数量=8 每桌=1 应有=8 看板=8
  ✓ id=2 双人    数量=4 每桌=2 应有=4 看板=4
  ✓ id=3 四人桌  数量=2 每桌=4 应有=8 看板=8

=== K. 看板真实格数（selectBoard 口径）===
  合计 20 格 → {'双人': 4, '单人': 8, '四人桌': 8}
```

### 3.6 admin 真浏览器全流程（0 console error）

```
① 基线            计时格列 = 8/8 · 4/4 · 8/8，无警示、无同步按钮
② 编辑 8 → 10     弹窗「看板实际 8 个计时格，按当前配置应有 10 个。现在对齐吗？」[稍后][立即同步]
③ 立即同步        → 单人 数量=10 计时格=10/10，mismatchCount=0
④ 编辑 10 → 8     弹窗「看板实际 10 个计时格，按当前配置应有 8 个。现在对齐吗？」
⑤ 点「稍后」      → 计时格 10/8 告警色 rgb(230,162,60) + 出现「同步计时格」按钮（错配行才有）
⑥ 点「同步计时格」 确认「…将移除多出的 2 个。仍挂着预约的座位不会被移除。确定同步吗？」
⑦ 执行            toast「计时格已对齐：10 → 8（配置应有 8）；移除 2 个（S9、S10）」→ 8/8，仍错配=0
console errors: 0
```

### 3.7 前端静态检查

```
vue-tsc  → 本批 5 个改动文件零错（全量 72 条均为既有基线，文件清单与本批无交集）
eslint   → 5 个文件 EXIT=0
i18n     → zh 110 key / en 110 key，zh-only=[] en-only=[]
```

## §4 已知 issue / 风险

1. **方案 A 未做**（`slotCapacity()` 改成数实际座位行）：会改变线上每小时实际售卖量，
   属商业口径变更，需甲方确认。本批只保证「漂了看得见 + 能一键对齐」。
2. **`expectedCells` 公式现有 3 份物理拷贝**（`GzBeanBookingServiceImpl.slotCapacity` /
   `GzBeanSeatServiceImpl.expectedSeatUnits` / `GzBeanSeatTypeConfigServiceImpl.expectedCells`），
   跨 service 无共享基类。三处都写了互相指认的注释，但没有机械守卫 —— 若日后再改配额口径需三处同改。
3. **停用座位仍会让 `boardCells < expectedCells`**，这是合法状态（店员停用坏椅子），
   已由 `disabledCells` + tooltip 解释；同步不会自作主张把它们改回启用。
4. **prod 存量错配需人工扫一遍**：本批只提供工具，不自动批量对齐所有门店（那属于改数据，需 Kevin 决定）。

## §5 对下游的提示

- 以后**任何**新增「移除座位」的路径（批量删、清理脚本、数据迁移）必须过 `assertSeatsRemovable`，
  否则会重新引入「已付款单从看板消失」。
- 判软删一律用「非 `'0'` 即已删」，不要再写死删除值 —— 全局配的是 `logicDeleteValue: 1`。
- mp 侧未改动，无需重建 `dist/dev`。
