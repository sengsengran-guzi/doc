---
ticket: GZ-SNAP-402
track: SNAP-ADMIN
phase: D11
size: M
req_refs: [REQ-SNAP-030, REQ-SNAP-042, REQ-SNAP-044]
depends_on: [GZ-SNAP-401]
touches:
  - code/main/plus-ui/src/views/gz-jp/snap/account/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/plus-ui/src/lang/zh_CN.ts
  - code/main/plus-ui/src/lang/en_US.ts
  - code/main/plus-ui/e2e/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - UI:admin.snap_account
  - FLOW:F-JP-07.step6
  - FLOW:F-JP-11.step3
  - FIELD:gz_jp_snap_account.admin_enabled
  - FIELD:gz_jp_snap_account.daily_limit
  - OWN:gz_jp_snap_account
  - OWN:snap_runtime_config
accept:
  - name: 采购账号 14060 段菜单 path/component 非空且父级是 14040
    form: MENU
    run: |
      Q() { docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "$1"; }
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id=14060 AND menu_type='C' AND parent_id=14040 AND path<>'' AND component<>''" | grep -qx 1 && \
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14061 AND 14069 AND menu_type='F' AND perms LIKE 'gz:jp:snap:account:%'" | grep -qE '^[2-9]'
    counterfeit: 菜单挂错父级或 path 为空 → 红
  - name: 恢复自动下单只能 admin 手动、需二次确认；有账号处于 challenge 时恢复被拒
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapAutoSwitchTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapAutoSwitchTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapAutoSwitchTest.xml
    counterfeit: 没有任何健康启用账号时仍允许打开总开关（打开后所有单立刻转 no_account）→ 红
  - name: 账号页 E2E：启停账号、改上限与冷却、总开关恢复的二次确认
    form: API
    run: cd code/main/plus-ui && npx playwright test e2e/gz-jp/snap-account.spec.ts --reporter=line
    counterfeit: 恢复按钮无二次确认，或页面显示的今日下单数不随换日清零 → spec 红
---

# GZ-SNAP-402 admin 采购账号与自动下单总开关

## §0 状态自检

1. GZ-SNAP-401 已建 14040 目录；GZ-SNAP-301 的熔断方法与探测结果（Redis）可读。
2. 菜单空号复查 14060–14069。

## What

1. 后端 `/system/gz/jp/snap/account`：列表 / 新增 / 编辑（`account_code` 新增后不可改、`nickname`、`daily_limit`、`cooldown_sec`）/ 启用 / 停用；「解除暂停」清空 `pause_reason`（风控熔断、余额不足都写它，处理完由 admin 解除，二次确认）；
   **不提供** health_status 写接口（只由心跳写）；不存任何密码或 Cookie 字段。
2. 总开关接口：`GET /auto-switch`（enabled / pausedReason / pausedAt / 最近一次探测结果）、`POST /auto-switch/resume`（需当前至少一个账号 `admin_enabled=1` 且 `healthy`，否则拒）、
   `POST /auto-switch/pause {reason}`（手动暂停 = 调熔断方法，queued 全转人工）。写 sys_config 后清两级缓存。
3. 页面（照 gz-bean/store 范式）：页头总开关块（开 / 关、原因、恢复二次确认）+ 最近探测结果；表格列与操作照 `UI:admin.snap_account`。
4. 菜单 14060（C，`gz-jp/snap/account/index`）+ 按钮 14061–14069（`gz:jp:snap:account:query|edit|switch`），授权 owner。

## AC

- 三条 accept 绿。
- 恢复总开关后，已在人工队列里的单**不会**自动回到自动队列（人工队列只由人处理）。
