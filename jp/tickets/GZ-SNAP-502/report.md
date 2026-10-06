# GZ-SNAP-502 实现报告

STATUS: DONE（AI自测通过；首版视觉仍待Kevin人验）

## 交付

- miniapp-jp `task/D12@d6bc61984535a2643be7813cf221f48689d6ba72`
- backend `task/D12@20a17b42a03f2dc8c51fe86b2cec63af20cedbd7`
- migrations: none；现有191条已验证。
- 无push、无合staging、无切分支、主miniapp零修改、真实煤炉请求0。

## 文件与实现

miniapp-jp：

- `src/pages/snap/detail.vue`：替换501路由壳，真实详情取数、服务端快照年龄、图轮播及图片失败兜底、中文标题及日文展开、人民币到手价/煤炉原价、三行价格抽屉、到付多退少不补、成色/运费承担/机翻描述及原文、准入三态、非在售及精确拒代购理由、报价过期禁买、下拉/显式刷新、固定BizButton立即购买。
- `src/api/gz-jp/snap-detail.ts`：公共投影契约及真实GET；确认路由`/pages/order/confirm?mode=snap&quoteId=<原ID>&externalId=<原商品>`，统一编码。
- `src/pages/snap/detail.logic.ts` / `.test.ts`：准入理由/过期守卫/真实快照时间/导航测试。
- `src/locale/snap.zh-CN.ts`：自包含locale扩展，不含禁用商业术语。
- `test/e2e/flows/snap-detail.mjs` / `test/e2e/run.mjs`：真实模拟器详情flow及注册。

后端：

- `GzJpSnapDetailVO.java`：新增可空只读`fetchedAt`，Unix epoch毫秒；保留此前18参数与14参数构造兼容，旧调用缺值为null。
- `GzJpSnapReadService.java`：取本次upsert实体的`fetchedAt`，按Asia/Shanghai将既有DATETIME转epoch，不拿前端请求时间伪装快照。
- `GzJpSnapDetailContractTest.java`：实际捕获持久化实体时间与返回时间一致、epoch接近当前时钟；保留公开投影不含私有定价项断言。

源导航来自`detail.vue`的definePage；生成且被忽略的`src/pages.json`已有`pages/snap/detail`和`enablePullDownRefresh=true`，无需强制提交生成文件。权威字段/impact/change-log由root同步，doc@5438a67。

## Accept与验证

#0 PASS：`cd code/main/miniapp-jp && node test/e2e/run.mjs snap-detail`，最终raw：`raw/502-e2e-r6.log`。

```text
manual：到付/コメント必須，按钮可用，完整人工协商及谈不成全额退款提示；三行和=4743分。
blocked：proxy_refuse，显示“卖家不接受代购”，按钮置灰且点击不导航。
blocked：専用，显示“该商品已被预定”，按钮置灰且点击不导航。
非在售：sold_out，即使gate=auto亦“已售出”且禁买。
auto：无准入提示，三行和=3834分，最后CTA保留原quoteId与externalId进入确认页。
每件MP标题/日元原价与真实HTTP详情同源；server fetchedAt与DB UNIX_TIMESTAMP差<1000ms。
[PASS] snap-detail
[run] 结束：1/1 flow 通过
```

样本由现有replay items m99000000001/3/4派生，唯一m502+当时时间ID，显式provenance synthetic；每件经Spring详情接口写真实快照，非前端mock，非手工造业务快照表。价格从公开goodsCent/fixedFeeCent/estShippingCent/totalCent投影读取；原quoteID从该页真实请求生成的专属Redis报价核对。截图来自模拟器真实渲染。

#1 PASS：ticket规定grep plus更严格将两个文件同时检查word `rate|markup|markupRatio|ratePer100Jpy`，两文件均无`汇率|加价`；exit0，`scheme-A-source-guard-pass`。

定向静态：`pnpm type-check` exit0；限定eslint（detail.vue/detail.logic.ts/detail.logic.test.ts/snap-detail.ts/snap.zh-CN.ts）exit0；`pnpm exec vitest run src/pages/snap/detail.logic.test.ts`：1个文件，4/4 pass。未跑全量MP或既已绿501flow。开发构建`pnpm exec uni build -p mp-weixin --mode development` exit0，raw `502-build-elevated.log`；最终prod build留root/D12QA。

后端定向：

```bash
JAVA_TOOL_OPTIONS=-javaagent:/Users/wkui/.m2/repository/org/mockito/mockito-core/5.17.0/mockito-core-5.17.0.jar \
  mvn -o test -DskipTests=false -Dtest=GzJpSnapDetailContractTest \
  -Dsurefire.failIfNoSpecifiedTests=false -pl ruoyi-modules/ruoyi-gz-jp -am
```

```text
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

raw `502-contract-final.log`与Surefire XML已永久归档。仅详情投影定向测试，未重测D10资金。共享脚本`bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp`完成clean install、启动与191迁移验证，raw `502-restart.log`。

## 临时配置与精确清理

经admin APIs临时设置定向测试pricing与FX（不是替用户设商业价）；开始先将sys_config.config_value原始HEX和update_by/update_time快照。finally先API恢复驱逐框架缓存，再原字节/审计列精确回写，admin配置读取与真实详情quoteErrorCode=4121分别读回两级配置路径。最终config_id=14040001、update_by=1、update_time=2026-10-06 16:50:24，原三项仍null、quoteTtlSec600。

仅删除本次新增FX ID（最终轮99030500026）、本次m502快照（active_order_item_id IS NULL）与对应quote/translation缓存；临时容器replay精确文件名删除并test不存在；仓内临时文件删除。现有商品、订单锁、mock用户昵称头像、配置审计原值均未覆盖。失败产品轮同样执行finally并成功精确清理。最终只读复核raw `final-restoration-readback.log`：pricing HEX+audit原样，业务租户FX0、本人m502快照0。

## 失败轮次及装置修正

- 初次后端定向测试Mockito自附加被沙箱拒绝（5执行、3错误），已有mockito-core javaagent后5/5绿，无引入依赖。
- 默认沙箱uni build文件监听EMFILE；宿主审批开发构建成功，无降级。
- 首产品轮tap抽屉后立即读到0行；补等待v-if异步渲染，保留3行及sum断言。
- 中间一次命令cwd错误未进入flow；两次产品轮在confirm后换样本时共享devtools reLaunch响应超时。阶段日志确认其余首件断言均成功；改navigateTo串行样本，将实际确认导航断言置flow最后，manual/blocked/sold/auto全部通过。没有移除按钮形态、金额、拒代购或原quoteID断言。
- 首次MP提交被subject-case hook拒绝；subject票号改小写、body保留GZ-SNAP-502，正常提交。
- 所有失败raw保留于raw/；无机械STOP、无降低产品判据。

## 人验及下游

`raw/snap-detail-{auto,manual}.png`、两张price抽屉截图、拒代购/预定/已售出截图已永久归档。AI功能绿不等于首版视觉已获人验；Kevin仍需按方案A看图。

503应读取原quoteId并维持原expiresAt语义，不因确认页重查商品而悄悄换价；详情CTA现在同时给externalId。公共原quote预览端点未提前实现，503按需补。确认页仍为既有一期实现，本ticket只证明导航参数正确。详情公开响应无后台内部QuoteSnapshot。

OUT_OF_TOUCHES: none（报告/raw为标准交付文档，root统一提交doc）。
代码仓最终miniapp-jp干净；后端只剩任务开始即存在的`ruoyi-admin/logs/sys-error.2026-10-01.log180801896327291.tmp`，未操作。
