# GZ-ORD-110 — 预购下线（屏蔽 admin + mp 入口，代码/表/视图全保留）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M3 §V1.2 定位调整（屏蔽入口保留代码）
**关联拆解**: doc/02-需求拆解.md §3.6.1 GZ-ORD-110 预购下线（屏蔽入口，保留代码）
**关联 mockup**: —（纯入口屏蔽，无新页面）
**关联 ADR**: —
**依赖**: 无（GZ-ORD-104 预购订单 + GZ-ADMIN-103 订单聚合 admin 已交付，D10）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §7 预定货品全流程（V1.2 定位：**屏蔽入口保留代码**，模块不删，仅不暴露入口）
- **字段表**：doc/11-字段权威表.md §6（`gz_ord_*` 表全保留不动，本卡不改 schema）+ §10.3 menu 段（GZ-ORD 9000/9100 段 + 订单聚合 admin 11007-11009）
- **UI 参考**（设计冻结期）：
  - admin：`N/A（仅 UPDATE sys_menu.visible，不改 plus-ui 视图）`
  - mp：`design/mockup/home.html（首页预购卡视觉参考，本卡是隐藏该卡不是重画）`

## What

屏蔽预购功能的 admin + mp 双端入口：① `UPDATE sys_menu` 将预购相关菜单（9110-9112）+ 订单聚合 admin（11007-11009）中**仅 preorder 项** `visible='0'`；② mp 首页预购卡 + 聚合页预购入口隐藏。`ruoyi-gz-ord` 模块代码、`gz_ord_*` 表、plus-ui `views/gz-ord/*` 视图、mp `pages/ord/*` 代码**全部保留不删**，仅入口不暴露，随时可恢复。

## AC（验收标准）

- [ ] **AC 1**：改 menu 前先执行并记录 `SELECT menu_id, menu_name, visible, perms FROM sys_menu WHERE menu_id IN (9110,9111,9112,11007,11008,11009)`（raw output 入 reports），逐行确认**哪些是 preorder 项、哪些是 gacha 项**。⚠️ 一票否决：**只藏 preorder，绝不藏扭蛋（gacha）项**——扭蛋 V1.2 保留做活（仅降开发优先级，D14 GZ-GACHA-111 入口迁「我的」+ 做活回归），其 admin 入口必须仍 `visible='1'`。
- [ ] **AC 2**：Flyway 迁移 `V<时间戳>__GZ-ORD-110-hide-preorder-entry.sql` 只 `UPDATE sys_menu SET visible='0' WHERE menu_id IN (<确认的 preorder menu_id>)`（**不 DROP 表、不删 menu 行、不改 perms**）。迁移后 admin 左侧菜单不再出现预购商品管理；订单聚合 admin 仍可见但预购 tab/筛选项隐藏（若聚合页是单菜单含多业务类型，则保留菜单，前端隐藏 preorder 业务类型筛选项）。
- [ ] **AC 3**：mp 首页（`pages/index/index.vue` 或 home 卡片区）预购卡隐藏——找到预购入口卡（跳 `pages/ord/*` 的 card / banner）并条件隐藏（`v-if="false"` 或删除该卡渲染，**不删 pages/ord 代码**）。GZ-SYS-010 tabbar 重构后首页会整体下线，本卡此处确保**当前首页无残留可点击预购入口**。
- [ ] **AC 4**：mp 聚合「我的订单」页（`pages/me/orders` MP-ORD-LIST）若有「预购」tab / 业务类型筛选项 → 隐藏该 tab（保留扭蛋 tab）；点不进预购订单详情入口。**不删 pages/ord/* 与订单聚合代码**。
- [ ] **AC 5**：代码/表/数据完整保留验证——`ruoyi-gz-ord` 模块、`gz_ord_*` 表、`plus-ui/src/views/gz-ord/*`、`miniapp/src/pages/ord/*` 一律存在未删（`ls` raw output 入 reports）；恢复方式 = 反向 `UPDATE sys_menu SET visible='1'` + 去掉 mp 入口隐藏，无数据损失。
- [ ] **AC 6**：重建库 + 启动后 Flyway 自动应用迁移；`SELECT menu_id, visible FROM sys_menu WHERE menu_id IN (<preorder ids>)` 全 `visible='0'`，gacha 项仍 `visible='1'`（raw output 入 reports）。
- [ ] **AC N: Tier 2 入口可达（本卡是「入口消失」验证）**（CLAUDE.md §8.3）— Kevin 从 mp 首页 + 我的订单页 **确认看不到任何预购入口**（卡片 / tab / 跳转）。
  - 入口路径：mp 启动 → 首页（确认无预购卡）；底部 tab「我的」→「我的订单」（确认无预购 tab，仅扭蛋）
  - 这是**反向验证**（入口应消失，非应出现）——无需临时入口；若仍能点到预购页 → §revision 回填

## Tech（端 + 范围）

- **后端 / DDL**：`ruoyi-modules/ruoyi-gz-ord/`（代码**不动**）
  - DDL（仅 UPDATE menu visible，无表结构变更）：`ruoyi-admin/src/main/resources/db/migration/V<时间戳 ≥ 202606190600>__GZ-ORD-110-hide-preorder-entry.sql`
- **Admin**：`code/main/plus-ui/src/views/gz-ord/*`（视图**保留不删**）；若订单聚合页含预购业务类型筛选项 → 前端隐藏该选项（`views/gz-ord/order/*` 或聚合页）
- **小程序**：`code/main/miniapp/src/`
  - `pages/index/index.vue`（或 home 卡片组件）：隐藏预购入口卡
  - `pages/me/orders`（聚合订单页）：隐藏预购 tab/筛选项
  - `pages/ord/*`：**保留不删**
- **测试**：kevin-qa Tier 1B — admin Playwright 验菜单不可见 + 扭蛋菜单仍可见；mp 可达性反向检查（首页/聚合无预购入口）

## 备注

- **屏蔽 ≠ 删除**（合同 §2.3 预购 V1.2 屏蔽入口保留代码）：随时可恢复，恢复只需反向操作 menu visible + mp 入口显隐，零数据迁移。
- ⚠️ **勿误藏扭蛋**：订单聚合 admin（11007-11009）下预购 + 扭蛋两类共存，扭蛋 V1.2 保留做活（仅降开发优先级，D14 GZ-GACHA-111 入口迁「我的」+ 做活回归）——本卡若误把 gacha 菜单一起 `visible='0'`，会让扭蛋 admin 入口消失，直接冲突。改 menu 前**必须** `SELECT` 逐行核对（AC 1）。
- 迁移文件**已应用不可改**（checksum）：若发现 menu_id 与预设 9110-9112/11007-11009 不符（实际段位由 GZ-ORD-101-menu / GZ-ADMIN-103-menu 落地），以 §0 自检 `SELECT` 出的真实 menu_id 为准，不要按 ticket 字面硬编码错的 id。
- mp 首页若 GZ-SYS-010（D14）会整体下线首页，本卡的首页预购卡隐藏是**过渡保险**（确保 D14 之前首页无残留入口），D14 tabbar 重构后首页下线即天然无入口——本卡隐藏不与 D14 冲突。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D11/GZ-ORD-110 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
