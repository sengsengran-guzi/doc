# GZ-ADMIN-001 — 管理员登录 + 账号 / 角色

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7.10 账号权限 / §关键字段 AdminUser
**关联拆解**: doc/02-需求拆解.md §2.6 第 550 行
**关联 mockup**: design/mockup/admin-login.html（V1.0 设计冻结期 admin 走 ruoyi 默认登录页，本 mockup 仅做布局参考）
**关联 ADR**: —
**依赖**: GZ-SYS-001 ✅

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §1 微信登录流 §合同 / PRD 引用（admin 与 mp 走两套登录，admin 复用 ruoyi sa-token user-client，mp 复用 mp-applet-client）
- **字段表**：doc/11-字段权威表.md — 本 ticket 不新建业务表，仅 ALTER ruoyi 自带 sys_user 加 `gz_store_id` + 插入 2 条 sys_role
- **UI 参考**（设计冻结期）：
  - admin ticket：**N/A**（ruoyi 默认登录页，mockup 仅作"该有登录页"的提醒）

## What

复用 ruoyi 自带 sa-token user-client 登录链路 + sys_user/sys_role/sys_menu 范式，建立 owner / staff 两级角色 + 关联门店字段；密码策略对齐 ruoyi 默认（≥8 位 + 大小写 + 数字 + 错误 5 次锁 30 分钟）。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202605291000__GZ-ADMIN-001-extend-sys-user.sql` 给 ruoyi 自带 `sys_user` 加 `gz_store_id BIGINT DEFAULT NULL COMMENT '关联门店 id（V1.0 单门店 default null=跨门店；staff 用户绑定具体门店）'` + 索引 `idx_gz_store`
- [ ] **AC 2**：DDL `V202605291001__GZ-ADMIN-001-seed-roles.sql` 插入 2 条 sys_role：`owner`（role_id=100, role_key=`owner`, role_sort=1）/ `staff`（role_id=101, role_key=`staff`, role_sort=2）；ruoyi 自带"超级管理员"role_id=1 / role_key=admin 保留作为开发兜底
- [ ] **AC 3**：插入种子 sys_user 2 条：`gz_owner` / `gz_owner123!`（绑 owner role + gz_store_id=null 跨门店）/ `gz_staff_chengdu` / `gz_staff123!`（绑 staff role + gz_store_id=门店主键 — 门店在 GZ-BEAN-001 落地，本 ticket 先 NULL，BEAN-001 完工后 ADMIN-002 UI 上配）
- [ ] **AC 4**：admin 登录走 ruoyi 自带 `/auth/login` 端点（无需新建 Controller）；前端 plus-ui 自带登录页样式不动（设计冻结期）
- [ ] **AC 5**：登录后 sa-token 颁发 user-client token，前端 axios 拦截器自动带；token 有效期 ruoyi 默认 2h + 自动续期
- [ ] **AC 6**：sys_menu 插入 menu_id 100 「谷子业务」一级目录（菜单类型 M 目录），后续 D 在此目录下挂业务菜单
- [ ] **AC 7**：单测可选（复用 ruoyi 范式，已有充分覆盖）

## Tech（端 + 范围）

- **后端**：仅 DDL，**不写 Java 代码**（完全复用 ruoyi 自带 sys_user / sys_role / SaTokenConfigure / AuthController）
  - DDL × 3 文件：
    - `V202605291000__GZ-ADMIN-001-extend-sys-user.sql`（ALTER sys_user）
    - `V202605291001__GZ-ADMIN-001-seed-roles.sql`（INSERT sys_role + sys_role_menu）
    - `V202605291002__GZ-ADMIN-001-seed-admin-users.sql`（INSERT sys_user 2 条种子账号，密码 BCrypt hash 提前用 dongjiaoshan 同款盐生成）
  - 密码 hash 工具：参考 dongjiaoshan `code/main/RuoYi-Vue-Plus/script/sql/djs/_password-gen.sh`（如存在）或 ruoyi 自带 `BCrypt.hashpw("gz_owner123!", BCrypt.gensalt())` 单元方法跑一次拿到值
- **Admin**：**完全不动 plus-ui 登录代码**（ruoyi 自带 LoginForm.vue）
- **测试**：mvn 启动 ruoyi-admin + 浏览器 http://localhost:8080 用种子账号 gz_owner / gz_owner123! 登录验证

## 备注

### 强约束

1. **不重写 ruoyi 登录链路**（认证 / 鉴权 / sa-token 全部复用），仅做数据层 seed
2. **owner / staff role_id 固定 100 / 101**（避免 ruoyi 自带 role_id 1/2 冲突，留 3-99 给 ruoyi 默认扩展）
3. **密码必须 hash**（不允许明文密码进 SQL）— BCrypt 标准 10 cost
4. **不要把 admin/admin123 删了**（上线前才删，开发期保留兜底访问）
5. **ALTER sys_user 不要加 NOT NULL**（已有数据兼容性 — ruoyi admin user 已存在）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 不新建 gz_admin_user 表 | sys_user 已是 ruoyi 范式核心，新建表会污染所有权限模型；扩字段是 dongjiaoshan 同款做法 |
| D2 | owner role_id=100 而非靠 ruoyi 自动生成 | 跨环境（dev/staging/prod）角色 ID 一致，便于权限分配脚本复用 |
| D3 | staff 用户 gz_store_id NULL 占位 | 拼豆 BEAN-001 落地门店后 ADMIN-002 UI 上配；不要在本 ticket 强约束 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | BCrypt hash 在不同环境/JDK 版本下行为不一致 | 用 dongjiaoshan 验证过的范式（BCrypt 标准库 + cost=10）|
| R2 | sys_user ALTER 在线 DDL 锁表 | dev 阶段无数据 + 后续 ALTER 量小，接受；prod 上线前 sys_user 已稳定，ALTER 在 V1.0 部署窗口完成 |

---

## §revision（Kevin testing-human 后填，初始空）
