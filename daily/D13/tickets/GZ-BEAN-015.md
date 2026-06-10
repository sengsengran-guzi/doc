# GZ-BEAN-015 — mp 拼豆付费页（选 1 类型 1 时段 + 显余量 → 采手机/微信号 → JSAPI，单笔金额）

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M-BEAN 拼豆域
**关联拆解**: doc/02-需求拆解.md GZ-BEAN-015
**关联 mockup**: design/mockup/（C 日漫海报浓墨视觉参考，不强求逐像素）
**关联 ADR**: doc/_adr/0007-pindou-paid-booking-state-machine.md + doc/_adr/0008-seat-type-quota-model.md
**依赖**: GZ-BEAN-014（D12，下单事务 + 余量接口 + PINDOU）+ GZ-COUPON-003（D13，选券模块）+ GZ-USER-005（D11，wechat_id）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §11（N1-N10 用户端节点 + 计费模型 + 异常 E1-E6，单笔单时段）
- **字段表**：doc/11-字段权威表.md §3.5（座位类型配置）+ §3.6（活跃 booking 定义 / 余量口径）
- **ADR**：0007（双状态机 + 免费单兜底）+ 0008（座位类型配额，按 booking 计数）
- **UI 参考**：C 日漫海报浓墨 — doc/tokens.md + doc/13；只用 `src/components/biz/Biz*` + `var(--c-*)`，不直接撒 `<wd-*>`

## What

在 D12 BEAN-014 后端核心之上落 mp 端拼豆付费页（C 日漫海报浓墨，**单笔单时段**）：选 1 类型 1 时段（显余量）→ 选券 → 采手机/微信号 → JSAPI 支付 → 预约详情（核销码）。

## AC（验收标准）

- [ ] **AC1 选座 UI（单笔单时段 + 显余量）**：bean/index 单页选 **1 个座位类型**（字典 gz_bean_seat_type 翻译：单人/双人/四人桌）**+ 1 个时段**（单选，非多选累加）→ 金额 = 该类型单价（单笔）。调 `GET /app/gz/bean/booking/type-slots?storeId&sessDate`（D12 接口，返各档 quantity/active/remaining/full + 单价）→ 每档**实时显余量**「还剩 N 个单人座」/「已满」灰显不可选。
- [ ] **AC2 门店默认（强约束 #13）**：V1.0 仅成都一家 → 默认选中，UI 隐藏切换。
- [ ] **AC3 选券模块（消费 COUPON-003）**：仅 unused + 适用拼豆 + 未过期；选中展示实付 = 单笔金额 − 券面额（下限 0）。用 `BizCouponPicker`（COUPON-003 产）。
- [ ] **AC4 付款前采集（doc/10 §11.N6，E2 拦截）**：① `gz_user.mobile` 空 → 原生 `getPhoneNumber`（留 Kevin 真机人验）；② `gz_user.wechat_id` 空 → 表单手动填微信号（USER-005 已填则预填）；**两者都采集成功才能 N7 提交**（拒绝/不填 → 拒收 + 提示）。后端兜底：未采集 paid-submit 分别返 4001 / 4014。
- [ ] **AC5 支付（doc/10 §11.N7-N9）**：提交 → `POST /app/gz/bean/booking/paid-submit`（body storeId/seatType/sessDate/slotStart/slotEnd/couponId?/dedupClientToken?）→ 付费单返 payParams 五参 → `wx.requestPayment`（JSAPI，复用 §6）→ onPaid → 跳预约详情；免费单 free=true 无 payParams 直接跳详情。
- [ ] **AC6 约满拒单 E1**：paid-submit 返约满（code 4011）→ 提示「[四人桌/下午] 已约满，请重选类型或时段」。
- [ ] **AC7 预约详情**：门店 / 类型 / 时段 / 实付 / pay_status + 核销码二维码（内嵌 `BK|{booking_no}|{verify_code}`，用 BizQrCode）。多类型/多时段 = 用户再下一笔（页面留「再约一笔」入口）。
- [ ] **AC8 Tier 2 可达**：tabbar 未重构（SYS-010 在 D14）→ **主动加临时入口**到 `pages/index/index.vue` 或现有首页，注释 `<!-- TODO(Tier2-entry-temp): GZ-BEAN-015, remove when GZ-SYS-010 merged -->`。Kevin 从现有首页/临时入口点 1 次到达拼豆付费页。
- [ ] **AC9 C 设计系统遵循**：只用 Biz* 原子组件 + `var(--c-*)` token（粗墨边 / 硬投影 / 朱红主色 / 报头风）；不混 emoji（占位用 MOCK 水印）。
- [ ] **AC10 vitest unit**：选座单选逻辑 + 余量灰显逻辑 + 实付计算（单笔 − 券面额下限 0）+ 采集拦截逻辑单测。

## Tech（端 + 范围）

- **小程序**：`code/main/miniapp/src/pages/bean/index.vue`（改造为单页付费选座）+ `src/api/bean.ts`（paid-submit/type-slots）+ 复用 BizSlotGrid/BizSeatList/BizFixedCta/BizQrCode/BizCouponPicker + `pages/index/index.vue` 临时入口。
- **后端**：调 D12 BEAN-014 现成接口（paid-submit/type-slots），如需微调（如 type-slots 加单价字段）在 gz-bean 补，**最小改动**。
- **DDL**：无（用 D12 已建表/接口）。

## 备注

- **串行批次**（COUPON-003 完工后派，第二波末）— 无并行撞车，正常 install。
- mp 陷阱：数字 `type=digit`；id 全 string；路由用 booking_no；getPhoneNumber + wx.requestPayment 真机留 Kevin 批量人验（mock 模式）。
- **不要 spawn kevin-qa**（子不能 spawn 孙；Tier 1B 主线程统一派）。写完 reports（含 §AI 测试段占位 + Tier 2 可达路径 + 临时入口注释位置）即返回。
- mp ticket → 进 progress.md「人验」列；testing-human.md 预填 happy path。

---

## §revision（Kevin 批量人验后填，初始空）
