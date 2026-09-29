# GZ-BEAN-059 实施报告 — 桌型使用时长 · 上桌率

> ticket：`doc/daily/D27/tickets/GZ-BEAN-059.md` · 需求提炼：`doc/daily/D27/README.md`
> 日期：2026-09-28 · 真栈：dev（`sensenran-dev-mysql` 3307 + 后端 8080 + admin 8090）

## v5 修订（2026-09-29 甲方微信）

**甲方原话**：「这里面有个漏洞 就是他们**现金入座的没有写金额**」「但是**也需要参与统计**」。

**核查结论（先说结论，因为它决定改法）**：**线下现金入座的单一直计入统计**。
分子只看 `status IN ('used','completed')` + `pay_status='paid'`，**既不筛 `source` 也不读 `amount_cent`** ——
金额从来没进过这张表（甲方 2026-09-28 第一句就是「店员没填现金」，所以本报表定为零金额依赖）。
真库实证（门店1 2026-07）：已上桌 **45 格·小时 = 小程序 33 + 线下 12**，独立 SQL 与端点逐条一致。

**所以甲方真正要的是把口径显性化**：拆列 + 给出线下单数（现金常常没录金额，靠单数对账）。

**改动**：
- `UsageRow` 投影加 `source`；VO 加 `mpHours` / `offlineHours` / `offlineBookings`；
  只算已上桌单，`source='mp'` 归小程序，其余（`walk_in` 看板现金入座 + `admin` 后台代客）归线下。
- 页面在上桌时长右侧新增「**小程序时长**」「**线下时长**」两列（线下 > 0 时橙色）+ 末尾「**线下单数**」。
- 口径说明补第 ⑥ 条：线下入座**一直计入**，只是以前混在一起看不出占比；金额仍不参与本报表。
- `source` 列是 `NOT NULL DEFAULT 'mp'`（小程序下单不显式写），所以判别只剩一个方向：非 `mp` 即线下。

**顺手发现的（不在这条需求里，需甲方/Kevin 拍板）**：真库里 **8 张 walk_in 已上桌单有 3 张 `amount_cent=0`**
（另 1 张 pending 也是 0）→ 这些单在**营业额卡片的「现金」里计 ¥0**。这是 GZ-BEAN-046 刻意定的口径
（「店员没录金额 = 没收钱，不臆造收入」），**不是 bug**；但如果店员普遍不录，营业额会系统性偏低。
可以低成本加一个「未录金额的线下单数」提醒（只提示、不动金额口径）—— 要不要做由甲方定。

## v4 修订（2026-09-28，Kevin 第三轮）

**打回原话**：「我觉得将门店放在顶部，做成筛选结构上会更好一点，**不要全部**；桌型也做一个筛选（可以全部），这样更清晰一点」。

**改动**：
1. **门店筛选改必选、去掉「全部门店」**：全部门店时同一月份会被渲染成「4月(店A) → 4月(店B)」多段，正是上一轮被读成
   「两个 4 月」的根源。现在一屏只看一家店 → **表格里不再有门店列**，行 = 月份 × 桌型。默认落第一家门店。
2. **区块标题旁加「桌型」筛选**（默认「全部桌型」，选项取本区间实际出现的桌型，自定义桌型自动出现）；
   筛选只影响本区块，合计行随筛选重算；换区间后原选中桌型若消失 → 自动回到「全部桌型」（否则表格静默空掉）。
3. 合并范围从「月份 + 门店」收敛为**只有月份**（门店已经是筛选条件）。
4. **容量只从桌型创建日起算**（顺带修的相邻问题）：甲方提到的「六人桌」现在还不存在，他一新建，
   若不夹取就会在过去几个月各显示一行「上桌率 0%」—— 他会读成"这张桌子没人坐"，真相是它当时还没买回来。
   `create_time` 为空的老 seed 行视为一直存在（dev 现有 6 个在营桌型全是 NULL → **本次数字零变化**）。

**已知取舍（已写进 ticket AC14b）**：门店改必选会连带让本页**其它区块**（汇总卡 / 拆分 / 明细 / 趋势）也变成单店口径。
后端仍支持 `storeId` 为空（能力保留，只是页面不给入口），要恢复全店口径是纯前端改动。

**v2 修订（2026-09-28，Kevin 复审打回）

**打回原话**：「小程序里只能看到桌型，具体座位其实是店员自行分配的，所以我觉得甲方想要的，
应该是**每种桌型分别做了多少小时**，**每个桌型的座位平均做了多少小时**」。

**判定**：需求提炼漏了一半 —— 第一版给了总时长 + 一个**我自己加的**上桌率百分比，
而甲方要的是**能直接对照的绝对量**（"我的单人桌一个月平均才坐 6.3 小时"）。
上桌率是我为了"能横向比"引入的归一化视图，不是甲方要的东西。
`slotCapacity()` 口径没错（分母本来就是档位容量，不是物理座位），缺的是**它作为分母的那个商**。

**改动（v2）**：新增「桌数/座位数」列（平均值的分母，带 `桌`/`座` 单位）+「平均每桌/座时长」列
（= 上桌时长 ÷ 容量，主指标配色）；合计行这两列给「—」（桌与座不是同一单位，跨桌型不可加）；
口径说明改写为 ①总时长 ②平均每座时长 ③上桌率（百分比视图）④合计规则 ⑤与金额无关。
后端新增派生字段 `avgHoursPerUnit`（容量 0 → `null`，不许 `Infinity`）。

**为什么「平均每桌」=「平均每座」**：整桌桌型一次预订就是整桌座位都在用，
分子分母同乘一个 `capacity` 因子，商不变。**所以一个列就够，不需要拆两列。**

## 改动文件

**后端**（`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-bean/`）

| 文件 | 改动 |
|---|---|
| `domain/vo/GzBeanSeatUsageVO.java` | 新增。19 个字段（门店/月份/桌型/量纲容量/上桌/可售/营业/**平均每座时长**/两比率/单数分布），**无金额字段** |
| `mapper/GzBeanBookingMapper.java` | 新增 `selectUsageRowsInRange`（轻量投影 `UsageRow`：sess_date/store_id/seat_type_config_id/seat_type_snapshot/slot_start/slot_end/status/pay_status/is_day_pass/**source**） |
| `mapper/GzBeanSlotQuotaCloseMapper.java` | 新增 `selectCloseRowsInRange`（区间内当日关闭记录一次查完） |
| `service/IGzBeanRevenueService.java` | 新增 `selectSeatUsage(startStr, endStr, storeId, staffStoreId)` |
| `service/impl/GzBeanRevenueServiceImpl.java` | 新增实现：`SEATED_STATUSES`/`coveredSlots`/`rate`/`closeKey`/`monthOf`；分母走 `effectiveCap(config, recordedClose)`；装 `avgHoursPerUnit`；**返回前按 月份→门店 排序**；**容量从 `create_time` 起算** |
| `controller/GzBeanRevenueController.java` | 新增 `GET /system/gz/bean/revenue/seat-usage`，权限 `gz:bean:revenue:list`（**复用旧权限，无新菜单**） |
| `src/test/.../GzBeanRevenueServiceImplTest.java` | 新增 9 条用例（分子只认已上桌 / 包天按营业格 / 分母 0 → null / 合计重算 / 长期与当日覆盖 / 平均每座时长含容量 0 → null / 月份优先于门店 / 容量只从桌型创建日起算 / **时长按来源拆且两段相加 = 总时长**） |

**前端**（`code/main/plus-ui/`）

| 文件 | 改动 |
|---|---|
| `src/api/gz-bean/revenue.ts` | 新增 `GzBeanSeatUsageVO` 类型（含 `avgHoursPerUnit`）+ `getGzBeanSeatUsage({startDate,endDate,storeId})` |
| `src/views/gz-bean/revenue/index.vue` | 新增区块「桌型使用时长 · 上桌率」；v2 加「桌数/座位数」「平均每桌/座时长」两列 + `unitOf()` + `.usage-avg` 样式，合计行两列给「—」；v3 月份 rowspan 合并 + 数值列 `sortable="custom"`；**v4 门店筛选改必选（去掉「全部门店」/清空）、去掉门店列、区块内加桌型筛选**、`load()` 并行拉聚合/使用时长/明细 |
| `src/lang/zh_CN.ts` · `src/lang/en_US.ts` | `gzBeanRevenue` 下新增 key（含口径说明长句）；zh/en key 数 **1555 = 1555** |
| `e2e/gz-bean/seat-usage.spec.ts` | 新增 L2 守卫：页面行与端点返回**逐字比对**（36 行 × 含门店维度）+ 口径说明可见 + 无 `NaN`/`Infinity` + 分母 0 显示「—」 |

**文档**：`doc/daily/D27/{README.md,tickets/GZ-BEAN-059.md,reports/GZ-BEAN-059.md}` · `doc/12-UI-权威索引.md`（新增 §AD-BEAN-REVENUE 卡片）· `AGENTS.md` §7.4 · `.dsh/knowledge/pitfalls.md` §8.13 §8.14

## 口径实现（一句话）

**分子** = Σ 每张已上桌单覆盖的**营业小时格数**（格起点落在 `[slot_start, slot_end)` 内）；
**分母 A** = Σ 每格 `slotCapacity − 当日生效关闭数`（`effectiveCap`，与小程序可卖量同源）；
**分母 B** = Σ 每格 `slotCapacity`。单位统一为 桌·小时 / 座·小时。**零金额依赖**。

## 证据

### 1. 独立 SQL 对账（真库，非自证）

递归 CTE 从 `gz_bean_time_slot_template` 自造营业格 + `gz_bean_booking`（已上桌单）+ `gz_bean_slot_quota_close`
+ `mp_long_close_count`，独立算出 2026-04-01～2026-09-28 × 2 家门店 × 3 个桌型 = **36 行**的
「上桌时长 / 可售时长 / 营业时长」，与端点返回**逐字相等**（store 1：单人 July 19h、双人 July 24h、四人桌 July 2h；
store 2 全部 0h）。

两处手算交叉校验（覆盖 ADR-0024 §6 的**覆盖**语义）：

```
四人桌 (cap 8, 长期关闭 2) 2026-07：营业 2728 = 31 天 × 11 格 × 8
                              可售 2046 = 2728 − 2 × 11 × 31 (=682)   ✅
四人桌 2026-09（区间止 09-28，28 天）：营业 2464 = 28 × 11 × 8
   可售 1859 = 27 天 × 11 × (8−2)  +  09-27 的 11 × (8−1)
             = 1782 + 77 = 1859        ← 当日 1 覆盖长期 2（不是 8−2−1=5）✅
双人 2026-07：营业 1364、可售 1358 → 差 6 = 07-07 的 6 条当日关闭记录 × 1   ✅
```

> 对账过程中出现过一次「双人 7 月 SQL 23 vs 报表 24」。查实：**我的 SQL 参照写错了** —— 用 `HOUR()` 截断，
> 而实现口径是「格起点落在单的时段内」。触发差异的是 07-07 那张 `09:16→11:10` 的延时单（覆盖 10:00、11:00 两格）。
> 记录在案：**自造对照只有口径逐字对齐才有判定力**（`pitfalls.md` §8.13）。

### 1b. 平均值的独立对账

同一条 CTE 直接算 `used_hours / cap`，独立得到 `5.0 / 0.3 / 6.3 / 6.0 / 0.3`，
与页面显示（`toFixed(1)`）**逐条相等**（`0.25 → 0.3` 两边同口径）：

```
2026-06 单人  19/3=5.0000→5.0   2026-07 单人 19/3=6.3333→6.3   2026-07 双人 24/4=6.0000→6.0
2026-06 双人   1/4=0.2500→0.3   2026-07 四人桌 2/8=0.2500→0.3
```

### 2. 单测（L0）

`mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-bean -am` →
`GzBeanRevenueServiceImplTest` **21/21** 绿（原 12 + 新 9），模块合计 **329/329**（skipped=0）。
其中「时长按来源拆」用 3 张单（mp 1h / walk_in 2h / admin 1h）断言 `4 = 1 + 3` 且**两段相加恒等于总时长**。
其中「容量只从桌型创建日起算」用 2026-09-15 建的桌型查 8~9 月：8 月整行不出现、9 月 `openHours = 16 天 × 4 格 × 容量 4 = 256`。
**变异验证**：把分子从「营业格数」改成「钟表时长」→ 2 条用例变红（说明测的是真行为，不是空转）。

### 3. 真栈 E2E（L2）

`pnpm exec playwright test e2e/gz-bean/seat-usage.spec.ts` → **1 passed**：
页面实际渲染行数与端点返回行数相等（36），逐行按 `月份 + 门店 + 桌型` 定位后端行并**逐字**比对
`上桌时长` / `可售时长` / **`桌数/座位数`（数字+单位）** / **`平均每桌/座时长`（= 后端值保留 1 位，且 = 上桌时长 ÷ 容量）**；
断言**合计行的容量与平均值都是「—」**（混量纲）；断言区块含口径说明「上桌时长 ÷ 可售时长」「平均每桌/座时长」「座·小时」「与金额无关」；
断言页面文本不含 `NaN` / `Infinity`。

### 4. 前端门

`eslint`（仅改动文件）0 error · `vue-tsc --noEmit` **72**（与改动前基线一致，无新增）· `pnpm build:prod` exit 0 ·
i18n key 数 zh 1548 = en 1548。

## 过程中的两个真缺陷（都已在本次内修掉）

1. **i18n key 插错命名空间**：新增的 17 个 `gzBeanRevenue.*` key 被插进了 `gzUser` 块
   （文本锚点 `detail: '详情',` 在文件里撞名），页面直接渲染出 `gzBeanRevenue.usageTitle` 这种**原始 key 字面量**；
   而 `zh/en` key 数仍然相等（两边错在同一个地方）→ 只有真跑页面才发现。
   → 已搬回 `gzBeanRevenue`，并写进 `pitfalls.md` §8.13。
2. **E2E 匹配键少了门店维度**：dev 有 2 家在营门店 × 3 个同名桌型（单人/双人/四人桌），
   用「月份 + 桌型」定位后端行会串到另一家店（表现为 `Expected 990 / Received 1980`）。
   → 匹配键改为 `月份 + 门店 + 桌型`；这也顺带证明了报表的**门店维度**真的生效。写进 `pitfalls.md` §8.14。

## v2 过程中修掉的一个真缺陷

**`el-table-column` 没写 `prop` → 自定义 `summary-method` 按 `col.property` 分派的分支静默落空**：
容量列只写了 `:label`，合计行里 `col.property === 'capacityPerSlot'` 永不命中 → 落到兜底 `''`，
**渲染成空串而不是「—」**（页面看着像"漏了一格"，不报错、不报红）。补齐 `prop` 即可。
E2E 现在钉死"合计行这两列必须是「—」"，也就把"漏 prop"挡在门外（`pitfalls.md` §8.16）。

## 遗留

- 本需求来自**甲方微信**，不在 `doc/test/kevin-test.xlsx` 里 → 未写验收账本（`ledger.json` 仍 3 条，全部 `已修复`）。
  如需它进账本，由 Kevin 在 xlsx 补一行后 `accept.py sync`。
- 报表的「六人桌」：dev/线上当前桌型档是 单人 / 双人 / 四人桌，甲方口中的「六人桌」= 他店里将要有的档位；
  报表按 `gz_bean_seat_type_config` 逐档输出，新增档位**无需改代码**即自动出现。
