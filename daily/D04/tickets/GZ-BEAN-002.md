# GZ-BEAN-002 — 座位主数据 + 时段模板配置

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M4 §关键字段 § Seat / TimeSlotTemplate + 后台座位/时段编辑
**关联拆解**: doc/02-需求拆解.md §2.3 第 297 行
**关联 mockup**: ⚠️ 缺口（待 designer 补 admin-booking-config.html）— V1.0 设计冻结期 admin 走 plus-ui 默认
**关联 ADR**: —
**依赖**: GZ-BEAN-001

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §前置依赖（座位 / 时段模板配置完整性是 mp 端可预约的前提）
- **字段表**：doc/11-字段权威表.md **§3.2 `gz_bean_time_slot_template`** + **§3.3 `gz_bean_seat`**（完整 DDL 来源）
- **UI 参考**（设计冻结期）：N/A（plus-ui 默认表格 + el-form）

## What

admin 端配置门店的座位列表（每个座位编号 + 是否启用）+ 时段模板（开始时间 / 结束时间 / 适用星期），支持按周批量配置 + 单座位停启切换；mp 端不直接消费本 ticket（BEAN-003 才用模板渲染时段）。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606011000__GZ-BEAN-002-create-seat-and-time-slot.sql` 落两张表：
  - `gz_bean_seat`（id / store_id / seat_no / is_active / + 公共字段）UNIQUE `(tenant_id, store_id, seat_no)` 索引 `idx_store_active`
  - `gz_bean_time_slot_template`（id / store_id / start_time / end_time / weekdays VARCHAR(20) 逗号分隔 1-7 / + 公共字段）UNIQUE `(tenant_id, store_id, start_time, end_time, weekdays)` 索引 `idx_store_weekdays`
- [ ] **AC 2**：admin 端「拼豆管理 → 座位 + 时段配置」页（menu_id 6011，perm `gz:bean:seat:edit` + `gz:bean:time-slot:edit`）
- [ ] **AC 3**：座位 tab — 列表 + 新建 + 编辑 + 停用（is_active=false）；批量「按编号自动生成 N 个座位」工具（N 1-30）
- [ ] **AC 4**：时段模板 tab — 列表 + 新建 + 编辑 + 删除；新建表单字段「开始时间 / 结束时间 / 适用星期（多选 1-7）」
- [ ] **AC 5**：admin 端「按周一次性配置」工具：选门店 + 选时段模板 + 选适用星期 → 一键 INSERT 多条 time_slot_template（避免逐条配）
- [ ] **AC 6**：写操作加 @Log；座位停用不影响已有预约（doc/10 §3 §业务规则）— 仅阻断 BEAN-003 选座 UI 显示该座位
- [ ] **AC 7**：种子数据可选（甲方业务上线前自己配；本 ticket 仅留接口 + UI）
- [ ] **AC 8**：单测 happy path（建座位 + 建时段）+ UNIQUE 拦截（同 store_id 同 seat_no 再加）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/GzBeanSeatController.java` + `controller/GzBeanTimeSlotTemplateController.java`（admin 路径分别 `/system/gz/bean/seat` / `.../time-slot`）
  - 对应 Entity / VO / BO / Mapper / Service / impl × 2
  - DDL × 2（建表 + 菜单）
- **Admin**：`views/gz-bean/config/index.vue`（tab 包两个子页 — 座位 + 时段）+ `api/gz-bean/seat.ts` + `api/gz-bean/time-slot.ts`
- **小程序**：本 ticket 不动 mp（BEAN-003 才消费）
- **测试**：mvn 单测 + admin 浏览器配 5 座位 + 3 个时段（周一到周五 14:00-16:00 / 周末 14:00-18:00 等）

## 备注

### 强约束

1. **weekdays 用 VARCHAR(20) 逗号分隔**而非 BIT 位运算 — doc/11 §3.2 已锚定（便于 SQL 查询 `FIND_IN_SET`）
2. **start_time / end_time 用 TIME 类型**（HH:MM:SS）— 不存日期，按日期 + 时段模板组合渲染
3. **UNIQUE 时段模板** `(tenant_id, store_id, start_time, end_time, weekdays)` 防同一门店同一适用范围重复时段
4. **座位停用不影响已有预约**（doc/10 §3 §业务规则）— BEAN-003 选座 UI 过滤 is_active=false 座位，已有 pending 预约的 booking 表通过 join 显示门店历史
5. **批量座位生成工具**：自动编号 `A01 / A02 / ...` 或允许用户自定义前缀；不要做复杂的座位平面图（V1.0 是列表型选座）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 时段模板不绑定座位 | 同一时段模板适用所有座位（5 座位 × 3 时段 = 15 预约位）。绑定座位会让配置爆炸（同时段同座位不同模板？无意义） |
| D2 | weekdays VARCHAR 而非 BIT | doc/11 §3.2 已锚定；SQL 查询 `FIND_IN_SET(DAYOFWEEK(date)-1, weekdays)` 直观 |
| D3 | 不支持「单日特例」（如假期临时关店）V1.0 | doc/02 §2.3 BEAN-002 AC 范围内不含；V1.1/v2 可扩展 `gz_bean_time_slot_override` 表 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | admin 时段模板配错（如周末忘了配）→ mp 端用户看到空可选时段 | BEAN-003 实施时友好提示「本门店暂无可预约时段」+ 联系客服 |
| R2 | 时段重叠（如 14-15 和 14:30-15:30）→ 业务不允许但 schema 不拦 | 应用层校验：admin 新建时段时检查重叠（query existing where start_time < new_end && end_time > new_start） |

---

## §revision（Kevin testing-human 后填，初始空）
