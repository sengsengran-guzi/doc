# GZ-BEAN-048 — 看板座位格两层（在座 + 待核销）+ 分层双栏格 UI

**优先级**: P0
**复杂度**: L
**关联 ADR**: doc/_adr/0018-pindou-group-booking-preassign-closure-rework.md §2
**关联 mockup**: design/mockup/_review/gz-bean-board-cell-compare.html（定稿 = 分层双栏格 + 空栏坍缩 + 左色棒/右上图标）
**依赖**: GZ-BEAN-047

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md（拼豆看板子流程）
- **字段表**：doc/11-字段权威表.md §gz_bean_booking
- **ADR**：doc/_adr/0018 §2「座位格 UI = 分层双栏格」
- **相关代码**：`GzBeanBookingServiceImpl.selectBoard()` / `pickCurrentBooking()` / `GzBeanBoardRowVO` / `plus-ui/src/views/gz-bean/board/index.vue`

## What

后端看板每座从「只返一张当前单」改为返 **current（在座 used）+ next（待核销 reserved）**两层；admin 看板座位格重做为**分层双栏格**（上=在座/放座、下=待核销/核销），空栏坍缩、左色棒+右上状态图标；顶部列表标题改「未排位客人」；核销待核销单直接用其已排座（不弹选座）。

## AC（验收标准）

- [ ] AC1：`GzBeanBoardRowVO` 增补 next 层字段（下一位 bookingNo / mobileSnapshot / slot / isFree / group 标签 / bookingId 等）；`selectBoard` 对每座算 current（used 覆盖当前）+ next（该座最近的 reserved 待核销单）。
- [ ] AC2：admin 座位格 = 上下两栏。上栏在座（倒计时/临近结束/超时 + 放座主 + 延时/改派次），下栏待核销（订单/手机/时段 + 核销主 + 取消排位次）。放座按钮在上、核销在下。
- [ ] AC3：空栏坍缩——只在座（无 next）→ 下栏收细条占位；只待核销（无 current）→ 上栏收细条；真两层才等高撑满。
- [ ] AC4：远距离辨识——左侧状态色棒（在座绿/临近黄/超时红/待核销蓝）+ 右上状态图标；修饰（免费/续坐/组·N人/备注）为小 chip 挂各自栏。
- [ ] AC5：顶部列表标题 `gzBeanBoard.pendingTitle` 改为「未排位客人」（i18n zh/en）。
- [ ] AC6：核销待核销单——从下栏「核销」直接调 `verify(bookingId, 该单已排 seatId)`，不弹选座弹窗。
- [ ] AC7：从下栏「取消排位」调 047 的 unassign，单回到「未排位客人」列表。
- [ ] 纯 admin ticket，无 mp AC N。

## Tech

- **后端**：`selectBoard` 每座聚合 current+next；`GzBeanBoardRowVO` 增字段；`pickCurrentBooking` 拆出 pickNextReserved。
- **Admin**：`board/index.vue` 座位格模板重写为分层双栏格；沿用现有 autoRefresh/倒计时/near_end 弹窗逻辑（memory `board-autorefresh-500-storm` 的节流/keep-alive 钩子不要回退）。
- 无新 DDL、无新 menu、无新权限。

## 备注

- 不逐像素还原 mockup，以 Element Plus 标准件（el-card 上下切 + el-tag + el-button）落地，视觉参考评审留档。
- 改 gz-bean 后 `mvn clean install` + restart。

---

## §revision（初始空）
