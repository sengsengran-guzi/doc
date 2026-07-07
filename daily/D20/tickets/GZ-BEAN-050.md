# GZ-BEAN-050 — 关闭重做（admin）：引导式关闭页 + 退休 seat_closure 页/menu

**优先级**: P1
**复杂度**: M
**关联 ADR**: doc/_adr/0018-pindou-group-booking-preassign-closure-rework.md §3
**依赖**: GZ-BEAN-049

---

## 必读权威文档

- **ADR**：doc/_adr/0018 §3
- **相关代码**：`plus-ui/src/views/gz-bean/seat-closure/index.vue`（退休）/ `slot-availability/index.vue`（余量页，并入或改造）/ `api/gz-bean/*`

## What

admin 关闭统一到一个引导式页：选桌型 → 选某天（默认今天）→ 自由选时间段 → 展示该时段各小时当前预约数量 → 输入关闭数量 →（可选）设为每周循环。同时下线按座位的 `seat-closure` 页 + 其 menu。

## AC（验收标准）

- [ ] AC1：引导式关闭页——① 桌型下拉；② 日期选择（默认今天）；③ 时间段选择（跨多个 1h 格，非单格）；④ 选定后展示区间内**各小时**的「已订 / 总量 / 已关」（调 049 预览接口）；⑤ 关闭数量输入 → 调 049 批量关闭接口。
- [ ] AC2：「设为每周循环」开关——开 → 提交 weekday（该星期每周生效）；关 → 提交 sessDate（仅当天）。
- [ ] AC3：退休 `seat-closure` 页——移除路由 / 侧边栏 menu（menu visible 置隐藏或删该 menu 记录，走 Flyway，注意 menu-id 不误删他人，memory `menu-id-collision`）；页面文件保留代码但不可达。
- [ ] AC4：已有关闭列表可查看 / 删除（沿用现有 slot-quota-close 列表能力）。
- [ ] 纯 admin ticket，无 mp AC N。

## Tech

- **Admin**：新建或改造 `slot-availability/index.vue` 为引导式关闭页；`api/gz-bean/slotQuotaClose.ts` 加 occupancy / batch 封装。
- **menu**：下线 seat-closure menu（Flyway 迁移，append-only，时间戳当下真实时间）。

## 备注

- 关闭前先看到各小时实占再决定关几个——这是本次简化的核心体验，别退回抽象规则表单。

---

## §revision（初始空）
