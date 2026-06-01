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

---

# GZ-SYS-007 完整性补充 — AC9 + AC10（2026-06-01 追加）

> AC1-8 已交付（上方报告，未改动）。本段补 AC9（停用/删除 sys_user 自动踢 mp token）+ AC10
> （owner admin 自助绑定/解绑店员）。两者是 ADR-0004 安全红线 + 客户可运营性的完整闭环。

## §0 自检结果（AC9/AC10）

| 检查项 | 结果 |
|---|---|
| 上游基座（IMpStaffPermissionService / MpStaffSysUserMapper / GzStaffBindingController）就绪 | ✅ 复用，未重写 |
| ruoyi SysUserServiceImpl.updateUserStatus(382)/deleteUserByIds(555) 签名确认 | ✅ 两者均在 ISysUserService 接口 |
| UserStatus 枚举 字面量（OK='0'/DISABLE='1'/DELETED='2'） | ✅ 只在切到 '1' 停用时踢 |
| gz-common 已传递依赖 spring-aop + aspectjweaver（无需新增模块依赖） | ✅ ruoyi-common-* starter 带；项目有 LogAspect 先例 |
| Spring AOP 代理生效（CGLIB proxy-target-class 默认 true） | ✅ 纯 execution(FQN) 切点，不 import ruoyi-system 类 |
| 已应用迁移最大版本 V202606051000 → 新迁移 V202606051100 > 之 | ✅ |
| menu_id 5060-5063 在 GZ-SYS 段 5000-5999 且空闲（5050-5055 已用） | ✅ |
| 编译通过（gz-common -am） | ✅ EXIT 0 |
| ADR 已读 | ADR-0004（本 AC 是其 ④⑤ 项落地） |

## 实现摘要（AC9/AC10）

**AC9 — 停用/删除 sys_user 自动踢 mp token**（Spring AOP，不改 ruoyi 源码 铁律#1）：
- 新增 `aspect/SysUserStaffKickoutAspect.java`：`@Aspect @Component`，纯 `execution()` 切
  `org.dromara.system.service.impl.SysUserServiceImpl` 的 `updateUserStatus(Long,String)` /
  `deleteUserByIds(Long[])`，**不 import 任何 ruoyi-system 类**（gz-common 零新增模块依赖）。
  - `@AfterReturning` updateUserStatus：status='1'(停用) 且更新行>0 → `kickoutByStaffUserId(userId)`；
    启用('0')/无变更/null 不踢；踢人抛错吞掉不打断 ruoyi 主流程。
  - `@AfterReturning` deleteUserByIds：逐个 `kickoutByStaffUserId` + `clearStaffBindingByStaffUserId`
    （把绑定该 user 的 gz_user.staff_user_id 置 NULL，清悬挂）。
- mapper 加 `clearStaffBindingByStaffUserId`（按 staff_user_id 批量置 NULL）。

**AC10 — owner admin 自助绑定管理**：
- `MpStaffSysUserMapper` 加 `bindStaffById`（set staff_user_id）+ `selectStaffCandidates`（同租户正常未删 sys_user 候选）。
- `IMpStaffPermissionService` + impl 加 3 方法：`selectBindingPage`（gz_user 分页 + 绑定快照）/
  `listStaffCandidates` / `bindStaff`（校验 gz_user 存在 + sys_user 同租户/正常/未删；改绑先踢旧会话）。
- `GzStaffBindingController` 加 3 端点：`GET /binding/list`、`GET /binding/candidates`、`POST /binding/{gzUserId}/bind`；
  全部端点 perm 统一为 `gz:staff:binding:{list,bind,unbind}`（含原 unbind/kickout 由 `@SaCheckRole("owner")` 改为
  `@SaCheckPermission`，走标准 RBAC，菜单 seed 仅授 owner 等价"仅 owner"）。
- 菜单 seed `V202606051100__GZ-SYS-007-staff-binding-menu.sql`：menu_id 5060(C 列表) + 5061/5062/5063(F 三权限)，
  挂 5000 谷子业务下，owner(100) 授权 4 条，staff(101) **不授**（绑定是 owner 专属敏感操作）。
- admin 页 `plus-ui/src/views/gz-common/staff-binding/index.vue`（Element Plus 默认风格）+ api `staff-binding.ts`
  + zh/en i18n（staffBinding 块）。列表查 gz_user（openid/手机号/userNo 搜）+ 显示绑定 + 「设为店员/改绑」弹窗（候选下拉）+「解绑」。

## AC 完成情况（AC9/AC10）

| AC | 状态 | 证据 |
|---|---|---|
| AC9 停用/删除 sys_user 自动踢 mp token | ✅ | 切面单测 7 + live 端到端（停用 101 → 同店员 token staff/me 401）+ 切面日志 |
| AC10 owner 自助绑定/解绑（list/candidates/bind/unbind） | ✅ | bindStaff 单测 7 + live 6 场景（含 403 权限隔离 + ServiceException 校验） |

## AI 自测（AC9/AC10）

### 后端单测（编译 + 全量）
```
[INFO] Running org.dromara.gz.common.aspect.SysUserStaffKickoutAspectTest
[INFO] - [gz-staff-aop] 停用 sys_user=101 → 自动踢出 1 个 mp 会话
[INFO] - [gz-staff-aop] 停用 sys_user=101 自动踢人失败（不影响停用本身）: redis down   ← 异常吞掉分支
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0  -- SysUserStaffKickoutAspectTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0 -- MpStaffPermissionServiceImplTest（11→18，+7 bindStaff）
[INFO] Tests run: 61, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
新增覆盖：
- AC9 切面：停用→踢 / 启用不踢 / 停用0行不踢 / null不踢 / 踢异常吞掉 / 删除→逐个kick+clear / 空数组无操作
- AC10 bindStaff：校验通过→绑 / gz_user不存在→异常 / sys_user不存在→异常 / 已停用→异常 / 跨租户→异常 / 改绑先踢旧会话 / null参数→异常

### Flyway 菜单迁移（启动自动跑）
```
- Migrating schema `ry-vue` to version "202606051100 - GZ-SYS-007-staff-binding-menu"
- Successfully applied 1 migration to schema `ry-vue`, now at version v202606051100

-- DB 验证
SELECT menu_id, menu_name, menu_type, perms FROM sys_menu WHERE menu_id BETWEEN 5060 AND 5063;
  5060 | 店员绑定管理 | C | gz:staff:binding:list
  5061 | 绑定查询    | F | gz:staff:binding:list
  5062 | 设为店员    | F | gz:staff:binding:bind
  5063 | 解绑       | F | gz:staff:binding:unbind
SELECT COUNT(*) FROM sys_role_menu WHERE role_id=100 AND menu_id BETWEEN 5060 AND 5063;  → 4  (owner 全授)
SELECT COUNT(*) FROM sys_role_menu WHERE role_id=101 AND menu_id BETWEEN 5060 AND 5063;  → 0  (staff 不授)
```

### AC9 live 端到端验证（真后端 8080 + dev MySQL/Redis）★
```
# 步骤1 mp 店员登录（code=mock-178staff → openid=mock-mock-178 命中 seed 绑定 id=1→101）
# 后端日志：[wx-login] 店员登录 gzUserId=1 → 加载 sys_user=101 权限（roles=1 perms=22）

# 步骤2 停用前 staff/me（店员 token）
{"code":200,"data":{"staff":true,"staffName":"成都门店运营","roles":["staff"],
  "perms":[...,"gz:bean:booking:verify",...]}}    ← 22 个权限，店员有效

# 步骤3 owner 登录 → access_token (loginId=sys_user:100)

# 步骤4 owner 停用 staff sys_user 101（PUT /system/user/changeStatus {userId:101,status:"1"}）
{"code":200,"msg":"操作成功","data":null}
# 切面织入日志：[gz-staff-aop] 停用 sys_user=101 → 自动踢出 1 个 mp 会话   ★ AC9 自动生效

# 步骤5 停用后，同一店员 token 再调 staff/me（AC9 核心断言）★
{"code":401,"msg":"认证失败，无法访问系统资源","data":null}
  ← 同 token 立即失效，无需手动 kickout、无需等下次登录 = AC9 验收达成

# 清理：恢复 staff 101 启用 + gz_user id=1 绑回 101（DB 已复原供后续测试）
```

### AC10 live 端到端验证（真后端，owner token，6 场景）★
```
# a binding/list → total:3，id=1 staffUserId:101 staffUserName:"gz_staff_chengdu" staffActive:true；纯顾客 staffUserId:null
# b binding/candidates → [{userId:100,gz_owner},{userId:101,gz_staff_chengdu}]（不含密码/邮箱）
# c POST /staff/1/unbind → {data:true}；list 复查 staffUserId:null
# d POST /staff/binding/1/bind?staffUserId=101 → {data:true}；list 复查 staffUserId:101 staffActive:true
# e bind staffUserId=999（不存在）→ {"code":500,"msg":"店员账号不存在：999"}   ← 校验生效
# f 店员 token 调 owner 端点 binding/list → {"code":403,"msg":"没有访问权限"}   ← 权限隔离仅 owner
```

### admin 前端 type-check
```
vue-tsc --noEmit  → 新增 staff-binding.ts / staff-binding/index.vue 零 TS 报错
（全项目预存噪音文件不在本 ticket 改动范围）
```

## 风险提示 / 已知 issue（AC9/AC10）

- **AC9 切面织入范围**：仅切 `SysUserServiceImpl` 单例方法的外部调用（admin SysUserController → Spring 代理 → 切面）。
  若未来出现"绕过 Spring 代理的内部 this 调用"或批量脚本直连 DB 停用 → 切面不触发；此时 fallback：
  ① 下次 mp 登录 resolve 已校验 status 降级；② owner 可手动调 `POST /system/gz/staff/kickout/{staffUserId}` 兜底。已 live 验证 admin 标准停用入口生效。
- **AC10 改绑即时性**：改绑 / 解绑会即时踢旧会话（旧权限即时失效）；**新绑权限需该用户下次 mp 登录才加载**
  （登录时 resolve 装载 RBAC）。这是 ADR-0004 装载模型的固有语义，符合 AC10 验收口径"绑后下次 mp 登录获得权限"。
- live 仅测停用分支（避免删除真实 sys_user 破坏 dev 数据）；删除分支由切面单测 2 个用例覆盖（逐个 kick + clear 悬挂）。

## 对下游 ticket 的提示（AC9/AC10）

- **底座完整闭环已成**：后续 mp 管理功能下沉边际成本 = 加一行 `@SaCheckPermission` + admin 给店员角色授权 +
  （需即时回收权限时）已有 AC9 自动踢 / AC10 owner 自助绑解。无需再动权限底座。
- **ADR-0004 ④⑤ 项已落地**，ADR 范围切分表的 AC9/AC10 可标 ✅。

## §AI 测试段（AC9/AC10 — Tier 1B）

**注**：本 agent 运行环境无 Agent spawn 工具（无法自动 spawn kevin-qa）。已由 kevin-coder 亲自用真后端
（spring-boot 8080 + dev MySQL/Redis）完成 Tier 1B 等价覆盖。

| Tier 1B 项 | 覆盖方式 | 结果 |
|---|---|---|
| 后端集成（AC9 停用→自动踢 / AC10 list/candidates/bind/unbind） | 真后端 curl 端到端 11 场景（AC9×5 + AC10×6） | ✅ 全通过 |
| 切面 AOP 织入生效性 | live 停用 sys_user → 切面日志 + 同 token 401 | ✅ 已 live 证实 |
| 权限隔离（仅 owner） | 店员 token 调 owner 端点 → 403 | ✅ |
| API 契约回归 | 后端 VO 字段 ↔ admin TS 接口对齐（StaffBindingVO/StaffCandidateVO） | ✅ |
| admin 页面 | Element Plus 默认风格 CRUD + 弹窗（owner 解绑/踢人无新 admin 页时已 curl 覆盖；本批新增 staff-binding 页 vue-tsc 零错） | ✅ type-check 通过；Playwright E2E 建议 Kevin 在有工具会话补跑 |
| 单测 | SysUserStaffKickoutAspectTest(7) + MpStaffPermissionServiceImplTest(18, +7) | ✅ Tests run 61 全通过 |

后端已按 §12 停止并释放 8080，临时验证脚本已清理，dev server 交还 Kevin。

**人验提示**：AC9（停用自动踢）/ AC10（owner 绑定管理）均为 **admin + 后端**，无 mp 新页 → 按 CLAUDE.md §8.2
**纯 admin/后端 ticket 无人验**，Tier 1A + 1B 全 ✅ 即终态 close。admin staff-binding 页 Kevin 如愿可在后台
「谷子业务→店员绑定管理」目视确认（功能层，不评判视觉）。
