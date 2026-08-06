---
ticket: GZ-JP-101
track: EVENT
phase: D3
size: M
req_refs: [REQ-EVENT-001]
depends_on: []
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
  - code/main/plus-ui/src/views/gz-jp/event/**
  - code/main/plus-ui/src/api/gz-jp/**
blueprint_refs:
  - FLOW:F-JP-01.step1
  - FLOW:F-JP-01.step3
  - FLOW:F-JP-01.step4
  - FIELD:gz_jp_event.status
  - UI:admin.event
accept:
  - name: 建表且公共字段全集齐
    form: DDL
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='ry-vue' AND table_name='gz_jp_event'
        AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
        | grep -qx 7
  - name: 菜单 path/component 非空且父级有效（防 404 与错父级）
    form: MENU
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14000 AND 14009
        AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
           OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
           OR (m.parent_id<>0 AND NOT EXISTS
               (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)) )" | grep -qx 0 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14000 AND 14009" | grep -qE '^[1-9]'
  - name: 关场后场不再出现在 mp 可下单列表
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpEventStatusTest 2>&1 | tail -5
---

# GZ-JP-101 场（gz_jp_event）建表 + admin 场管理

## §0 状态自检

1. `grep -rhoE "\b1[45][0-9]{3}\b" ruoyi-admin/src/main/resources/db/migration/*.sql | sort -un | head` —— 
   ★ 确认 14000 段仍空闲。**menu_id 撞号是本项目踩过 3 次的坑**（GZ-BEAN-036 曾误删核销权限导致全线 403）。
2. `date +V%Y%m%d%H%M` 取当下真实时间戳做迁移文件名。
3. 确认 `ruoyi-gz-jp` 模块已在父 pom 注册；没有则本 ticket 先建模块骨架。

## What

新建后端模块 `ruoyi-gz-jp`（包名 `org.dromara.gz.jp`）+ 场的建表与 admin CRUD。

字段以 `doc/jp/authority/field-ssot.yaml` 的 `gz_jp_event` 为唯一真源，勿另起口径。

**状态判定走读时惰性**：查询时比对 `end_time` 实时判定是否已结束，同时允许店员手动置 closed。
★ **不要写 cron** —— SnailJob 在 prod 根本没部署，`@JobExecutor` 一个都不会跑，写了等于没有。

## AC

- admin 场管理：列表 / 新建 / 编辑 / 开场 / 关场 / 删除
- 菜单挂 14000 段（14000 目录「日本拼团」、14001 场管理 + 按钮 14002-14005）
- 场未 open 时 mp 侧查不到

## ⚠️ 改 ruoyi-gz-* 模块后必须 clean install

`mvn spring-boot:run -pl ruoyi-admin` 加载的是 `~/.m2` 里的 jar 而非 target/classes。
非 clean 的 install 既不重打 jar 也不重编译测试，exit 0 骗人。必须 `mvn clean install -DskipTests -pl ... -am` 后重启。
