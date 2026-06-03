# GZ-GACHA-102 — mp 扭蛋机列表

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §用户操作流程 §抽扭蛋主路径 步骤 1（列表浏览）+ §关键页面
**关联拆解**: doc/02-需求拆解.md §3.3（GZ-GACHA-102 微信端扭蛋机列表）
**关联 mockup**: design/mockup/gacha-list.html（仅布局参考；视觉以 C 系统为准，doc/13；立体迷你机器视觉为 C 日漫海报浓墨：Biz* 组件 + var(--c-*)，不逐像素还原）
**关联 ADR**: —
**依赖**: GZ-GACHA-101（gz_gacha_machine / gz_gacha_prize 建表 + admin CRUD）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（**不是 §7 = 预购**）— N1「U 进扭蛋机列表」
- **字段表**：doc/11-字段权威表.md **§7.1 `gz_gacha_machine`** + **§7.2 `gz_gacha_prize`**（列表聚合 stock_remain 来源）
- **UI 参考**（mp ticket）：doc/12-UI-权威索引.md **§MP-GACHA-LIST**（页面结构 / 卡片字段 / 跳转关系）；mockup gacha-list.html 视觉参考，不逐像素还原
- **稀有度色**：doc/tokens.md **§1.4 稀有度色**（SSR `--c-r-ssr` / SR `--c-r-sr` / R `--c-r-r` / N `--c-r-n`，四档不引第五档）+ §1 朱红价格铁律 + §2 描边 / §3 投影 token。**禁止引 tokens §9（不存在）**
- **CLAUDE.md §7.5**：mp 视觉走 C 日漫海报浓墨 — 页面只用 Biz* 原子组件（**不直接撒 `<wd-*>`**）+ var(--c-*)，doc/13

## What

mp 端展示在售扭蛋机卡片列表（双列网格，立体迷你机器视觉），用户点卡片跳单机详情页（GACHA-103）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/machine/list?pageNum=&pageSize=`（sa-token mp-client 拦截）→ 仅返回 `status='on_shelf'` + `del_flag=0` 的机器（**排除 `off_shelf` / `auto_off`**），排序按 `online_time DESC, id DESC`（无 `sort_order` 字段，doc/11 §7.1 未定义该列）；分页 PageQuery。返回字段（对齐 doc/11 §7.1）：`id` / `name` / `coverImageId`（FK→gz_file_object，前端经 OSS url 解析；**不存裸 url**）/ `singlePriceCent`（分）/ `tenPackPriceCent`（可空）/ `ipTag` / 当前在池奖品总剩余库存 `stockRemainSum`（`SUM(gz_gacha_prize.stock_remain)` WHERE `enabled=1`）。
- [ ] **AC 2**：page `pages/gacha/index.vue`（复用现有 V1.0 占位页位置，**把 ComingSoonV11 占位替换为真列表**，使 home 扭蛋 teaser 直达本页）：
  - 顶部分类筛选条：V1.1 简版仅「全部」一个 chip（预留按 `ip_tag` 扩展的 UI 结构，本卡不接后端筛选）
  - 卡片网格（双列）：立体迷你机器视觉（CSS box-shadow + linear-gradient 模拟玻璃罩 / 胶囊 / 出蛋口，**非平面商品图**，doc/12 §MP-GACHA-LIST 关键视觉约束）+ 机器封面图（coverImageId 解析）
  - 卡片字段：机器名 `name` / 单抽价 `singlePriceCent`（÷100 显示「¥X.XX」，朱红 var(--c-red)）/ 剩余库存提示（`stockRemainSum` ≥ 10 显示「剩余 X」；`1 ≤ stockRemainSum < 10` 显示「即将售罄」；`stockRemainSum = 0` 显示「已抽完」灰态不可点）
  - 触底加载分页（Biz 包装 loadmore，不直接撒 wd-loadmore）
  - 卡片点击 → `uni.navigateTo({ url: '/pages/gacha/detail?id=' + machineId })`
- [ ] **AC 3**：C 设计系统视觉对齐（视觉走 `var(--c-*)`，**不硬编码 hex**，doc/tokens.md + doc/13）：
  - 卡片用 BizPanel 分镜框：直角（`--c-radius`=0）+ 粗墨边 `--c-bw` + 硬投影 `--c-shadow-sm`
  - 价格永远朱红 `--c-red`（tokens §1 铁律：价格不用竹绿）
  - 卡片如露稀有度角标，稀有度色走 `var(--c-r-ssr/-sr/-r/-n)`（tokens §1.4 四档）
- [ ] **AC 4**：i18n 全走 `t('gacha.list.xxx')`（zh-CN + en-US 同步，无硬编码中文）；**所有可见字符串严格盲盒语义** — 用「扭蛋 / 开盒 / 获得 / 出现概率」，**禁** 出现「抽奖 / 中奖 / 开奖 / 抽奖率」等词（grep 自查）。
- [ ] **AC 5**：业务组件包一层（CLAUDE.md §7.5 组件库无关纪律）：
  - `components/biz/BizGachaMachineCard.vue`（机器卡片，含立体迷你机器视觉）
  - 页面 / 卡片内**不直接撒 `<wd-*>`** 标签
- [ ] **AC 6**：空数据 friendly 提示（`t('gacha.list.empty')`「暂无在售扭蛋机」+ 客服入口可联系）。
- [ ] **AC 7**：单测 — vitest 覆盖 mp `api/gz-gacha.ts` getMachineList 调用 + 卡片库存提示档位 happy path；`mvn test -DskipTests=false` 后端覆盖 `listOnShelfForMp` 分页 + 仅 `on_shelf` 过滤 + `stockRemainSum` 聚合 happy path（每个 service impl ≥ 1 个单测）。
- [ ] **AC 8: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从**已上线首页**点 1 次「扭蛋机」teaser（home `goPage('/pages/gacha/index')`，已存在）即达本列表页（本卡把该页 ComingSoon 占位替换为真列表，**入口天然可达，无需加临时入口**）。再点任一在售卡片 1 次跳 `/pages/gacha/detail`（详情 GACHA-103 落地前为占位页，路径已可触发）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaMachineMpController.java`（`@RequestMapping("/app/gz/gacha/machine")`，`/list` 端点）
  - service 复用 GACHA-101 的 `IGzGachaMachineService`，新增 `listOnShelfForMp(PageQuery)`（带 `SUM(gz_gacha_prize.stock_remain)` 子查询，过滤 `status='on_shelf'` + `del_flag=0` + prize `enabled=1`）
  - DTO：`GzGachaMachineMpVo`（仅 mp 列表字段，不暴露 admin 内部字段如 weight / version）
  - 包名 `org.dromara.gz.gacha.{controller.applet,service,domain.vo}`
  - **本卡无新建表 / 无 DDL**（machine / prize 表由 GACHA-101 建）；如需补 mp 查询索引 `idx_machine_status_online`，DDL 命名 `V<yyyyMMddHHmm>__GZ-GACHA-102-add-mp-list-idx.sql`（时间戳 > 当前最大 `V202606051200`；已应用迁移不可改）
- **小程序**：
  - `pages/gacha/index.vue`（占位 ComingSoon → 真列表）
  - `components/biz/BizGachaMachineCard.vue`
  - `api/gz-gacha.ts` 加 `getMachineList(pageQuery)`
  - `lang/zh-CN/gacha.ts` + `lang/en-US/gacha.ts`（`gacha.list.*` key）
- **测试**：mvn 后端单测 + vitest + 微信开发者工具实操（Tier 2 走首页 teaser → 列表）

## 备注

### 强约束

1. **mp API 前缀 `/app/gz/gacha/...`**（sa-token mp-client 拦截 — CLAUDE.md §6）。
2. **盲盒语义**（D09 README §B / doc/10 §8）— 所有 UI 文案 + `t('gacha.list.*')` key 用「扭蛋」系，**禁** 抽奖系；后端 enum / 字段可保留 `draw`（技术语义）。
3. **立体迷你机器视觉**（doc/12 §MP-GACHA-LIST）— 非平面商品图；用 CSS `box-shadow` + `linear-gradient` 模拟玻璃罩 / 胶囊 / 出蛋口，GPU 友好（不用 setInterval 重绘）。
4. **图片走 `cover_image_id`（FK→gz_file_object）**，前端经 OSS 解析 url，**不存裸 url**（doc/11 §7.1 / 字段硬约束）。
5. **金额 `single_price_cent`（分）**，UI ÷100 显示，**不用 `_fen`**。
6. **状态枚举** `on_shelf` / `off_shelf` / `auto_off`（doc/11 §7.1）；列表仅出 `on_shelf`，**不用 off_shelf 之外的下架名**。
7. **业务组件包一层** `<BizGachaMachineCard>`，组件库切换时不动 page（CLAUDE.md §7.5）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 列表返回奖品总剩余库存 `stockRemainSum`（SUM），不返回每个奖品 | 列表只需「剩余 / 即将售罄 / 已抽完」三档提示；详情页才查全量奖品池（GACHA-103） |
| D2 | 复用 `pages/gacha/index.vue`（占位页）改真列表，不另建 `list.vue` | 首页 teaser 已指向 `/pages/gacha/index`，Tier 2 天然可达；doc/12 标 `/pages/gacha/list` 是早期命名，实际脚手架用 `gacha/index` |
| D3 | 排序 `online_time DESC, id DESC` | doc/11 §7.1 `gz_gacha_machine` **无 `sort_order` 字段**，按上架时间倒序最新优先 |
| D4 | 立体机器视觉用 CSS 而非 SVG / Lottie | 兼容性好 + 性能优 + 不引依赖（CLAUDE.md §6 不引未澄清新依赖）；V1.1 简版可接受度足够 |
| D5 | 分类筛选条预留单 chip「全部」 | 现状仅「全部」，v2 按 `ip_tag` 分类，预留 UI 结构不接后端 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **§0 自检须 grep migration 目录确认上游表实际存在**（不假设 GACHA-101 已 ✅）| §0 自检 `grep -rl "gz_gacha_machine\|gz_gacha_prize" code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/` 确认两表已建 + `gz_file_object` 存在（封面 FK）；缺 → STOP，挂起等 GACHA-101 |
| R2 | `SUM(stock_remain)` 子查询在机器多奖品多时耗时 | GACHA-101 已建 prize `(tenant_id, machine_id, enabled, stock_remain)` 索引；V1.1 流量小（< 10 机器）无性能问题；必要时补 `idx_machine_status_online` |
| R3 | 立体机器视觉在不同微信版本 CSS 兼容性差异 | 主流微信版本 box-shadow / gradient 全支持；老版本 fallback 走机器封面平面图 |
| R4 | 「即将售罄」阈值（< 10）写死 | 接受：V1.1 简单阈值；v2 可改机器粒度配置 |
| R5 | 盲盒语义在旧 mockup（gacha-list.html）可能含「抽奖」字样 | 实施以盲盒语义纪律为准，文案走 `t()`，**不动 mockup**（mockup 是历史快照）|

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D09/GZ-GACHA-102 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
