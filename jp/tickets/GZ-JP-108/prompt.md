---
ticket: GZ-JP-108
track: FULFILL
phase: D5
size: L
req_refs: [REQ-FULFILL-001, REQ-FULFILL-003, REQ-FULFILL-004, REQ-FULFILL-006, REQ-FULFILL-007]
depends_on: [GZ-JP-106, GZ-JP-107]
touches:
  - code/main/plus-ui/src/views/gz-jp/fulfill/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - UI:admin.fulfill_board
  - UI:admin.fulfill_board.batch_advance
  - UI:admin.fulfill_board.batch_ship
  - UI:admin.fulfill_board.mark_failed
  - FLOW:F-JP-03.step1
accept:
  - name: 菜单 path/component 非空且父级有效（防 404 与错父级）
    form: MENU
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14030 AND 14039
        AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
           OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
           OR (m.parent_id<>0 AND NOT EXISTS
               (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)) )" | grep -qx 0 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14030 AND 14039" | grep -qE '^[1-9]'
  - name: getRouters 真下发本页路由（不只是库里有行）
    form: MENU
    run: |
      TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"admin123","grantType":"password","tenantId":"1001","clientId":"e5cd7e4891bf95d1d19206ce24a7b32e"}' | jq -r '.data.access_token'); \
      curl -s http://localhost:8080/system/menu/getRouters \
        -H "Authorization: Bearer $TOKEN" -H 'clientid: e5cd7e4891bf95d1d19206ce24a7b32e' \
        | jq -e '[.data | .. | objects | select(.path? != null) | .path] | map(select(test("fulfill"))) | length > 0' >/dev/null
  - name: 按客人聚合视图 + 批量推进 + 批量发货 E2E
    form: API
    run: |
      cd code/main/plus-ui && npx playwright test e2e/gz-jp/fulfill-board.spec.ts --reporter=line
---

# GZ-JP-108 admin 履约看板（★ 店员侧最重要的页）

## §0 状态自检

1. GZ-JP-106/107 接口可调。
2. `grep -rhoE "\b140[0-9]{2}\b" ruoyi-admin/src/main/resources/db/migration/*.sql | sort -un` —— 
   确认 14030 段未被前序 ticket 占用。

## What

Kevin 已拍板：**主视图按客人聚合**（不是平铺商品行）。理由是打包决策的问法就是
「这个客人有哪些货到齐了」，且可跨订单凑包裹（REQ-FULFILL-006）。

**布局**：客人为可展开行组，组头显示「客人名 · 共 N 款 · 待处理 M」+ 组级批量操作按钮；
组内每行 = 一个订单商品行（商品 / 数量 / 所属订单号 / 当前状态 / 运单号）。
支持跨组勾选（同一批发货可能来自不同客人？—— **不支持跨客人**，一个运单号只属一个客人，
勾选限制在组内，跨组勾选时按钮置灰并提示）。

**顶部筛选**：客人 / 履约状态 / 场 / 下单时间段。

**三个批量操作**：
1. 批量推进到下一状态（可跳过中间态）
2. 批量发货 —— 弹窗选快递公司（`gz_express_carrier` 字典）+ 填一个运单号
3. 批量标记购买失败 —— **二次确认**（会触发真实退款，不可逆）

## AC

- 按客人聚合、可展开、组内可多选
- 跨订单的货能在同一个客人组里一起勾选发货
- 批量标记失败有二次确认弹窗
- 菜单挂 14030 段

## 视觉纪律

admin 走 ruoyi / Element Plus 默认审美，**不引用 mockup、不调样式**，复用 plus-ui BizTable。
