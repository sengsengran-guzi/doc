# 设计方案 · 谷子宇宙拼团一期

关键页面的 2-3 方案与选定记录。**选定后此页视觉/IA 锁为基准**，ticket 与 `authority/ui-index.yaml` 以此为准。

## 两层顺序（★ 不能颠倒）

```
① 视觉基调（全局，一次）   00-theme.md      ← 主色/底色/圆角/阴影/字号阶
        ↓ 选定后才进
② 关键页面方案（每页 2-3）  各页 md          ← IA / 布局 / 交互范式
        ↓ 全部选定后才进
③ 拆 ticket
```

页面方案建在视觉基调之上。基调没定就出页面方案，每个方案都隐含一个没人确认过的主题。

| 层 | 文档 | 状态 |
|---|---|---|
| ① 视觉基调 | [00-theme.md](00-theme.md) | ✅ 已选定 · 方案 A |
| ② 页面方案 | 见下表 | ✅ 5 页全部已选定 |

## 覆盖判定

| 页面 | 是否关键页 | 出方案？ | 理由 |
|---|---|---|---|
| admin 履约看板 | ★ 是（看板 + 复杂交互） | ✅ [已选定](admin-fulfill-board.md) | 店员每天开的主操作页 |
| mp 订单详情 | ★ 是（客人侧最重要） | ✅ [已选定](mp-order-detail.md) | 一单 30 款的呈现方式决定可用性 |
| mp 首页 | ★ 是（一级导航主页） | ✅ [已选定](mp-home.md) | tabbar 第一格 |
| mp 商品详情 | ★ 是（高频浏览 + CTA） | ✅ [已选定 A](mp-product-detail.md) | 注意事项区块的位置与形态影响下单决策 |
| mp 购物车 | ★ 是（高频操作） | ✅ [已选定 A](mp-cart.md) | 30 款时的分组与批量操作形态 |
| admin 场管理 / 商品管理 / 订单管理 | 否 | ❌ 不出 | 标准 ruoyi CRUD，走 Element Plus 默认审美（CLAUDE.md §7.5：admin 不引用 mockup、不调样式） |
| mp 场详情 / 订单列表 / 下单确认 | 否 | ❌ 不出 | 通用列表/表单形态，跟随选定方案的规范走 |

## 产出方式说明

本项目 **admin 端不出 mockup**（项目纪律），**mp 端用 HTML 草案**（skill 允许的 Claude Design 兜底形式）。
全部方案合并在一个页面 [design-review.html](design-review.html)，顶部 tab 切换。

## 二期 · 代切（2026-10-03）

视觉基调沿用一期方案 A，不另出基调方案。草图：[snap-review.html](snap-review.html)。

| 页面 | 是否关键页 | 出方案？ | 理由 |
|---|---|---|---|
| mp 代切搜索（含入口位置） | ★ 是（一级入口 + 高频） | ✅ [已选定 B](mp-snap-search.md) | 入口放哪决定代切是不是一门显眼的生意 |
| mp 代切详情 | ★ 是（决定下单） | ✅ [已选定 A](mp-snap-detail.md) | 价格透明度直接影响比价与信任 |
| admin 代切下单 | ★ 是（日本员工主操作页） | ✅ [已选定 A](admin-snap-purchase.md) | 人工代买与交易跟踪的组织方式 |
| mp 下单确认 / 订单详情代切态 | 否 | 不出 | 复用一期已选定页面，只加区块（`UI:mp.order_confirm.snap` / `UI:mp.order_detail.snap`） |
| admin 账号 / 配置 / 词表 | 否 | 不出 | 照 gz-bean/store 范式的 CRUD / 表单页 |

### 设计权威（实现以此为准，草图只作参考）

**token**：沿用 `code/main/miniapp-jp/src/style/c-tokens.scss` + `uno.config.ts`，不新建主题、不新增 token；
组件禁止硬编码 hex。admin 走 Element Plus 默认审美。

**草图里会变的内容块，来源一律可算，禁止手填 / 写死**：

| 内容块 | 来源 |
|---|---|
| 煤炉 tab 空态热门词 chips | `gz_jp_snap_term` 中 `term_type=ip`、`enabled=1`，按 `sort_no` 取前 12 条（无新配置） |
| 详情「实时价格 · x 秒前」 | `gz_jp_snap_item.fetched_at` 与当前时间之差 |
| 「需人工确认」角标 / 详情准入提示条 | `gz_jp_snap_item.gate_result`（manual / blocked）+ `gate_reason` |
| 详情「煤炉原价 ¥x 円」与「价格说明」三行 | 报价（`quote:{quoteId}`）的 `price_jpy` / 商品价 / `fixed_fee_cent` / `est_shipping_cent`；**不出现汇率与加价比例** |
| 下单确认页报价剩余时间 | 报价 `quoted_at` + `quoteTtlSec` |
| 订单详情代切状态段 | `gz_jp_snap_purchase.purchase_status` / `trade_status` 映射（unknown 与 executing 统一显示「抢购中」） |
| 订单详情「运费差价已退 ¥x」 | `gz_jp_refund` 中 `refund_type=shipping_diff` 且已退款 |
| admin 各 tab 数字角标 / 今日下单数 / 上限 / 评价期限剩余 | count 查询 / `today_count` / `daily_limit` / `rate_deadline_at` |
| 煤炉 tab 图标 | 新素材 `static/tabbar/mercari.png` / `mercariHL.png`：AI 按 home / me 的线性风格先画，甲方可替换（REQ-SNAP-045） |
| 代切协议条款 | `UI:mp.agreement.snap`，文案甲方过目后定稿（确认单第三部分） |

**误导料**：[snap-review.html](snap-review.html) 里未选中的方案（搜索 A / C、详情 B / C、admin B / C）是被否决的方向，不是实现依据。
草图里的示例商品、价格、汇率数字都是假数据。
