# GZ-ADMIN-002 — 管理员账号 CRUD

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7.10 账号权限 + M7.11 操作日志
**关联拆解**: doc/02-需求拆解.md §2.6 第 564 行
**关联 mockup**: ⚠️ 缺口（待 designer 补 admin-users.html）— V1.0 设计冻结期改用 plus-ui BizTable + el-form 默认
**关联 ADR**: —
**依赖**: GZ-ADMIN-001 + GZ-SYS-006

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md M7.10 账号管理流（如有；本 ticket 复用 ruoyi sys_user CRUD，业务流即 ruoyi 范式）
- **字段表**：doc/11-字段权威表.md — 不新建表，仅消费 ruoyi 自带 sys_user + GZ-ADMIN-001 加的 `gz_store_id`
- **UI 参考**（设计冻结期）：admin ticket：**N/A**（plus-ui BizTable 默认风格，el-form 默认）

## What

admin 端「系统管理 → 谷子管理员」页 — owner 创建 / 编辑 / 禁用 / 重置 staff 账号；列表筛选 + 详情 + 操作日志写入。

## AC（验收标准）

- [ ] **AC 1**：admin 端 `views/gz-common/admin-user/index.vue` 列表页（plus-ui BizTable 默认，支持按 userName / status / gz_store_id 筛 + 分页）；可配关联门店下拉（V1.0 仅 1 个）
- [ ] **AC 2**：新建 / 编辑表单（el-form 默认）— 字段：userName / nickName / password（新建必填，编辑可选）/ role（owner/staff）/ gz_store_id / status / phoneNumber / email
- [ ] **AC 3**：禁用账号操作 = `status='1'`（ruoyi 范式 0 启用 / 1 禁用）+ 写操作日志
- [ ] **AC 4**：重置密码按钮（仅 owner 可见）→ 弹框输新密码 → 调 ruoyi `/system/user/resetPwd` → 写操作日志
- [ ] **AC 5**：staff 角色用户访问本页时 → 403（perm `gz:admin-user:list` 仅 owner 角色 sys_role_menu 配上）
- [ ] **AC 6**：删除走软删（ruoyi 自带 `del_flag='2'`），不物理删
- [ ] **AC 7**：所有写操作（新建/编辑/禁用/重置）@Log 注解写 sys_oper_log（SYS-006 同步落实 @Log 集成）

## Tech（端 + 范围）

- **后端**：**不写新 Controller**，复用 ruoyi 自带 `/system/user/*` 端点（list/add/edit/changeStatus/resetPwd）
  - 仅 sys_menu 插入：`谷子业务 → 谷子管理员` 菜单（menu_id 5050，parent=100 GZ-ADMIN-001 已建的目录）
  - DDL `V202605291100__GZ-ADMIN-002-menu.sql`
- **Admin**：`views/gz-common/admin-user/index.vue`（参考 dongjiaoshan `views/system/user/index.vue` 同款，但增加 gz_store_id 字段 + 角色限制为 owner/staff 2 选）+ `api/gz-common/admin-user.ts`（thin wrapper 调 ruoyi `/system/user/*`）+ i18n
- **测试**：mvn 跑通后浏览器实操：owner 登录 → 加 staff 账号 → staff 重新登录 → 看不到本页 → 写出 → 操作日志有记录

## 备注

### 强约束

1. **不重写 CRUD 端点**（ruoyi 已完备）— 仅做前端页 + 菜单挂载 + perm
2. **gz_store_id 在表单是下拉**（GZ-BEAN-001 完工后从门店列表拉取；本 ticket 实施时可能门店表还没建 — 下拉为空，仅在 BEAN-001 完工后回填）
3. **role 字段限定**：表单角色下拉只列 owner / staff 2 选（不让 owner 误把 staff 提升为 ruoyi 自带 admin）
4. **操作日志依赖 SYS-006**：本 ticket 全部写操作走 @Log 注解；@Log 是 ruoyi 自带 AOP，本 ticket 仅在 Controller 层补注解 — 但 ADMIN-002 不写自定义 Controller，因此实际 @Log 在 ruoyi 自带 `SysUserController` 已有

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 门店表未建时 gz_store_id 下拉空 | 接受：本 ticket 先做 UI + 菜单 + perm；BEAN-001 完工后下拉自动有数据 |
| R2 | ruoyi 自带 admin 账号被误删 | 表单"禁用 admin 账号"按钮加确认；上线前手动清理 |

---

## §revision（Kevin testing-human 后填，初始空）
