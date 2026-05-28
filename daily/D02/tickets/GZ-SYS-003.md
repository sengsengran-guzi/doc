# GZ-SYS-003 — 用户基础模型（C 端 + 后台读）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M1 §关键字段 / M7.7 用户管理
**关联拆解**: doc/02-需求拆解.md §2.1 第 204 行
**关联 mockup**: design/mockup/admin-c-user-list.html ⚠️ V1.0 设计冻结期 admin 走 ruoyi 默认 + plus-ui BizTable，不参考 mockup 视觉
**关联 ADR**: —（无相关 ADR）
**依赖**: GZ-SYS-002（schema 服务于登录落库 + 配合补 SYS-002 service DAO）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§1 微信登录 + 实名认证流** §状态机（gz_user 状态机即用户表生命周期）+ §4 会员中心占位流（涉及 admin 查 C 端用户）
- **字段表**：doc/11-字段权威表.md **§2.1 `gz_user` 用户主表**（完整 32 列字段定义 + DDL 来源 — 本 ticket 落 DDL 的权威依据）+ §1 全局公共字段（tenant_id / create_by / del_flag 等）
- **UI 参考**（设计冻结期）：
  - admin ticket：**N/A**（设计冻结期 admin 走 ruoyi 默认 + plus-ui BizTable，使用 element-plus 默认表格样式）
  - mp ticket：N/A（本 ticket 不涉及 mp UI）

## What

落地 `gz_user` 表 DDL + entity + mapper + Service；admin 端提供 C 端用户分页查询接口（只读，不修改），按 openId / 注册时间 / 最后登录时间筛选。

## AC（验收标准）

- [ ] **AC 1**：DDL 文件 `V202605281000__GZ-SYS-003-create-gz_user.sql` 在 `ruoyi-admin/src/main/resources/db/migration/`，字段严格按 doc/11 §2.1 落地（含 openid / unionid / session_key / nick_name / avatar_url / phone_num / status / registered_at / last_login_at + 全局公共字段 tenant_id/create_by/create_time/update_by/update_time/del_flag/remark），UNIQUE KEY `(tenant_id, openid)`，索引 `idx_unionid` / `idx_phone_num`
- [ ] **AC 2**：Entity `GzUser.java`（继承 `TenantEntity`）+ Mapper `GzUserMapper`（extends `BaseMapperPlus<GzUser, GzUserVO>`）+ Service `IGzUserService` / `GzUserServiceImpl`
- [ ] **AC 3**：admin 端 `GET /system/gz/user/list?openid=&start=&end=&pageNum=&pageSize=` 分页查询（sa-token user 权限 + `gz:user:list` perm）+ `GET /system/gz/user/{userId}` 详情；**不**提供 update / delete
- [ ] **AC 4**：SYS-002 `WxLoginServiceImpl` 落库逻辑切到真实 `IGzUserService.upsertByOpenid(...)`（替换 TODO mock 入库），mock 通道与真实通道走同一 service
- [ ] **AC 5**：Flyway 跑通后 `SHOW CREATE TABLE gz_user` 输出字段对齐 doc/11 §2.1（diff 0 字段差异）
- [ ] **AC 6**：admin 端用户管理页（plus-ui ruoyi 默认风格 BizTable）能查、能搜、能看详情；分页正常；空数据 friendly 提示
- [ ] **AC 7**：单测 `GzUserServiceImplTest` 至少 1 个 happy（upsert by openid 新增 + 二次更新）+ 1 个分页查询（按 openid 过滤）
- [ ] **AC 8**：mp 端登录后调 `/app/gz/common/me`（SYS-002 已建 controller 占位）返回当前用户基础信息（id / nick / avatar / phone / registered_at）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`
  - `controller/GzUserController.java`（admin 端，路径 `/system/gz/user`，`@SaCheckPermission("gz:user:list")`）
  - `controller/applet/MeController.java` 中加 `getMe()` 接口（mp 端，路径 `/app/gz/common/me`）
  - `domain/GzUser.java` + `domain/vo/GzUserVO.java` + `domain/bo/GzUserQueryBo.java`
  - `mapper/GzUserMapper.java`
  - `service/IGzUserService.java` + `service/impl/GzUserServiceImpl.java`
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V202605281000__GZ-SYS-003-create-gz_user.sql`
  - sys_menu 插入：admin 端「用户管理 → C 端用户列表」菜单（menu_id 5001-5010 段，参考 CLAUDE.md §6 #6 段划），`V202605281001__GZ-SYS-003-menu.sql`
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-common/user/index.vue`（plus-ui ruoyi 默认 BizTable，无自定义样式）
  - `api/gz-common/user.ts`（封装 list / getInfo）
  - `lang/zh_CN/gz-common.ts` + `en_US/gz-common.ts`（i18n key 加入）
- **小程序**：仅 `api/gz-common.ts` 加 `getMe()` 调用；`pages/me/index.vue` 暂不实装（GZ-USER-001 才做会员中心首页 UI）
- **测试**：单测 + 集成测试 mvn test -pl ruoyi-modules/ruoyi-gz-common -am

## 备注

### 强约束

1. **DDL 字段必须 1:1 对齐 doc/11 §2.1**（包含字段名 / 类型 / NOT NULL / DEFAULT / 注释 / 索引），任何不一致 → STOP 修 doc/11（CLAUDE.md §9.5 复盘优先级 #1：改源头 doc）
2. **UNIQUE 必含 tenant_id**（`uk_tenant_openid (tenant_id, openid)`）— CLAUDE.md §6 #3
3. **INSERT 不显式赋 tenant_id**（走 InjectionMetaObjectHandler 自动 — CLAUDE.md §6 #3）
4. **本 ticket admin 不实现修改用户资料**（doc/02 §2.1 第 211 行明确"不含修改用户资料"，甲方只看不改）
5. **OSS bucket 未就位时 avatar_url 仍存外链** — SYS-005 完工后由 SYS-005 内部决定是否做"微信外链 → OSS 镜像"（本 ticket 不做）
6. **menu_id 5001-5010 段**（CLAUDE.md §6 #6 GZ-SYS 段 5000-5999）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | gz_user 用独立表，不复用 sys_user | sys_user 是 ruoyi 后台管理员表（账号密码），与 C 端微信用户语义完全不同；混用会污染 sys_user 范式 |
| D2 | openid 用 VARCHAR(64) | 微信官方限制 ≤ 64 字符 |
| D3 | phone_num 用 VARCHAR(20) NULL | 拼豆预约（GZ-BEAN-004）才强收集，登录时可空 |
| D4 | session_key 落库不暴露给前端 | doc/10 §1.2 明确"session_key 仅后端用于解密手机号 / 加密敏感数据" |
| D5 | status 字段 enum (`'active'`/`'disabled'`) — 不做积分 / 等级 / 火花券（V1.1 用 ALTER 加）| doc/11 §2.1 V1.0 schema 不预留 V1.1 字段 |
| D6 | admin 查询不脱敏 openid（甲方运营需要全量看） | 合同 §6 数据隐私允许甲方运营看完整 openid（不是手机号 — 手机号需脱敏中间 4 位）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | Flyway baseline 时间戳冲突 | 命名严格 `V202605281000__` 起步，本日 SYS-003 / SYS-005 时间戳分别 1000 / 1100，留 99 个空位给 hot fix |
| R2 | gz_user 字段后续需要 ALTER（V1.1）→ 表已大可能影响在线 DDL | 接受：V1.0 上线初期数据量小（< 1k 用户预计），ALTER 风险可控 |
| R3 | sys_menu 插入冲突（已有 menu_id）| 落 SQL 前 `SELECT MAX(menu_id) FROM sys_menu` 确认，重 ID 时调到 5002 / 5003 |
| R4 | 「SYS-002 service DAO 真实化」要回头改 SYS-002 文件 | 接受：subagent 派 SYS-003 时显式扫 SYS-002 service 是否有 TODO 标记，按 TODO 把 mock 落库替换为真实 service 调用 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
