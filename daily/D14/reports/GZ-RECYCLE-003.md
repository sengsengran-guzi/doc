# GZ-RECYCLE-003 完工报告 — 店员核对 + 拍照 + 触发反向打款 + admin 管理

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（工作区非 git 仓库，env 已确认 "Is directory a git repo: No"） |
| 上游 RECYCLE-002 merge | ✅ entity/service/mapper/mp controller/VO/BO/ApptNoGenerator/ErrorCode + menu 13002 已 seed 授 owner |
| 上游 PAY-105 merge | ✅ IGzPayPayoutService.initiatePayout/scanAndQuery + PayoutStatus + mapper(含 retryFailedToCreated) + MockWechatPayClient(setQueryTransferState/setTransferAcceptFail) |
| 关键类/表存在 | ✅ gz_recycle_appointment（全字段含 verify_image_ids/final_amount_cent/verified_by/verify_time/out_payout_no/version）/ gz_pay_payout_transaction |
| 编译通过 | ✅ gz-recycle + gz-common clean install（exit 0） |
| ADR 已读 | ADR-0004（openid 绑 sys_user + @SaCheckPermission + 停用即踢）/ ADR-0006（out_payout_no+batch_id 双重幂等 + 主动查单优先 + mock） |
| 权威蓝图引用 | doc/10 §13.N6-N12 + §14 / doc/11 §12.2+§4.8+§4.6 已 Read 并落地 |

### 权威蓝图关键约束摘录（落地点）
- **doc/10 §13.N8/N9**：店员核对 → 拍照 verify_image_ids + 微调 final_amount + 确认 → submitted→confirmed_onsite（留痕 verified_by/verify_time）→ 触发打款 confirmed_onsite→paying。✅ `verifyAndPayout` 落地。
- **doc/10 §13.N10**：paid 时发 `CouponIssuanceEvent`（event_type='recycle_paid'，V1 仅留位）。✅ `syncOne` 内留 `TODO(GZ-COUPON recycle-issuance)` 注释钩子，不强制发券。
- **doc/11 §12.2**：触发打款用 out_payout_no + batch_id 双重幂等（PAY-105 内建）+ version 乐观锁兜底防并发。✅ markConfirmedOnsite/markPaying 全含 `version=#{version}` 守卫。
- **doc/11 §4.6 补注 / ADR-0006**：回收反向出账 business_type='recycle'，独立核算不计 GMV、不参与 4% 分成、不进对账中心。✅ 代码注释 + 本报告 AC6 写明。

## 实现摘要

### 改动文件（按层）

**后端 gz-common（扩 PAY-105 暴露重试/查单，不破坏既有）**
- `pay/service/IGzPayPayoutService.java` — 加 `retryPayout(businessOrderNo, remark)` + `queryAndAdvanceByBusinessOrderNo`
- `pay/service/impl/GzPayPayoutServiceImpl.java` — 实现两方法（retry = failed→created→重新受理；queryAdvance = 单条主动查单）
- `pay/controller/GzPayPayoutController.java` — 加 `POST {businessOrderNo}/retry` + `/query`（@SaCheckPermission gz:pay:payout:retry）
- `enums/GzFileUsageType.java` — 加 `RECYCLE_VERIFY_IMAGE("recycle_verify_image")`

**后端 gz-recycle（核对 + 触发打款 + paid 回写 + no_show + admin）**
- `mapper/GzRecycleAppointmentMapper.java` — 加 7 个手写原子 UPDATE/SELECT（markConfirmedOnsite/markPaying/markPaid/markPayoutFailed/markRetryPaying/markNoShow + selectPayingIds/selectExpiredSubmittedIds），全 version+前态守卫
- `service/IGzRecycleAppointmentService.java` + `impl/...ServiceImpl.java` — getAdminDetail/verifyAndPayout/retryPayout/syncPayoutResult/selectAdminPage/markExpiredNoShow
- `domain/bo/GzRecycleVerifyBo.java` + `GzRecycleAppointmentQueryBo.java` + `domain/vo/GzRecycleAppointmentAdminVO.java`（两套照片 + 留痕 + 快照）
- `exception/GzRecycleErrorCode.java` — +4104/4105/4106
- `controller/applet/GzRecycleStaffMpController.java`（mp `/app/gz/recycle/staff/{appointment/{id},verify}`）+ `controller/GzRecycleAppointmentController.java`（admin `/system/gz/recycle/appointment/{list,{id},{id}/retry-payout}`）
- `job/GzRecyclePayoutSyncJob.java` + `GzRecycleNoShowJob.java`（SnailJob 薄壳）
- `pom.xml` — 加 ruoyi-common-job

**DDL（时间戳 > V202606220110）**
- `V202606230100__GZ-RECYCLE-003-menu-perm.sql` — staff(101) 授 gz:recycle:appointment:list/verify（13002/13020/13021）+ 反向打款重试权限 5113（gz:pay:payout:retry）授 owner
- `V202606230101__GZ-RECYCLE-003-seed-recycle-status-dict.sql` — gz_recycle_status 字典（9256-9263，doc/11 附录 A.20，7 态）

**admin（plus-ui）**
- `views/gz-recycle/appointment/index.vue`（BizTable 列表筛 store/date/status + drawer 两套照片预览 + 估价/实付 + 核对留痕 + payout_failed 重试）+ `api/gz-recycle/appointment.ts`
- `views/gz-pay/payout/index.vue` 扩 failed→重试 / processing→主动查单按钮 + `api/gz-pay/payout.ts` 加 retryPayout/queryPayoutOnce
- `lang/zh_CN.ts` + `en_US.ts` — gzRecycleAppointment + gzPayPayout 扩 key

**mp（uni-app）**
- `pages/recycle/staff-verify.vue` + `staff-verify.logic.ts` + `staff-verify.logic.test.ts`
- `api/gz-recycle.ts` 扩 staff 接口（getStaffRecycleAppointment/staffVerifyRecycle + VO/BO）；`api/gz-staff.ts` 加 PERM_RECYCLE_VERIFY；`api/gz-file.ts` 加 RECYCLE_VERIFY_IMAGE
- `pages/me/index.vue` 门店管理区加「回收核对」入口（hasPerm 门控）+ `locale/user.zh-CN.ts` staffEntryRecycleVerify + `locale/recycle.zh-CN.ts` 店员核对页文案
- `pages.json` 注册 pages/recycle/staff-verify

## AI 自测

### 编译（gz-recycle + gz-common install）
```
$ mvn -q install -DskipTests -pl ruoyi-modules/ruoyi-gz-recycle,ruoyi-modules/ruoyi-gz-common -am
exit=0   (clean，无 warning/error)
```

### 单测（触发打款幂等 + 状态机，AC9 ≥ 80%）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run: 10, ... -- in GzRecycleVerifyPayoutTest        ← RECYCLE-003 新增
[INFO] Tests run: 8,  ... -- in GzRecyclePriceRuleOverlapTest
[INFO] Tests run: 7,  ... -- in GzRecyclePriceRuleEstimateTest
[INFO] Tests run: 8,  ... -- in GzRecycleAppointmentServiceImplTest
[INFO] Tests run: 33, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

# PAY-105 回归（改了其 service/controller）：
$ mvn test -pl ruoyi-modules/ruoyi-gz-common -Dtest=GzPayPayoutServiceImplTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0  ← 未破坏
```

GzRecycleVerifyPayoutTest 10 例覆盖（全 mock，mapper/payoutService @Mock 驱动状态机）：
- 核对确认 → confirmed_onsite + 留痕（verify_image_ids 逗号分隔 "11,12" + final_amount + verified_by 进 markConfirmedOnsite）+ 触发打款 → **paying 全链路第一步**
- **微调留痕**：finalAmount 4200 ≠ estimated 5000 时，markConfirmedOnsite 收到 4200（非估价）
- **重复核对幂等**：version 漂移 markConfirmedOnsite affected=0 → NOT_VERIFIABLE 抛错 + **never initiatePayout / never markPaying**（不二次触发打款）
- 非 submitted 单核对 → NOT_VERIFIABLE 拒绝
- **paid 回写钩子**：payout success → markPaid 被调（paying→paid）
- **failed→payout_failed**：payout failed → markPayoutFailed 被调（留人工）
- payout 仍 processing → 保持 paying 不回写（等下轮）
- **failed 重试**：payout_failed → retryPayout(RCY-...) + markRetryPaying → paying
- 非 payout_failed 重试 → 拒绝（never retryPayout）
- **no_show 兜底**：过期 submitted → markNoShow ×2

### mp vitest（店员核对纯逻辑 + 全量回归）
```
$ pnpm test -- --run src/pages/recycle/staff-verify.logic.test.ts
 Test Files  40 passed (40)
      Tests  374 passed (374)   ← 含 staff-verify.logic 新增 30 例（元↔分换算 / 金额合法性 / 核对门控）
```
（修了一处 bug：`Number('') === 0` 导致空输入误判合法 → yuanStrToCent 先排除空串再 cast。）

### admin build（plus-ui）
```
$ pnpm build:prod
✓ built（全绿，TS + i18n 通过，含 gz-recycle/appointment + payout 扩展）
dist/index.html.gz 111.32kb -> 48.39kb
```

### mp build（mp-weixin，dist 生成即成功）
```
$ pnpm build:mp-weixin
🚀 正在打开微信小程序开发者工具...   ← 编译完成（devtools cli 假挂起，已 pkill）
$ grep pages/recycle/staff-verify dist/build/mp-weixin/app.json  → 命中
$ ls dist/build/mp-weixin/pages/recycle/ → staff-verify.{js,json,wxml,wxss,logic.js} 全生成
```

## 全链路状态机（mock 闭环，AC2）

`submitted → confirmed_onsite → paying → paid` 验证机制：
1. 店员 `verifyAndPayout`：markConfirmedOnsite（留痕）→ payoutService.initiatePayout（mock 受理 ACCEPTED→processing）→ markPaying（回填 out_payout_no）。
2. PAY-105 `gzPayoutQueryTask` 查单：mock setQueryTransferState=SUCCESS → payout 单 processing→success。
3. **回收单 paying→paid 回写机制 = 自建 `GzRecyclePayoutSyncJob`（SnailJob）**：扫 paying 单 → 按 out_payout_no 查 payout 单终态 → success 回写 paid / failed 回写 payout_failed。与 PAY-105 查单解耦（PAY-105 只推进 payout 单本身），最终一致。单测 `sync_payoutSuccess_writesBackPaid` 直接 mock payout 单注入 success 验证闭环。
4. failed 分支：mock setTransferAcceptFail 或 setQueryTransferState=FAIL → payout failed → 回写 payout_failed → owner admin 重试（retryPayout → PAY-105 retryFailedToCreated→重新受理 → markRetryPaying→paying）。

## SnailJob 控制台注册（禁止 Flyway INSERT sys_job，memory scheduler-is-snailjob）

| 任务名 | 执行器路由（@JobExecutor name）| CRON | 说明 |
|---|---|---|---|
| GZ-RECYCLE-PAYOUT-SYNC | `gzRecyclePayoutSyncTask` | `0 1/2 * * * ?`（每 2 分钟，错峰 PAY-105 查单 1 分钟）| paying→paid 回写（按 out_payout_no 关联 payout 终态收敛）|
| GZ-RECYCLE-NO-SHOW | `gzRecycleNoShowTask` | `0 30 3 * * ?`（每日凌晨 03:30）| 扫过期 submitted → no_show（店员标记优先，本任务兜底）|

阻塞策略：丢弃（DISCARD）；组：ruoyi_group；容器时区 Asia/Shanghai。

## ADR-0004 + ADR-0006 已读摘录

- **ADR-0004**：mp 店员端复用 ruoyi RBAC —— 核对端点用标准 `@SaCheckPermission("gz:recycle:appointment:verify")`（与 admin 同一权限 key、同一真源），零新增鉴权基建。本卡仅加一行注解 + DDL 授 staff(101)；停用/解绑 sys_user 即时踢 token（底座已支持）；同租户 1001 由 ruoyi 拦截器兜底。verifiedBy 取绑定 sys_user nick_name（IMpStaffPermissionService.resolveByGzUserId）。
- **ADR-0006**：反向打款 out_payout_no + batch_id 双重幂等（PAY-105 内建，本卡不自防重）；主动查单优先（GzRecyclePayoutSyncJob 查单驱动 paid，回调为辅）；mock 降级（gz.pay.client.mode=mock 全链路可测）；独立 PayoutStatus 枚举不复用收款 PayStatus。

## 回收单 status=paid 回写机制说明（任务卡明确要求）

选 **自建 SnailJob（GzRecyclePayoutSyncJob）+ service.syncPayoutResult() 钩子**，不在 PAY-105 scanAndQuery 内耦合回写。理由：
1. **职责单一**：PAY-105 scanAndQuery 只关心 payout 单状态机（不应知道回收业务）；回收单回写是回收域职责。
2. **解耦可测**：syncPayoutResult 在 gz-recycle service，单测直接 mock payout 单注入 success/failed 验证 paying→paid/payout_failed，不依赖 PAY-105。
3. **最终一致可接受**：商家转账到账本有延迟，PAY-105 查单先把 payout 推到 success，回收 sync 下一轮（≤2min）回写 paid。

## 风险提示 / 已知 issue

- **真实上线 gate（ADR-0006 pending）**：微信「商家转账到零钱」权限需甲方商户平台单独申请（非默认开通），transferbatch SDK 待 Kevin 批准。当前全 mock（gz.pay.client.mode=mock），代码就绪不被阻塞，不影响 D14 close。
- **CouponIssuanceEvent（recycle_paid）**：doc/10 §13.N10 要求 paid 发券钩子，V1 仅留位（syncOne 内 TODO 注释），发券策略待优惠券域接入，不强制实现。
- **mp 店员调出预约用 id**：当前 staff-verify 页店员手输 appointment id 调出（支持 ?id= 带入）；未做扫码（回收预约无核销码二维码，与拼豆不同）。如需扫码可后续接 RCY- 号搜索，本卡按 id 调出已满足核对闭环。
- **待 Kevin 批量人验关注（mp 端）**：① 店员登 mp → 我的（店员端）门店管理 → 回收核对 入口可达；② 调出预约 → 看用户实物照 → 拍照存证 → 微调金额 → 确认 → 提示「已触发打款」+ 返回；③ 微信 chooseImage 拍照 + COS 上传真机；④ 核对后 admin 列表状态变 paying / 详情见两套照片 + verified_by/verify_time 留痕。

## 对下游 ticket 的提示

- **SYS-010 不依赖本卡**（无交集）。
- **D15 对账（ADMIN-105）**：回收反向出账 `gz_pay_payout_transaction.business_type='recycle'` **独立核算 —— 不计 GMV、不参与 4% 分成、不进对账中心 §9 GMV 口径**（合同 §4.1 / ADR-0006 / doc/11 §4.6 补注）。对账中心需把 payout 流水单列，与拼豆/扭蛋正向流水隔离不交叉冲抵。
- **优惠券域**：本卡在 paid 回写处留了 `recycle_paid` 发券钩子位（syncOne 内 TODO）；优惠券域落地回收返券时在此消费。
- **Tier 2 临时入口**：本卡入口（回收核对）走业务主线真入口（me/index.vue 门店管理区 hasPerm 门控），**无临时入口需清理**。

## §AI 测试段（kevin-qa 完工后追加）

（占位，待 Tier 1B kevin-qa 追写）
