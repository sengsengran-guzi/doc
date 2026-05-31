# GZ-ORD-102 — mp 商品列表 + 筛选

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §用户操作流程 步骤 2 + §关键页面
**关联拆解**: doc/02-需求拆解.md §3.2 第 687-697 行
**关联 mockup**: design/mockup/preorder-list.html（仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-ORD-101 + GZ-ADMIN-005 ✅

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §6 V1.1 演进流 §6.4 预购商品浏览流（如无 → 实施前补写：进入入口 / 排序逻辑 / 筛选交互 / 倒计时计算）
- **字段表**：doc/11-字段权威表.md §6.1 gz_ord_product（所有展示字段含 ip_tag / series_tag / deadline_at / arrival_at / arrival_text）
- **UI 参考**：mp `preorder-list.html`（卡片含截止倒计时 + 价格 + 到货日 + IP 标签）+ doc/12 §MP-ORD-PREORDER-LIST

## What

mp 端预购商品列表页：

1. 排序切换：「到货时间近的优先」/「热度」/「截止日紧迫」三选一
2. 筛选：IP 标签 / 作品系列标签（多选）
3. 卡片视觉：主图 + 商品名 + 起始价 + 截止倒计时（实时计算）+ 到货日（精确显示日期 / 模糊显示文案）+ IP 标签 chip
4. 分页：下拉加载（每页 20）
5. 点击卡片 → 跳 ORD-103 商品详情

## AC（验收标准）

- [ ] **AC 1**：mp `GET /app/gz/ord/product/list` 接口：
  - 参数：page / size / sortBy(`arrival_asc`/`hot`/`deadline_asc`) / ipTags(逗号分隔) / seriesTags(逗号分隔)
  - 查询条件：`status='on' AND deadline_at > NOW()` 强约束（兜底 ORD-101 cron 万一漏跑）
  - 排序：
    - arrival_asc：`ORDER BY COALESCE(arrival_at, '9999-12-31') ASC, deadline_at ASC`（无精确日期的排最后）
    - hot：`ORDER BY view_count DESC`（view_count 字段如 ORD-101 未加 → 本 ticket 加 ALTER `view_count INT NOT NULL DEFAULT 0`）
    - deadline_asc：`ORDER BY deadline_at ASC`
  - 返回：商品 list + 起始价（取所有 SKU min price_fen）+ 主图 + ip_tag + series_tag + deadline_at + arrival_at + arrival_text
- [ ] **AC 2**：商品详情访问时 view_count + 1（在 ORD-103 实施时接入；本 ticket 仅加字段 + 接口预留）
- [ ] **AC 3**：mp 端 `pages/ord/preorder-list.vue` 页面：
  - 顶部 tab 切换排序（Biz 组件包装，不直接撒 wd-*；视觉走 C 设计系统 var(--c-*)，选中态 var(--c-red)）
  - 筛选抽屉用功能性 `<wd-action-sheet>` 或 `<wd-popup>`（IP / 系列多选），外观套 C token
  - 商品卡片 `<components/biz/BizPreorderCard.vue>`（业务组件包装层，遵循 CLAUDE.md §7.5 组件库无关纪律 + C 设计系统，不直接撒 wd-*）
  - 下拉加载 + 上拉刷新（uni 原生 onReachBottom / onPullDownRefresh）
  - 截止倒计时 setInterval 每秒刷新（页面卸载 clearInterval）
- [ ] **AC 4**：tabBar 加"预购"入口（与 V1.0 已有的拼豆 / 资讯 / 我的并列）
  - tabBar 配置 4 项 → 5 项（首页 / 拼豆 / 预购 / 资讯 / 我的）
  - tabBar 顺序按 doc/tokens.md §7.2 V1.1 扩展 5 tab 规范排（首页 / 扭蛋 / 预购 / 资讯 / 我的），选中态 var(--c-red)
- [ ] **AC 5**：i18n：所有可见字符串走 `t('ord.preorderList.xxx')`
- [ ] **AC 6**：单测（vitest）：
  - BizPreorderCard 倒计时计算（mock Date.now）
  - 排序参数映射到 SQL ORDER BY 字段（service 层）
  - 共 ≥ 2 个测试方法

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`
  - `controller/applet/GzOrdProductMpController.java`（路径 `/app/gz/ord/product`）
  - `service/IGzOrdProductService.java` 增 `listForMp(req)` 方法
  - `domain/dto/applet/OrdProductListReq.java` + `vo/applet/OrdProductCardVO.java`
  - `enums/OrdProductSortEnum.java`
  - ALTER `gz_ord_product` 加 `view_count INT NOT NULL DEFAULT 0`（如未加）
  - DDL × 1（仅 ALTER 一句）
- **小程序**：`code/main/miniapp/src/`
  - `pages/ord/preorder-list.vue`
  - `components/biz/BizPreorderCard.vue` + `BizFilterDrawer.vue`
  - `composables/useCountdown.ts`（倒计时复用）
  - `api/gz-ord.ts`（新建文件，加 `getPreorderProductList` 调用）
  - `i18n/zh-CN/ord.ts`（新建 i18n 字典文件）
  - `pages.json` tabBar 加预购页 + 顶部 navigationBar 标题
- **测试**：vitest + 微信开发者工具浏览列表 + 切换排序 + 筛选标签

## 备注

### 强约束

1. **status='on' AND deadline_at > NOW()** 后端强校验 — 不靠 mp 端过滤
2. **业务组件包一层 BizPreorderCard**（CLAUDE.md §7.5 组件库无关纪律）— 不直接在 page 撒 `<wd-card>` 标签
3. **i18n 强制** — 包括 "已截止" "热度" "到货" 等所有可见字（doc/02 §3.2 隐含）
4. **倒计时 setInterval 必须 onUnmounted clearInterval** — 防内存泄漏
5. **起始价取 SKU min**（不是商品表存）— SKU 价格变更时不需要同步父表
6. **menu_id 不涉及**（mp 路径无菜单权限）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | view_count 字段加在 product 表（非独立 stat 表） | V1.1 流量小，热度统计简单累加足够；高并发场景再考虑独立表 + 异步累加 |
| D2 | 排序 3 选 1 而非多排序 | mockup 锚定 3 个 tab；多选排序 UX 复杂 |
| D3 | 筛选用抽屉 + 多选 chip | 功能性 wd 抽屉外观套 C token；mockup 锚定布局 |
| D4 | 倒计时前端实时算（不靠后端） | 减少接口调用；服务器 NOW() 与客户端时间偏差 < 1min 用户无感知 |
| D5 | tabBar 4 → 5 项 | V1.1 预购入口最重要；首页 / 拼豆 / 预购 / 资讯 / 我的 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 客户端时间被改 → 倒计时不准 | 接口返回 deadline_at 时同时返回 server_now，前端校准 |
| R2 | 列表分页时商品下架（status 改 on→off）→ 翻页可能跳号或重复 | 客户预购品类少，下架瞬间用户翻页概率低，接受 |
| R3 | view_count 高并发累加竞争 | UPDATE ... SET view_count = view_count + 1 原子操作；无需乐观锁 |
| R4 | tabBar 5 项布局在小屏机型挤压 | wot tabBar 默认支持 5 项；mockup 已按 5 项设计 |
| R5 | 筛选标签多选 SQL IN 长度过长 | 限制最多选 10 个标签；前端 UI 提示 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
