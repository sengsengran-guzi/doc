# GZ-GACHA-103 — mp 单机详情 + 概率公示

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §用户操作流程 步骤 2 + §概率算法 + §关键页面
**关联拆解**: doc/02-需求拆解.md §3.3 第 772 行
**关联 mockup**: design/mockup/gacha-detail.html（仅布局参考；视觉以 C 系统为准，doc/13；概率条为 doc/13 §3.2 待建 Biz 组件 BizProbBar）
**关联 ADR**: —
**依赖**: GZ-GACHA-102

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md §7 扭蛋抽奖流（步骤 2 详情 + 步骤 3 单抽确认 CTA）
- **字段表**：doc/11-字段权威表.md §7.1 `gz_gacha_machine` + §7.2 `gz_gacha_prize`
- **UI 索引**：doc/12-UI-权威索引.md **§MP-GACHA-DETAIL**（拟物扭蛋机视觉 / 奖品网格 / 概率公示折叠区）
- **tokens.md §9**：拟物扭蛋机（玻璃罩 + 胶囊 + 把手 + 出蛋口）+ 概率公示默认折叠 + "合规 / 实时归一化"双标签外露 + 盲盒语义

## What

mp 端单台扭蛋机详情页：拟物扭蛋机视觉 + 全部奖品网格（按稀有度色）+ 底部"出现概率公示"折叠区 + CTA「单抽」按钮跳支付（GACHA-104）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/machine/{id}/detail` 返回机器主体 + 奖品列表（全部含库存=0 灰显，前端区分；不在后端过滤）+ **归一化后的出现概率**（按当前在池有库存的奖品 weight 重算）
- [ ] **AC 2**：page `pages/gacha/detail.vue`：
  - **顶部 banner**：拟物扭蛋机（玻璃罩 + 胶囊 + 把手 + 出蛋口）— CSS 实现，mockup gacha-detail.html 仅作布局参考；视觉走 C 系统 var(--c-*)（粗墨边 + 硬投影），doc/13
  - **中部"全部奖品"网格**（3 列）：每张奖品卡按 rarity 配色边框（SSR 金 var(--c-r-ssr) / SR 紫 var(--c-r-sr) / R 蓝 var(--c-r-r) / N 灰 var(--c-r-n)）+ 稀有度徽章（doc/13 §3.2 待建 Biz 组件）+ 库存=0 灰显「已抽完」遮罩
  - **底部"出现概率公示"折叠区**（默认折叠，wd-collapse）：
    - 折叠头部并排两个标签：「合规」「实时归一化」
    - 展开内容：表格列出每个奖品（名称 / 稀有度 / 出现概率%，按概率降序）
    - 表头说明："出现概率为按当前在池剩余库存归一化后的实时值，不构成保底承诺"
  - **底部 fixed CTA 条**（BizFixedCta，纸底 + 顶部粗墨边 + 安全区）：「单抽 ¥X」按钮（var(--c-red) 朱红）→ 跳支付（GACHA-104）
- [ ] **AC 3**：归一化算法（前端展示 + 后端返回一致）：
  - 输入：所有 current_stock > 0 的奖品 weight 数组
  - 输出：每个奖品 weight / sum(weights) × 100，保留 2 位小数
  - 库存=0 的奖品概率显示 "—"（不参与归一化）
- [ ] **AC 4**：盲盒语义（tokens.md §9）：
  - ❌ "中奖概率" / "中奖率"
  - ✅ "出现概率" / "出现率"
  - 概率公示首行金句：「100% 获得，概率为获得对应商品的可能性」
- [ ] **AC 5**：业务组件包一层：`components/biz/BizGachaMachineHero.vue`（拟物视觉）+ `components/biz/BizPrizeGridCard.vue`（奖品卡）+ `components/biz/BizProbabilityPanel.vue`（公示折叠区）
- [ ] **AC 6**：i18n 走 `t('gacha.detail.xxx')`
- [ ] **AC 7**：单测 happy（归一化算法在边界情况：全部库存=0 / 单 1 奖品有库存 / 权重总和巨大不溢出）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaMachineMpController.java` 加 `getDetail(machineId)` 方法
  - `service/impl/GzGachaMachineServiceImpl.java` 加 `getDetailForMp(machineId)`：查机器 + 所有奖品 + 归一化（service 层算，不放数据库）
  - `service/internal/ProbabilityNormalizer.java`（独立 Bean — GACHA-104 也会复用归一化逻辑）
  - 新增 VO `GzGachaMachineDetailVO`（含 prizes 数组 + 每条 normalizedProbability 字段）
- **小程序**：
  - `pages/gacha/detail.vue`
  - `components/biz/BizGachaMachineHero.vue` + `BizPrizeGridCard.vue` + `BizProbabilityPanel.vue`
  - `api/gz-gacha.ts` 加 `getMachineDetail(id)`
- **测试**：mvn + vitest（归一化纯函数单测）

## 备注

### 强约束

1. **概率公示默认折叠**（tokens.md §9）+ "合规"+"实时归一化"双标签外露
2. **归一化在 service 层算并返回**（前端不重算）— 避免前端 / 后端 / GACHA-104 三处算法实现不一致
3. **`ProbabilityNormalizer` 抽独立 Bean** — GACHA-104 抽奖事务内也会用同一实现（核心算法一致性是 GACHA-104 风险点 R3 的兜底）
4. **盲盒语义全文严格**（tokens.md §9）
5. **拟物视觉 CSS 实现**（不引 Lottie）— 性能 + 兼容

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 归一化算法抽 `ProbabilityNormalizer` 独立 Bean | 详情页展示概率 / GACHA-104 抽奖核心都用同一算法，避免不一致 |
| D2 | 详情接口返回全部奖品（含 stock=0 灰显）| 用户能看到"已抽完"的物品，激励"早抽早赚"心理；前端区分而非后端过滤 |
| D3 | 概率展示保留 2 位小数（如 12.34%）| 商业惯例；权重归一化精度足够 |
| D4 | "100% 获得"金句硬编码到组件 | 是合规 + 营销核心金句，不走 i18n 抽取（en-US 暂不支持，海外业务在合同 §2.3 外）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 拟物视觉在不同微信版本兼容性 | CSS 用 box-shadow + linear-gradient + transform，主流版本全支持；老版本 fallback 渐变背景 + 文字标签 |
| R2 | 概率归一化精度（如 weight 总和 99 但展示 3 位）| 保留 2 位 + 用 BigDecimal HALF_UP 舍入；总和近似 100%（接受 99.9X% 误差）|
| R3 | 库存=0 的奖品仍在 weight 数组里参与归一化 | service 层归一化前过滤 stock=0 的奖品 |
| R4 | mockup gacha-detail.html 文案仍含"抽奖" | 实施时改 t() 文案，不动 mockup 文件 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
