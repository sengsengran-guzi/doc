# ADR-0019 多小程序（多 appid）支持

- **状态**：Accepted
- **日期**：2026-08-06
- **决策人**：Kevin
- **关联**：`FLOW:F-JP-00`（多小程序底座）/ REQ-SYS-004 / ADR-0009（登录态与 session 持久化）/ ADR-0003（支付通道 mock 降级）
- **关联 ticket**：GZ-DOC-001（本 ADR）+ SYS track 后续实施 ticket

---

## 背景

第二个小程序（独立 appid）要复用同一套后端。现有后端把微信 appid 建模成**单值标量**：

- `WxMiniappProperties.appid`（`wx.miniapp.appid`，`wxMOCK` = 走 mock 通道）
- `WechatPayProperties.appid`（`gz.pay.appid`）

real / mock 由 **8 处启动期条件 Bean** 全局互斥：real 侧 4 处 `@ConditionalOnExpression("'${wx.miniapp.appid:wxMOCK}' != 'wxMOCK'")`（`WxRealLoginAdapter` / `WxRealPhoneAdapter` / `WxRealAccessTokenManager` / `WxRealShippingClient`），mock 侧 4 处对称 `@ConditionalOnProperty(prefix="wx.miniapp", name="appid", havingValue="wxMOCK", matchIfMissing=true)`。JVM 启动那一刻整个进程只认一个 appid、只能整体是 real 或 mock。

**不改造的直接表现**：新小程序拿自己的 code 调 `/app/gz/common/auth/wx-login`，后端用旧 appid + 旧 secret 去 `jscode2session` → 微信返 `invalid code`，登录不通；即便绕过登录，下单拿到的 prepay_id 与调起签名也都是旧 appid，`uni.requestPayment` 必失败。这是一期唯一硬阻塞，须先于业务开发完成。

**路由载体已现成**：mp 请求带 `clientid` header（现小程序 `mp-applet-sensenran-guzi`，新小程序 `mp-applet-gz-jp`）。`SecurityConfig:66-74` 的校验是 token extra 与 header/param 的纯字符串比对、**不查 `sys_client` 表**，新增客户端零成本。因此不引入新维度，直接以 clientid 作「是哪个小程序」的路由键。

---

## 决策

### §1 配置 Map 化 + real/mock 运行时分派

**改什么**：`wx.miniapp` 由标量改 `Map<clientid, app>`，每个 app 独立持有 appid / secret / mock 判定 / TTL。real 与 mock 两套实现**都注册为 Bean**，在 `WxLoginAdapter` / `WxPhoneAdapter` / `WxAccessTokenManager` / `WxShippingClient` 之上加一层分派器：按当前请求的 clientid 解析出 app，再按该 app 的 `isMock()` 选实现。8 处 `@ConditionalOn*` 不再承担通道选择。

**为什么必须改**：mock/real 是**每个小程序各自的属性**，不是进程的属性——新小程序在 dev 阶段可能还没拿到 secret 必须走 mock，而现小程序 prod 已是 real。启动期条件 Bean 的粒度是进程级，表达不了「同一进程内 A real、B mock」。

**不改会怎样**：只能二选一。dev 要联调新小程序 → 全进程切 mock → **现小程序的真登录、真手机号、真 access_token、真发货上报一起失效**，回归无从做起；prod 保 real → 新小程序在没有 secret 时启动即配置不全，无法灰度接入。

> ⚠️ 这里**不包括支付**。支付的 mock/real 由另一个开关 `gz.pay.client-mode` 控制（`MockWechatPayClient` / `WechatPayV3ClientImpl:52` 各自 `@ConditionalOnProperty(prefix="gz.pay", name="client-mode")`），与 `wx.miniapp.appid` 无关 —— 把 appid 切成 wxMOCK 不会让真支付失效。详见 §5。

### §2 `access_token` Redis key 加 appid 维度

**改什么**：`WxRealAccessTokenManager` 的缓存 key `wx:miniapp:access_token` 改为 `wx:miniapp:access_token:{appid}`；刷新、读取、失效重取三条路径一律按 appid 取。

**为什么必须改**：`cgi-bin/token` 返回的 access_token 是 appid 维度凭证，两个小程序的 token 值不同且互不通用。key 不带 appid → 两端共享同一个 Redis 槽位，后刷新者覆盖先刷新者。

**不改会怎样**：手机号解密（`getPhoneNumber`）、发货信息上报（`upload_shipping_info`）、客服等所有 access_token 消费方会随机拿到另一个小程序的 token → 微信返 40001 `invalid credential`。因为是缓存竞争，故障表现为**间歇性失败**（重试可能又好了），是四点里最难定位的一处；发货上报失败还直接影响资金结算（微信曾就未发货订单发过警告）。

### §3 支付：统一下单与**调起签名**的 appid 从下单上下文取

**改什么**：`WechatPayV3ClientImpl:93`（`request.setAppid(props.getAppid())`，统一下单）与 `WechatPayV3ClientImpl:125`（`String message = props.getAppid() + "\n" + ts + ...`，5 参调起签名）都不再读全局 `props.getAppid()`，改由下单上下文（`UnifiedOrderRequest` / 构建 `JsapiPayParams` 的入参）携带。真源落到 **`gz_pay_channel.appid`** —— 该列建表即有（`V202606041200`），当前是 placeholder 值、从未被读过，本次激活为按小程序一行的通道配置。商户号（`mch_id`）两端共用不变。

**为什么必须改**：JSAPI 的 prepay_id 与 appid 绑定，调起签名的第一个因子也是 appid。商户号可以共用，appid 不可。签名 appid 与实际调起方 appid 不一致，微信侧验签直接不过。

**不改会怎样**：`:93` 写死 → 新小程序拿到的是「属于旧 appid 的 prepay_id」，`uni.requestPayment` 报 appid 与 prepay_id 不匹配。更隐蔽的是只修 `:93` 漏了 `:125`：下单接口返 200、日志一切正常，前端调起时才报签名错误，排查会被日志指向错误方向。**`:125` 是本次改造最容易漏的一处。**

### §4 `gz_user` 加 `app_id` 列，唯一键改三元组

**改什么**：`gz_user` 加 `app_id VARCHAR(32) NOT NULL`（存量行回填现小程序 appid `wx2f8b93e09703f07d`），唯一键由 `uk_tenant_openid (tenant_id, openid)` 改为 `(tenant_id, app_id, openid)`；微信登录按 `app_id + openid` upsert。

**为什么必须改**：openid 是 **appid 维度**标识，微信只保证在单个 appid 内唯一。两个小程序对同一自然人下发不同 openid，且跨 appid 不保证不撞。

**不改会怎样**：新小程序的用户落进同一张表、同一个二元唯一键。运气好是各自新建行；一旦两个小程序的 openid 撞上，第二个小程序的用户会**直接登进第一个小程序某人的账号**，拿到别人的订单、券与会员权益。这是数据串户级事故，不是「功能不通」量级的问题。

---

### §5 `gz.pay.client-mode` 保持进程级全局，一期刻意不 Map 化

**改什么**：不改。支付客户端的 mock/real 由 `gz.pay.client-mode`（`mock` / `real`）单独控制，
是与 `wx.miniapp.appid` **完全正交的第二个开关**，本次不动它。

**为什么不改**：同一环境下两个小程序的收款模式必然相同 —— dev 全 mock、prod 全 real。
把它也 Map 化只会引入一个没有真实场景支撑的维度，还多一处配置要对齐。

**什么情况下要推翻**：将来要「一个小程序 mock 收款、另一个 real 收款」（例如新小程序灰度期先不接真钱）。
那时按 §3 同样的形态把 `client-mode` 也下沉到 `gz_pay_channel` 按渠道取。

**为什么必须写下来**：`wx.miniapp.appid` 与 `gz.pay.client-mode` 长得像、位置近、都叫 mock/real，
实施 §1 时极易顺手把它一起 Map 化 —— 那会让支付客户端的装配条件从进程级变成请求级，
而 `IWechatPayClient` 是单例注入，运行时切换会拿到错误实现。

---

## 被否决的方案：unionid 合并

**方案**：不加 `app_id`，两小程序用 `unionid` 认同一个自然人，一条 `gz_user` 服务两端。`gz_user.unionid` 列建表即有（`V202605281000`），当前 NULL-able、只有普通索引 `idx_tenant_unionid`。

**否决理由**：

1. **前置条件在甲方手里**——unionid 只有把两个小程序绑到**同一个微信开放平台账号**才下发。这是甲方的账号治理动作，工期不可控，而多 appid 是一期硬阻塞，不能等。
2. **当前 prod 该字段极可能全为 NULL**——建表注释即写明「甲方未绑公众号/开放平台时为 NULL」，且现有登录链路从未写过它。拿一个可能整列为空的字段当主身份键，等于把「用户能不能登录」变成运行时不确定。
3. **合并身份是商业口径变更**——一条记录服务两端意味着余额、订单、券、会员权益全部打通，必须甲方明确要，不能由技术侧默认选择。

**一期口径**：同一自然人在两个小程序 = 两条独立 `gz_user` 记录，互不干扰。

**列为后续增强，不是永久否决。复活条件**（三条同时满足）：

- 甲方已把两个小程序绑到同一开放平台账号，且抽样验证登录回包**稳定**带 unionid；
- 甲方书面确认要打通两端的用户资产（订单 / 券 / 会员权益）口径；
- 有可执行的存量合并方案（同 unionid 多条 `gz_user` 的资产归并规则 + 主记录选取 + 回滚路径）。

届时 **`app_id` 列保留不删**——它记录「这条记录来自哪个小程序」，是合并时的溯源依据，与 unionid 作主身份键不冲突。

---

## 影响面

改的是线上**正在跑的登录与收款核心**，四个改造点在同一个窗口内落地。每一点都必须对**现有小程序**做全量回归——「新小程序通了」不是验收条件，「现有小程序没坏」才是。

| 改造点 | 现有小程序回归项 |
|---|---|
| §1 配置 Map 化 + 运行时分派 | prod real 登录 + dev mock 登录各跑一轮；确认 8 处条件 Bean 退场后 mock 侧不会被 real 实现顶掉（两套 Bean 同时在容器里，分派器选错就是静默走错通道） |
| §2 `access_token` key 加 appid | 手机号绑定 + 发货信息上报各跑一轮（这两条是 token 的真实消费方；发货上报影响资金结算，必验） |
| §3 支付 appid 从上下文取 | 现小程序真实下单 → 调起 → 回调 → 退款全链路，用 1 分真钱单（`gz.pay.test.amount-cent`）。`gz_pay_channel.appid` 从 placeholder 换成真值这一步本身就改变现小程序行为，不能只在新小程序上验 |
| §4 `gz_user` 加列改唯一键 | 迁移内先回填 `app_id` 再建新唯一键（NOT NULL 列加到有数据的表上，回填与约束须在同一迁移里有序完成）；回填后核对 `gz_user` 总行数 == `(tenant_id, app_id, openid)` 去重行数，不一致说明存量本就有脏数据，停下来查清再继续 |

**不需要额外做的**：mp 登录态本就与 clientid 绑定（`SecurityConfig:66-74` 校验 token extra 与 header 一致），两个小程序的 token 天然互不通用，无需再加隔离；新增 clientid 不落 `sys_client` 表，无迁移成本。
