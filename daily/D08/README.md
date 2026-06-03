# D08 — V1.1 预购支付域：业务统一支付（V3）+ 预购商品/订单数据模型 + 预购下单全链路（mock 自测）

> 阶段：**V1.1 实施期**（V1.0 已通过 AI 测试，**尚未客户验收、尚未上线** —— 不是"已上线运行 1-2 周"）
> 上一日：[D7x](../D7x/README.md) ｜ 下一日：[D09](../D09/README.md)

---

## 今日目标

- **主线 1（业务统一支付，V3）**：把 PAY-001 已交付的【微信支付 V3】通道升级为**业务统一支付服务** —— 统一订单号 / SPI 回调路由 / 回调幂等 + 真实笔费回写对账批 + 主动查单补单 + 全额退款（PAY-101 / 104 / 102 / 103）。**全部基于已落地的 `gz_pay_transaction` / `gz_pay_callback_log` + `IWechatPayClient`（V3）**，不新造支付表、不回退 V2。
- **主线 2（预购下单全链路）**：预购商品 + SKU 数据模型（从零建）→ mp 商品列表 + 筛选 → 商品详情 + 下单确认 → 预购下单跨域事务（建 `gz_ord_order`，`business_type=preorder` 落 `gz_pay_transaction`）→ 预购订单查询（ORD-101 ~ 105）。

完工后，预购业务线在 **mock client 全链路自测**下端到端可跑通（C 端浏览 → 下单 → 调起 mock 支付 → mock 回调 → 出单 → 查单），为 D09 扭蛋（业务线 B）+ D10 物流/对账铺路。

> **推进姿态（Kevin 决策 1）= Mock 全链路自测**：dev/staging 用 `gz.pay.client.mode=mock`（`MockWechatPayClient`）跑通全链路并作为本日 DoD。**真实商户号 / 0.01 元端到端验证列为【外部前置风险】**（见 §已知风险 R1），不当默认就绪；同时并行催甲方完成 V1.0 验收。

## Ticket 清单（9 个，按依赖图分波次）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-PAY-101 | 业务统一支付服务（V3 / business_type 分流 / SPI 回调路由 / 回调幂等） | M | GZ-PAY-001 ✅ | pending |
| GZ-PAY-104 | 业务通道账单对账批（每日 SnailJob 拉 fundflowbill 回写真实笔费） | M | GZ-PAY-101 | pending |
| GZ-PAY-102 | 主动查单 + 补单（SnailJob） | S | GZ-PAY-101 | pending |
| GZ-PAY-103 | 退款服务（仅全额 / @SaCheckPermission / V3 退款回调 / 新建 gz_pay_refund） | M | GZ-PAY-101 | pending |
| GZ-ORD-101 | 预购商品 + SKU 数据模型（gz_ord_product / gz_ord_sku + admin CRUD 从零建 + 截止下架 SnailJob） | M | GZ-SYS-001 ✅ | pending |
| GZ-ORD-102 | mp 商品列表 + 筛选 | M | GZ-ORD-101 | pending |
| GZ-ORD-103 | mp 商品详情 + 下单确认 | M | GZ-ORD-101 + GZ-USER-003 ✅ | pending |
| GZ-ORD-104 | 预购下单跨域事务（建 gz_ord_order / business_type=preorder / C1 物流 2 态默认 in_japan） | M | GZ-ORD-103 + GZ-PAY-101 | pending |
| GZ-ORD-105 | 预购订单查询（C 端列表 + 详情） | S | GZ-ORD-104 + GZ-USER-004 占位页 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图（严格按波次 spawn —— 9 个 ticket 密度大，乱并行容易撞 schema / 撞回调路由链路）**：

```
波次 1（并行，互无依赖；两条主线各自起头）：
   GZ-PAY-101 ━━━━━━━━━━━━━━━━━━━┓   (锚定统一订单号 + SPI 回调路由 + business_type 分流)
   GZ-ORD-101 ━━━━━━━━━━━━━━━━━━━┫   (锚定 gz_ord_product/sku schema + snapshot 字段)
                                  ┃
波次 2（PAY-101 完工后 ‖ ORD-101 完工后，可同时并行）：
   GZ-PAY-104 ──依赖 PAY-101 ─────┫   (注册 SPI handler 不冲突 → 与 102/103 串行 review 回调路由)
   GZ-PAY-102 ──依赖 PAY-101 ─────┫
   GZ-PAY-103 ──依赖 PAY-101 ─────┫
   GZ-ORD-102 ──依赖 ORD-101 ─────┫
   GZ-ORD-103 ──依赖 ORD-101 + USER-003 ✅ ─┫
                                  ┃
波次 3（PAY-101 ✅ + ORD-103 ✅ 都完工后）：
   GZ-ORD-104 ──依赖 ORD-103 + PAY-101 ─┫   (V1.1 第一个跨域事务：ORD 落单 + 写 gz_pay_transaction)
                                        ┃
波次 4（ORD-104 完工后）：              ┃
   GZ-ORD-105 ──依赖 ORD-104 + USER-004 占位页 ─┛
```

## 派单方式

**整日触发**（推荐 —— 主线程读本 README → 严格按依赖图 spawn）：
```
开始 d8
```

**单 ticket 触发**（如某 ticket revision 闭环 / 局部重做）：
```
@coder 做 D08/GZ-PAY-101
```

主线程动作：
1. 读 D08/README.md（本文件）+ 依赖图
2. **波次 1**：并行 spawn GZ-PAY-101 + GZ-ORD-101（互无依赖）
3. **波次 2**（PAY-101 ✅ 后）：并行 spawn GZ-PAY-104 / PAY-102 / PAY-103；（ORD-101 ✅ 后）并行 spawn GZ-ORD-102 / ORD-103
4. **波次 3**（PAY-101 ✅ + ORD-103 ✅）：spawn GZ-ORD-104
5. **波次 4**（ORD-104 ✅）：spawn GZ-ORD-105
6. 9 个 ticket Tier 1A + 1B 全 ✅ → mp ticket（ORD-102/103/104/105）进 progress.md「人验」列；主线程提示 Kevin 可批量人验 + 日终 closing

⚠️ **不要乱并行**：波次 3 的 ORD-104 同时依赖 PAY-101（统一订单号 + 写 transaction 契约）+ ORD-103（下单确认页传参 + snapshot 字段），**两者都未 close 前 spawn 必然踩坑**。PAY-104/102/103 都注册 SPI 回调 handler，三者落地后**串行 review 一次回调路由表**避免 SPI 撞 key。

## 今日特殊约束

### 支付（PAY-101/104/102/103 必读）
- **复用 PAY-001 已交付的微信支付 V3**：`IWechatPayClient`（`WechatPayV3ClientImpl` / `MockWechatPayClient`）+ `apiV3Key` + V3 `NotificationParser`（AES-GCM）+ 回调 `POST /api/pay/v3/notify`。支付流水表是已落地的 `gz_pay_transaction` / `gz_pay_callback_log`。
  - **禁止**：V2 / XML / api-key（签名密钥旧体系）/ 新建 `gz_pay_order` / `amount_fen` 列 / `/api/wxpay/pay-notify` 端点。
- **Mock 姿态**：dev/staging `gz.pay.client.mode=mock`，本日全链路自测以 mock client 为准；真实商户号验证 = 外部前置风险（R1）。
- **统一订单号格式**（PAY-101 锚定，全 V1.1 ORD/GACHA/TEST 复用）：
  ```
  <域大写>-yyyyMMdd-<6 位序号>
  前缀枚举：PREORD / GACHA / TEST（与 D07 已发的 TEST-20260604-NNNNNN 单格式一致）
  全局唯一（DB UNIQUE 约束，含 tenant_id）
  ```
- **business_type 分流**（PAY-101 锚定，落 `gz_pay_transaction.business_type`）：取值 `preorder` / `gacha` / `test`。两业务线 4% 分成分别核算靠 `business_type` + 真实笔费 `fee_cent`，**不交叉冲抵**（合同 §4.1）。**禁止**在业务订单表（gz_ord_order）加 `business_line` / `biz_line` / A/B 列 —— 分流真源在 `gz_pay_transaction`。
- **回调幂等**（PAY-101 AC 锚定）：V3 回调 handler 入口先按 `out_trade_no` / `transaction_id` 在 `gz_pay_callback_log` 去重 + `SELECT ... FOR UPDATE` 锁交易行，已终态（paid/refunded）直接返回 success 不重复处理。
- **SPI 回调路由**（PAY-101 锚定）：支付成功回调按 `business_type` 路由到对应业务 handler（预购 → ORD 出单；扭蛋 → D09 GACHA）。各业务模块注册 SPI（如 `PayCallbackHandler` 接口），PAY-101 提供分发骨架 + 预购占位 handler（ORD-104 填实现）。
- **真实笔费回写（PAY-104，对账依赖）**：每日 SnailJob 拉 `/v3/bill/fundflowbill`（资金账单）解析回写 `gz_pay_transaction.fee_cent`（真实通道手续费，分），供 D10/D11 对账中心算"实际到账流水 = GMV − 退款 − 通道费"。mock 模式下生成 mock 账单文件自测解析逻辑。
- **退款仅全额（PAY-103）**：一笔对一单，**无金额 input**；新建 `gz_pay_refund`；V3 退款回调（独立 SPI 路由 key，与支付回调分流）。权限 `@SaCheckPermission("gz:pay:refund:apply")`（**不用 @SaCheckRole**）+ admin 授权 + 同租户 1001。**C 端无退款入口**，mp 订单详情仅文案"如需退款请联系客服"。

### 调度（PAY-104/102 + ORD-101 截止下架必读）
- **调度框架 = SnailJob**（`com.aizuda` `@JobExecutor`），**仓库无 sys_job 表**。cron 任务写法：`@Component` + `@JobExecutor(name="...")` 薄壳，业务逻辑下沉到**可单测 service**。
  - **禁止**：Quartz / Flyway `INSERT sys_job`（会启动 hard-fail）。
  - `ruoyi-gz-ord` 模块 pom **显式加 `ruoyi-common-job` 依赖**（gz-ord 当前是空脚手架，需新增）。
  - 任务名 + CRON 表达式写进 reports + testing-human，**由人在 SnailJob 控制台注册**（不写进迁移）。

### 数据模型（ORD-101 锚定，全域字段铁律）
- 金额一律 `_cent`（分），**不用 `_fen`**。
- snapshot 用 `*_snapshot_json`（JSON 列），**不散列成多列**。
- 图片用 `image_id` / `*_image_ids`（FK 到 `gz_file_object`），**不存裸 url**。
- 库存 `stock_total` / `stock_remain`（**不用 init/left**）；乐观锁 `version`；扣减 `UPDATE ... WHERE id=? AND version=?`。
- 状态枚举含 `auto_off`（自动下架，截止 SnailJob 触发），**不用 off_shelf/archived**。
- `del_flag` 仅 2 值（0 正常 / 2 删除，对齐 ruoyi `@TableLogic`），**不用 3 值**。
- `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`；INSERT 不显式赋（走自动填充）；UNIQUE 约束**必含 tenant_id**。
- 包名 `org.dromara.gz.ord.{controller,service,mapper,domain,dto}` / `org.dromara.gz.pay.*`。

### 订单 / 物流（ORD-104 锚定）
- **订单状态机**：`created → paid → in_logistics → delivered`（delivered = 终态）。`cancelled` 仅 `created`（未支付）态可达。
- **跨境物流 = C1 两态 + 终态**（**不是 7 节点**）：`logistics_status` 取值 `in_japan` / `in_china_dispatching` / `delivered`，**独立于 business_status 并行**，互不覆盖。预购下单默认 `in_japan`。
  - 进 `in_china_dispatching` 必录 `cn_carrier_code`（字典 `gz_express_carrier` 9 项：yto/sf/zto/yunda/jd/ems/debang/jitu/other）+ `cn_tracking_no`。
  - **禁止**：7 节点 / `logistics_node` / `gz_logistics_node` 表 / 批次推进 / 自动归集 / `gz_express_company` / 物流时间线色 / tokens 1.5。（admin 物流推进留 D10，本日仅落 logistics 字段 + 默认 in_japan。）
- **snapshot 落单**：ORD-104 下单时把当时商品名 / SKU 规格名 / 单价分 / 主图 image_id / 数量完整写进 `gz_ord_order.*_snapshot_json`，防商品下架/改名/调价后历史订单显示异常。
- **跨域事务**：ORD-104 同事务内建 `gz_ord_order` + 扣 `gz_ord_sku.stock_remain`（乐观锁）+ 调 PAY-101 创建 `gz_pay_transaction`（`business_type=preorder`）；任一失败回滚。

### 前端 / UI
- **mp 端视觉** = C 日漫海报浓墨设计系统：页面只用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token（不直接撒 `<wd-*>`，功能性 wd 组件如 swiper/popup/action-sheet 外观套 C token），权威 doc/tokens.md + doc/13；mockup 仅布局参考，不逐像素还原。注意 **C 阴影 token 无 `--c-shadow-card`**（mem）。
- **admin 端**（PAY-103 退款 / ORD-101 预购商品 CRUD）走 ruoyi/Element Plus 默认审美 + 复用 BizTable / Form；**ORD-101 admin UI 从零建**（无 V1.0 商品骨架可复用）。
- **i18n 强制**：mp / admin 可见字符串全走 `t('xxx.yyy')` + zh-CN 默认；不混 emoji。

### 流程
- **§0 自检改为 grep migration 目录实际存在的表**（`ls db/migration/` + grep `gz_ord_` / `gz_pay_`），**不假设上游已建**。gz-ord / gz-gacha 当前是空脚手架（仅 HelloController），gz_ord_* 表全部不存在 → 本日从零起。
- **menu_id 分段**：预购商品 admin 走 **9100 段**（GZ-ORD）；退款权限 perm key `gz:pay:refund:apply`（菜单挂 GZ-PAY 5100 段）。
- **DDL 命名**：`V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`，时间戳必须 > 当前最大 `V202606051200`。已应用迁移不可改。
- **不要 commit**：9 个 ticket Tier 1A + 1B 全 ✅ + mp ticket 进人验列后再统一 commit。

## 与昨日 reports 对账（真实已交付清单）

> ⚠️ 以下是**经核实的真实已交付状态**（grep 代码 + migration 目录确认），不是"假 OK"。gz-ord / gz-gacha 是空脚手架，V1.1 从零起。

**可直接复用的真实底座**：
- ✅ **PAY-001 微信支付 V3 通道**：`IWechatPayClient`（`WechatPayV3ClientImpl` / `MockWechatPayClient`）+ `apiV3Key` + V3 `NotificationParser`（AES-GCM）+ 回调 `/api/pay/v3/notify` 已交付。PAY-101 在其上做业务通用化，**不改 V3 选型**。
- ✅ **支付三表已落地**：`gz_pay_channel` / `gz_pay_transaction` / `gz_pay_callback_log`（迁移 `V202606041200`）。PAY-101 扩展 `gz_pay_transaction`（加 `business_type` / `fee_cent` 等），**不新建支付表**。
- ✅ **gz_user_address 地址簿已交付**（迁移 `V202606031100`）：ORD-103 下单确认选地址直接读，无需新建表。
- ✅ **D7x mp 管理端权限底座（ADR-0004 / GZ-SYS-007）已交付**：`gz_user.staff_user_id` 绑 sys_user + 登录加载 ruoyi RBAC + `@SaCheckPermission` + 停用/解绑即时踢（`SysUserStaffKickoutAspect`）+ `StaffMeController`。**下沉 mp 的功能复用它**：加一行 `@SaCheckPermission(perm key)` + admin 授权 + 同租户 1001（本日退款权限即走此底座）。
- ✅ **gz_user / gz_user_audit_log** 已落地（USER 域 V1.0）；**gz_file_object** 已落地（image_id FK 目标表）。

**明确不存在 / 不要当 OK（从零建）**：
- ❌ `ruoyi-gz-ord` / `ruoyi-gz-gacha` = 空脚手架（各 1 个 HelloController），`gz_ord_*` / `gz_gacha_*` / `gz_recon_*` 表**全部不存在**，plus-ui 这些域只有 Hello.vue。
- ❌ 无"V1.0 已上线"前提：V1.0 仅"已通过 AI 测试、未客户验收、未上线"。回切 V1.0 路径需评估（不假设线上稳定）。
- ❌ 无 USER-101（已删，不依赖）；ORD-105 依赖 **GZ-USER-004 占位页**（会员中心订单入口占位），不依赖假 USER-101。
- ❌ 无 ADMIN-005 商品骨架（不存在，ORD-101 admin CRUD 从零建）；无 ADMIN-103 订单详情骨架（不存在，PAY-103 退款 admin 页从零建）。

## 完成判定（DoD）

- [ ] 9 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 9 个 reports/<T>.md 写完（含 §0 自检 grep migration 实际表 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] mvn install（含新增 `ruoyi-gz-ord` 实体/依赖）+ plus-ui build + miniapp dev:mp-weixin 三端全绿
- [ ] **PAY-101 + 104 + 102 + 103 在 `gz.pay.client.mode=mock` 下自测通过**：创建预订单（PREORD-yyyyMMdd-NNNNNN）→ mock 调起 V3 支付 → mock V3 回调（AES-GCM 解析）→ business_type SPI 路由到预购 handler → 订单 paid；重复回调幂等（不二次变更）；查单补单；全额退款 + 退款回调；fundflowbill mock 解析回写 fee_cent
- [ ] **ORD-104 + 105 在 mp 模拟器 + mock 支付下跑通**：商品列表 → 筛选 → 详情 → 下单确认（选 gz_user_address）→ 跨域事务出单（gz_ord_order + gz_pay_transaction business_type=preorder + logistics_status=in_japan）→ mock 支付成功 → 状态 paid → 会员中心订单查询可见
- [ ] mp ticket（ORD-102/103/104/105）Tier 2 入口可达性已验（临时入口注释存在）+ 进 progress.md「人验」列
- [ ] testing-human.md 全勾（含 SnailJob 任务名 + CRON 待人工注册清单）
- [ ] cat reports/*.md > summary.md 已生成

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **真实微信支付商户号 / 0.01 元端到端 = 外部前置风险**（甲方挂号 + cert + apiV3Key 就绪滞后） | 本日 DoD 仅认 mock 全链路（`gz.pay.client.mode=mock`）；真实端到端在备注段标注【外部前置风险】，不当默认就绪；并行催甲方完成 V1.0 验收 + 提供商户配置 |
| R2 | PAY-104/102/103 都注册 SPI 回调 handler / 路由 key → 撞 key 或回调路由混乱 | PAY-101 先定 SPI 接口 + 路由表（按 business_type + 支付/退款类型分流）；104/102/103 落地后**串行 review 一次路由表**，支付回调与退款回调用不同 SPI key |
| R3 | 9 个 ticket 同日密度大，波次 3 ORD-104（V1.1 第一个跨域事务）被挤压草率收尾 | 严格按波次 spawn；ORD-104 §0 自检若发现 PAY-101 SPI 契约或 ORD-103 传参未定 → STOP 报 Kevin，宁可单独抽到 D09 头，不强压 |
| R4 | gz-ord 是空脚手架，pom 缺 `ruoyi-common-job` → ORD-101 截止下架 SnailJob executor 编译失败 | ORD-101 §0 自检确认 pom 依赖；新增 `ruoyi-common-job` 到 gz-ord pom 后先 `mvn install -pl ruoyi-gz-ord -am` 再写 executor |
| R5 | ORD-101 snapshot 字段定义不齐 → ORD-104 下单漏字段 | ORD-101 与 ORD-104 同步 review snapshot 清单（商品名 / 主图 image_id / SKU 规格名 / 单价分 / 数量，至少 5 项），写进 doc/11 `gz_ord_order` 段；统一 `*_snapshot_json` JSON 列不散列 |
| R6 | mp 商品筛选字段（IP / 系列标签）在 ORD-101 未建 → ORD-102 回退改 schema | ORD-101 schema 含筛选标签字段（如 `ip_tag` / `series_tag`）+ 建索引；ORD-102 实施前 grep migration 确认字段存在 |
| R7 | business_type 分流误落在订单表（biz_line/A-B 列）→ 违反字段铁律 + 对账取数错源 | 分流真源只在 `gz_pay_transaction.business_type`；ORD-104 落单不加 business_line 列；kevin-qa Tier 1B grep `gz_ord_order` schema 无 business_line/biz_line |
| R8 | C1 物流被实现成 7 节点 / 批次推进（违反 Kevin 决策 4） | ORD-104 logistics 字段仅 `logistics_status`（in_japan/in_china_dispatching/delivered）+ `cn_carrier_code` + `cn_tracking_no`；禁建 logistics_node 表；admin 推进留 D10 |

---

## 日终 closing 命令

```bash
cd doc/daily/D08
cat reports/*.md > summary.md
# Kevin 批量人验（mp ticket ORD-102/103/104/105 真机 happy path）按自定节奏跑，不阻塞日常
# AI 全 ✅ 后统一 commit：
git add -A && git commit -m "D08: V1.1 预购支付域 — 业务统一支付(V3) PAY-101/104/102/103 + 预购全链路 ORD-101~105（mock 自测）"
# 然后写 D09/README.md（D09 候选：GACHA 域扭蛋数据模型 + 抽盒事务 business_type=gacha + mp 扭蛋机）
```
