# 修正：E2E flow 选择器深度回填（GZ-JP-204 之后，D4 QA 门之前）

> 不是正式 ticket，是主线程发现的 E2E harness 缺陷，按 CLAUDE.md §9.5「改源头」原则处理。

## 背景

GZ-JP-204 实施时发现：微信小程序 `SelectorQuery`（automator `page.$`/`page.$$` 底层）**不跨自定义组件边界**。本项目大量元素（`.biz-cart-item__name`、`.jp-event-card`、`.login-agree__box`、`.me-header__top` 等）定义在 `src/components/biz/**` 组件内部，直接查一律 `null`/`[]`——「页面上不应该出现 X」这类否定式断言因此**恒为真**，是沉默的测试失效。

204 在自己的 `checkout.mjs` 里用官方 `>>>` 深度选择器语法修了这个问题，主线程随即派单把修复回填到 D2/D3 阶段的 `smoke/login/home/product/cart` 五个 flow。

## ★ 回填时发现：204 的 `>>>` 修法本身在真模拟器上是坏的（第二层同款缺陷）

真连模拟器验证（不只是 self-test）：

```
.jp-screen >>> .me-header__top   → HIT，但拿到的是 .jp-screen 自己（text = 整页文字）
.jp-screen >>> .zzz-根本不存在     → 照样 HIT（同一个节点）      ← 决定性证据
```

`Page.getElement` 在这版 automator 上**只按祖先那半截匹配**，`>>>` 后面整段被忽略。204 换来的不是修好，是把「恒真」从 `$$` 挪到了 `deep`：元素存在类断言恒真、`deepTexts` 取回整页文本而非目标元素文本。204 自己没能跑到真模拟器这一步（devtools 登录当时还没恢复），所以没照出这层。

**真正修法（在 `mp-e2e.mjs` 源头改，`deep/deepAll/deepTexts` 签名不变，六个 flow 与调用方零改动）**：改用 **xpath**——`page.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," foo ")]')`。配套两个坑：`getElementsByXpath` 在这版 automator 直接抛异常（`deepAll` 改走 `(xpath)[n]` 下标逐个取直到拿不到）；`page.xpath()` 未命中时**不返回 null** 而是给一个空壳 Element（缺 `tagName`）——不认这个特征，下标循环永不收敛。

### 真模拟器验证（含真的能不能点）

`deep` 命中/未命中正确、`deepAll` 收敛、`deepTexts('.me-grid__label')` = `["购物车","关于"]`（不再是整页文本）；tap 打通了「首页订单入口 → 弹协议 sheet → 勾选框变 `is-on` → 登录按钮 `disabled` true→false」，即 login flow 的合规闸门那段真跑过了。

### self-test 破坏性验证（证明护栏真的会咬）

原假件对 `page.$` 和 `deep` 一视同仁，改完全绿证明不了什么——已让它复刻真语义（从 `src` 现扫类名归属：组件模板有/页面模板没有 = 组件内部，页面作用域查组件内部一律 `null`/`[]`；新增 `xpath()` 反解析 `toXpath` 的产物；对手写 `>>>` 直接抛）。破坏性验证：把 `cart.mjs` 的 `.biz-stepper__plus`、`home.mjs` 的 `.jp-event-card__name` 退回 `page.$` → **66/72 立刻变红**，恢复后 72/72。

## ★★ 安全发现：模拟器域名白名单里恰好含生产后端域名

`run.mjs` 目前卡在的不是 automator 层，是 devtools **本地设置**里的「不校验合法域名」GUI 开关（一次性人工动作，与文件里任何 `urlCheck` 字段无关，改配置文件改不动这个开关）。这个开关关闭时按**域名白名单**拦：

```
http://localhost:8080/…       ✗ not in domain list
https://guzi.tianda.studio/…  ✓ 200      ← 借用 appid 的合法域名 —— 是生产后端！
```

**⚠️ 由此一条安全红线**：模拟器在开关未勾选时唯一打得通的地址恰恰是生产后端。谁要是拿 production profile 的构建产物去跑 E2E，`cart`/`checkout` flow 会**往生产库真实写单**。`run.mjs` 现有的 `distLooksDev` 前置校验就是拦这个的（构建产物必须确认是 dev profile 才放行跑 E2E），**这条护栏不能被绕过或注释掉**，已写进 `test/e2e/README.md`。

## 五个 flow 各改了几处选择器（共 17 处，逐个 grep 类名归属核实非猜测）

| 文件 | 处数 | 改了什么 |
|---|---|---|
| `smoke.mjs` | 1 + 计数修复 | `.me-header__top`（MeHeader.vue）加 `mustDeep: true`；外加 view 计数口径修复（见下） |
| `login.mjs` | 4 | `.jp-entry-card` / `.login-sheet` / `.login-agree__box` / `.login-sheet__cta`（BizEntryCard、BizLoginSheet） |
| `home.mjs` | 4 | `.hb__img` / `.hb__ph`（BizHomeBanner）、`.jp-event-card__name`（BizEventCard）、`.jp-entry-card` |
| `product.mjs` | 3 | `.jp-event-card`、`.jp-product-card`、`.jp-product-card__name`；顺带删掉因此变成死代码的本地 `textsOf` |
| `cart.mjs` | 5 | `.jp-event-card`、`.jp-product-card`、`.biz-cart-item__name`、`.biz-stepper__plus`、`.biz-cart-item__mask-text` |

`checkout.mjs` 一个字没动（它的调用方式不变，源头 `mp-e2e.mjs` 一改全好）。

## smoke 的 `MIN_VIEWS=3` 确实会假红（非可选，已一并修）

真机数出来：`pages/cart/index`（游客态）、`pages/order/confirm`（空态）**只有 2 个**页面级 view，`product/detail`（取数失败态）也是 2——内容全在 `BizPanel`/`BizState` 里。旧写法这 3 页 + `me/index` 的 marker 共 **4/12 页会假红**。改成「页面作用域 / 跨组件两个口径取大」（跨组件那侧取到阈值就停，省 RPC）。

## 阻塞现状（截至这轮修复完工时）

`node test/e2e/run.mjs smoke`（及其余 login/home/product/cart/checkout）仍卡在**同一个** devtools「不校验合法域名」本地设置未勾选（Kevin 尚未完成这最后一步）。

**绕开 run.mjs 后端硬 gate 的诊断性 probe**（不算 accept，纯验证选择器机制）在真模拟器上跑通 **12/12 页**：

```
✓ /pages/index/index          ✓ /pages/me/index（靠 mustDeep）
✓ /pages/product/detail?id=1  ← 旧码假红，现在真过
✓ /pages/cart/index           ← 旧码假红，现在真过
✓ /pages/order/confirm        ← 旧码假红，现在真过
[probe] smoke PASS
```

login/home/product/cart/checkout 五个需要打后端的 flow 域名开关一勾开就能真跑——跨组件查询机制已在真模拟器上逐条验过，不再是未知数。

## 改动文件

```
code/main/miniapp-jp/test/e2e/mp-e2e.mjs        +103/-  ★ deep/deepAll/deepTexts 改走 xpath（连带修好 checkout）
code/main/miniapp-jp/test/e2e/self-test.mjs     +258/-  组件边界模拟 + xpath 假件 + 3 条 meta 用例
code/main/miniapp-jp/test/e2e/flows/smoke.mjs   +49     mustDeep + 两口径 view 计数
code/main/miniapp-jp/test/e2e/flows/cart.mjs    +25     5 处
code/main/miniapp-jp/test/e2e/flows/home.mjs    +24     4 处
code/main/miniapp-jp/test/e2e/flows/product.mjs +24     3 处 + 删死代码
code/main/miniapp-jp/test/e2e/flows/login.mjs   +11     4 处
code/main/miniapp-jp/test/e2e/README.md         +65     >>> 失效实测 / xpath 三坑 / 域名白名单 + 生产库红线
```

`checkout.mjs`、任何 `.vue`、`src/**` 一行没碰；`pnpm test` 268 全绿；RuoYi / plus-ui / miniapp 三仓 0 改动。

## self-test：72/72（原 69 + 3 条 meta）

3 条 meta 用例守住这套模拟本身不退化成 no-op（含用真 `deep()` 跑一遍 mp-e2e ↔ 假件的闭环）；`ALL_PAGES` 的 view 数按真产物填（`cart`/`confirm`/`result` = 2）。

---

**建议下一步**：Kevin 在 devtools「详情 → 本地设置」勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」后，直接 `node test/e2e/run.mjs all`——六个 flow 应该能真跑了。若 cart/checkout 报断言错，那才是真业务问题，不再是 harness 的假信号。
