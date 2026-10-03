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
