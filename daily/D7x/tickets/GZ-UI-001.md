# GZ-UI-001 — mp 视觉 token 收口 + 客服浮层换皮（旧 brand token 残留清理）

**优先级**: P0（FAB）+ P1（伪 token）
**复杂度**: S（纯改皮，无运行时逻辑改动）
**关联**: doc/tokens.md（唯一色值/尺寸真源）+ doc/13 §5（页面禁止硬编码 hex / 伪 token）+ 铁律 #7
**由来**: 上线前 C 设计系统视觉审计（kevin-designer，2026-06-01）发现旧 `--brand-primary` 时代的 token 残留未随 C 换皮清理，导致全站客服浮层 + 两页核销/店员区视觉跑偏。

---

## What

清掉 miniapp 里旧 brand token 残留（粉色 `#ff6b81` / 伪 `--c-font-*` / `--c-ink-60` / `--c-accent-tint`），全部收口到 c-tokens.scss 真 token，让客服浮层 + 核销页 + 店员徽章回到 C 系统（朱红 + 墨黑粗描边 + 硬投影 + 直角）。**纯改 `<style>`，不动任何运行时逻辑 / 模板结构 / 业务行为。**

## 缺陷明细（审计已核实 file:line）

| # | 严重度 | file:line | 现状 | 期望 |
|---|---|---|---|---|
| D-1 | **P0** | `src/components/biz/BizCustomerServiceFab.vue:124,125,147,164` | 圆钮 `background:#ff6b81`（粉）+ `box-shadow:0 4rpx 16rpx rgba(255,107,129,.35)`（柔光）+ `:active` 同款柔光 + 红点 `#faad14` | 朱红 `var(--c-red)` 底 + 墨黑描边 `var(--c-bw-2) solid var(--c-ink)` + 硬投影 `4rpx 4rpx 0 var(--c-ink)`；`:active` 投影缩 `2rpx 2rpx 0`；红点 `var(--c-yellow)` + `2rpx solid var(--c-ink)` |
| D-3 | **P1** | `src/pages/bean/verify-scan.vue:157,158,171,174,184,185,188` | 5 个伪 token（c-tokens.scss 零定义，靠兜底 hex）：`--c-font-sm,26rpx`→`--c-ink-60,#666`→`--c-accent-tint,#ffe8e0`→`--c-font-lg,34rpx`；成功框 `8rpx` 圆角 | `--c-fs-sm` / `--c-ink-2` / 成功框底 `--c-tint-green` / `--c-fs-lg`；圆角 `0`；投影 `var(--c-shadow-btn)`。**理想**：成功结果框换 `<BizPanel>` + 顶部竹绿状态条，与 success.vue 核销凭证视觉对齐 |
| D-4 | **P1** | `src/pages/me/index.vue:193,195,197` | staff-badge 伪 token：`--c-font-xs,22rpx` / `--c-accent-tint,#ffe8e0`（粉）/ `border-radius:6rpx` | `--c-fs-xs` / 底色 `--c-tint-yellow`（店员徽章鸟金系）/ 圆角 `0`；或直接换 `<BizTag type="yellow">` / `<BizTag type="ink">` |
| D-6 | P2 | `src/components/biz/BizSeatList.vue:120` | 满席态 `&.is-occupied{background:#e5e0d5}`（近似但≠ token） | `background: var(--c-line)`（`#E0D9C8`） |
| D-cleanup | P2 | BizFixedCta / BizButton / login JSDoc 内 `#FF6B81`/`#5BC85F`/`#FF4B4B` 旧注释 | 注释里的旧 token，不渲染 | 顺手清理（无视觉影响，避免误导后人） |

## AC（验收标准）

- [x] AC 1（P0 D-1）：客服浮层圆钮 `#ff6b81`→`var(--c-red)` 底 + `var(--c-bw-2) solid var(--c-ink)` 墨黑粗描边 + `4rpx 4rpx 0 var(--c-ink)` 硬投影（无虚化）；`:active` 投影缩 `2rpx 2rpx 0`；红点 `#faad14`→`var(--c-yellow)` + `2rpx solid var(--c-ink)`。截图留 Kevin Tier 2（AI 端无真机截图工具）。
- [x] AC 2（P1 D-3）：`verify-scan.vue` 7 处伪 token 全换真 token（`--c-fs-sm/--c-ink-2/--c-tint-green/--c-fs-lg/--c-shadow-btn`）；圆角归零；**理想已落地**：成功结果框加竹绿状态条（`--c-green` + 墨黑描边）+ `--c-tint-green` 底，与 success.vue 核销凭证对齐。
- [x] AC 3（P1 D-4）：`me/index.vue` staff-badge `--c-font-xs`→`--c-fs-xs`、`--c-accent-tint`→`--c-tint-yellow`（鸟金系）；圆角 `6rpx`→`0`。
- [x] AC 4（P2 D-6）：BizSeatList 满席态 `#e5e0d5`→`var(--c-line)`。
- [x] AC 5（回归 gate）：`cd code/main/miniapp && grep -rnE "var\(--c-(font-(sm|lg|xs|body|h1|h2|hero)|ink-[0-9]{2}|accent)" src` **无输出**（伪 token 清零），贴 raw output。
  > **AC5 正则修正（2026-06-01，复盘优先级 §1 改权威 spec）**：原正则用 `ink-[0-9]`（1 位数）会**误伤真 token** `--c-ink-2`/`--c-ink-3`（全站 91 处合法用法）。伪 token 实为 `--c-ink-60` 这类**2 位数**写法，故收紧为 `ink-[0-9]{2}` 才能只抓伪 token、不误伤真 token。改后该正则在 src 下零输出（实测 91 处合法 ink-2/3 均不命中）。
- [x] AC 6：**纯改皮，零运行时行为改动**（仅改 `<style>` + 1 处布尔 prop 绑定修正 + verify-scan 模板加竹绿状态条容器）；`pnpm type-check` 零 error（与 GZ-SYS-008 一并）+ vitest 114/114 全绿不回归。
- [x] AC 7（Tier 2 可达）：相关页本就有现成入口（FAB 全站常驻 / verify-scan 店员中心「核销」/ me 我的 tab），**无需新增临时入口**。真机视觉留 Kevin Tier 2 批量人验。

## Tech（端 + 范围）

- **小程序**（仅改 `<style>` / 模板属性，无 .ts 逻辑）：
  - `src/components/biz/BizCustomerServiceFab.vue`（D-1）
  - `src/pages/bean/verify-scan.vue`（D-3）
  - `src/pages/me/index.vue`（D-4）
  - `src/components/biz/BizSeatList.vue`（D-6）
  - JSDoc 注释清理（D-cleanup）
- **测试**：grep gate 伪 token 清零 + type-check 零 error + vitest 不回归。**无后端 / 无 DB / 无微信原生能力。**

## 备注

- **根因统一**：旧 `--brand-primary`（粉 `#FF6B81`）时代的 token 命名（`--c-font-*` 而非现行 `--c-fs-*`、`--c-ink-60`、`--c-accent-tint`）在换 C 皮时漏清。本票一次清干净 + AC5 grep gate 防回潮。
- **不进 Tier 2 视觉主观评判**之外的范围：admin 不动；不引新依赖；不改 token 真源数值（只把页面引用对齐到已有真 token）。
- success.vue 假 QR 网格**不在本票** —— 已属 GZ-BEAN-012 AC1 范围（detail.vue 已真 QR，success.vue 待补）。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-UI-001 revision 段 -->
