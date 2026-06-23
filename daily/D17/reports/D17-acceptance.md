# D17 — 上线前整体验收（产品 + 安全 + 设计角度）

> 性质：第一版上线前的整体验收测试（workflow 多 agent 编排）。立场 = 资深产品 + 安全负责人，生产前最后一道关。
> 方法：8 域并行评审（T1-T8）+ 重跑 3 个崩溃域，每条 finding 对抗式复核杀误报；主线程并行跑 H5 视觉走查 + 真实 API/DB 探测。
> 环境：dev profile / wxMOCK 通道 / mock 全链路（真实微信支付·打款·getPhoneNumber·客服 = 商户号下证后单独回归，不在本轮）。

## 结论

确认 **24 条 finding**（去重）：🔴 4 / 🟠 4 / 🟡 13 / 🟢/polish 3，外加验证中新发现 1 条（article_no 软删冲突）。
**AI 已闭环修复 21 条 + 全部 runtime 回归通过**；3 条 = 甲方内容依赖 / V1.1 增强，列上线 checklist。

## 已修 + 回归（全绿）

| # | Sev | 域 | 问题 | 修复 | 回归证据 |
|---|---|---|---|---|---|
| T4.4 | 🔴 | 资讯 | 网关 XssFilter 剥光后台富文本所有标签 → CMS 富文本+内嵌图端到端不可用 | application.yml `xss.excludeUrls` 加 `/system/gz/news/article`，XSS 交业务层 jsoup HtmlSanitizer 白名单兜底 | admin 建含 `<p>/<img>/<script>` 文章 → DB 存 `<p><h2><img>` 保留、`<script>/onerror` 剥除 ✅ |
| T6.3 | 🔴 | 支付 | `out_trade_no` 用 DB MAX+1 + 仅重试3次 → 并发付款大面积 500（死锁/撞键），影响全部业务收款 | PayOrderNoGenerator/PayoutNoGenerator 改 Redis RAtomicLong 当日原子序号 + DB MAX 一次性 CAS 播种 | 5 并发 gacha draw/start → **全 200，零 500**（原 1×200+4×500）✅ |
| T7.5 | 🔴 | admin | 三张 recon upsert mapper 误用 `@Select` 执行 INSERT → BindingException，整条对账/分成/季结线瘫痪 | `@Select`→`@Insert` ×3（SQL 不变） | rebuild → 200；gz_recon_monthly 落 gacha 行 ✅ |
| T7.4 | 🔴 | admin | 对账中心恒 ¥0（T7.5 下游），4% 分成不可见 | 随 T7.5 解决 | summary gacha gmvCent=500 / settleCent=500 / commissionCent=20(@4%) ✅ |
| T2.10 | 🟠 | 拼豆 | 取消带券未付单不解锁券 → 券永久卡 locked、用户白丢券 | cancel() 补 `couponServiceProvider.unlock(couponId)`（同 closePindou 超时路径） | 单测绿；unlock 幂等 WHERE status='locked' |
| T7.6 | 🟠 | admin | Excel 导出汇总 ¥0 vs 明细 ¥5 自相矛盾 | T7.5 修后 monthly 有值自动消除 | 导出汇总取 monthly 同源，monthly 已落库 |
| T8.4a | 🟠 | 安全 | 公开 sys_config 端点匿名读任意 key → 泄露分成率/默认密码 | GzConfigMpController.get 加 key 白名单（仅 banner/home 运营素材） | `sys.user.initPassword`/`gz.commission.rate.*` → 拒绝；`gz.home.banners` → 放行 ✅ |
| T8.4b | 🟠 | 安全 | mock 支付客户端 prod 漏配 env 时 fail-open（回调零验签资金洞） | ProdSecretGuard 增 `gz.pay.client-mode != real` prod 启动 fail-fast | 单测覆盖（prod-only） |
| T1-001 | 🟡 | 底座 | http.ts 续期失败分支丢弃挂起队列 → 并发 401 孤儿 Promise 永久挂死（拼豆「加载门店中…」死锁真因） | taskQueue 存 `{replay,fail}`，续期成败都对每个挂起请求确定性 settle | mp type-check + token 单测绿 |
| T1-002 | 🟡 | 底座 | silentWxRenew 打 `/applet/auth/*`(404) → 续期必败 → 清有效 token + 弹登录页 | 统一走 wxLoginGz(`/app/gz/common/auth/wx-login`)，不再二次 getInfo | token 单测绿 + 端点实测 200 |
| T2.5 | 🟡 | 拼豆 | 提交门槛只校验手机号、不校验微信号 → 用户反复撞 4014 toast | bean/recycle onSubmit 加 hasWechat gate；BizAuthSheet 微信号设必填 | mp type-check 绿 |
| T2.8 | 🟡 | 拼豆 | 未付单详情 VO 仍返有效 qrPayload（绕过遮罩可读） | buildQrPayload 仅 paid 才出码，未付返 null（doVerify NOT_PAID 守卫做最终闸） | 单测绿（fixtures 改 paid） |
| T4.5 | 🟡 | 资讯 | 取消定时后端有、admin UI 未接 | plus-ui 加 cancelSchedule API + 按钮 + handler + i18n | schedule→scheduled / cancel→draft+NULL ✅ |
| T5-001 | 🟡 | 个人中心 | 已过期但 cron 未翻态的券错留「未使用」tab | listMyCoupons 按 expireTime 实时分流 + VO effectiveStatus | unused=[12] 不含 13；expired=[13 as 'expired'] ✅ |
| T7.2 | 🟡 | admin | 回收价目重叠校验未排除停用规则 | assertNoOverlap 加 `enabled=ON`；toggleEnabled 启用前补重叠校验 | 单测绿 |
| T8.3 | 🟡 | 安全 | sys_menu 6020 perms 逗号脏值 | Flyway 迁移清空（叶子 F 6021/6030 承载真 perm） | 迁移已跑，perms=NULL ✅ |
| T3-001 | 🟡 | 回收 | 无照提交返 code 500 非契约声明的 4101 | BO 去 `@NotEmpty`，空判交 service 抛 4101 | 空 images → code 4101 ✅ |
| T3-002 | 🟡 | 回收 | 重试非法态返裸 500 无业务码 | GzRecycleErrorCode 增 4108 + 改双参 ServiceException | retry 非 failed → code 4108 ✅ |
| T1-003 | 🟡 | 底座 | tabbar/config.ts 注释陈旧（3 tab）+ useNavGuard 失效描述 | 注释更新为 4 tab + 懒登录 | — |
| T5-004 | polish | 个人中心 | 扭蛋订单列表 chip 恒朱红 | gachaStatusTone（已签收=green/已退款=muted） | mp type-check 绿 |
| 新-article_no | 🟡 | 资讯 | article_no 生成只查未删行，uk 含软删 → 当日「建→软删→再建」409 | mapper 加含软删的 MAX 查询 | 软删 5 条后建文 → ART-…-000006，无 409 ✅ |

## 待 Kevin / 待甲方（不阻塞 AI 闭环，列上线 checklist）

- **T5-002** 🟡：mp 服务协议 / 隐私政策为占位 toast（微信审核 + 个人信息合规硬性要求隐私政策可达）→ **待甲方文案**，接 H5/内置静态页
- **T5-003** 🟡：删默认地址后零默认态（doc/11 §2.2 明确允许零默认，纯体验增强）→ 排 V1.1
- **T3-003** polish：submit/verify 不校验 image fileId 是否真实存在于 gz_file_object（正常前端经 uploadFile 拿真 id，非客户端可触发）→ 存证类硬化，可上线后补
- **（误报已杀）** T6.2 扭蛋参考价 null 不展示 = works-as-intended（F7.5「null=不公示」+ 种子数据缺口，非代码 bug）

## 测试/回归汇总

- 后端单测：改动模块（gz-common / bean / recycle / coupon / news / ord）`mvn test` 全绿
- mp：`pnpm type-check` 0 错；`pnpm test` vitest **40 文件 / 374 测试全过**
- 真实 API/DB 回归：上表「回归证据」列逐条 curl/DB 实测通过
- H5 视觉走查：扭蛋机 / 资讯「谷子号外」公开页 C 风渲染正常；4-tab（扭蛋第3位）确认

## 未 commit

按项目纪律，等 Kevin 过目 + 决策项拍板后统一 commit（本会话改动未 commit）。
