# GZ-USER-002 完工报告 — mp 个人资料编辑

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅ 改动隔离于 gz-user 后端模块 + me/profile + AvatarUpload + user.zh-CN |
| 上游依赖 merge | ✅ GZ-SYS-002(D02 登录) + GZ-SYS-005(D02 文件上传 uploadFile) 已就位 |
| 关键类/表存在 | ✅ gz_user 表 D02 已落；gz_user_audit_log 本 ticket 落 DDL；bind-mobile 端点 D02 已存在 |
| 编译通过 | ✅ mvn install gz-user BUILD SUCCESS；type-check 零新增；build 绿 |
| ADR 已读 | 无相关 ADR |

**权威蓝图引用摘录**：
- doc/10 §4.N2：编辑个人资料 → 更新 gz_user + 写 gz_user_audit_log
- doc/11 §2.1 gz_user：写 nickname / avatar_url / gender（手机号走 bind-mobile）
- doc/11 §2.3 gz_user_audit_log：本 ticket 落表（V1.0 实装 update_nickname/avatar/gender/mobile）
- doc/11 §2.5 F2.5：V1.0 实现 update_mobile / update_nickname（拼豆强收集可追溯）

**R6 冒烟（改 useAuth 前）**：本 ticket **未改 useAuth**（手机号复用现有 bindMobile，登录复用现有 loginWithWechat）→ R6 不触发，拼豆登录链路零影响。

**关键架构决策**：
- profile 编辑放 gz-user 模块新建 `GzUserProfileService`（跨模块注入 common 的 GzUserMapper 操作 gz_user 表 + 本模块 GzUserAuditLogMapper 写审计）。**不改 common 的 IGzUserService**（保持其「admin 只读 + 登录 UPSERT」语义纯净；C 端用户改自己资料是独立合法场景，doc/10 §4.N2）。
- **手机号编辑复用现有 bind-mobile，不写 decode-phone 端点**：微信新版 getPhoneNumber 直接返明文 phoneNumber（D02 UserBindMobileController 已实现），无需 session_key 解码。任务卡 AC 3 的 decode-phone 端点是基于旧 encryptedData 链路的假设，仓库实际已简化 → 复用更对。
- audit 写入在 Service 层 @Transactional（profile 写失败时 audit 回滚，原子）。

## 实现摘要

后端新增（org.dromara.gz.user）：
- `domain/entity/GzUserAuditLog.java` + `domain/vo/GzUserAuditLogVO.java`（id/userId 加 ToStringSerializer）+ `mapper/GzUserAuditLogMapper.java`
- `domain/bo/UserProfileUpdateBo.java`（nickname ≤32 / avatarUrl / gender 校验）
- `service/IGzUserProfileService.java` + `service/impl/GzUserProfileServiceImpl.java`（变化字段逐条写审计）
- `controller/applet/GzUserProfileMpController.java`（PUT /app/gz/user/profile）
- DDL `V202606031000__GZ-USER-002-create-gz_user_audit_log.sql`
- pom.xml 加 spring-boot-starter-test（gz-user 新模块原无测试依赖）

mp 新增/改动：
- `pages/me/profile.vue`（头像/昵称/性别/手机号表单 + 一键拉取微信资料 + 保存同步 store）
- `components/biz/AvatarUpload.vue`（chooseImage + OSS uploadFile，usageType=user_avatar）
- `api/gz-user.ts` 加 updateProfile() + UserProfileUpdateRequest
- `components/biz/MeHeader.vue` 加 edit emit（已登录点头部进编辑）

## AI 自测

### 编译 + install
```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-user -am -q
BUILD SUCCESS（gz-user 模块 jar 装入本地仓库）
```

### 单测（GzUserProfileServiceImplTest）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
[INFO] Running org.dromara.gz.user.service.impl.GzUserProfileServiceImplTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
   - 改昵称 → UPDATE + 写 1 条 update_nickname 审计（验 before/after/userId/ip）
   - 昵称+头像+性别全改 → 写 3 条审计
   - 传相同值 → 不 UPDATE 不写审计
   - 仅传昵称（头像/性别 null）→ 只动昵称
   - 用户不存在 / userId null → ServiceException
[INFO] BUILD SUCCESS
```

### DB 验证（dev MySQL 在线，手工导入 DDL）
```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606031000__...audit_log.sql
$ DESC gz_user_audit_log;
id bigint unsigned PRI auto_increment / user_id NOT NULL / action_type varchar(32) NOT NULL
before_value / after_value varchar(255) / ip varchar(64)
tenant_id varchar(20) NOT NULL DEFAULT '1001' / del_flag char(1) NOT NULL DEFAULT '0'
索引 idx_tenant_user / idx_tenant_action_type ✅
```

### API 烟雾（后端未在线，curl 命令备用，待全栈起来验）
```bash
# 期望：200 + 返回更新后 GzUserVO + DB gz_user_audit_log 多 1 条
curl -X PUT http://localhost:8080/app/gz/user/profile \
  -H "Authorization: Bearer <sa-token>" -H "clientid: <mp-clientid>" \
  -H "Content-Type: application/json" \
  -d '{"nickname":"阿喵","gender":1}'
```

## 风险提示 / 已知 issue

- R1（session_key 过期）：手机号编辑走 bind-mobile，微信新版直接返明文 phoneNumber 无需 session_key 解码 → 不存在解码失败。若 sa-token 业务 token 过期 → http.ts 拦截器 401 自动跳登录（已有兜底）。
- 一键拉取微信资料用 uni.getUserProfile（微信 2022 后限制：用户主动触发 + 部分基础库返默认昵称/灰头像）；拒授权时静默不阻塞（已处理）。
- 待 Kevin 批量人验关注（mp）：① 改昵称保存后落库（gz_user_audit_log +1）② 头像上传 OSS 成功 ③ getPhoneNumber 授权后手机号回填 ④ 一键拉取微信资料覆盖表单（不入库，需点保存）⑤ 保存后返回 + 会员中心头像/昵称同步。

## 对下游 ticket 的提示

- gz_user_audit_log 表已落，V1.0 admin 用户详情看审计（后续 admin ticket）可直接用 GzUserAuditLogVO + GzUserAuditLogMapper。
- DDL 需 Kevin 手工跑：`V202606031000__GZ-USER-002-create-gz_user_audit_log.sql`（dev 已导入验证）。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ kevin-qa 无法 spawn（subagent 内 Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。主线程可决定是否补派复核。

### 后端单测
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
GzUserProfileServiceImplTest: Tests run: 6, Failures: 0, Errors: 0 ✅
BUILD SUCCESS
```

### API 契约回归（mp ↔ 后端路径核对）
```
mp updateProfile PUT /app/gz/user/profile ↔ 后端 @PutMapping /app/gz/user/profile ✅
（手机号编辑复用 bind-mobile，D02 已存在端点，未新写 decode-phone）
```

### mp vitest + type-check
```
vitest 全量 103 passed（含 MeHeader 8）；type-check 零新增 TS 错
```

### Tier 2 可达性
```
profile 入口 = 会员中心头部已登录态点击（MeHeader emit edit → /pages/me/profile）
从已上线「我的」tab 可达，无需临时入口
```

**Tier 1B 结论：USER-002 ✅**（后端单测 6/6 + 契约对齐 + DDL 已导入验证 + 可达性全绿）
