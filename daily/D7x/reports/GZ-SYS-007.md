# GZ-SYS-007 完工报告 — mp 管理端权限底座

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游依赖 GZ-SYS-002(微信登录)/GZ-ADMIN-001(gz_owner/staff sys_user) | ✅ 已交付 |
| 关键类存在（WxLoginServiceImpl / GzUser / SaPermissionImpl / PermissionService） | ✅ |
| gz_user.staff_user_id 列 | 实现前不存在 → 本 ticket 加列 ✅ |
| 编译通过（gz-common -am） | ✅ EXIT 0 |
| ADR 已读 | ADR-0004（本 ticket 是其落地） |
| 已应用迁移最大版本 | V202606041600 → 新迁移 V202606051000 > 之 ✅ |

### 权威蓝图引用摘录（§0 强制）

- **doc/10 §1 N4-N6**：微信登录 LoginUser 装载点 — issueToken 建 app_user LoginUser；本 ticket 在此注入店员权限。
- **doc/11 §2.1 gz_user**：加列 `staff_user_id`，IDX(tenant_id, staff_user_id)。
- **ADR-0004 决策 1**：openid 绑定 sys_user + 登录加载 ruoyi RBAC，不另造平行 RBAC。安全红线：禁用/解绑即时踢 token。

### sa-token 权限装载链路验证结论（实现前小样验证，备注要求）

读源码确认（无需运行验证，逻辑确定）：
- `ruoyi-common-satoken/SaPermissionImpl#getPermissionList` 第 43 行：对**当前 token 的 LoginUser 不区分 userType**，直接 `return loginUser.getMenuPermission()`；APP_USER 分支（第 40 行）是空的「自行根据业务编写」。
- **结论**：只要 mp 登录时把 menuPermission/rolePermission 装进 APP_USER 的 LoginUser，`@SaCheckPermission` 在 mp 端点直接生效，**无需改 ruoyi 源码**。
- 权限真源 = `ruoyi-common-core` SPI `PermissionService`（运行时注入 `SysPermissionServiceImpl`）。gz-common 已依赖 ruoyi-common-core，**零新增模块依赖**，与 admin `SysLoginService#buildLoginUser` 同一加载入口（`getMenuPermission`/`getRolePermission`）。
- 集成层已端到端复核（见下「AC4/AC5 集成验证」），结论与源码分析一致。

## 实现摘要

改动文件：
- **迁移**：`ruoyi-admin/.../db/migration/V202606051000__GZ-SYS-007-add-gz_user-staff_user_id.sql`（加列 + IDX + seed 绑定 gz_staff_chengdu(101) 到现有 mp 用户 id=1）
- **gz-common 新增**：
  - `domain/dto/MpStaffPermission.java`（权限载荷 DTO）
  - `domain/dto/StaffSysUserCheck.java`（sys_user 校验快照）
  - `domain/vo/StaffMeVO.java`（staff/me 响应，不暴露 staffUserId）
  - `mapper/MpStaffSysUserMapper.java`（只读直查 sys_user + 反查/解绑 gz_user，@InterceptorIgnore 旁路 tenant）
  - `service/IMpStaffPermissionService.java` + `impl/MpStaffPermissionServiceImpl.java`（底座核心：resolve 加载 / kickout / unbind）
  - `controller/applet/StaffMeController.java`（GET /app/gz/staff/me）
  - `controller/GzStaffBindingController.java`（admin owner 解绑 + 踢人，AC5 可验证手段）
- **gz-common 改动**：
  - `domain/entity/GzUser.java`（加 staffUserId 字段）
  - `service/impl/WxLoginServiceImpl.java`（issueToken 条件装载店员权限）
- **mp 新增**：`api/gz-staff.ts` / `hooks/useStaff.ts`
- **mp 改动**：`pages/me/index.vue`（门店管理区块条件渲染）/ `locale/user.zh-CN.ts`（管理区文案）
- **单测**：`MpStaffPermissionServiceImplTest`（11）/ 修 `WxLoginServiceImplTest`（构造加参 + resolve stub）/ mp `gz-staff.test.ts`（4）/ `useStaff.test.ts`（4）

## AC 完成情况

| AC | 状态 | 证据 |
|---|---|---|
| AC1 gz_user 加列 staff_user_id | ✅ | DDL 验证 SHOW COLUMNS 见下 |
| AC2 登录加载绑定 RBAC + 同租户/未禁用/未软删校验 | ✅ | 单测 5 分支 + curl staff/me staff=true |
| AC3 提供 isStaff+perms 服务（GET /app/gz/staff/me） | ✅ | curl 返回 staff/staffName/roles/perms |
| AC4 @SaCheckPermission 放行店员 / 403 纯顾客 | ✅ | curl 店员过拦截 / 纯顾客 403 |
| AC5 安全红线：禁用/解绑即时失效（踢 token） | ✅ | 解绑后同 token 立即 401（见 AC5 集成验证）|
| AC6 seed 绑定 gz_staff_chengdu(101) | ✅ | DB id=1 staff_user_id=101 |
| AC7 个人中心条件「管理」区块 | ✅ | me/index.vue v-if=isStaff + useStaff hook |
| AC8 Tier2 可达 | ✅ | 「我的」tab(已上线)→门店管理区→扫码核销（无需临时入口）|

## AI 自测

### 编译
```
mvn compile -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-bean -am -q
=== COMPILE EXIT 0 ===   （无错误输出）
```

### 后端单测
```
Tests run: 4, ... WxLoginServiceImplTest
Tests run: 8, ... GzUserServiceImplTest
Tests run: 11, ... MpStaffPermissionServiceImplTest
Tests run: 23, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

MpStaffPermissionServiceImplTest 覆盖：
- 绑定店员 + 同租户 + 正常 + 未软删 → 加载 RBAC（staff=true）
- 纯顾客（staff_user_id=null）→ 空载荷（不查 sys_user）
- 降级分支：sys_user 不存在 / 已软删 / 已停用 / 跨租户 → 均降级纯顾客
- kickoutByStaffUserId → 反查 gz_user 逐个 StpUtil.logout
- unbindStaffAndKickout → 置 NULL + 踢；本就非店员 → false 无操作
```

### mp 单测
```
✓ src/api/gz-staff.test.ts (4 tests)
✓ src/hooks/useStaff.test.ts (4 tests)   （含「拉取失败→保守降级纯顾客」console.warn 为预期）
Test Files  3 passed (3) / Tests 23 passed (23)   （含 gz-bean 15，BEAN-011 共用）
全量 vitest：Test Files 15 passed / Tests 103 passed（未破坏现有）
```

### DDL + seed 验证（Flyway 启动自动跑）
```
Flyway: Migrating schema ry-vue to version "202606051000 - GZ-SYS-007-add-gz user-staff user id"
        Successfully applied 2 migrations, now at version v202606051000

SHOW COLUMNS FROM gz_user LIKE 'staff_user_id';
  staff_user_id | bigint | YES | NULL          ← 加列成功

SELECT id, staff_user_id, tenant_id FROM gz_user;
  1 | 101 | 1001                                ← seed 绑定成功（gz_staff_chengdu）

SHOW INDEX ... idx_gz_user_staff_user_id        ← (tenant_id, staff_user_id) 索引建好
```

### AC2/AC3/AC4 集成验证（curl，真后端 8080）
```
# 店员登录（openid mock-mock-178 命中 seed 绑定用户 id=1）→ loginId=app_user:1
POST /app/gz/common/auth/wx-login {"code":"mock-178staff"}
  → 200 token（JWT loginId=app_user:1, tenant 1001）

# AC3 + AC2：staff/me 返回店员身份 + RBAC 权限集
GET /app/gz/staff/me  (Bearer 店员 token)
  → {"staff":true,"staffName":"成都门店运营","roles":["staff"],
     "perms":[...,"gz:bean:booking:verify",...]}    ← 权限装载链路工作

# AC4：纯顾客 token 调管理端点 → 403
POST /app/gz/bean/booking/verify-scan (Bearer 纯顾客 token)
  → {"code":403,"msg":"没有访问权限，请联系管理员授权"}
GET /app/gz/staff/me (纯顾客) → {"staff":false,"roles":[],"perms":[]}
```

### AC5 安全红线集成验证（解绑即时失效，端到端）
```
# ① 解绑前：店员 token 有效
GET /app/gz/staff/me (店员 token) → staff:true

# ② owner 解绑（owner password 登录 → loginId=sys_user:100）
POST /system/gz/staff/1/unbind (Bearer owner token) → {"code":200,"data":true}

# ③ 解绑后：同一店员 token 立即失效（不靠下次登录）★
GET /app/gz/staff/me (同一店员 token) → {"code":401,"msg":"认证失败，无法访问系统资源"}
POST /app/gz/bean/booking/verify-scan (同一店员 token) → 401

# ④ DB staff_user_id 已置 NULL
SELECT staff_user_id FROM gz_user WHERE id=1 → NULL

（验证后已恢复 seed 绑定 id=1→101，供后续测试 + Kevin 人验）
```

## 风险提示 / 已知 issue

- **ruoyi 后台直接停用 sys_user 的即时性**：在「系统管理→用户管理」停用某店员 sys_user 时，ruoyi 原生不会自动踢已登录 mp token。本 ticket 提供 `POST /system/gz/staff/kickout/{staffUserId}` 由 owner 停用后手动踢（fallback：停用后下次 mp 登录 resolve 已校验 status 降级纯顾客）。**完整自动钩子（监听 sys_user 停用事件自动踢）属 V1.1 加固**，已在 ADR-0004 范围切分声明。
- **type-check 噪音**（非本 ticket 引入）：`BizCustomerServiceFab.vue` / `login/index.vue` 各 1 处预存 TS 错误，本 ticket 改动文件 TS 干净。建议后续单独 ticket 清。
- mp 端 unibest 内置 store 把 userId 存为 number（useAuth loginToBackend），与跨层契约 ID=string 有张力；V1.0 用户量 << 2^53 安全，已有注释说明。本 ticket 未触碰。

## 对下游 ticket 的提示

- **GZ-BEAN-011（本批次后做）**：mp verify-scan 端点已能复用本底座的权限装载（curl 已验证店员可调、纯顾客 403）。
- **V1.1 admin 自助绑定 UI**：owner 给微信号分店员身份 — 复用 `IMpStaffPermissionService`，新增"按 openid/手机号查 gz_user → set staff_user_id"端点即可（绑定逻辑零新增，解绑/踢人已就绪）。
- **V1.1 更多 mp 管理功能**：边际成本 = 加一行 `@SaCheckPermission("gz:xxx:yyy")` + 在 admin 给店员角色授该权限；前端 `useStaff().hasPerm('gz:xxx:yyy')` 控入口显隐。

## §AI 测试段（Tier 1B）

**注**：当前 kevin-coder 运行环境无 Agent spawn 工具，无法自动 spawn kevin-qa subagent。已由 kevin-coder
亲自用真后端（spring-boot 8080 + dev MySQL/Redis）完成 Tier 1B 等价覆盖（后端集成 + API 契约回归 +
mp vitest），结果如下；建议 Kevin 在有 Agent 工具的会话补跑一次 kevin-qa 形式化确认。

| Tier 1B 项 | 覆盖方式 | 结果 |
|---|---|---|
| 后端集成（登录加载权限 → 端点放行/403 → 解绑即时失效） | 真后端 curl 端到端 7 场景 | ✅ 全通过（见上 AC2/AC4/AC5 集成验证）|
| admin Playwright E2E | 本批次 admin 仅新增 owner 解绑/踢人端点（无新 admin 页面）→ owner password 登录 curl 覆盖 | ✅ 解绑 data:true |
| API 契约回归 | mp gz-staff/gz-bean API 单测 + 后端 staff/me / verify-scan 响应结构核对 | ✅ |
| mp vitest unit | 全量 15 文件 103 测试 + 本 ticket 新增 useStaff(4)/gz-staff(4) | ✅ 全通过 |
| 入口可达性 | me tab → 门店管理区（useStaff 条件渲染），无需临时入口 | ✅ |

后端已按 §12 停止并释放 8080，dev server 交还 Kevin。
