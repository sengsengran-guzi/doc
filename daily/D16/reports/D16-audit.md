# D16 上线前三角度审计报告

> 方法：12 路 auditor 并行（5 业务域 + 5 横切 + 2 设计）→ 对抗式复核（证伪假阳性 + 校正 severity + 补 file:line）→ 汇总去重分级。25 个 agent，每条 finding 均 READ 实际代码取证。
> 去重后 **41 条**（原始 50）：🔴 阻塞 **4** / 🟡 上线前 **14** / 🟢 上线后 **23**。AI 可闭环 33 / 需 Kevin·真机·甲方 26。

## 就绪度结论

**暂不可上线，但距离很近。** 核心是 4 个 blocker 必须先清——其中 2 个纯代码可闭环（type-slot 字段对齐、IDOR 归属校验），2 个代码可闭环但各带 1 个 Kevin 决策点（prod 漏配守卫、回收 retry 收敛）。清掉 blocker + 第二档资金/体验缺陷后即进真机人验与部署 gate 阶段。

**三个不能代码绕过、必须 Kevin 拍板的系统性问题**：
1. **18 个定时任务全挂默认关闭的 SnailJob**（资讯定时发布 / 拼豆 no_show / 券过期 / 支付·退款兜底查单 / 对账日·月·季跑批）。doc/04「不启用 SnailJob」与 doc/10+代码自相矛盾。后果之一：**首月上线当天 owner 看 4% 分成必为 ¥0**（无 in-app 重算入口）。= 部署 gate + 架构口径决策。
2. **真实支付/退款两条资金兜底缺失**（unpaid 超时关单不查单会强关已付单且无退款；退款侧无主动查单 job 致永久卡 refunding + 4% 分成多算）。真实商户号下证后才触发，是「真实支付启用前必补」。
3. **真实商户号 / 正式 AppID / 客服 kfid / 美术资产** = 甲方外部前置，进 checklist 跟踪。

---

## 🔴 阻塞项（4，上线前必修，全 AI 可闭环）

### B1 · 拼豆付费选座 /type-slots 跨端字段名错位 → 座位列表恒空，整条不可下单 ⭐
- **角度**：test · **域**：bean · **AI 可闭环**：是（needsHuman=none）
- **证据**：后端 `GzBeanTypeSlotAvailabilityVO.java:28-54` 字段 `seatTypeName/priceCent` 且**无 `active`**；service builder `GzBeanBookingServiceImpl.java:934-944` set `seatTypeName/priceCent` 不 set active。mp `gz-bean.ts:409/411/423` 期望 `name/unitPriceCent/active(boolean)`；`index.logic.ts:35` `if(!ts.active){continue}`（后端不返 active→undefined→falsy→**每档跳过**）；`index.vue:393-394` 渲染 `opt.name`/`¥formatYuan(opt.unitPriceCent)`（→空白 + ¥NaN）。`http.ts:141` 透传无重映射 → typeOptions 恒空 → 命中空状态。
- **影响**：拼豆付费预约（第一版头号功能）整条 0 转化，上线即不可用。
- **修法**：后端 VO `seatTypeName→name`、`priceCent→unitPriceCent`（或 @JsonProperty 别名）+ 新增 `active`；builder set `.active(true)`（`:914` 已 eq enabled=1 故恒 true）。⚠️ **必同步改 `index.logic.test.ts:17-21` fixtures**——当前 fixtures 用 mp 字段名导致 vitest 一路绿、掩盖契约断裂，必须让 fixtures = 真实后端 JSON。`mvn test -pl ruoyi-gz-bean` + `pnpm test` 双跑。

### B2 · mp 支付状态轮询端点 IDOR → 枚举 out_trade_no 读他人 openid/金额/transactionId ⭐
- **角度**：product · **域**：pay · **AI 可闭环**：是（needsHuman=none）
- **证据**：`GzPayMpController.java:23` 类级仅 `@SaCheckLogin` 无归属，`:38-44` `status(@PathVariable outTradeNo)` 直接 `getByOutTradeNo` 返整个 VO 无 userId 比对（对照 `GzBeanBookingMpController:211-213`/`GzUserOrderMpController:127` 均有归属写法，独此缺）。VO 含 userId/openid/amountCent/transactionId。out_trade_no 可枚举（`PayOrderNoGenerator` `<前缀>-yyyyMMdd-6位连续序号`）。
- **影响**：任一登录顾客暴力枚举即拿全平台支付单的微信 openid（PII）+ 实付 + transactionId。拼豆 V1.2 已产生真实 pindou 支付单并由 mp 轮询此端点，C 端上线即暴露横向越权读 PII。
- **修法**：`status()` 取 `LoginHelper.getUserId()` 比对 `vo.getUserId()` 不符返 403（照搬 `GzBeanBookingMpController:211-213`）；更稳在 service 加 `getByOutTradeNoForUser(outTradeNo,userId)` 下推 SQL；轮询新建窄 VO 只返 outTradeNo/status/amountCent/paidTime，剔除 openid/transactionId/prepayId。补单测断言他人 403 / 本人 200。

### B3 · prod 漏注入 WX_MA_APPID 时静默启用 mock 登录 → 鉴权完全失效 + QR 密钥裸奔
- **角度**：product · **域**：sys · **AI 可闭环**：是（守卫纯代码）· **needsHuman**：决策（确认 profile=prod + 「漏配即拒绝启动」为期望）
- **证据**：`application-prod.yml:276` `appid:${WX_MA_APPID:wxMOCK}`（env 缺即落 wxMOCK）；`WxMockLoginAdapter.java:34` `@ConditionalOnProperty(...havingValue=wxMOCK,matchIfMissing=true)` 缺省也匹配 mock，`:54-59` openid=`mock-`+code 前 8 位（稳定可预测）；登录模块零 prod 守卫（仅 pay `WechatPayV3ClientImpl` 有 fail-fast）；`WxMockPhoneAdapter` 同款 matchIfMissing=true。同根因：`application-prod.yml:286` `gz.bean.qr.signing-secret` 默认 `CHANGE_ME_BEFORE_PROD_DEPLOY`，`QrCodeSigner` 直接用做 HMAC 无校验。
- **影响**：运维漏注入 WX_MA_APPID（合同明确 AppID 待甲方=高风险窗口）→ 后端静默 mock 登录，任何人传任意 code 即拿稳定 openid + token，鉴权完全失效。**与「mock 支付是已知 gate」不同——这是鉴权静默降级，无显式 gate。**
- **修法**：prod 启动 fail-fast `@Configuration`：`spring.profiles.active` 含 prod 且 `wx.miniapp.appid==wxMOCK`（或 signingSecret 仍占位）时 `@PostConstruct` 抛 `IllegalStateException` 拒绝启动（照抄 `WechatPayV3ClientImpl.init()`）。dev 不受影响。

### B4 · 回收反向打款双 retry 入口与回收单状态脱钩 → 钱二次转出但回收单永久卡 payout_failed
- **角度**：test · **域**：recycle · **AI 可闭环**：是（option b 代码可闭环）· **needsHuman**：决策（入口收敛 a/b/a+b）
- **证据**：两条 retry 指向同一 payout。① 回收单页 `retryPayout→markRetryPaying`（`GzRecycleAppointmentMapper:117-119` payout_failed→paying，是回收单唯一脱离 payout_failed 的路径）；② 打款单页 `GzPayPayoutServiceImpl.retryPayout:116-156` 仅重置 payout failed→created→processing，**全程不触碰 gz_recycle_appointment**。回写钩子 `selectPayingIds:142-143` 只扫 `status='paying'`。`doc/10 §14.N6` 明确 owner 权威重试入口 = admin『打款单管理』页 = **正是不修复回收单状态那条路径**。
- **影响**：owner 按 doc 主指引在『打款单管理』页重试成功，payout 推进 success，但回收单仍停 payout_failed（markRetryPaying 从未被调，sync 只扫 paying 永不收敛）→ 钱二次真实转出、单据孤儿、对账口径错。仅因 mock 未真出账暂未爆雷。
- **修法（建议 a+b）**：(b) `selectPayingIds` 改扫 `status IN('paying','payout_failed')` 且 out_payout_no 非空，syncOne 放开 status 守卫，按 payout 终态 success→markPaid → 任一入口重试成功都被收敛；(a) payout 页对 `business_type='recycle'` 的 failed 单隐藏 retry 按钮统一引导回回收单页。补单测。统一 doc §14.N6 与 §13.E4 口径。

---

## 🟡 上线前应修（14）

| # | 标题 | 域 | AI可闭环 | 需 Kevin/真机 |
|---|---|---|---|---|
| P1 | mp 拼豆详情/列表座位栏渲染 seatNoSnapshot（付费单恒 NULL）→空白 + 未付单照常亮可扫 QR | bean | 是 | 改完真机验 |
| P2 | 拼豆 pindou 缺退款 SPI handler → 退款后座位类型配额永不释放（资金账不一致） | bean | 是（配额释放） | 券回退口径决策 |
| P3 | unpaid 超时回收关 paying 单前不查单 → 真实支付下已付单被强关 cancelled 无退款 | bean | 否 | 真机+决策（超时窗口/查单时序） |
| P4 | 退款侧无主动查单兜底 job → 回调丢失永久卡 refunding，4% 分成多算 | pay | 否（real 依赖商户号） | 决策（是否上线前必补） |
| P5 | 店员核对 final_amount 无金额上限软校验 → 反向真打款可被误操作放大 | recycle | 是（配置化阈值） | 决策（阈值 N + 软拦截 vs 仅告警；doc §1545 F12.2 vs §1352 E3 冲突） |
| P6 | recycle/my-list 列表页缺错误态，加载失败静默退化为「暂无记录」 | recycle | 是 | none |
| P7 | 扭蛋做活后整条订单链路 C 端断裂（我的订单 gacha tab 写死空占位 + 我开过的跳死路由 /pages/me/order/detail） | gacha | 是 | 决策（扭蛋是否纳首版）+真机 |
| P8 | 资讯定时发布上线即静默失效（唯一触发器是默认关 SnailJob，连带 18 任务全静默） | news | 否 | 决策+部署（SnailJob 方案） |
| P9 | 对账/季度结算全依赖 SnailJob 手动注册 cron，无 in-app 重算 → 首月 owner 看分成必 ¥0 | recon | 否 | 决策+部署（cron 注册是上线 gate） |
| P10 | Excel 导出与月度 settle 跨月退款归属口径打架 → 分成凭证对不上 | recon | 是 | 决策（成交月 vs 退款发生月口径） |
| P11 | owner 改店员角色/撤权限（不停用）时 mp token 权限快照不刷新，旧 token 7 天内仍可触发回收打款/物流推进 | sys | 是（补切面） | 决策（修复手段选型） |
| P12 | 4 处核心付费/回收金额强调大字引用未定义 token `var(--c-fs-h)` → 字号塌缩成正文 | design | 是 | none |
| P13 | 回收店员核对页 staff-verify.vue 大面积引用未定义 token（--c-ink-60×9/--c-fs-md×4 等）→ 文字层级塌陷 | design | 是 | none |

> （P1-P13 上表 13 行 + 扭蛋 P7 合并了 #16/17/19/21/41/42 多条同根因，实计 14 条 pre-launch。）

---

## 🟢 上线后迭代（23，摘要）

**多数是「修 doc 而非改代码」（符合复盘优先级 #1 改权威蓝图）**：
- doc/10 vs doc/11 `unpaid 是否占配额`口径矛盾（代码取 doc/11 正确，修 doc）
- doc/11 估价口径 total_qty vs 分品类命中矛盾（代码取 F12.1 正确，修 doc）
- 默认地址唯一性 doc 称「DB 约束+乐观锁」实为事务内 reset-then-set（不变量成立，修 doc 措辞）
- booking_no 无连字符，doc/11 三处格式自相矛盾（需 Kevin 定 dash 口径）
- gz_bean_pay_status 字典 doc 声明 sys_dict 但无 migration 建库（VO 埋 dict-tag 假前提）

**死代码清理（AI 可闭环）**：
- 7 个 `Hello.vue` 空壳页 + `helloGzXxx()` + `gzHello` i18n（零路由引用）
- 2 个 `/hello` 探活端点（CommonHello/OrdHello）
- `bean/success.vue` 死页（明文 verifyCode query 传参，无可达路径）
- `recycle/form.vue` 未使用 import `listMyRecycle`
- ord/* 已下线页仍 definePage 注册路由无 onLoad 守卫（可加深链重定向兜底）

**防御纵深/健壮性加固（AI 可闭环，当前不可利用）**：
- lockForBooking 锁券未二次校验 applicable_business（被「模板仅放行 pindou」硬闸挡住）
- submit/verify image_id 未校验存在性/归属/usage_type
- verifyAndPayout markPaying affected=0 仅告警不补偿（version 守卫已挡，近不可达）
- 季度结算重跑覆盖已结算金额不留痕（三条件同时低频）
- mp sanitizer 伪协议正则仅匹配带引号（写入层 jsoup 已防住）
- video_urls 不校验 URL 协议、资讯阅读/分享计数可匿名刷量（V1.0 显式取舍）
- 物流回退不清空 cn_carrier_code/单号（in_japan 态 UI 不外露，纯数据卫生）
- 单 token 401 首请求被 reject 与「无感续期」注释不符（偶发一次性闪错）
- 状态机漏 `scheduled→draft` 取消定时（运营设错时间只能立即发/删重建）

**设计/美术（需甲方资产，非纯代码）**：
- 回收 tab 图标占位（字节级复用旧 home 图，房子图标语义错位）→ designer 出图同名替换
- 正式 UI emoji 占位（我的页九宫格 / 资讯 ♡☆ / bean success ⚠✓ / 各空态）→ 上线前替 SVG

**待发货看板卡只数 preorder（已下线）→ 常驻 0**（需确认扭蛋是否走跨境物流）

> ✅ 正向确认（非缺陷）：预购下线干净（mp 无可达入口 + admin 菜单 visible='1' + 不 DROP 表保历史）；系统底座登录/OSS 链路无越权/崩溃（四重文件校验、token issue 防 NPE）。

---

## AI 当场闭环修复记录（本会话已修 + 自测通过）

> 后端 `mvn install` 全 SUCCESS；定向单测 **B1 40✅ / B2 4✅ / B3 4✅ / B4 11✅**。mp `vue-tsc type-check 0 错` + `vitest 40 文件 374 测试全过`。

### 🔴 4 个 blocker（全修 + 单测）

| # | 改了什么 | 文件 | 自测 |
|---|---|---|---|
| B1 | 后端 type-slot VO 字段对齐 mp 契约（`seatTypeName→name`、`priceCent→unitPriceCent`、补 `active=true`）+ builder + 后端测试加契约断言（防复发） | `GzBeanTypeSlotAvailabilityVO.java` / `GzBeanBookingServiceImpl.java:934` / `GzBeanBookingServiceImplTest.java` | bean 单测 40✅ |
| B2 | 支付轮询端点加 userId 归属校验（非本人 403）+ 投影窄 VO `GzPayStatusVO`（剔除 openid/prepayId/userId/feeCent） | `GzPayMpController.java` / 新 `GzPayStatusVO.java` / 新 `GzPayMpControllerTest.java` | IDOR 单测 4✅（本人 200/他人 403/不存在/未登录） |
| B3 | prod 启动 fail-fast 守卫：`@Profile("prod")` 下 appid=wxMOCK 或 qr-secret 占位 → 拒绝启动 | 新 `ProdSecretGuard.java` / 新 `ProdSecretGuardTest.java` | 守卫单测 4✅ |
| B4 | 回收 payout 回写收敛：sync 扫描集纳入 `payout_failed`（out_payout_no 非空）+ `markPaid` 放开 `payout_failed→paid` + `syncOne` 守卫放开 | `GzRecycleAppointmentMapper.java`（selectPayingIds→selectSyncablePayoutIds + markPaid WHERE）/ `GzRecycleAppointmentServiceImpl.java` / `GzRecycleVerifyPayoutTest.java`（+ B4 收敛回归测试） | recycle 单测 11✅ |

### 🟡 上线前清晰项（mp，全修 + type-check/vitest 通过）

| # | 改了什么 | 文件 |
|---|---|---|
| P1 | 拼豆详情/列表座位栏改渲 `seatTypeSnapshot‖seatType‖seatNoSnapshot`（付费单不再空白）+ 详情加金额/抵扣/支付态行 + **QR 可扫收紧为 `pending && payStatus==='paid'`**（未付单显「待支付」遮罩，不再亮可扫码） | `bean/detail.vue` / `bean/my-list.vue` / `locale/bean.zh-CN.ts`（+qrUnpaidTip） |
| P6 | 回收 my-list 加显式错误态（loadError + 可重试），不再静默退化「暂无记录」 | `recycle/my-list.vue` / `locale/recycle.zh-CN.ts`（+listLoadError/retry） |
| P12 | 4 处金额强调大字 `var(--c-fs-h)`（未定义）→ `var(--c-fs-h1)`（40rpx 朱红大字回归） | `bean/index.vue` / `recycle/form.vue` / `recycle/my-list.vue` / `BizCouponPicker.vue` |
| P13 | staff-verify 大面积未定义 token 语义映射（`--c-ink-60→ink-2`/`-40→ink-3`/`-20→line`/`fs-md→fs-body`）+ staff-orders/detail 同 | `recycle/staff-verify.vue` / `me/staff-orders/detail.vue` |

### 🟡 第二批（Kevin「7 项按默认执行」后续）— 进行中

| # | 项 | 状态 |
|---|---|---|
| P2 | 拼豆退款 SPI handler `PindouRefundCallbackHandler` + `onPindouRefunded`（paid→refunded，未核销单释放配额；**券保守默认不退还**）+ mapper `markRefunded` + 3 单测 | ✅ done（bean 43 测试） |
| P5 | 回收 `final_amount` 资金上限软校验（≤ 估价×N 且 ≤ 绝对上限，均 sys_config 可调默认 3 倍/¥1000，超限抛 `FINAL_AMOUNT_EXCEEDS_LIMIT`）+ 单测 | ✅ done（recycle 20 测试） |
| #1 | 对账中心 owner「立即重算」按钮（消除首月 ¥0 风险，方案 A）：后端 `/reconcile/rebuild` 调 runDaily+runMonthly（幂等重跑）+ api + 按钮 + i18n | ✅ done（gz-common 编译 + plus-ui build 绿） |
| P11 | 店员权限即时回收切面（补 `insertUserAuth`/`updateUser` 切点踢具体 user + `updateRole` 保守踢全部绑定店员）+ mapper `selectAllBoundStaffUserIds` + 3 单测 | ✅ done（common 切面 10 测试） |
| P10 | Excel 导出汇总行改取 `gz_recon_monthly` 落库值（与对账中心同源，不再 detail 现算 → 跨月退款口径不打架）；明细行保留作凭证 | ✅ done（recon 16 测试） |
| P1a | 回收 payout 页 retry 对 recycle 单收敛 | ✅ **资金核心已被 B4 闭合**（任一入口重试成功都收敛 paid）；剩 UI 隐藏(B4 后已安全·marginal) + doc §14.N6/§13.E4 统一 → 并入 🟢 doc 批 |
| P7 | 扭蛋订单链路三层接线 | ⏳ **下一轮专门做**（orders.vue 整页围绕预购 useOrderList 构建，gacha tab 死占位；正确修需新 api + 不同 VO shape + 后端 gacha 历史 VO 补 orderNo + 改 history.vue 死路由 = 3 层，避免赶工改坏订单页，独立一轮） |

> **后端 3 模块（bean/recycle/common）一起 install SUCCESS；bean 43 / recycle 20 / common 34 单测全过。**

> **券回退口径决策（P2）**：doc/11 §11.3 未明确"用券单退款时券是否退还"。采**保守默认：券不退还**——退款只退实付（=单笔金额−券面额，用户付多少退多少），券让利已消费，退钱又退券=双重让利对甲方有风险。已在 `onPindouRefunded` 写 booking_log 留痕；如甲方要退券，加 1 行 `couponService.returnUsed`。

### 🟢 第三批（都做）— 进行中

**已完成 + 验证**：
- **死代码清理**：删 7 个 admin `Hello.vue` + 7 个纯 hello stub api（`api/gz-*.ts`）+ `gzHello` i18n（zh/en）+ 6 个后端 `*HelloController` + mp 死页 `bean/success.vue`（明文 verifyCode）+ `recycle/form.vue` 死 import。→ 后端编译 ✅ + plus-ui build ✅ + mp type-check 0 ✅
- **doc 修正 4 处**（修权威蓝图内部矛盾，防未来代码踩坑）：① doc/10 unpaid 占配额 → 不占（活跃=paying/paid，ADR-0008）② doc/11 估价 total_qty → 分品类 qty（F12.1）③ doc/11 booking_no `BK-yyyyMMdd-` → `BK<yyyyMMdd>`（无连字符，match 代码）④ doc/10 默认地址「DB约束+乐观锁」→ 事务内 reset-then-set
- **防御加固 2 项**：① 季度结算重跑守卫（已 paid/settled 季度遇 late 退款重跑 → 告警不覆盖 payable，recon 7 测试 ✅）② 资讯 `scheduled→draft` 取消定时（补漏流转，service+mapper+controller，定时设错可撤回改期）

**第三批续 — 已完成 + 验证**：
- **🟡 P7 扭蛋订单链路**：① mp orders.vue 扭蛋 tab 解死占位 → 接 `getUnifiedOrderList('gacha')` 真数据(状态/金额/获得物名，点卡→order-detail 物流+确认收货) ② gz-user.ts 加 `getUnifiedOrderList`(修原错误路径 /orders/list) ③ gacha/history.vue 死路由 → 跳「我的订单」(B4 后可用) → mp type-check 0 + build DONE ✅
- **🟢 防御加固 5 项**：video_urls 协议校验(news) / sanitizer 无引号伪协议正则(news) / 物流回退清快递三列(ord) / 待发货看板纳扭蛋单(recon dashboard) / lockForBooking 适用业务校验(coupon，纵深兜底) → news 48 + coupon 13 测试 ✅

**最终自检**：8 个 gz 模块一起 install SUCCESS · 后端 158 单测全过(bean43/recycle20/common34/news48/coupon13) · plus-ui build ✅ · mp type-check 0 + build DONE(pages.json 已去 success.vue)。

**明确 defer（带理由，非遗漏）**：
- **单 token 401 续期**：改鉴权关键路径(改错断登录) + 审计本就需真机验 + 仅一次性错误闪烁(自恢复) → 留真机验证时做
- **ord 深链 onLoad 兜底**：预购保留代码可恢复，加 redirect 反复杂化恢复 + 仅深链/历史码边缘可达(无资金风险) → 接受「无入口即可」
- **markPaying 补偿**：version 守卫 + 同事务行独占已挡，近不可达 → 加固价值极低
- **image_id 存在性校验**：无效 id 仅显空白(无安全/钱风险) → post-launch backlog
- **资讯计数防刷**：V1.0 显式取舍(仅计数污染) + Redis 滑窗复杂度不值 → post-launch backlog
- **gz_bean_pay_status 字典 / P1a doc §14.N6**：前者 0 运行影响且「建字典 vs 删注释」是决策项；后者 B4 已闭合资金核心 → 0-impact，留决策
- **真实支付 P3/P4**：Kevin #2 等甲方商户号下证联调

## 需 Kevin 决策 / 真机 / 甲方（不擅自代劳）

### 🔴 系统性必拍板（3 项 — 不可代码绕过）

| 项 | 问题 | 建议默认 |
|---|---|---|
| **SnailJob 上线方案** | 18 个定时任务（资讯定时发布/拼豆 no_show/券过期/支付·退款查单/对账日·月·季跑批）全挂默认关 SnailJob；doc/04「不启用」vs doc/10+代码冲突；**首月上线当天 owner 看分成必 ¥0** | 上线部署 SnailJob server + `SNAIL_JOB_ENABLED=true` + 控制台注册 18 executor（写进部署 checklist）；或全改 @Scheduled |
| **真实支付/退款资金兜底** | unpaid 超时关单前不查单（强关已付单无退款）；退款侧无主动查单 job（卡 refunding + 分成多算） | 真实商户号下证联调时补 closePindou 关单前查单 + PayRefundQueryJob；mock 期不触发 |
| **商户号/AppID/客服 kfid/美术资产** | 甲方外部前置 | 进上线 checklist 跟踪（你催甲方） |

### 🟡 上线前决策（每项附建议，拍板后我落代码）

1. **回收 retry 入口（B4 的 a）**：B4 收敛(b)已修闭合资金漏洞；是否再隐藏 payout 页对 recycle 单的 retry 按钮统一引导回回收单页？建议做（防运营困惑）+ 统一 doc §14.N6 vs §13.E4。
2. **prod 守卫 profile 名（B3）**：确认上线 profile = `prod` + 「漏配即拒绝启动」为期望（已按此实现，dev 不受影响）。
3. **拼豆退款 handler（P2）**：退款释放配额我可直接做；**退款时已抵扣的优惠券是否回退**？按 doc/11 §11.3 拍。
4. **回收 final_amount 上限（P5）**：建议 `≤估价×N`（N 走 sys_config 默认 3）软拦截抛错；但 doc §1545 F12.2(软校验) vs §1352 E3(仅留痕) 冲突，拍「拦截 vs 仅告警」+ 阈值。
5. **Excel 导出退款归属口径（P10）**：导出汇总按成交月还是退款发生月？建议直接取 monthly 落库值与对账中心对齐。
6. **店员权限即时回收（P11）**：补切面(改角色/撤权限即踢) vs 缩 mp token TTL vs V1 单店接受残余风险。建议补切面。
7. **扭蛋是否纳首版（P7）**：订单链路 C 端断裂已具体定位（我的订单 tab 写死空占位 + 跳死路由）；纳首版则我修三层接线，否则标 post-launch。

### 🟢 上线后决策（15 项，摘要）

估价口径(F12.1 修 doc)/默认地址唯一性(修 doc)/季度 late 退款重跑/资讯计数防刷/待发货看板纳 gacha/支付测试入口 5103 收口/ord 深链兜底/booking_no dash 口径/gz_bean_pay_status 字典/两个 /hello 端点去留 —— 详见 §🟢 各条 `needsHuman`，多为修 doc，可随时批量处理。

### 真机 / 甲方（不阻塞代码）

- mp 真机批量人验（D05-D14 积压一大批 ⬜）+ 本次修复项真机复验（付费单详情/扫码、回收列表错误态）
- 微信原生能力（wx.login/chooseAvatar/getPhoneNumber/企业客服）待甲方正式 AppID/kfid
- 回收 tab C 风图标 + 正式 UI emoji 替 SVG（待 designer 出图 + 甲方素材）
