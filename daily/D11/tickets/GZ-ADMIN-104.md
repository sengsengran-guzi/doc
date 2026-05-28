# GZ-ADMIN-104 — 物流批次推进

**优先级**: P1
**复杂度**: L（V1.1 admin 域复杂 ticket — 批次定义 + 批量事务 + 强制录单号 + 操作日志）
**关联 PRD**: doc/02-prd.md M5 §物流推进方式 + M7.4 物流管理
**关联拆解**: doc/02-需求拆解.md §3.5 第 950 行
**关联 mockup**: ⚠️ 缺口（admin-logistics.html 待补；设计冻结期改用 plus-ui BizTable + el-form 默认 + el-dialog 批量编辑表格）
**关联 ADR**: —（如批量事务策略遇到分歧可新建 ADR）
**依赖**: GZ-ADMIN-103（订单聚合管理）+ GZ-USER-103（物流节点订阅消息；如未完工本 ticket 留 hook 不阻塞）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md
  - **§6 物流推进流**（7 节点状态机 — 本 ticket 核心锚定）
  - §6 §批次定义 段（自动归集口径 / 手动多选口径）
  - §6 §强约束段（进入"国内派送"必录单号 / 节点不可逆）
  - §6 §异常分支（甲方录错单号修正 / 单批 > 50 单异步走法）
- **字段表**：doc/11-字段权威表.md
  - §5.x `gz_ord_order` 表 `logistics_node` 字段 enum 定义（7 节点）
  - §5.x `gz_ord_order` 表 `express_company` + `express_no` 字段
  - §5.x `gz_logistics_log` 物流推进日志表（如已建）/ 否则本 ticket 不新建（走 sys_oper_log）
- **UI 参考**（设计冻结期）：admin ticket — **N/A**（plus-ui BizTable + el-table-column type="selection" + el-dialog 批量录单号表单 + el-button-group 节点推进按钮）

## What

admin 端「订单管理 → 物流推进」页 — 甲方按批次（自动归集 / 手动多选）一键把 N 个预购订单从当前节点推进到下一节点，进入"国内派送"节点时强制每单录入快递公司 + 单号，推进操作写日志。

## AC（验收标准）

- [ ] **AC 1**：admin 端 `views/gz-ord/logistics/index.vue` 列表页（plus-ui BizTable，支持按 logistics_node / 商品 / 截止日 / 客户筛 + 分页 + 多选）
  - 左侧 sidebar：节点分布卡片（7 节点各显示订单数 — 点击筛选）
  - 主表：勾选框 / 订单号 / 商品名 / 数量 / 客户 / 当前节点 / 截止日 / 操作列
- [ ] **AC 2**：批次定义两种方式：
  - **自动归集模式**：admin 顶部 tab "按批次推进" → 后端按 `(sku_id, expected_arrival_date)` 自动 GROUP BY → 列出"批次卡片"（含商品 + 截止日 + 订单数 + 当前节点）→ 点卡片选中该批次全部订单
  - **手动多选模式**：admin 顶部 tab "手动多选" → 主表显示订单列表 → 勾选多个订单（不限商品 / 截止日）→ 顶部"已选 N 单"显示
- [ ] **AC 3**：一键推进按钮逻辑：
  - 顶部"推进到下一节点"按钮 → 弹 el-dialog 二次确认（列出当前所选订单 + 当前节点 + 目标节点）
  - 目标节点 = 当前节点 + 1（按 doc/10 §6 7 节点 enum 序）
  - 所选订单若处于不同节点 → 按钮 disable + tooltip"请仅选择同节点订单"
  - 节点不可逆（doc/10 §6 强约束）— 后端校验 target_node > current_node，否则 400
- [ ] **AC 4**：进入"国内派送"节点的强校验：
  - 目标节点 = `domestic_shipping`（国内派送）→ el-dialog 不是简单确认而是**批量录单号表格**（el-table，每行：订单号 / 商品 / 快递公司下拉 / 单号 input）
  - 快递公司下拉走 sys_dict_data `gz_express_company`（顺丰 / 京东 / 中通 / 圆通 / 韵达 / 其他）
  - 任一单号留空 → 提交按钮 disable + 行高亮红框
  - 全部填完 → 提交时后端事务内 UPDATE 每单的 logistics_node + express_company + express_no
- [ ] **AC 5**：批量事务策略（doc/10 §6 §异常分支）：
  - 单批 ≤ 50 单：同步事务 + 进度条
  - 单批 > 50 单：拒绝同步提交，提示"请拆分为 ≤ 50 单 / 一批"（V1.1 不做异步 job，简化）
  - 事务中任一单更新失败 → 整批 rollback + toast 错误明细
- [ ] **AC 6**：推进操作写 sys_oper_log（@Log 注解）：
  - 业务标题：`物流批次推进 [批次定义] [N 单] [from→to]`
  - 业务类型：`UPDATE`
  - 操作人：当前登录 admin
- [ ] **AC 7**：订阅消息 hook（如 USER-103 已实现）：
  - 推进成功后异步 publish `LogisticsNodeChangedEvent`（包 order_ids + new_node + timestamp）
  - USER-103 监听该事件 → 调微信订阅消息 API 通知 C 端用户
  - USER-103 未完工 → ApplicationEventPublisher 调用保留但 listener 暂无人接（不报错）
- [ ] **AC 8**：单号修正二级入口（R4 缓解）：
  - 单订单详情页（GZ-ADMIN-103 已建）补"修改快递单号"按钮（owner 权限）→ 弹简单 el-form 改 express_company + express_no → 写 sys_oper_log
- [ ] **AC 9**：单测覆盖：
  - happy path：批量推进 5 单 from `paid` to `domestic_warehouse`（mock DB）
  - 进入 `domestic_shipping` 节点 + 任一单号留空 → 校验失败 returns 400
  - 节点不可逆：尝试 target_node < current_node → 校验失败 returns 400
  - 不同节点订单混选 → 校验失败 returns 400
  - 单批 51 单 → 校验失败 returns 400
  - 共 5 个测试方法，全部 raw assertion
- [ ] **AC 10**：所有写操作加 @Log；新建菜单 menu_id 11005-11009 段（ADMIN V1.1 11000-11099）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`（物流主域）
  - `controller/admin/GzLogisticsAdminController.java`（admin 路径 `/admin/gz/ord/logistics`）+ 接口：
    - `GET /batches/auto`（自动归集查询，按 sku_id + expected_arrival_date GROUP BY）
    - `POST /advance`（批量推进 — body: order_ids[] + target_node + express_info[]?）
    - `PUT /express/{order_id}`（单单单号修正）
  - `service/IGzLogisticsService.java` + impl
  - `service/internal/LogisticsAdvanceValidator.java`（节点不可逆 / 同节点 / ≤ 50 单 / 国内派送录单号 校验集中处）
  - `domain/event/LogisticsNodeChangedEvent.java`（领域事件）
  - DDL × 1（`V202606191100__GZ-ADMIN-104-menu-and-dict.sql`）：插入「订单管理 → 物流推进」菜单（menu_id 11005）+ sys_dict_data `gz_express_company` 6 项
- **Admin 前端**：`code/main/plus-ui/`
  - `views/gz-ord/logistics/index.vue` 主列表 + 左侧节点 sidebar + 顶部 tab
  - `views/gz-ord/logistics/components/BatchAdvanceDialog.vue`（普通节点推进 dialog）
  - `views/gz-ord/logistics/components/DomesticShippingDialog.vue`（国内派送强制录单号 dialog，含 el-table 编辑表格）
  - `views/gz-ord/logistics/components/ExpressEditDialog.vue`（单单单号修正）
  - `api/gz-ord/logistics.ts` 三个 API 封装
- **测试**：mvn 单测 + 浏览器实操：自动归集 → 批量推进 5 单 → 进入国内派送录单号 → 数据库 verify

## 备注

### 强约束

1. **节点不可逆**（doc/10 §6 §强约束）— 即便 owner 也不能回退节点（业务上节点回退引发对账混乱）；如确需回退走 ADR 流程
2. **进入"国内派送"必录单号**（合同 §2.3 + doc/10 §6）— 无单号不可推进
3. **国内物流仅展示甲方录入单号**（合同 §2.3）— 后端不调任何快递查询 API（不抓物流轨迹，C 端用户复制单号自查）
4. **跨境物流甲方手动 7 节点推进**（合同 §2.3 + doc/10 §6）— 不自动抓海外仓 / 国际段轨迹
5. **批量事务 ≤ 50 单** — 超过强制拆分（不在 V1.1 引入异步 job 框架）
6. **不动 ruoyi 自带模块**（CLAUDE.md §6 #1）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 自动归集按 `(sku_id, expected_arrival_date)` GROUP BY，不存独立批次表 | V1.1 数据量小，运行时查询足够；建批次表引入额外同步成本 |
| D2 | 单批 ≤ 50 单 + 同步事务（不引入异步 job） | 简化 V1.1 / 50 单同步事务实测 < 2s 可接受 / 异步 job 引入复杂度（进度条 / 失败重试 / 状态查询）不划算 |
| D3 | 节点推进用领域事件 LogisticsNodeChangedEvent | 解耦 USER-103 订阅消息 + ADMIN-105 对账触发（如未来需要按节点流转记账） |
| D4 | 国内派送 dialog 用 el-table 编辑表格而非循环 el-form | 用户体验：5 单一屏看完 + tab 切换填单号比逐表单切换快 |
| D5 | 修改单号入口在订单详情页，不在物流推进页 | 物流推进页是"批量操作"思维，单号修正是"单据修正"思维，UX 分离更清晰 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 批量推进 50 单事务卡 DB 写锁 | 实测 < 2s 可接受；如压测发现 > 5s → 切批次 25 单 |
| R2 | 甲方录错单号 | AC 8 提供"修改单号"二级入口 + 写 sys_oper_log 留痕，不要禁止修改 |
| R3 | sys_dict_data `gz_express_company` 6 项可能不够（甲方用顺心捷达等小众快递）| 下拉提供"其他"选项 → 弹文本输入快递公司名（落 `gz_order.express_company_custom` 字段，本 ticket 加字段）|
| R4 | 节点不可逆 + 甲方误操作推进了不该推进的订单 | 详情页加"误推进申诉" hook → 走 ADR 流程不在本 ticket 处理 |
| R5 | 自动归集查询慢（订单表大）| GROUP BY (sku_id, expected_arrival_date) 加复合索引 `idx_sku_arrival_node`（DDL 内加）|
| R6 | LogisticsNodeChangedEvent 异步发布失败影响推进事务 | 用 Spring `ApplicationEventPublisher.publishEvent` + @TransactionalEventListener(phase=AFTER_COMMIT) — 事件失败不影响推进事务 |

### ADR 候选

- **ADR-V1.1-XX**：是否引入异步批量推进 job（如 V1.1 上线后甲方反复反馈"50 单不够" → 升级评估）

---

## §revision（Kevin testing-human 后填，初始空）
