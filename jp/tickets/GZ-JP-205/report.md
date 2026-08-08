# GZ-JP-205 完工报告 — 小程序订单列表 + 详情（按履约状态分组）

> **accept #2（26 单测）与 #3（grep 无「包裹」）PASS；#1（`run.mjs orders`）BLOCKED** 于本机 devtools「不校验合法域名」GUI 开关（与 D2-D5 同一个人工动作）。
> 全量 **294 单测** + **self-test 72/72** + dev profile 构建通过，两页已注册进 `app.json`。
> ⚠️ 本卡经历 **3 次 API 503 中断**，由主线程接手收尾。

## 交付分工（诚实标注）

| 部分 | 谁做的 |
|---|---|
| `src/pages/order/{list,detail}.vue` + `{list,detail}.logic.ts` | 中断前的 subagent |
| `src/api/gz-jp/order.ts` 列表端点封装、`locale/order.zh-CN.ts` | 中断前的 subagent |
| **`src/pages/order/detail.logic.test.ts`（accept #2 本体，26 用例）** | **主线程补** |
| **`test/e2e/flows/orders.mjs`（accept #1 的 flow）** | **主线程补** |
| smoke 两页可达性 + self-test 夹具 + run.mjs 注册 | 主线程补 |
| 修 3 个真缺陷（见下） | 主线程 |

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游 106/107 已 merge | ✅ `47110b805` / `30bf7b5f6` |
| dev 库有跨多状态订单行 | ✅ 106 留的 fixture（cn_sorting / delivered 共用单号 / purchase_failed / purchasing） |
| 两个新页有 `<BizScreen class="jp-screen">` 锚点 | ✅ 各 1 处（E2E 深选择器依赖它） |
| 路由常量与 204 对齐 | ✅ `/pages/order/list`、`/pages/order/detail`（204 的支付结果页两个出口按钮直接打通） |
| 两页已注册进 app.json | ✅ `pages/order/{confirm,detail,list,result}` |

## 主线程修掉的 3 个真缺陷

### 1. ★ `Number(null) === 0` → 已退款行会渲染成「已退款 ¥0」

`resolveRefundDisplay` 原写法 `Number(refundAmountCent)`，而 JS 里 `Number(null)` 是 **0** 不是 NaN。后端漏字段时客人会看到一个**错的金额**——这恰恰是该函数 javadoc 自己声明要防的事（「过早显示一个具体数字，等它变了就是客诉」）。给客人错数字比不显示金额糟得多。

```ts
const cent = refundAmountCent === null || refundAmountCent === undefined
  ? Number.NaN : Number(refundAmountCent)
```
**没有为了让测试变绿去弱化断言**（那是「改断言迁就现状」反模式）。

### 2. `BizSectionTitle` 用法错误 → type-check 报错
该组件收 `title` **prop** 不是 slot，原写法 `<BizSectionTitle>{{ ... }}</BizSectionTitle>` 缺必填 prop。改成 `:title="..."`（与首页一致）。

### 3. `[...map.values()]` → TS2802
本工程 tsconfig 未开 `downlevelIteration`，展开 MapIterator 直接编译报错（真机产物走同一条路径，不是纯类型洁癖）。改 `Array.from(...)`。

## accept 三条

### #2 同一运单号在详情页只出现一次 ✅（26 单测）
```
$ pnpm vitest run src/pages/order/detail.logic.test.ts
 ✓ src/pages/order/detail.logic.test.ts (26 tests) 5ms
 Test Files  1 passed (1)      Tests  26 passed (26)
```
重心不是把导出函数点一遍，而是**把分组的核心收益钉死**：
- 12 款共用一个单号 → 1 个组、单号出现 1 次
- ★ **30 款真实订单**（12 SF + 8 JD + 5 清关 + 3 购买中 + 2 失败）→ 单号数组**去重前后长度相同** = 没有任何一个重复；30 行一个不丢
- 同状态两个不同单号 → 分子组各带各的单号；单号带空格视作同一个合并；同单号的行**不相邻也能合并**
- 组序倒序状态链、**购买失败恒最后**、AC「≤7 组」
- 退款：`refunded` 才给金额；`refunding`/`refund_failed` 只说处理中；`refund_failed` 额外给客服出口但**不暴露「失败」二字**
- 未知状态不丢弃（总数守恒）；`delivered` 缺单号不崩

### #3 全页不出现「包裹」二字 ✅
```
$ ! grep -qE '包裹|package' src/pages/order/detail.vue
ACCEPT3 PASS (exit 0)
```
（连英文 `package` 也不能出现 —— 注释和变量名都避开了。）

### #1 `node test/e2e/run.mjs orders` — BLOCKED（环境）
```
[preflight] ✓ devtools cli / ✓ 服务端口 / ✓ devtools 已登录
           ✓ dist 完整 / ✓ dist = dev profile / ✓ 后端可达 / ✓ 认 clientid
[preflight] ✓ 通过
[run] ✓ automation launched
[run] launch/run 异常: 小程序侧 wx.request 被域名校验拦下（request:fail url not in domain list）
```
**preflight 8 项全绿，只卡在小程序侧网络**。解除条件：微信开发者工具 →「详情」→「本地设置」→ 勾「不校验合法域名…」（本机一次性人工动作，Kevin 尚未完成）。**没有为了变绿去改 preflight**。

替代证据：
- `node test/e2e/self-test.mjs` → **72/72**（含新加的两页可达性夹具）
- `node test/e2e/build-dist.mjs development` → exit 0，两页进 `app.json`
- `pnpm test` → **294 全绿**；`pnpm type-check` / `pnpm lint` → 0 错

## orders flow 写了什么（域名开关一勾就能真跑）

`test/e2e/flows/orders.mjs`，拆 `run(mp)` + `runWith(mp, data)` 两段好让 self-test 零环境跑：
1. 列表页可达 + **卡片订单号与后端 `/app/gz/jp/order/list` 逐条比对**（前端塞假数组过不了）
2. 四个状态 tab 齐
3. 两跳可达详情页
4. ★ **抓页面上所有运单号文本，去重前后数量必须相同**；后端有几个不同单号页面就该显示几个
5. 分组数与**独立重算**的期望一致（flow 自己算一遍，**不 import `detail.logic`** —— oracle 必须独立于被测实现，否则实现和断言一起错就一起绿）；购买失败组排最后
6. 退款文案：`refunded` 显金额、处理中**绝不漏具体金额**
7. 整页 wxml 扫「包裹」二字

## 风险提示 / 已知 issue

1. **两个页面未经真模拟器渲染**（同 D2-D5 的所有 mp 页）。功能与数据流由 294 单测 + LIVE 契约覆盖，**视觉与真机交互未验**。
2. **30 款订单的滚动性能没测过**：分组后组数少，但单页仍可能渲染 30 个商品行。真机上的滚动流畅度需要抽验时看。
3. **快递中文名是前端映射表**（`CARRIER_NAMES` 9 项）——因为 mp 的 `GzJpOrderItemVO` **只下发 `carrierCode` 没有 `carrierLabel`**（对比 `fulfillStatusLabel`/`refundStatusLabel` 后端都给了）。**正解是后端 VO 补一个 `carrierLabel`，补上后删掉这张表**。目前未知编码显示空串（只显示单号），不回落成原始编码。
4. **`refund_failed` 对客人显示「退款处理中」** —— 刻意不暴露「失败」（107 报告要求：那是内部状态，多半几分钟内被店员重试好了）。**代价**：真的退款卡住时客人看不出异常，只能靠客服出口。这是产品选择不是 bug。
5. **待 Kevin 残留人验**：两个新页的**首版视觉拍板**（按项目约定新页首版视觉需人看）。不碰真机微信原生能力，无支付相关。

## 对下游 GZ-JP-301（联调回归上线）的提示

**mp 端整体还差什么**（本卡收尾时的观察）：
1. ★ **全部 6 个 flow（smoke/login/home/product/cart/checkout/orders 共 7 个）从未在真模拟器上跑通过一次** —— 全卡在「不校验合法域名」这一个 GUI 开关。这是上线前**最大的单点残留**，勾一次就能一次性解锁 7 个 flow 的真跑。
2. **真机 1 分钱支付**（wxMOCK 期物理拉不起真收银台）—— appid 回补后必跑，D1 报告已列清单。
3. **首版视觉拍板**：首页/场详情/商品详情/购物车/下单确认/支付结果/订单列表/订单详情 共 8 个新页，一个都没被人眼看过。
4. **`gz.home.banners` 是与谷子宇宙共用的 sys_config key**（201 报告风险 1）——运营一配 banner，拼团首页会跟着显示拼豆的图。**建议在运营开始配 banner 之前**排掉。
5. 图片是 MinIO 预签名 **1h 过期**，长时间停留后图会 404（各页已 `@error` 兜占位块）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A ✅（#1 环境阻塞除外），待 Tier 1B**

建议覆盖：`pnpm test`（294）/ `self-test`（72）/ 后端契约 curl；**域名开关解锁后跑 `node test/e2e/run.mjs all`**（7 个 flow，这是本项目第一次全量真跑，最有价值）；重点看 orders flow 的「同一运单号只出现一次」在真渲染下是否成立（单测锁的是逻辑层，真页面模板可能另有重复渲染）。
