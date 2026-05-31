# GZ-GACHA-105 — mp 抽奖动画 + 结果展示

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §用户操作流程 步骤 5-7 + §用户故事 2 + tokens.md §9 收集驱动
**关联拆解**: doc/02-需求拆解.md §3.3 第 803 行
**关联 mockup**: design/mockup/gacha-draw.html + design/mockup/me-collection.html（仅布局参考；视觉以 C 系统为准，doc/13；出奖动画为 doc/13 §3.2 待建 Biz 组件 BizGachaDraw）
**关联 ADR**: —
**依赖**: GZ-GACHA-104

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md §7 扭蛋抽奖流（步骤 5 动画 / 步骤 6 揭晓 / 步骤 7 跳图鉴）
- **字段表**：doc/11-字段权威表.md §7.3 `gz_gacha_draw`（prize_snapshot JSON 结构）
- **UI 索引**：doc/12-UI-权威索引.md §MP-GACHA-DRAW（三段分镜节奏 / 稀有度光晕 / 揭晓后 CTA 选项）
- **tokens.md §9 ★**：三段分镜「转动 → 裂开光爆 → 揭晓稀有度光晕」+ 收集驱动伏笔（揭晓后强提示图鉴入口）+ 盲盒语义

## What

支付成功后 mp 端轮询 draw 状态 → 拿到 drawn 状态后播放三段分镜动画 → 揭晓中奖物 + 稀有度光晕 + 强提示图鉴进度（伏笔 GACHA-107 me-collection）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/draw/{drawId}/status` 返回 draw 当前状态（pending_pay / paid / pending_draw / drawn / stock_empty_refunded）+ 若 drawn 则带 prize_snapshot
- [ ] **AC 2**：page `pages/gacha/draw.vue`：
  - 入参：drawId（从详情页跳转 query）
  - 初始进入：屏蔽返回键 + 全屏占位（防用户误操作）
  - 轮询 status 接口（1s 一次，超 60s 弹"已支付，结果稍后到账，请到历史页查看"+ 跳 GACHA-106）
  - 拿到 drawn → 播放三段分镜（tokens.md §9）：
    - **段 1：转动**（0~1.5s）— 扭蛋机晃动 + 胶囊滚动动画（CSS transform rotate + 抖动）
    - **段 2：裂开光爆**（1.5s~2.5s）— 胶囊裂开光爆效果（CSS radial-gradient + scale + opacity 关键帧）
    - **段 3：揭晓**（2.5s~）— 中奖物展示 + 对应稀有度光晕（SSR 金 var(--c-r-ssr) / SR 紫 var(--c-r-sr) / R 蓝 var(--c-r-r) / N 灰 var(--c-r-n)，光晕走 C 稀有度 token，不硬编码 hex）
  - 拿到 stock_empty_refunded → 友好弹窗"很遗憾，奖品已被抢空，已自动退款"+ 跳列表页
- [ ] **AC 3**：揭晓后 UI：
  - 中奖物大图 + 稀有度徽章（doc/13 §3.2 待建 Biz 组件，走 var(--c-r-ssr/-sr/-r/-n)）+ 名称 + 公示价值（如有）
  - **强提示图鉴进度伏笔**：底部条「⭐ 已收集 X/Y 件 — 查看图鉴」点击跳 `/pages/me/collection?machineId={machineId}`（GACHA-107）
  - **集齐特典明示徽章奖励**：如该机器已集齐 → 上方弹"集齐特典 🏆"徽章动画 + "恭喜集齐 XX 系列"
  - 双 CTA：「再抽一次」（跳回详情页保留 machineId）/「去历史看看」（跳 GACHA-106）
- [ ] **AC 4**：动画性能：
  - CSS transform / opacity（GPU 友好），**禁用** setInterval 重绘
  - 低端机 fallback：检测 navigator.hardwareConcurrency < 4 → 直接段 3 揭晓（跳过段 1+2）
- [ ] **AC 5**：盲盒语义（tokens.md §9）：
  - 所有文案用"获得 / 出现 / 开盒"，不用"中奖 / 抽中"
  - 揭晓金句："获得 SSR — {prizeName} ✨"（不是"中奖：XX"）
- [ ] **AC 6**：业务组件包一层：
  - `components/biz/BizGachaSpinningStage.vue`（段 1 转动）
  - `components/biz/BizGachaBurstStage.vue`（段 2 裂开光爆）
  - `components/biz/BizPrizeRevealCard.vue`（段 3 揭晓 + 光晕）
- [ ] **AC 7**：i18n 走 `t('gacha.draw.xxx')`
- [ ] **AC 8**：单测 happy（轮询逻辑：mock 5 次 pending_draw → 1 次 drawn → 触发动画 callback）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaDrawMpController.java` 加 `getStatus(drawId)` 方法（仅查询）
  - service 复用 GACHA-104 的 IGzGachaDrawService 加 `getStatusForMp(drawId, userId)` 方法（校验 user_id 归属）
- **小程序**：
  - `pages/gacha/draw.vue`
  - `components/biz/BizGachaSpinningStage.vue` + `BizGachaBurstStage.vue` + `BizPrizeRevealCard.vue`
  - `composables/useDrawPolling.ts`（轮询编排 + 超时处理）
  - `api/gz-gacha.ts` 加 `getDrawStatus(drawId)`
  - `static/sounds/gacha-burst.mp3`（可选音效 — 段 2 裂开音）
- **测试**：mvn 加 getStatus 单测 + vitest 轮询逻辑单测 + 微信开发者工具实际跑动画

## 备注

### 强约束

1. **三段分镜节奏严格**（tokens.md §9）— 1.5s / 1s / 揭晓，不允许调快或省略
2. **稀有度光晕色严格走 C 稀有度 token**（var(--c-r-ssr/-sr/-r/-n)，doc/tokens.md §1.4）— SSR 金 / SR 紫 / R 蓝 / N 灰，不硬编码 hex/rgba
3. **图鉴入口伏笔强提示**（tokens.md §9 收集驱动）— 揭晓页底部条不可省略
4. **盲盒语义严格**（tokens.md §9）
5. **低端机 fallback** — 不让动画卡死老机型
6. **轮询超时跳历史页**（不卡死用户）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 轮询查 status 而非 ws 推送 | V1.1 简单可靠；微信小程序 ws 维护成本高；轮询 1s 一次延迟可接受 |
| D2 | 动画 CSS 实现（不引 Lottie / GSAP） | 性能 + 兼容 + 不引依赖；视觉可接受度 85%（V1.1 简版）|
| D3 | 低端机 fallback 检测用 hardwareConcurrency | 简单有效；微信小程序 API 限制下能拿到该字段 |
| D4 | 音效用 mp3 而非微信内置 | 文件 < 50KB；mp 端 inner-audio-context 支持好 |
| D5 | "集齐特典徽章"逻辑前端判断 | 揭晓时调 `/app/gz/gacha/collection/check` 拿 isCompleteSet 标识（GACHA-107 提供）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 用户在动画过程中切后台 / 关闭 mp | 重新进入时检测 drawId 状态，直接跳揭晓页（不重播动画） |
| R2 | 轮询频繁导致 mp 端流量浪费 | 1s 一次 + 12 次后退化为 5s 一次；超 60s 跳历史页 |
| R3 | 揭晓后用户截图分享 → IP 占位 emoji 不雅观 | 揭晓页右下角加水印「来自谷子宇宙」+ 不用真实 IP 图（合规） |
| R4 | 低端机 fallback 判定不准 | 加二级 fallback：动画播放期间检测帧率 < 30fps → 强制跳段 3 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
