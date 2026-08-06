---
ticket: GZ-JP-109
track: ORDER
phase: D5
size: S
req_refs: [REQ-ORDER-006, REQ-FULFILL-001]
depends_on: [GZ-JP-105]
touches:
  - code/main/plus-ui/src/views/gz-jp/order/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - UI:admin.order
accept:
  - name: 菜单 path/component 非空且父级有效（防 404 与错父级）
    form: MENU
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14020 AND 14029 AND m.del_flag='0'
        AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
           OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
           OR (m.parent_id<>0 AND NOT EXISTS
               (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id AND p.del_flag='0')) )" | grep -qx 0 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14020 AND 14029 AND del_flag='0'" | grep -qE '^[1-9]'
  - name: 订单列表返回行内容完整
    form: API
    run: |
      TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' \
        -H 'clientid: e5cd7e4891bf95d1d19206ce24a7b32e' \
        -d '{"username":"admin","password":"admin123","grantType":"password","tenantId":"1001"}' | jq -r '.data.access_token'); \
      curl -s 'http://localhost:8080/system/gz/jp/order/list' \
        -H "Authorization: Bearer $TOKEN" -H 'clientid: e5cd7e4891bf95d1d19206ce24a7b32e' \
        | jq -e '.rows[0] | has("orderNo") and has("totalAmountCent") and has("businessStatus") and has("itemCount")' >/dev/null
---

# GZ-JP-109 admin 订单管理（只读）

## §0 状态自检

1. GZ-JP-105 已 merge，dev 库有已支付订单。

## What

只读查询列表 + 详情抽屉。**不在此页做履约推进**（那是 GZ-JP-108 履约看板的职责），
本页定位是"查单"。

- 列：订单号 / 客人 / 款数 / 实付 / 订单状态 / 下单时间
- 筛选：订单号 / 客人 / 订单状态 / 时间段
- 详情抽屉：订单头 + 逐行商品及其履约状态（只读）+ 收货地址

## AC

- 菜单挂 14020 段
- 列表与详情均只读，无写操作按钮
