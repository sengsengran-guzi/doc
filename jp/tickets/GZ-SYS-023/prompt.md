---
ticket: GZ-SYS-023
track: SYS
phase: D1
size: M
req_refs: [REQ-SYS-004]
depends_on: [GZ-SYS-020]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/domain/entity/GzUser.java
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/service/impl/GzUserServiceImpl.java
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - FLOW:F-JP-00.step3
  - FIELD:gz_user.app_id
accept:
  - name: app_id 列已加且唯一键改为三列
    form: DDL
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='ry-vue' AND table_name='gz_user' AND column_name='app_id'" | grep -qx 1 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT GROUP_CONCAT(column_name ORDER BY seq_in_index) FROM information_schema.statistics
        WHERE table_schema='ry-vue' AND table_name='gz_user' AND index_name='uk_tenant_app_openid'" \
        | grep -qx 'tenant_id,app_id,openid'
  - name: 存量行已回填现小程序 appid，无空值
    form: DATA
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM gz_user WHERE app_id IS NULL OR app_id=''" | grep -qx 0
  - name: 同 openid 不同 app 可共存（两条独立记录）
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-common -am \
        -Dtest=GzUserMultiAppUpsertTest 2>&1 | tail -5
---

# GZ-SYS-023 gz_user 加 app_id 维度

## §0 状态自检

1. `grep -rn "uk_tenant_openid" ruoyi-admin/src/main/resources/db/migration/` —— 找到原始建表迁移，确认唯一键现状。
2. `grep -rn "Tier2-entry-temp\|out-of-order" .claude/CLAUDE.md` —— 复习 Flyway append-only 铁律：**新建迁移文件，绝不改已应用的**。
3. `date +V%Y%m%d%H%M` 取当下真实时间戳做文件名，不要手填计划日期。

## What

同一个自然人在两个小程序里是**两个不同的 openid**，而 `gz_user` 目前只按 `(tenant_id, openid)` 唯一 —— 
不加 app 维度会静默产生"重复人"，且无法判断某条记录属于哪个小程序。

- 新增迁移：`gz_user` 加 `app_id VARCHAR(32) NOT NULL DEFAULT '<现小程序appid>'`
- 唯一键 `uk_tenant_openid` → `uk_tenant_app_openid (tenant_id, app_id, openid)`
- 存量行回填 = 现小程序 appid（用 DEFAULT 即自动完成）
- `GzUserServiceImpl.upsertByOpenid()` 签名加 appId，查询条件带上
- `REGISTER_SOURCE` 常量改为可区分来源

## 决策：不做 unionid 合并

走"加 app_id 列隔离"而非"unionid 合并"，理由：unionid 需甲方把两个小程序绑到同一微信开放平台账号，
当前 prod 该字段极可能为 NULL，依赖它会引入不确定性。合并列为后续增强（ADR-0019 已记）。

## AC

- 两个小程序同一人登录 → 两条独立 gz_user，各自的订单/地址互不可见
- 现有小程序登录行为零变化
