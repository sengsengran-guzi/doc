# GZ-ADMIN-004 — 后台路由 / 布局 / 侧边栏

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7 §模块清单（基础布局承载所有子模块）
**关联拆解**: doc/02-需求拆解.md §2.6 第 592 行
**关联 mockup**: 所有 admin-*.html 共享布局（V1.0 设计冻结期走 ruoyi 默认）
**关联 ADR**: —
**依赖**: GZ-ADMIN-001

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md — 本 ticket 是 UI 框架，无核心业务流
- **字段表**：doc/11-字段权威表.md — 本 ticket 不落 DDL
- **UI 参考**（设计冻结期）：admin ticket：**N/A**（plus-ui 自带布局 = ruoyi 默认 sidebar/topbar/breadcrumb）

## What

复用 plus-ui 自带布局（Layout.vue / Sidebar / Navbar / Breadcrumb），仅做菜单结构 seed + 角色 perm 映射 + 顶部门店切换占位组件；详情页隐藏底部 5 tab 用 fixed CTA 条等约束已被 mockup 锚定。

## AC（验收标准）

- [ ] **AC 1**：sys_menu 整体结构 seed `V202605291200__GZ-ADMIN-004-menu-structure.sql`，建立完整菜单树（一级目录 4 个 + 二级菜单为各域占位，业务菜单后续 ticket 各自插入）：
  - 100 谷子业务（目录）
  - 200 系统管理（已存在 ruoyi 自带 1 — 复用，不动）
  - 300 数据看板（目录，业务菜单 ADMIN-003 落地）
  - 400 操作日志（已存在 ruoyi 自带 — 复用，不动）
- [ ] **AC 2**：sys_role_menu 配置 owner / staff perm 映射：
  - owner role_id=100 → 所有 menu_id（含 ruoyi 自带 + 100/200/300）
  - staff role_id=101 → 仅业务菜单（100 + 子级）+ 部分 ruoyi 系统（不含管理员账号管理）
- [ ] **AC 3**：plus-ui topbar 加自定义组件 `<StoreSelector>`（V1.0 单门店但保留组件，从 D04 BEAN-001 完工后从 gz_bean_store 表拉门店选项），位置在 nav-bar 右侧用户头像左边
- [ ] **AC 4**：plus-ui sidebar 自动按 sys_menu 动态生成（ruoyi 自带行为，本 ticket 仅 seed 数据）
- [ ] **AC 5**：面包屑走 ruoyi 自带 Breadcrumb 组件
- [ ] **AC 6**：登录后默认跳转「谷子业务 → 谷子管理员」（仅 owner）/「谷子业务 → C 端用户」（staff）— 配 sys_menu `is_default_path` 或前端 router-guard 实现
- [ ] **AC 7**：i18n 加 `route.gz.xxx` 系列 key（zh-CN + en-US）

## Tech（端 + 范围）

- **后端**：仅 DDL（菜单 + perm seed）— 不写 Java
  - `V202605291200__GZ-ADMIN-004-menu-structure.sql`
  - `V202605291201__GZ-ADMIN-004-role-menu-mapping.sql`
- **Admin**：
  - `views/components/StoreSelector.vue`（顶部门店切换器 — V1.0 单门店时仅展示"成都拼豆店"不可切；多门店预留）
  - `layout/components/Navbar/index.vue` 中挂载 StoreSelector（参考 dongjiaoshan 同款 patch 位置）
  - `lang/zh_CN/route.ts` + `en_US/route.ts`（菜单 i18n）
  - `store/modules/permission.ts`（默认路由跳转配置 — 按角色不同）
- **测试**：浏览器实操：用 owner 登录看到所有菜单 + 默认跳到管理员；切到 staff 登录看到子集菜单 + 默认跳到 C 端用户

## 备注

### 强约束

1. **不重写 Layout.vue**（plus-ui 自带已完备）— 仅在 Navbar 加 StoreSelector 一个组件
2. **菜单 seed 不要 INSERT 重复 menu_id**（落 SQL 前 `SELECT MAX(menu_id) FROM sys_menu` + 检查 100/200/300/400 不冲突 — 已知 ruoyi 自带 1=系统管理，2=系统监控，11=系统工具，100+ 应该空闲）
3. **sys_role_menu 配置粒度到 menu_id**（不要按 perm_key 间接配 — ruoyi 范式按 menu_id 直配）
4. **default_path 实现走前端 router-guard**（不动 sys_menu schema）— 在 `router/permission.ts` 登录后回调里判断角色

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | StoreSelector 在 BEAN-001 完工前空数据 | 接受：V1.0 单门店写死显示"成都拼豆店"硬编码占位（i18n 字符串），BEAN-001 完工后切真实数据源 |
| R2 | menu_id 100/200/300 冲突 ruoyi 自带 | 落 SQL 前查；冲突时跳到 110/210/310 |
| R3 | sys_role_menu 配置量大（50+ 行 INSERT）| 用 SQL 多行 VALUES，不要逐行 INSERT |

---

## §revision（Kevin testing-human 后填，初始空）
