# GZ-BEAN-015 完工报告 — mp 拼豆付费页（选 1 类型 1 时段 + 显余量 + 采集 + JSAPI）

> mp + 少量 be（仅 mp api 补充），复杂度 M，**mp 人验**（进 progress.md 人验列）。C 日漫海报浓墨。
> **实施方式**：mp api（gz-bean.ts V1.2 付费段）由 background subagent 建成（崩在写 locale 前）；**locale + index.logic + index.vue 重写 + 采集 + 支付编排 + me 入口收尾由主线程接管**（见文末异常留痕）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游依赖 | ✅ BEAN-014（D12）paid-submit/type-slots 接口 + PINDOU；COUPON-003（D13）BizCouponPicker；USER-005（D11）wechat_id |
| 关键接口/组件 | ✅ getTypeSlots/submitPaidBooking（gz-bean.ts）+ BizCouponPicker（easycom `^Biz` 自动注册）+ updateProfile（gz-user，存 wechat_id）+ useOrderSubmit 支付范式 |
| 拼豆 tab 可达 | ✅ pages.json tabBar「拼豆」→ pages/bean/index（已上线 3-tab） |
| ADR 已读 | ✅ ADR-0007（双状态机 + 免费单兜底）+ ADR-0008（座位类型配额，按 booking 计数） |
| 权威蓝图引用 | ✅ doc/10 §11（N1-N10 + E1-E6 单笔单时段）+ doc/11 §3.5（座位类型配置）/§3.6（余量口径） |

### 权威蓝图关键约束摘录
- **选座（doc/10 §11.N3/N4，单笔单时段）**：选 1 类型 + 1 时段（单选非累加）；余量 = quantity − 活跃 booking；「还剩 N」/「已满」灰显。金额 = 类型单价（单笔无累加）。
- **抵扣（doc/11 §11.3）**：实付 = 单价 − 券面额（下限 0）；amount_cent = 实付，券面额不计 GMV（后端 paid-submit 重算）。
- **采集（doc/10 §11.N6，E2 拦截）**：mobile 空 → getPhoneNumber；wechat_id 空 → 手动填；两者齐才能提交（后端兜底 4001/4014）。
- **支付（§11.N7-N9）**：付费单 wx.requestPayment（JSAPI）→ onPaid 跳详情核销码；免费单（实付 0）直跳详情。

## 实现摘要

### mp api（gz-bean.ts，subagent 建 + 主线程补 id）
- `TypeSlotVO`（seatType/name/unitPriceCent/slotStart/slotEnd/quantity/remaining/full/active）+ `getTypeSlots(storeId, sessDate)`。
- `PaidBookingSubmitRequest`（storeId/seatType/sessDate/slotStart/slotEnd/couponId?/dedupClientToken?）+ `PaidSubmitVO`（**主线程补 id + amountCent/discountAmountCent/payAmountCent**）+ `submitPaidBooking` + `BEAN_PAID_ERROR_CODE`（4011/4001/4014）。

### mp 页（miniapp，C 设计系统，主线程）
- `pages/bean/index.vue`（**重写** V1.1 免费具体座位 → V1.2 付费类型配额）：报头 + 门店（单店隐藏切换）+ ① 选日期 BizDatePicker + ② 选类型（chip 显单价/全满灰显）+ ③ 选时段（chip 显余量「还剩 N」/「已满」灰显单选）+ ④ BizCouponPicker 选券 + 金额（单价−券=实付/免费）+ ⑤ 手机号 getPhoneNumber + ⑥ 微信号手动填（updateProfile）+ 到店须知 + BizFixedCta。付费提交 → submitPaidBooking → wx.requestPayment（仿 useOrderSubmit）→ 跳 detail；免费单直跳。
- `pages/bean/index.logic.ts` + `.test.ts`（主线程）：纯逻辑（groupTypes 类型聚合 / slotsOfType 时段 / unitPriceOf / calcPayCent 实付下限0 / remainLabel 余量 / slotSelectable / canSubmitPaid 采集门控 / formatYuan / shortHHmm），15 vitest。
- `locale/bean.zh-CN.ts`（主线程）：加 `beanPaidZhCN` scope（50+ key）+ t() `bean.paid.` dispatch。

## AI 自测（Tier 1A）

### ① type-check（vue-tsc，bean/index + index.logic + gz-bean + BizCouponPicker + me 全部 0 TS 错）
```
pnpm type-check | grep 'pages/bean/index|bean/index.logic|api/gz-bean|BizCoupon|me/coupons' = 0
（修 2 处：index.logic [...map.values()] → Array.from；index.vue <input maxlength="64"> → :maxlength="64"）
```

### ② vitest（bean/index.logic 15 tests：聚合 + 余量 + 实付 + 采集门控）
```
 ✓ src/pages/bean/index.logic.test.ts (15 tests) 9ms
 Test Files  1 passed (1)
      Tests  15 passed (15)
```
覆盖：groupTypes 聚合 + active 过滤 + anyAvailable / slotsOfType 过滤排序 / unitPriceOf / calcPayCent 下限 0 / remainLabel 满·余量 / slotSelectable / canSubmitPaid 各采集门控。

### ③ mp build（uni build -p mp-weixin，BizCouponPicker easycom + coupons 页 uni-pages 注册 + dist 生成）
```
DONE  Build complete.   (exit 0)
dist/build/mp-weixin/app.json 生成（1956 bytes）
coupons 页 uni-pages 自动注册：grep dist app.json → pages/me/coupons ✅
BizCouponPicker easycom `^Biz` 自动注册 + bean/index.vue 付费页整体编译 0 error
（尾部唤 devtools cli 假挂起 → pkill -o cli，dist 已生成，memory mp-build-devtools-hang）
（pre-existing 警告：pay/test.vue / pay/result.vue <route/> 废弃标签，非本卡文件）
```

## Tier 2 可达性（mp 硬约束，CLAUDE.md §8.3）
- **拼豆付费页**：Kevin 点底部「拼豆」tab（pages.json tabBar 已上线指向 pages/bean/index）→ 付费页，**N=1** ✅
- **⚠️ 纠正任务卡假设**：任务卡说「tabbar 未重构 → 加临时入口」，但实测**拼豆 tab 在 V1.0 3-tab 里早已存在**（CLAUDE.md §7.5）→ bean/index.vue 即拼豆 tab 落地页，**无需临时入口**。SYS-010（D14）是扩 5 tab，不影响现有拼豆 tab。
- 选券模块（BizCouponPicker）已集成在付费页 ④ 步。

## 风险提示 / 已知 issue
- **R-1 跳详情用 detail 页**：付费/免费成功 redirectTo `/pages/bean/detail?id=`；detail.vue（BEAN-005）展示 BookingDetailVO（含 payStatus/amountCent/seatType/qrPayload 核销码）。若 detail 未渲染 V1.2 付费字段（实付/类型）= 小 revision，留 Kevin 人验反馈。
- **R-2 支付最终态不信前端**：requestPayment success/fail 都跳详情，pay_status 以后端微信回调为准（detail 拉最新）；取消单留 paying 可在「我的预约」继续。
- **R-3 wechat_id 采集走 updateProfile**：复用 USER-002 个人资料更新接口（body.wechatId）；已填预填 input。
- 待 Kevin 批量人验（仅 mp，真机）：① 选类型/时段余量「还剩 N/已满」准确；② getPhoneNumber 原生授权；③ 微信号填写保存；④ wx.requestPayment 拉起（mock 模式）；⑤ 支付成功跳详情看核销码；⑥ 选券实付；⑦ 可再约一笔（多次预约）；⑧ C 设计系统遵循度（粗墨边/朱红选中/报头风）。

## 对下游 ticket 的提示
- **D14 GZ-SYS-010（tabbar 重构 5 tab）**：拼豆 tab 已指向 bean/index（付费页），SYS-010 扩 tab 时保留拼豆 tab 指向不变。
- 详情页 detail.vue 若需补 V1.2 付费字段展示（实付/类型/pay_status），可在 D14 或 revision 补（BookingDetailVO 字段已就绪）。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

**Tier 1B（主线程整批集成验证 2026-06-10）** — 主线程一次启动 app 整批验：
- App `Started in 10.958s`，curl `/app/gz/bean/booking/type-slots?storeId=1&sessDate=2026-06-20` → HTTP 200（BEAN-014 接口注册，BEAN-015 调用）
- mp build dist 生成（bean/index.vue 付费页 + BizCouponPicker easycom 整体编译 0 error）
- vitest index.logic 15 passed + type-check 0 错
- 可达：拼豆 tab N=1（pages.json tabBar 已上线指向 pages/bean/index）
- ⬜ **mp 卡 → 进 progress.md 人验列**待 Kevin 批量真机验（选座余量 + getPhoneNumber + 微信号 + requestPayment mock + 核销码 + C 系统，见 testing-human.md）；8080 已释放

---

## §异常留痕
- BEAN-015 background 前台 subagent **崩于 `tool call could not be parsed`**（29 tool_uses / 5min，崩在写 bean.zh-CN.ts locale 的 Edit 时，result 暴露畸形 `<invoke>` 文本）。
- 崩前已建 gz-bean.ts 的 V1.2 付费 api 段（TypeSlotVO/getTypeSlots/PaidSubmitVO/submitPaidBooking，质量合格）+ 规划好 beanPaidZhCN 文案（result 中可复用）。
- **主线程接管补全**：locale（复用规划文案）+ index.logic + test + index.vue 重写（V1.1→V1.2 付费）+ 采集/支付编排 + PaidSubmitVO.id + 全套验证 + 本 report。
- 全批次 subagent 崩溃率 5/7（仅 COUPON-002 + PAY-105 前台成功）；可靠路径 = 主线程实施。
