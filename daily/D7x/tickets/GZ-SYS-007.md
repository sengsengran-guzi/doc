# GZ-SYS-007 — mp 管理端权限底座（openid 绑定 sys_user + 登录加载 RBAC）

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md M7.10（主理人 + 店员两级权限）
**关联 ADR**: doc/_adr/0004-mp-admin-permission-foundation.md（**必读，本 ticket 是其落地**）
**依赖**: GZ-SYS-002（mp 微信登录，已交付）/ GZ-ADMIN-001（gz_owner/gz_staff sys_user + 角色，已交付）

> **实施状态（2026-06-01）**：AC1-AC8 已实现 + 自测通过（见 [reports/GZ-SYS-007.md](../reports/GZ-SYS-007.md)）。
> 为达「D7x 零 V1.1 推诿」追加两条完整性 AC（**AC9 停用自动踢 / AC10 owner 绑定管理**），与本批次一起做完，不留尾到 V1.1。

---

## 必读权威文档

- **业务流**：doc/10 §1 微信登录（LoginUser 装载点）；ADR-0004 §决策 1（绑定 + 加载机制）
- **字段表**：doc/11 §gz_user（加列 `staff_user_id`）
- **UI 参考**：mp 个人中心 `design/mockup/`（视觉参考，条件入口区不强求逐像素）；admin 绑定管理走 ruoyi 默认审美

## What

建 mp 管理端权限底座：C 端微信用户（gz_user.openid）可绑定到 ruoyi 店员账号（sys_user）；mp 登录时若已绑定，把该 sys_user 的角色 + 权限载入当前 app_user 会话，使 mp 管理端点能直接用标准 `@SaCheckPermission`。**不另造平行 RBAC**（ADR-0004 决策 1）。权限失效要彻底（停用/解绑即时踢），且 owner 能自助管理绑定（不靠 dev 跑 SQL）。

## AC（验收标准）

### 已实现（AC1-AC8，见 reports）

- [x] AC 1：`gz_user` 加列 `staff_user_id BIGINT NULL`（指向 sys_user.user_id，NULL=纯顾客）。迁移 `V202606051000__GZ-SYS-007-add-gz_user-staff_user_id.sql`。
- [x] AC 2：mp wx-login 建 app_user LoginUser 后，若 openid 对应 staff_user_id 非空 → 加载该 sys_user 的 rolePermission + menuPermission 到 LoginUser（复用 ruoyi 装载，不手写权限串），校验同租户(1001)+status 正常+未禁用，否则降级纯顾客。
- [x] AC 3：`GET /app/gz/staff/me` 返回 isStaff + perms，供 mp 个人中心条件渲染。
- [x] AC 4：mp 管理端点 `@SaCheckPermission("gz:xxx:yyy")`：绑定且有权限的店员可调；纯顾客/无权限 → 403。
- [x] AC 5：**解绑**（staff_user_id 置 NULL）后对应 mp token 管理权限即时失效（解绑后同 token 立即 401，已验证）。
- [x] AC 6：seed 绑定 `gz_staff_chengdu`(101) 的 openid（dev 已绑 gz_user id=1 → 101 验证）。
- [x] AC 7：个人中心条件入口——店员登录显示「门店管理」区块；纯顾客不显示。
- [x] AC 8：**Tier 2 入口可达** — 绑定店员账号登 mp → 个人中心可见「门店管理」区块。

### 完整性补充（AC9-AC10，本批次必做，不推 V1.1）

- [ ] AC 9：**停用 sys_user 即时踢 mp token（自动）**。现状仅提供 owner 手动 `POST /system/gz/staff/kickout/{staffUserId}` + 下次登录降级。补：在 admin「系统管理→用户管理」**停用/删除店员 sys_user 时自动触发**对应 mp token 踢出（监听 ruoyi 用户停用/删除事件或在停用入口挂钩，复用已就绪的 `kickoutByStaffUserId`）。验收：admin 停用 gz_staff → 该店员当前 mp token 立即失去管理权限（再调管理端点 401/403），无需手动调 kickout、无需等下次登录。给出实现 + raw output。
- [ ] AC 10：**owner 自助绑定管理**（admin 端）。owner 在 admin 新增「店员绑定管理」：按 openid / 手机号 / user_no 查 gz_user → 设/改/解其 `staff_user_id`（即指定某微信用户为某 sys_user 店员）。复用 `IMpStaffPermissionService`（绑定零新增逻辑，解绑/踢人已就绪），仅加查询 + set 端点 + 一个 admin 列表/操作页。验收：owner 不写 SQL 即可给一个微信用户绑/解店员身份，绑后该用户下次 mp 登录（或即时）获得权限，解后即时失效。perms 走 `gz:staff:binding:*`，仅 owner 角色。

## Tech（端 + 范围）

- **后端**：`ruoyi-gz-common`
  - 已落：`WxLoginServiceImpl` 登录加载 / `MpStaffPermissionServiceImpl`（resolve/kickout/unbind）/ `StaffMeController` / `GzStaffBindingController`(owner 解绑+踢人)
  - AC9：ruoyi sys_user 停用/删除挂钩（找 ruoyi `SysUserService` 停用/删除入口或事件，调 `kickoutByStaffUserId`）
  - AC10：`GzStaffBindingController` 补「查 gz_user + set staff_user_id」端点 + perms `gz:staff:binding:list/bind/unbind`；菜单 seed（menu_id 5000-5999 GZ-SYS 段，挂「谷子业务」或「系统管理」下）
- **Admin**：`plus-ui/src/views/gz-*/`（AC10 绑定管理页，走 ruoyi 默认 CRUD 风格）
- **测试**：补 AC9（停用→自动踢）/ AC10（绑定 set→生效、解绑→失效）单测 + 集成

## 备注

- ⚠️ AC9/AC10 是 ADR-0004 安全红线 + 客户可操作性的完整闭环：**没有 AC9，停用店员的 mp 权限不能即时收回（安全漏）；没有 AC10，客户加店员必须找 Kevin 跑 SQL（不可运营）**。故拉进本批次，不推 V1.1。
- 真正属 V1.1 的是「**更多 mp 管理功能**」（订单/物流/资讯管理下沉 mp）——那是新功能，不是本批次欠债；底座已让其边际成本 = 加一行 `@SaCheckPermission` + 授权，无需再动底座。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-SYS-007 revision 段 -->
