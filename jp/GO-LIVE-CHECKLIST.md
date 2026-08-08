# 谷子宇宙拼团一期 —— 上线残留清单

> 由 GZ-JP-301 收尾时通读全部 20 份完工报告 + phase-plan + 确认单 + change-log + 两份修正记录汇总而成，并对两个存疑项**读代码实测**确认。
> 分 4 桶：① appid 回补 ② 甲方行政事项 ③ Kevin 人验 ④ prod 部署缺口。
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
| 3 | `scripts/upload-weixin.js:172-178` | 硬闸：appid 以 `wxMOCK` 开头直接 throw ⇒ **回补前体验版/CI 上传链路物理不可用**（这是对的，防误传） |
| 4 | `test/e2e/mp-e2e.mjs:66` `E2E_APPID` | 现借用谷子宇宙 appid 让 devtools 能打开工程；真 appid 到位后 `/^wxMOCK/i` 不再命中，自动停止改写 |
| 5 | ★★ **`test/e2e/preflight.mjs:31` 与 `test/e2e/run.mjs:61` 的 dev-profile 指纹写死了字面量 `wxMOCKMOCKMOCKMOCK`** | **见下方「★ 回补时最容易踩的坑」** |
| 6 | `src/manifest.json`（由 `manifest.config.ts` 生成）→ 产物 `project.config.json` | 构建期自动跟随 env，**不用手改** |
| 7 | `src/hooks/useAuth.ts`、`src/store/token.ts` | 运行时按 `VITE_WX_APPID.startsWith('wxMOCK')` 分支，**自动切真链路，零代码改动** |

> **★ 回补时最容易踩的坑**：`run.mjs` 的 `distLooksDev()` 用三个指纹判断产物是不是 dev profile —— `localhost:8080` / `wxMOCKMOCKMOCKMOCK` / `mp-applet-gz-jp`。若按 phase-plan 把**三套 env 都换成真 appid**，这个判定会失败 → preflight **exit 2 挡掉所有 E2E**。
> **处置二选一**：① **dev 保留 wxMOCK、只换 staging/prod**（推荐，dev 本来就该走 mock）；② 同步把这两处指纹换成新 appid。
> 这个连带关系**任何一份 ticket 报告都没提过**，是收尾时读代码发现的。

**注意**：`.env` 的 `VITE_APP_CLIENT_ID='mp-applet-gz-jp'` 是 **clientid 不是 appid**，回补时不动；`VITE_UNI_APPID='__UNI__GZJP01'` 是 uni 侧标识，也不动。

### 1.2 后端配置

| # | 位置 | 动作 |
|---|---|---|
| 8 | `application-prod.yml:274-289` | **仍是单值形态** → 必须切成 `apps:` Map；现成模板已写在 `:276-284` 注释里（含 `mp-applet-gz-jp` 与 `register-source: mp_wechat_jp`）。不切 = 拼团 clientid 在 prod 被明确拒绝 |
| 9 | `application-dev.yml:283-297` | 已是 apps 形态，只需注入 `WX_JP_MA_APPID` / `WX_JP_MA_SECRET` 即切 real，**不用改代码** |
| 10 | ★ `script/docker/docker-compose.deploy.yml:105-106` | **只透传 `WX_MA_APPID`/`WX_MA_SECRET`，缺 `WX_JP_MA_*`** → 光改 yml 驱动不起来（见「实测确认 2」） |
| 11 | `register-source` | 新小程序**必须**配自己的值，否则继承全局 `mp_wechat`，admin 分不清用户来源 |

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
- **发货信息上报开通**：拼团**没接**（见实测确认 1）→ 是桶 4 的头号未决策项。
- ★ **服务器合法域名白名单**（报告未列但上线必须）：新小程序后台需把后端域名加进 request 合法域名，否则真机白屏。
- **隐私/法务素材（要甲方提供）**：协议正文仍是**草拟**，法务确认项（公司全称/统一社会信用代码/ICP 号/联系方式/退款时效/管辖地）未落实；提审前需与新小程序后台的「用户隐私保护指引」逐项对齐。文件：`src/locale/agreement.zh-CN.ts` + `src/pages/agreement/index.vue`。

---

## 桶 3：留给 Kevin 的 Tier 2 人验清单

### 3.1 本机一次性动作

| # | 项 | 状态 |
|---|---|---|
| 1 | devtools 扫码登录 | ✅ **已完成** |
| 2 | devtools →「详情」→「本地设置」→ 勾「不校验合法域名…」（**miniapp-jp 工程**） | ✅ **已完成**（D5 QA 实测确认解除） |
| 3 | ⭐ 同一个勾，**再给老 `miniapp` 工程勾一次** | ⬜ **待 Kevin，30 秒**（见下，卡着 GZ-JP-301 accept #1） |

> ⭐ **#3 为什么必须做**：这个开关在微信开发者工具里是**每个工程各自一份**，给 miniapp-jp 勾过对老工程无效。
> 老工程没勾 ⇒ 模拟器里所有 `wx.request` 被拦（`url not in domain list`）⇒ **老小程序全量回归永远真跑不了**，
> 于是「多 appid 改造有没有伤到线上小程序」这条 accept 拿不到端侧证据（后端侧已用 19 个端点 + 登录 + 建单验绿）。
> 操作：微信开发者工具 → 打开 `code/main/miniapp/dist/build/mp-weixin` → 右上「详情」→「本地设置」→ 勾上 → 告诉我，我重跑 `node test/e2e/run.mjs all`。
> （已实测：改 `project.config.json` 的 `setting.urlCheck` / 换 appid / cli 重开 **都压不住它**，只能 GUI 勾。老 harness 现已加 gate，没勾时会**立刻报错并给出这段路径**，不再伪装成业务 bug。）

> ⚠️ **配套安全红线**：模拟器在该开关**关闭**时唯一打得通的是**生产后端**（借用旧 appid 的合法域名）⇒ 拿 production profile 产物跑 E2E 会往**生产库真写单**。`run.mjs` 的 `distLooksDev` 护栏**不可绕过/注释**。

### 3.2 真机微信原生能力

| # | 能力 | 结论 |
|---|---|---|
| 3 | ★★ **真实支付（真钱 1 分单）** | **必验 4 条**：① 现小程序（谷子宇宙）1 分单全链路 —— **最重要，动的是它正在跑的收款链路** ② 拼团小程序 1 分单 ③ 两小程序**交叉验证**（A 的单不能用 B 的 appid 调起）④ 看日志 `[gz-pay] createJsapiOrder … appid=` / `buildPayParams … appid=` |
| 4 | ★★ **真钱行级部分退款** | **必验且至今零真钱验证**：dev 全程 `MockWechatPayClient`，「微信真的会按行金额部分退款」没验过。做法：真商户号下一笔多行拼团单，标 1 行失败，确认微信侧退款金额 = 行金额而非整单 |
| 5 | `getPhoneNumber` | 拼团 mp **本身没有手机号绑定页**；回补阶段建议「两个 real 小程序同时在线跑一轮手机号绑定 + 发货上报」 |
| 6 | 头像昵称授权 | ✅ 有真实载体：`AvatarUpload.vue` 的 `open-type="chooseAvatar"` + `pages/me/profile` 昵称填写 |
| 7 | 微信客服 / 扫码 | 一期无入口 / 无功能 → **N/A** |

### 3.3 新页首版视觉拍板（**8 个 mp 页 + 1 个 admin 页，全部未被人眼看过**）

- **mp 8 页**：首页 / 场详情 / 商品详情 / 购物车 / 下单确认 / 支付结果 / 订单列表 / 订单详情
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

- **SnailJob 未部署**：`snail-job.enabled` prod 默认 false，全后端 **34 个 `@JobExecutor` 一个都不跑**。
- **但有本地兜底**（报告里没说清，实测补上）：`GzLocalPayScheduler`（`gz.local-scheduler.enabled` prod 默认 **true**）用 Spring `@Scheduled` 覆盖了三条**资金相关**任务：支付主动查单（90s）/ **发货上传兜底重试**（300s）/ 支付单超时关闭 ⇒ 拼豆的发货上报与支付补单在 prod 是活的。
- 仍然哑的（与 jp 相关）：
  - **jp 未支付订单的 5 分钟超时关单**依赖 `@JobExecutor` ⇒ prod 的 jp `created` 单会长期停滞（不影响资金，`markCancelled` 已备好）
  - **退款卡单自动补偿没有** ⇒ 事务提交后、调微信前进程挂掉 = 一张永远 `refunding` 的单。兜底做成人可操作：退款单列表把失败/超 10 分钟无回调排最前 + `POST /system/gz/jp/refund/{id}/retry`
  - 设计上**刻意零 cron**的不受影响：场「到点即结束」是读时惰性判定；购物车失效项同理

### 4.2 部署配置缺口

| # | 缺口 |
|---|---|
| 1 | compose 未透传 `WX_JP_MA_APPID` / `WX_JP_MA_SECRET`（`docker-compose.deploy.yml:105-106`） |
| 2 | prod `wx.miniapp` 仍单值形态 → 拼团 clientid 在 prod 一律被拒（报错清晰） |
| 3 | **staging / prod 从未部署过任何 jp 迁移**，待补跑 **12 条**：`V202608062249`(pay_channel) / `062251`(gz_user) / `070202`+`070203`(event) / `070232`+`070233`(product) / `070548`(cart) / `070632`+`070633`(order+dict) / `071027`(109菜单) / `071102`(gz_jp_refund) / `071157`(108菜单)。`out-of-order: true` 已开 |
| 4 | 部署后 **admin 必须重登**才刷新菜单/权限（`sys_role_menu` 走登录快照），涉及 14000/14010/14020/14030 四段 |
| 5 | **miniapp-jp 无 git 远程**（`git remote -v` 空），phase-plan 标「待建 github:sengsengran-guzi/miniapp-jp」；deploy compose 只有 mysql/redis/ruoyi-admin 三服务，mp 走体验版上传不走容器 |
| 6 | `GZ_TEST_ENABLED` prod 默认 **false**（好）；Kevin 真机测试窗口需临时置 true 再关回 |

### 4.3 sys_config 共用 key 冲突

★ **`gz.home.banners` 与现有谷子宇宙小程序共用同一个 key**，同租户同端点，**无 clientid 维度隔离**。当前值 `"[]"` ⇒ 走默认图降级，问题不暴露；**只要运营给拼豆配了首页 banner，拼团首页会立刻显示拼豆的图**。

- 前端读点：`miniapp-jp/src/api/gz-common.ts` 的 `GZ_CONFIG_KEYS.HOME_BANNERS`
- 处置：谁先要配 banner，谁先做「后端加 `gz.jp.home.banners` + admin 配置项 + 前端换 key（一行常量）」小卡
- **建议在运营开始配 banner 之前排掉**

### 4.4 存储 / 图片

**预签名 URL 有效期 1h**，页面长驻后图 404 → 各页 `@error` 兜占位块（不出破图，但显示占位块）。全项目既有口径。根治要后端换长效 URL 或前端定时重拉，**无人认领**。

### 4.5 未决策项（需甲方 / Kevin 拍板）

| # | 项 | 现状与选项 |
|---|---|---|
| 1 | ★ **`upload_shipping_info` 对拼团是否适用** | 拼团**完全没接**（见实测确认 1）。若要接，应接在**置 `delivered` 那一刻**，不是支付回调。**需甲方向微信商户侧确认**。⚠️ 项目记忆：发货上报对拼豆是强制项且影响资金结算 |
| 2 | 拼团 GMV 是否进 4% 分成 | 现状**刻意不进**（recon 只算 preorder+gacha）。纳入属**合同 §4.1 商业口径变更，须客户书面确认**后另开 ticket |
| 3 | `purchase_failed` 是否可从任意非终态进入 | 现状可以（一期无回退，收紧会让清关中发现缺货的货**永远退不了款**）。若口径是「只有购买中能标失败」，改一行，单测会立刻红 |
| 4 | REQ-PROD-007 多规格 SKU | Kevin 暂定一期不做、**甲方未表态**；反悔 = 结构性返工（波及 102+105） |
| 5 | 购物车默认全选 | **产品决策非 AC**，可推翻（改一处 + 3 条单测） |
| 6 | 「已阅读不支持退款」勾选**未落库** | 前端闸门有效，但**事后拿不出「他勾过」的证据**。要举证需后端加列 + 时间戳，**建议另开 ticket** |
| 7 | 无库存 = 无超卖保护 | 「卖完」靠店员手动下架，有人工滞后窗口。需求侧刻意选择 |

### 4.6 后端 VO 缺字段

- ★ mp `GzJpOrderItemVO` **只下发 `carrierCode` 没有 `carrierLabel`**（对比 `fulfillStatusLabel`/`refundStatusLabel` 后端都给了）⇒ 前端只好维护 `CARRIER_NAMES` 9 项映射表。**正解是后端补 `carrierLabel`，补上后删掉这张表**
- `payFeeCent` 恒 null（mock 通道不回传手续费），真微信回调才有值
- admin `keyword` **匹配昵称/openid，搜不了手机号**（列表显示了手机号但搜不到，店员大概率会试）。改它要动 gz-common，波及多域 ⇒ **独立小 ticket**

### 4.7 资金安全类残留

| # | 项 |
|---|---|
| 1 | ★★ **admin 支付管理页仍能对已部分退款的 jp 单发起全额退款** —— jp 行级退款不写 `gz_pay_refund`，绕开了「一笔支付只允许一条退款单」闸。微信会因超额拒绝（**钱是安全的**）但留 failed 记录。**缓解**：① 支付管理页对 `business_type='jp'` 禁用退款按钮 ② 运维文档写「拼团退款只走履约看板」 |
| 2 | `gz_pay_transaction` / `gz_pay_shipping_order` **无 app 维度** ⇒ 两个小程序都要真发货上报时会**把 B 的订单用 A 的 token/appid 报上去**。「在这张卡落地前，**第二个小程序不要开真发货上报**」。**目前无人认领** |
| 3 | gz-bean **代客预定按手机号找用户不带 `app_id`** ⇒ 拼团有真实用户后，同一手机号可能把代客单挂到拼团那条 `gz_user` 上。修法加一个 `.eq(GzUser::getAppId, ...)`，**原文即「留给拼团上线 checklist」** |
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
- **本域外的既有缺陷**（实测发现，未修，建议单开 ticket）：
  - `GzBeanBookingServiceImpl:3426-3427` 的 `ceilToHour(now)` 在 23:00-24:00 回绕成 `00:00` 使 clamp 失效 ⇒ **23 点档放座会写出 `actual_end_slot=00:00`**，对应单测每天 23 点稳定失败
  - gz-news 2 个单测陈旧 stub（`UnnecessaryStubbingException`），修一行即可

---

## 桶 5：D6 QA 门新增（干净 QA 独立跑出来的）

| # | 项 | 严重度 | 结论 / 待办 |
|---|---|---|---|
| 1 | 老 `miniapp` 工程的「不校验合法域名」没勾 | **blocker（对 accept #1）** | ⬜ 见 §3.1 #3，Kevin 30 秒。老 harness 已加 gate + 超时按 flow 数摊 + launch 重试（已提交） |
| 2 | 老 `miniapp` **3 个既有单测红**：`token.test.ts` 的 `silentWxRenew` ×2、`MeHeader.test.ts` ×1 | 重要 | ⚠️ **与本项目无关**（工作区与 HEAD `59635d4 2026-07-27` 逐字节一致，本项目 08-06 才开工且从未改过该仓 `src/`）。但 `silentWxRenew()` 返 false 意味着**静默续期失败 → 用户被踢去重登**，上线前建议单独查 |
| 3 | `gz_jp_order_item.id=25` 自相矛盾：`fulfill_status=purchasing` + `refund_status=refunded` ¥256，且**无对应 `gz_jp_refund` 行** | 次要 | 早期 ticket 手工改库的遗留脏数据（走正常流程复现不出来）。**演示前清掉**，否则 admin 履约看板会显示「购买中 / 已退款」一行 |
| 4 | 跑一次 E2E 会把 `dist/build/mp-weixin/project.config.json` 的 appid 改写成**线上谷子宇宙的** `wx2f8b93e09703f07d` | 次要（操作风险） | harness 有意为之且注释充分（占位 appid 非法，游客模式打不了本地后端），只改 dist 不改源。**但这份 dist 在 IDE 里就是「线上谷子宇宙工程」——误点「上传」会把拼团代码推到线上小程序**。真 appid 到位后这条自然消失 |
| 5 | mp 每次登出都打 `POST /applet/auth/logout` → **404**（新旧两个小程序都有） | 次要 | 脚手架继承的端点，后端从来没实现。只刷日志，不影响登出。**非 JP 引入** |
| 6 | `GET /app/gz/user/orders/list` → 403（被 `/{id}` PathVariable 吃掉） | 次要 | V1.0 占位接口，mp 实际不调。**改造前既有** |

**QA 真跑出来的覆盖**（供上线评估参考）：miniapp-jp 294 单测 / 后端 gz-jp 194 单测 / Flyway 全库 / JP 下单→支付→履约→行级退款→回调 rollup 的**跨表金额守恒**（含全库 sweep：不平订单 0、超退 0）/ 4 类并发（并发加购、**同一批 cartItemIds 并发下单只落 1 单**、并发支付回调、并发标记失败只出 1 张退款单）/ 多 appid **6 条串味邪路**（跨 clientid token 401、跨小程序读订单 4105）/ 非超管与无 token 权限各 5 条 / **真等到跨过 `end_time` 的边界行为**（场读时翻 closed、车内项自动失效、结算被拒 4102）/ miniapp-jp 模拟器 7 flow / plus-ui 4 个 JP 页真浏览器 0 console error。

**QA 明确没验到的**：老小程序**前端**回归（§5 #1 阻塞）/ 任何真机微信原生能力 / prod 真 appid 下的 `gz_user.app_id` 隔离（dev 两边都是 `wxMOCK`，**结构上测不出**）/ real 模式退款回调**验签**（mock 通道不验签）/ staging·prod 部署与灰度。

## 实测确认（收尾时读代码核实的两件事）

### 确认 1：gz-jp **完全没有**接入 `upload_shipping_info`

**结论：没接，且是明确的、有理由的「刻意不接」，链路在 SPI 分发那层就断了。**

1. 上报入口只有一个：`GzPayTransactionServiceImpl:311` `dispatcher.resolveShippingInfo(tx).ifPresent(...)` —— **只有 `PayCallbackHandler.buildShippingInfo()` 返回非空的业务才会落 `gz_pay_shipping_order` 并异步上报**
2. SPI 默认值是「不上报」：`PayCallbackHandler:64` `default Optional<ShippingInfo> buildShippingInfo(...) { return Optional.empty(); }`
3. **全后端只有拼豆 override 了它**：`PindouPayCallbackHandler:60`
4. 拼团的 handler **刻意不 override**，`JpPayCallbackHandler:29-33` 类 javadoc 原文：
   > 「`buildShippingInfo` **刻意不 override**（保持默认「不上报」）：拼团的到货周期是几周到几个月、发货由店员手工填顺丰单号 —— 支付当下没有任何可上报的发货事实。硬报会误导微信侧的收货判定。拼团的发货上报若要接，应在**置 delivered 那一刻**接，且**需甲方确认商户号侧要求**，不是在支付回调里。」
5. 有单测钉死：`GzJpPayCallbackTest:347` `assertTrue(handler.buildShippingInfo(...).isEmpty(), "不接订单中心发货上报")`

⇒ **`gz_pay_shipping_order` 里永远不会出现 `business_type='jp'` 的行**；admin「手动补报」按钮与兜底 scheduler 都只服务拼豆。

### 确认 2：deploy compose **没有** `WX_JP_MA_*` 透传

`docker-compose.deploy.yml:105-106` 实际内容只有：
```yaml
WX_MA_APPID: ${WX_MA_APPID:-wxMOCK}
WX_MA_SECRET: ${WX_MA_SECRET:-}
```
全文件 grep `WX_JP` → **0 命中**。该 compose 只定义 3 个服务：mysql / redis / ruoyi-admin。

⇒ `application-prod.yml` 那段「拿到拼团 appid 后改成 apps 形态」的注释**光改 yml 驱动不起来**，必须同时给 compose 补两行 env 透传 + 在部署机 `.env` 放真值。

> 建议补进去时沿用 `:-`（可空）而不是 `:?`（缺失即拒启动），靠 `ProdSecretGuard` 在应用层 fail-fast 点名 clientid，避免部署脚本与守卫两套报错口径。
