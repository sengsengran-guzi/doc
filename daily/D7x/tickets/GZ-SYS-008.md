# GZ-SYS-008 — mp type-check 噪音清零

**优先级**: P2
**复杂度**: S
**关联**: kevin-coder 在 GZ-SYS-007 自测时发现的预存 TS 错误（非本批次引入，但 D7x 要求完整收口，不留尾）

> **由来**：D7x 实施中发现 miniapp 有预存 type-check 错误（`BizCustomerServiceFab.vue` / `login/index.vue` 各 1 处），与本批次无关但一直在。按 D7x「测试期问题完整解决、不推后」原则一并清掉。

---

## What

把 miniapp `pnpm type-check` 跑干净：定位并修复全部预存 TS 错误（已知 `BizCustomerServiceFab.vue` / `login/index.vue` 各 1 处，实施时以 type-check 实际输出为准，可能还有其它）。不改业务逻辑，只修类型。

## AC（验收标准）

- [x] AC 1：`cd code/main/miniapp && pnpm type-check`（vue-tsc --noEmit）**零 error**，exit=0，raw output 见 report。
- [x] AC 2：**真修类型**，零 `any` / 零 `@ts-ignore`：① `BizCustomerServiceFab.vue:92` `show-message-card="false"`（字符串）→ `:show-message-card="false"`（布尔绑定，修 TS2322）；② `login/index.vue:35` `uni.switchTab({...}).catch()`（在 void 上调 catch，TS2339）→ 改用 uni-app 的 `fail` 回调（语义等价，类型干净）。
- [x] AC 3：纯类型修复，运行时行为等价（`:show-message-card="false"` 与原 `"false"` 渲染一致；`fail` 回调与原 `.catch` fallback 逻辑一致）；vitest 114/114 全绿。

## Tech（端 + 范围）

- **小程序**：`miniapp/`（type-check 报错的文件，已知 `src/components/biz/BizCustomerServiceFab.vue`、`src/pages/login/index.vue`）
- **测试**：type-check 零 error + 既有 vitest 不回归

## 备注

- 纯前端类型清理，无后端 / 无 DB / 无微信原生能力 → 不进 Tier 2 人验（仅 Tier 1A/1B）。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-SYS-008 revision 段 -->
