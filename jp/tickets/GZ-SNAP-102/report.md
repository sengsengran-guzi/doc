# GZ-SNAP-102 完工报告（部分完成；状态机一项 spec_conflict 已 escalate）

> 主线程代为落盘（impl subagent 写 .md 被 hook 拦截，原文回传）。commit：RuoYi-Vue-Plus@2c46e7f1d（task/D7），33 文件全在 ruoyi-gz-jp，无迁移。

## §1 SPEC_CONFLICT：What #5 与 accept #0
- ticket 要求：新增 `await_seller_ship → purchase_failed`，只对 source=snap 生效，拼团行仍被拒；counterfeit 为「全局放开 → batch 行非法转移被拒用例红」。
- 一期现状（GZ-JP-106）：`GzJpFulfillStateMachine.check()` 对目标 purchase_failed 只要当前非终态即放行，**拼团行早已能从 await_seller_ship 进 purchase_failed**；类注释列为「两个刻意的决定」之一（中途买不到的货必须能退款）。已有用例 `GzJpFulfillStateMachineTest.purchaseFailedIsBranch` 断言 PURCHASING / AWAIT_SELLER_SHIP / JP_SHIPPED / CUSTOMS / CN_SORTING → purchase_failed 全部允许（主线程已核实）。
- 矛盾：收紧拼团行 → 违反本卡 AC「一期单测照旧绿、拼团行为零变化」，且只砍 await_seller_ship 一个起点规则自相矛盾；维持现状 → accept #0 的 counterfeit 不可能成立。
- 口径来源：flows.yaml F-JP-09.step1（第 425 行）、phase-plan D7 QA 范围、纸面推演 S6，推测照 `GzJpFulfillStatus` 枚举注释图推出，未核对状态机实现。
- **方案 A（实现方推荐）**：状态机不收紧；加按来源判定入口 `checkAdvance(source, from, to)`，snap 行 await_seller_ship→purchase_failed 允许，batch 行对全部 (from,to) 与一期 `checkAdvance(from,to)` 逐一相等（7×7 穷举）。accept #0 改为断言这两点，counterfeit 改为「按来源入口对 batch 行偏离一期结果就红」。同步修正 flows F-JP-09.step1 / phase-plan D7 QA 措辞、枚举注释图。代切行真正需要的拦截在 F-JP-09.step3 守卫（admin 三个批量入口），归守卫卡。
- **方案 B（不推荐）**：真收紧拼团行，需改一期用例并接受「等待官方发货中的拼团货不能标失败」。
- 口径定后补做：一个静态方法 + 一个测试类，无迁移。

## 实现摘要（What 1/2/3/4/6，已完成）
**新增**：实体 `GzJpSnapItem` / `GzJpSnapPurchase` / `GzJpSnapAccount`（带 @Version）/ `GzJpSnapTerm` / `GzJpFxRate`（`ratePer100jpy` 显式 `@TableField("rate_per_100jpy")`）；5 个 `BaseMapperPlus` 空 mapper；枚举 `GzJpSnapPurchaseStatus` / `GzJpSnapTradeStatus` / `GzJpSnapGateResult` / `GzJpSnapMode` / `GzJpSnapFailReason` / `GzJpSnapAccountHealth` / `GzJpRefundType`（项目惯例 GzJpSnapX；`GzJpSnapGate` 留给 303 的判定器）；`service/internal/GzJpOrderItemSourceInvariant`（batch ⇔ product_id 非空且 snap_item_id 空；snap ⇔ 反之；source 空/未知一律拒，ServiceException 4116）；测试 `GzJpOrderItemSourceInvariantTest`(8) / `GzJpMixedSourceQueryTest`(5) / `GzJpSnapEnumDictTest`(2)。

**修改**：`GzJpItemSource` 加 SNAP；`GzJpOrderItem` 加 snapItemId；`GzJpRefund` 加 refundType；`JpOrderSnapshot` 新增 `Snap` 段 15 字段（`Product.snap` `@JsonInclude(NON_NULL)`，拼团快照文本不变；`resolveName()` / `resolveMainImageId()` @JsonIgnore）；`GzJpOrderServiceImpl` 拼团下单 insert 前调不变量校验、mp 详情/列表走 resolve*；`GzJpOrderAdminServiceImpl` / `GzJpFulfillServiceImpl` 走 resolve*；`GzJpOrderItemMapper` 仅注释；`GzJpRefundTxService` 新建退款显式 `refundType=purchase_failed`、注释改 uk_item_type；`GzJpRefundFixture` 唯一键模拟改 (order_item_id, refund_type)；`GzJpOrderErrorCode` +ITEM_SOURCE_INVALID=4116。

## AI 自测
```
accept#1 exit=0
name="org.dromara.gz.jp.service.impl.GzJpOrderItemSourceInvariantTest" tests="8" errors="0" skipped="0" failures="0"
accept#2 exit=0
name="org.dromara.gz.jp.service.impl.GzJpMixedSourceQueryTest" tests="5" errors="0" skipped="0" failures="0"
[SQL] 扫描 15 条 @Select，无 INNER JOIN gz_jp_product
accept#0 exit=1   （GzJpFulfillStateMachineSnapTest 未写：口径冲突）
```
gz-jp 全量（-Dtest='GzJp*'）：tests=232 failures=0 errors=0（一期 217 + 本卡 15）；GzJpOrderSubmitTest 21 全绿（拼团下单接入不变量无误拒）。枚举⇔字典 7 组值与 V202610050725 完全一致。

## 风险
- accept #0 红（§1）。
- 未重启 8080 做真库冒烟（SQL 未改，读侧由单测覆盖）。
- 代切行 productNo / eventName 为 null，看板与详情显示空，是否用 externalId 顶替归 UI 卡。

## 对下游
- GZ-SNAP-304：建 snap 行 insert 前调 `GzJpOrderItemSourceInvariant.check(item)`；报价写进 `JpOrderSnapshot.Product.snap`。F-JP-06.step3 ⑥「主图转存失败快照留原 URL 兜底」但 field-ssot snap 段无 URL 字段 —— 要兜底须先在 field-ssot 加字段（**蓝图缺口**）。
- GZ-SNAP-306：`GzJpRefundMapper.selectByOrderItemIds` 不区分类型，一行有 shipping_diff 后 `createRefunds` 会误判「已退过」跳过 purchase_failed —— 306 须按类型过滤。
- GZ-SNAP-303：准入结果枚举 `GzJpSnapGateResult`。jp 域下一个空闲错误码 4117。

---

# 返工增量（Kevin 定方案 A）—— What #5 完成

commit：RuoYi-Vue-Plus@e3bc65aa1（task/D7，在 GZ-JP-110 @34e849c28 之后）。

| 文件 | 改动 |
|---|---|
| `service/internal/GzJpFulfillStateMachine.java` | 新增 `checkAdvance(source, from, to)`：batch 原样委托一期 `checkAdvance(from,to)`；snap 显式允许 `await_seller_ship→purchase_failed`，其余同一期；source 空/未知 → `UNKNOWN_CURRENT`（不回落 batch）。类注释图更正。一期二参入口与 `check` 未动 |
| `domain/enums/GzJpFulfillStatus.java` | 注释图更正为「分支：任意非终态 → purchase_failed」，枚举值不变 |
| `test/.../GzJpFulfillStateMachineSnapTest.java`（新，`@Tag("dev")`） | ① batch 7×7 与一期逐一相同（49 组计数校验）② snap 该转移允许 ③ snap 其余组同一期 + TERMINAL/SHIP_REQUIRED 锚 ④ source null/""/"SNAP"/"pindou" → UNKNOWN_CURRENT |

```
accept#0 exit=0  tests="4" errors="0" skipped="0" failures="0"
[状态机] snap await_seller_ship → purchase_failed 允许
[状态机] batch 49 组与一期逐一相同
```
反向验证（临时让 batch await_seller_ship→purchase_failed 返回 BACKWARD，已还原）：`exit=1 failures=1 拼团行结果偏离一期`。
三条 accept 复跑：4/0、8/0、5/0 全 exit=0。gz-jp `-Dtest='GzJp*'`：19 类 tests=253 failures=0；一期 `GzJpFulfillStateMachineTest` 18/18 未改。

对下游：代切系统路径（卖家取消 / 验货退货）改 purchase_failed 用 `checkAdvance(source, from, to)`；「snap 且 trade_status≠rated 拒 admin 三个批量入口」守卫在 F-JP-09.step3 守卫卡，不在状态机。一期 admin 批量入口仍调二参版，对 batch 结果相同。
