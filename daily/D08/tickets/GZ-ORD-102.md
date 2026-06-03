# GZ-ORD-102 — mp 预购商品列表 + 筛选 + 排序（接真数据，解 ComingSoon）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §用户操作流程 步骤 2 + §关键页面
**关联拆解**: doc/02-需求拆解.md §3.2
**关联 mockup**: design/mockup/preorder-list.html（仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-ORD-101（gz_ord_product / gz_ord_sku 数据模型 + admin CRUD，**本日同波次，未 close 前不可起**）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。
> UI 索引在设计冻结期降级为"视觉参考"，doc/12 §MP-ORD-PREORDER-LIST 里的「5 tab / 购物车 fab / brand-primary token」是 mockup 旧注记，与 Kevin V1.1 决策冲突，**以本卡为准**（不加第 5 tab、走 C 系统 token、不做购物车）。

- **业务流**：doc/10-业务流权威图.md **§7 预定货品全流程**（触发条件 = 「首页推荐卡 → 预购列表」；V1.0/V1.1 边界 = V1.1 真数据；业务规则表 = 全款 / 截止日下架 / 库存 SKU 级可选）。**注意：物流是 §9、扭蛋是 §8，本卡只读 §7。**
- **字段表**：doc/11-字段权威表.md **§6.1 gz_ord_product**（展示字段：`name` / `main_image_id` / `ip_tag` / `deadline_time` / `delivery_date_text` / `delivery_date_exact` / `status` / `sales_count` / `sort_no`）+ **§6.2 gz_ord_sku**（`price_cent` / `enabled` 取 min 价做起始价）。
- **UI 参考**：doc/12-UI-权威索引.md §MP-ORD-PREORDER-LIST + mp `design/mockup/preorder-list.html`（卡片含截止倒计时 + 价格 + 到货日 + IP 标签；视觉走 C 系统不逐像素还原）。
- **设计系统**：doc/tokens.md（色卡 / 字号 / 描边 / 阴影；**无 `--c-shadow-card` token**）+ doc/13-设计语言-C日漫浓墨.md（Biz* 原子组件清单）。

## What

mp 端预购商品列表页（路径 `/pages/ord/list`）：三态排序切换（到货近 / 热度 / 截止紧迫）+ IP 标签筛选 + 卡片（主图 + 商品名 + 起始价 + 截止倒计时 + 到货日 + IP chip）+ 下拉加载分页；点击卡片跳 ORD-103 商品详情。同时把首页已有的「日谷预购」teaser 从 ComingSoon 改指向本真列表页（解 ComingSoon）。

## AC（验收标准）

- [ ] **AC 1**：后端 mp 接口 `GET /app/gz/ord/product/list`：
  - 参数：`pageNum` / `pageSize`（默认 20）/ `sortBy`（枚举 `arrival_asc` / `hot` / `deadline_asc`，默认 `deadline_asc`）/ `ipTags`（逗号分隔，可空）
  - 查询强约束：`status = 'on_shelf' AND deadline_time > NOW() AND del_flag = 0`（兜底 ORD-101 截止下架 SnailJob 万一漏跑；`auto_off` / `off_shelf` 不返回）
  - 排序映射：
    - `arrival_asc`：`ORDER BY COALESCE(delivery_date_exact, '9999-12-31') ASC, deadline_time ASC`（无精确到货日的排最后）
    - `hot`：`ORDER BY sales_count DESC, deadline_time ASC`（热度复用 §6.1 已有 `sales_count`，**不新增 view_count 字段**）
    - `deadline_asc`：`ORDER BY deadline_time ASC`
  - `ipTags` 非空 → 追加 `AND ip_tag IN (...)`（最多 10 个，超出截断 + 日志 warn）
- [ ] **AC 2**：返回 VO（`OrdProductCardVO`）每项含：`id` / `name` / `mainImageUrl`（由 `main_image_id` 经 gz_file_object 解析为可访问 url，**前端不存裸 url 字段**）/ `startPriceCent`（取该商品所有 `enabled=1` 的 `gz_ord_sku.price_cent` MIN）/ `ipTag` / `deadlineTime`（ISO8601）/ `deliveryText`（`delivery_date_exact` 优先格式化 `yyyy-MM-dd`，否则取 `delivery_date_text`，都空则空串）/ `salesCount`；列表外层额外返回 `serverNow`（服务器当前时间，供前端校准倒计时）。
- [ ] **AC 3**：IP 筛选项来源接口 `GET /app/gz/ord/product/ip-tags`：返回当前在售商品（同 AC1 强约束）去重后的 `ip_tag` 列表（`DISTINCT ip_tag WHERE status='on_shelf' AND deadline_time > NOW() AND ip_tag IS NOT NULL`），供前端筛选 chip 渲染（不前端硬编码 IP 列表）。
- [ ] **AC 4**：mp 页面 `pages/ord/list.vue`：
  - 顶部排序切换用 Biz 组件包装（不直接撒 `<wd-*>`；选中态 `var(--c-red)`，视觉走 C 系统 `var(--c-*)` token）
  - IP 筛选 chip 横滑多选，外观套 C token（功能性 wd 组件可用，外观必须 C 化）
  - 商品卡片用 `components/biz/BizPreorderCard.vue`（业务组件包一层，遵循 CLAUDE.md §7.5 组件库无关纪律 + C 设计系统，**不在 page 直接撒 `<wd-card>`**）
  - 卡片字段：主图 + 商品名 + 起始价（`startPriceCent / 100` 转元 + `¥` 前缀）+ 截止倒计时 + 到货日文案 + IP chip
  - 下拉刷新 + 上拉加载（uni 原生 `onPullDownRefresh` / `onReachBottom`）
  - 截止倒计时：以接口 `serverNow` 与 `deadlineTime` 差值起算，`setInterval` 每秒刷新；倒计时归零显示「已截止」并置灰卡片（不可点）
- [ ] **AC 5**：点击卡片 → `uni.navigateTo` 跳 `/pages/ord/detail?id=<productId>`（ORD-103 页面）。
- [ ] **AC 6**：i18n —— 所有可见字符串（含「到货近」「热度」「截止紧迫」「已截止」「到货」「筛选」「暂无在售商品」等）走 `t('ord.list.xxx')`，新建 `i18n` 字典；默认 zh-CN，不混 emoji。
- [ ] **AC 7**：单测（vitest ≥ 2 个测试方法）：
  - `BizPreorderCard` 倒计时计算（mock `Date.now()` / 给定 `serverNow` + `deadlineTime` 断言剩余天时分秒，含归零分支）
  - service 层排序参数 → SQL ORDER BY 字段映射（3 个枚举各断言一次，非法值兜底 `deadline_asc`）
- [ ] **AC 8: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从**首页**点 1 次「日谷预购」teaser 卡到达本列表页。
  - 现状：`pages/index/index.vue` 已有「日谷预购」teaser（`goPage('/pages/ord/index')` + `soon: true`），当前落 ComingSoon 占位页 `pages/ord/index.vue`。
  - 本卡动作：把该 teaser 的 `url` 改为 `/pages/ord/list` + 去 `soon`（解 ComingSoon），指向本真列表页；**不新增第 5 个 tab**（tabBar 维持 V1.0 3 tab：首页 / 拼豆 / 我的，doc/tokens.md §7.2 的 5 tab 是 V1.1 全量收尾时再扩，不在本卡）。
  - 旧占位页 `pages/ord/index.vue` 保留不删（避免断已注册路由），但首页不再指向它。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`
  - `controller/applet/GzOrdProductMpController.java`（基路径 `/app/gz/ord/product`，公开/登录态按 mp 鉴权惯例，不挂 `@SaCheckPermission` —— C 端浏览无需店员权限）
  - `service/IGzOrdProductService.java` + impl 增 `listForMp(req)` / `listOnSaleIpTags()`
  - `domain/dto/applet/OrdProductListReq.java` + `domain/vo/applet/OrdProductCardVO.java`
  - `enums/OrdProductSortEnum.java`（`ARRIVAL_ASC` / `HOT` / `DEADLINE_ASC` + 非法值兜底）
  - **本卡无 DDL**：展示字段（`ip_tag` / `deadline_time` / `delivery_date_*` / `sales_count` / `main_image_id`）+ 起始价（min `gz_ord_sku.price_cent`）全部由 GZ-ORD-101 已建 schema 提供。**若 §0 自检发现缺字段 → STOP 报 Kevin，回 ORD-101 补，不在本卡 ALTER**（避免 schema 双写撞）。
  - 包名 `org.dromara.gz.ord.{controller,service,mapper,domain,enums}`
- **小程序**：`code/main/miniapp/src/`
  - `pages/ord/list.vue`（新建；`definePage` 注册路由 `pages/ord/list`，navbar 标题「预购日谷」）
  - `components/biz/BizPreorderCard.vue`（新建业务卡组件）
  - `composables/useCountdown.ts`（倒计时复用，接 `serverNow` 校准 + 卸载 `clearInterval`）
  - `api/gz-ord.ts`（新建，封 `getPreorderList` / `getPreorderIpTags`）
  - `locale/` 加 `ord.list.*` 字典（zh-CN + en）
  - `pages.json`：新增 `pages/ord/list` 页面声明；**tabBar 不动**（维持 3 tab）
  - `pages/index/index.vue`：改「日谷预购」teaser `url` → `/pages/ord/list` + 去 `soon`
- **测试**：vitest（AC7）+ 微信开发者工具浏览列表 / 切排序 / 选 IP chip / 上拉加载 / 点卡进详情（详情页 ORD-103 落地后联调）

## 备注

### 强约束

1. **status / 截止后端强校验**：`status='on_shelf' AND deadline_time > NOW()`，不靠 mp 端过滤；状态枚举用 §6.1 的 `on_shelf` / `off_shelf` / `auto_off`（**不用 `'on'` / `off_shelf`/`archived` 之外的值**）。
2. **字段名锚定 doc/11 §6.1**：截止 = `deadline_time`（**非 `deadline_at`**）；到货 = `delivery_date_exact`(DATE) / `delivery_date_text`(VARCHAR)（**非 `arrival_at` / `arrival_text`**）；图片 = `main_image_id` FK gz_file_object（**非裸 url**）；价格 = `price_cent`（**非 `price_fen`**）；筛选标签只有 `ip_tag`（**无 `series_tag` / 作品系列标签字段** —— 旧卡的"作品系列标签多选"删除，schema 不存在该列）。
3. **热度 = `sales_count DESC`**：复用 §6.1 已有 `sales_count`（订单 paid 时累加），**不新增 view_count 字段、不做浏览量埋点**（旧卡 view_count 方案废弃）。
4. **起始价取 SKU min**：`MIN(gz_ord_sku.price_cent) WHERE product_id=? AND enabled=1`，不在 product 表冗余存；SKU 改价不需同步父表。
5. **业务组件包一层 BizPreorderCard**（CLAUDE.md §7.5）；倒计时 `setInterval` 必须 `onUnmounted` `clearInterval` 防泄漏。
6. **i18n 强制 + 不混 emoji**（CLAUDE.md §6 #9）。
7. **menu_id 不涉及**（mp C 端浏览页，无后台菜单 / 无权限）。
8. **DDL 命名规约**（本卡虽无 DDL，约束保留）：如确需迁移用 `V<yyyyMMddHHmm>__GZ-ORD-102-<desc>.sql`，时间戳必须 > 当前最大 `V202606051200`；已应用迁移不可改。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 热度复用 `sales_count` 而非新建 view_count | §6.1 已有 `sales_count`（paid 累加）；V1.1 不做浏览量埋点，省一张表 + 一次 ALTER |
| D2 | 排序 3 选 1（单选）非多排序 | mockup / doc/12 锚定 3 个 sort tab；多选排序 UX 复杂，V1.1 不做 |
| D3 | IP 筛选项走接口动态拉（非前端硬编码） | 在售 IP 随商品变动；后端 DISTINCT 单一真源，避免前端漏维护 |
| D4 | 倒计时前端算 + `serverNow` 校准 | 减接口调用；服务器时间为基准防客户端改表，偏差 < 1min 用户无感 |
| D5 | 入口 = 首页 teaser 解 ComingSoon，**不加第 5 tab** | 当前 tabBar 仅 3 tab（无预购 tab 占位）；Kevin 决策 = 改现有首页 teaser 指真页；5 tab 留 V1.1 全量收尾再扩 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **§0 自检须 grep migration 目录确认上游表实际存在**（gz-ord 曾是空脚手架） | §0 自检 `ls db/migration \| grep GZ-ORD-101` + 连库 `SHOW COLUMNS FROM gz_ord_product` 确认 `ip_tag`/`deadline_time`/`delivery_date_*`/`sales_count`/`main_image_id` 全在；缺 → STOP 回 ORD-101，不本卡 ALTER |
| R2 | 客户端时间被改 → 倒计时不准 | 接口返回 `serverNow`，前端以其为基准起算，不用 `Date.now()` 直接对比 |
| R3 | 分页中商品被截止下架（status 改）→ 翻页跳号/重复 | 预购品类少、下架瞬间翻页概率低，接受；卡片倒计时归零本地置灰兜底 |
| R4 | `main_image_id` 为 NULL（admin 未传图）→ 卡片裂图 | VO 解析图片时 NULL → 返回占位图 url（C 系统占位 `MOCK` 水印图），不返裸空串 |
| R5 | IP 多选 SQL `IN` 过长 | 后端最多取前 10 个 ip_tag，超出截断 + warn 日志；前端 chip 不限选但传参截断 |
| R6 | 旧卡的「作品系列标签」「view_count」字段不存在 → 误 ALTER 撞 ORD-101 schema | 本卡明确删除该需求；筛选仅 `ip_tag`；热度仅 `sales_count`；**本卡零 DDL** |

### 外部前置 / 联调依赖

- 商品卡点击跳 `/pages/ord/detail`（ORD-103）—— ORD-103 未落地时跳转报"页面不存在"属预期，AC5 仅验跳转 url 正确，详情联调留 ORD-103 完工后。
- 真实商品图依赖甲方素材；未到位前 `main_image_id` 走 `MOCK` 水印占位图（CLAUDE.md §7.5 待甲方素材清单）。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D08/GZ-ORD-102 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
