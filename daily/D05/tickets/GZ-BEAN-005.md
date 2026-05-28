# GZ-BEAN-005 — mp 预约详情 + 核销码 QR 大图

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §关键页面 §我的预约详情
**关联拆解**: doc/02-需求拆解.md §2.3 第 342 行
**关联 mockup**: design/mockup/booking-list.html（V1.0 设计冻结期：列表项点入详情；wot-design-uni 默认 + tokens.md brand-primary）
**关联 ADR**: —
**依赖**: GZ-BEAN-004 ✅(D04)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §状态机（4 状态 pending/used/cancelled/no_show） + §关键节点 N8 跳预约详情页 + §异常分支 E6/E7/E8（核销码被扫后的状态校验）
- **字段表**：doc/11-字段权威表.md **§3.4 `gz_bean_booking`**（详情读取字段 — store_id/seat_id/date/slot_start/status/verify_code/verify_sign） + §3.6 拼豆状态字段详细口径 + §A.3 状态字典编码 `gz_bean_booking_status`
- **UI 参考**（设计冻结期）：doc/12 §MP-BEAN-LIST 详情段（mockup `booking-list.html` 列表项点入）；详情页本身 doc/12 未单独立 page-id，**作为 LIST 的子视图实现**

## What

mp 端用户在「我的预约」列表点入某条预约 → 展示门店 / 日期 / 时段 / 座位 / 状态 / 核销码 QR 大图。pending 状态 QR 完整可扫；used / cancelled / no_show 状态 QR 灰显 + 大字状态标识。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `pages/bean/detail.vue` 路由 `?id=<bookingId>`，调 `GET /app/gz/bean/booking/{id}` 拉详情，未登录 / 非本人预约 → 拒绝（sa-token 权限校验 + 后端比对 user_id）
- [ ] **AC 2**：详情页布局自上而下：门店名 + 地址 → 日期 + 时段（如「2026-06-15 14:00-16:00」）→ 座位编号 → **核销码 QR 大图**（约屏宽 70%）→ 状态 tag → 底部 CTA（pending 显示「取消预约」给 BEAN-007 用，其他状态不显示按钮）
- [ ] **AC 3**：QR payload = D04 `BeanQrService.sign()` 返回的 `{bookingId}.{HMAC签名}` 字符串；前端用 `wx.createOffscreenCanvas` + qrcode-uni（或同类 wxapi 兼容库）渲染，**不依赖外部 CDN**（V1.0 合规：腾讯云全栈，合同附件二）
- [ ] **AC 4**：4 状态视觉：pending = QR 彩色 + brand-primary tag；used = QR 灰度 + "已核销"绿 tag；cancelled = QR 灰度 + "已取消"灰 tag；no_show = QR 灰度 + "已过期"灰 tag
- [ ] **AC 5**：i18n 全覆盖（`bean.detail.xxx`）；状态文案走 sys_dict_data `gz_bean_booking_status` 字典
- [ ] **AC 6**：单测可选；联调验：D04 提交完一个预约 → 进详情 → QR 可被微信扫码识别（payload 内容正确）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/applet/GzBeanQueryMpController.java`（D04 已存在，本 ticket 加 `getBookingDetail(id)` 方法）
  - `service/IGzBeanBookingService.java` + impl 加 `getDetail(bookingId, userId)`（含权限校验）
  - 不落新 DDL（只读详情）
- **小程序**：`code/main/miniapp/src/`
  - `pages/bean/detail.vue`（新建）
  - `api/gz-bean.ts` 加 `getBookingDetail(id)`
  - `components/biz/BizQrCode.vue`（封装 wxapi QR 渲染，复用方便）
  - `components/biz/BizStatusTag.vue`（状态 tag，按字典渲染）
- **测试**：mp 端真机扫一次 QR 验 payload；admin 端先用 BEAN-008 扫码功能验签名校验（互证）

## 备注

### 强约束

1. **QR 渲染走 wxapi 离屏 canvas**，不依赖外部 CDN（合同附件二腾讯云全栈合规）
2. **payload 不含敏感字段**（不放手机号 / openId / userId），仅 `bookingId + HMAC 签名`
3. **签名密钥统一**：与 D04 BEAN-004 落的 `gz.bean.qr.signing-secret` 同源，不要在本 ticket 新生 secret
4. **权限校验**：后端必须 `where user_id = ${current_user_id}`，前端 hide 链接不算防御
5. **4 状态视觉走字典 + tokens.md**，不要硬编码颜色

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 低端机 wxapi QR 渲染慢 / 模糊 | payload < 200 字符；纠错级别用 `L`（payload 短不需要高纠错）；真机验一次 |
| R2 | 用户截图 QR 转给他人扫 → 黄牛 | V1.0 不防（合同未要求）；v2 候选：核销码增加时效 + 一次性 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
