# GZ-BEAN-006 — mp 我的预约列表（4 状态 tab）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §关键页面 §我的预约列表
**关联拆解**: doc/02-需求拆解.md §2.3 第 356 行
**关联 mockup**: design/mockup/booking-list.html（仅布局参考；视觉以 C 设计系统为准，doc/13。页面用 Biz* 组件 + var(--c-*)，不直接撒 wd-*）
**关联 ADR**: —
**依赖**: GZ-BEAN-005

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §状态机（4 状态枚举 + UI 同义词 upcoming/used/cancelled/no_show） + §关键节点 N8 → 列表入口
- **字段表**：doc/11-字段权威表.md **§3.4 `gz_bean_booking`**（列表读取字段） + §A.3 状态字典编码（**关键：mockup 仅 3 状态视觉，PRD 4 状态 — 已裁定 V1.0 实现 4 状态，no_show 用默认灰 tag 占位**）
- **UI 参考**：doc/12 §MP-BEAN-LIST（`/pages/bean/my-list`，4 状态 tab + 详情 + 核销码）；mockup `booking-list.html` 仅作布局参考，视觉以 C 设计系统为准（doc/13）

## What

mp 端「我的预约」列表页：顶部 4 个 tab（待核销 / 已核销 / 已取消 / 已过期），按时间倒序展示卡片（门店 + 日期 + 时段 + 座位 + 状态 tag + 缩略 QR）；点击卡片跳 BEAN-005 详情页。从 MP-ME-HOME 九宫格"我的预约"或 BEAN-004 提交成功后跳入。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `pages/bean/my-list.vue` 路由 `/pages/bean/my-list`，顶部横向分类条（4 状态，选中态朱红填充 var(--c-red)，Biz* 组件实现不直接撒 wd-*）+ 下方 scroll-view 列表；默认 active "待核销" tab（pending）
- [ ] **AC 2**：调 `GET /app/gz/bean/booking/my-list?status=&pageNum=&pageSize=` 拉当前用户预约（后端按 user_id + status 过滤，分页默认 20 条，时间倒序 `ORDER BY create_time DESC`）
- [ ] **AC 3**：列表卡片：门店名 + 日期时段 + 座位编号 + 状态 tag（颜色按字典） + 缩略 QR（约 80px 见方，用于快速识别）；卡片点击跳 BEAN-005 `pages/bean/detail?id=`
- [ ] **AC 4**：pending tab 卡片右下角额外显示「取消预约」按钮（BEAN-007 实现按钮 click 逻辑，本 ticket 只渲染按钮 + 占位 click handler）；其他 3 tab 不显示该按钮
- [ ] **AC 5**：nav-bar 右上角「+ 新建」链接（跳 MP-BEAN-SELECT = BEAN-010 拼豆首页 → 选座）
- [ ] **AC 6**：空状态：当前 tab 无数据时显示插画 + 文案「暂无 XX 预约」 + 「立即预约」 CTA → BEAN-010 落地页
- [ ] **AC 7**：i18n 全覆盖（`bean.list.xxx`）；状态文案走 `gz_bean_booking_status` 字典

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/applet/GzBeanQueryMpController.java` 加 `getMyBookingList(status, pageQuery)` 方法
  - `service/IGzBeanBookingService.java` + impl 加 `pageMyBookings(userId, status, pageQuery)`
  - 不落新 DDL
- **小程序**：
  - `pages/bean/my-list.vue`（新建）
  - `api/gz-bean.ts` 加 `getMyBookingList(params)`
  - 复用 BEAN-005 的 `BizQrCode.vue` + `BizStatusTag.vue` 渲染缩略 QR 和状态 tag

## 备注

### 强约束

1. **后端必须按当前 user_id 过滤**（sa-token 取登录 userId），不能透传任意 userId
2. **状态枚举走字典**（`gz_bean_booking_status`），不在 mp 端硬编码 4 个 status string
3. **取消按钮逻辑在 BEAN-007**，本 ticket 只占位 + 跳转骨架（避免与 BEAN-007 出现职责重叠）

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | mockup booking-list.html 仅 3 状态 → no_show tab 视觉缺口 | doc/10 §3 状态机已裁定"V1.0 实现 4 状态，mockup 待 designer 补"，本 ticket no_show 用 BizTag 灰款（var(--c-ink-3)）；已切 C 系统，视觉以 doc/tokens.md + doc/13 为准 |
| R2 | 缩略 QR × 20 条卡片 × wxapi 渲染卡顿 | 列表卡片用文字 + 状态 tag 为主，QR 缩略图改为静态 icon（如盲盒 icon）替代；真实 QR 仅详情页渲染 |

---

## §revision（Kevin testing-human 后填，初始空）
