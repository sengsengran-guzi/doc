# GZ-PAY-105 — 反向打款链路（商家转账到零钱 V3）+ mock + payout 表 + 查单 SnailJob

**优先级**: P1
**复杂度**: L
**关联 PRD**: doc/02-prd.md 回收域 / 支付域
**关联拆解**: doc/02-需求拆解.md GZ-PAY-105
**关联 mockup**: N/A（admin 走 ruoyi 默认，不引 mockup）
**关联 ADR**: **doc/_adr/0006-reverse-payout-wechat-transfer.md（必读全文）** + 承接 ADR-0003（mock 降级范式）
**依赖**: GZ-PAY-001（`IWechatPayClient` 抽象 + Mock/V3 双实现，已就绪）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §14（反向打款时序）
- **字段表**：doc/11-字段权威表.md §4.8（payout 单）+ §4.9（回调流水）+ §4.10（待澄清 F4.6/F4.7）+ 附录 A.16（PayoutStatus 枚举）
- **ADR**：doc/_adr/0006 全文（mock 双实现 / 主动查单优先 / out_payout_no+batch_id 双幂等 / business_order_no 1:1 / transferbatch SDK 待批准）
- **UI 参考**：N/A（admin 走 ruoyi 默认）

## What

扩 `IWechatPayClient` 反向打款能力（mock 跑通，real 留 hook）；建 payout 两表 + 独立 `PayoutStatus` 枚举；查单 SnailJob 轮询 `processing→success/failed`；双重幂等防重复转账。本卡仅建链路 + mock 闭环，回收业务触发在 D14 RECYCLE-003。

## AC（验收标准）

- [ ] **AC1 接口扩展**：`IWechatPayClient` 加 `transferToUserWallet(TransferRequest)` + `queryTransferByOutNo(String outPayoutNo)`（**不新建平行 client**，在现有接口扩，ADR-0006 §1）。`TransferRequest` 含 `outPayoutNo`(PAYOUT-)/`receiverOpenid`/`amountCent`/`transferRemark`/`businessOrderNo`。
- [ ] **AC2 双实现**：`MockWechatPayClient` 扩 mock（`transferToUserWallet` 返占位 payout_id+batch_id 置 `processing`；`queryTransferByOutNo` 首查 `processing`、再查/模拟成功按钮 → `success`；可单测 created→processing→success + **failed 分支**）。`WechatPayV3ClientImpl` real 接 V3 `/v3/transfer/batches` 部分**留 hook + 注释 `// 待 transferbatch SDK 批准（ADR-0006 / 铁律 8）`，不私引依赖**。复用 `gz.pay.client.mode` 开关（不另起）。
- [ ] **AC3 payout 两表**：`gz_pay_payout_transaction`（`out_payout_no` PAYOUT-/`business_type='recycle'`/`business_order_no`(=RCY-，D14 回填)/`receiver_openid`/`amount_cent`/`status` 独立 PayoutStatus/`payout_id`+`batch_id` UNIQUE/`fail_reason`/`version`/审计列）+ `gz_pay_payout_callback_log`（仿 `gz_pay_callback_log`，原始 body + 解析 + 幂等标记）。
- [ ] **AC4 独立 PayoutStatus（附录 A.16）**：`created → processing → success`；旁路 `failed`（可重试，重置 `created`）/ `cancelled`。**不复用** `gz_pay_transaction.status`。
- [ ] **AC5 查单 SnailJob**：`@Component + @JobExecutor`(name=`gzPayoutQueryTask`) 薄壳 + 可单测 service，扫 `processing` 态 → `queryTransferByOutNo` → 推进 `success`/`failed`（主动查单优先，ADR-0006 §3）。`gz_pay_payout_callback_log` 仅存档备查。**禁止 Flyway INSERT sys_job**；任务名 + CRON 写 reports。
- [ ] **AC6 双重幂等（ADR-0006 §5）**：`out_payout_no` UNIQUE + `payout_id`/`batch_id` UNIQUE WHERE NOT NULL + 一笔 `business_order_no` 与 payout 单 **1:1**（建单前查已有非 failed/cancelled 单 → 拒重复发起）+ `version` 乐观锁。**reports 必含重复 `out_payout_no` 触发不二次转账 raw output**。
- [ ] **AC7 admin 反向打款单管理页**：plus-ui `views/gz-pay/payout/index.vue`（ruoyi/Element Plus 默认，BizTable，**不引 mockup/不调样式**），menu 挂 **5110-5119**（5100 段空）。列表 + 详情 + 状态 dict-tag。
- [ ] **AC8 单测 ≥ 80%**：mock 状态机（created→processing→success + failed→重试）+ 幂等（重复 out_payout_no / 重复 business_order_no 拒绝）+ 1:1 约束。
- [ ] **AC9 SDK 批准状态留痕**：§0 自检 `mvn dependency:tree | grep wechatpay` 确认 transferbatch service 是否在当前版本可用；reports 记录「未引入新 Maven 坐标 / 走 mock / real 留 hook 待批准」。

## Tech（端 + 范围）

- **后端领地**（独占 gz-common pay 域）：`ruoyi-modules/ruoyi-gz-common/src/.../pay/`
  - `service/internal/IWechatPayClient.java`（扩 2 方法 + TransferRequest/TransferResult/TransferQueryResult record）
  - `MockWechatPayClient.java` + `WechatPayV3ClientImpl.java`（双实现）
  - 新增 `payout` 子域：entity/bo/vo/mapper/service(+impl)/job（`GzPayoutQueryJob` 薄壳）/controller(admin)
  - `ruoyi-common-job` 依赖 gz-common **已有**（无需补）。
- **Admin**：`code/main/plus-ui/src/views/gz-pay/payout/index.vue` + `api/gz-pay/payout.ts`（id 全 string）+ i18n block `gzPayPayout`。
- **DDL**：时间戳 `V202606210100`+（payout 表）/ `V202606210110`+（5110 menu）/ `V202606210120`+（dict `gz_payout_status`）。**dict_id 用 9250-9255 / dict_code 9251-9256**（避开 COUPON 已用 9220-9236）。migration 用 raw SQL 验证不污染 flyway_schema_history。

## 备注（并行批次纪律 ⭐）

- **本卡与 COUPON-002 / RECYCLE-001 第一波并行**。你独占 gz-common pay 域 + admin gz-pay；不碰 gz-bean/gz-coupon/gz-recycle。
- **编译/单测**：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common`（你改 gz-common 自身，可不 -am）。**不要 `mvn install`**（留主线程统一）。
- **plus-ui i18n 单文件 append**（`src/lang/zh_CN.ts`+`en_US.ts`）：RECYCLE-001 并行也 append。**append `gzPayPayout` block 前重读文件实际尾部**，Edit 锚定你新增 block 紧邻的稳定上文；若 Edit 失配 = 并行已改，重读再 append，**不覆盖他人 block**。
- **transferbatch SDK 未见 Kevin 批准信息 → 走 mock**（铁律 #8）：real 部分留 hook 注释，**不私引 `com.wechat.pay.java...transferbatch`**。
- **不要 spawn kevin-qa**（子不能 spawn 孙；Tier 1B 主线程统一派）。写完 reports（含 §AI 测试段占位 + SnailJob 注册信息 + SDK 批准状态）即返回。

---

## §revision（Kevin 批量人验后填，初始空）
