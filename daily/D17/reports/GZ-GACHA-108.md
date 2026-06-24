# GZ-GACHA-108 完工报告 — 开盒重做（竞品式暗场开盒 + 恭喜获得 + 领取背包）

> Tier 1A 自测（主线程实施 + 自测）。Tier 1B（kevin-qa mp 模拟器 E2E）+ Tier 2（真机支付/震动/视觉拍板）待派。
> 注：本卡经 3 轮方向调整定稿——摇一摇方案已废弃，最终 = 竞品式按钮触发暗场开盒（无摇一摇）。

## §0 状态自检

| 检查 | 结果 |
|---|---|
| 设计真源 | ✅ 清爽皮肤（c-tokens.scss）；暗场仅开盒动画那一刻戏剧化，揭晓回亮底 |
| 去摇一摇 | ✅ 加速度计 / shake 逻辑全清（仅注释提「无摇一摇」） |
| 后台可配置 | ✅ 开盒只读 gz_gacha_prize（image/rarity/name/参考价），无硬编码 |
| 盲盒语义 | ✅ 「开盒/获得/恭喜获得/领取」，禁抽奖/中奖/命中（单测断言） |
| 合规 | ✅ 结果后端定、无 near-miss；**不照抄竞品 C2C 集市/假抽/微信支付规避** |

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `doc/daily/D17/tickets/GZ-GACHA-108.md` | 重写为竞品式（去摇一摇） |
| `src/pages/gacha/draw.logic.ts` | opening→crack→reveal 序列 + 稀有度 tier/震动节奏/加强档（删 shake 全部纯逻辑） |
| `src/components/biz/BizGachaDraw.vue` | 暗场发光神秘胶囊(?) + 环境光 + 漂浮星点 → 裂开光晕 + 粒子 → spring 揭晓（删进度环/charging/shake） |
| `src/pages/gacha/draw.vue` | 自动播放状态机 + 暗场↔亮底切换 + 恭喜获得 + 领取(→背包)/再抽 + 低端机直 reveal（删加速度计/点击兜底） |
| `src/locale/gacha.zh-CN.ts` | 删 shake 文案，增 congrats(恭喜获得)/claim(领取)；ctaAgain→再抽一次（zh+en） |
| `src/pages/gacha/draw.logic.test.ts` | 重写：openingSequence + tier/震动/加强档（21 例） |

## AI 自测 raw output

### 1. 单测（全 gacha 72 例，draw.logic 21）

```
$ pnpm exec vitest run src/pages/gacha/ src/api/gz-gacha.test.ts
 ✓ src/pages/gacha/list.logic.test.ts (12 tests)
 ✓ src/api/gz-gacha.test.ts (3 tests)
 ✓ src/pages/gacha/detail.logic.test.ts (16 tests)
 ✓ src/pages/gacha/draw.logic.test.ts (21 tests)
 ✓ src/pages/gacha/history.logic.test.ts (20 tests)
 Test Files  5 passed (5)
      Tests  72 passed (72)
```

### 2. 残留 shake / 加速度计引用（应仅注释）

```
$ grep -rnE "shakeHint|shakeProgress|startAccelerometer|postShakeSequence|SHAKE\b" src/
src/components/biz/BizGachaDraw.vue:11: * ...（传 stage，按钮触发自动播放，无摇一摇）...   ← 注释
src/pages/gacha/draw.logic.ts:4: * 竞品式开盒（按钮触发，自动播放，无摇一摇）...        ← 注释
（无代码残留）
```

### 3. lint + type-check

```
$ pnpm exec eslint <5 改动文件>        → 0 error
$ pnpm exec vue-tsc --noEmit（全量）   → error TS 计数 = 0
```

## 已知 issue / 待办（下游）

- **GZ-GACHA-109 后台配置增强**（待建）：machine 补「出荷时间 ship_time + 尺寸 size_desc」对齐竞品（Flyway + entity + VO + admin form + mp 展示）。其余 machine/prize 字段已齐。
- **背包**：当前 = 复用 GACHA-106「我开过的」（已抽待发货列表），未新建表；如需独立「我的背包」页/语义可另议。
- **多连抽**（抽3/抽5/全收）：竞品有，需后端批量出货事务，V1.2+。
- **AC8(a) mp 模拟器 E2E flow**：需新建 gacha-draw flow，kevin-qa Tier 1B 跑。
- **AC8(b) Tier 2 真机**：真实支付 + 震动 + 暗场动画观感拍板。

## 风险提示

- draw 仍为页面跳转（非真·页内弹层）：保留了可用的微信支付流；真页内 overlay 须重构支付流，未做。
- 暗场用近黑暖底（#15120e）——与全站清爽亮底反差大，是刻意的「开盒 moment」；如甲方要更克制可调浅。
- conic-gradient（SSR 柔光底）老基础库不支持时自然退化，不影响主流程。
