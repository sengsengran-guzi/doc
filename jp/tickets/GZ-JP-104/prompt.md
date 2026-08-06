---
ticket: GZ-JP-104
track: ORDER
phase: D4
size: S
req_refs: [REQ-ORDER-005]
depends_on: [GZ-JP-102]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - FLOW:F-JP-02.step2
  - FIELD:gz_jp_cart_item.qty
accept:
  - name: 建表且公共字段全集齐
    form: DDL
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='ry-vue' AND table_name='gz_jp_cart_item'
        AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
        | grep -qx 7
  - name: 同商品重复加购合并数量而非新增行
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpCartServiceTest 2>&1 | tail -5
---

# GZ-JP-104 购物车（gz_jp_cart_item）建表 + API

## §0 状态自检

1. GZ-JP-102 已 merge（商品表存在）。

## What

购物车是**我方从甲方「一个客人买了 30 款商品」推导出的必需件**（REQ-ORDER-005）——
逐款单独下单在这个量级不可用。

- 建表 `gz_jp_cart_item`，唯一键 `(tenant_id, user_id, product_id)` → 重复加购走 qty 累加
- `POST /app/gz/jp/cart` 加购 · `PUT` 改数量 · `DELETE` 删除 · `GET /list` 列表（按场分组返回）
- 列表接口需**实时标注失效项**：场已 closed 或商品已 off_shelf → `invalid: true`，不计入合计

## AC

- 同商品重复加购 = 数量累加，不产生第二行
- 失效项在列表里明确标出且不可勾选
- 跨场商品可共存于同一购物车
