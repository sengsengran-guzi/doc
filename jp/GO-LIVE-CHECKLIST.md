# 谷子宇宙拼团一期 —— 上线残留清单

> 分 5 桶：① appid 回补 ② 甲方行政事项 ③ Kevin 人验 ④ prod 部署缺口 ⑤ QA 门产出。
>
> **每一条都逐条拿代码/活库核对过**（不是从完工报告转抄）。判定口径：
> 「文档写得比现实乐观」按 blocker 处理 —— 那会让人在错误认知下上线。
> 已修好的条目直接改写成现状、不留「原来是 X 现在是 Y」的中间态。
>
> **D0 的 GZ-DOC-001/002/003 无 report.md 属正常** —— 那三张卡的产出就是 ADR-0019 / ADR-0020 / CLAUDE.md 本体。

---

## 桶 1：appid 回补清单（真 appid 到位后要改的地方）

phase-plan §「appid 回补清单」列了 6 项，实测下来散落的更多。下面是补全版。

### 1.1 miniapp-jp 侧

| # | 位置 | 现值 → 目标 |
|---|---|---|
| 1 | `.env.development` / `.env.staging` / `.env.production` 的 `VITE_WX_APPID` | `'wxMOCKMOCKMOCKMOCK'` → 真 appid |
| 2 | 仓库根 `private.<appid>.key`（上传私钥，`.gitignore` 已覆盖） | 缺失 → 放置 |
| 3 | `scripts/upload-weixin.js:177` | 硬闸：appid 以 `wxMOCK` 开头直接 throw ⇒ **回补前体验版/CI 上传链路物理不可用**（这是对的，防误传） |
| 4 | `test/e2e/mp-e2e.mjs:66` `E2E_APPID` | 现借用谷子宇宙 appid 让 devtools 能打开工程；真 appid 到位后 `/^wxMOCK/i` 不再命中，自动停止改写 |
| 5 | ★★ **`test/e2e/preflight.mjs:31` 与 `test/e2e/run.mjs:98` 的 dev-profile 指纹写死了字面量 `wxMOCKMOCKMOCKMOCK`** | **见下方「★ 回补时最容易踩的坑」** |
| 6 | `src/manifest.json`（由 `manifest.config.ts` 生成）→ 产物 `project.config.json` | 构建期自动跟随 env，**不用手改** |
| 7 | `src/hooks/useAuth.ts`、`src/store/token.ts` | 运行时按 `VITE_WX_APPID.startsWith('wxMOCK')` 分支，**自动切真链路，零代码改动** |

> **★ 回补时最容易踩的坑**：`run.mjs` 的 `distLooksDev()` 用三个指纹判断产物是不是 dev profile —— `localhost:8080` / `wxMOCKMOCKMOCKMOCK` / `mp-applet-gz-jp`。若按 phase-plan 把**三套 env 都换成真 appid**，这个判定会失败 → preflight **exit 2 挡掉所有 E2E**。
> **处置二选一**：① **dev 保留 wxMOCK、只换 staging/prod**（推荐，dev 本来就该走 mock）；② 同步把这两处指纹换成新 appid。
> 这个连带关系**任何一份 ticket 报告都没提过**，是收尾时读代码发现的。

**注意**：`.env` 的 `VITE_APP_CLIENT_ID='mp-applet-gz-jp'` 是 **clientid 不是 appid**，回补时不动；`VITE_UNI_APPID='__UNI__GZJP01'` 是 uni 侧标识，也不动。

### 1.2 后端配置

| # | 位置 | 动作 |
|---|---|---|
| 8 | `application-prod.yml` | ✅ **已是 `apps:` Map 形态且已含拼团段**，`yml 不用动`。`:281 apps:` → `:283 mp-applet-sensenran-guzi`；`:298 spring.config.activate.on-profile: jp` 段下 `:302 mp-applet-gz-jp`（含 `appid: ${WX_JP_MA_APPID:}` / `secret: ${WX_JP_MA_SECRET:}` / `register-source: mp_wechat_jp`）。<br>⚠️ **别去"切成 apps 形态"** —— 这份配置正承载线上谷子宇宙小程序的登录，改坏 = 现小程序全挂 |
| 9 | `application-dev.yml` | 同样已是 apps 形态含 jp 段，注入 `WX_JP_MA_APPID` / `WX_JP_MA_SECRET` 即切 real |
| 10 | `script/docker/docker-compose.deploy.yml` | ✅ **已透传**：`:116 WX_JP_MA_APPID` / `:117 WX_JP_MA_SECRET`（用 `:-` 可空而非 `:?` 缺失即拒，理由见 `:113-115` 注释）；`:99 SPRING_PROFILES_INCLUDE` 也已透传 |
| 11 | ★★ **部署机 `.env`** | **这才是唯一还没做的一步**，且全清单此前一字未提。prod 的拼团配置段是 `on-profile: jp` 门控的 —— `.env` 里不设 `SPRING_PROFILES_INCLUDE=jp`，那段**根本不加载**，拼团 clientid 在 prod 依旧被拒。三个变量一起加：<br>`SPRING_PROFILES_INCLUDE=jp` + `WX_JP_MA_APPID=<真 appid>` + `WX_JP_MA_SECRET=<真 secret>` |
| 12 | `register-source` | 已在 prod yml 的 jp 段配好 `mp_wechat_jp`，随 profile 生效，无需额外动作 |

### 1.3 相关 Java 类（配置驱动、代码不动，但要知道谁在读）

- `WxMiniappProperties` — `Map<clientid, MiniappApp> apps` + `resolveApps()` + `InitializingBean` fail-fast（`default-client-id` 不在 apps 里 → 启动失败）
- `WxAppResolver` — ⚠️ **两个口径别用错**：`currentApp()` 严格（登录/手机号，未登记 clientid 抛错）vs `currentAppOrDefault()` 宽松（发货上报/access_token/admin/`@Async`/cron）。GZ-SYS-020 §6 是用真机复现换来的教训
- `WxAdapterDispatcher` — `@Primary` 门面，8 个 real/mock Bean 同时在容器里，运行时按 app 分派
- `ProdSecretGuard` — 遍历 `resolveApps()` 逐 app 校验，任一占位/漏配 → **prod 启动被拒并点名 clientid**
- `WxRealAccessTokenManager` — key 已是 `wx:miniapp:access_token:{appid}`；部署后旧 key 变孤儿靠 TTL≤2h 自然消亡，每个 real 小程序首调 miss 一次属正常

### 1.4 支付 / 商户号

- **回补的唯一必要动作 = 配 `wx.miniapp.apps.<clientid>.appid + secret`**；`gz.pay.appid` 与 `gz_pay_channel.appid` **都不需要动**。
- `PayAppidResolver` 三级优先级：① `gz_pay_channel.appid`（按 `client_id` 行，最高优先级显式覆盖）② `wx.miniapp.apps.<clientid>.appid`（**默认走这条**，保证 `payer.openid` 与 appid 同源）③ `gz.pay.appid`（兜底）
- ⚠️ **地雷**：prod `gz_pay_channel` 那行现在 `appid=wx_placeholder_appid`（seed 占位＝视同没配）。**谁手工改成别的值，它会立刻接管收款 appid**，与 `wx.miniapp` 不一致就是「openid 与 appid 不匹配」微信拒付。日本拼团**刻意没建行**。
- 商户号：`mch_id` 两端共用不变；商户号绑定新 appid 是**甲方侧动作**（桶 2 #4）。

### 1.5 用户表

- `gz_user.app_id NOT NULL DEFAULT 'wx2f8b93e09703f07d'` + `uk_tenant_app_openid(tenant_id, app_id, openid)`，真 appid 到位后**自动分家，无需改表**。
- dev 库有 `app_id='wxMOCK'` 的过渡行（`mock-dev-tester` / `mock-jp-tester`），回补时一并核对；**prod 不受影响**。

---

## 桶 2：甲方（客户）侧行政事项

原始清单在 `doc/jp/confirmation/一期范围确认单.md`：

| # | 事项 | 周期 | 状态 |
|---|---|---|---|
| 1 | 注册新小程序（**主体必须与现在收款的商户号一致**） | 数天 | ❌ 未完成 |
| 2 | **给新小程序做 ICP 备案** | **2-3 周，最慢**「办不完新小程序上不了线」 | ❌ 未过 |
| 3 | 申请海淘类目资质 | 1-2 周，可能补材料 | ❌ 未过 |
| 4 | 现有微信支付商户号绑定到新 appid | 数天 | ❌ 未见记录（真机 1 分钱验证依赖它） |
| 5 | 日本员工联系煤炉官方合作 | — | **二期**，一期不阻塞 |

### 微信侧其它申请 —— 逐条结论（避免清单里凭空多列）

- **订阅消息模板**：一期**全项目未接**（grep 不到 `requestSubscribeMessage`）→ **不需要申请**。要「到货通知」是新需求新 ticket。
- **微信客服**：拼团 mp 的客服链路在 GZ-JP-001 被整条删除（guzi 侧早已 `CS_ENABLED=false` 下线）；`MeGrid.vue` 仍保留 `open-type="contact"` 能力但无 item 用它 → **一期不需要**。GZ-JP-205 的「退款失败→客服出口」若要真落地，需先定客服形态。
- **发货信息上报**：拼团**已接**（GZ-JP-301，挂在「店员点发货」那一刻，不在支付回调 —— 支付当下没有可上报的发货事实）。要甲方确认的只剩**商户号侧是否已开通实物商品发货上报**，以及 `receiver_contact` 的掩码口径。
- ★ **服务器合法域名白名单**（报告未列但上线必须）：新小程序后台需把后端域名加进 request 合法域名，否则真机白屏。
- **隐私/法务素材（要甲方提供）**：协议正文仍是**草拟**，法务确认项（公司全称/统一社会信用代码/ICP 号/联系方式/退款时效/管辖地）未落实；提审前需与新小程序后台的「用户隐私保护指引」逐项对齐。文件：`src/locale/agreement.zh-CN.ts` + `src/pages/agreement/index.vue`。

---

## 桶 3：留给 Kevin 的 Tier 2 人验清单

### 3.1 本机一次性动作

| # | 项 | 状态 |
|---|---|---|
| 1 | devtools 扫码登录 | ✅ **已完成** |
| 2 | devtools「不校验合法域名」（**miniapp-jp 工程**） | ✅ **已完成** |
| 3 | 同一个勾（**老 `miniapp` 工程**） | ✅ **已完成**，accept #1 已解锁真跑 |

> ⭐ **这个坑值得记住**：该开关在微信开发者工具里**按「工程路径」存**，`dist/dev/mp-weixin` 与
> `dist/build/mp-weixin` 是**两个不同的工程**。人自然会打开 `dist/dev` 去勾（那是 `pnpm dev:mp` 的产物），
> 而 E2E harness 默认打开 `dist/build` —— 勾了也没用，且现象与「没勾」一模一样。
> 排查方法：`~/Library/Application Support/微信开发者工具/<hash>/WeappLocalData/localstorage_*.json`
> 按 `projectid`（工程绝对路径）索引，里面的 `setting.urlCheck` 就是这个开关。
> **程序化改它没用** —— devtools 一打开该工程就会把 `setting` 覆盖回去（实测）。
>
> 老小程序现在的跑法（用已授信那个路径，不必再勾一次）：
> ```bash
> cd code/main/miniapp
> export MP_DIST="$PWD/dist/dev/mp-weixin"
> node test/e2e/run.mjs all
> ```

> ⚠️ **配套安全红线**：模拟器在该开关**关闭**时唯一打得通的是**生产后端**（借用旧 appid 的合法域名）⇒ 拿 production profile 产物跑 E2E 会往**生产库真写单**。`run.mjs` 的 `distLooksDev` 护栏**不可绕过/注释**。

### 3.2 真机微信原生能力

| # | 能力 | 结论 |
|---|---|---|
| 3 | ★★ **真实支付（真钱 1 分单）** | **必验 4 条**：① 现小程序（谷子宇宙）1 分单全链路 —— **最重要，动的是它正在跑的收款链路** ② 拼团小程序 1 分单 ③ 两小程序**交叉验证**（A 的单不能用 B 的 appid 调起）④ 看日志 `[gz-pay] createJsapiOrder … appid=` / `buildPayParams … appid=` |
| 4 | ★★ **真钱行级部分退款** | **必验且至今零真钱验证**：dev 全程 `MockWechatPayClient`，「微信真的会按行金额部分退款」没验过。做法：真商户号下一笔多行拼团单，标 1 行失败，确认微信侧退款金额 = 行金额而非整单 |
| 5 | ★★ `getPhoneNumber` | **有完整载体，必验**：`pages/me/profile.vue:273-275` 的 `open-type="getPhoneNumber"` + `@getphonenumber` → `src/api/gz-user.ts:90-100 bindMobile` → `POST /app/gz/common/user/bind-mobile`（后端拿该 appid 的 access_token 调 `getuserphonenumber` 换明文）。<br>`:118-120` 在 dev 走 `code='mock-phone-code'` 回落 ⇒ **模拟器路径是假的，只有真机能验**。<br>强依赖「**新 appid 自己**的 access_token + 该 appid 已在微信后台开通『手机号快速验证』」—— 恰是换新 appid 最容易翻车的一项。回补阶段两个 real 小程序同时在线各跑一轮 |
| 6 | 头像昵称授权 | ✅ 有真实载体：`AvatarUpload.vue` 的 `open-type="chooseAvatar"` + `pages/me/profile` 昵称填写 |
| 7 | 微信客服 / 扫码 | 一期无入口 / 无功能 → **N/A** |

### 3.3 新页首版视觉拍板（**13 个 mp 页 + 1 个 admin 页，全部未被人眼看过**）

- **mp 业务 8 页**（重点拍板）：首页 / 场详情 / 商品详情 / 购物车 / 下单确认 / 支付结果 / 订单列表 / 订单详情
- **mp 另 5 页**（同为本项目新建，别漏）：`login/index` / `agreement/index` / `me/index` / `me/about` / `me/profile`
  - `me/profile` 是最大的一个页（11.6KB），承载 `chooseAvatar` + `getPhoneNumber` 两个真机能力
  - `agreement/index` 挂的协议正文仍是草拟稿，待甲方法务落实（见桶 2）
- **admin 1 页**：**履约看板**（43KB）—— 6 个 Playwright 用例覆盖功能与数据流，但「列宽 / 分组展开观感 / 操作条位置」没人看过；**它是店员每天用最久的页**
- 具体要盯的「算出来而没看过」的点：确认页底部两层条 + 安全区（`.jp-confirm__spacer` 220rpx）；购物车 CTA 条 4 元素在 750rpx 下主按钮剩约 310rpx；商品详情 swiper 640rpx / 须知琥珀底醒目度 / 两列网格
- **dev 期视觉噪音（不是 bug）**：场封面全是渐变 + 🎏 占位块（fixture 的 `/static/images/mock-product.png` 在 mp 侧不存在）

### 3.4 真机性能 / 交互（未验）

- 订单详情 **30 款商品行**的滚动流畅度
- 场详情**上拉分页**的手感与触发时机 —— dev fixture 只有 1 件商品，`onReachBottom` **从未触发过**
- 场详情**倒计时每秒重绘**是否卡
- 图片停留 >1h 后的 404 表现（各页已 `@error` 兜占位块）

---

## 桶 4：prod 部署前的已知缺口

### 4.1 调度 / cron

- **SnailJob 未部署**：`snail-job.enabled` prod 默认 false，全后端 **27 个 `@JobExecutor` 一个都不跑**（gz-jp 模块本身 0 个）。
- **但有本地兜底**：`GzLocalPayScheduler`（`gz.local-scheduler.enabled` prod 默认 **true**）用 Spring `@Scheduled` 覆盖三条**资金相关**任务：支付主动查单（90s）/ **发货上传兜底重试**（300s）/ 支付单超时关闭（300s）⇒ 拼豆的发货上报与支付补单在 prod 是活的。
- 与 jp 相关的真实缺口：
  - ★ **jp 未支付订单没有任何超时关单实现** —— 这**不是** cron 没跑，装了 SnailJob 也修不好。`ruoyi-gz-jp` 里没有 job 包、没有任何 `@JobExecutor`；`GzJpOrderMapper.markCancelled` 全项目**无调用方**（死代码）。支付侧的 `GzPayExpireOrderJob` 只把**支付单**标 timeout，不动业务单，且它在 prod 早已被 `GzLocalPayScheduler.payExpire` 覆盖。<br>⇒ prod 的 jp `created` 单会长期堆积（不影响资金）。要修得**单开 ticket**：写 jp 关单任务，或在支付超时回调里挂 `markCancelled`
  - **退款卡单自动补偿没有** ⇒ 事务提交后、调微信前进程挂掉 = 一张永远 `refunding` 的单。兜底做成人可操作：退款单列表把失败/超 10 分钟无回调排最前 + `POST /system/gz/jp/refund/{id}/retry`
  - 设计上**刻意零 cron**的不受影响：场「到点即结束」是读时惰性判定；购物车失效项同理

### 4.2 部署配置缺口

| # | 缺口 |
|---|---|
| 1 | **部署机 `.env` 缺 `SPRING_PROFILES_INCLUDE=jp`** —— 见 §1.2 #11。yml 与 compose 都已就绪，只差这一步；不设则拼团配置段不加载、clientid 在 prod 依旧被拒 |
| 2 | **staging / prod 从未部署过任何 jp 迁移**，待补跑 **18 条**（不是 12）：<br>**建新表类 12 条**：`V202608062249`(pay_channel 加 client_id) / `062251`(gz_user 加 app_id) / `070202`+`070203`(event) / `070232`+`070233`(product) / `070548`(cart) / `070632`+`070633`(order+dict) / `071027`(109菜单) / `071102`(gz_jp_refund) / `071157`(108菜单)<br>**★ 改线上活表类 6 条**：`V202608090231` / `091025` / `091105` / `100739`（**含 `DROP KEY idx_transaction_id`**）/ `101006` —— 这 5 条全是 `ALTER TABLE gz_pay_shipping_order`，那是**拼豆正在 prod 使用、且影响微信资金结算**的活表；另 `V202608101050`(jp banner config) 是插 sys_config 行。<br>⚠️ **这批不能按「全是新表、失败也只影响拼团」评估** —— 改活表结构 + DROP 索引，停机窗口与回滚代价完全不同，需单独评估。`out-of-order: true` 已开 |
| 3 | 部署后 **admin 必须重登**才刷新菜单/权限（`sys_role_menu` 走登录快照），涉及 14000/14010/14020/14030 四段 |
| 5 | **miniapp-jp 无 git 远程**（`git remote -v` 空），phase-plan 标「待建 github:sengsengran-guzi/miniapp-jp」；deploy compose 只有 mysql/redis/ruoyi-admin 三服务，mp 走体验版上传不走容器 |
| 6 | `GZ_TEST_ENABLED` prod 默认 **false**（好）；Kevin 真机测试窗口需临时置 true 再关回 |

### 4.3 sys_config 按小程序分家

✅ **已隔离**（GZ-JP-201）。四层都已落地：

- 建 key：迁移 `V202608101050` 建 `gz.jp.home.banners`（tenant 1001，默认 `[]`）
- 后端归一：`MpPublicConfigKeyResolver` 按请求 header 的 `clientid` 把 `gz.home.banners` 路由到各自那份（**前端漏改常量也不会串味**）
- mp 端：`miniapp-jp/src/api/gz-common.ts` 的 `HOME_BANNERS = 'gz.jp.home.banners'`，有硬断字面量的单测钉住
- admin：「首页 Banner」页顶部可切小程序，切哪个编辑哪个

⚠️ **运营侧动作**：拼团要单独配一份 banner，配拼豆那份对拼团首页无效（这是分家的目的）。不配则走内置占位轮播。

### 4.4 存储 / 图片

**预签名 URL 有效期 1h**，页面长驻后图 404 → 各页 `@error` 兜占位块（不出破图，但显示占位块）。全项目既有口径。根治要后端换长效 URL 或前端定时重拉，**无人认领**。

### 4.5 未决策项（需甲方 / Kevin 拍板）

| # | 项 | 现状与选项 |
|---|---|---|
| 1 | `upload_shipping_info` 拼团侧 | **已接**（GZ-JP-301），挂在店员点发货那一刻。待甲方确认的只剩：① 商户号侧是否已开通**实物商品**发货上报 ② `receiver_contact` 掩码口径。⚠️ 真商户号下的报文（含 `get_delivery_list` 中文承运商名能否命中）**至今零真钱验证**，必须在真机那一轮验 |
| 2 | 拼团 GMV 是否进 4% 分成 | 现状**刻意不进**（recon 只算 preorder+gacha）。纳入属**合同 §4.1 商业口径变更，须客户书面确认**后另开 ticket |
| 3 | `purchase_failed` 是否可从任意非终态进入 | 现状可以（一期无回退，收紧会让清关中发现缺货的货**永远退不了款**）。若口径是「只有购买中能标失败」，改一行，单测会立刻红 |
| 4 | REQ-PROD-007 多规格 SKU | Kevin 暂定一期不做、**甲方未表态**；反悔 = 结构性返工（波及 102+105） |
| 5 | 购物车默认全选 | **产品决策非 AC**，可推翻（改一处 + 3 条单测） |
| 6 | 「已阅读不支持退款」勾选**未落库** | 前端闸门有效，但**事后拿不出「他勾过」的证据**。要举证需后端加列 + 时间戳，**建议另开 ticket** |
| 7 | 无库存 = 无超卖保护 | 「卖完」靠店员手动下架，有人工滞后窗口。需求侧刻意选择 |

### 4.6 后端 VO 缺字段

- ✅ `GzJpOrderItemVO` 已补 `carrierLabel`（读字典 `gz_express_carrier`，整单只读一次），mp 侧那张硬编码映射表已删。降级口径：未发货 / 编码不在字典 / 字典整体不可用 → 一律 `null`，页面只显运单号，**不回落成原始编码**（客人看「sf SF765…」比只看单号更困惑）。<br>  副作用是好的：后台字典新加承运商，mp 立刻能显示中文名 —— 旧的硬编码表做不到，单测里专门钉了这条
- `payFeeCent` 恒 null（mock 通道不回传手续费），真微信回调才有值
- admin `keyword` **匹配昵称/openid，搜不了手机号**（列表显示了手机号但搜不到，店员大概率会试）。改它要动 gz-common，波及多域 ⇒ **独立小 ticket**

### 4.7 资金安全类残留

| # | 项 |
|---|---|
| 1 | ★★ **支付域全额退款能绕开拼团的已退金额校验**。链路：`订单管理`（GZ-ADMIN-103，`plus-ui/src/views/gz-ord/orders/`，**不是**「支付管理页」—— 那两个页一个没退款按钮、一个按钮硬 disabled）→ `POST /system/gz/pay/refund/apply` → `PayRefundTxService.createRefunding`。<br>根因：拼团行级退款写 `gz_jp_refund`，而支付域防重闸只查 `gz_pay_refund`，**两张表互盲**；且拼团行级退款**从不改** `gz_pay_transaction.status`（全模块只 select 不 update），退完仍停在 `paid` ⇒ 支付域三道闸（存在 / paid / 无在途退款单）**全部放行**，退款额取 `txn.amountCent` 全额、不扣已退。<br>⚠️ **「微信会因超额拒绝、钱是安全的」这个结论不成立**，两条反证：① prod 的 `client-mode` 默认值就是 **mock**（`${WECHAT_PAY_CLIENT_MODE:mock}`），mock 通道无条件放行，会一路走完回调把单标 refunded —— 账面就是退了两次；② **更容易发生的一条路清单从没覆盖**：一张**从没做过行级退款**的拼团单走这里全额退，金额合法、微信正常受理，而回调 handler 刻意不碰 `fulfill_status` ⇒「货已发出 + 全款退回」一次点击完成，无任何二次校验。<br>**已加双闸并真打接口验过**：前端 `OrderDetailDrawer.vue` 的 `canRefund` 加 `businessType !== 'jp'` + 禁用提示；后端 `PayRefundTxService` 加 `business_type='jp'` 硬拒 —— 前端闸可被 curl 绕过（`@SaCheckPermission` 拦不住持权限的人，superadmin 更是直接绕过），所以后端那道才是真闸。<br>验证：起后端对 jp 的 txn 45 打 `POST /system/gz/pay/refund/apply` → 被拒；**反面**造一条 `business_type='test'` 的一次性单打同一接口 → 正常受理出退款单（确认没把非拼团的一起拦掉），验完硬删。单测另做过变异验证（把闸改成 `if (false && ...)` → 用例立刻红，4 条非 jp 反面用例保持绿）。<br>⚠️ **这条动的是拼豆/回收也在用的线上资金链路**（GZ-JP-107 当时明令不碰），按 `business_type` 收窄且反面已验，但属跨卡决策 —— 不认可可单独回退这一处 |
| 2 | ✅ **发货上报的 app 维度已修**（`cdb0a8f39` + 迁移 `V202608090231`）：`gz_pay_shipping_order.client_id` 存归属，上报时 appid / secret / token 的 Redis 槽位三者都按**行上的 clientId** 取，不读请求上下文（上报本就跑在无上下文的 `@Async`/cron 里）。拼豆行 `client_id=''` → 走 `default-client-id` = 谷子宇宙自己，两条线不交叉。<br>**残留半条**：`gz_pay_transaction` 仍无 app 维度，于是**支付回调触发**的那条上报路径（`PayCallbackHandler.buildShippingInfo` 只拿得到 txn）无从知道归属，`ShippingInfo.virtual()` 硬写 `clientId=null`。今天无害——唯一走回调上报的业务（拼豆）恰好就住在 default 那个小程序里。**一旦第二个小程序也上「虚拟商品/回调即上报」的业务线就会串**。修法二选一：给 `ShippingInfo.virtual` 加 clientId 重载（要改 `PindouPayCallbackHandler`，在 gz-bean，**Kevin 飞完 GZ-BEAN-053 再动**），或给 `gz_pay_transaction` 加 `client_id` 列 |
| 3 | gz-bean **代客预定按手机号找用户不带 `app_id`**（`GzBeanBookingServiceImpl` 里 `.eq(GzUser::getMobile, mobile).last("LIMIT 1")`）⇒ 拼团有真实用户后，同一手机号可能把代客单挂到拼团那条 `gz_user` 上。修法 = 加一个 `.eq(GzUser::getAppId, ...)`。<br>⚠️ **本轮没修**：该文件属 Kevin 在飞的 GZ-BEAN-053 范围，禁止改动 |
| 4 | 同一 appid 内 access_token **并发刷新无分布式锁**（改造前就有的性质） |
| 5 | ★ **`FORCE INDEX(PRIMARY)` 不许被「优化」掉** —— 写在 `GzJpOrderItemMapper` 的三个批量方法上，是**防死锁必需品**（多租户拦截器注入的 `tenant_id` 会把优化器推向二级索引，服务层的 id 升序纪律被架空）。摘掉前必须重跑 6 并发压测。**通用坑**：gz_bean / gz_recycle 的批量锁查询同样以 `tenant_id` 打头建索引，值得排查 |
| 6 | 已 `delivered` **不可改单号**（终态锁死）。「单号填错了」目前只能改库。若甲方提需求是独立小 ticket，**不要偷偷放宽终态规则** |
| 7 | 一期**不做回退**，误操作不可逆。108 已做二次确认（标失败恒弹窗），推进类全成功时只弹绿条 |
| 8 | 同客人**不同收货地址**仍可被塞进一个包裹（只拦了跨客人） |

### 4.8 测试 / 工程侧

- Playwright（admin）：`playwright.config.ts` 的 webServer 自动起 dev server **在本机会 240s 超时**（health-check 被 clash 代理吞掉）。跑法：先手工 `BROWSER=none pnpm dev --port 8090 --host 127.0.0.1 &`，再 `unset *_PROXY; export NO_PROXY='*'`
- E2E **会改真库**：admin 夹具 id 段 99101-99199 跑完硬删；mp `cart`/`checkout` flow 会**清空 userId=14 的购物车**
- `@RepeatSubmit` 会挡「完全相同 payload 的连续两次请求」→ 返 500，**别用两次一样的 body 写幂等 E2E**
- accept 命令形态：`-am` + `-Dtest=X` **必须加 `-Dsurefire.failIfNoSpecifiedTests=false`**；单测类**必须 `@Tag("dev")`** 否则静默跳过
- **本域外的既有缺陷 —— 均落在 `ruoyi-gz-bean`（Kevin 在飞 GZ-BEAN-053，本轮禁止改动），待他飞完单开 ticket**：
  - `GzBeanBookingServiceImpl:3464-3465` 的 clamp 失效：`ceilToHour`（定义在 `:3763`）用 `truncatedTo(HOURS).plusHours(1)`，`LocalTime 23:xx` 会**回绕成 `00:00`**，于是 `:3465` 的 `ceil.isAfter(slotEnd)` 判不出来 ⇒ **23 点档放座会写出 `actual_end_slot=00:00`**。对应单测每天 23 点稳定失败
  - `GzUserServiceImpl:204-206` 的 admin `keyword` 只 like nickname / openid

---

## 桶 5：D6 QA 门新增（干净 QA 独立跑出来的）

| # | 项 | 严重度 | 结论 / 待办 |
|---|---|---|---|
| 1 | 老 `miniapp` 工程的「不校验合法域名」没勾 | ✅ 已解决 | 开关已勾，accept #1 真跑 6/6 通过。老 harness 另加了后端可达硬 gate + 超时按 flow 数摊 + launch 重试 |
| 2 | 老 `miniapp` 3 个既有单测红 | ✅ 已修（`79bf392`） | **定性 = 用例过期，不是产品 bug**：`silentWxRenew` 头一行的 `if (!hasAgreedPrivacy()) return false` 是微信审核驳回后加的闸门，用例写在那之前没造前置；`MeHeader` 的收藏占位条在「清爽白卡」改版（`c12a9e7`）里被删了而用例没跟。现 519/519 绿。<br>⚠️ 连带修正：本项目**确实动过老 miniapp 的 `src/`**（两处纯注释 + 测试），所以「老小程序前端回归」这项仍然欠着 |
| 3 | `gz_jp_order_item.id=25`：`fulfill_status=purchasing` + `refund_status=refunded` ¥256，无对应 `gz_jp_refund` 行 | ★ 改判为**证据** | **不是脏数据，别清。** 溯源查到 `gz_pay_refund id=2`（RF-20260807-000001，refunded，25600）+ `sys_oper_log` 里 `PayRefundController.apply()` 的完整 HTTP 调用记录（reason 写着「客服整单退（GZ-PAY 旁路测试）」，与该行 `update_time` 同一秒，`version` 恰好 +1）。<br>⇒ 它是**支付域全额退款旁路**的正确产物，走 §4.7 #1 那条链路正常复现得出来 —— 也就是说**那个洞在 2026-08-07 被真的走过一次**。账目全对平（订单头 25600 = 行金额 25600 = `gz_pay_refund` 25600）。<br>两个"修法"都会把正确数据改错：置 NULL 会抹掉客人真实收到的 25600 退款；补 `gz_jp_refund` 行 = 伪造资金凭证（`refund_no` 是微信 `out_refund_no` 幂等键，且 `uk_order_item` 会永久挡住该行未来真正的行级退款）。<br>全库同类扫描 4 类：仅此 1 行，且有匹配的支付域凭证 —— **无真脏数据**。<br>看板显示「购买中 / 已退款」难解释是 **UI 问题**，正解是给这类行加「整单退款（支付侧）」标记，不是改数据 |
| 4 | 跑一次 E2E 会把 `dist/build/mp-weixin/project.config.json` 的 appid 改写成**线上谷子宇宙的** `wx2f8b93e09703f07d` | 次要（操作风险） | harness 有意为之且注释充分（占位 appid 非法，游客模式打不了本地后端），只改 dist 不改源。**但这份 dist 在 IDE 里就是「线上谷子宇宙工程」——误点「上传」会把拼团代码推到线上小程序**。真 appid 到位后这条自然消失 |
| 5 | mp 每次登出都打 `POST /applet/auth/logout` → **404**（新旧两个小程序都有） | 次要 | 脚手架继承的端点，后端从来没实现。只刷日志，不影响登出。**非 JP 引入** |
| 6 | `GET /app/gz/user/orders/list` → 403（被 `/{id}` PathVariable 吃掉） | 次要 | V1.0 占位接口，mp 实际不调。**改造前既有** |

**QA 真跑出来的覆盖**（供上线评估参考）：miniapp-jp 295 单测 / 后端 gz-jp 211 个 `@Test`（12 个测试类全带 `@Tag("dev")`）/ Flyway 全库 / JP 下单→支付→履约→行级退款→回调 rollup 的**跨表金额守恒**（含全库 sweep：不平订单 0、超退 0）/ 4 类并发（并发加购、**同一批 cartItemIds 并发下单只落 1 单**、并发支付回调、并发标记失败只出 1 张退款单）/ 多 appid **6 条串味邪路**（跨 clientid token 401、跨小程序读订单 4105）/ 非超管与无 token 权限各 5 条 / **真等到跨过 `end_time` 的边界行为**（场读时翻 closed、车内项自动失效、结算被拒 4102）/ miniapp-jp 模拟器 7 flow / plus-ui 4 个 JP 页真浏览器 0 console error。

**QA 明确没验到的**：老小程序**前端**回归（域名开关已解决、E2E 已能跑，但本项目动过该仓 `src/`，回归仍欠）/ 任何真机微信原生能力 / prod 真 appid 下的 `gz_user.app_id` 隔离（dev 两边都是 `wxMOCK`，**结构上测不出**）/ real 模式退款回调**验签**（mock 通道不验签）/ staging·prod 部署与灰度。

## 两个易误解点的详细口径

### 确认 1：拼团发货上报 —— **已接**（GZ-JP-301，挂在「发货」不在「支付回调」）

上报的落点与形状：

| 位置 | 做法 |
|---|---|
| **支付回调** | **仍然不报**（`JpPayCallbackHandler` 不 override `buildShippingInfo`，单测钉死）。拼团到货要几周到几个月，付款当下没有任何可上报的发货事实；且微信把「修改物流模式」视为**重新发货**、每笔支付单**只给一次**机会（`10060003`），先按虚拟报一次等于开局烧掉 |
| **批量发货（店员填快递 + 运单号）** | ★ 上报就挂在这里。按「一笔支付单」拆：同一客人跨订单凑一个包裹时，两笔支付单**各报一次**（微信 upload 是按支付单的） |
| 物流模式 | `logistics_type=1`（实体）+ `delivery_mode=2`（**分拆发货**）。拼团一单 30 款分批到货，统一发货报出去后再来包裹就只剩那唯一一次机会 |
| `is_all_delivered` | 该订单还有「既没发货、也没购买失败」的行 → `false`；全落定才 `true`（`countUnfinishedByOrderId`） |
| 包裹累计 | 一笔支付单一行，多包裹累加进 `shipping_list_json`（同运单号去重替换），每次把**截至目前的全部包裹**整份报上去；微信上限 15 个（`10060024`），到顶记 error 等人工并单 |
| 快递编码 | 运行时按中文名反查微信 `get_delivery_list`（运力 1379 家，官方无静态编码表），结果 Redis 缓存 24h |
| 收件人联系方式 | 订单地址快照手机号 → 掩码 `138****5678`（微信要求后 4 位不打码） |
| `client_id` | 随任务落库。access_token 是 **appid 维度**凭证，拿错 appid 的 token 去报，微信恒回 `10060001`「支付单不存在」且重试永远好不了 |
| 失败处置 | 上报失败**绝不回滚发货**（店员交寄是既成事实）；微信终态拒绝（`10060002`/`10060003`）落 `blocked` **停止自动重试**留人工，cron 与补报只扫 `pending`/`failed` |

**拼豆（虚拟商品）那条线一字未动** —— `ShippingInfo.virtual()` 的请求体形状有回归单测钉死（统一发货、`shipping_list` 只含 `item_desc`、不带 `is_all_delivered`）。

### 48h 发货时限 —— **查清楚了：不是死规矩，当前设计不用推翻**

QA 第 5 轮提过「微信要求支付后 48h 内上传发货信息，而拼团几周后才发货」。查完微信规则，
结论是**这条对拼团不成立**，原方案（发货那一刻上报）是对的：

| 规则 | 原文口径 |
|---|---|
| 普通商品 | 支付成功后 **48 小时**内发货 |
| **预售商品** | 按**预售承诺的周期**发货，约定最长发货周期**不超过 330 天** |
| 「约定发货时效」怎么认定 | 以商家**设置、展示的最短时效**为准 —— 如**商品标题、商品详情页的展示信息** |
| 超时怎么罚 | **运营规范层面**：下发警告通知 → 连续 3 天未整改 → 触发支付风险提示 → 直至暂停小程序交易 |
| 接口层面 | **不是硬拒**。社区里 `upload_shipping_info` 的常见错误码是 `47001` 参数格式 / `10060001` 支付单不存在 / `48001` 未授权，**没有「超时」这类码** |

⇒ 拼团/代购天然是**预售场景**，只要商品页把到货周期展示清楚，约定时效就是那个周期（上限 330 天），
不是 48h。**发货时才上报是正确做法**，也符合「支付当下没有发货事实」的判断。

⚠️ **但有一个真的待办（小而关键）**：本项目商品详情页确实展示了「预计到货」
（`deliveryDateText`，REQ-PROD-004），可**商家不填时的兜底文案是「待定（以店内通知为准）」**
—— 那**不构成承诺时效**，微信很可能按普通商品的 48h 判，于是每单都超时。

**已处理**（2026-08-10）：兜底文案由「待定（以店内通知为准）」改为 **「下单后 7 天内发出」**
（Kevin 暂定），落在 `miniapp-jp/src/locale/product.zh-CN.ts` 的 `deliveryUnset`，
改一行即可换。商家在 admin 给单品填了具体到货时间时用商家填的，不走兜底。

⚠️ **仍需 Kevin/甲方最终确认的口径差异**：页面写的是「预计**到货**」，微信管的是「**发货**时效」
（上传运单号那一刻）。拼团是日本采购 → 跨境 → 国内发货，代码注释里的到货周期是「几周到几个月」。
**若 7 天被读作「发货」承诺，按当前业务流大概率兑现不了** —— 承诺短于实际发货速度同样算超时。
真实周期确定后改上面那一处。

来源：[交易类小程序运营规范](https://developers.weixin.qq.com/minigame/product/jiaoyilei/yunyingguifan.html) ·
[微信小店发货管理规则](https://store.weixin.qq.com/chengzhang/webdoc/wiki/407/e4ca8eb1ee772cf7/growth_center_rule_for_store) ·
[发货信息录入接口](https://developers.weixin.qq.com/miniprogram/dev/server/API/order_shipping/api_uploadshippinginfo.html)

⚠️ **其余待甲方确认**：
1. 商户号侧是否已开通**实物商品**发货上报（拼豆是虚拟件，走的是另一套）；
2. `receiver_contact` 用掩码手机号是否符合甲方对客人隐私的口径（当前实现：`138****5678`）。

⚠️ **另一条设计缺口（QA 第 4 轮）**：上报任务的重试窗口锚的是 `paid_time`（47h），
而拼团发货远晚于付款 ⇒ 兜底 cron `uploadPending` **永远扫不到 JP 的失败单**；
叠加「prod 没部署 SnailJob」，实际只剩 owner 手点「补报」（该入口实测有效、不受窗口限制）。
要自动化，得给上报行加一个 `enqueued_time` 并按它开窗。

⚠️ **本地验不到的**：真实商户号下微信是否接受该报文（mock 通道不校验）、`get_delivery_list` 真实运力表里「顺丰速运」等中文名能否命中。**必须在真机 1 分钱支付那一轮一起验**。

### 确认 2：prod 配置链路 —— **代码侧全部就绪，只差部署机 `.env`**

三层逐层核实：

| 层 | 状态 |
|---|---|
| `application-prod.yml` | ✅ 已是 `apps:` Map（`:281`），且 `:298` 起有整段 `spring.config.activate.on-profile: jp` 注册 `mp-applet-gz-jp`（`:302-306`，含 appid / secret / `register-source: mp_wechat_jp`）。**这不是注释模板，是生效配置** |
| `docker-compose.deploy.yml` | ✅ 已透传 `:99 SPRING_PROFILES_INCLUDE` / `:116 WX_JP_MA_APPID` / `:117 WX_JP_MA_SECRET`。用 `:-`（可空）而非 `:?`（缺失即拒），让 `ProdSecretGuard` 在应用层 fail-fast 点名 clientid，避免部署脚本与守卫两套报错口径 |
| **部署机 `.env`** | ❌ **唯一缺口**。拼团那段是 `on-profile: jp` 门控的，不设 `SPRING_PROFILES_INCLUDE=jp` 就**根本不加载** |

```bash
# 部署机 .env 追加这三行（真 appid 到位后）
SPRING_PROFILES_INCLUDE=jp
WX_JP_MA_APPID=<真 appid>
WX_JP_MA_SECRET=<真 secret>
```

⚠️ **不要去"把 prod yml 切成 apps 形态"** —— 它早就是了，而那份配置正承载线上谷子宇宙小程序的登录，动它 = 现小程序全挂。
