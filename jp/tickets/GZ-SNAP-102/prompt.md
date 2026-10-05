---
ticket: GZ-SNAP-102
track: SNAP
phase: D7
size: M
req_refs: [REQ-SNAP-004, REQ-SNAP-021]
depends_on: [GZ-SNAP-101]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FIELD:gz_jp_order_item.source
  - FIELD:gz_jp_order_item.product_id
  - FIELD:gz_jp_order_item.snap_item_id
  - FIELD:gz_jp_order_item.product_snapshot_json
  - FIELD:gz_jp_order_item.fulfill_status
  - FLOW:F-JP-09.step1
  - OWN:gz_jp_snap_item
accept:
  - name: 按来源判定的状态机入口：snap 行 await_seller_ship→purchase_failed 允许；batch 行全部状态对与一期结果逐一相同
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpFulfillStateMachineSnapTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpFulfillStateMachineSnapTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpFulfillStateMachineSnapTest.xml
    counterfeit: 按来源入口对 batch 行任一 (from,to) 的结果偏离一期 checkAdvance(from,to)（如顺手收紧或放宽拼团行），或 snap 行该转移被拒 → 穷举用例红
  - name: 订单行 source 与两个外键互斥校验 + 快照 snap 段往返不丢字段
    form: DATA
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpOrderItemSourceInvariantTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpOrderItemSourceInvariantTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpOrderItemSourceInvariantTest.xml
    counterfeit: source=snap 却允许 product_id 有值 / snap_item_id 为空，或快照序列化漏了 quoteId、priceJpy → 红
  - name: 一期履约看板 / 订单查询在混入代切行（product_id 为空）后不报错、拼团行结果不变
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpMixedSourceQueryTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpMixedSourceQueryTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpMixedSourceQueryTest.xml
    counterfeit: 履约看板仍用 INNER JOIN gz_jp_product（代切行被吞掉）或取名称时 NPE → 红
---

# GZ-SNAP-102 代切实体 / 枚举 / 快照 / 状态机扩展

## §0 状态自检

1. GZ-SNAP-101 已完工：5 张新表与两表 ALTER 在 dev 库里（`DESC gz_jp_snap_purchase`）。
2. 列出一期所有依赖 `product_id` 非空的地方，逐个过：
   `grep -rn "product_id\|getProductId\|gz_jp_product" ruoyi-modules/ruoyi-gz-jp/src/main --include=*.java --include=*.xml`
3. `GzJpItemSource` 枚举（ADR-0025 frontmatter anchor）与履约状态机实现类（`GzJpFulfillStateMachineTest` 测的那个）。

## What

1. 5 张新表的 entity / mapper（`org.dromara.gz.jp.domain.entity` / `mapper`），字段照 field-ssot；带 `@Version` 的表注意
   「insert 后 updateById 补字段会静默不落库」——字段一次配齐再 insert。
2. 枚举：`GzJpItemSource.SNAP`；`SnapPurchaseStatus` / `SnapTradeStatus` / `SnapGate` / `SnapMode` / `SnapFailReason` / `SnapAccountHealth`，值与 101 的字典一一对应。
3. 订单行快照新增 `snap` 段 DTO（字段见 `FIELD:gz_jp_order_item.product_snapshot_json`），序列化 / 反序列化往返测试。
4. 应用层不变量（订单行写入的统一入口里校验）：`source=batch ⇔ product_id 非空且 snap_item_id 为空`；`source=snap ⇔ snap_item_id 非空且 product_id 为空`。
5. 履约状态机：加按来源判定的入口（如 `checkAdvance(source, from, to)`）——snap 行 `await_seller_ship → purchase_failed` 允许；batch 行对全部 7×7 (from,to) 与一期 `checkAdvance(from,to)` 结果逐一相同（一期 GZ-JP-106 有意允许任意非终态→purchase_failed，不收紧；Kevin 2026-10-05 定方案 A）。顺手修正 `GzJpFulfillStatus` 枚举注释里「purchase_failed 只挂在 purchasing 下」的误导图。
6. 一期查询兼容：履约看板、admin 订单、mp 订单列表 / 详情凡是 JOIN `gz_jp_product` 的改 LEFT JOIN 或按 source 分支；代切行的名称 / 图片取快照 `snap` 段。

## AC

- 一期全部单测照旧绿（拼团行为零变化）。
- 三个新测试类绿；混合来源查询下拼团行的返回与改动前逐字段一致。

## 口径提示

- 本卡只做「能装下代切行」，不做任何代切业务（下单、调度、退款都在后续卡）。
- 不新增 API。
