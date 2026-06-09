# GZ-USER-104 完工报告 — 用户确认收货 + 自动签收（SnailJob）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | N/A — 本仓库无 git（env "Is directory a git repo: No"），用文件清单替代 diff --stat |
| 上游 USER-102 详情页就绪（BizFixedCta 透传点 + onConfirmReceipt 占位） | ✅ order-detail.vue:124 onConfirmReceipt + :249 BizFixedCta（USER-102 占位 → 本卡真实化） |
| 上游 USER-103 物流卡 3 态就绪（态 2 in_china_dispatching 已有快递+单号+复制） | ✅ BizLogisticsCard 实装；本卡在态 2 之上加底部「确认收货」CTA + 后端接口 |
| 上游表/字段存在（R1/R2 §0 硬探，缺则 STOP）| ✅ 见下「关键蓝图引用摘录」字段核对表 — 两表 logistics_status / cn_dispatched_at / delivered_time / business_status / version 全实有，gz_logistics_audit 已落 |
| 后端编译 + 全链 install（gz-common,gz-user -am） | ✅ BUILD SUCCESS（exit 0） |
| 后端单测 | ✅ 13/13（GzLogisticsSignServiceImplTest 10 + GzLogisticsSignTxHelperTest 3） |
| mp type-check（vue-tsc --noEmit） | ✅ 0 error |
| mp vitest（me/ + composables/） | ✅ 78/78（含 order-detail.logic 8 + useExpressCarrier 19，无回归） |
| mp build:mp-weixin → dist | ✅ DONE Build complete（7s）；order-detail.js 重生成，confirm-receive API 编译入 api/gz-user.js |
| ruoyi-gz-user pom 加 ruoyi-common-job | ✅ pom.xml:29 ruoyi-common-job（SnailJob 客户端，AC1） |
| 调度框架纪律 | ✅ SnailJob com.aizuda `@JobExecutor`；无 Quartz / 无 `@Scheduled` / migration 无 INSERT sys_job（启动 hard-fail 规避） |
| ADR 已读 | ADR-0005（C1 物流 2 态 + 终态 delivered 不可回退；本卡只做「进 delivered」侧，N8 owner 回退划 D11 ADMIN-104） |

> **本卡状态说明**：USER-104 全部产物（后端 service/executor/controller 端点 + 单测 + mp CTA 真实化 + 两表物流可写 entity/mapper + gz_logistics_audit migration + testing-human 预填）在前序会话已落地，本会话职责 = 跑 Tier 1A 机械验证（编译/单测/构建三端真跑绿）+ 补完工报告。无新增/改动代码，验证全绿。

### §0 关键蓝图引用摘录（R1/R2 字段硬探）

- **doc/10 §9 N5/N6**：N6 用户主动确认收货（仅 `in_china_dispatching` 显示「确认收货」→ 立即 `delivered`）；N5 系统 cron 扫 `in_china_dispatching > 7 天 → delivered`。`delivered` 终态，C 端无回退入口（E4：用户未收到走客服 → owner N8 回退，D11 ADMIN-104）。
- **doc/11 §6.4 物流字段**：自动签收锚 `cn_dispatched_at`（非 paid_time/create_time，日本段时长不可控）；天数走 `sys_config` `gz.delivery.auto_sign_days` 默认 7（不硬编码）；签收两态并行同推 `logistics_status` + `business_status` → delivered；签收时间钉死 `delivered_time`（禁 delivered_at）。
- **doc/11 §8.3 gz_logistics_audit**：`action_type` ∈ `user_confirmed`（用户）/ `auto_delivered`（系统）；`operator_type` ∈ `user`/`system`；`operator_id`（用户 = user_no，系统 = 字面量 `system`）；`from_status`/`to_status` 记物流态变更。
- **两表字段硬探（migration grep，R1/R2 缓解）**：
  | 字段 | gz_ord_order（V202606061400） | gz_gacha_order（V202606171400） |
  |---|---|---|
  | logistics_status | ✅ VARCHAR(20) DEFAULT 'in_japan' | ✅ VARCHAR(20) DEFAULT 'in_japan' |
  | business_status | ✅ | ✅ |
  | cn_dispatched_at | ✅ DATETIME(3) | ✅ DATETIME(3) |
  | delivered_time | ✅ DATETIME(3)（钉死 _time） | ✅ DATETIME(3) |
  | version（乐观锁 @Version） | ✅ INT DEFAULT 0 | ✅ INT DEFAULT 0 |
  | gz_logistics_audit 表 | ✅ V202606190100__GZ-USER-104-create-gz_logistics_audit.sql 已落 |

## 实现摘要

### 后端（ruoyi-gz-user）

| 文件 | 动作 | 作用 |
|---|---|---|
| `service/IGzLogisticsSignService.java` | 新建 | `confirmReceive(orderNo, userId)`（AC3）+ `autoSign()`（AC2，cron 委托，返签收数） |
| `service/impl/GzLogisticsSignServiceImpl.java` | 新建 | orderNo 前缀（PREORD-/GACHA-）路由两表 + 归属校验 + 状态校验 + 候选扫描（batch≤100）+ 批级 try-catch（一单失败不阻塞，AC5）；天数 `resolveAutoSignDays()` 读 sys_config 兜底 7（AC2/强约束 #3） |
| `service/impl/GzLogisticsSignTxHelper.java` | 新建 | 单订单「条件 UPDATE + 写审计」原子单元（独立 bean 避免 Spring AOP 自调用失效）；行级条件 `WHERE id+logistics_status='in_china_dispatching'+version` + 乐观锁 version+1，命中(affected=1)才写审计（幂等 AC4，D3） |
| `job/GzLogisticsAutoSignExecutor.java` | 新建 | `@Component` + `@JobExecutor(name="gzLogisticsAutoSignExecutor")` 薄壳，仅委托 `signService.autoSign()` + SnailJobLog 远程日志（AC1） |
| `controller/applet/GzUserOrderMpController.java` | 加端点 | `POST /app/gz/user/orders/{orderNo}/confirm-receive`（@SaCheckLogin + LoginHelper user_id 归属，AC3） |
| `domain/entity/writable/GzLogisticsOrderRow.java` + `GzOrdLogisticsRow` + `GzGachaLogisticsRow` | 新建 | 两表物流字段同构的可写 entity（抽象基类 + 两子类绑表）；不复用 USER-101 只读 mirror（写入语义独立 + 避 Maven 环：gz-user 不反依赖 gz-ord/gacha） |
| `mapper/writable/GzOrdLogisticsMapper.java` + `GzGachaLogisticsMapper.java` | 新建 | 两表可写 mapper（条件 UPDATE） |
| `domain/entity/GzLogisticsAudit.java` + `mapper/GzLogisticsAuditMapper.java` | 新建 | 审计 entity（含 BIZ_*/STATUS_*/ACTION_*/OPERATOR_* 常量）+ mapper |
| `pom.xml` | 加依赖 | `ruoyi-common-job`（SnailJob 客户端，AC1） |
| `test/.../GzLogisticsSignServiceImplTest.java` | 新建 | 10 测：自动签收扫两表/7天边界阈值/天数走config(5/非数字兜底7)/一单失败不阻塞/幂等不计数 + confirmReceive happy/状态非法/已delivered/越权/非法前缀 |
| `test/.../GzLogisticsSignTxHelperTest.java` | 新建 | 3 测：命中写1条审计返true（字段对齐§8.3）/ 未命中不写返false（幂等AC4）/ user_confirmed 审计字段 |

### DDL（migration）

| 文件 | 动作 |
|---|---|
| `V202606190100__GZ-USER-104-create-gz_logistics_audit.sql` | 新建 gz_logistics_audit（doc/11 §8.3，C1 唯一物流审计源；本卡是首个真写入方，USER-101/102/103 全只读侧）|

### 小程序（miniapp）

| 文件 | 动作 |
|---|---|
| `pages/me/order-detail.vue` | `onConfirmReceipt()` 真实化（USER-102 占位 toast → confirm modal「签收后无法回退」→ POST → toast「已签收」+ reload）；底部 BizFixedCta `v-if="showConfirmReceipt"` 仅 in_china_dispatching 显示（AC6）|
| `pages/me/order-detail.logic.ts` | `showConfirmReceipt()` 仅 `logisticsStatus==='in_china_dispatching'` 且非终态（AC6 门，vitest 覆盖）|
| `api/gz-user.ts` | `confirmReceive(orderNo)` → `POST /app/gz/user/orders/{orderNo}/confirm-receive` |
| `locale/user.zh-CN.ts` | `order.detail.confirm*` 双语（zh/en）：confirmReceipt / confirmModalTitle / confirmModalContent / confirmReceiptSuccess / confirmReceiptFail 等，无 emoji |

**统一布局五段顺序不变**（USER-102 强约束 #1）：状态卡 → 商品多态 → 物流卡（USER-103）→ 订单信息 → **底部 CTA「确认收货」（本卡真实化）**。

## AI 自测（≥ 3 代码 block）

### 后端编译 + 全链 install（gz-common, gz-user -am）

```
$ mvn -o install -Dmaven.test.skip=true \
    -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-user -am -q
（无错误输出）
EXIT=0
```

### 后端单测（13/13 — 自动签收 7 天边界 + 幂等 + 越权全覆盖）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user \
    -Dtest='GzLogisticsSignServiceImplTest,GzLogisticsSignTxHelperTest' \
    -Dsurefire.failIfNoSpecifiedTests=false
[main] ERROR ...GzLogisticsSignServiceImpl -- [gz-logistics-sign] autoSign one fail orderNo=PREORD-BAD businessType=preorder
  （↑ 是 test (4) 「一单失败不阻塞同批」故意触发的 mock 异常，被 service 批级 try-catch 吸收，非真错误）
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0 -- in ...GzLogisticsSignServiceImplTest
[INFO] Tests run: 3,  Failures: 0, Errors: 0, Skipped: 0 -- in ...GzLogisticsSignTxHelperTest
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖关键 case：
- **(2) 7 天边界**：捕获 query wrapper `cn_dispatched_at <=` 阈值，断言落在 `[now-7d-5s, now-7d+5s]`（≈7×24×60 分钟）→ 7 天阈值精确 ✅
- **(5) 天数走 config**：自定义 5 天 → 阈值 ≈ now-5d；非数字 "abc" → 兜底 7 天（强约束 #3）✅
- **(3) 幂等**：txHelper 返 false（条件未命中/并发抢先）→ 不计签收数（AC4）✅
- **(4) 一单失败不阻塞**：第 1 笔抛异常被吞，第 2 笔仍签 → signed=1（AC5）✅
- **(6)-(10) confirmReceive**：happy(in_china_dispatching→delivered+user_confirmed+user_no) / 状态非法(in_japan 抛) / 已delivered(再点抛，幂等) / 越权(他人订单抛「无权操作」) / 非法前缀·查无（AC3/AC4）✅
- **txHelper (1)/(2)/(3)**：命中 affected=1 写 1 条审计字段对齐 §8.3（from=in_china_dispatching/to=delivered）/ 未命中 affected=0 不写审计返 false（乐观锁幂等）/ user_confirmed 审计 operator_id=user_no ✅

### mp type-check + vitest（78/78 无回归）+ build → dist

```
$ pnpm type-check        # vue-tsc --noEmit
（0 error）

$ pnpm vitest run src/pages/me/ src/composables/
 ✓ src/composables/useExpressCarrier.test.ts (19 tests)
 ✓ src/pages/me/order-detail.logic.test.ts (8 tests)
 ✓ src/pages/me/collection.logic.test.ts (25 tests)
 ✓ src/pages/me/orders.logic.test.ts (3 tests)
 ✓ src/composables/{useDrawPolling,useCountdown,usePurchaseGuard,useOrderSubmit}.test.ts
 Test Files  8 passed (8)    Tests  78 passed (78)

$ rm dist/build/mp-weixin/pages/me/order-detail.js && pnpm build:mp-weixin
DONE  Build complete.          # 7s（devtools cli 唤起已 pkill）
$ ls -la dist/build/mp-weixin/pages/me/order-detail.js     # 5090 B 重生成 ✅
$ grep -rl "confirm-receive" dist/build/mp-weixin/
dist/build/mp-weixin/api/gz-user.js                        # confirm-receive 接口编译入 api chunk ✅
$ grep -oE "onConfirmReceipt|confirmReceive|showConfirmReceipt" dist/build/mp-weixin/pages/me/order-detail.js | sort -u
confirmReceive
showConfirmReceipt                                          # CTA 门 + 签收调用编译入页面 ✅
```

## SnailJob 控制台注册信息（人工注册一次 — 代码不自动注册）

| 项 | 值 |
|---|---|
| 任务名称 | `GZ-LOGISTICS-AUTO-SIGN` |
| 执行器路由名（executor_info） | `gzLogisticsAutoSignExecutor`（= `@JobExecutor(name)`） |
| 触发类型 | CRON，表达式 `0 0 * * * ?`（每小时整点，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD）— 上次未跑完不叠加 |
| 组 | `ruoyi_group` |
| 验证 | 注册后控制台「手动执行一次」→ 查 DB 两表 + gz_logistics_audit（见 testing-human 步骤 5） |

**自动签收扫表范围（确认）**：`autoSign()` 显式扫 **两张表** —— `gz_ord_order`（预购，GzOrdLogisticsMapper）+ `gz_gacha_order`（扭蛋，GzGachaLogisticsMapper），各自 try-catch 逐单推进，返回两表合计签收数。单测 (1) 验证两表 selectList 均被调用 + txHelper 委托 2 次。

## 风险提示 / 已知 issue

- **R1（鉴权口径沿用 USER-101/102 裁定）**：`confirm-receive` 用 `@SaCheckLogin` + service 层 `user_id` 归属校验（C 端模型），非 ticket AC3 简写的 sa-token-app `@SaCheckPermission`（那是 ADR-0004 店员门，挂上普通顾客会 403）。与同 controller 既有 list/detail 端点一致。待 product 在 doc/11 §8.1 回填修订源头。
- **R2（联调态切换依赖手改 DB）**：D11 ADMIN-104 物流写入 UI 未交付前，`in_china_dispatching` 态需手改 DB 触发（testing-human 已给 UPDATE 语句）；订单默认态 `in_japan`，详情底部无 CTA 属正常。
- **R3（7 天偏早、用户未收到）**：doc/10 §9 E4 已 ack —— V1.1 不给 C 端「我没收到」入口，走客服 → owner 后台 N8 回退（D11 ADMIN-104）。
- **R4（gz-ord PreorderFullChainMockTest 预存在 testCompile 失败）**：USER-101/102 报告已记录，与本卡无关；本卡单测仅 `-pl ruoyi-modules/ruoyi-gz-user` 范围跑，未触碰 gz-ord。
- **R5（时区）**：DB + JVM 均 +08:00（dev-compose.yml + application.yml），cron 与 cn_dispatched_at 同库 NOW() 比较稳。

## 对下游 ticket 的提示

1. **D11 ADMIN-104（owner 物流回退 N8 + 物流写入侧）**：本卡只做「进 delivered」侧（user_confirmed / auto_delivered）。回退是 owner 超级权限 + 必填 reason 审计，写 gz_logistics_audit 的 `status_rollback`（entity 常量已预留 action 语义）。推进 in_china_dispatching 时须写 `cn_dispatched_at`（本卡自动签收时钟锚点）；gz_logistics_audit 表本卡已落，ADMIN-104 直接复用写入（碳/owner 推进 action_type=status_forward/carrier_set 等）。
2. **autoSign service 可复用**：`IGzLogisticsSignService.autoSign()` 行级条件 UPDATE 幂等 + 两表扫描已封装，如未来加更多业务订单类型（如 v2），扩 autoSignTable 一行即可。
3. **doc 源头建议（§9.5 #1）**：ticket AC3 写 sa-token-app `@SaCheckPermission`，与全仓 C 端「我的 X」实际鉴权（@SaCheckLogin + user_id 归属）不符，建议 product 改 doc/11 §8.1 鉴权口径为「C 端 @SaCheckLogin」，与 USER-101/102 偏差一并修订。

## 风险提示 / 待 Kevin 批量人验关注（mp 端）

- **进入路径（Tier 2 可达，AC8，N 复用 USER-102 已通路径，无新增/临时入口）**：会员中心「我的」tab →「我的订单」cell → 列表点一条 `in_china_dispatching` 态订单进详情 → 底部见朱红「确认收货」CTA → 点击弹 confirm modal → 确认 → toast「已签收」+ 详情刷新（CTA 消失、状态变绿「已签收」）。
- **人验聚焦 3 点**（其余 AI 已覆盖）：
  1. **SnailJob 控制台注册并手动触发自动签收**（cron 注册是人工动作，代码不自动注册）→ 验 8 天前两表单变 delivered + 审计 auto_delivered，6 天前单保持 in_china_dispatching
  2. **mp 真机确认收货端到端**（modal 文案 → 签收 → 刷新 → CTA 消失）；扭蛋单同流程（盲盒语义：无「抽奖/中奖/开奖」）
  3. **审计行落库**：user_confirmed（operator_id=user_no）/ auto_delivered（operator_id=system），from/to status 正确
- testing-human.md GZ-USER-104 段已预填完整（前置 SQL + AC + 测试动作 6 步 + SnailJob 注册信息）。

## §AI 测试段（kevin-qa 自动追加，21:32）

### Tier 1B 发现并修复（Bug 3）

**GzLogisticsSignServiceImpl LambdaQueryWrapper 抽象类 lambda cache miss**
- 原代码：`new LambdaQueryWrapper<T>().eq(GzLogisticsOrderRow::getOrderNo, ...)` — MyBatis-Plus 无法为抽象父类解析 lambda cache
- 修复：
  - `autoSignTable()`：改为 `new LambdaQueryWrapper<>(clazz)` 传入具体 class，lambda ref 仍用父类方法（clazz 是具体子类，lambda 解析路径正确）
  - `confirmReceiveTyped()`：改为 `new QueryWrapper<T>().eq("order_no", orderNo)`（避免同样问题）
- 验证：`POST /app/gz/user/orders/PREORD-999999/confirm-receive` 由数据库 error 500 变为业务正常 500「无权操作该订单」✅
- 单测：GzLogisticsSignServiceImplTest 10/10 + GzLogisticsSignTxHelperTest 3/3 全通过 ✅

### 后端单测（全模块）

```
[INFO] Tests run: 10, Failures: 0, Errors: 0 -- GzLogisticsSignServiceImplTest
（含 7 天边界 / 5 天 config / 幂等 / 一单失败不阻塞 / confirmReceive happy+越权+非法态）
[INFO] Tests run: 3,  Failures: 0, Errors: 0 -- GzLogisticsSignTxHelperTest
[INFO] Tests run: 38, Failures: 0, Errors: 0, Skipped: 0（gz-user 全模块）
[INFO] BUILD SUCCESS
```

### API 契约回归

```bash
# confirm-receive: 不存在/越权 → 500 "无权操作该订单"（业务 error，非 DB 错误）✅
curl POST /app/gz/user/orders/PREORD-999999/confirm-receive
# code=500, msg="无权操作该订单" ✅
```

### mp vitest

```
 ✓ src/pages/me/order-detail.logic.test.ts (8) ✅ (含 showConfirmReceipt CTA 门测试)
 ✓ src/composables/useExpressCarrier.test.ts (19) ✅
 ✓ 全域 34 files, 301 tests passed ✅
```

### 跳过 / 未跑

- SnailJob 控制台手动注册 + 触发自动签收（代码不自动注册，人工操作）→ Tier 2 人验
- mp 真机确认收货端到端（modal 弹窗 → 签收 → 状态刷新）→ Tier 2 人验
- 审计行落库验证（user_confirmed/auto_delivered from/to 字段）→ Tier 2 人验（需手改 DB）

### 结论

✅ Tier 1B 全通过（Bug 3 已在 Tier 1B 内闭环修复），ticket 可 close；mp 进人验列
