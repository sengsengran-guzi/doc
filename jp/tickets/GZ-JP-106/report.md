# GZ-JP-106 完工报告 — 履约状态机 + 批量推进 / 批量发货 API

> **结论：accept 三条全 PASS。** gz-jp 单测 153 全绿（本卡新增 31）。
> **真库端到端已实跑**（独立实例 `:8081`，不碰在跑的 `:8080`）：22 个业务场景 + **3 轮真并发压测**（6 并发推进 / 6 并发发货 / 3 推进×3 发货混合，窗口重叠、一半降序传 id）—— **零死锁、零脏数据、每行恰好写一次**。
> **无迁移、无菜单、无字典**（14030 段留给 108）。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（`staging`，HEAD `6618054d6`） | ✅ | 开工前 `git status --porcelain` 空 |
| 上游 GZ-JP-105 已 merge | ✅ | `6618054d6 D4/GZ-JP-105: 订单+订单行建表 + 下单事务 + 支付回调` |
| `gz_jp_order_item` 有数据可推 | ✅ | 10 行（7 行属已支付单 / **3 行属未支付单**，正好用来验最重要的那道闸） |
| `gz_express_carrier` 字典已存在 | ✅ | `dict_id=9130`，9 项（sf/yto/zto/yunda/jd/ems/debang/jitu/other），seed 于 `V202606190000__GZ-USER-103`。**本卡未新建、未改** |
| `gz_jp_fulfill_status` 字典已 seed | ✅ | `dict_id=9284` 7 项（105 已 seed，本卡**未重 seed**，避免撞 dict_code 主键） |
| Flyway append-only | ✅ | **本卡零迁移**；`git status -- db/migration/` 空 |
| menu 段位（本卡不占） | ✅ | 14030 段归 108（其 accept 断言 `COUNT(*) BETWEEN 14030 AND 14039 >= 1`），本卡若 seed 会让 108 的父级校验失败 |
| 编译基线 | ✅ | 动手前 `mvn -o compile -pl ruoyi-gz-jp` → BUILD SUCCESS |
| 权威蓝图已读 | ✅ | `flows.yaml` F-JP-03.step1~4 + F-JP-04.step1；`field-ssot.yaml` `gz_jp_order_item.{fulfill_status,carrier_code,tracking_no,shipped_at}`；`ui-index.yaml` UI:admin.fulfill_board（含 batch_advance / batch_ship / mark_failed 三条 step） |
| ADR | 本域无 ADR；沿用 105 的守卫 UPDATE 范式与 `GzJpProductServiceImpl.changeStatus` 的批量口径 |

**蓝图关键约束摘录**：
- `fulfill_status`「★ 允许跳过中间态（现货无 await_seller_ship）」+「默认 purchasing」
- `carrier_code`「复用现有 `gz_express_carrier` 字典，**置 delivered 时必填**」
- `tracking_no`「员工手工填。★ **本列即包裹标识**——同单号的行属同一包裹，**不另建包裹表**」
- `F-JP-03.step2`「状态链…**允许跳过中间态**…**不可回退（一期不做回退）**」
- `F-JP-03.step3`「勾选已到齐的一批 → 填**一个**顺丰单号 → 一起置为发货完毕」
- `F-JP-04.step1`「勾选没买到的商品行 → 标记购买失败（可批量）→ 分支终态，不再往下走」
- `UI:admin.fulfill_board`「主视图**按客人聚合**、可跨订单」+「批量接口做分页与**单次条数上限**（一个客人可能 30+ 行）」

## 实现摘要（1 改 + 15 新增，+2326 行）

```
 M mapper/GzJpOrderItemMapper.java                    +156   ← 加 5 个方法（锁行 / 守卫推进 / 守卫发货 / 单号归属 / 看板分页）
?? service/internal/GzJpFulfillStateMachine.java      136    ← ★ 状态链判定唯一真源（纯静态）
?? service/{IGzJpFulfillService, impl/GzJpFulfillServiceImpl}.java   69 + 564
?? controller/GzJpFulfillController.java              112
?? domain/enums/GzJpFulfillRejectReason.java          51
?? domain/bo/{GzJpFulfillAdvanceBo, GzJpFulfillShipBo, GzJpFulfillQueryBo}.java   42+49+54
?? domain/vo/{GzJpFulfillBatchResultVO, GzJpFulfillRejectVO, GzJpFulfillBoardItemVO}.java  57+38+100
?? domain/dto/GzJpFulfillBoardRow.java                43
?? test/.../{GzJpFulfillFixture, GzJpFulfillStateMachineTest, GzJpShipRequireTrackingTest}.java  197+418+296
```

**零改动区**：`GzJpOrderServiceImpl` / `JpPayCallbackHandler` / `GzJpFulfillStatus` 枚举 / 任何迁移 / 任何 GZ-PAY 代码 / 拼豆·回收·预购·扭蛋一行未动。`GzJpFulfillStatus` 只被**读**（`getStep()` / `isValid()` / `labelOf()`）—— 按 105 交代「别在枚举里长第二份真源」。

### 状态链规则（全部收在 `GzJpFulfillStateMachine`，只有三条）

```
purchasing 购买中
  ├─ purchase_failed 购买失败        ← 分支终态（退款归 107）
  └─ await_seller_ship 等待官方发货
       → jp_shipped → customs → cn_sorting → delivered（终态，必带运单号）
```

1. **允许跳过中间态** —— 只要求位次严格变大（`to.step > from.step`），不要求逐级
2. **不可回退** —— 位次相同或变小即拒（`BACKWARD`）
3. **不可跨越终态** —— `delivered` / `purchase_failed` 之后任何批量操作都不碰（`TERMINAL`）

**两个刻意决定**（评审请连同理由看）：

- **`purchase_failed` 可从任意非终态进入**，不限于 `purchasing`。枚举里它与 `purchasing` 同为 step 1 —— 它是**分支**不是前进，位次规则对它不适用。业务上「买到了但卖家取消 / 日方缺货 / 清关退运」都可能在链条中段才暴露，而一期**没有回退功能**；若只许从「购买中」标失败，一件卡在「清关中」的货**永远退不了款**。误标风险由 admin 侧二次确认承担（UI:admin.fulfill_board.mark_failed 已写明「会触发真实退款」）。
- **`delivered` 不能由 `/advance` 达成**，必须走 `/ship`。`checkAdvance(*, delivered)` 直接返回 `SHIP_REQUIRED` —— 这就是 AC「置 delivered 未填单号被拒」的落点，且**拦在读库之前**，不存在「先置 delivered 再补单号」的窗口。

### 三道闸都写进 SQL，不靠调用方自觉

```sql
UPDATE gz_jp_order_item SET fulfill_status=#{target}, version = version + 1, ...
WHERE del_flag='0' AND fulfill_status=#{expectFrom} AND id IN (...)
  AND EXISTS (SELECT 1 FROM gz_jp_order o WHERE o.id = gz_jp_order_item.order_id
              AND o.del_flag='0' AND o.tenant_id = gz_jp_order_item.tenant_id
              AND o.business_status IN ('paid','partial_refunded','refunded'))
```

- `fulfill_status=#{expectFrom}` 状态守卫（affected 与预期不符 → **整批回滚**，不糊近似计数）
- `EXISTS(...)` ★ **只碰付过款的订单的行** —— 105 交代的头号坑，看板查询同样内置且不可关闭
- `o.tenant_id = gz_jp_order_item.tenant_id` —— 多租户拦截器只给**被更新表**补 tenant 条件、**不下探子查询**，手写补齐
- `version = version + 1` **手写**（`@Version` 自增只对 MP 生成的 `updateById` 生效；全程**没有 insert 后 updateById 补字段**）

### 批量执行骨架

① **按 id 去重 + 升序** → `SELECT ... FOR UPDATE` 锁行（★ 防死锁）② 批量取订单付款态 → ③ 逐行判定（发货另加「同一客人」闸）→ ④ **按当前状态分组**、每组一条带守卫的 UPDATE（组内再按 100 切片）→ ⑤ 汇总

**部分成功语义**：能推的推掉，推不动的**逐行给原因**（`rejects[].reasonCode/reason`）。唯一例外：`advanced==0 && skipped==0` → 抛 **4108**。「全部已是目标态」算**幂等成功**（200 + `skipped=N`），不报错不写库。

### 发货专属约束

- `carrierCode` + `trackingNo` **缺一即 4109**；运单号 trim 后按 `^[A-Za-z0-9][A-Za-z0-9\-_]{3,63}$` 卡格式（只挡明显手滑）
- 快递编码对 `gz_express_carrier` 做**成员校验**（字典整体取不到时**只告警不拦**，字典故障不该让发货停摆）
- **一个运单号 = 一个包裹 = 一个收件人**：本批必须同客人（4110），且该单号不能已挂在别人名下（4110）。同客人分两次往同一包裹补行 → 允许
- 状态 + 单号 + 时间**一次 UPDATE 写齐**（accept[2] 正是断言「delivered 无单号」0 条）
- **不建包裹表**（蓝图明令）

### 超出 What 的最小补充：`GET /system/gz/jp/fulfill/list`

GZ-JP-108 的 `touches` 只有 `plus-ui/**` + `db/migration/**`，**没有 `ruoyi-gz-jp/**`** —— 履约看板的查询端点**无人认领**，不补则 108 的 accept（`fulfill-board.spec.ts` E2E）直接阻塞。同 105 补 mp 读端点的处理方式：**纯读、无新表、无新菜单**。恒按客人聚簇排序（`user_id → order_id → item id`）。

## AI 自测（Tier 1A）

### 1. accept[1] 非法状态转移被拒 + 合法链路全程可达 ✅

```
$ cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-jp -am -Dsurefire.failIfNoSpecifiedTests=false -Dtest=GzJpFulfillStateMachineTest
[AC1] 倒退被拒：customs→purchasing / cn_sorting→jp_shipped / customs→await_seller_ship 全部拒绝
[AC2] 跳过中间态允许：purchasing→jp_shipped / purchasing→customs / purchasing→delivered(发货)
[AC3] 终态锁死：delivered / purchase_failed 对任何目标（含再次发货）均返回 TERMINAL
[分支] purchase_failed 可从 5 个非终态进入，进入后不可再出
[发货闸] 任何来源推进到 delivered 一律 SHIP_REQUIRED
[矩阵] 7×7=49 组合：允许 19 / 拒绝 30                     ← 每一格都被钉死，新增状态时立刻炸
[链路] purchasing → await_seller_ship → jp_shipped → customs → cn_sorting → delivered（版本号 6，每步 +1）
[跳过] purchasing ×2 一次推到 jp_shipped，advanced=2
[未支付] 混入未支付订单行 21：advanced=1 rejected=1 reason=订单未支付，不可推进；该行状态仍为 purchasing
[4108] 没有可推进的商品行：订单未支付，不可推进（共 2 行被拒）
[终态] 推进与发货两条路径下，purchase_failed / delivered 行均被拒且数据零变化
[幂等] 重复推进同一批：advanced=0 skipped=2，不报错不写库
[防死锁] 入参 [13,11,12,11,null,13] → 实际加锁顺序 [11, 12, 13]
[上限] 201 行被拒：单次最多操作 200 行，请分批处理
[分组] 三种起始状态（purchasing/await_seller_ship/jp_shipped）一次推到 cn_sorting
Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
ACCEPT1_EXIT=0
```
单测的 mapper 是**内存版且逐字照搬了 SQL 的两道 WHERE 守卫**（`fulfill_status=expectFrom` + 订单付过款）—— 用 `when(...).thenReturn(1)` 把 mapper 桩掉等于把要测的东西删掉了。

### 2. accept[2] 批量发货后同批行共用一个单号且均为 delivered ✅

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
    SELECT COUNT(DISTINCT fulfill_status) FROM gz_jp_order_item
    WHERE tracking_no IS NOT NULL AND tracking_no<>'' AND del_flag='0'" | grep -qx 1 &&
  docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
    SELECT COUNT(*) FROM gz_jp_order_item
    WHERE fulfill_status='delivered' AND (tracking_no IS NULL OR tracking_no='' OR carrier_code IS NULL)
    AND del_flag='0'" | grep -qx 0
ACCEPT2_EXIT=0

--- 明细佐证 ---
tracking_no     carrier_code  items  rows_  statuses
SF7654321000    sf            2,3    2      delivered
```

### 3. accept[3] 置 delivered 未填单号被拒 ✅

```
$ mvn -q test ... -Dtest=GzJpShipRequireTrackingTest
[AC 未填单号] 批量推进→delivered 被 4109 拒：「发货完毕」必须通过批量发货填写快递公司与运单号
[AC 未填单号] 缺 carrierCode / carrierCode 空串 / carrierCode 全空格 → 4109 发货必须同时填写快递公司与运单号
[AC 未填单号] 缺 trackingNo / trackingNo 空串 / trackingNo 全空格（trim 后为空） → 4109
[AC 未填单号] 过短 / 含空格 / 含中文 → 4109 运单号格式不正确（4~64 位字母、数字或短横线）
[快递闸] 未知的快递公司编码：shunfeng
[降级] 字典空 → 跳过编码校验，发货成功，carrierLabel=null
[发货] 3 行（跨 2 张订单、3 种起始状态）一次置 delivered，共用单号 SF7654321000
[accept2 镜像] delivered 缺单号行数=0；带单号行的状态种类数=1（全 delivered）
[跨客人] 同一个运单号只能属于一个客人，本次勾选跨了 2 个客人，请分开发货
[单号归属] 运单号 SF4444444444 已用于其他客人的包裹，请核对后重填
[同包裹补行] 同客人两次发货共用单号 SF5555555555 → 2 行都 delivered
[不可重发] 没有可发货的商品行：当前已是终态，不可再变更（共 1 行被拒）
[未支付] 没有可发货的商品行：订单未支付，不可推进（共 1 行被拒）
Tests run: 13, Failures: 0, Errors: 0, Skipped: 0
ACCEPT3_EXIT=0
```
每条「被拒」都额外 `verify(never()).shipGuarded(...)` + 断言行数据零变化 —— 证明是**拦在写库之前**，不是写了再回滚。

### 4. ★ 真库端到端（独立实例 `:8081`，admin 超管 token）

**先验最重要的那道闸**——看板只出付过款的行：
```
DB 全量 10 行：id 1,2,3,24,25,26,27 属 paid 单；id 28,29,30 属 created 单（fulfill_status 同样是 purchasing）
GET /system/gz/jp/fulfill/list → total=7，item ids = [1, 2, 3, 24, 25, 26, 27]
  ★ 28/29/30 一条没出 —— 未支付订单的行不会被店员当成可采购对象
```

批量推进 10 个场景：
```
A) 推进到 delivered            → 4109 「发货完毕」必须通过批量发货填写快递公司与运单号
B) 混入未支付行 28             → 200 requested=2 advanced=1 rejected=1
                                   x item=28 cur=购买中 why=ORDER_UNPAID / 订单未支付，不可推进
C) 倒退 jp_shipped→await       → 4108 没有可推进的商品行：不可回退到更早的状态（共 1 行被拒）
D) 跳过中间态 jp_shipped→cn_sorting → 200 advanced=1
E) 重复推进同一目标            → 200 requested=1 advanced=0 skipped=1        （幂等，且入参 ["1","1"] 被去重）
F) 只勾未支付行 28,29          → 4108 …：订单未支付，不可推进（共 2 行被拒）
G) 标记购买失败 24             → 200 advanced=1                              （分支，从 purchasing 进）
H) 已 purchase_failed 再推进   → 4108 …：当前已是终态，不可再变更
I) 目标值非法 "shipped"        → 非法的目标状态：shipped                      （不读库不写库）
J) 目标=purchasing 起点        → 4108 …：非法的目标状态
```
批量发货 10 个场景：
```
K) 缺运单号 / L) 缺快递公司 / M) 运单号全空格 → 4109 发货必须同时填写快递公司与运单号
M'') 运单号含中文              → 4109 运单号格式不正确（4~64 位字母、数字或短横线）
N) 未知快递编码 shunfeng       → 未知的快递公司编码：shunfeng
O) 正常发货 2+3                → 200 advanced=2 carrier=sf(顺丰速运) tracking=SF7654321000
P) 已 delivered 换单号再发     → 4108 …：当前已是终态（原单号 SF7654321000 一字未改）
Q) 已 delivered 再推进         → 4108 …：当前已是终态
R) 未支付行发货 30             → 4108 …：订单未支付
S) 跨客人一起发（user14+user13）→ 4110 同一个运单号只能属于一个客人，本次勾选跨了 2 个客人，请分开发货
T) 给 user13 发货              → 200 carrier=jd(京东快递) tracking=JD9999900001
U) 拿 user13 已占的单号发 user14 → 4110 运单号 JD9999900001 已用于其他客人的包裹，请核对后重填
V) 同客人往同一包裹补行        → 200 advanced=1（两行共用 JD9999900001）
```
落库核对（`update_by` = 操作人 sys_user.id，自定义 SQL 手动填）：
```
id  ord     fulfill_status   carrier  tracking_no     shipped_at            version  update_by
1   paid    cn_sorting       NULL     NULL            NULL                  3        1
2   paid    delivered        sf       SF7654321000    2026-08-07 10:05:23   2        1
3   paid    delivered        sf       SF7654321000    2026-08-07 10:05:23   2        1
24  paid    purchase_failed  NULL     NULL            NULL                  2        1
25/26/27 paid purchasing     NULL     NULL            NULL                  1        14   ← 未被本卡碰过
28/29/30 created purchasing  NULL     NULL            NULL                  0        14   ← ★ 未支付，全程零变化
```
看板筛选（供 108 直接照抄）：
```
按状态多选 delivered+purchase_failed → total=30      按运单号 SF7654321000 → total=2（正好一个包裹）
按订单号 JPO-20260807-000003 → total=2               按客人关键词「别人」→ total=2（命中 user 13）
按 userId=13 → total=2                               按场 eventId=1 → total=37
下单时间段 08-07~08-07 → total=39 / 08-01~08-02 → 0   关键词无匹配 → total=0（★ 不退化成全量）
非法状态筛选值 bogus → 拒：非法的履约状态筛选值：bogus
排序：user_id 13 的行排在 14 前面 —— 按客人聚簇，前端断组即可
```

### 5. ★★ 真并发压测（3 轮，窗口重叠、一半降序传 id）

> 105 的教训：**涉及并发的实现单测全绿不算数**（本项目已两次靠真并发才逮到真缺陷）。临时造 30 行同订单商品行做靶子，压完硬删。

**轮 1 — 6 并发 `/advance` → jp_shipped**（窗口 [40,49] [44,53] [48,57] [52,61] [56,65] [60,69]，交集 60%）
```
  resp_0: code=200 advanced=8  skipped=2   resp_3: code=200 advanced=0  skipped=10
  resp_1: code=200 advanced=0  skipped=10  resp_4: code=200 advanced=10 skipped=0
  resp_2: code=200 advanced=8  skipped=2   resp_5: code=200 advanced=4  skipped=6
  合计 advanced=30 skipped=30 rejected=0  响应码=[200,200,200,200,200,200]

压测后：jp_shipped 30 行，version 全部 = 2（压测前 =1）
  ★ 每行恰好被写 1 次：没有重复写、没有丢更新、没有状态错乱
死锁扫描（应用日志 grep -ic deadlock）= 0
```

**轮 2 — 6 并发 `/ship`（同一运单号，窗口同上）**
```
  5 个 200（advanced 4/8/4/4/10）+ 1 个 4108（它那 10 行已全部被别人发完 → 终态）
  合计 advanced=30 rejected=20
落库：delivered / sf / SF-CONC-0001 / 30 行 / version 全部 = 3 / distinct shipped_at = 1
死锁 = 0
```

**轮 3 — 混合并发（3 个 `/advance`→customs 与 3 个 `/ship` 同时打同一批重叠行）**
```
  mix_adv_0: 200 advanced=5  skipped=2 rejected=8      mix_ship_0: 200 advanced=5  rejected=10
  mix_adv_1: 200 advanced=15 skipped=0 rejected=0      mix_ship_1: 200 advanced=5  rejected=10
  mix_adv_2: 4108（15 行全被别人发完）                  mix_ship_2: 200 advanced=15 rejected=0

不变量核对：
  ★坏数据(delivered 缺单号)      = 0
  ★坏数据(非 delivered 却带单号) = 0
  最终分布：customs 2 行(v=2) / delivered+SF-MIX-0000 5 行(v=3) / delivered+SF-MIX-0001 5 行(v=3)
            / delivered+SF-MIX-0002 15 行(v=2~3) / purchasing 3 行(v=1)
死锁 = 0；全程无 500
```
**为什么不死锁**：所有入口在锁行前都把 id **去重 + 升序**（`normalizeIds`），六个请求申请行锁的顺序完全一致 —— 最坏只是排队。压测刻意让一半请求**降序**传 id，验的就是「排序发生在服务端、不依赖调用方守规矩」。

压测数据已硬删（`DELETE` 不是软删 —— 软删行仍会被 accept[2] 的全表扫描看到）：`残留临时订单 0 / 残留临时行 0`。

### 6. 回归

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp
13 GzJpShipRequireTrackingTest · 21 GzJpOrderSubmitTest · 20 GzJpProductServiceTest · 17 GzJpEventStatusTest
 · 38 GzJpCartServiceTest · 18 GzJpFulfillStateMachineTest · 20 GzJpProductMpQueryTest · 6 GzJpPayCallbackTest
→ Tests run: 153, Failures: 0, Errors: 0, Skipped: 0 — BUILD SUCCESS
（gz-common / gz-user 未改动，无需回归）
```

## 风险提示 / 已知 issue

1. **`purchase_failed` 可从任意非终态进入是判断，不是蓝图明写的**。蓝图的树画在 `purchasing` 下面。放宽的理由见「两个刻意决定」（一期无回退 ⇒ 收紧会让中段发现买不到的货永远退不了款）。**若甲方口径是「只有购买中能标失败」**，改一行即可（`GzJpFulfillStateMachine.check` 里给 `PURCHASE_FAILED` 目标加 `from == PURCHASING` 判断），单测 `purchaseFailedIsBranch` 会立刻红。**建议 107 实施前跟 Kevin 确认一句**。
2. **一期不做回退 = 误操作不可逆**。店员把 30 行错推到「清关中」没有撤销按钮（AC 明令不做）。108 的批量操作条建议**推进前二次确认并显示「将影响 N 行、目标 X，不可撤销」**。
3. **已 `delivered` 不可改单号**（终态锁死）。真实场景「单号填错了」目前只能改库。若甲方提出这个需求，是一个**独立小 ticket**（带审计的「更正运单号」端点），不要偷偷放宽终态规则。
4. **同客人不同收货地址仍可被塞进一个包裹**：只拦了「跨客人」，没拦「同客人两张订单地址不同」。**108 的发货弹窗建议把地址显示出来**让店员自己看；若要后端硬拦，是 108 阶段的小改（比对 `address_snapshot_json`）。
5. **`@RepeatSubmit` 会挡住「完全相同 payload」的连续两次请求**（返回 `500 Repeat submit is not allowed`）。真库实测确认。对 108 是好事（防双击），但**写 E2E 时别用两次一模一样的 body 断言幂等** —— 会拿到 500 而不是 200+skipped。
6. **`/auth/login` 的 `clientId` 是 body 字段不是 header**（`LoginBody.@NotBlank`）。⚠️ 108/109 两张卡的 accept 第 2/3 条原文把它写成了 header，**主线程已直接修正这两张卡的 prompt.md**（同 del_flag 那次的处置方式），并用真登录验证过。
7. **本卡无迁移、无菜单、无字典**：`gz:jp:fulfill:{list,advance,ship}` 三个权限串由 **108 在 14030 段 seed**。在那之前只有超管（admin）能调这三个端点，普通角色 403。**这是预期，不是漏做** —— 本卡若 seed，108 的菜单 accept 会因父级不存在而失败。
8. **不写 cron**（SnailJob prod 未部署）：本域没有任何「自动推进」。全部靠 admin 手动批量。
9. **dev 库当前状态**（留给 108/109/205 当 fixture，比全 purchasing 好用）：`item 1=cn_sorting` / `2,3=delivered+SF7654321000（同一包裹）` / `24=purchase_failed` / `25,26,27=purchasing` / `28,29,30=未支付单的行（不该出现在看板）`。
10. **待 Kevin 残留人验：N/A** —— 纯后端，无 mp / admin 页面，不碰真机原生能力。

## 对下游 ticket 的提示

### 给 GZ-JP-107（行级退款）

- **要的「标记购买失败」已经能用了**：`POST /system/gz/jp/fulfill/advance {"itemIds":[...],"targetStatus":"purchase_failed"}`。**不要再写第二套状态判定** —— 调 `IGzJpFulfillService.advance(...)` 或直接用 `GzJpFulfillStateMachine.checkAdvance`，然后在同一事务里接退款链路。
- 需要「标失败 + 发起退款」原子化的话，建议在 107 里包一层 `markPurchaseFailedAndRefund`，内部先调 `advance` 拿到 `advanced/rejects`，**只对真的被推成 `purchase_failed` 的行发起退款**（`rejects` 里的行一分钱都不能退）。
- 订单 rollup（`partial_refunded` / `refunded`）的守卫 UPDATE 归你加。照 `GzJpOrderMapper.markPaid` 的 `WHERE business_status=...` 写法，**记得 `version = version + 1`**。
- ⚠️ SQL 里「付过款」= `business_status IN ('paid','partial_refunded','refunded')`（`GzJpOrderStatus.isPaidLike`）。订单 rollup 成 `partial_refunded` / `refunded` 后，**剩余未失败行仍能正常推进发货** —— 这是有意的，别改窄。
- 错误码下一个空号 **4111**（本卡占 4108/4109/4110）。

### 给 GZ-JP-108（admin 履约看板）

**三个端点全在 `/system/gz/jp/fulfill`，权限 `gz:jp:fulfill:{list,advance,ship}`（★ 菜单 + 按钮 seed 归你，14030 段仍全空）**

```jsonc
GET /system/gz/jp/fulfill/list?pageNum=1&pageSize=20
    &userId=13 | &keyword=小王                       // keyword 匹配昵称/手机号/用户编号；无匹配返回 total=0（不会退化成全量）
    &fulfillStatus=purchasing&fulfillStatus=customs   // 多选，重复参数名；非法值直接报错不静默丢弃
    &eventId=1 &orderNo=JPO-... &trackingNo=SF...     // 精确
    &beginDate=2026-08-01&endDate=2026-08-07          // 按【下单时间】，含首尾整天
// ★ 读 res.rows（TableDataInfo）不是 res.data —— D16 逮到过 6 处这类 bug
{ "rows":[{
    "id","orderId","orderNo","businessStatus",             // ★ id 就是批量接口要传的 itemIds 元素（string）
    "userId","userNickname","userMobile","userNo",          // ★ 按 userId 断组；后端已按 user_id→order_id→id 聚簇排序
    "productId","productNo","name","eventName",             // 商品信息全部来自下单快照（商品改名/删除不影响）
    "qty","unitPriceCent","amountCent",
    "fulfillStatus","fulfillStatusLabel",                   // 中文后端已给，别在前端再维护一份映射
    "terminal",                                             // ★ true = delivered/purchase_failed → 该行 checkbox 直接禁掉
    "carrierCode","carrierLabel","trackingNo","shippedAt",
    "refundStatus","refundStatusLabel","refundAmountCent",
    "orderCreateTime","paidTime" }], "total":39 }

POST /system/gz/jp/fulfill/advance   { "itemIds":["12","13"], "targetStatus":"jp_shipped" }
POST /system/gz/jp/fulfill/ship      { "itemIds":["12","13"], "carrierCode":"sf", "trackingNo":"SF1234567890" }
// 两者同构返回：
200 { "code":200, "data":{
      "targetStatus","targetStatusLabel","requested","advanced","skipped","rejected",
      "carrierCode","carrierLabel","trackingNo",            // 仅 /ship
      "rejects":[{"itemId","currentStatus","currentStatusLabel","reasonCode","reason"}] } }
```
| code | 含义 | 前端动作 |
|---|---|---|
| 200 `advanced>0` | 部分/全部成功 | 提示「已推进 N 行」；`rejects` 非空时把那几行标红并显示 `reason` |
| 200 `advanced=0, skipped=N` | 全部已是目标态（同事刚推过） | 提示「已是最新状态」，**刷新列表**，不算失败 |
| 4108 | 一行都推不动 | 红字弹 msg（已含首条原因 + 被拒行数），**刷新看板** |
| 4109 | 发货缺快递/运单号，或误用 advance 推 delivered | 引导改用「批量发货」并填齐两个字段 |
| 4110 | 跨客人 / 单号已属他人 | 提示取消跨组勾选或换单号 |
| 500 `非法的目标状态：x` | 目标值不在字典里 | 下拉写死字典值即可 |

`rejects[].reasonCode` 取值：`NOT_FOUND` / `ORDER_UNPAID` / `TERMINAL` / `BACKWARD` / `ILLEGAL_TARGET` / `UNKNOWN_CURRENT` / `SHIP_REQUIRED`。

- **目标状态下拉**：读字典 `gz_jp_fulfill_status`（9284）。★ **去掉 `purchasing`（起点，推它必被拒）和 `delivered`（必须走发货按钮）**，剩 5 项：`purchase_failed` / `await_seller_ship` / `jp_shipped` / `customs` / `cn_sorting`。
- **快递公司下拉**：读字典 `gz_express_carrier`（9130，既有）。
- **跨客人勾选置灰**：后端已硬拦 4110（`/ship`）；`/advance` 不限客人（推进状态与包裹无关）。
- **单次上限 200 行**：超了后端直接拒。「全选」时记得截断或分批发。
- ⚠️ **别用两次一模一样的 body 写幂等 E2E** —— `@RepeatSubmit` 会返回 `500 Repeat submit is not allowed`（改一下 itemIds 顺序即可绕开）。
- ⚠️ **原 accept 第 2 条的登录命令跑不通**（`clientId` 要放 body），**主线程已直接修正 prompt.md**，正确写法见修正后的文件。

### 给 GZ-JP-109（admin 订单管理只读）

- 需要新建 `/system/gz/jp/order/*`，本卡**没碰**（本卡只有 `/system/gz/jp/fulfill/*`）。
- 可直接照抄的模式：`GzJpFulfillServiceImpl.selectBoardPage` —— **自定义 `@Select` + `Page` 作首参 + `<script>` 动态条件 + 服务层补人信息**（`IGzUserService.selectVoMapByIds` 批量取，别逐单查 N+1）；`GzJpOrderItemMapper.selectBoardPage` 是现成模板。
- **订单管理与履约看板的口径不同**：看板**只出付过款**的行；订单管理是资金视角，`created` / `cancelled` 的单**必须出**，别顺手把 `isPaidLike` 抄过去。
- 菜单 14020 段仍全空；`sys_menu` GZ-JP 已占 14000-14005、14010-14014。
- ⚠️ **原 accept 第 2 条的登录命令同样跑不通**，**主线程已直接修正 prompt.md**。

### 编号段位现状

| 资源 | 已占 | 下一个空号 |
|---|---|---|
| `sys_menu` GZ-JP | 14000-14005、14010-14014；**本卡未占** | 14020 段（109）/ 14030 段（108） |
| `dict_id` / `dict_code` | 9280-9285 / 92801-92821；**本卡未占** | 9286 / 92822 |
| jp 业务错误码 | 4101-4107（105）、**4108-4110（本卡）** | **4111** |
| Flyway | …V202608070633；**本卡零迁移** | `date +V%Y%m%d%H%M` |

### 全 jp 域通用（本卡再次踩到 / 新增）

- **改 gz-jp 后必须 `mvn clean install`**，跑测试带 `-am`；accept 的 STATE 类命令在上游模块会因「没有匹配的测试」失败，加 `-Dsurefire.failIfNoSpecifiedTests=false`。
- 单测类必须 `@Tag("dev")`。
- **`docker exec` 传 heredoc SQL 必须带 `-i`**（否则 stdin 不进容器，SQL 静默不执行、还不报错）。
- **多租户拦截器对自定义 UPDATE 只补被更新表的 `tenant_id`，不下探子查询** —— EXISTS 子查询里的 `o.tenant_id` 要手写。
- **自定义 UPDATE 不走公共字段自动填充**：`version = version + 1` 和 `update_by` 都得手写。
- **批量接口的入参 id 必须服务端去重 + 升序**再加锁，别指望调用方守规矩。
- 涉及并发的实现**单测全绿不算数**，必须真库并发跑一轮（本卡跑了 3 轮，含推进×发货混合）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

建议覆盖：后端集成 `/system/gz/jp/fulfill/{list,advance,ship}` 全链路（4108/4109/4110、未支付行排除、终态不可动、跳过中间态、幂等 skip）；权限（108 seed 前非超管应 403，别当 bug 报）；API 契约回归（字段名与「给 108」段逐字一致、ID 全 string、列表返 `rows`）；跨域回归（`GET /app/gz/jp/order/{id}` 的 `items[].fulfillStatus/carrierCode/trackingNo/shippedAt` 应随本卡推进/发货实时变化）；并发回归（6 并发重叠 itemIds → 总 advanced == 行数、每行 version 只 +1、无死锁）。本卡**无 admin/mp 页面** → 无 Playwright / 模拟器 E2E 对象。⚠️ 跑前确认 8080 上是本卡 `mvn clean install` 后的 jar。

---

**环境交还**：起的 `:8081` 实例已关闭；并行 agent 在用的 `:8080` 未被触碰、仍返回 200。压测临时数据已硬删（残留 0 行）。测试脚本在 scratchpad，未污染项目目录。**未 commit**。

**accept 三条：PASS**（ACCEPT1_EXIT=0 / ACCEPT2_EXIT=0 / ACCEPT3_EXIT=0）。
