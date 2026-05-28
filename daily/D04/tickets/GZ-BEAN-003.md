# GZ-BEAN-003 — mp 时段 + 座位选择

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M4 §用户操作流程 步骤 3-5
**关联拆解**: doc/02-需求拆解.md §2.3 第 311 行
**关联 mockup**: design/mockup/booking-select.html（V1.0 设计冻结期：视觉参考，wot-design-uni 默认 + tokens.md brand-primary）
**关联 ADR**: —
**依赖**: GZ-BEAN-002

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §关键节点 步骤 3-5（选日期 → 选时段 → 选座位）+ §状态机（座位可用 / 已占用判定）
- **字段表**：doc/11-字段权威表.md §3.2 时段模板 + §3.3 座位 + **§3.4 `gz_bean_booking`**（消费方需了解预约表 schema 才能做"已占用"判定）+ §3.6 拼豆状态字段详细口径
- **UI 参考**（设计冻结期）：`booking-select.html` 视觉参考，**不强求逐像素还原**；座位用列表型（不是平面图）

## What

mp 端用户选日期（默认今天，前 7 天） → 看时段（按门店时段模板渲染，已满 / 未开放灰显） → 看座位列表（已占用灰显，可选高亮 brand-primary）；底部 fixed CTA 「下一步：填写信息」（暂不提交，BEAN-004 才提交）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `pages/bean/select.vue` 三层选择 UI（日期 / 时段 / 座位），从上到下垂直布局；fixed CTA 条吸底
- [ ] **AC 2**：日期选择器顶部水平滑动，默认今天高亮 brand-primary；展示今 + 6 天共 7 天；过去日期不显示
- [ ] **AC 3**：时段块按门店当日时段模板渲染（调 `GET /app/gz/bean/time-slot/by-date?storeId=&date=`）；后端返回 [{slot_start, slot_end, is_available: bool, available_seat_count, total_seat_count}]
- [ ] **AC 4**：选时段后展示该时段所有座位（调 `GET /app/gz/bean/seat/by-slot?storeId=&date=&slotStart=`）；后端返回 [{seat_id, seat_no, is_occupied: bool}]
- [ ] **AC 5**：座位 UI：列表型，每个座位卡片含编号 + 状态色（可选=brand-primary 边框 / 已占用=gray-300 灰显不可点 / 选中=brand-primary 实心）；座位停用（is_active=false）不显示
- [ ] **AC 6**：实时占用判定：后端 query gz_bean_booking 表，`status IN ('pending', 'used') AND date=? AND slot_start=? AND seat_id=?` 有记录则该座位 is_occupied=true
- [ ] **AC 7**：底部 fixed CTA「下一步」按钮 — 选座完成才高亮可点；点击跳转到 BEAN-004 提交确认页（参数 store_id + date + slot_start + seat_id 经 query string 传）
- [ ] **AC 8**：未登录用户进入此页 → 弹「登录后才能预约」（GZ-SYS-002 useAuth 复用）→ 登录后回到本页保留上下文
- [ ] **AC 9**：i18n key 全覆盖（`bean.select.xxx`）
- [ ] **AC 10**：单测可选；mp 端联调验：在 admin 端配座位 + 时段后，mp 端能渲染正确状态

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/applet/GzBeanQueryMpController.java`（mp 路径 `/app/gz/bean/time-slot` + `/app/gz/bean/seat`，查询接口）
  - `service/IGzBeanQueryService.java` + impl — 按 date + storeId 渲染时段（join 时段模板 + 已存在预约表统计占用）
  - 不落新 DDL（只查询）
- **小程序**：
  - `pages/bean/select.vue`（主页）
  - `components/biz/BizDatePicker.vue`（水平日期选择器）
  - `components/biz/BizTimeSlotGrid.vue`（时段块）
  - `components/biz/BizSeatList.vue`（座位列表）
  - `api/gz-bean.ts` 加 `getTimeSlotsByDate()` + `getSeatsBySlot()`
  - `composables/useBookingSelection.ts`（pinia store 临时存选中日期 / 时段 / 座位，BEAN-004 提交时消费）
- **测试**：admin 端配 1 门店 / 5 座位 / 3 时段 → mp 端开发者工具走一遍

## 备注

### 强约束

1. **是查询不是提交**：本 ticket 完全只读，所有 INSERT 在 BEAN-004
2. **实时占用查询性能**：用 join + GROUP BY（按 slot_start 聚合 count 已占用座位），不要 N+1 查询
3. **wot-design-uni 默认 + tokens.md**：座位卡片用 brand-primary token（不要硬编码 #色值）
4. **未登录拦截**：useNavGuard composable（D03 ADMIN-005 已建）自动拦截，本 ticket 不重写
5. **设计冻结期 mockup 仅参考结构**：座位卡片可以用 wd-button 或 wd-card 默认样式，不强求 mockup 圆角 / 间距

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 座位列表型而非平面图 | doc/02 §2.3 已锚定（"mockup 已定为列表型"）+ V1.0 仅 5-10 座位，列表足够 |
| D2 | 时段块用 grid 布局每行 2-3 个 | wot-design-uni grid + tokens.md spacing 默认 |
| D3 | 临时选中状态用 pinia store | 跨页面带状态（select → confirm → submit），用 query string 易丢；pinia 更清晰 |
| D4 | 实时占用查询每次进入都拉 | V1.0 流量小，不做客户端缓存；BEAN-004 提交时再次双查（防 stale）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 用户停留在选座页 30 秒后他人占了座 → 提交时失败 | BEAN-004 提交时 friendly 提示「座位已被占，请重选」+ 自动回退本页 |
| R2 | 后端 join 性能（座位 × 时段 × 预约）| V1.0 数据量极小（5 座 × 3 时段 × 7 天 = 105 行）；索引设计已覆盖（idx_store_active / idx_store_weekdays / 预约表唯一索引） |

---

## §revision（Kevin testing-human 后填，初始空）
