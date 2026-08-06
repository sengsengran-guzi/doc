# GZ-SYS-022 微信支付多 appid（配置 + 统一下单 + 调起签名）— 完工报告

> **结论**：accept 两条 **全 PASS**（15 个新单测全绿）。
> **现有小程序（谷子宇宙）回归 = 绿**：拼豆「下单 → 5 参签名 → mock 回调 → paid → 重复回调幂等」全链路走通，且断言了下单与调起签名拿到的是**同一个、且是现小程序的** appid（`wx2f8b93e09703f07d`）。
> 全模块回归 gz-common **220 tests 全绿**；gz-ord / gz-gacha / gz-user / gz-recycle / gz-coupon 全绿。gz-bean / gz-news 各有失败，**均为改造前就存在、与本卡零关联**，取证见 §AI 自测 5。
>
> ⚠️ **真机 1 分钱真钱验证未做**（AC 明确推迟到 appid 回补阶段）—— 留给 Kevin 的 Tier 2 清单见 §风险提示。

---

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态（RuoYi-Vue-Plus，branch `staging`，HEAD `0e5d2bf7c`） | ✅ 开工前工作区含 GZ-SYS-020 未提交产物（预期，主线程统一收尾） |
| §0.1 `WechatPayV3ClientImpl` `:93` / `:125` 两处 appid 读点仍在原位 | ✅ 确认（raw 见下） |
| §0.2 `gz_pay_channel.appid` 列存在 + seed 是占位值 | ✅ 列在、值 = `wx_placeholder_appid`（从未被读过） |
| §0.3 ★ `gz.pay.client-mode` 保持进程级全局、**不 Map 化** | ✅ 一行未动（ADR-0019 §5） |
| 编译健康（基线） | ✅ 改动前 `mvn test-compile -pl ruoyi-gz-common -am` EXIT=0 |
| ADR 已读 | ✅ ADR-0019（§3 本卡范围 / §5 刻意不动 client-mode / §影响面「现小程序没坏才是验收条件」） |
| 上游 GZ-SYS-020 对接说明已读 | ✅ 其 report「给 GZ-SYS-022」段 4 条全部采纳 |
| 蓝图引用 | ✅ `FLOW:F-JP-00.step4` |
| Flyway append-only 自检 | ✅ 迁移目录 `git status` 全空（无 M/D/R）；已有最大版本 `V202607272121`，新建 `V202608062249`（`date +V%Y%m%d%H%M` 当下真实时间）> 最大版本 |

### §0.1 raw output（改造前）

```
$ sed -n '85,130p' .../pay/service/internal/WechatPayV3ClientImpl.java
 91:    public String createJsapiOrder(UnifiedOrderRequest req) {
 92:        PrepayRequest request = new PrepayRequest();
 93:        request.setAppid(props.getAppid());                       ← :93 统一下单，在位
...
118:    public JsapiPayParams buildPayParams(String prepayId) {
125:        String message = props.getAppid() + "\n" + ts + "\n" + nonce + "\n" + pkg + "\n";   ← :125 调起签名，在位
```

### §0.2 raw output

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "DESC gz_pay_channel"
id  channel_code  display_name  appid  mch_id  api_v3_key_ref  mch_cert_serial
notify_url  refund_notify_url  enabled  tenant_id  create_dept  create_by
create_time  update_by  update_time  del_flag  remark
       ↑ appid 列在；无 client_id 列（本卡新增）

$ SELECT id,channel_code,appid,mch_id,enabled FROM gz_pay_channel;
1  wechat_pay_v3  wx_placeholder_appid  mch_placeholder  1
   ↑ appid 是建表 seed 占位值 —— 印证 ADR「建了从未被读过」
```

---

## 实现摘要

```
本卡改动（不含 GZ-SYS-020 / 021 / 023 在同一工作区的产物）：
 ruoyi-admin/src/main/resources/application-dev.yml           gz.pay 段注释（无值变更）
 ruoyi-admin/src/main/resources/application-prod.yml          gz.pay 段注释（无值变更）
 .../pay/config/WechatPayProperties.java                      |  16 ++-
 .../pay/domain/entity/GzPayChannel.java                      |  16 ++-
 .../pay/domain/vo/GzPayChannelVO.java                        |   3 +
 .../pay/service/impl/GzPayTransactionServiceImpl.java        |  23 +++-
 .../pay/service/internal/IWechatPayClient.java               |  18 +++-
 .../pay/service/internal/MockWechatPayClient.java            |  11 +-
 .../pay/service/internal/WechatPayV3ClientImpl.java          |  37 ++++++-
 .../pay/service/GzPayBusinessFullChainMockTest.java          | 118 +++++++++++++++++-
 .../pay/service/GzPayTransactionServiceImplTest.java         |  16 ++-
 gz-ord .../PreorderFullChainMockTest.java                    |   7 +-

新增（untracked）：
 .../pay/service/internal/PayAppidResolver.java                       ← 「这一单用哪个 appid」唯一来源
 .../pay/service/WechatPayMultiAppidTest.java                         ← accept[1]（15 个用例）
 db/migration/V202608062249__GZ-SYS-022-gz_pay_channel-add-client_id.sql
```

### §1 契约改造：appid 变成「必填形参」，不再是全局配置

- `UnifiedOrderRequest` 加 `String appid`（`:93` 用它）。
- `buildPayParams(String prepayId)` → **`buildPayParams(String prepayId, String appid)`**（`:125` 用它）。

做成**必填形参而不是让实现内部去查**，是为了让编译器接管上游点名的那个坑：「只改 `:93`、漏了 `:125`」在运行期表现为**下单返 200、日志全绿、前端调起才报签名错**。改成形参后任何调用点都必须交代 appid。生产调用点只有一个（`GzPayTransactionServiceImpl.createOrderInternal`），它**解析一次、两处复用同一个值** —— 两处分别解析是另一种隐蔽错法，故意规避。

### §2 `PayAppidResolver`：三级优先级 + 降级不阻断

| 级 | 来源 | 说明 |
|---|---|---|
| ① | **`gz_pay_channel.appid`**（按新增的 `client_id` 列一行） | ADR-0019 §3 指定真源，本卡激活。配了就赢。空 / 建表占位值 → 视同没配 |
| ② | `wx.miniapp.apps.<clientid>.appid`（GZ-SYS-020 已 Map 化） | **默认走这条** |
| ③ | `gz.pay.appid`（改造前的全局标量） | 纯兜底，保证历史配置形态不劣化 |

**为什么默认是 ② 而不是 ①（本卡唯一需要 Kevin 追认的判断）**：`payer.openid` 是登录时用**那个 appid** 换来的，openid 是 appid 维度标识 —— 两者必须同源，否则微信返「openid 与 appid 不匹配」。把默认值取自「签发 openid 的那个 appid」，同源就是**结构上成立**的；若默认改成读 DB，同源退化成「靠两处配置人工对齐」，多一个环境、多一次回补就多一次错配机会，而错配的表现恰恰是最难查的那类微信含糊报错。所以：**DB 保留为最高优先级的显式覆盖（ADR §3 的真源地位不变），但不作为默认取值路径。**

**对 prod 现状的影响 = 零**：prod DB 那行 `appid` 是 seed 占位值 → ① 跳过 → ② 取 `wx.miniapp.appid` = `wx2f8b93e09703f07d` = **改造前 `gz.pay.appid` 的同一个值**。本卡跑或不跑、迁移应用或不应用，现小程序下单/签名的实际 appid 逐字不变。

其余两个设计点：
- **clientid 用宽松口径**（`currentAppOrDefault()`）：`POST /system/gz/pay/test` 是 plus-ui 后台发的通道测试单，带 PC 客户端 id。用严格口径会让后台按钮抛「未配置的小程序客户端」，正是 GZ-SYS-020 §6 打挂发货补报按钮的同款事故。已加防回归单测。
- **DB 查询失败只降级、绝不阻断下单**：① 是可选覆盖不是硬依赖。在一条正在收款的链路上，新引入的「可选增强」不允许成为新的失败点。已加单测。

### §3 real 通道 appid 真实性校验（新增 fail-fast）

`:93` / `:125` 前各校验一次：null / 空白 / `wxMOCK` / 建表占位值 → 直接抛，报文点明是「统一下单」还是「调起支付签名」这一步、该改哪个配置。放行这些值的后果是微信返「appid 不存在 / 与 mch_id 未绑定 / 验签失败」这类含糊错误，排查成本高得多。mock 通道不校验。

### §4 `gz_pay_channel` 加 `client_id`（迁移 `V202608062249`）

不复用 `channel_code`：它是通道类型语义且被 `gz_pay_transaction.channel_code` 写死引用，兼做小程序维度会让两个语义纠缠。迁移是纯 `ADD COLUMN`（可空）+ 只回填 `wechat_pay_v3` 那一行 + 加 `UNIQUE(tenant_id, client_id, del_flag)`。**不动任何既有行的业务字段、不动 `appid` 值**。日本拼团刻意不建行（appid 没拿到，建空行只是噪音）。

### 不做（守边界）

- ❌ **不把 `gz.pay.client-mode` Map 化**（ADR-0019 §5）—— 一行未动。
- ❌ 不照抄 020 的 `WxAdapterDispatcher` 模式：支付只有一个 `IWechatPayClient` 实现，本卡纯粹只解决「appid 从哪里取」。
- ❌ 不动回调 / 查单 / 关单 / 退款：只用 `mch_id`，回调 URL 按 `out_trade_no + business_type` 路由，两端共用不变。
- ❌ 不给 `gz_pay_transaction` / `gz_pay_shipping_order` 加 app 维度（超出 What/AC，见 §对下游）。

---

## AI 自测（Tier 1A）

### 1. accept[1] —— 先跑 prompt.md 字面命令（失败，命令形态问题，非代码问题）

```
$ cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-common -am -Dtest=WechatPayMultiAppidTest 2>&1 | tail -5
[ERROR] For more information about the errors and possible solutions, please read the following articles:
[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/MojoFailureException
[ERROR]
[ERROR] After correcting the problems, you can resume the build with the command
[ERROR]   mvn <args> -rf :ruoyi-common-core
```

根因与 GZ-SYS-020 报告 §0.5 完全一致（`-am` 拉入 21 个上游模块，`-Dtest=X` 对每个模块生效）。与本卡代码无关。

### 2. accept[1] 修正命令 —— ✅ PASS

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am \
    -Dsurefire.failIfNoSpecifiedTests=false -Dtest=WechatPayMultiAppidTest
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0 -- in org.dromara.gz.common.pay.service.WechatPayMultiAppidTest
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

同一次运行的关键业务日志：

```
[gz-pay] createJsapiOrder out_trade_no=PINDOU-20260806-000001 appid=wxjp0000000000jp01 → prepay_id=wx_prepay_from_sdk
[gz-pay] buildPayParams prepay_id=wx20260806JP0001 appid=wxjp0000000000jp01
[gz-pay] 建单成功 business_type=pindou out_trade_no=PINDOU-20260806-000001 business_order_no=BK-GUZI-001 amount=3000 appid=wx2f8b93e09703f07d ...
[gz-pay] 建单成功 business_type=pindou out_trade_no=PINDOU-20260806-000002 business_order_no=BK-JP-001   amount=3000 appid=wxjp0000000000jp01 ...
       ↑ 同一个 JVM、同一个单例 service，切 clientid 后 appid 跟着切
[gz-pay] 读取 gz_pay_channel 失败（clientid=mp-applet-sensenran-guzi），降级用 wx.miniapp 的 appid：Unknown column 'client_id'
       ↑ 降级路径的真实日志（单测注入 DB 异常），下单没被打断
```

**15 个用例覆盖**：

| 段 | 用例 |
|---|---|
| §A 调起签名 :125 | ★ 真 RSA 验签：paySign 用「上下文 appid」拼的 message 验得过、用「全局 `gz.pay.appid`」拼的验不过、用「另一个小程序 appid」拼的也验不过 · 同一 prepay_id 两个小程序签出的 paySign 各自只对自己成立且互不相等 · 6 种不可用 appid 全部 fail-fast |
| §B 统一下单 :93 | 反射注入 mock SDK 捕获 `PrepayRequest`：appid = 上下文 appid ≠ 全局配置 · mch_id 共用不变 · payer.openid 同源 · 烂 appid 时根本不发请求给微信 |
| §C 解析优先级 | 两 clientid 各自 appid · DB 行覆盖生效 · 占位值被忽略 · DB 抛异常只降级 · **后台 PC clientid 不抛错** · 无请求上下文落默认 · 单值形态 = prod 现状 · 三级兜底 · 全空报错 |
| §D 端到端 | 同进程切 clientid 两次下单：下单 appid 与签名 appid **成对**且各自正确 |

> §A 用真 RSA 密钥对做**密码学验签**而不是断言两个 String 相等 —— 后者只能证明参数被读到了，前者证明**被签进去的那串字节**就是上下文 appid。这是 ADR-0019 §3「最容易漏的一处」唯一过硬的证据。

### 3. accept[2]「签名 appid 不再来自全局配置（防回归）」—— ✅ PASS

```
$ ! grep -nE 'props\.getAppid\(\)\s*\+\s*"\\n"' \
    code/main/RuoYi-Vue-Plus/.../pay/service/internal/WechatPayV3ClientImpl.java
ACCEPT2_EXIT=0

# 顺带扫全文件（比 accept 更严）：
$ grep -n "props.getAppid()" .../WechatPayV3ClientImpl.java
（无输出 = 零残留，:93 与 :125 都不再读全局）
```

### 4. ★ 现有小程序（谷子宇宙）回归 —— 拼豆下单 → 签名 → mock 回调（accept 之外，追加）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am \
    -Dsurefire.failIfNoSpecifiedTests=false -Dtest=GzPayBusinessFullChainMockTest
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0 -- in ...GzPayBusinessFullChainMockTest
[INFO] BUILD SUCCESS

# 同次运行日志（真 MockWechatPayClient + 内存 DB 模拟 UNIQUE/乐观锁，非纯 mock 桩）：
[gz-pay] 建单成功 business_type=pindou out_trade_no=PINDOU-20260806-000001
         business_order_no=BK20260806-000123 amount=3000 appid=wx2f8b93e09703f07d
         prepay_id=mock_prepay_PINDOU-20260806-000001
[gz-pay] 补单成功 out_trade_no=PINDOU-20260806-000001 business_type=pindou → paid
         transaction_id=mock_wx_txn_PINDOU-20260806-000001
[gz-pay] 建单成功 ... appid=wxCHANNEL_OVERRIDE ...      ← 第二个用例：DB 行覆盖生效
```

新增的两个回归用例逐条断言「与改造前一致」：
- `out_trade_no` 前缀 `PINDOU-` + 日内序号从 `000001` 起
- `status`=pending、`business_type`=pindou、`business_order_no` 落库、`channel_code`=`wechat_pay_v3`
- `fee_cent` 建单留 NULL（PAY-104 回写口径不变）
- `packageVal`=`prepay_id=<mock prepay>`、`signType`=`RSA`、`paySign` 仍以 `mock_pay_sign_` 开头（**mock 5 参格式逐字未变** —— mp / E2E 对这个前缀有断言）
- ★ `createJsapiOrder` 与 `buildPayParams` 的 appid **都等于 `wx2f8b93e09703f07d`（现小程序）**，且 `payer.openid` 就是本单 openid（同源）
- mock 回调 → `paid` + `transaction_id` 落库 + `callback_log` = received/processed
- 重复回调 → 仍 `paid` + `duplicated`（幂等未破）

preorder / test 单两条原有全链路用例**一行未改、仍全绿**。

### 5. 全模块回归 + 两处「不是我的」失败的取证

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am
[INFO] Tests run: 220, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

$ mvn -o test -DskipTests=false --fail-at-end -pl <ord,bean,gacha,user,recycle,news> -am
[INFO] ruoyi-gz-common .................................... SUCCESS
[INFO] ruoyi-gz-coupon .................................... SUCCESS
[INFO] ruoyi-gz-bean ...................................... FAILURE
[INFO] ruoyi-gz-user ...................................... SUCCESS
[INFO] ruoyi-gz-news ...................................... FAILURE
[INFO] ruoyi-gz-gacha ..................................... SUCCESS
[INFO] ruoyi-gz-ord ....................................... SUCCESS
[INFO] ruoyi-gz-recycle ................................... SUCCESS

全部失败用例（共 3 个，集中在 2 个类）：
GzBeanBookingServiceImplTest.releaseSeatEarly_overtime_clampsToSlotEnd  expected: <23:00> but was: <00:00>
GzNewsArticleServiceImplTest.insertByBo_happyPath_draft                 UnnecessaryStubbingException
GzNewsArticleServiceImplTest.insertByBo_sanitizesXss                    UnnecessaryStubbingException
```

**取证 —— 两处都与本卡零关联**：

```
$ git diff HEAD --stat -- ruoyi-modules/ruoyi-gz-bean ruoyi-modules/ruoyi-gz-news
（空 —— 这两个模块的工作区就是 HEAD 版本，跑的是已提交代码）

$ grep -rn "buildPayParams\|UnifiedOrderRequest\|PayAppidResolver" \
    ruoyi-modules/ruoyi-gz-bean/src/ ruoyi-modules/ruoyi-gz-news/src/
（空 —— 两个模块完全不引用本卡改动的任何契约）
```

各自根因（已定位到行，均为改造前就存在）：

1. **gz-bean `releaseSeatEarly_overtime_clampsToSlotEnd` = 挂钟依赖的既有 flaky，且是真实的跨日边界 bug。** `GzBeanBookingServiceImpl:3426-3427`：
   ```java
   LocalTime ceil = ceilToHour(now.toLocalTime());
   LocalTime actualEndSlot = ceil.isAfter(booking.getSlotEnd()) ? booking.getSlotEnd() : ceil;
   ```
   本次运行时刻为 **23:0x**：`ceilToHour(23:0x)` 在 `LocalTime` 上回绕成 `00:00`，而 `00:00.isAfter(23:00)` = **false** → clamp 不触发 → 写入 `00:00`（测试期望 `23:00`）。任何非 23 点区间运行都会通过 —— 但反过来说，**生产上 23 点档放座会写出 `actual_end_slot=00:00`，clamp 形同虚设**。真实缺陷，不在本卡范围，已列入 §风险提示，建议单开 ticket。

2. **gz-news 2 个用例 = 陈旧 stub。** 生产 `generateArticleNo` 调 `baseMapper.selectMaxArticleNoIncludeDeleted(prefix)`（`GzNewsArticleMapper:70`），测试仍 stub `baseMapper.selectOne(any(Wrapper.class))`（测试 `:251` / `:274`）→ 该 stub 永不被用到 → Mockito 严格模式判 `UnnecessaryStubbingException`。是「D17 article_no 软删冲突修复」把查询换成自定义 mapper 方法后测试没跟着改。

### 6. Flyway 迁移验证

**6a. 真实 Flyway 应用（dev 库，`success=1`）** —— 并行跑的 GZ-SYS-021/023 重启了 8080 上的应用，Flyway 自动把本卡迁移一并应用了（非手工执行）：

```
$ SELECT version,script,success,installed_on FROM flyway_schema_history WHERE version LIKE '20260806%';
202608062249  V202608062249__GZ-SYS-022-gz_pay_channel-add-client_id.sql  1  2026-08-06 23:00:17
202608062251  V202608062251__GZ-SYS-023-alter-gz_user-add-app_id.sql      1  2026-08-06 23:00:17

$ SELECT id,channel_code,client_id,appid,enabled,tenant_id,del_flag FROM gz_pay_channel;
1  wechat_pay_v3  mp-applet-sensenran-guzi  wx_placeholder_appid  1  1001  0
   ↑ 回填成功；appid 仍是占位值 → 解析器降级取 wx.miniapp = 现小程序原行为

$ SHOW INDEX FROM gz_pay_channel WHERE Key_name='uk_tenant_client_id';
uk_tenant_client_id  1 tenant_id / 2 client_id / 3 del_flag   Non_unique=0
```

**6b. 独立 scratch DB 从「真·迁移前」状态复跑**（克隆真实表结构+数据，DROP 掉列与索引回退，再造一行「历史遗留通道行」）：

```
--- 迁移前 ---
1  wechat_pay_v3  wx_placeholder_appid
2  legacy_other   wx_other

--- 执行迁移 ---（无任何错误输出）

--- 迁移后 ---
1  wechat_pay_v3  mp-applet-sensenran-guzi  wx_placeholder_appid   ← 只回填这一行
2  legacy_other   NULL                      wx_other               ← 历史行不动、不撞唯一键

  `client_id` varchar(64) DEFAULT NULL COMMENT '归属小程序 clientid（...）；NULL=不参与按小程序解析',
  UNIQUE KEY `uk_tenant_channel_code` (`tenant_id`,`channel_code`),
  UNIQUE KEY `uk_tenant_client_id` (`tenant_id`,`client_id`,`del_flag`),
```

唯一键语义三连验：

```
① 再插一行 client_id=NULL      → 成功（多个 NULL 并存，历史行安全）
② 再插一行同 client_id（启用）  → ERROR 1062 Duplicate entry '1001-mp-applet-sensenran-guzi-0'
                                    for key 'gz_pay_channel.uk_tenant_client_id'   ← 防「同一小程序两行配置」
③ 软删原行后同 client_id 新建   → 成功（del_flag 进唯一键 = 软删可复用，仓库铁律）
```

scratch 库已 `DROP DATABASE`，`SHOW DATABASES LIKE 'gzsys022%'` 无输出。

### 7. 编译健康（全仓，含 ruoyi-admin 打包模块）

```
$ mvn -o test-compile -DskipTests=false -pl ruoyi-admin -am
[INFO] ruoyi-admin ........................................ SUCCESS [  1.098 s]
[INFO] BUILD SUCCESS
```

### 8. 后台进程

本卡实施过程**未启动任何后台进程**。8080 上的 java 进程是并行 ticket / Kevin 自己的 dev server，全程未触碰（也因此本卡没做「真起应用 + curl」验证，避免打断并行工作）。

---

## 风险提示 / 已知 issue

### 还剩什么没验（→ Kevin Tier 2 残留人验清单）

1. **⚠️ 真机 1 分钱真钱支付未验（AC 明确推迟）。** 一期两个小程序都没有真 appid/secret，拉不起真收银台。**留给 Kevin 的检查项（appid 回补阶段、`gz.pay.client-mode=real` 之后各跑一次）**：
   - [ ] **现小程序（谷子宇宙）真机 1 分钱单**：下单 → `uni.requestPayment` **能拉起收银台**（拉不起 = 签名 appid 错）→ 付款成功 → 回调 → 订单 `paid` → 退款。用 `gz.pay.test.amount-cent`。★ 本卡**最重要**的人验项：改的是它正在跑的收款链路。
   - [ ] **拼团小程序真机 1 分钱单**：同上一遍（验新 appid 通）。
   - [ ] 两个小程序**交叉验证**：A 下的单不能用 B 的 appid 调起（应报错而非静默成功）。
   - [ ] prod 切 real 后看一眼日志 `[gz-pay] createJsapiOrder ... appid=` / `buildPayParams ... appid=`，确认是期望的那个 appid（本卡新加的两行日志就是给这一刻用的）。

2. **本卡对现小程序的行为变更 = 零，但依赖一个前提**：prod `gz_pay_channel.appid` 保持 seed 占位值。**若有人手工改成别的值，那个值会立刻接管收款 appid**（① 优先级最高）。回补阶段若要用 DB 覆盖，必须与 `wx.miniapp` 的 appid 一致，否则 `payer.openid` 与 appid 不同源 → 微信拒付。已在迁移注释与实体 javadoc 写明。

3. **prod 尚未配 `wx.miniapp.apps`（仍是单值形态，020 有意保留）**：拼团小程序在 prod 会被拒。上线前需 ①`application-prod.yml` 切 apps 形态 ②`docker-compose.deploy.yml` 补 `WX_JP_MA_APPID` / `WX_JP_MA_SECRET` 透传（020 已点名的 ops 缺口）—— **补了 wx.miniapp，支付这边就自动通，不需要再配第二处**。

4. **【本卡外的既有缺陷，建议单开 ticket】gz-bean 放座跨日边界**：`GzBeanBookingServiceImpl:3426` 的 `ceilToHour(now)` 在 23:00-24:00 回绕成 `00:00`，使 clamp 失效。影响：23 点档放座写出的占用止界是当日 `00:00`。对应单测每天 23:00-24:00 稳定失败。**与本卡无关，本卡未修**，建议后续单开 ticket。

5. **【本卡外的既有缺陷】gz-news 2 个单测陈旧 stub**（见 §AI 自测 5），修一行即可，未动。

6. **多小程序并行 real 的两个已知缺口**（不在本卡范围，会影响真机验证的编排）：`access_token` 缓存 key 隔离 = GZ-SYS-021（已并行完工）；`gz_user` 按 app_id 隔离 = GZ-SYS-023（已并行完工）。appid 回补阶段两张卡已落地，不再是限制。

7. **待 Kevin 残留人验（mp 侧）**：**N/A** —— 纯后端，无 mp 页面变更、无新页可达性问题。

### 与 prompt.md / 上游报告不一致之处（需要主线程知道）

| 描述 | 实际 |
|---|---|
| accept 命令可直接跑 | ❌ 同 020 §0.5：`-am` + `-Dtest` 必须加 `-Dsurefire.failIfNoSpecifiedTests=false`。**021 / 023 同款写法，同样要加** |
| `touches` 只列 `pay/**` + `application*.yml` | 实际还动了 `db/migration/`（新增 1 个迁移）与 3 个测试文件（构造器签名变更的连带） |
| ADR-0019 §3「真源落到 `gz_pay_channel.appid`」 | 已激活为**最高优先级覆盖**，但**默认取值路径是 `wx.miniapp`**（同源保证）。理由见 §实现摘要 §2，是本卡唯一需 Kevin 追认的判断；若要求 DB 无条件当默认真源，改法是删掉优先级 ② 并在迁移里把 prod 那行 appid 回补成真值（**那样 prod 行为会立刻依赖这次 DB 写入是否正确**，风险更高） |

---

## 对下游 ticket 的提示

**给「appid 回补阶段」**：补 appid 的**唯一必要动作**是 `wx.miniapp.apps.<clientid>.appid` + `secret`（登录 / 手机号 / access_token / 发货 / **支付** 全部跟着走）。`gz.pay.appid` 与 `gz_pay_channel.appid` **都不需要动**。

**给未来做「按小程序拆分资金/发货」的 ticket**：`gz_pay_transaction` 与 `gz_pay_shipping_order` **仍没有 app 维度**（本卡刻意未加）。现状后果：`@Async` / cron 的发货上报按 `default-client-id` 取 access_token。两个小程序都真上报时必须给这两张表加归属 clientid。建议：`gz_pay_transaction` 加 `client_id`（下单时写入，与本卡解析结果同源），`gz_pay_shipping_order` 从交易行继承。

**给任何要改 `IWechatPayClient` 的人**：`buildPayParams(prepayId, appid)` 的 appid 是**必填形参**。不要为了「省事」加一个读全局配置的重载 —— 那正是本卡拆掉的东西。

---

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

（占位 —— 纯后端：admin 无页面变更、mp 无页面变更。Tier 1B 建议范围 = ① 后端集成：mp 拼豆下单真起应用打一遍，看日志 `appid=` 是否为现小程序 appid；② admin 通道测试单 `POST /system/gz/pay/test`（**PC clientid 场景**，本卡最易翻车处，务必真点）；③ admin 支付管理 → 通道配置列表页（VO 加了 `clientId` 字段，验证页面不炸）；④ mp 模拟器 E2E 拼豆付费流回归（验证 5 参签名格式未变）。）

---

**一句话结论：accept = PASS（两条全绿，15 个新单测含真 RSA 验签证明 `:125` 签的就是上下文 appid）；现有小程序（谷子宇宙）拼豆下单→签名→mock 回调→幂等 全链路回归 = 绿，且 prod 实际 appid 取值逐字不变。**
