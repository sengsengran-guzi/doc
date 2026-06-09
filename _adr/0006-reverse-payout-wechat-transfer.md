# ADR-0006 回收反向打款（微信「商家转账到零钱」V3）的能力扩展与 mock 降级

- 日期：2026-06-08
- 状态：Accepted
- 决策人：Kevin（kevin-product 评估，kevin-coder 落地）
- 关联 ticket：GZ-PAY-105（反向打款链路）/ GZ-RECYCLE-003（店员核对触发打款）；承接 ADR-0003（mock 降级范式）
- 落地批次：D14（PAY-105 mock 跑通）

---

## Context

V1.2 新增「回收预约」业务线：用户把闲置谷子卖给店家，店员到店核对实物后，**店家要把钱打给用户**（钱从商户账户流出到用户微信零钱）。这是一笔**反向资金流**——和 V1.0/V1.2 拼豆收款方向相反。

现状能力为零：

- `IWechatPayClient`（ADR-0003 抽象）目前**只有收款能力**（`createJsapiOrder` / `queryByOutTradeNo` / 验签解密回调）。
- 微信支付 V3 的「商家转账到零钱」(`/v3/transfer/batches`) 是**独立于收款的另一套接口 + 另一套商户权限**，不是收款 SDK 的子集，收款通了不代表转账能用。

两个硬现实：

1. **商户权限**：「商家转账到零钱」需商户在微信支付商户平台**单独申请开通**（默认不开），且对商户经营资质 / 历史交易有门槛。甲方商户号（ADR-0003 尚在「收款下证 + 主体核对」尾项）此能力**远未到位**。
2. **回调模型不同**：收款靠微信主动回调驱动 paid；商家转账的回调到达性弱、且部分场景无回调，**微信官方建议主动查单为准**。直接照搬收款的「等回调」会导致打款状态长期悬空。

GZ-PAY-105 是 V1.2 回收业务线的必交项，不能因商户权限未到位阻塞整个回收域代码落地——沿用 ADR-0003 的「代码先就绪、外部资质 gate 在上线」范式。

## Decision

### 1. IWechatPayClient 扩两个反向打款方法（承接 ADR-0003 抽象）

在现有 `IWechatPayClient` 接口上扩展，**不新建平行 client**：

```
TransferResult transferToUserWallet(TransferRequest req);   // 发起转账（幂等键 out_payout_no）
TransferQueryResult queryTransferByOutNo(String outPayoutNo); // 按商户单号查单（主动查单为准）
```

- `req` 必含：`outPayoutNo`（商户侧幂等单号 PAYOUT-）/ `receiverOpenid`（收款用户 openid）/ `amountCent` / `transferRemark`（转账备注，用户零钱可见）/ `businessOrderNo`（=回收预约号，溯源）。
- 两套实现，沿用 ADR-0003 的 `@ConditionalOnProperty` profile 切换（**复用同一个 `gz.pay.client.mode` 开关**，不另起开关）：
  - `MockWechatPayClient`：扩 mock 实现——`transferToUserWallet` 返回固定占位 `payout_id` + `batch_id`，状态置 `processing`；`queryTransferByOutNo` 首次查返回 `processing`、再查（或 admin 测试工具页「模拟转账成功」按钮）返回 `success`。dev 默认 + 单测永远走它，CI 不依赖真实商户权限。
  - `WechatPayV3ClientImpl`：real 实现接 V3 `/v3/transfer/batches` + `/v3/transfer/batches/out-batch-no/{out_batch_no}` 查单。

### 2. 新依赖：transferbatch SDK —— **待 Kevin 批准（铁律 #8）**

官方 `wechatpay-java` SDK 的转账能力在 `com.wechat.pay.java.service.transferbatch` 包，是 ADR-0003 已引入的 `wechatpay-java:0.2.17` 的**同一 artifact 内子包**——理论上**无新增 Maven 坐标**（不是新 jar）。但：

- **若现版本不含 transferbatch service** → 需升 `wechatpay-java` 版本（动版本号 = 变更依赖，过 §0 `mvn dependency:tree` 核对冲突，**报 Kevin 批**）。
- **若含** → 仅 import 新子包，无依赖变更，但仍按铁律 #8 在 GZ-PAY-105 §0 自检里**显式记录「未引入新 Maven 坐标」**留痕。

> 实施 gate：GZ-PAY-105 §0 自检先 `mvn dependency:tree | grep wechatpay` 确认 transferbatch service 类是否在当前版本可用；不可用 → STOP 报 Kevin 决定升版本，不擅自改 pom。

### 3. 主动查单优先于回调（与收款的关键差异）

- **驱动 success 的主路径 = SnailJob 定时查单**（`@JobExecutor(name="gzPayoutQueryTask")`，逻辑在 service、job 类仅触发壳，沿用 ADR-0003 §4 的 SnailJob 范式 + memory `scheduler-is-snailjob`）：扫 `processing` 态的 payout 单 → 调 `queryTransferByOutNo` → 命中 `success`/`failed` 则推进终态。
- **回调为辅**：`gz_pay_payout_callback_log` 表保留（仿 `gz_pay_callback_log`），收到转账回调也走同一推进逻辑，但**不作为唯一依赖**——回调没到也能靠查单收敛。
- **CRON 注册**同 ADR-0003：仓库无 `sys_job` 表，**绝不在 Flyway DDL `INSERT INTO sys_job`**；任务由 SnailJob 控制台手工注册（任务名 / 路由 / CRON 写进 GZ-PAY-105 reports §SnailJob 控制台注册）。

### 4. 独立 payout 数据模型 + 独立状态枚举（不复用收款 transaction）

新两表（DDL 走 Flyway，强约束 #2/#3 tenant_id + 自动填充；菜单段 admin 挂 5100 GZ-PAY 段）：

- `gz_pay_payout_transaction`（反向打款单）：`out_payout_no`(PAYOUT- 业务码) / `business_type`(`recycle`) / `business_order_no`(=回收预约号 RCY-) / `receiver_openid` / `amount_cent` / `status`（**独立 `PayoutStatus` 枚举**）/ `payout_id` + `batch_id`（微信侧返回，**UNIQUE 幂等**）/ `fail_reason` / 审计列。
- `gz_pay_payout_callback_log`：仿 `gz_pay_callback_log`，记原始回调 body + 解析结果 + 处理幂等标记。

**`PayoutStatus` 枚举**（独立于收款 `PayStatus`，避免语义混用）：

| 取值 | 含义 | 进入条件 |
|---|---|---|
| `created` | 单已建、未发起 | 店员触发打款、落库 |
| `processing` | 已发起、待微信处理 | `transferToUserWallet` 返回成功受理 |
| `success` | 转账成功（终态） | 查单 / 回调命中 SUCCESS |
| `failed` | 转账失败（旁路终态） | 查单 / 回调命中 FAIL（余额不足 / 收款方限制等） |
| `cancelled` | 已撤单（旁路终态） | 极少，预留（如重复单人工撤） |

### 5. 幂等：商户单号双保险

- `out_payout_no`（商户侧生成、PAYOUT- 前缀）作为发起转账的**幂等键**——微信侧以 out_batch_no 去重，重复提交不重复打款。
- DB 侧 `payout_id` + `batch_id` 加 **UNIQUE**（微信返回唯一），二次回调/查单写入命中唯一约束 → 幂等丢弃。
- 一笔回收预约（`business_order_no`）与 payout 单 **1:1**：建单前先按 `business_order_no` 查是否已有非 `failed`/`cancelled` 的 payout 单，有则拒绝重复发起（防店员重复点「打款」）。

## Rationale

- **复用 ADR-0003 抽象与开关**：反向打款是收款 client 的能力扩展，不另起体系——同一 `IWechatPayClient`、同一 `gz.pay.client.mode`、同一 SnailJob 范式，认知与维护成本最低。
- **查单优先是微信官方姿态**：商家转账回调到达性弱，照搬收款「等回调」会让 payout 单长期 `processing`。查单驱动 + 回调辅助，状态机一定能收敛。
- **独立枚举 + 独立表**：资金流向相反、状态语义不同（收款的 paid/verified vs 打款的 success/failed），混用 `PayStatus` 必然语义漂移；独立 `PayoutStatus` 让对账与审计清晰。
- **mock 范式让全流程可测**：商户权限未到位时，mock 下 `created→processing→success` 全链路 + `failed` 分支 + 幂等都能跑通单测与 admin 工具页演示，外部资质不阻塞 D14。

## Consequences

- ✅ V1.2 回收反向打款代码完整落地（接口扩展 + 两表 + 状态机 + 查单 job + 幂等），不被商户权限阻塞。
- ✅ 单测稳定（永远 mock）；mock 下回收业务线 `submitted→...→paying→paid`（ADR-0007/回收状态机）可端到端演示。
- ✅ 商户「商家转账」权限到位后，切 `gz.pay.client.mode=real` + 注入 transfer 相关 env → 无缝切真实通道，代码零改动（同 ADR-0003 范式）。
- ⚠️ **真实上线 gate = 商户「商家转账到零钱」权限**：需甲方在商户平台单独申请（非默认开通，有资质门槛）。这是回收业务线唯一「代码就绪、待外部资质」尾项；列为 **pending，需 Kevin × 甲方**推进，不阻塞 D14 ticket close。权限到位后参照 ADR-0003 §2 流程做小额真实回归（建议 0.1 元 / 1 笔）。
- ⚠️ **新依赖批准 gate（铁律 #8）**：若 transferbatch service 不在当前 `wechatpay-java:0.2.17` 内需升版本 → GZ-PAY-105 §0 自检 STOP 报 Kevin，不擅自改 pom。
- ⚠️ **独立核算（合同 §4.1）**：回收反向出账是「店家付钱给用户」，**不计入 GMV、不计 4% 分成**（分成口径是正向流水 GMV − 退款 − 通道费）。对账中心（顺延 D16 ADMIN-105）需把 payout 流水**单列**，与拼豆/扭蛋正向流水隔离、不交叉冲抵。
- ⚠️ **转账手续费**：微信商家转账可能有手续费/笔数限制，归甲方运营成本，本系统不分摊；mock 不模拟手续费，真实环境届时核对。
