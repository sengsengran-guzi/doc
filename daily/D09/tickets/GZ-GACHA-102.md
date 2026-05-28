# GZ-GACHA-102 — mp 扭蛋机列表

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §用户操作流程 步骤 1 + §关键页面
**关联拆解**: doc/02-需求拆解.md §3.3 第 758 行
**关联 mockup**: design/mockup/gacha-list.html（视觉参考 — 设计冻结期 mp 走 wot 默认 + tokens.md，不逐像素还原）
**关联 ADR**: —
**依赖**: GZ-GACHA-101 + GZ-ADMIN-005 ✅

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md §7 扭蛋抽奖流（步骤 1 列表浏览）
- **字段表**：doc/11-字段权威表.md §7.1 `gz_gacha_machine`
- **UI 索引**：doc/12-UI-权威索引.md **§MP-GACHA-LIST**（页面字段 / 交互 / 跳转）
- **tokens.md §9**：扭蛋机用立体迷你机器视觉（不是平面商品图）+ 盲盒语义纪律（"扭蛋" / "出现概率"）
- **CLAUDE.md §7.5**：设计冻结期 mp 走 wot 默认 + tokens.md 主色

## What

mp 端展示在售扭蛋机卡片列表（按 sort_order 倒序），用户点卡片跳详情页（GACHA-103）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/machine/list?pageNum=&pageSize=`（sa-token mp-client）→ 返回 status='on_shelf' + del_flag=0 的机器列表（按 sort_order DESC，id DESC 兜底）；返回字段：id / name / cover_url / single_price / 当前奖品总剩余库存 sum(current_stock)
- [ ] **AC 2**：page `pages/gacha/list.vue`：
  - 顶部分类筛选条（V1.1 简版只显示「全部」一个 tab，预留扩展位）
  - 卡片网格（2 列）：机器封面 + 立体迷你机器视觉效果（tokens.md §9 + CSS 阴影/光泽模拟，不堆静态图）
  - 卡片字段：机器名 / 单抽价格（红色 .price token）/ 剩余库存提示（"剩余 X" 或 "即将售罄" 当剩余 < 10）
  - 触底加载分页（wd-loadmore）
  - 卡片点击 → 跳 `/pages/gacha/detail?id={machineId}`
- [ ] **AC 3**：tokens.md 视觉对齐：
  - 稀有度色 / brand-primary CTA token 应用
  - 价格永远 `--price` 红
  - 卡片圆角 `rounded-lg` (8px)
  - 卡片阴影 `0 1px 3px rgba(0,0,0,.04)`
- [ ] **AC 4**：i18n 走 `t('gacha.list.xxx')`（zh-CN + en-US 同步）；**所有可见字符串严格扭蛋语义**（无"抽奖"/"中奖"等词）
- [ ] **AC 5**：业务组件包一层（CLAUDE.md §7.5 组件库无关纪律）：
  - `components/biz/BizGachaMachineCard.vue`（机器卡片）
  - 不在 page 内直接撒 `<wd-*>`
- [ ] **AC 6**：空数据 friendly 提示（"暂无在售扭蛋机" + 客服入口）
- [ ] **AC 7**：单测（vitest）覆盖 mp service 调用 happy path；mvn 后端单测覆盖 list 分页 happy

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaMachineMpController.java`（`/app/gz/gacha/machine`）
  - service 复用 GACHA-101 的 `IGzGachaMachineService`，新增方法 `listOnShelfForMp(pageQuery)`（带 sum 子查询统计 current_stock 总和）
- **小程序**：
  - `pages/gacha/list.vue`
  - `components/biz/BizGachaMachineCard.vue`
  - `api/gz-gacha.ts` 加 `getMachineList()`
  - `lang/zh-CN/gacha.ts` + `en-US/gacha.ts`
- **测试**：mvn + vitest + 微信开发者工具实操

## 备注

### 强约束

1. **mp API 前缀 `/app/gz/gacha/...`**（sa-token mp-client 拦截 — CLAUDE.md §6）
2. **盲盒语义**（tokens.md §9 2026-05-18 大修订）— 所有 UI 文案用"扭蛋"系，不用"抽奖"系
3. **立体迷你机器视觉**（tokens.md §9）— 不是平面商品图；用 CSS box-shadow + linear-gradient 模拟玻璃罩 / 胶囊
4. **i18n 强制 t() 调用**（无硬编码中文）
5. **业务组件包一层** `<BizGachaMachineCard>`，组件库切换时不动 page

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 列表返回"奖品总剩余库存"sum 而非每个奖品 | 列表只需"即将售罄"提示，详情页才查全量奖品（GACHA-103） |
| D2 | 立体机器视觉用 CSS 而非 SVG / Lottie | 兼容性好 + 性能优 + 不引依赖；视觉可接受度 90%（V1.1 简版） |
| D3 | 分类筛选条预留单 tab | 现状只有"全部"，但 v2 会按 IP 系列分类，预留 UI 结构 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | sum(current_stock) 在 SQL 上耗时（机器多奖品多时）| 加 `idx_machine_stock` 索引（GACHA-101 已加）；V1.1 流量小（< 10 机器）不会有性能问题 |
| R2 | 立体机器视觉在不同微信版本 CSS 兼容性差异 | 主流微信版本 box-shadow / gradient 全支持；老版本 fallback 走平面图 |
| R3 | "即将售罄" 阈值（< 10）写死 | 接受：V1.1 简单阈值；v2 可改为机器粒度配置 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
