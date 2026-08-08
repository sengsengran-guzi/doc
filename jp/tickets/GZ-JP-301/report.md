# GZ-JP-301 完工报告 — 联调回归与上线

> **accept #2（新小程序全量 E2E）★ 7/7 全绿 —— 本项目第一次全量真跑通过**；**accept #3（Flyway）PASS**。
> **accept #1（老小程序全量回归）BLOCKED** 于本机 devtools 的**每工程独立** GUI 开关（Kevin 只给 miniapp-jp 勾过），
> 已用不依赖模拟器的手段把「D1 多 appid 改造有没有伤到老小程序」这个问题**单独回答清楚了：没有**（见下）。
>
> 过程中**逮到 1 个真产品缺陷**（购物车改数量会把人带走）和 **3 个 harness 缺陷**，全部已修。

## accept 逐条

### #2 新小程序全流程 E2E ✅ 7/7

```
$ cd code/main/miniapp-jp && node test/e2e/run.mjs all
=== flow: smoke ===     [PASS] smoke
=== flow: login ===     [PASS] login
=== flow: home ===      [PASS] home
=== flow: product ===   [PASS] product
=== flow: cart ===      [PASS] cart
=== flow: checkout ===  [PASS] checkout
=== flow: orders ===    [PASS] orders

[run] 结束：7/7 flow 通过     EXIT=0
```

打的是**真模拟器 + 真本地后端 + 真库**，不是 mock。链路覆盖：
首页 → 场 → 商品 → 加购 → 购物车 → 去结算 → 地址 → 提交下单（真落库 `JPO-20260809-000005`）
→ mock 支付驱动结算（订单 `paid`、商品行进 `purchasing`）→ 支付结果页 → 订单列表 / 详情。

### #3 两库迁移全部应用且无 pending ✅

```
$ docker exec sensenran-dev-mysql mysql ... -e "SELECT COUNT(*) FROM flyway_schema_history WHERE success=0" | grep -qx 0
ACCEPT3 PASS (success=0 的迁移 0 条)
```
本项目 10 个 jp 迁移全部 `success=1`（101 建表+seed / 102 建表+seed / 104 车 / 105 单+seed / 107 退款 / 108 菜单 / 109 菜单）。

### #1 老小程序全量回归 ⛔ BLOCKED（环境，非代码）

```
$ cd code/main/miniapp && node test/e2e/run.mjs all
[FAIL] ×6   Cannot destructure property 'rawPath' ...      ← 老 harness 没有 launch 重试
（改成逐 flow 独立进程重跑后）
  tour ✅   kevin-check ✅   smoke ❌   login ❌   focus ❌   daypass ❌
```

**但 `tour` / `kevin-check` 的 PASS 不能当数据面通过用** —— 看截图才发现问题：

![](file:///tmp/gz-e2e-shots/tour_pages_bean_my-list.png) `我的预约` 页显示「**加载失败，下拉重试**」，
`资讯中心` 页同样「加载失败」。**老 harness 只断言"页面落对了 + 渲染出 N 个 view"，不断言数据加载**，
所以数据全挂它照样报 PASS。这本身是老 harness 的一个真缺陷（见「发现的 harness 缺陷」#4）。

根因用 jp 那套 app 侧探针测死了：

```
[probe] ❌ 老小程序打不到本地后端：小程序侧 wx.request 被域名校验拦下（request:fail url not in domain list）
```

**「不校验合法域名」这个开关在微信开发者工具里是【每个工程独立】的**，Kevin 之前只给
`miniapp-jp` 勾过，`miniapp` 那个工程还没勾。两个 dist 的 `project.config.json` 都是
`setting.urlCheck=false`，**压不住它**（harness 注释里已实测记录：改配置 / 换 appid / 换路径 / cli 重开都没用，只能 GUI 勾一次）。

**没有为了变绿去改 preflight 或降级断言**（那是把硬 gate 变成假绿）。
解除办法（Kevin，一次性 30 秒）：微信开发者工具 → 打开 `code/main/miniapp/dist/build/mp-weixin`
→ 右上「详情」→「本地设置」→ 勾「不校验合法域名…」→ 我再重跑一次即可。

#### 「D1 多 appid 改造有没有伤到老小程序」—— 用不依赖模拟器的手段单独回答：**没有**

这才是 accept #1 真正要回答的问题。四条独立证据：

1. **本项目从未改过老小程序的源码**。老仓工作区 `git status --porcelain` **0 变更**，
   最后一次提交 `59635d4 2026-07-27`，而本拼团项目 **2026-08-06** 才开工；
   `git log --since=2026-08-05 -- src` **为空**。⇒ 只可能经由**共享后端**影响它。
2. **老小程序的 clientid 走多 appid 后端登录正常**（这正是 D1 唯一改到的面）：
   ```
   $ curl -X POST /app/gz/common/auth/wx-login -H 'clientid: mp-applet-sensenran-guzi' -d '{"code":"mock-code"}'
   {"code":200,"msg":"操作成功","data":{"token":"eyJ..."}}     ← 解出 clientid=mp-applet-sensenran-guzi, tenantId=1001
   ```
   （顺带印证配置注册齐全：故意传错 clientid 时后端报 `已配置：[mp-applet-sensenran-guzi, mp-applet-gz-jp]`。）
3. **老小程序在用的业务接口仍正常返数据**：`/app/gz/news/article/list` 匿名 200 / `total=5`。
   即页面上的「加载失败」是**模拟器网络被拦**，不是后端坏了。
4. **D1 的改动面**（`WxMiniappProperties` / `WxAdapterDispatcher` / `WxAppResolver`）只经过
   wx 登录 / 手机号 / 头像昵称 / 支付 / 发货上报；而 4 个红 flow 断言的是资讯列表渲染、
   登录页按钮、回收详情 view 数、拼豆日期步骤 —— **没有一条经过这些代码**。

**结论**：无 D1 回归证据；D1 唯一真实改动面（老 clientid 的多 appid 登录）实测为绿。
**诚实边界**：我**没有**跑到"老小程序全量 E2E 绿"这一步，也**没有** pre-D1 基线可比对。
上线前建议 Kevin 勾一次开关让我把老小程序全量回归真跑完（见「残留」）。

## ★ 逮到的真产品缺陷：购物车点「＋」会把人带离购物车

**现象**：cart flow 报「改数量后合计没刷新：页面=null」。

**根因**（不是合计不刷新，症状离病因很远）：mp 里**原生 tap 会穿过自定义组件边界往上冒泡**。
`BizStepper` 的加减按钮用的是 `@tap`（编译成 `bindtap`），而购物车行
`<BizCartItem @tap="onItemTap">` 编译出来是组件标签上的 `bindtap` ——
点「＋」在改数量的**同时**触发了行点击 `uni.navigateTo(商品详情)`。
数量确实改对了、库也落了，但人已经跳走，页面所有断言自然全查空。

编译产物实证：
```
dist ... <biz-cart-item ... bindtap="{{item.d}}"/>          ← 行点击（跳商品详情）
dist ... class="...biz-stepper__plus..." bindtap="{{e}}"    ← 修前：冒泡上去
dist ... class="...biz-stepper__plus..." catchtap="{{e}}"   ← 修后：就地消费
```

**修**：`BizStepper` 加减按钮改 `@tap.stop`（`catchtap`），并在组件头写明**别改回去**的理由。
同组件的勾选框 / 删除本来就写了 `@tap.stop` —— 作者知道这个坑，只是漏了 stepper。

修后：`✓ ★ 改数量实时刷新合计：¥80 → ¥160（后端 qty=2）`。

**波及面**：`BizStepper` 只用在购物车行与商品详情两处；商品详情没有行级点击，无影响。

**顺带加了一条精确回归断言**（原来的失败信息指向症状不指向病因）：
```js
// 点完「＋」先确认人还在购物车
if (!pathAfterQty.includes('pages/cart/index')) fails.push(`★ 点「＋」改数量把人带离了购物车：当前页=${pathAfterQty}...`)
```

## 发现并修掉的 harness 缺陷（4 个，都会造成"假红"）

| # | 缺陷 | 后果 | 处置 |
|---|---|---|---|
| 1 | `run.mjs` 硬超时 **240s 是整轮预算**，却是照单 flow 定的 | 跑 `all`（7 flow）最后一个必被砍，报成 flow 挂了 | 改成 `flow 数 × 240s`，可用 `MP_E2E_TIMEOUT_MS` 覆盖 |
| 2 | 7 个 flow **共用一个 automator 会话** | 逐个往下烂：先是深层页查不到元素，最后连首页场卡都查不出（同时刻后端 curl 一切正常）。实测 3/7 → 换成独占会话后 **7/7** | 每个 flow 独占一个全新会话，跑完即断（+10-20s/flow，很值） |
| 3 | 跳页后用固定 `sleep(2500)` 等接口驱动的元素 | 商品卡挂在 `v-else`（loading/failed/空 三分支之后），接口慢一点就报「没有商品卡」 | 新增 `deepWait()` 轮询等待（命中即返回，等不到照样失败，**不放宽断言**） |
| 4 | **老 miniapp harness 没有 app 侧后端可达性 gate** | 数据全部加载失败，flow 仍报 PASS（`tour`/`kevin-check` 就是这么"绿"的） | ⚠️ **未修**（属老仓，见「未做的事」） |

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游 108/109/205 已完成 | ✅ D5 QA 门已过 |
| 老 miniapp 仓工作区干净、未被本项目污染 | ✅ `git status --porcelain` = 0；最后提交 2026-07-27 |
| Kevin 在飞的 GZ-BEAN-053 改动未被碰 | ✅ 全程未动 `ruoyi-gz-bean/**`、`plus-ui` 的 gz-bean 文件 |
| Flyway 无失败迁移 | ✅ accept #3 |
| 甲方四件行政事项 | ⛔ 未完成（备案/类目/商户号绑定）→ **按本卡 §0 只能到 staging，不能上 prod** |

## 未做的事（诚实列明，不是漏了）

1. **staging / prod 部署**：需要 Kevin 的服务器凭据 + 甲方行政事项（ICP 备案 2-3 周是最长杆）。本卡只做到"代码与迁移就绪"。
2. **真机 1 分钱支付（新旧各一遍）**：wxMOCK 下物理拉不起真收银台，必须真机 + 真 appid + 商户号绑定后由 Kevin 跑。
3. **微信发货信息上报验证**：同上，依赖真实支付单。
4. **老 miniapp 的 3 个既有单测失败**（`token.test.ts` 的 `silentWxRenew` ×2、`MeHeader.test.ts` ×1）：
   工作区与 HEAD 逐字节一致 ⇒ **在 2026-07-27 那个 commit 上就是红的**，与本项目无关。
   ⚠️ **但值得 Kevin 单独看一眼**：`silentWxRenew()` 返回 false 意味着**静默续期失败 → 用户被踢去重登**。
   本卡**没有替它改**（属拼豆域、且 Kevin 正在该仓域内有在飞改动，越界改反而危险）。
5. **老 miniapp harness 的可达性 gate**（上表 #4）：同属老仓，未改。补它的收益很大（否则老仓 E2E 的"绿"信不过）。

## 风险提示

1. ★ **老小程序 E2E 的"绿"目前信不过**（harness 缺陷 #4）。在补上 app 侧可达性 gate 之前，
   不要拿 `tour`/`kevin-check` 的 PASS 当"老小程序没问题"的证据。
2. **`gz.home.banners` 是与谷子宇宙共用的 sys_config key**（201 报告风险 1）——运营一配 banner，拼团首页会跟着显示拼豆的图。**建议在运营开始配 banner 之前排掉**。
3. **8 个 mp 新页 + 1 个 admin 看板页从未被人眼看过**（视觉首版拍板未做）。功能有 E2E 背书，视觉没有。
4. 图片是预签名 **1h 过期**，长时间停留后会 404（各页已 `@error` 兜占位块）。

## 对下游 / 上线的提示

上线前残留已汇总在 [doc/jp/GO-LIVE-CHECKLIST.md](../../GO-LIVE-CHECKLIST.md)（4 桶：appid 回补 / 甲方行政 / Kevin 真机人验 / prod 部署缺口）。
本卡新增两条进该清单：
- **老 miniapp 工程的「不校验合法域名」需勾一次**，否则老小程序回归永远真跑不了；
- **老 miniapp 3 个既有单测红**（含 `silentWxRenew`），建议上线前单独查一次。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A：accept #2 / #3 ✅，#1 环境阻塞**

建议覆盖：新小程序 `run.mjs all` 重跑一遍确认 7/7 稳定（不是一次侥幸）；
`pnpm test`（miniapp-jp 294）/ `self-test`（72）；
**重点复核本卡对 accept #1 的"无 D1 回归"结论是否成立**（那是推理 + 旁证，不是全量真跑）。
