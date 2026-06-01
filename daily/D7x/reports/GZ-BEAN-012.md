# GZ-BEAN-012 完工报告 — 顾客核销码真二维码（success.vue 收尾）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（按指令不做 git 操作；分支 staging） |
| 上游依赖 merge | ✅ GZ-BEAN-004（success 页）/ GZ-BEAN-005（detail 真 QR）/ GZ-BEAN-011（扫码端）均已交付 |
| 关键组件存在 | ✅ `BizQrCode.vue`（props value/size/disabled/canvasId，@fail，failed 兜底）已存在；detail.vue 已用真 QR |
| 待补点定位 | ✅ 仅 success.vue 还是占位假网格（`.qr__grid` 49 格 + TODO(GZ-BEAN-005)） |
| type-check | ✅ exit=0 零 error |
| vitest | ✅ 114/114 全绿，BizQrCode.test.ts 4/4 |
| ADR 已读 | doc/_adr/0004-mp-admin-permission-foundation.md（关联，本票无新决策） |

## 实现摘要

**改动**：`src/pages/bean/success.vue`（单文件，纯前端）。

- 删占位假网格：模板内 `<BizPanel small flat class="qr"><view class="qr__grid">` 49 格 + `TODO(GZ-BEAN-005)` 注释 → 换 `<BizQrCode :value="qrPayload || bookingNo" :size="qrSize" canvas-id="success-qr" @fail="onQrFail" />`（参照 detail.vue 用法）。
- 删死样式：`.qr__grid` / `.qr__cell` / `.qr__cell.is-on`（约 22 行 SCSS）→ 换轻量 `.qr` 容器（BizQrCode 自带纸白底 + 墨黑描边 + 硬投影）。
- script：新增 `qrSize`（固定 200px）+ `qrFailed` ref + `onQrFail()` 失败回调（留痕 console.warn + 弱化 QR 区，class `qr--fallback`）。
- 兜底（doc/10 §3 R4）：QR 下方 `.ticket__code-num`（`verifyCode || bookingNo`）+ payload 文本本就常显 → 渲染失败不白屏，店员手动核销。
- canvas-id 用 `success-qr`（与 detail 页默认 `biz-qrcode` 隔离，避免多页 canvas-id 冲突）。
- JSDoc 顶注同步更新（删 V1.0 降级方案描述，改为真 QR + 兜底说明）。

QR 内容 = `qrPayload`（格式 `"BK|{bookingNo}|{verifyCode}"`），与 GZ-BEAN-011 verify-scan 解析格式一致。

## AI 自测（Tier 1A）

### type-check
```
> vue-tsc --noEmit
=== type-check exit=0 ===
```

### vitest（BizQrCode 单测仍绿）
```
 ✓ src/components/biz/BizQrCode.test.ts (4 tests) 25ms
 Test Files  1 passed (1)
      Tests  4 passed (4)
```
四分支全覆盖：空 payload→failed+emit fail / 有 payload→建 context / disabled→灰显态 class+建 context / value 变化→重渲染。

### 占位残留扫描（确认假网格 + TODO 已清）
```bash
grep -rn "qr__grid\|qr__cell\|TODO(GZ-BEAN-005)" src/pages/bean/success.vue
# 输出：(空) — 占位与 TODO 已全部移除
```

## 风险提示 / 已知 issue

- happy-dom 无真实 canvas，vitest 只锁组件层逻辑分支，**像素级可扫性未验**（与 detail 页一致，BEAN-005 已定调）。
- 真机端到端「店员扫顾客 success 页二维码 → 核销成功」(011×012 闭环) **未在 AI 端跑**（无真机 wx.scanCode 工具）→ 留 Kevin Tier 2。

## 待 Kevin Tier 2 批量人验（mp 端）

- ⬜ 顾客提交预约 → success 页见真二维码矩阵图（非占位格子）
- ⬜ success 页「查看预约详情」→ detail 页见核销码大图
- ⬜ 店员（GZ-BEAN-011 扫码端）扫 success 页 / detail 页二维码 → 核销成功（011×012 端到端闭环）
- ⬜ 低端机/渲染失败兜底：二维码区不出图时，下方文本核销码 + payload 仍可见

## 对下游 ticket 的提示

- success.vue 与 detail.vue 现已统一走 BizQrCode；后续若 BizQrCode 改 canvas 实现（如 type=2d），两页同步即可，无页面级特例。
- 本票无新增临时入口（success→detail 走既有真实业务入口，Tier 2 可达）。

## §AI 测试段（kevin-qa 完工后追加）

（本环境不 spawn subagent；Tier 1B 由主线程集成 gate 处理。占位）
