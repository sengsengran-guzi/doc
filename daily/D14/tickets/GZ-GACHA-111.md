# GZ-GACHA-111 — 扭蛋入口迁「我的」+ 端到端做活回归（最低优先级，本日最后）

**优先级**: P2（本日最后一项）
**复杂度**: S
**关联 PRD**: doc/02-prd.md M2 §V1.2 定位调整（降开发优先级，入口迁「我的」，排最后）
**关联拆解**: doc/02-需求拆解.md §3.6.6 GZ-GACHA-111
**关联 ADR**: -
**依赖**: GZ-SYS-010（「我的」tab 扭蛋入口卡 + tabbar 已迁扭蛋入口）+ GACHA-101~104（V1.1 已交付，gacha-list/detail/draw）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **PRD**：doc/02-prd.md M2 §V1.2 定位调整（扭蛋降开发优先级 = 入口迁「我的」+ 做活回归，**不改概率/weight**）
- **UI 参考**：doc/12 §MP-GACHA-LIST（扭蛋机大厅 V1.2 做活，入口迁「我的」）+ §4.0「我的」扭蛋入口卡 → MP-GACHA-LIST

## What

扭蛋（V1.1 已建）入口从「我的」tab 入口卡进入（配合 SYS-010），**保留 `pages/gacha` 做活非 ComingSoon**。端到端做活回归：「我的」→ 扭蛋入口 → 列表 → 单机详情（概率公示）→ 投币 → JSAPI 支付（mock）→ 开盒事务出 1 件 → 出奖动画 → 进待发货订单。**降开发优先级 = 仅入口迁移 + 做活回归，不改概率/不改 weight 数据/不动抽奖逻辑**。

## AC（验收标准）

- [ ] AC 1：**入口接通**：SYS-010 已建「我的」扭蛋入口卡 → 本卡接通入口卡跳 `pages/gacha`（做活非 ComingSoon）。清理扭蛋相关历史临时入口（grep `Tier2-entry-temp`，GZ-GACHA-106 等）用「我的」入口卡真入口替换（与 SYS-010 协同，避免重复清理）。
- [ ] AC 2：**端到端做活回归**：从「我的」→ 扭蛋入口卡 → 扭蛋机列表（BizGachaMachineCard）→ 单机详情（概率公示 BizProbBar）→ 投币 → JSAPI 支付（mock，wxMOCK 短路）→ 开盒事务出 1 件 → 出奖动画（BizGachaDraw）→ 进待发货订单，全链路跑通无回归（GACHA-101~104 既有逻辑不破坏）。
- [ ] AC 3：**降开发优先级硬约束**：`git diff` 应仅含 mp 入口接通 + 必要回归修复，**不含 `gz_gacha_prize.weight` 数据 / 概率逻辑 / 抽奖事务改动**。reports 必含 `git diff --stat` 自证无 weight/概率改动。
- [ ] **AC 4: Tier 2 入口可达**（mp 强制）：Kevin 从「我的」点扭蛋入口卡 1 次到达扭蛋机列表，可走完一次做活（mock 支付）。

## Tech（端 + 范围）

- **小程序**：`miniapp/src/pages/me/index.vue` 扭蛋入口卡接通（SYS-010 已建卡）+ `pages/gacha/*` 清理临时入口；如做活回归发现 bug 仅修回归不改概率。无新增后端/表/menu。
- **测试**：做活回归走 mock 全链路（手动/vitest 既有 gacha 单测不破坏）。

## 备注

- 本日最后一项：SYS-010 完工（入口卡 + tabbar）后再 spawn。
- R10 纠正点：本卡是「权重放低」误解的纠正 = 仅入口迁移 + 做活回归，无任何 weight 数据调整（原 GACHA-110 权重卡已删）。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 待 Kevin 批量人验填 -->
