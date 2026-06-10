# GZ-COUPON-003 — mp 选券 + 我的券列表

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md 优惠券域
**关联拆解**: doc/02-需求拆解.md GZ-COUPON-003
**关联 mockup**: design/mockup/（C 日漫海报浓墨视觉参考，不强求逐像素）
**关联 ADR**: 无（券态权威 = doc/11 §11.2）
**依赖**: GZ-COUPON-002（D13，券态 service：unused/locked/used/expired 已落地）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §12.N3（选券接口 `usable?business=pindou&total_amount`）
- **字段表**：doc/11-字段权威表.md §11.2（券态机）+ §11.3（抵扣口径，前端展示实付）
- **UI 参考**：C 日漫海报浓墨 — doc/tokens.md + doc/13；只用 `src/components/biz/Biz*` + `var(--c-*)`

## What

mp 端「我的优惠券」列表（unused/used/expired 三 tab，入口在「我的」）+ 拼豆付款页**选券模块**（被 GZ-BEAN-015 消费）。新建 gz-coupon applet controller。

## AC（验收标准）

- [ ] **AC1 我的券列表**：mp 页 unused / used / expired 三 tab，展示券面额 / 适用范围 / 有效期；C 设计系统（Biz* 组件 + `var(--c-*)`，不直接撒 `<wd-*>`）。
- [ ] **AC2 选券模块**：仅展示 `unused + applicable_business=pindou + 未过期` 券；选中回传 couponId 给调用方（BEAN-015）；展示实付 = 单笔金额 − 券面额（下限 0，doc/11 §11.3）。
- [ ] **AC3 选券接口**：applet controller `GET /app/gz/coupon/usable?business=pindou&totalAmount=` 返用户可用券（unused + 适用 + 未过期）；`GET /app/gz/coupon/my?status=` 返我的券分态列表。id 全 string。
- [ ] **AC4 过期券二次校验**：选券提交时后端再校验券态（前端缓存兜底，过期券拦截提示）。
- [ ] **AC5 Tier 2 可达**：Kevin 从「我的」tab（已上线）点 N 次到达券列表页（列入「我的」页菜单项）；选券模块由 BEAN-015 集成（BEAN-015 卡负责）。
- [ ] **AC6 vitest unit**：券列表分态逻辑 + 可用券筛选逻辑（applicable + 未过期）单测。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-coupon/src/.../controller/applet/`（新建 applet controller，仿 gz-bean 的 `controller/applet/GzBeanBookingMpController`）；复用 COUPON-002 的券查询 service。
- **小程序**：`code/main/miniapp/src/pages/me/coupons.vue`（我的券列表，新建）+ 选券组件 `src/components/biz/BizCouponPicker.vue`（被 BEAN-015 消费）+ `src/api/coupon.ts`；「我的」页加券入口菜单项。
- **DDL**：无（纯查询 + mp 页）。

## 备注

- **串行批次**（COUPON-002 完工后派，不与第一波并行）— 无并行撞车风险，正常 install。
- mp 数字/金额：`type=digit` + 前端 parseFloat；id 全 string；路由用业务码不用 id。
- **不要 spawn kevin-qa**（子不能 spawn 孙；Tier 1B 主线程统一派）。写完 reports（含 §AI 测试段占位 + Tier 2 可达路径说明）即返回。
- mp ticket → 进 progress.md「人验」列待 Kevin 批量验。

---

## §revision（Kevin 批量人验后填，初始空）
