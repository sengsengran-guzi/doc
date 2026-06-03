# D08 — Progress ⭐ V1.1 预购支付域开张

> 9 ticket 全部 AI Tier 1A ✅ + 主线程波次集成 gate 全绿。预购业务线 A 在 **mock 全链路自测**下端到端打通。
> 支付域纯后端/admin（PAY-101/102/103/104）+ ORD-101 → AI ✅ 即终态（CLAUDE.md §8.2 例外，无 mp 人验）。
> mp ticket（ORD-102/103/104/105）→ 进「人验」列，待 Kevin 批量人验（真机 happy path + getPhoneNumber + mock 支付调起手感）。
> **真实微信支付商户号 / 0.01 元端到端 = 外部前置风险 R1**，本日 DoD 仅认 `gz.pay.client.mode=mock`。

---

| Ticket | 标题 | AI Tier 1A | 集成 gate | 人验 | revision | 状态 |
|---|---|---|---|---|---|---|
| GZ-PAY-101 | 业务统一支付服务（V3/business_type 分流/SPI 路由/幂等） | ✅ gz-common 18 新测 | ✅ install -am 绿 | N/A 纯后端 | 0 | ✅ AI done · 终态 close |
| GZ-PAY-104 | 业务通道账单对账批（SnailJob 拉 fundflowbill 回写 fee_cent） | ✅ 10 单测 | ✅ | N/A 纯后端 | 0 | ✅ AI done · 终态 close |
| GZ-PAY-102 | 主动查单 + 补单（SnailJob 复用回调幂等路径） | ✅ 10 单测（applyPaid 单点） | ✅ | N/A 纯后端 | 0 | ✅ AI done · 终态 close |
| GZ-PAY-103 | 退款服务（全额/@SaCheckPermission/V3 退款回调/gz_pay_refund） | ✅ 5 单测 + admin build | ✅ SPI 路由表 review 干净 | N/A 纯 admin/后端 | 0 | ✅ AI done · 终态 close |
| GZ-ORD-101 | 预购商品 + SKU 模型 + admin CRUD + 截止下架 Job | ✅ 12 单测 + 真 MySQL DDL | ✅ | N/A 纯后端/admin | 0 | ✅ AI done · 终态 close |
| GZ-ORD-102 | mp 预购商品列表 + 筛选 + 排序（解 ComingSoon） | ✅ 16 vitest + 16 后端 | ✅ | ⬜ 待批量人验（首页 teaser→列表/排序/IP chip/倒计时） | 0 | ✅ AI done · 进人验列 |
| GZ-ORD-103 | mp 商品详情 + 下单确认 | ✅ 后端 26 + mp 21 vitest | ✅ | ⬜ 待批量人验（详情/规格/校验/确认页/地址/勾选退款） | 0 | ✅ AI done · 进人验列 |
| GZ-ORD-104 | 预购下单跨域事务（gz_ord_order/business_type=preorder/物流 2 态） | ✅ gz-ord 36 单测 + mock 全链路 | ✅ 处理器下沉验证（每 SPI 1 handler，无重复注册） | ⬜ 待批量人验（提交→mock 支付→pay-result 三态） | 0 | ✅ AI done · 进人验列 |
| GZ-ORD-105 | 预购订单查询（C 端列表+详情 + admin 只读） | ✅ 后端 45 单测 + mp 7 vitest | ✅ 三端 build 绿 | ⬜ 待批量人验（我的→订单→预购 tab 真数据→详情时间线/物流卡） | 0 | ✅ AI done · mp 进人验列（admin 部分终态） |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

---

## 主线程波次集成 gate（DoD，按依赖图分波亲跑）

| 波次 | 命令 | 结果 |
|---|---|---|
| Wave 1（PAY-101∥ORD-101） | `mvn install -am -pl gz-common,gz-ord` | **BUILD SUCCESS** ✅ |
| Wave 2（PAY-104/102/103 串行 ∥ ORD-102/103 串行） | install -am + 合并单测 | **BUILD SUCCESS** · 0 fail ✅ |
| Wave 3（ORD-104 跨域 + 处理器下沉） | install -am + grep 验证 | **BUILD SUCCESS** · 每 SPI 恰 1 个 preorder handler ✅ |
| Wave 4（ORD-105） | install -am + 合并单测 + 三端 build | **BUILD SUCCESS** ✅ |
| D08 全量终态 | `mvn test -pl gz-common,gz-ord` | **gz-common 98 + gz-ord 45 = 143 单测 0 fail** ✅ |
| mp 全量 vitest | `pnpm test` | **172/172（25 文件）** ✅（修复 1 个 pre-existing bean 陈旧测试，见复盘） |
| plus-ui | `pnpm build:prod` | ✅（gz-ord 商品/订单 + gz-pay 退款 chunk 已 emit） |

---

## ⭐ SPI 回调路由表 review（R2 串行 review，主线程亲验）

PAY-104/102/103 落地后串行 review 一次 SPI 路由表，确认零撞 key：
- **支付 SPI**：`PayCallbackHandler.onPaid`（`PayCallbackDispatcher`，key=business_type）；callback_type=`payment`；endpoint `/api/pay/v3/notify`
- **退款 SPI**：`IRefundCallbackHandler.onRefunded`（`RefundCallbackDispatcher`，key=business_type）；callback_type=`refund`；endpoint `/api/pay/v3/refund-notify`
- 两套独立注册中心 → `preorder` key 落在不同 map，**零交叉**。PAY-104（拉账单跑批）/ PAY-102（查单补单复用 payment）均**未新增 SPI key**。
- **处理器归属（ORD-104 架构修正）**：gz-common 不能依赖 gz-ord（循环），故 preorder 的 pay/refund handler **下沉 gz-ord 实现**（`org.dromara.gz.ord.service.callback.*`），gz-common 占位 handler 已删，mock test 改内联匿名 handler。验证：每个 SPI 现恰好 1 个 preorder handler，无启动 fail-fast。

---

## ⏳ 待 Kevin / 部署侧动作（非阻塞，不影响 ticket close）

1. **SnailJob 控制台注册 3 个新 cron（D08）**：
   - `gzPayFundflowBillJob`（PAY-104，CRON `0 30 3 * * ?` 凌晨拉前一日资金账单）
   - `payOrderQueryJob`（PAY-102，CRON `0 0/1 * * * ?` 每分钟查单补单）
   - `ordProductDeadlineJob`（ORD-101，CRON `0 0 * * * ?` 每小时截止下架）
   - 均薄壳委托可单测 service；未注册前对应 cron 不触发（不影响主流程）。
2. **真实微信支付商户号（R1 外部前置）**：商户号 + cert + apiV3Key 就绪 → 核对主体「成都谷子宇宙贸易有限公司」（STOP 闸口）→ 注 env var + staging 切 `gz.pay.client.mode=real` → 打 0.01 元真单（预购/退款）+ 资金账单真实拉取验证。并行催甲方完成 V1.0 验收。
3. **Kevin 批量人验**（mp ticket ORD-102/103/104/105 真机 happy path + getPhoneNumber + mock 支付调起）。

## 阻塞 / 风险

- **后端 dev 离线**：集成 live API / admin Playwright E2E / SnailJob 控制台触发未跑（单测 + install + 三端 build 已绿，mock 全链路单测已覆盖跨域事务 + 回调路由 + 幂等）。kevin-qa 因 subagent 嵌套限制未独立 spawn，Tier 1B 由主线程波次集成 gate + grep 验证等效覆盖。
- 无功能性阻塞。**D08 9 ticket 全闭环（mock 自测口径）**。

## 已知 gap（需 Kevin 决策 / 排后续 ticket）

1. **「继续支付」幂等端点缺失**（ORD-105 raise）：卡面假设"复用 PAY-101 same order_no 幂等"，但 `createBusinessOrder` 每次生成新 out_trade_no + `business_order_no` 有 UNIQUE → 无现成"同单重唤收银台"端点。当前 created 态「继续支付」跳 pay-result（轮询+客服兜底，不重复扣库存）。**真·重唤需 PAY 域加幂等重建 prepay 端点** —— 建议排 V1.1 后续小 ticket（如 GZ-PAY-105），不在本日 scope。
2. **支付超时订单自动取消未实现**（ORD-104 raise，doc/10 §7.E7）：PAY-102 推进 transaction 到 timeout/closed，但 gz_ord_order 停在 created（用户可继续支付/主动 cancel 兜底）。订单侧自动 cancel 联动留后续。
3. **业务字典 seed 未落库**（ORD-105 raise）：`gz_express_carrier` / `gz_ord_business_status` / `gz_logistics_status` 用后端 enum 兜底翻译（功能完整）；建议 carrier 字典 seed 归 D10 ADMIN-104（录单号选择器才用到）。

## 已挪到明日的 ticket

无。D08 9 ticket 全部实现完成。**下一步 D09（GACHA 域：扭蛋数据模型 + 抽盒事务 business_type=gacha + mp 扭蛋机 + 注册 gacha SPI handler）。**
