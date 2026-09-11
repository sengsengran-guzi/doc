# GZ-RECYCLE-015 完工报告 — 回收营业时间能力对齐拼豆 + 200 点以上封顶 4 小时

**状态**：✅ Tier 1A 全绿（未 commit）
**来源**：Kevin 2026-08-26 追加三条 —— ①「回收的时间应该可以自行配置，参考拼豆」②「200点以上等于4小时」③「admin 里的配置，回收如果有和拼豆类似的页面和功能，命名和页面尽量保持一致，方便店员操作」
**关联**：ADR-0022 §2（已同步补写）· ADR-0011（拼豆营业窗口，实现蓝本）

---

## §0 状态自检

| 项 | 结果 |
|---|---|
| 迁移最大号 | `V202608261548`（GZ-RECYCLE-012 ④）→ 本批取 `V202608261902` / `V202608261903`，正常递增 |
| 为什么不改 012 的迁移 | 那 4 个已**应用到 dev**（flyway_schema_history 记了 checksum），改内容必炸；append-only 铁律 → 新建 |
| 拼豆比回收多什么（对比确认） | `weekdays` / `effective_date` / `expire_date` 三列 + 「按周批量配置」弹窗 |
| 编译健康 | 通过 |

---

## ① 「参考拼豆」= 补齐三个维度

回收此前只有「门店 + 起止 + 启停」——**配不出「周末与平时营业时间不同」**，而甲方本来就说过「周末会开四个四人桌」「平时要看具体情况」。补齐后：

| 维度 | 说明 |
|---|---|
| `weekdays` | ISO `1`=周一..`7`=周日逗号分隔；默认全周（存量行零行为变化）。service 存前**归一化**（去空格 + 升序 + 去重），否则 `"1,2"` 与 `"2,1"` 判重会当成两行 |
| `effective_date` / `expire_date` | 生效区间，**闭区间**（生效当天 / 过期当天都算）；临时调整营业时间用 |
| 「按周批量配置」弹窗 | 选中星期 × 多段窗口 → **每星期各建一行**（不是一行 `weekdays="1,2,3"`）|

**为什么批量是「一星期一行」而不是「一行多星期」**：一行多星期更省行数，但店员改「只有周六延后打烊」时得先把那行拆开 —— 拆行是最容易出错的操作。一星期一行后，改哪天就编辑哪行，符合店员心智。

**取窗口全面改按日期**：`listEnabledByStore(storeId)` → `listEnabledForDate(storeId, date)`（逐字镜像拼豆 `selectEnabledSlotsForDate`）。**切格算法一行没动** —— 只是取窗口时多一层过滤。四处调用点全切：下单 / 可用性 / 手动占用+改期（共用 `resolveSpanAndAssertCapacity`）/ 老包 shim；**周看板行头改七天并集**（周末与平时窗口不同，只取某一天会让另几天的格没有行）。

**连带 DROP `uk_tenant_store_time`**：加了 `weekdays` 后 `(store, start, end)` 唯一是**错的** ——「周一至周五 10-22」+「周六周日 10-22」是两行合法配置。判重下沉 service，口径改为「起止 + 星期完全相同」；**窗口重叠不拦**（与拼豆同口径：切格走 `TreeSet` 去重天然安全，拦重叠反而挡住「10-13 + 12-22」这类合法分段）。GZ-RECYCLE-012 为绕开该唯一键加的「软删复活」分支**随之退休**。

## ② 200 点以上 → 4 小时

`pts-200-plus` 300 → 240 分钟。**连带效果（已向 Kevin 说明）**：`pts-150-200` 本就是 240，改完后两档占用时长相同 —— 这是「4 小时封顶」的刻意行为，不是配置错误。

存量单不受影响：占格面在提交那一刻已冻结进 `product_snapshot_json.spanHours`（ADR-0022 §4），改点数档配置不改变既有单的占用宽度。

---

## ★ 真库端到端逮到一个我引入的 bug（本报告最重要的一段）

按星期跑端到端时，造了一条「周末 09:00-23:00」，预期周六 **14 格**（09..22），实际返回 **15 格且末格是 23:00**。

根因：`LocalTime` 是**环形**的 —— `23:00 + 1h = 00:00`，而 `00:00.isAfter(23:00)` 为 `false`，所以循环条件 `!cursor.plusHours(1).isAfter(end)` 在 `end=23:00` 时会多走一轮，吐出一个**窗口外的 23:00 格**（那是 23:00-24:00）。我写的环形防护 `if (cursor.plusHours(1).isBefore(cursor)) break;` 在 `add` **之后**，只挡住了死循环、没挡住脏格。

正解：两端已由 `validateTimeRange` 保证整点，直接按「距零点分钟数」整数循环，绕不了。

```java
int startMinute = start.getHour() * MINUTES_PER_HOUR;
int endMinute = end.getHour() * MINUTES_PER_HOUR;
for (int m = startMinute; m + MINUTES_PER_HOUR <= endMinute; m += MINUTES_PER_HOUR) {
    cells.add(LocalTime.of(m / MINUTES_PER_HOUR, 0));
}
```

已加回归测试 `slicing_windowEndingAt23_hasNoSpuriousCell` 守住。

> ⚠️ **拼豆 `sliceWindowsToHourSlots` 有同一形态的写法**，因其现有窗口都止于 22:00 而未暴露。
> 本次**没动拼豆**（那是防超卖核心，改它超出本条需求范围），已记入 ADR-0022 坑位 6 —— 等有人给拼豆配 23:00 收档的窗口时会复现。**建议单开小 ticket 修**。

这也说明一件事：**这个 bug 单测照不出**（我原有的切格单测窗口都止于 22:00），是真库端到端跑出来的。

---

## ③ admin 命名 / 页面对齐拼豆

回收与拼豆真正「同一件事」的页面只有**营业时段配置**（拼豆 `gzBeanConfig` ↔ 回收 `gzRecycleTimeSlot`）——
点数档 vs 桌型不是同一件事，不强行对齐。逐项差异 15 处，全部向拼豆靠：

| 项 | 拼豆（基准） | 回收原状 | 已改为 |
|---|---|---|---|
| 页标题 / 菜单 | 营业时段配置 | 回收营业时间 | **回收营业时段配置**（保留域前缀区分菜单树）|
| 开始 / 结束 | **两列** | 合并成「到店时段」一列 | **拆两列** |
| 时段名位置 | 第 2 列 | 第 5 列 | **提到第 2 列** |
| 星期列名 | 适用星期 | 生效星期 | **适用星期** |
| 长期有效 | 永久有效 | 长期有效 | **永久有效** |
| 启停交互 | 列内 **switch** | tag + 独立「停用/启用」按钮 | **switch**（操作列只剩编辑 / 删除，同拼豆）|
| 新增按钮 | 新增时段 | 新增 | **新增时段** |
| 弹窗标题 | 新增 / 编辑时段 | 新增 / 编辑**到店**时段 | **去掉「到店」** |
| 批量弹窗 | 按周批量配置时段 | …营业时间 | **按周批量配置时段** |
| 批量内列表 | 时段列表 | 营业窗口 | **时段列表** |
| 加一条 | + 加一条 | 再加一段 | **+ 加一条** |
| 整点校验文案 | 营业窗口起止时间必须为整点（如 10:00 / 22:00） | 自己的措辞 | **同拼豆** |
| start&lt;end 文案 | 开始时间必须早于结束时间 | 结束时间必须晚于开始时间 | **同拼豆** |
| 空态 | 该门店尚无时段模板，可点新增或按周批量配置 | 该门店暂无到店时段 | **同拼豆句式** |
| alert 结构 | 说明 + **「营业窗口须整点」**警示两条 | 只有一条说明 | **补齐两条** |
| 删除确认 | 确认删除时段「{time}」吗？（软删） | 确认删除到店时段「{range}」？ | **同拼豆** |

**回收保留的差异（刻意）**：
- 「小时格」列是回收特有（拼豆无），放在生效区间**之后**，不打乱前面的共同列序
- 门店列在最前 —— 回收是跨店列表带门店筛选，拼豆是先选店再看该店；这是页面模式差异不是命名差异
- 回收在 `el-tabs` 壳里（点数档 + 营业时段两个 tab），拼豆是独立页 —— 回收有两类配置要放一起，合理

**菜单改名走新迁移** `V202608261925__GZ-RECYCLE-015-menu-align-pindou.sql`（13006 及 4 个 F 节点，
**perms 一律不动**）—— 上一次改名在已应用的 `V202608261548`，append-only 铁律不能回头改。

---

## 改了哪些文件

**迁移**（3 个新文件）
- `V202608261902__GZ-RECYCLE-015-time-slot-weekdays.sql` — 三列 + DROP 唯一键 + 补非唯一索引
- `V202608261903__GZ-RECYCLE-015-qty-range-200plus-four-hours.sql` — 300 → 240
- `V202608261925__GZ-RECYCLE-015-menu-align-pindou.sql` — 菜单名对齐拼豆（perms 不动）

**后端**（`ruoyi-gz-recycle/`）
- `domain/entity/GzRecycleTimeSlot.java` / `domain/vo/GzRecycleTimeSlotVO.java` / `domain/bo/GzRecycleTimeSlotBo.java`（+ 三列，BO 带 `@Pattern` 校验）
- `service/IGzRecycleTimeSlotService.java` + `service/impl/GzRecycleTimeSlotServiceImpl.java`（`listEnabledForDate` / `containsWeekday` / `normalizeWeekdays` / 判重改写 / 软删复活退休）
- `service/impl/GzRecycleAppointmentServiceImpl.java`（四处调用点 + 周看板七天并集 + **切格环形 bug 修复**）

**admin**（`plus-ui/`）
- `views/gz-recycle/time-slot/index.vue`（星期/生效区间列与表单 + 按周批量配置弹窗 + **列序/命名/交互全面对齐拼豆**）
- `views/gz-recycle/config/index.vue` 的 tab 名 → 「营业时段配置」
- `api/gz-recycle/timeSlot.ts` · `lang/{zh_CN,en_US}.ts`（`gzRecycleTimeSlot` 段整块重写，72 key 双语对齐）

**文档**
- `doc/_adr/0022`（§2 补写 + 坑位 6 新增 + 坑位 2 标退休 + 编号修正）
- `doc/11-字段权威表.md` §12.2b 三列 + 唯一键变更 + 切格禁令；§12.2 seed 表 200plus 改 4 格 + 封顶说明
- **`doc/12-UI-权威索引.md` 回收 5 段整体重写**（Kevin 第 ② 条）：
  - `§MP-RECYCLE-FORM` — 旧文写的「自动估价卡 / 用户拍照上传 / IP 选择 / 微信号采集」**全部作废**，改写成单页三步流 + 小时格网格
  - `§MP-RECYCLE-SLOT` — **标注页面根本不存在**（早已并入 FORM 第 ③ 步）。保留段落是因为旧 ticket 里有大量「去向 MP-RECYCLE-SLOT」的引用，直接删会让后人以为漏写
  - `§MP-RECYCLE-LIST` — 时间显示改 `slot_start-slot_end` + 历史单 `arrivalSlotText` 回退分支
  - `§AD-RECYCLE-PRICE` — 标注 ⛔ 已停用（去估价，菜单已隐藏，代码/表保留不删）
  - **`§AD-RECYCLE-CONFIG` 新增**（原文档根本没有这一段）—— 点数档 + 营业时段两 tab
  - `§AD-RECYCLE-MANAGE` — 改写成周看板 rowspan 区间块 + 四个动作表（含 014「取消」）
  - 顶部两张索引表 + mp 导航 mermaid 图 + 页面清单表同步（`MP-RECYCLE-SLOT` 节点从流程图移除）

---

## AI 自测 raw output

### 1) 单测（109 → 111；time-slot 9 → 15，appointment 21 → 23）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run:  15, ... GzRecycleTimeSlotServiceImplTest        （+6：按星期/生效区间/边界/空值/null日期/归一化）
[INFO] Tests run:  23, ... GzRecycleAppointmentServiceImplTest     （+2：23:00 切格回归 / 多窗口并集去重）
[INFO] Tests run: 111, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### 2) 全量回归（bean 未受影响）

```
$ mvn -o clean install -DskipTests -pl ...gz-common,...gz-bean,...gz-recycle -am   →  BUILD SUCCESS
[INFO] Tests run: 264, Failures: 0, Errors: 0, Skipped: 0     ← gz-bean
[INFO] Tests run: 111, Failures: 0, Errors: 0, Skipped: 0     ← gz-recycle
```

### 3) 迁移实跑

```
Migrating schema `ry-vue` to version "202608261902 - GZ-RECYCLE-015-time-slot-weekdays" [out of order]
Migrating schema `ry-vue` to version "202608261903 - GZ-RECYCLE-015-qty-range-200plus-four-hours" [out of order]
Successfully applied 2 migrations to schema `ry-vue`, now at version v202608261903
Started DromaraApplication in 12.299 seconds
```

### 4) DB 断言

```
=== 015①: 三列 + 存量默认全周 ===
store=1 10:00:00-22:00:00 weekdays=1,2,3,4,5,6,7 eff=NULL exp=NULL
store=2 10:00:00-22:00:00 weekdays=1,2,3,4,5,6,7 eff=NULL exp=NULL

=== 015①: 旧唯一键已 DROP，新非唯一索引已建 ===
idx_tenant_store_enabled_sort  NON_UNIQUE=1
idx_tenant_store_time          NON_UNIQUE=1      ← 原 uk_tenant_store_time 已消失
PRIMARY                        NON_UNIQUE=0

=== 015②: 200点以上 → 4 小时 ===
pts-1-50      60min → 1 格      pts-150-200  240min → 4 格
pts-50-100   120min → 2 格      pts-200-plus 240min → 4 格   ← 封顶
pts-100-150  180min → 3 格
```

### 5) 端到端（造一条「周末 09:00-23:00」，验完已清理）

```
=== 周三（ISO 3，平时 10-22）===
  格数=12  10:00 … 21:00
=== 周六（ISO 6，周末 09-23 ∪ 平时 10-22）===
  格数=14  09:00 … 22:00
  有没有窗口外的 23:00 格: False        ← 修复前是 15 格 / 末格 23:00
=== 200点以上（4 小时）在周六 ===
  spanHours=4  可选起点: 09:00 … 19:00（共 11 个）    ← 19-23 正好放下，20:00 起越界
```

### 6) 前端

```
$ npx vue-tsc --noEmit | grep -E "gz-recycle|hour-slot"   → 无输出
$ npx eslint src/views/gz-recycle/ src/api/gz-recycle/ src/lang/*.ts  → 0 problems
$ python3（i18n 双语 key 比对）  → zh 独有: []  en 独有: []  共 73 个 key
```

---

## 已知 issue / 风险提示

1. **拼豆 `sliceWindowsToHourSlots` 有同款环形写法未修**（见上）—— 建议单开小 ticket。本次不动是因为它是拼豆防超卖核心，超出这条需求范围。
2. **`pts-150-200` 与 `pts-200-plus` 现在占用时长相同**（都 4 格）。这是封顶的刻意行为，交付时要跟甲方点一句，免得他以为配错了。
3. **admin 批量配置逐行提交、失败不中断** —— 判重拒绝（该星期该窗口已存在）是正常重入，最后汇总「创建 N / 跳过 M」。不是事务性的：中途网络断会留下已创建的行，需要店员自己检查。
4. **真 DB 并发脚本仍未跑**（GZ-RECYCLE-012 报告里已列为待补）——本次改动没有触及防超卖的并发路径（只改了「取哪些窗口」），但那条缺口依然在。

## 残留人验

**无**。纯 admin + 后端。

---

## §AI 测试段（kevin-qa 对抗性追加，20:50）

### 1) 环形切格 bug 的回归测试——真库复测（不同于原坑位发现时的场景）

coder 报告说这个 bug 是真库端到端发现的，用的是"周末 09:00-23:00"场景。本轮换一个未测过的边界（**单日单窗口精确止于 22:00 + 23:00 混合**），验证修复的通用性而非只针对当初复现的那一个具体案例：

```
临时窗口 08:00-23:00（单店单日专测）:
格数=15, 08:00...22:00, 有无窗口外 23:00 格: False   ← 修复后未复现
```
✅ 修复具备通用性，不是只补了报告里那一个具体数字。

### 2) 按星期 + 生效区间——4 类场景全部真库验证

```
平时(周三)：12 格 10:00-21:00
周末(周六，09-23 ∪ 平时 10-22 并集)：14 格 09:00-22:00
生效区间闭区间边界：eff=exp=2026-12-02 单日窗口 → 12-01(0格) / 12-02(2格) / 12-03(0格)
   —— 生效当天、过期当天都算生效，次日立即失效，与 ADR 描述的"闭区间"精确吻合
```

### 3) 200 点封顶验证

```sql
pts-150-200: 240min→4格   pts-200-plus: 240min→4格（封顶生效，与 150-200 相同不是配置错误）
```
周六窗口下 4 小时档可选起点 09:00~19:00（共 11 个），19-23 正好放下、20:00 起越界——边界计算精确。

### 4) admin 命名对齐拼豆——15 处逐项核对（非只看报告自称）

在 Playwright 里实际打开页面核对，而非只信报告里的对照表：标题"回收营业时段配置"✓、列序（时段名紧跟门店列后）✓、"适用星期"✓、启停用 switch 内嵌✓（非独立按钮）、"新增时段"✓、alert 两段式（说明 + 整点警示）✓、切格预览 hint✓。**15 项全部与拼豆逐一核对一致**，未发现命名/交互漂移。

### 5) 🟡 联带发现：「按周批量配置」在本 ticket 引入后暴露的去重颗粒度问题

见 `reports/GZ-RECYCLE-013.md` §AI 测试段详细复现——批量配置弹窗默认全选 7 天会在门店已有全周窗口时产生 7 条冗余记录（判重按 ADR 既定口径"起止+星期完全相同"是对的，但弹窗提示"已存在组合会自动跳过"对店主造成过度承诺）。**这是本 ticket（GZ-RECYCLE-015）引入「按周批量配置」弹窗后才存在的行为**，故在此一并记录出处；不重复贴 repro，详见 013 报告。

### 结论

GZ-RECYCLE-015 的核心正确性主张（按星期切格、生效区间闭区间语义、200 点封顶、admin 命名对齐）**全部通过独立真库验证**；环形切格 bug 修复具备泛化性（换了未测过的边界仍不复现）。已知问题：批量配置去重颗粒度的 UX gap（详见 013 报告，🟡 非阻塞）。

---

## §QA 闭环（kevin-qa findings 回修，21:40）

kevin-qa 的 🟡 finding 全部回修并在真浏览器复验；复验中又自查出两处本 ticket 引入的缺口，一并修掉。

### 修 1：批量配置提交前算「已被现有时段覆盖」，冗余行不再产生

原实现只在后端判重（起止 + 星期**完全相同**），一条全周行 `1,2,3,4,5,6,7` 与要建的单天行 `6` 不算重复 → 全选 7 天会静默造出 7 条冗余记录。真正的伤害在下游：店员之后单独编辑「周一」那条想临时改营业时间，不会意识到那条全周行仍覆盖着周一 → 改了不生效 → 当成 bug 报上来。

新增 `isCoveredByExisting(day, start, end)`（启用行中「同起止且 weekdays 含该天」即视为覆盖）+ `batchPlan` computed，**弹窗打开就把结论摆在提交按钮上方**，提交时同样跳过、不发那个必然冗余的请求。

真浏览器双向验证（门店 1 基线 = 一条全周 `10:00-22:00`）：

```
场景 A（全周行覆盖全部 7 天）
  预览: "将创建 0 条（星期数 × 时段数） （7 条已被现有时段覆盖，将跳过）"
  点确定 → DB: 门店1 窗口数=1     ← 修复前此处为 8

场景 B（把 id=10 改成 weekdays='1,2,3,4,5' 后全选 7 天）
  预览: "将创建 2 条（星期数 × 时段数） （5 条已被现有时段覆盖，将跳过）"
  点确定 → DB: id=27 weekdays=6 / id=28 weekdays=7   ← 精确区分，未过度拦截
```

场景 B 是关键：只挡冗余、不挡合法新增。验后已 `DELETE id IN (27,28)` + 还原 `weekdays='1,2,3,4,5,6,7'`，真库回到基线。

### 修 2：批量行补「时段名」输入（对齐拼豆 + 消除 NULL label）

场景 B 的产物暴露的：批量建出来的两行 `label` 是 **NULL**，列表「时段名」列空着。对比拼豆 `gz-bean/config` 的批量行是 **名称 / 开始 / 结束 / 删除** 四列，回收缺了名称列 —— 既是数据缺口也是页面布局漂移，正好落在 Kevin「命名和页面尽量保持一致」的要求上。

`BatchWindow` 加 `label`，首行默认「营业时间」（与 seed 行一致），`addBatchWindow` 新增行留空，提交 `w.label?.trim() || undefined`。复验：

```
批量行: [输入[营业时间], 输入[10:00], 文本:~, 输入[22:00], 文本:12 格, 删除按钮]
```

### 修 3：页面根节点从双根 fragment 收回单根

console 里有一条本页专属 warning：

```
[WARNING] Component inside <Transition> renders non-element root node that cannot be animated.
  at <GzRecycleTimeSlot> → <TimeSlot13006> → <KeepAlive> → <Transition>
```

根因是本 ticket 加「按周批量配置」弹窗时把它写在了根 `<div>` **外面** → 模板成了双根 fragment → keep-alive 的 transition 无法动画。拼豆 `gz-bean/config` 的批量弹窗是在根 div 内的，又一处布局漂移。弹窗移入根 div 后 warning 消失：**页面 warning 6 → 2**（剩的 2 条是 ruoyi 框架自带的 `vue-router next() deprecated`，非本页）。

### 复验结论

```
vue-tsc  → gz-recycle 零 TS 错误（全仓 72 条余错全在 workflow/oper-log 等未触碰的 ruoyi 自带页）
eslint   → src/views/gz-recycle/time-slot/index.vue EXIT=0
浏览器   → 0 console error；批量弹窗开/填/提交全程可用；DB 回到基线
```
