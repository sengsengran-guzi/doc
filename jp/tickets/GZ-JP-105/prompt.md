---
ticket: GZ-JP-105
track: ORDER
phase: D4
size: L
req_refs: [REQ-ORDER-003, REQ-ORDER-004, REQ-ORDER-006, REQ-ORDER-010, REQ-SNAP-004]
depends_on: [GZ-JP-104, GZ-SYS-022]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - FLOW:F-JP-02.step4
  - FLOW:F-JP-02.step5
  - FLOW:F-JP-02.step6
  - FIELD:gz_jp_order.total_amount_cent
  - FIELD:gz_jp_order_item.source
  - FIELD:gz_jp_order_item.fulfill_status
accept:
  - name: 两表建表且公共字段全集齐
    form: DDL
    run: |
      for T in gz_jp_order gz_jp_order_item; do
        docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema='ry-vue' AND table_name='$T'
          AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
          | grep -qx 7 || exit 1
      done
  - name: 订单金额后端重算，前端篡改价不生效
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpOrderSubmitTest 2>&1 | tail -5
  - name: 支付回调后订单转 paid 且全部行进入购买中
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpPayCallbackTest 2>&1 | tail -5
---

# GZ-JP-105 订单 + 订单行建表 + 下单事务 + 支付回调

## §0 状态自检

1. GZ-SYS-022（支付多 appid）已 merge —— 否则新小程序调不起支付，本 ticket 无法端到端验。
2. `grep -rn "PayBusinessType" ruoyi-modules/ruoyi-gz-common/` —— 确认枚举位置，本卡要加 `jp`。
3. 确认 `PayCallbackDispatcher` 的 SPI 接口签名（照 `PreorderPayCallbackHandler` 范式写）。

## What

本域的核心链路。**照抄 `GzOrdOrderServiceImpl.submit()` 的范式**（跨域事务 + 快照 + 统一建单），
但表不复用（旧表服务旧小程序的旧用户）。

**下单事务**：
1. 校验购物车勾选项：场仍 open、商品仍 on_shelf、价格与快照一致
2. 校验地址归属当前用户
3. **后端重算金额**（`Σ unit_price × qty`），**不信前端传来的价**
4. 生成 `order_no = JPO-yyyyMMdd-6位`
5. INSERT 订单 + 逐行 `gz_jp_order_item`，每行落 `product_snapshot_json`
6. 调 GZ-PAY 统一建单，`business_type='jp'`

★ **无运费项** —— 全包邮（REQ-ORDER-004），订单表不设运费列，合计就是商品合计。

★ `order_item.source` 默认 `'batch'` —— 为二期代切 `snap` 预留维度（REQ-SNAP-004），
二期只加枚举值不改表结构。

**支付回调 SPI**：实现 `PayCallbackHandler`，`supportedBusinessType()="jp"`。
回调后订单转 `paid`，**全部 order_item 的 `fulfill_status` 置 `purchasing`**。

## AC

- 下单金额后端重算，前端传假价不生效
- 支付回调幂等（重复回调不重复推进）
- 一单可含多场商品

## ⚠️ 已知坑

`@Version` 实体 **insert 后再 updateById 补字段会静默不落库**（内存 version 仍为 null）。
校验后**配齐字段一次 insert**，不要 insert 完再补 update。
