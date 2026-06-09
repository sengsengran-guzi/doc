# D15 — V1.1 收官：物流 2 态推进 + 对账中心 ⭐（4% 分成核心）+ 看板扩展 + 软删恢复

> 阶段：**V1.1 实施期 收官日**（软期限 7/31，不绑日历日）
> 主题：**物流 C1 2 态推进（下沉 mp 店员端 + plus-ui owner 兜底）+ 对账中心 ⭐（合同 §4.1 4% 分成兑现核心）+ 数据看板扩展 + 软删恢复回收站**；火花券店移出实施位
> 上一日：[D14](../D14/README.md)（V1.2 批次收官 — 回收完成 RECYCLE-002/003 + tabbar 重构 SYS-010）｜ 下一日：— （V1.1 开发收官 → staging 部署 + 客户验收周期，软期限 7/31）
>
> **V1.0 真相**：V1.0 **已通过 AI 测试，但未客户验收、未上线**（不是"已上线运行 1-2 周"）。任何回切 V1.0 行为需评估，不假设线上稳定。
> **本批次起点真相**（主线程 §0 自检 **grep migration 目录实际验证，不假设上游已建**）：对账域 `gz_recon_*` 表**全部不存在**，对账从零起；物流推进依赖 D08/D09 已建的 `gz_ord_order` / `gz_gacha_order`（含 `logistics_status` / `cn_carrier_code` / `cn_tracking_no`）+ `gz_logistics_audit`（doc/11 §8.3）；通道真实笔费依赖 D08 **GZ-PAY-104**（`gz_pay_transaction.fee_cent` 回写）。

---

## 今日目标

V1.1 admin 收尾 + **对账中心立起来**（合同 §4.1 4% 分成兑现的唯一权威数据来源）：

- **主线 1（物流 2 态推进，下沉 mp）**：GZ-ADMIN-104 — 店员/owner 在订单详情手动把订单 `in_japan → in_china_dispatching`（**必录** `cn_carrier_code` + `cn_tracking_no`）→ `delivered`，写 `gz_logistics_audit` + `@Log`。**主形态下沉 mp 店员端**（手机现场发货录单），plus-ui owner 兜底。
- **主线 2（对账中心 ⭐）**：GZ-ADMIN-105 — `gz_recon_daily/monthly/settle` 跑批表（SnailJob 02:00 跑批前一日）；源 `gz_pay_transaction`（`amount_cent` / `fee_cent`，status=`paid`）+ `gz_pay_refund`；按 `business_type` 分 A（preorder）/ B（gacha）核算；**实际到账 = GMV − 退款 − 真实通道费**；月度落 `commission_cent`（bp=400）；季度 settle 含月维护费 ¥3000×3；Excel 每笔颗粒度 + 四项汇总导出。
- **主线 3（数据看板扩展）**：GZ-ADMIN-106 — V1.0 看板叠加 V1.1 交易/扭蛋/待发货指标；**复用 ADMIN-105 对账 service**；一个聚合接口一次性返所有卡片。
- **主线 4（软删恢复）**：GZ-ADMIN-108 — `del_flag` 2 值回收站（列 `del_flag=2`、恢复为 `0`）+ SnailJob 清理；`@InterceptorIgnore` 绕逻辑删拦截器。
- ⚠️ **GZ-ADMIN-107 火花券店 = v2 候选（Kevin C3 已裁定，移出 V1.1 实施位）**：本日**不实施代码**，仅占位标注，不阻塞其余 4 卡。

完工后甲方可以：
- 店员手机登 mp（或 owner 在 plus-ui）把预购/扭蛋订单从「在日本 → 已发往中国」（必录快递公司 + 单号）推到「已签收」，全程进 `gz_logistics_audit` + 操作日志；录错单号有二次入口可改。
- 在 admin「对账中心」按月/季度拉两条业务线（A 预定 / B 扭蛋）的 GMV / 退款 / 通道费 / 实际到账，Excel 导出每笔颗粒度对照微信商户后台流水比对（误差 = 0）。
- 在 admin「数据看板」一屏看到 V1.1 完整交易盘面 + 待发货订单数提醒。
- 在 admin「回收站」找回误删的商品 / 文章 / 扭蛋 SKU / 门店等业务记录（`del_flag=2 → 0`）。

**V1.1 收官完成后整理 V1.1 集成回归（见末节 checklist）→ staging 部署 + 通知甲方进入客户验收周期。**

## Ticket 清单（5 个 / 4 个实做 + 1 个 v2 候选占位）

| Ticket | 标题 | 端 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| GZ-ADMIN-104 | 物流 2 态推进（mp 店员端主形态 + plus-ui owner 兜底） | mp + admin + 后端 | M | GZ-ADMIN-103 + GZ-USER-103 | pending |
| **GZ-ADMIN-105 ⭐** | **对账中心（4% 分成兑现核心，合同 §4.1）** | admin + 后端 | **L** | GZ-ADMIN-103 + **GZ-PAY-104** | pending |
| GZ-ADMIN-106 | 数据看板扩展（复用 ADMIN-105 service） | admin + 后端 | M | GZ-ADMIN-103 + GZ-ADMIN-105 | pending |
| GZ-ADMIN-108 | 软删恢复回收站（del_flag 2 值 + SnailJob 清理） | admin + 后端 | S | GZ-ADMIN-101 + GZ-NEWS-003 | pending |
| ⚠️ GZ-ADMIN-107 | 火花券店 → **v2 候选（移出实施位）** | — | — | — | **deferred (v2，Kevin C3 已裁定)** |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图**：

```
ADMIN-104 ━━━━━━━━━━━━━━━┓  (物流 2 态推进，独立链，下沉 mp)
ADMIN-108 ━━━━━━━━━━━━━━━┫  (回收站，独立链)
ADMIN-105 ⭐ ━━━━━━━━━━━━━┫  (对账中心，独立链；显式依赖 PAY-104 真实 fee_cent)
                          ┃
                          ▼
        ADMIN-105 ✅ ──→ ADMIN-106 (看板复用对账 service + 待发货聚合)

ADMIN-107 ✗ 不实施（v2 候选占位，不阻塞）
```

- **ADMIN-104 / ADMIN-105 / ADMIN-108 可并行**（互无依赖，仅依赖前序日已完工的 ticket — 主线程 §0 grep migration 实际校验上游表存在）
- **ADMIN-106 必须等 ADMIN-105 完工后**再起（看板复用对账聚合 service）
- **ADMIN-107 本日不实施**：v2 候选，仅占位卡（doc/11 附录 X.1 已记，C3 裁定），不产出代码、不进波次

## 派单方式

```
开始 d15
```

主线程动作：
1. 读 D15/README.md + 依赖图，做 §0 自检（grep migration 目录确认 `gz_ord_order` / `gz_gacha_order` / `gz_logistics_audit` 已建 + `gz_pay_transaction.fee_cent` 由 PAY-104 回写在位；`gz_recon_*` 应不存在 = 从零建）
2. **第一波并行 spawn**：ADMIN-104 + ADMIN-105 ⭐ + ADMIN-108 三条线同时起
3. ADMIN-105 ✅ 后 spawn ADMIN-106
4. ADMIN-107 跳过实施，主线程仅确认占位卡标 `deferred (v2)`，不派单
5. kevin-coder 每卡完工自动 spawn kevin-qa（Tier 1B）：
   - 纯 admin / 纯后端（ADMIN-105 / 106 / 108）→ AI Tier 1A + 1B 全 ✅ 即终态，**无人验**
   - mp 部分（ADMIN-104 mp 店员端物流推进）→ 进 progress.md「人验」列待 Kevin 批量验
6. 4 卡全 ✅ → 日终 closing + **整理 V1.1 集成回归 checklist**（见末节）

## 今日特殊约束 ⭐

### ADMIN-105 对账中心是 4% 分成兑现核心（合同 §4.1，零容忍）

> **doc/11 §9（对账中心域 4 表字段口径）+ §4.6（4% 分成核心计算口径）是本 ticket 唯一权威，AI 实施前必读全文。doc/10 §10（对账中心流）是业务流权威。**

- **跑批表（从零建，doc/11 §9）**：
  - `gz_recon_daily`（§9.1）— SnailJob **每日 02:00 跑批前一日**，UNIQUE(tenant_id, business_day, business_type)，每业务线一条
  - `gz_recon_monthly`（§9.2）— 每月 1 日跑批前月，含 `commission_rate_bp`（默认 400 = 4%）+ `commission_cent`
  - `gz_recon_settle`（§9.4）— 每季度末月 15 日前跑批，季度结算记录
  - `gz_recon_exception`（§9.3）— 系统侧 vs 通道侧 diff 异常（V1.1 可先建表 + 留 hook，channel 侧数据待 PAY 拉账单）
- **金额口径（doc/11 §9.1 / §4.6，逐字落地，不自行发挥）**：
  ```
  system_gmv_cent    = SUM(gz_pay_transaction.amount_cent  WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)
  system_refund_cent = SUM(gz_pay_refund.refund_amount_cent WHERE 关联 transaction.business_type=? AND DATE(refunded_time)=?)
  system_fee_cent    = SUM(gz_pay_transaction.fee_cent     WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)   ← fee_cent 来自 PAY-104 拉 fundflowbill 回写
  system_settle_cent = system_gmv_cent − system_refund_cent − system_fee_cent     ← 实际到账流水（合同 §1.5 核心口径）
  ```
- **business_type 分流（A / B 分别核算，不交叉冲抵，合同 §4.1.2）**：
  - 业务线 A = `business_type='preorder'`；业务线 B = `business_type='gacha'`
  - 两条线各自 `settle_cent × 400 / 10000`（向下取整到分）= 各自 `commission_cent`，不互相冲抵
  - **任一业务线该月负流水 → 该业务线该月 `settle_cent = MAX(0, ...)`**（不让乙方倒贴，doc/10 Q10.4 / doc/11 §9.2）
  - **`business_type='test'` 单 exclude**（不进对账，doc/11 F4.2）
- **退款归属（C4 已裁定）**：仅全额退款，按 `refunded_time` **当日归属**，不追溯调整原订单成交日（doc/11 §9.1 / §4.6）
- **季度 settle（doc/11 §9.4）**：锚 3/6/9/12 月 15 日前；`commission_total_cent = SUM(monthly.commission_cent WHERE quarter)`（A+B 相加）；`maintenance_total_cent = 300000 × 3 = 900000`（¥3000 月维护 × 3，合同 §4.6）；`payable_total_cent = commission_total + maintenance_total`
- **Excel 导出（合同 §4.2.1 强制，doc/11 F9.5）**：每笔交易颗粒度 5 列（订单号 / 金额 / 时间 / 状态 paid·refunded / 通道费明细）+ 四项汇总（GMV / 退款 / 通道费 / 实际到账）；**给甲方可一键复制到银行流水比对的颗粒度**（不做透视表 / 不合并单元格）；ruoyi 自带 EasyExcel
- **commission_rate_bp 走 sys_config**（doc/11 F9.4）：`gz.commission.rate.preorder` / `gz.commission.rate.gacha` 默认 `400`；`gz.commission.maintenance.monthly.cent` 默认 `300000`
- **SnailJob 跑批（非 sys_job）**：跑批逻辑写**可单测 service**，外层 `@Component + @JobExecutor` 薄壳；任务名 + CRON 写进 reports / testing-human 由 Kevin 在 SnailJob 控制台注册；**禁止** Quartz / Flyway INSERT sys_job（启动 hard-fail）；模块 pom 显式加 `ruoyi-common-job` 依赖
- **reports/<T>.md 必须含「对账数据 vs 沙箱流水比对」raw output**：取测试库一周数据 → 跑对账中心 GMV / 退款 / 通道费 / 实际到账 → 与 mock/沙箱流水对比（**金额误差 = 0**）；比对失败 → STOP 报 Kevin，不 close

### ADMIN-104 物流 C1 2 态推进（不是 7 节点 / 不是批次推进）

> **doc/10 §9（跨境物流流，C1 裁定 2 态 + 终态）是业务流权威；doc/11 §8.3（`gz_logistics_audit`）+ 附录 A.7（logistics_status）是字段权威。** ⚠️ **删除 7 节点 / `logistics_node` / `gz_logistics_node` 表 / 批次推进 / 自动归集 GROUP BY / `gz_express_company` 等一切 v0.1 概念。**

- **物流状态（C1 2 态 + 终态，附录 A.7）**：`in_japan`（建单默认）→ `in_china_dispatching`（已发往中国）→ `delivered`（已签收）。`logistics_status` **独立于 `business_status` 并行**，不互相覆盖（退款时 business_status=refunded，logistics_status 保留最后态，UI 显「已退款」覆盖）
- **进 `in_china_dispatching` 必录**（doc/10 §9.N2）：`cn_carrier_code`（走字典 `gz_express_carrier` **9 项**：yto/sf/zto/yunda/jd/ems/debang/jitu/other）+ `cn_tracking_no`；**表单二者必填，否则提交按钮 disabled**（doc/10 §9.E5）
- **admin 端形态 = 订单详情手动切换状态 + 录单号**（**不是**批次推进、不是多选批量归集）。支持单订单切；如要多选可勾选一起切（doc/10 Q9.5），但**无"按批次自动归集"概念**
- **录错单号二次入口**（doc/10 §9.N9 / §9.E2）：admin 可改 `cn_carrier_code` / `cn_tracking_no`，写 `gz_logistics_audit`（`action_type=carrier_update`，记 from/to）；**不禁止修改**（甲方运营反复修是常态）
- **每次状态/单号变更写 `gz_logistics_audit`（doc/11 §8.3）+ `@Log`**：`action_type` 取 `status_forward` / `carrier_set`（首录）/ `carrier_update`（改单号）/ `status_rollback`（owner 回退，`reason` 必填）；`operator_type=admin`
- **下沉决策（Kevin 决策 2）**：物流推进**主形态下沉 mp 店员端**（复用 ADR-0004 权限底座：`@SaCheckPermission` + 同租户 1001 + 停用/解绑即时踢），店员手机现场发货录单；**plus-ui owner 兜底**（owner 电脑后台也能切 + 回退）
- **订阅消息（doc/10 §9.N7，可选）**：如 USER-103 已留 hook，进「已发往中国」/「已签收」推订阅消息；未就绪则留 hook 不阻塞

### ADMIN-106 数据看板扩展（复用 ADMIN-105 service）

> **doc/10 §10 涉及 ticket 含 ADMIN-106；复用 ADMIN-105 对账 service，不另建汇总表。**

- 卡片清单：
  - 今日订单数 / 今日 GMV（按 `business_type` 分 A / B 两块）
  - 本月累计 GMV / 退款 / 实际到账（按 A / B，**复用 ADMIN-105 `gz_recon_monthly` / 对账 service**）
  - 扭蛋本月开盒数 + 平均出货价值（盲盒语义：开盒 / 获得，非抽奖 / 中奖）
  - 热销预购商品 Top N
  - **待发货订单数** = `business_status='paid' AND logistics_status='in_japan'`（提醒甲方推进物流）
- **一个聚合接口一次性返所有卡片**（R5：不要前端 8 次串行调）；V1.1 数据量小不加缓存
- 数据源：ADMIN-105 对账聚合 service + `gz_ord_order` / `gz_gacha_order` / `gz_pay_transaction` 实时查询

### ADMIN-108 软删恢复回收站（del_flag 2 值，对齐 ruoyi @TableLogic）

> **doc/11 §0.3（命名规范，`del_flag` 仅 2 值 0 正常 / 2 删除）是字段权威。** ⚠️ **不用 3 值（无 1=删 2=归档 的旧范式）。**

- **回收站页**：列出业务表 `del_flag=2` 记录（按删除时间倒序），owner「恢复」= `del_flag=2 → 0`
- **`entity_type` 列举**：**§0 自检 grep migration 目录确认真实表名**（如 `gz_bean_store`，**不假设** `gz_user` / `gz_news_article` 命名）；只把实际建了的业务表纳入回收站
- **`@InterceptorIgnore` 绕逻辑删拦截器**：查 `del_flag=2` 记录 + 恢复更新必须绕过 ruoyi `@TableLogic` 默认拦截（否则查不到已删记录 / 恢复 update 被拦），mapper 方法标 `@InterceptorIgnore(tenantLine=false 不动；blockAttack/illegalSql 视需要)` 仅放开逻辑删拦截
- **SnailJob 清理（非 sys_job）**：如需定时物理清理超期 `del_flag=2` 记录，写可单测 service + `@JobExecutor` 薄壳；任务名/CRON 写 reports/testing-human；**禁止** Flyway INSERT sys_job
- **权限**：owner `@SaCheckPermission`（如 `gz:admin:recyclebin:list` / `:restore`），不用 `@SaCheckRole`

### ADMIN-107 火花券店 = v2 候选（移出 V1.1 实施位）⚠️

- **Kevin C3 已裁定为 v2 候选**（doc/11 附录 X.1 火花券店 + mockup `gacha-spark-shop.html`）：PRD §5.2 明确"不做扭蛋积分 / 代币兑换"，早期 designer 出图未对齐 PRD
- 本日**不实施任何代码**，`tickets/GZ-ADMIN-107.md` 仅占位 + 标 `deferred (v2)`；**不进波次、不阻塞其余 4 卡**
- 不再走 5/31 会议决策流程（C3 已拍板 v2）；关联 mockup 在 doc/11 附录 X.1 已标 v2 候选

### 全局

- **admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统）**：ADMIN-105 / 106 / 108 全部 plus-ui BizTable + Element Plus 默认 + ruoyi 自带 EasyExcel 导出，**不调样式、不引 mockup 像素**（admin 不评判视觉）
- **mp（ADMIN-104 店员端物流推进）走 C 日漫海报浓墨**：只用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token，不直接撒 `<wd-*>` 标签；doc/tokens.md + doc/13 为准（**禁止**引 tokens §9，不存在）。⚠️ **不做物流时间线色 / 不引 tokens 1.5**（C1 删节点流转，无时间线）
- **menu_id 段（doc/11 §10.3，无 FINANCE 11100 段）**：
  - 物流推进 → **11003**
  - 对账中心 → **11004**
  - 季度结算 → **11005**
  - 软删恢复回收站 → **11006**
  - （预购商品 admin 9100 段 / 扭蛋池 admin 10100 段 / GACHA 10000-10099 在前序日已占；本日新增 menu 严格落 11003-11006）
- **包名（CLAUDE.md §6 #4）**：`org.dromara.gz.<域>.{controller,service,mapper,domain,dto}`；ADMIN-105 / 106 跨域对账聚合 → 放 `org.dromara.gz.recon.*`（对账域独立包）；物流推进 ADMIN-104 复用 `gz.ord.*` / `gz.gacha.*` 订单域 + `gz.common` 物流审计
- **字段/命名硬约束（每卡复核）**：金额 `_cent`（不用 `_fen`）/ snapshot 用 `*_snapshot_json`（JSON 列）/ 图片 `image_id`·`*_image_ids`（FK gz_file_object，不存裸 url）/ 业务线统一 `business_type`（落 gz_pay_transaction，**禁止** business_line·biz_line·A/B 列）/ 订单号 `域大写-yyyyMMdd-6位序号`（PREORD·GACHA·TEST，全局唯一 DB 约束）/ 库存 `stock_total`·`stock_remain`+乐观锁 `version`+状态含 `auto_off`/ `del_flag` 2 值 / `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋，走自动填充；UNIQUE 必含 tenant_id）
- **DDL 命名 `V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`**（时间戳 > 已有最大版本；已应用迁移不可改）；**不动 ruoyi 自带模块**
- **不要 commit**：4 卡全完工 + AI 测试全 ✅ + Kevin 批量人验过 ADMIN-104 mp 店员端物流推进后再统一 commit

## 推进姿态（Kevin 决策 1）= Mock 全链路自测

- 对账数据源是 `gz_pay_transaction`（含 `fee_cent`）+ `gz_pay_refund`，在 **`gz.pay.client.mode=mock`** 下由 D08/D09 mock 全链路产生的交易/退款数据驱动；ADMIN-105 跑批 + 比对在 mock 数据上闭环
- **真实商户号 / 0.01 元端到端 / 真实 fundflowbill 笔费 / 微信商户后台流水比对列为【外部前置风险】**（见 §已知风险 R2），不当默认就绪；并行催甲方完成 V1.0 验收

## 上游 reports 对账（V1.1 收官真实依赖 D08-D10；上一日 = D14 V1.2 批次收官）

本日真实上游来自 V1.1 早期 ticket（D08-D10），**不是上一日 D14（V1.2 批次）**——应交付（**主线程 §0 自检 grep migration 目录实际验证，不假设上游已建**）：
- GZ-ADMIN-103 订单管理三类聚合（走 `gz_pay_transaction` 按 `business_type` 回查）→ ADMIN-104 物流推进 / ADMIN-105 对账 / ADMIN-106 看板都消费它
- GZ-USER-103 mp 物流 C1 2 态展示（只读侧）→ ADMIN-104 是其**写入侧**（USER-103 渲染的状态/单号由 ADMIN-104 写入 + `gz_logistics_audit`）
- GZ-ADMIN-101 预购商品 CRUD + GZ-NEWS-003 资讯 CMS（含 `del_flag`）→ ADMIN-108 回收站消费其软删字段
- `gz_ord_order` / `gz_gacha_order`（D08/D09 已建，含 `logistics_status` / `cn_carrier_code` / `cn_tracking_no` / `paid_time` / `delivered_time`）+ `gz_logistics_audit`（doc/11 §8.3）+ `gz_pay_transaction.fee_cent`（D08 PAY-104 回写）+ `gz_pay_refund`（D08 PAY-103）

进 D15 前主线程 §0 自检校验（**grep 实际存在的表，不假设**）：
```bash
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ \
  | grep -E 'GZ-ORD-104|GZ-GACHA-104|GZ-PAY-104|GZ-PAY-103|gz_logistics_audit|GZ-ADMIN-103|GZ-USER-103'
grep -rl 'gz_logistics_audit\|fee_cent\|gz_pay_refund' \
  code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
# gz_recon_* 应当查不到（= 本日从零建，正常）
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'gz_recon|GZ-ADMIN-105' || echo "gz_recon 不存在 = 正常，本日从零建"
```
上游表/字段齐 → 开工；缺则 STOP 报 Kevin（先回前序日收尾）。D10 summary.md「对下游 ticket 的提示」段（统一 logistics_status 枚举 / cn_carrier_code 命名 / business_type 取值）在 ADMIN-104/105 实施前主线程逐条对齐（D10 = ADMIN-103/USER-103 交付日，对账真源所在）。

## 完成判定（DoD）

- [ ] 4 个实做 ticket 任务卡 §revision 段空（ADMIN-104 / 105 / 106 / 108）
- [ ] GZ-ADMIN-107 占位卡标 `deferred (v2，Kevin C3 已裁定)`，不产出代码
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 grep migration raw output + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] **ADMIN-105 ⭐ reports 必须含「对账数据 vs 沙箱流水比对」raw output（金额误差 = 0）**（GMV / 退款 / 通道费 / 实际到账四项 + A/B 分流 + commission_cent 校验）
- [ ] mvn install（ruoyi-gz-ord / gacha / common + recon 所在模块 -am）+ plus-ui build:prod 全绿；ADMIN-104 含 mp 部分 → 加 miniapp build:mp-weixin 绿
- [ ] ADMIN-105 / ADMIN-108 SnailJob 任务名 + CRON 写进 reports + testing-human（待人在 SnailJob 控制台注册）；**确认无 Flyway INSERT sys_job**
- [ ] Tier 1A + 1B（kevin-coder 自测 + kevin-qa：admin Playwright E2E + 后端集成 + 单测）全 ✅
  - 纯 admin / 纯后端（ADMIN-105 / 106 / 108）AI ✅ 即终态，**无人验**
  - mp（ADMIN-104 店员端物流推进）进 progress.md「人验」列待 Kevin 批量验
- [ ] testing-human.md 预填（mp happy path + 可达路径，仅 ADMIN-104 mp 部分）：
  - 店员账号登 mp → 个人中心「门店管理」→「物流推进」（或从「订单查看」详情进）→ 选订单 → 切「已发往中国」必录快递公司 9 选 1 + 单号 → 提交 → 再改单号一次 → 推到「已签收」；停用 sys_user 后即踢，再调 401/403
- [ ] V1.1 集成回归 checklist 全绿（见下节）
- [ ] V1.1 范围 ticket 全部 close（D08-D10 + 本日 D15；GZ-ADMIN-107 标 v2 deferred，不计入实施）

## V1.1 收官 — 集成回归 checklist（本日末整理，写 `D15/v1.1-integration-checklist.md`）

收官完成后整理一份独立 checklist（closing 时写，不在本 README 内），按 **C1 2 态物流 + 对账 business_type 分流** 全链路验：

- [ ] V1.1 全链路（业务线 A 预购，mock client）：mp 浏览商品 → 下单 → mock 支付 → mock 回调出单（`business_type=preorder` 落 `gz_pay_transaction`，`logistics_status=in_japan`）→ 店员 mp 推「已发往中国」必录 9 选 1 快递 + 单号 → mp 用户详情看 2 态 + 复制单号 → 「确认收货」/ 7 天自动签收 `delivered` → 次日 02:00 SnailJob 跑批 → 对账中心业务线 A 看到对应 GMV / 通道费 / 实际到账
- [ ] V1.1 全链路（业务线 B 扭蛋，mock client）：mp 开盒（盲盒语义）→ mock 支付 → 衍生订单（`business_type=gacha`）→ 订单聚合页可见 → 物流 2 态推进 → 对账中心计入业务线 B（与 A 不交叉冲抵）
- [ ] 对账金额三层比对（误差 = 0）：`gz_recon_daily` SUM → `gz_recon_monthly` GMV/退款/通道费/实际到账 → 手动 SQL 汇总 `gz_pay_transaction`/`gz_pay_refund`；`commission_cent = settle_cent × 400 / 10000`（向下取整）逐月校验；`business_type='test'` 单已 exclude
- [ ] A/B 不交叉冲抵：构造业务线 A 当月退款 > 收入（负流水）→ A 该月 `settle_cent=0`、分成 0，**不冲减 B 的分成基数**
- [ ] 退款归属：跨月退款按 `refunded_time` 当日归属（不追溯调原成交月）
- [ ] 季度 settle：`commission_total_cent`（A+B）+ `maintenance_total_cent`（300000×3）= `payable_total_cent` 计算正确
- [ ] 对账中心 Excel 导出：每笔交易 5 列颗粒度（订单号/金额/时间/状态/通道费明细）+ 四项汇总，可一键复制比对
- [ ] 物流 2 态推进：进「已发往中国」未录单号 → 提交按钮 disabled；录单号后写 `gz_logistics_audit`（`carrier_set`）；改单号写 `carrier_update`（记 from/to）；owner 回退写 `status_rollback`（reason 必填）
- [ ] 软删恢复：误删 1 个业务记录（`del_flag=0→2`）→ 回收站可见（`@InterceptorIgnore` 生效）→ 恢复（`del_flag=2→0`）→ 业务列表/mp 端重新可见；SnailJob 清理任务可手动触发
- [ ] 数据看板：今日/本月数据 + 待发货订单数（`paid AND in_japan`）vs 手动 SQL 汇总（误差 = 0）；一个聚合接口返所有卡片
- [ ] 跨端权限：店员（ADR-0004 底座）可 mp 推物流，owner 可 plus-ui 物流兜底 + 对账中心 + 回收站 + 看板；停用/解绑 sys_user 即时踢 mp token

集成回归全绿 → staging 部署 + 通知甲方进入客户验收周期（软期限 7/31）。

## 已知风险 ⭐

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | ADMIN-105 对账金额口径出错 → 4% 分成兑现错 → 合同纠纷 | doc/11 §9 + §4.6 唯一权威口径逐字落地 + reports raw output 必含三层比对（误差 = 0）+ 单测覆盖 A/B 分流·负流水·test exclude·退款 refunded_time 归属·commission 取整 |
| R2 ⭐（外部前置）| 真实通道费 `fee_cent` 依赖 PAY-104 拉 fundflowbill；真实商户号未开通 → 真实笔费/真实流水比对做不了 | **推进姿态 = mock 全链路自测**（dev/staging）；真实笔费 + 微信商户后台流水比对列为外部前置风险，验收前与甲方拿真实商户对账单跑一遍；通道费率/分成 bp 走 `sys_config` 可调 |
| R3 | ADMIN-104 进「已发往中国」漏录快递公司/单号 | 表单 `cn_carrier_code`（9 项字典必选）+ `cn_tracking_no` 二者必填，否则提交 disabled（doc/10 §9.E5） |
| R4 | ADMIN-104 国内单号录错无法回滚 | 提供「改单号」二次入口 + 写 `gz_logistics_audit`（`carrier_update` 记 from/to）；**不禁止修改**（甲方运营反复修是常态，doc/10 §9.N9） |
| R5 | ADMIN-106 看板一屏 8+ 卡片串行查询慢 | 后端 1 个聚合接口一次性返所有卡片（不前端 8 次串行调）；复用 ADMIN-105 对账 service；V1.1 数据量小不加缓存 |
| R6 | ADMIN-108 回收站漏建/错建 entity_type（假设了不存在的表名） | §0 自检 **grep migration 目录确认真实表名**（如 `gz_bean_store`），只纳入实际建了的表；不假设 `gz_user`/`gz_news_article` 命名 |
| R7 | SnailJob 跑批误用 Quartz / Flyway INSERT sys_job → 启动 hard-fail | 跑批 = `@Component + @JobExecutor` 薄壳 + 可单测 service；模块 pom 显式加 `ruoyi-common-job`；任务名/CRON 写 reports 由人在控制台注册；**禁止** sys_job INSERT |
| R8 | 对账 A/B 业务线归类错 → 预购退款算到扭蛋 | 统一按 `gz_pay_transaction.business_type` 强分流（`preorder`/`gacha`，`test` exclude）；**禁止** business_line/biz_line/A·B 列；单测覆盖跨业务线退款归属 |
| R9 | `@InterceptorIgnore` 放开范围过大（误绕租户/SQL 注入拦截） | 仅放开逻辑删拦截（查/恢复 `del_flag=2`），租户线保持；mapper 方法级精确标注，不全局关 |

---

## 日终 closing 命令

```bash
cd doc/daily/D15
cat reports/*.md > summary.md
git add -A && git commit -m "D15: V1.1 收官 — 物流 2 态推进 ADMIN-104 + 对账中心 ⭐ ADMIN-105 + 看板 ADMIN-106 + 回收站 ADMIN-108（火花券 ADMIN-107 移 v2）"
# 写 D15/v1.1-integration-checklist.md（集成回归）
# V1.1 开发收官 → staging 部署 + 通知甲方进入客户验收周期（软期限 7/31）
# 不再排下一个开发日（D15 = V1.1 收官 = 全部开发期结束）；后续客户验收 revision 按需新建日号目录处理
```
