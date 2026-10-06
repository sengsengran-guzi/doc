---
ticket: GZ-SNAP-401
track: SNAP-ADMIN
phase: D11
size: L
req_refs: [REQ-SNAP-031, REQ-SNAP-033, REQ-SNAP-034, REQ-SNAP-043]
depends_on: [GZ-SNAP-307]
touches:
  - code/main/plus-ui/src/views/gz-jp/snap/purchase/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/plus-ui/src/layout/components/Sidebar/SidebarItem.vue
  - code/main/plus-ui/src/lang/zh_CN.ts
  - code/main/plus-ui/src/lang/en_US.ts
  - code/main/plus-ui/e2e/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - UI:admin.snap_purchase
  - FLOW:F-JP-08.step1
  - FLOW:F-JP-09.step5
  - FLOW:F-JP-07.step5
accept:
  - name: 代切目录 14040 + 代切下单 14050 段菜单 path/component 非空、父级有效、按钮权限串齐
    form: MENU
    run: |
      Q() { docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "$1"; }
      Q "SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14040 AND 14059
          AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
             OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
             OR (m.parent_id<>0 AND NOT EXISTS (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)) )" | grep -qx 0 && \
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id=14050 AND menu_type='C' AND parent_id=14040" | grep -qx 1 && \
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14051 AND 14059 AND menu_type='F' AND perms LIKE 'gz:jp:snap:%'" | grep -qE '^[3-9]'
    counterfeit: 14050 挂错父级（挂到 14030 履约看板下）或 component 写错路径为空 → 红
  - name: getRouters 真下发代切下单路由
    form: MENU
    run: |
      TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"admin123","grantType":"password","tenantId":"1001","clientId":"e5cd7e4891bf95d1d19206ce24a7b32e"}' | jq -r '.data.access_token'); \
      curl -s http://localhost:8080/system/menu/getRouters \
        -H "Authorization: Bearer $TOKEN" -H 'clientid: e5cd7e4891bf95d1d19206ce24a7b32e' \
        | jq -e '[.data | .. | objects | select(.path? != null) | .path] | map(select(test("snap"))) | length > 0' >/dev/null
    counterfeit: 菜单 visible 写成 '1'（本项目语义是隐藏）或 status 停用 → 路由不下发 → 红
  - name: 三个 tab 的 E2E：待人工填成功 / 填失败、交易跟踪推进与期限置顶、自动任务只读
    form: API
    run: cd code/main/plus-ui && npx playwright test e2e/gz-jp/snap-purchase.spec.ts --reporter=line
    counterfeit: 交易跟踪没按评价期限升序、「交易取消」不弹二次确认直接退款、或到付商品「已到仓」不填运费也能提交 → spec 红
---

# GZ-SNAP-401 admin 代切下单页（待人工 / 交易跟踪 / 自动任务）

## §0 状态自检

1. GZ-SNAP-305~307 的 admin 接口可调。
2. 菜单空号：`grep -rhoE "\b140[0-9]{2}\b" code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/*.sql | sort -un` +
   活库 `SELECT menu_id FROM sys_menu WHERE menu_id BETWEEN 14040 AND 14099` —— 应全空。本卡占 14040（目录）与 14050–14059。
3. 照抄范式：`plus-ui/src/views/gz-bean/store/index.vue`（查询表单 + 工具栏 + 裸 el-table + 自研 Pagination + dialog + drawer）；
   一期 `views/gz-jp/fulfill/` 与 `e2e/gz-jp/fulfill-board.spec.ts`。
4. `sys_menu.visible`：`'0'`=显示、`'1'`=隐藏。

## What

1. 菜单迁移：14040 目录「代切」（M，挂 GZ-JP 顶级目录 14000 同级或其下，照一期结构）、14050「代切下单」（C，`gz-jp/snap/purchase/index`）、
   14051–14059 按钮：查询 / 人工填结果 / 交易操作 / 查看证据（perms `gz:jp:snap:purchase:query|manual|trade|evidence`）。
   给 owner 角色授权（照一期 seed-menu 迁移的做法）。
2. 页面（方案 A，`UI:admin.snap_purchase`）：
   - 顶部状态条：自动下单开关（只显示，点击跳账号页）+ 暂停原因 + 账号健康汇总；
   - tab「待人工（N）」：manual-list，显示入队原因的中文说明（`reconcile_sold` 标红提示「可能已买到，请先到采购账号的购买记录里核实」；
     `account_unpayable` 提示「采购账号余额不足 / 付款方式不可用」）；行内「填成功」（交易号 + 实际价，实际价高于锁定价时前端直接提示改填失败）「填失败」弹窗；
   - tab「交易跟踪」：按 trade_status 筛选，默认评价期限升序、12h 内标红置顶；行内「卖家已发货」「交易取消（二次确认，待发货 / 已发货可用）」「已到仓（到付商品弹窗必填实际运费，提交后显示差价退款结果）」「已评价」「退货完成（二次确认）」；
   - tab「自动任务」：queued / executing / unknown 只读，含对账次数、last_error、证据查看（图片走 `GzImageThumb`）。
   - 菜单角标 = 待人工数 + 评价临期数（GZ-SNAP-307 `reminder-count`）。
3. 后端补齐本页需要的只读列表接口（自动任务列表、状态条汇总），权限串同上。
4. 可见文案全走 i18n（`zh_CN.ts` / `en_US.ts`），不混 emoji。
5. E2E：`e2e/gz-jp/snap-purchase.spec.ts`，数据造在 fixture 里（经后端接口 + fake 驱动产生，不直接 INSERT 业务表）。

## AC

- 三条 accept 绿。
- 会触发退款的操作（交易取消、退货完成、填失败）都有二次确认；到付商品「已到仓」不填运费无法提交。
