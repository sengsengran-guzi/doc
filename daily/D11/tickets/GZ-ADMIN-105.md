# GZ-ADMIN-105 ⭐ — 对账中心（合同 §4.1 4% 分成兑现核心）

**优先级**: P1
**复杂度**: L（V1.1 最高优先级 ticket — 合同核心；L 级思考密度，禁止快速过 §0 自检；reports 必须含微信沙箱比对 raw output）
**关联 PRD**: doc/02-prd.md M7.8 对账中心 + 合同 §4.1 + §4.2
**关联拆解**: doc/02-需求拆解.md §3.5 第 965 行
**关联 mockup**: ⚠️ 缺口（admin-finance.html 待补；设计冻结期改用 plus-ui BizTable + el-statistic + el-tabs + el-date-picker 默认 + ruoyi EasyExcel）
**关联 ADR**: —（如通道费率挂哪一层 / 跨业务线退款归属判定遇到分歧 → 新建 ADR）
**依赖**: GZ-ADMIN-103（订单聚合管理）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 反复读）

- **字段表**：doc/11-字段权威表.md
  - **§4.6 4% 分成核心计算口径**（本 ticket 唯一权威 — 全文必读）：
    - 公式：实际到账 = GMV − 退款 − 通道费
    - 业务线 A、B 分别核算，不交叉冲抵
    - 季度结算锚点 3/6/9/12 月 15 日前
  - §4.x `gz_order` 表 `biz_line` 字段（A/B 业务线枚举 — 跨业务线退款归属判定锚定）
  - §4.x `gz_order` 表 `paid_amount` / `refund_amount` / `channel_fee` 字段
  - §4.x `gz_pay_transaction` 流水表（如已建，单笔交易颗粒度）
- **业务流**：doc/10-业务流权威图.md
  - §8 对账流（如有；本 ticket 实施时如发现 doc/10 缺 §8 → 优先回补 doc/10 §8 再写代码，9.5 复盘优先级 §1）
- **合同**：[doc/03-contract.md](../../../03-contract.md) §4.1（4% 分成口径 + 业务线独立核算 + 季度结算）+ §4.2.1（Excel 导出必含字段）
- **UI 参考**（设计冻结期）：admin ticket — **N/A**（plus-ui BizTable + el-statistic 四栏数字卡片 + el-tabs 业务线 A/B 切换 + el-date-picker-range 周期筛选）

## What

admin 端「财务管理 → 对账中心」页 — 甲方按业务线 A（预定）/ B（扭蛋）分别核算当月或任意周期的 GMV / 退款 / 通道费 / 实际到账，Excel 导出明细给甲方对照微信商户后台流水比对，支撑合同 §4.1 4% 分成季度结算。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606191200__GZ-ADMIN-105-finance-and-menu.sql`：
  - 建对账聚合视图 `v_gz_finance_daily`（按 tenant_id + biz_line + 日期 维度，列：GMV / refund_amount / channel_fee / net_amount / order_count）
    - 视图 source = `gz_order` 表过滤 status IN ('paid','partial_refund','full_refund') + GROUP BY
    - 视图实时计算（V1.1 数据量小不预聚合；后续 v2 数据量大可换物化表）
  - 插入对账中心菜单：menu_id 11100（FINANCE 段 11100+），parent 取「财务管理」目录（如不存在则同 DDL 插入目录 menu_id 11100）
  - 插入 sys_config：
    - `gz.pay.channel-rate-default` = `0.006`（默认通道费率 0.6%，admin 可调）
    - `gz.finance.reconcile.quarter-anchor-day` = `15`（季度锚点日，写死 15 但放配置便于调整）
- [ ] **AC 2**：admin 端 `views/gz-common/finance/reconcile.vue` 对账中心页：
  - 顶部 **el-tabs**：业务线 A（预定）/ 业务线 B（扭蛋）/ 合计（仅展示，无 4% 分成意义）
  - 顶部 **筛选区**：el-date-picker-range + 快捷按钮（今日 / 本周 / 本月 / 上月 / 本季度 / 上季度 / 自定义）
  - 中部 **四栏 el-statistic 卡片**：
    - GMV（含税总流水）
    - 退款（含税总退款）
    - 通道费（基于实际到账金额 × 费率）
    - **实际到账 = GMV − 退款 − 通道费**（高亮加粗，绿色字号 28px）
  - 中部 **4% 分成展示**（仅业务线 A、B tab 显示，"合计" tab 不显示）：
    - "应付甲方分成 = 实际到账 × 4%"（黄色高亮卡片）
    - 下方小字注释："合同 §4.1.2 业务线独立核算 / 季度结算 3/6/9/12 月 15 日前"
  - 下部 **明细表**（BizTable，分页 50/页）：
    - 列：交易时间 / 统一订单号 / 业务线 / 商品名 / 客户 / 金额 / 状态 / 通道费 / 实际到账
    - 状态：paid（绿）/ partial_refund（橙）/ full_refund（红）
- [ ] **AC 3**：4% 分成计算口径（doc/11 §4.6 权威）：
  - **业务线 A、B 分别核算**（gz_order.biz_line = 'A' 或 'B' 严格分流）
  - **不交叉冲抵**：业务线 A 实际到账即便为负（极端场景 退款 + 通道费 > GMV）不能用业务线 B 的盈余补偿（即各自独立算 4%，亏的那条线 4% = 0，不要算负数）
  - **退款归属**：按退款发生时点归到对应业务线（不按原订单时点归月），即 6/19 退 5/30 的预购订单 → 退款记 6/19 业务线 A
  - **通道费**：基于**实际到账金额**（即已扣退款后的净流水）× 费率（默认 0.6%，挂 sys_config）
    - 注意：微信商户实际是按"成功支付笔数 × 笔费率"扣，本 V1.1 简化用"净流水 × 比例费率"近似（合同 §4.1 注解未要求颗粒度，6/22 staging 沙箱跑通后如甲方反对可改 ADR）
- [ ] **AC 4**：Excel 导出（合同 §4.2.1 强制字段）：
  - 用 ruoyi 自带 EasyExcel + @ExcelProperty 注解
  - 文件名：`对账中心_业务线A_2026-06.xlsx`（含 tab 名 + 周期）
  - 表头：交易时间 / 统一订单号 / 业务线 / 商品名 / 客户 / 金额 / 状态 / 通道费 / 实际到账 / 备注
  - **颗粒度强约束**：每笔交易一行（不做透视 / 不合并单元格 / 不做小计行）— 让甲方可一键复制到银行流水 Excel 比对
  - 末尾**总计行**（合计 GMV / 退款 / 通道费 / 实际到账 / 4% 分成）— 加粗背景灰色
  - 业务线 A、B 各自一份导出按钮（不要合并到一个 sheet）
- [ ] **AC 5**：季度结算快捷入口：
  - 周期筛选快捷按钮"上季度"自动算上一自然季度（如 6/19 → 2026 Q1 = 1/1-3/31）
  - 提示文案："合同 §4.1.2 季度结算锚点 3/6/9/12 月 15 日前 → 下次结算应在 7/15 前完成"（动态算锚点日）
- [ ] **AC 6**：权限：
  - 对账中心仅 **owner 角色**可见（perm `gz:finance:reconcile`）
  - staff 角色访问 → 403 + 跳转 admin 首页 toast"无权限"
- [ ] **AC 7**：Controller 写操作 @Log 注解：
  - 导出 Excel → 写 sys_oper_log（业务类型 EXPORT，业务标题"对账中心 Excel 导出 [业务线] [周期]"）
  - 查询不写日志（@Log 仅写写操作 / 敏感读）
- [ ] **AC 8**：单测覆盖：
  - happy path：业务线 A 当月聚合金额计算正确（mock gz_order 数据，5 单 paid + 1 单 partial_refund + 1 单 full_refund → 验 GMV / refund / 通道费 / 实际到账 / 4% 分成）
  - 业务线独立：业务线 A 实际到账 = -100（极端场景）→ 4% 分成 = 0（不算负数 / 不用业务线 B 补）
  - 跨业务线退款归属：6/19 退 5/30 业务线 A 订单 → 6/19 业务线 A 退款列计入
  - 通道费率 sys_config 改 0.6% → 0.8% → 通道费重新计算正确
  - 季度锚点：6/19 → "上季度"返回 2026-01-01 ~ 2026-03-31
  - 共 5 个测试方法，全部 raw assertion
- [ ] **AC 9** ⭐：**reports 必须包含「对账数据 vs 微信商户后台沙箱流水比对」raw output**：
  - 取测试库一周 paid + refund 数据 → 跑对账中心 API → 与微信商户后台沙箱（pay.weixin.qq.com 沙箱环境）流水汇总比对
  - 期望误差 = 0；若有误差 → 立刻 STOP 报 Kevin，不能 close ticket
  - raw output 含：
    - 测试库 SQL `SELECT SUM(paid_amount), SUM(refund_amount) FROM gz_order WHERE biz_line='A' AND DATE BETWEEN ...`
    - 对账中心 API JSON 响应
    - 微信商户沙箱日终对账文件下载（截图 / 文本）
    - 三者数值对齐表
- [ ] **AC 10**：菜单挂载 + 文档：reports 末尾必引 doc/11 §4.6 原文片段（"实际到账 = GMV − 退款 − 通道费"完整段）证明实现一致

## Tech（端 + 范围）

- **后端**：新建包 `org.dromara.gz.common.finance.*`（跨域聚合，挂 ruoyi-gz-common 模块）
  - `controller/admin/GzFinanceReconcileAdminController.java`（admin 路径 `/admin/gz/common/finance/reconcile`）+ 接口：
    - `GET /summary`（params: biz_line + start_date + end_date → 返四栏聚合数 + 4% 分成）
    - `GET /detail`（params: 同上 + page → 返明细表分页）
    - `GET /export`（params: 同上 → 返 Excel 流，response.setContentType("application/vnd.ms-excel")）
    - `GET /quarter/anchor`（当前 / 上 / 下 季度锚点日，纯函数计算）
  - `service/IGzFinanceReconcileService.java` + impl
  - `service/internal/FinanceCalculator.java`（4% 分成 + 通道费 + 实际到账纯函数计算逻辑，独立 Bean 便于单测）
  - `domain/vo/FinanceSummaryVO.java`（聚合返回）
  - `domain/vo/FinanceDetailRowVO.java`（明细行，带 @ExcelProperty 注解供导出复用）
  - `mapper/GzFinanceMapper.java`（指向 v_gz_finance_daily 视图）
  - DDL × 1（视图 + 菜单 + sys_config）
- **Admin 前端**：`code/main/plus-ui/`
  - `views/gz-common/finance/reconcile.vue` 主页（el-tabs + el-statistic 卡片 + BizTable）
  - `views/gz-common/finance/components/QuarterTipBanner.vue`（季度锚点提示横幅）
  - `api/gz-common/finance.ts` 四个 API 封装
  - i18n：`zh_CN.ts` / `en_US.ts` 加 finance.* 段（实际到账 / 业务线 / 4% 分成 / 通道费 等术语）
- **测试**：mvn 单测 + 浏览器实操（5 单测试数据走通流程 + Excel 下载 + 沙箱比对）+ Kevin testing-human 重点验金额

## 备注

### 强约束 ★

1. **doc/11 §4.6 是唯一权威**（CLAUDE.md §6 #5 + 9.5 复盘优先级 §1）— 实施前 AI 必须读全文 + reports 末尾引原文片段
2. **业务线独立 + 不交叉冲抵**（合同 §4.1.2）— 任一线亏算 4% = 0，不要算负数 / 不用另一线补
3. **退款按时点归当期**（不按原订单期）— 退款发生在 6/19 → 计入 6/19 当期，不退回 5 月
4. **Excel 导出颗粒度** = 每笔交易一行（合同 §4.2.1 给甲方"可一键复制到银行流水比对"的颗粒度，**不要做透视 / 不要合并单元格 / 不要小计行**），末尾总计行加粗灰底
5. **owner 角色权限**（staff 无权访问）— 财务数据敏感
6. **不动微信支付商户号配置**（合同 §2.1 商户号挂甲方公司）— 本 ticket 只读交易数据
7. **菜单挂在 FINANCE 段 11100+**（CLAUDE.md §6 #6）— 不混到 ADMIN 段

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 `v_gz_finance_daily` 视图实时聚合，不建物化表 | V1.1 数据量小（预计 < 1000 单/月），视图实时查询 < 500ms；预聚合引入同步成本 + delete/refund 时反聚合复杂度 |
| D2 | 4% 分成在前端展示，不存 DB | 分成不是事务数据（只读，每次结算时算）；存 DB 引入"结算后是否锁定"复杂度，本 V1.1 不做 |
| D3 | 通道费按"实际到账金额 × 费率"近似，不按真实笔费率 | 微信真实费率按笔扣，本 V1.1 颗粒度不够（每笔 paid_amount 已含税但未拆通道费）；合同 §4.1 注解未要求笔级颗粒度 → 6/22 staging 跑通如甲方反对可改 ADR-V1.1-XX |
| D4 | Excel 导出用 ruoyi 自带 EasyExcel（不引新依赖） | 设计冻结期 + CLAUDE.md §6 #8 不引未澄清新依赖 |
| D5 | 跨业务线退款归属判定锚定 gz_order.biz_line 字段 | 该字段下单时即定 + 不可变；退款时按订单的 biz_line 归属，简洁无歧义 |
| D6 | 季度锚点纯函数计算（不存 DB） | 锚点是日历常量（3/6/9/12 月 15 日），动态算更简单 |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | 对账金额与微信商户后台对不上 → 4% 分成口径出错 → 合同纠纷 | AC 9 强制 reports 含沙箱比对 raw output + Kevin testing-human 手动用沙箱数据交叉验 + doc/11 §4.6 引原文片段证明一致 |
| R2 ⭐ | 通道费率近似（D3 决策）甲方不接受 | 6/22 staging 跑通后立刻 demo 给甲方 → 接受则定调，不接受走 ADR-V1.1-XX 改为按笔费率（需 gz_pay_transaction 表补 channel_fee 字段，工作量 +1 天） |
| R3 | 退款归属判定边界（5/30 paid + 6/19 partial_refund 5 月归 GMV 但 6 月归 refund，业务线 A 6 月实际到账可能为负）| 这是设计意图（doc/11 §4.6 锚定），UI 上极端负数到账时按 D2 决策 → 4% = 0；季度结算时正负相抵问题不存在（业务线独立） |
| R4 | Excel 导出大数据量（> 10000 行）OOM | EasyExcel 是流式写不会 OOM；但前端下载体验差 → V1.1 暂不限行数，如压测发现 > 30s 加进度条 |
| R5 | sys_config 通道费率被误改 | UI 不暴露此配置入口（仅 DBA 改）；后期如要给甲方改入口需 ADR |
| R6 | v_gz_finance_daily 视图 JOIN 慢（gz_order × gz_ord_item × gz_gacha_draw） | 视图避免 JOIN 大表 — 仅聚合 gz_order 单表（已含 paid_amount / refund_amount / biz_line / channel_fee 冗余字段）；如 channel_fee 字段无 → 本 ticket DDL 加（V202606191200__... + ALTER TABLE gz_order ADD COLUMN channel_fee）|
| R7 | "合计" tab 4% 分成歧义（业务线 A + B 合计的 4% ≠ A 的 4% + B 的 4%）| AC 2 明确"合计" tab **不显示 4% 分成**，只显示 GMV / 退款 / 通道费 / 实际到账 4 个聚合数；分成只在 A、B tab 显示 |

### ADR 候选（如本日实施时遇到分歧）

- **ADR-V1.1-FN-01**：通道费颗粒度（净流水 × 比例 vs 笔费率）— 默认 D3 净流水 × 比例；如甲方 6/22 demo 反对则切笔费率
- **ADR-V1.1-FN-02**：4% 分成是否存 DB 锁定（结算后不可改）— 默认 D2 不存；如甲方要求历史结算金额冻结则升级

---

## §revision（Kevin testing-human 后填，初始空）
