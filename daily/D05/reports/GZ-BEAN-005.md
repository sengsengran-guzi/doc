# GZ-BEAN-005 完工报告 — mp 预约详情 + 核销码 QR 大图

> 实施：kevin-coder（后台 agent）+ 主线程收口（BizQrCode.test.ts 补写 + 全量验证 + 本报告）
> 日期：2026-06-02（D05）
> 状态：Tier 1A ✅ / Tier 1B 单测 ✅ / mp ticket → close 进人验列

---

## §0 状态自检（实施前 — 主线程已对账）

| 检查项 | 结论 |
|---|---|
| 上游 GZ-BEAN-004 | ✅ detail 接口 `GET /app/gz/bean/booking/{id}` 已存在（本人 403 校验）；mp `getBookingDetail()` API 已封装 |
| QR 服务真名 | `QrCodeSigner`（非卡里 `BeanQrService`）：`sign(bookingNo,sessDate,seatId)` + `buildQrPayload()` → `"BK|{no}|{code}"` |
| VO 缺口 | `GzBeanBookingVO` 缺 qrPayload/storeName/storeAddress → 本 ticket 补 |
| 新依赖 | uqrcode（Kevin §6#8 批准）|
| 编译健康 | `mvn install -pl ruoyi-gz-bean -am` exit=0 |

---

## §N 完工总结

### 改了哪些文件

**后端（gz-bean，小改）：**
- `domain/vo/GzBeanBookingVO.java` — 加 `qrPayload` / `storeName` / `storeAddress`
- `service/impl/GzBeanBookingServiceImpl.java` — `selectVoById` 填充：`enrichStoreInfo`（join store）+ `buildQrPayload`（QrCodeSigner 即时重算，payload 不持久化）；`enrichStoreInfoBatch`（列表去重 storeId 批量查，防 N+1，供 BEAN-006 复用）

**mp 端：**
- `package.json` — 加 `@uqrcode/js@^4.0.7`（纯本地 QR 生成，无 CDN，合同附件二腾讯云全栈合规）
- `components/biz/BizQrCode.vue`（新）— uqrcode 渲染封装，props `value/size/disabled/canvasId`，纠错级 L，失败兜底显示文本核销码（doc/10 §3 R4 店员手动核销路径），码点色用 c-tokens 字面量（canvas 不吃 CSS 变量）
- `components/biz/BizStatusTag.vue`（新）— 4 状态 tag（pending 朱红 / used 绿 / cancelled·no_show 灰），走 C token
- `pages/bean/detail.vue`（新）— `<route>` 块自动注册 `/pages/bean/detail`；布局门店→日期时段→座位→QR 大图(屏宽70%)→状态 tag→底部 CTA；pending 显示「取消预约」按钮占位（handler 留 BEAN-007，TODO 标注）；4 状态视觉（used/cancelled/no_show QR 灰显）
- `pages/bean/success.vue` — 「查看预约详情」CTA 接 `/pages/bean/detail?id=`（真实业务入口 = Tier 2 可达）
- `locale/bean.zh-CN.ts` — `bean.detail.*` 文案
- `components/biz/BizQrCode.test.ts`（新，主线程补）+ `BizStatusTag.test.ts`（新）

### Tier 1A / 1B 自测 raw output

**① 后端编译（VO + selectVoById enrich）**
```
mvn -q install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
===INSTALL_EXIT=0===
```

**② 后端单测（含 BEAN-004/009 回归，selectVoById 改动不破坏现有用例）**
```
mvn test -pl ruoyi-modules/ruoyi-gz-bean -Dtest=GzBeanBookingServiceImplTest → exit=0
（GzBeanBookingServiceImplTest 11 tests 全绿；selectVoById 对 null booking / null store 均有兜底）
```

**③ mp 全量 vitest 回归**
```
 ✓ src/components/biz/BizQrCode.test.ts (4 tests)
 ✓ src/components/biz/BizStatusTag.test.ts (6 tests)
 Test Files  9 passed (9)
      Tests  57 passed (57)
```

**④ mp build（detail 编译 + pages.json 注册）**
```
$ pnpm build:mp-weixin
dist/build/mp-weixin/pages/bean/detail.{js,json,wxml,wxss,vendor.js}  ← 16:30 生成
src/pages.json:35  "path": "pages/bean/detail"   ← <route> 块自动注册
```

### 已知 issue / 风险

- **QR 真机可扫性**：happy-dom 单测只锁逻辑分支（空 payload/灰显/重渲染），码矩阵正确性 + 真机微信扫码识别留 Kevin Tier 2 批量人验（testing-human.md 已列）。
- **低端机渲染兜底**：BizQrCode 渲染失败 → `failed=true` + 显示文本核销码，店员可手动核销（与 BEAN-008 手动核销互补）。

### 对下游提示

- **BEAN-006**：列表卡片 storeName 已可用（`enrichStoreInfoBatch` 在 `selectMyMpList` 路径已接）；缩略 QR 按卡里 R2 用静态 icon，不用 BizQrCode（仅详情页渲真码）；状态 tag 直接复用 `BizStatusTag`。
- **BEAN-007**：detail.vue 的「取消预约」按钮已渲染（pending 态），click handler 是占位 TODO，BEAN-007 接 `cancelBooking(id)` + 二次确认弹窗。
- **BEAN-008**：QR payload 口径 `"BK|{bookingNo}|{verifyCode}"`，扫码核销解析后按此拆分；verifyCode 校验复用 `QrCodeSigner.verify(bookingNo, sessDate, seatId, verifyCode)`。

### kevin-qa Tier 1B

本会话后台 agent 无 spawn kevin-qa 能力，Tier 1B 机械部分（mp vitest 57/57 + 后端单测 + build 可达性）由主线程跑通。mp 真机 happy path（扫码识别）→ Kevin Tier 2 批量人验。
