# D11（Kevin 口径 d10）— V1.1 收官：物流推进 + 对账中心 ⭐ + 看板扩展 + 软删恢复

> 日期：2026-06-19（周五）
> 阶段：V1.1 实施期 day 4 — **V1.1 最后一天 / 合同 §4.1 4% 分成兑现核心日 ⭐**
> 上一日：[D10](../D10/README.md) ｜ 下一日：— （V1.1 开发收官；6/22 起进入 staging 部署 + 客户验收周期，截止 7/31 软期限）

---

## 今日目标

- **主线**：V1.1 admin 收尾 + **对账中心立起来**（合同 §4.1 4% 分成兑现的核心数据来源）：
  1. 物流批次推进（GZ-ADMIN-104）— 甲方一键推进 7 节点 + 国内单号录入
  2. **对账中心 ⭐**（GZ-ADMIN-105）— GMV / 退款 / 通道费 / 实际到账四栏 + Excel 导出（合同 §4.1 + §4.2.1）
  3. 数据看板扩展（GZ-ADMIN-106）— V1.0 基础上叠加 V1.1 交易 / 扭蛋 / 物流指标
  4. ⚠️ 扭蛋火花券店（GZ-ADMIN-107）— **placeholder，本日不实施代码**（PRD §5.2 标"不做" / mockup 已存 — 待 Kevin × 甲方决策升 V1.1 或 v2 推迟）
  5. V1.0 软删除恢复机制（GZ-ADMIN-108）— 回收站 + 30 天定时归档

完工后甲方可以：
- 在 admin「物流」页一键把 N 个预购订单从"已下单 → 国内仓"或更后续节点推进，进入"国内派送"必须录快递单号
- 在 admin「对账中心」按月 / 任意周期拉取两条业务线（A 预定 / B 扭蛋）的 GMV / 退款 / 通道费 / 实际到账，Excel 导出对照微信商户后台流水比对
- 在 admin「数据看板」一屏看到 V1.1 完整交易盘面 + 待发货订单数提醒
- 在 admin「回收站」找回 30 天内误删的商品 / 文章 / 扭蛋 SKU

**V1.1 收官完成后整理 V1.1 集成回归 + 准备 6/22 起 staging 部署 + 客户验收。**

## Ticket 清单（5 个 / 4 个实做 + 1 placeholder）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-ADMIN-104 | 物流批次推进 | L | GZ-ADMIN-103 + GZ-USER-103 | pending |
| **GZ-ADMIN-105 ⭐** | **对账中心（4% 分成核心）** | **L** | GZ-ADMIN-103 | pending |
| GZ-ADMIN-106 | 数据看板扩展 | M | GZ-ADMIN-103 + GZ-ADMIN-105 | pending |
| ⚠️ GZ-ADMIN-107 | 扭蛋火花券店（placeholder） | M | GZ-GACHA-104 | **deferred (待甲方决策)** |
| GZ-ADMIN-108 | V1.0 软删除恢复机制 | S | GZ-ADMIN-101 + GZ-NEWS-003 | pending |

详见 `tickets/<TICKET-ID>.md`。

**依赖说明**：
- ADMIN-104 / ADMIN-105 / ADMIN-108 **可并行**（无相互依赖，仅依赖前序日已完工的 ticket）
- ADMIN-106 **必须等 ADMIN-105 完工后**再起（看板要消费对账聚合数据）
- ADMIN-107 ⚠️ **本日不实施**，仅产出任务卡占位 + 待办标注；PRD v1.0 5/31 签字会议时由 Kevin 与甲方过一遍决策

## 派单方式

```
开始 d10
```

主线程动作：
1. 读 D11/README.md + 依赖图
2. **第一波并行 spawn**：ADMIN-104 + ADMIN-105 ⭐ + ADMIN-108 三条线同时起
3. ADMIN-105 ✅ 后 spawn ADMIN-106
4. ADMIN-107 跳过实施，仅由主线程把任务卡 §revision 段留空交给 Kevin 5/31 会议带去对甲方
5. 4 ticket（104 / 105 / 106 / 108）全部 ✅ → Kevin testing-human 重点验 ADMIN-105 对账金额准确性 + 日终 closing + **整理 V1.1 集成回归 checklist**

## 今日特殊约束 ⭐

### ADMIN-105 对账中心是 4% 分成兑现核心（合同 §4.1）

- **doc/11 §4.6 4% 分成核心计算口径** 是本 ticket 唯一权威，AI 实施前必读全文
- **业务线 A、B 分别核算 + 不交叉冲抵**（合同 §4.1.2）：
  - 业务线 A = 预定货品 GMV（GZ-ORD 域）
  - 业务线 B = 扭蛋抽奖 GMV（GZ-GACHA 域）
  - 两条线各自计算 4% 分成，不互相冲抵（即 B 亏 A 不补）
- **实际到账 = GMV − 退款 − 通道费**（合同 §4.1）
  - GMV = SUM(已支付订单金额)，含退款前的总流水
  - 退款 = SUM(已退款金额)，按退款发生时点归到对应业务线（不按原订单归月）
  - 通道费 = 微信支付商户号扣的手续费（费率挂 `sys_config` `gz.pay.channel-rate`，V1.1 默认 0.6%）
- **季度结算锚点 3/6/9/12 月 15 日前**（合同 §4.1）— 对账中心需要支持"上个季度"快速筛选 + 导出，便于甲方按季度对账
- **Excel 导出必含字段**（合同 §4.2.1 强制）：
  - 每笔交易订单号（统一订单号，跨预购 / 扭蛋）
  - 金额 / 时间 / 状态（paid / refunded）/ 通道费明细
  - 给甲方"可一键复制到银行流水比对"的颗粒度（不要做透视表 / 不要合并单元格）
- **reports/<T>.md 必须含"对账数据 vs 微信商户后台流水比对" raw output**：
  - 取测试库一周数据 → 跑对账中心 GMV / 退款汇总 → 与微信商户后台沙箱流水对比（金额误差 = 0）
  - 比对失败 → 立刻 STOP 报 Kevin，不能 close ticket

### ADMIN-107 是 placeholder，本日不实施 ⚠️

- **PRD §5.2 明确"不做扭蛋积分 / 代币兑换"**，但 `design/mockup/gacha-spark-shop.html` 已存（早期 designer 出图未对齐 PRD）
- 本日仅产出 `tickets/GZ-ADMIN-107.md` 占位任务卡，AC 段写"本 ticket 暂不实施，等甲方 5/31 PRD v1.0 签字时与 Kevin 决策"
- Kevin 5/31 签字视频会议带这个 ticket 走（备选话术："mockup 早期画了但 PRD 没有，要不要塞进 V1.1？预计 +1.5 天工时 — 在月 40h 内还是推 v2？"）
- 甲方确认升 V1.1 → 本 ticket 转 D12（如新增）；甲方确认推 v2 → 本 ticket 标 `archived` + 关联 mockup 在 PRD 备注里加"v2 候选"标记

### ADMIN-104 物流批次推进

- **批次定义**（doc/10 §6 物流推进流）：
  - **自动归集**：按"商品 + 截止日"自动聚合（同一批预定的同款商品在同截止日下到货 → 同批次推进）
  - **手动多选**：admin 列表全选 / Shift 多选订单 → 手动建临时批次
- **节点推进**：一键把所有勾选订单的 logistics_node 字段推到下一个枚举值（doc/10 §6 7 节点状态机）
- **进入"国内派送"节点的强约束**：每单必须录入 `express_company` + `express_no`（admin 端弹批量编辑表格，留空不可提交）
- **推进操作写 sys_oper_log**（@Log 注解必加）
- **订阅消息**：如 USER-103 已实现节点推进订阅消息，ADMIN-104 推进后异步触发；如未实现 → 留 hook 但不阻塞

### ADMIN-106 看板新增卡片清单

- 今日订单数（按业务线 A / B 分两块）
- 今日 GMV（按业务线 A / B 分两块）
- 本月累计 GMV / 退款 / 实际到账（按业务线 A / B 分两块）
- 扭蛋本月抽数 + 平均出货价值
- 热销预购商品 Top 10
- **待发货订单数（提醒甲方推进物流，跨 logistics_node 状态聚合）**
- 数据源全部走 ADMIN-105 对账聚合表 + 现有 gz_order / gz_gacha_draw / gz_ord_item 实时查询，**不另建汇总表**（V1.1 数据量小，直接查可接受）

### ADMIN-108 软删除恢复机制

- **V1.0 所有业务表已用 `del_flag`（ruoyi 范式 0 正常 / 1 删除 / 2 stash 归档）** — 本 ticket 不动表结构，仅做"回收站"页 + 定时归档
- 回收站页：列出所有 del_flag='1' 的业务记录（商品 / 文章 / 扭蛋 SKU / 拼豆座位 / 门店等）按删除时间倒序，owner 可"恢复"（del_flag→0）或"立即归档"（del_flag→2）
- 定时归档：cron 每天凌晨扫 `del_flag='1' AND update_time < NOW() − INTERVAL 30 DAY` → 批量更新为 del_flag='2'（归档后回收站不再展示，仅 owner 查归档库可见）
- 归档库查询：复用回收站页 + 切 tab "已归档"，owner 权限

### 全局

- **设计冻结期纪律**：admin 全部走 plus-ui BizTable + Element Plus 默认 + ruoyi 自带 EasyExcel 导出（**不调样式**，6/10-6/14 风格统一窗口再调）
- **menu_id 段**（CLAUDE.md §6 #6）：ADMIN V1.1 11000-11099 / FINANCE 11100+（ADMIN-105 对账中心占 11100-11199）
- **包名**（CLAUDE.md §6 #4）：`gz.ord.*` / `gz.gacha.*` / `gz.user.*` / `gz.common.*`（ADMIN-105 / 106 跨域聚合 — 新建 `gz.common.finance.*` 装对账逻辑）
- **不动 ruoyi 自带模块**（CLAUDE.md §6 #1）
- **CRUD 不写新 Controller**（复用 ruoyi 范式）；ADMIN-105 因是新业务（对账聚合）必须写新 Controller，AC 段标注
- **不要 commit**：5 个 ticket（实质 4 个）全部完工 + Kevin testing-human 验过 ADMIN-105 金额准确性后再统一 commit

## V1.1 收官 — 集成回归 checklist（本日末 Kevin 整理）

收官完成后，Kevin 列一份 `D11/v1.1-integration-checklist.md`（本日 closing 时写，不在本 README 内）：

- [ ] V1.1 全链路 E2E：mp 端预购下单 → 支付 → 物流 7 节点推进 → 收货 → admin 对账中心看到对应 GMV / 通道费
- [ ] V1.1 全链路 E2E：mp 端扭蛋抽奖 → 支付 → 中奖记录 → 订单聚合页可见 → 对账中心计入业务线 B
- [ ] admin 数据看板今日 / 本月数据 vs 手动 SQL 汇总比对（误差 = 0）
- [ ] 对账中心 Excel 导出 vs 微信商户后台沙箱流水比对（误差 = 0）
- [ ] 软删恢复 + 30 天定时归档跑通一遍（手动 mock update_time 触发 cron）
- [ ] 物流推进推到"国内派送"节点 → 强制录单号校验起作用
- [ ] 跨域权限：staff 角色 ≠ owner 角色，仅 owner 可访问对账中心 + 软删恢复

集成回归全绿 → 6/22 起 staging 部署 + 通知甲方进入客户验收周期（截止 7/31 软期限）。

## 与昨日 reports 对账（D10）

D10 完工后预期产物（依据 02-需求拆解.md V1.1 排布推断）：
- ✅ ADMIN-103 订单聚合管理已就位（ADMIN-104 物流推进 + ADMIN-105 对账中心 + ADMIN-106 看板都消费它）
- ✅ ADMIN-101 / NEWS-003 软删除字段已就位（ADMIN-108 直接消费）
- ✅ USER-103 物流节点订阅消息（ADMIN-104 推进时触发；如 D10 未完成 → ADMIN-104 留 hook 不阻塞）
- ✅ GACHA-104 扭蛋出货 / 火花券积累（ADMIN-107 暂不实施 → 不阻塞）

## 完成判定（DoD）

- [ ] 4 个实做 ticket 任务卡 §revision 段空（ADMIN-104 / 105 / 106 / 108）
- [ ] ADMIN-107 任务卡产出 + 标 `deferred`，待 5/31 决策
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] **ADMIN-105 ⭐ reports 必须包含「对账数据 vs 微信商户后台流水比对」raw output**（误差 = 0）
- [ ] mvn install + plus-ui build:prod 两端全绿（本日无 mp 改动）
- [ ] testing-human.md 全勾：
  - admin 端 owner 在物流页一键把 5 个测试预购订单推进到"国内派送"，录单号后推到"国内仓"，操作日志有记录
  - admin 端 owner 在对账中心拉本月 → 业务线 A、B 分别核算 → Excel 导出打开核对每笔交易颗粒度
  - admin 端 owner 看数据看板，今日订单数 + 待发货订单数与手动查询一致
  - admin 端 owner 在回收站找回 1 个误删商品（恢复后 mp 端可见）+ mock update_time 触发归档 → 归档库可查
- [ ] V1.1 集成回归 checklist 全绿（见上节）
- [ ] V1.1 范围 ticket 全部 close（D08-D11 27 个 ticket / 含 ADMIN-107 deferred 26 个实施）

## 已知风险 ⭐

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | ADMIN-105 对账金额与微信商户后台对不上 → 4% 分成口径出错 → 合同纠纷 | doc/11 §4.6 权威口径 + reports raw output 必须含比对结果 + Kevin testing-human 必须手动用沙箱数据交叉验 |
| R2 ⭐ | 通道费率挂 `sys_config` 但实际微信费率随商户类型 / 行业浮动 | V1.1 用固定 0.6% + 后台 sys_config 可调；正式上线前甲方提供商户真实费率合同截图 → Kevin 改值 |
| R3 | ADMIN-104 批量推进 N 个订单事务过大 → 超时 | 单批 ≤ 50 单 / 大批量异步走 sys_job + 进度条；前端 Promise.all 分批调 |
| R4 | ADMIN-104 国内单号录错（甲方手动输错）无法回滚 | 提供"修改单号"二次入口 + 写 sys_oper_log 留痕；不要禁止修改（甲方运营反复修是常态） |
| R5 | ADMIN-106 看板聚合查询慢（一屏 8+ 卡片）→ admin 加载 > 3s | 后端给 1 个聚合接口一次性返所有卡片数据（不要前端 8 次串行调）；V1.1 数据量小不加缓存 |
| R6 | ADMIN-108 cron 跑归档时碰到 V1.0 占位表（gz_user / gz_news_article）del_flag 命名不一致 | 任务卡 §0 自检要求 AI 先 `SHOW COLUMNS` 检查所有 gz_* 表的 del_flag 字段，不一致直接 STOP 报 Kevin |
| R7 | ADMIN-107 5/31 甲方坚持升 V1.1 → 工时挤压 6/22 起 staging 期 | Kevin 5/31 会议直接说"升 V1.1 → V1.1 上线日推到 7/15"，让甲方在工期 vs 范围间二选一 |
| R8 | V1.1 集成回归发现跨域问题（预购订单的退款被算到扭蛋业务线 B） | ADMIN-105 对账聚合按 `order.biz_line` 字段强分流（在 gz_order 表 V1.1 已加），AC 单测覆盖跨业务线退款归属 |

---

## 日终 closing 命令

```bash
cd doc/daily/D11
cat reports/*.md > summary.md
git add -A && git commit -m "D11 (d10): V1.1 收官 ADMIN-104/105 ⭐/106/108 + 对账中心 + V1.1 集成回归"
# V1.1 收官 — 6/22 起进入 staging 部署 + 客户验收周期（截止 7/31 软期限）
# 不再写 D12/README.md（V1.1 开发期结束；后续按需新建 D12 处理客户验收 revision）
```
