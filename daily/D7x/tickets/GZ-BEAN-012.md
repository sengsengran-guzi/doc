# GZ-BEAN-012 — 顾客核销码二维码渲染（接 @uqrcode/js）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4（核销二维码 / 预约详情含核销码大图）
**关联 ADR**: doc/_adr/0004-mp-admin-permission-foundation.md
**依赖**: GZ-BEAN-004（success 页，已交付）/ GZ-BEAN-005（预约详情页，已交付）；**与 GZ-BEAN-011 互为闭环**（011 扫码端 / 012 被扫端）

> **由来**：GZ-BEAN-011 核销店员端已就绪，但顾客端核销码当前是**降级文本 + 占位格子**（success.vue TODO(GZ-BEAN-005)），真机店员无真二维码可扫 → 整个扫码核销闭环不通。本 ticket 补齐被扫端。

---

## 必读权威文档

- **业务流**：doc/10 §3（核销码生成 / R4 低端机兜底：渲染失败显示 booking_no）
- **字段表**：doc/11 §3.4 gz_bean_booking（qr_payload / verify_code）
- **UI 参考**：`design/mockup/` 预约成功 / 详情页核销码区（视觉参考）

## What

把已安装的 `@uqrcode/js`（^4.0.7，uni-app 标准二维码库，已在 package.json）接进顾客侧 `success.vue` + 预约详情页，把 `qrPayload` 渲染成**可扫的真二维码矩阵图**，替换现降级文本 + 占位 `.qr__grid`。**不引新依赖**（库已装）。

## AC（验收标准）

- [x] AC 1：`success.vue` + 预约详情页（BEAN-005，`detail.vue`）用 `@uqrcode/js`（经 BizQrCode 封装）把 `qrPayload` 渲染成二维码矩阵（canvas）。detail.vue 此前已真 QR；本票补齐 success.vue（删占位 `.qr__grid` + TODO，换 `<BizQrCode canvas-id="success-qr">`）。
- [x] AC 2：二维码内容 = `qrPayload || bookingNo`，qrPayload 原文 `"BK\|{bookingNo}\|{verifyCode}"`，与 GZ-BEAN-011 `verify-scan` 解析格式一致。端到端真机扫码核销留 Tier 2 与 011 联测。
- [x] AC 3：渲染失败 / 低端机兜底（doc/10 §3 R4）：BizQrCode `@fail` → `onQrFail` 留痕 + 弱化 QR 区；下方 `.ticket__code-num`（`verifyCode || bookingNo`）+ payload 文本本就常显，店员可手动核销，不白屏。
- [x] AC 4：BizQrCode 走 `uni.createCanvasContext(id, this)` + uqrcode `drawCanvas()` 的 mp 组件内适配写法；视觉契合 C 系统（包一层 Biz 组件，组件库无关纪律 §7.5）。
- [x] AC 5：**Tier 2 入口可达** — 顾客提交预约 → success 页见真二维码；success「查看预约详情」→ detail 页见核销码大图。真机店员扫码核销留 Kevin Tier 2 与 011 联测（AI 端不跑真机 wx.scanCode）。

## Tech（端 + 范围）

- **小程序**：
  - 新 `miniapp/src/components/biz/BizQrCode.vue`（包 `@uqrcode/js`，props: payload / size，含 fallback slot/文本）—— 组件库无关纪律，页面不直接撒 uqrcode
  - 改 `pages/bean/success.vue`（删占位 `.qr__grid` + TODO，换 BizQrCode）+ 预约详情页同理
- **测试**：mp vitest（BizQrCode 渲染 / fallback 分支）；真机扫码闭环留 Tier 2 人验

## 备注

- `@uqrcode/js` 已是 deps（无需 Kevin 批新依赖）。mp canvas 渲染有平台差异，注意 mp-weixin 的 canvas 2d 接口 + `uni.createCanvasContext` / offscreen 用法，按 @uqrcode/js 文档的 uni-app/mp 适配写。
- 二维码内容必须与 GZ-BEAN-011 verify-scan 的解析格式严格一致，否则扫了核销不了——交付前 011×012 真机联测一次。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-BEAN-012 revision 段 -->
