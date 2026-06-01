# GZ-BEAN-011 — mp 扫码核销（wx.scanCode + 复用后端 verify）

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M4 拼豆预约（到店扫码核销）/ M7.5 预约管理
**关联 ADR**: doc/_adr/0004-mp-admin-permission-foundation.md（§决策 2）
**依赖**: GZ-SYS-007（mp 权限底座）/ GZ-BEAN-008（后端 verify 逻辑，复用）/ **GZ-BEAN-012（顾客二维码渲染 —— 真机扫码闭环的被扫端）**

> **实施状态（2026-06-01）**：核销**店员端** AC1-AC6 已实现 + 自测通过（见 [reports/GZ-BEAN-011.md](../reports/GZ-BEAN-011.md)）。
> ⚠️ **真机闭环未通**：被扫的顾客二维码当前是降级文本，店员真机扫不到东西 → 必须 **GZ-BEAN-012** 把顾客码渲染成真二维码后，整个 mp 扫码核销才真机可用。本批次两者一起做完。

---

## 必读权威文档

- **业务流**：doc/10 §3 拼豆预约（N8-N9 核销：扫码 → 验签 → pending→used）
- **字段表**：doc/11 §3.4 gz_bean_booking（status / verify_code / qr_payload）
- **UI 参考**：mp 个人中心管理区「核销」+ 扫码结果页（`design/mockup/`，视觉参考）

## What

把扫码核销从 admin 网页搬到 mp：店员在个人中心「门店管理」区点「核销」→ `wx.scanCode` 扫顾客预约码 → 调 mp 核销端点（复用后端 `GzBeanBookingServiceImpl` 验签 + 标 used 逻辑）。admin 手动核销保留作兜底。

## AC（验收标准）—— 已实现

- [x] AC 1：mp 端点 `POST /app/gz/bean/booking/verify-scan`，`@SaCheckPermission("gz:bean:booking:verify")`，**复用** service（解析 `"BK\|{bookingNo}\|{verifyCode}"` → `QrCodeSigner` 验签 → pending→used），不复制逻辑。
- [x] AC 2：mp 扫码页 `wx.scanCode` 拿码 → 调端点 → 成功提示。
- [x] AC 3：异常分支提示：已核销/已取消/已过期/无效码（4007-4010）。
- [x] AC 4：纯顾客无「核销」入口；直接调端点 403。
- [x] AC 5：核销写操作日志（`@Log`）。
- [x] AC 6：**Tier 2 入口可达** — 绑定店员账号登 mp → 门店管理 → 核销。

## Tech（端 + 范围）

- **后端**：`ruoyi-gz-bean` — `applet/GzBeanBookingMpController#verifyScan`（复用 service，BO 复用 `GzBeanBookingVerifyScanBo`）✅
- **小程序**：`miniapp/src/pages/bean/verify-scan.vue` + `api/gz-bean.ts` verifyScan 封装 ✅；`wx.scanCode` 已按 wxMOCK 约定补 dev 短路
- **测试**：service 核销分支单测 + mp vitest ✅

## 备注

- 后端验签 + 状态流转复用 GZ-BEAN-008，未复制逻辑 ✅。
- **真机闭环硬依赖 GZ-BEAN-012**：店员端就绪，但顾客端无真二维码可扫。两 ticket 同批次交付，缺 012 则 011 真机不可用（仅 dev 粘 qrPayload 可验逻辑）。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-BEAN-011 revision 段 -->
