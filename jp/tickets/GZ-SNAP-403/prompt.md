---
ticket: GZ-SNAP-403
track: SNAP-ADMIN
phase: D11
size: M
req_refs: [REQ-SNAP-007, REQ-SNAP-019, REQ-SNAP-020, REQ-SNAP-022, REQ-SNAP-040, REQ-SNAP-048, REQ-SNAP-061]
depends_on: [GZ-SNAP-402]
touches:
  - code/main/plus-ui/src/views/gz-jp/snap/config/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/plus-ui/src/lang/zh_CN.ts
  - code/main/plus-ui/src/lang/en_US.ts
  - code/main/plus-ui/e2e/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - UI:admin.snap_config
  - FLOW:F-JP-11
  - FLOW:F-JP-11.step1
  - OWN:snap_runtime_config
accept:
  - name: 代切配置 14080 段菜单 path/component 非空且父级是 14040
    form: MENU
    run: |
      Q() { docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "$1"; }
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id=14080 AND menu_type='C' AND parent_id=14040 AND path<>'' AND component<>''" | grep -qx 1 && \
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14081 AND 14089 AND menu_type='F' AND perms LIKE 'gz:jp:snap:config:%'" | grep -qE '^[2-9]'
    counterfeit: 菜单挂错父级或 path 为空 → 红
  - name: 配置保存校验 + 落 1001 租户 + 保存后立即生效（两级缓存已清）
    form: DATA
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapConfigServiceTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapConfigServiceTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapConfigServiceTest.xml
    counterfeit: 只清 Redis 不清 Caffeine（保存后报价仍用旧加价比例）或允许负数 / 超过 1 的加价比例 → 红
  - name: 配置页 E2E：五个 tab 读写、定价未配时红字提示、手动录入汇率
    form: API
    run: cd code/main/plus-ui && npx playwright test e2e/gz-jp/snap-config.spec.ts --reporter=line
    counterfeit: 定价为空时页头不提示，或手动汇率保存后汇率 tab 仍显示旧值 → spec 红
---

# GZ-SNAP-403 admin 代切配置（定价 / 过滤 / 准入 / 交易 / 汇率）

## §0 状态自检

1. 读 `FLOW:F-JP-11` body 的 5 个配置键结构；读 memory「新增 sys_config 必写 tenant 1001 + 两级缓存」——保存后必须清 Caffeine + Redis 两级。
2. GZ-SNAP-303 的汇率手动录入接口可调。菜单空号复查 14080–14089。

## What

1. 后端 `/system/gz/jp/snap/config`：`GET /{key}` / `PUT /{key}`，key ∈ pricing / filter / gate / trade（auto 归账号页管）；
   校验：`markupRatio ∈ [0,1]`、金额类为非负整数分、`quoteTtlSec ∈ [60,1800]`、`rateDeadlineHours ∈ [1,240]`、`patrolMinutes ∈ [5,120]`、列表去重去空白。
   保存写 1001 租户那一行，随后清两级缓存。
2. 汇率 tab：最新一条（值 / 来源 / 抓取时间 / 是否超 6 小时）+ 最近 20 条 + 手动录入。
3. 页面 tab 表单（`UI:admin.snap_config`），准入 tab 三组词：屏蔽词 / 拒代购词 / 转人工词；定价三项任一为空 → 页头红字「未配置，小程序无法报价」。
4. 菜单 14080（C，`gz-jp/snap/config/index`）+ 按钮 14081–14089（`gz:jp:snap:config:query|edit|fx`），授权 owner。

## AC

- 三条 accept 绿。
- 加价比例与汇率只在本页与订单快照出现，mp 侧拿不到（GZ-SNAP-303 已断言）。
