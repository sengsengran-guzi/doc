# GZ-JP-001 完工报告 — miniapp-jp 工程初始化

**结论：accept 两条全 PASS（exit 0）**，另附 AC 要求但不在 accept frontmatter 里的 type-check / lint / vitest 全绿。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| appid 策略确认 | ✅ 一期 wxMOCK 占位（Kevin 2026-08-06），不等真 appid，本卡可 close |
| `ls code/main/miniapp/` 源工程完好 | ✅ 45 项、src 30 子项，`git status` clean（HEAD `59635d4`） |
| `code/main/miniapp-jp/` 不存在（全新目录） | ✅ 创建前确认，非覆盖 |
| 后端 D1 已 commit（clientid 已登记） | ✅ RuoYi-Vue-Plus HEAD `82af7f60f`（本卡未改动） |
| 蓝图引用可读 | ✅ FLOW:F-JP-00.step1 / UI:global.theme |
| 其余仓未被污染 | ✅ miniapp / RuoYi-Vue-Plus / plus-ui 工作区 clean |

**蓝图关键约束摘录**
- `UI:global.theme`：token 真源 = `miniapp-jp/src/style/`，**从现有 miniapp 复制不改值**；★ 组件禁止硬编码 hex → 本卡新写的首页 / 我的 / 登录页全部只用 `var(--c-*)`。
- `FLOW:F-JP-00.step1`：请求带 `clientid`，本小程序恒为 `mp-applet-gz-jp`；clientid 是纯字符串比对不查 `sys_client` → 写错直接报「未配置的小程序客户端」而非静默串号。

## 实现摘要

新仓 `code/main/miniapp-jp/`（**独立本地 git 仓，无远程**，首个 commit `637d7d6`，256 files / 47970 insertions，源码 756K + unibest CLI 1.6M，工作区 clean）。

复制方式：`rsync -a` 从 `code/main/miniapp/`，排除 `node_modules/ dist/ .git/ docs/ test/ .github/ .changeset/ .cursor/ .trae/ .codebase-memory/ private.*.key` 与插件生成物（`src/pages.json`、`src/manifest.json`、`src/types/{components,uni-pages,async-*}.d.ts`，构建时自动重建）。`src/test/setup.ts` 与 `packages/cli/dist/index.js` 被 `test/`+`dist/` 排除规则误伤，已单独回补。

**保留**（按 What）：

| 目录 | 文件数 | 内容 |
|---|---|---|
| `src/http/` | 8 | `http.ts`（**401 静默续期 + 队列重放**原样）/ `interceptor.ts`（注入 clientid + Authorization）/ alova / types |
| `src/store/` | 4 | `token.ts`（sa-token + `silentWxRenew`）+ test / `user.ts` / `index.ts`（去 current-store 导出） |
| `src/hooks/` | 5 | `useAuth.ts`（wxMOCK 短路 / silentLogin / ensureLoggedIn / logout）/ useRequest / useScroll / useUpload |
| `src/components/biz/` | 18 | BizButton / BizPanel / BizScreen / BizState / BizTag / BizSectionTitle / BizStepTitle / BizFixedCta / BizMangaTitle / BizMasthead / BizScreentone / BizSpeechBubble / BizHomeBanner / MeGrid / MeHeader(+test) / AvatarUpload + 合规件 **BizLoginSheet** |
| 登录合规链 | — | `composables/useLoginConsent.ts`（默认不勾选 + 「同意一次」持久化）/ `pages/agreement/index.vue` + `locale/agreement.zh-CN.ts` |
| 样式 token | 3 | `src/style/c-tokens.scss` **字节未改**（方案 A）+ index.scss（仅改注释）+ iconfont.css；`uno.config.ts` 原样 |
| 测试 | — | `vitest.config.ts` + `src/test/setup.ts`（uni/wx 全局 mock）+ 6 个 test 文件 |

**删除**：页面 `pages/{bean,gacha,news,ord,order,pay,recycle,test}` 与 `pages/me/{address,staff-orders,collection*,coupons*,orders*,order-detail*}`；api `gz-bean / gz-gacha / gz-news / gz-ord(+目录) / gz-recycle / gz-staff / staffOrder / gz-coupon / gz-test / types/order`（含各自 test）；Biz 业务组件 37 个；composables `useDrawPolling / useExpressCarrier / useOrderList / useOrderSubmit / usePurchaseGuard / useStoreGuard / useStoreList / useNavGuard`；hooks `useStaff`；store `current-store`；locale `bean / coupon / gacha / news / ord / recycle / staff`；tabbar 图标 `bean* / recycle* / gacha*`。

**超出「删业务页面」的两处判断（需知会）**：
1. **客服链路整条删除**（`api/customer-service` + `store/customer-service` + `composables/useCustomerServiceConfig` + `locale/customer-service` + App.vue 预热）。理由：唯一 UI 载体 `BizCustomerServiceFab` 在 guzi 里已 `CS_ENABLED = false` 下线，JP `ui-index.yaml` 也无客服位 → 留着是无入口死代码。要恢复：从 `code/main/miniapp` 整条 4 文件 + Fab 回搬。协议正文里「通过小程序内客服入口联系」相应改为「通过运营方公示的联系方式」（避免协议描述不存在的功能）。
2. **`utils/toLoginPage.ts` 删除**：unibest 遗留，硬编码 `'/pages/login/login'`（本工程登录页是 `/pages/login/index`，路径本就错），且全仓零引用。

**改配置**：

| 文件 | 关键改动 |
|---|---|
| `.env` | `VITE_APP_CLIENT_ID='mp-applet-gz-jp'`、`VITE_UNI_APPID='__UNI__GZJP01'`、`VITE_APP_TITLE='谷子宇宙拼团'`、端口 9100（避开现有 9000） |
| `.env.development` | `VITE_WX_APPID='wxMOCKMOCKMOCKMOCK'`、后端 `http://localhost:8080`、`VITE_MOCK_PAY=true` |
| `.env.staging` / `.env.production` | `VITE_WX_APPID='wxMOCKMOCKMOCKMOCK'`、后端沿用 `https://guzi.tianda.studio` |
| `pages.config.ts` | 标题「谷子宇宙拼团」、导航栏 `#FFFFFF` / 底 `#F4F2ED`（对齐 c-tokens 实际值） |
| `src/tabbar/config.ts` | **2 格：首页 `pages/index/index` / 我的 `pages/me/index`**；去 SHOW_*_TAB 开关、去测试 tab、去 mp-alipay `customize` 分支 |
| `package.json` | name `sensenran-guzi-miniapp-jp` / version 0.1.0 / description 与来源说明 |
| `eslint.config.mjs` | ignores 增 `packages/**` 与 `src/customize-tab-bar/**` |
| `.gitignore` | 未改 —— 原本就有 `private.*.key`，覆盖 appid 回补阶段的上传私钥 |

**新写 / 重写页面（3 个）**：
- `pages/index/index.vue` — 首页 tab（`type:'home'` 启动落地）：报头 + 登录态卡（未登录点「微信登录」→ `ensureLoggedIn` 弹协议 sheet；已登录显昵称、点进个人资料）+ 场次占位 `BizState`。真实内容由 **GZ-JP-201** 按 `UI:mp.home` 实装。
- `pages/me/index.vue` — 我的 tab：MeHeader 两态 + 入口格（当前仅「关于」）+ 退出登录，订单入口留了明确落点注释给 **GZ-JP-205**。
- `pages/login/index.vue` — 整页登录（**兜底路径**，非主入口）：修掉原来跳 `/pages/bean/index` 的死链 → 统一回首页 tab；去掉已删的客服浮层；文案改拼团口径。

**文案 / 协议本地化**：新增 `locale/home.zh-CN.ts`；`user.zh-CN.ts` 裁到 `user.home.*` + `user.profile.*`；`common.zh-CN.ts` 只留 `common.*`。`agreement.zh-CN.ts` 改写为**代购口径**（服务内容 = 拼团场次/下单/履约进度/物流单号/退款；明确「线下现场货源不确定 → 未购得按该款实付金额退款」；价格含寄送费用无运费行）。⚠️ 顶部「法务确认项」提示保留，正文仍属草拟。

## AI 自测（raw output）

**1. 依赖安装**（accept 前置，`--frozen-lockfile` 通过 = lockfile 与 workspace 一致）
```
$ pnpm install --frozen-lockfile
packages/cli prepare$ pnpm build
. prepare$ pnpm init-husky & pnpm init-baseFiles
packages/cli prepare: ESM dist/index.js 53.88 KB  ESM ⚡️ Build success in 20ms
Done in 11.2s using pnpm v10.10.0
```

**2. accept 断言 #1（逐字，`rm -r dist` 后从零构建）**
```
$ rm -r code/main/miniapp-jp/dist
$ cd code/main/miniapp-jp && pnpm install --frozen-lockfile >/dev/null 2>&1; \
  pnpm build:mp >/dev/null 2>&1; pkill -f 'cli -o' 2>/dev/null; \
  test -f dist/build/mp-weixin/app.json && grep -q 'pages/index/index' dist/build/mp-weixin/app.json
ACCEPT#1 exit=0
```
产物 `dist/build/mp-weixin/app.json`：
```json
{
  "pages": ["pages/index/index","pages/agreement/index","pages/login/index",
            "pages/me/about","pages/me/index","pages/me/profile"],
  "window": { "navigationBarTitleText": "谷子宇宙拼团",
              "navigationBarBackgroundColor": "#FFFFFF", "backgroundColor": "#F4F2ED" },
  "tabBar": { "custom": false, "color": "#857D70", "selectedColor": "#33B36B",
    "list": [
      { "iconPath": "static/tabbar/home.png", "selectedIconPath": "static/tabbar/homeHL.png",
        "pagePath": "pages/index/index", "text": "首页" },
      { "iconPath": "static/tabbar/me.png",   "selectedIconPath": "static/tabbar/meHL.png",
        "pagePath": "pages/me/index",    "text": "我的" } ] }
}
```
`project.config.json` → `"appid": "wxMOCKMOCKMOCKMOCK"`（一期占位，符合决策）。

**3. accept 断言 #2（逐字）**
```
$ grep -q "mp-applet-gz-jp" code/main/miniapp-jp/.env && \
  ! grep -rq "wx2f8b93e09703f07d" code/main/miniapp-jp/.env*
ACCEPT#2 exit=0
```

**4. 全仓反残留 grep（AC「全仓 grep 不到旧 appid / clientid」）**
```
$ grep -rn "mp-applet-sensenran-guzi\|wx2f8b93e09703f07d" code/main/miniapp-jp/ \
    --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.git
grep exit=1 (1=无命中，符合预期)

$ grep -rl "wx2f8b93e09703f07d" code/main/miniapp-jp/     # 连 node_modules/dist 一起扫
(空)
```
> 旧 appid 曾潜伏在 `src/store/token.test.ts`（不在 `.env*`，accept #2 照不出）——已换中性占位 `wxJPREALAPPID0001`；`.github/workflows/upload-mp-staging.yml` 里的旧 appid 随整个 `.github/` 未复制而消失。

**5. type-check / lint**
```
$ pnpm type-check
> vue-tsc --noEmit
tc exit=0            # 无输出 = 无类型错误

$ pnpm lint
> eslint
lint exit=0          # 无 problem 输出
```
lint 从 **958 problems** 降到 0 的路径（源仓 miniapp 同命令 **1403 problems**，从未绿过——新仓不继承这笔债）：`pnpm lint:fix` 自动修 869 条 → 剩 89 条中 86 条来自 `packages/**`（unibest CLI 模板素材）与 `src/customize-tab-bar/**`（`Component()` 全局）→ 加进 ignores；最后 3 条手改（`tabbar/config.ts` 去 `process` 全局、`scripts/bump-version.js` 两行多语句拆行）。

**6. 单测**
```
$ pnpm test
 ✓ src/api/gz-common.test.ts (8 tests)      ✓ src/api/gz-user.test.ts (4 tests)
 ✓ src/utils/watermark.test.ts (9 tests)    ✓ src/composables/useCountdown.test.ts (7 tests)
 ✓ src/store/token.test.ts (7 tests)        ✓ src/components/biz/MeHeader.test.ts (8 tests)
 Test Files  6 passed (6)
      Tests  43 passed (43)
```
修了 3 个**从源仓继承的 red**（已在 `code/main/miniapp` 复现同样 3 个失败，非本卡引入）：
- `token.test.ts × 2`：`silentWxRenew` 后加了「同意一次」门控（`hasAgreedPrivacy()` false 直接 return），用例没跟着更新 → 恒 false。修 = 用例前置 `uni.setStorageSync('gz_privacy_agreed', true)`；**另补 1 条门控用例**（未同意 → 返 false 且不调 `getWxCode`/`wxLoginGz`，守「不偷偷把游客登录回去」）。
- `MeHeader.test.ts × 1`：断言早已删掉的「收藏占位」DOM → 换成断言未设头像时的补全引导副标。
- `gz-common.test.ts` 因删 `fetchBeanHomeBanner` 整体重写为 `fetchHomeBanners` 的 6 条兜底用例。

**7. tabbar 图标重生成（顺带修的视觉不一致）**：源仓 `homeHL.png` 是旧朱红 `#E73E2A`，而 `selectedColor` 早已是品牌绿 `#33B36B`——选中态「图标红、文字绿」。新仓改 `scripts/gen-tabbar-icons.mjs`（删拼豆图标、active 改品牌色）并重跑：
```
$ node scripts/gen-tabbar-icons.mjs
inactive(墨黑 #1A1A1A) + active(品牌 #33B36B)，80×80 透明底：
  home.png 80x80 非透明像素=1714   homeHL.png 80x80 非透明像素=1714
  me.png   80x80 非透明像素=1448   meHL.png   80x80 非透明像素=1448
$ node -e "...读 PNG 实际像素..."
home.png [ '26,26,26' ]   homeHL.png [ '51,179,107' ]   # = #33B36B，与 selectedColor 一致
me.png   [ '26,26,26' ]   meHL.png   [ '51,179,107' ]
```

**8. git**
```
$ git log --oneline -1
637d7d6 feat: init miniapp-jp scaffold (GZ-JP-001)
$ git show --stat HEAD | tail -1
 256 files changed, 47970 insertions(+)
$ git status --short | wc -l
0
# 其余仓未被污染
miniapp        staging  59635d4  (clean)
RuoYi-Vue-Plus staging  82af7f60f (clean)
plus-ui        staging  eb1d47a  (clean)
```
**做了 commit / 没做 push**：新仓 `git init` 分支 `main`，**未配任何远程**——按 phase-plan「多仓拓扑」远程「待建」，Kevin 之后自建 `github:sengsengran-guzi/miniapp-jp` 再关联。**未向 doc / RuoYi-Vue-Plus / plus-ui / miniapp 任何仓提交**。

## 风险提示 / 已知 issue

1. **未跑模拟器**：本卡只验到「能构建 + 类型/lint/单测绿」，**没在微信开发者工具里真跑过页面**（E2E harness 是 GZ-JP-002 的交付物）。三页实际渲染与登录链路由 GZ-JP-002 + kevin-qa Tier 1B 首次真验。
2. **wxMOCK 期不能上传体验版**：`scripts/upload-weixin.js` 有硬闸——appid 以 `wxMOCK` 开头直接抛错。这是对的（防误传），但意味着 appid 回补前 CI/体验版链路不可用。
3. **`gz.home.banners` 是与现有小程序共用的 sys_config key**：直接复用会让拼团首页显示拼豆 banner。已在 `api/gz-common.ts` 的 `GZ_CONFIG_KEYS` 写明，**GZ-JP-201 落首页前必须先定**：复用同一批，还是后端另开 `gz.jp.home.banners`。
4. **`packages/cli`（unibest CLI，1.6M）保留未删**：它是 `pnpm-workspace.yaml` 成员 + `pnpm-lock.yaml` 的 importer，删了会让 `--frozen-lockfile`（accept #1 前置）直接失败。已用 eslint ignore 隔离；真要清得连 workspace 配置一起去掉并重生成 lockfile，属独立小卡。
5. **协议正文仍是草拟**：法务确认项（公司全称/信用代码/ICP/联系方式/退款时效/管辖地）未落实；隐私政策条目提审前需与新小程序后台「用户隐私保护指引」逐项对齐。
6. **`api/gz-pay.ts` 保留但未接业务**：里面是 guzi 的测试单端点（`/system/gz/pay/test/*`）+ 通用 `getPayStatus`。GZ-JP-204 接支付时按 jp 订单端点重写，别直接照用测试单接口。
7. sass `mixed-decls` deprecation warning（`BizFixedCta.vue` 等）构建期刷屏，**源仓同款**，不影响产物。

## 对下游 ticket 的提示

**GZ-JP-002（登录打通 + E2E harness）**
- **E2E harness 本卡没带**（`test/e2e/` 整目录未复制，flows 全是拼豆/回收的）。可从 `code/main/miniapp/test/e2e/` 移植四件套：`run.mjs`（flow 注册表 + 硬超时 + 退出码语义）/ `preflight.mjs` / `mp-e2e.mjs`（uni-automator launch）/ `build-dist.mjs`，flows 重写。源 harness 的 `dist` 默认指向 `dist/build/mp-weixin`。
- **登录链路已就绪、无需重写**：`useAuth.loginWithWechat / silentLogin / ensureLoggedIn` + `store/token.silentWxRenew` 原样保留。wxMOCK 下走短路：不调 `uni.login`，直接给后端 `mock-${Date.now()}` 作 code。**你要验的是 clientid 打通**（请求头 `clientid: mp-applet-gz-jp` 由 `src/http/interceptor.ts` 注入，值来自 `.env`）。
- ⚠️ **「同意一次」门控会挡住静默登录**：`App.onLaunch` 的 `silentLogin()` 与 401 续期的 `silentWxRenew()` 都先查 `hasAgreedPrivacy()`（storage key `gz_privacy_agreed`）。E2E 不先同意会看到「启动后仍是游客态」——**设计如此**（微信合规），不是 bug。可选：① 走 UI 勾选 + 「微信登录」；② 前置 `wx.setStorageSync('gz_privacy_agreed', true)`。
- **可达路径（AC X(a) 用）**：`pages/index/index`（首页 tab，启动落地）、`pages/me/index`、`pages/me/about`、`pages/me/profile`、`pages/agreement/index?type=service|privacy`、`pages/login/index`。**共 6 页，全部可 `reLaunch` 直达**。首页按钮选择器 `.jp-hero__cta`；我的页头部 `.me-header__top`、退出 `.logout-btn`。

**GZ-JP-201（首页）**：首页现为占位实现，直接改 `src/pages/index/index.vue`。`BizHomeBanner`（swiper + 占位 slide + `emit('tap', link)`）与 `fetchHomeBanners()` 已保留，但先解决「风险 3」的 key 归属。场卡片/角标用 `BizPanel` + `BizTag` + `BizSectionTitle`，倒计时用 `useCountdown`（已保留+有单测），空态统一 `BizState`。

**GZ-JP-205（订单）**：「我的」页 `gridItems` / `ROUTE_MAP` 已留订单入口落点（`src/pages/me/index.vue` 第 42-57 行附近），文案 key `user.home.entryOrders` 已在 locale；`LOGIN_REQUIRED_KEYS` 加 `'orders'` 即要求登录。订单文案建议新开 `user.orders.*` scope（`t()` 是 prefix 分发）。

**所有 mp 卡通用**：页面禁止直接撒 `<wd-*>`，统一 `Biz*`（缺件就新建包一层，easycom 自动引入）；禁硬编码 hex，一律 `var(--c-*)`——注意 `--c-red` 是**品牌主色令牌名但当前值是绿 `#33b36b`**（历史令牌名，c-tokens.scss 有注释），`--c-green` 才是「成功/营业中」语义色，别用混；新增 mp 页记得给 `test/e2e/flows/` 补 flow。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**本卡 Tier 1B 说明**：mp 模拟器 E2E 的 harness 本身是 GZ-JP-002 的交付物，本卡尚无 `test/e2e/run.mjs` 可跑；本卡可跑的自动化已在 §AI 自测跑完（构建 / type-check / lint / vitest 43 passed）。建议 Tier 1B 与 GZ-JP-002 合并一次跑（那时 harness 就位，可一并回归本卡 6 个页面的可达性）。

---

**一句话结论：accept PASS**（`ACCEPT#1 exit=0`、`ACCEPT#2 exit=0`），附加的 type-check / lint / vitest(43) 也全绿。
