# GZ-SYS-010 — tabbar 重构（去首页 → 拼豆/回收/我的 + 资讯·扭蛋迁我的）

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M1 §导航
**关联拆解**: doc/02-需求拆解.md §3.6.4 GZ-SYS-010
**关联 ADR**: -
**依赖**: GZ-RECYCLE-002（`/pages/recycle/form` 回收页存在）+ GZ-BEAN-015（D13，拼豆付费页 = 拼豆 tab 落地）+ designer 回收 tab C 风图标（未交付用占位）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：N/A（纯导航重构）
- **UI 权威**：doc/12 §4.0（V1.2 tabbar 重构 + 入口结构，3 tab 表 + 「我的」入口卡清单 + mermaid）+ CLAUDE.md §7.5（tabbar 形态：3 tab 选中朱红 / 去首页指向 bean / 资讯·扭蛋迁我的）
- **设计**：doc/tokens.md（C 色卡，选中 `--c-red` #E73E2A）+ designer tab 图标范式（80×80 PNG，active=HL 后缀）

## What

底部 tabbar 从「首页/拼豆/我的」改为 **3 tab：拼豆 / 回收 / 我的**（去独立首页，启动默认指向 bean）。原首页非主线入口（资讯/扭蛋）迁入「我的」tab 入口卡。清理历史临时入口（用真 tab 入口替换）。

## AC（验收标准）

- [x] AC 1：**3 tab 重构** ✅ tabbar/config.ts + pages.json = 拼豆/回收/我的，朱红 #E73E2A。
- [x] AC 2：**去独立首页 + 启动指向 bean** ✅ bean/index 设 type:home（app.json pages[0]=bean）；index 降 redirect 兜底页；banner/资讯内容评估丢弃（reports 写明，不下沉）。
- [x] AC 3：**回收 tab 图标** ✅ recycle.png/recycleHL.png 占位（复用 home 图）+ config 注释 designer 待补。拼豆沿用 bean 图标（语义对）。
- [x] AC 4：**资讯 + 扭蛋入口迁「我的」** ✅ me/index 发现区：资讯→/pages/news/list、扭蛋→/pages/gacha/index（做活真列表）。另补回收记录→/pages/recycle/my-list。预购隐藏。
- [x] AC 5：**清理历史临时入口** ✅ index.vue GZ-RECYCLE-002 + GZ-PAY-001 随首页下线消失（真入口替换）；gacha GZ-GACHA-106 有意保留留 GACHA-111（reports 写明分工）。
- [x] **AC 6: Tier 2 入口可达** ✅ 启动落地拼豆 tab；回收/拼豆 tab 直达；资讯/扭蛋/回收记录从「我的」N=2 可达。

## Tech（端 + 范围）

- **小程序**：
  - `src/tabbar/config.ts`（nativeTabbarList 改 3 tab）+ `src/pages.json`（tabBar.list + pages 首页路由）
  - `src/static/tabbar/`（回收 tab 图标占位 recycle.png / recycleHL.png）
  - `src/pages/me/index.vue`（加资讯 + 扭蛋入口卡，MeGrid / BizPanel）
  - `src/pages/index/index.vue` 下线处理（评估内容下沉）
  - 清理 `pages/index/index.vue` + `pages/gacha/index.vue` 的 Tier2-entry-temp
- **测试**：tabbar config / 入口卡逻辑如抽纯函数加 vitest；否则 build 通过 + 可达性人验

## 备注

- 纯 mp 导航，无新增后端/表/menu。
- GACHA-111（本日最后）依赖本卡「我的」扭蛋入口卡就绪后接通做活回归。
- BEAN-015 reports 确认：拼豆 tab 早已存在（V1.0 3-tab），SYS-010 保留拼豆 tab 指向 bean/index 不变。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 待 Kevin 批量人验填 -->
