# GZ-GACHA-103 — mp 单机详情 + 概率公示（实时归一化）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §用户操作流程 步骤 2-3 + §概率算法 + §关键页面
**关联拆解**: doc/02-需求拆解.md §3.3 GZ-GACHA-103
**关联 mockup**: design/mockup/gacha-detail.html（仅布局参考，不逐像素还原；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-GACHA-102（mp 扭蛋机列表，提供本页入口）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（**N2** 进单机详情含奖品池 + 实时归一化概率 / **N3** 看概率公示「不是后台配置原值」/ E4 概率公示实时归一化是合规要求不修复）。**不是 §7（预购流）**。
- **字段表**：doc/11-字段权威表.md **§7.1 `gz_gacha_machine`** + **§7.2 `gz_gacha_prize`**（含 §7.2 计算口径：`P = weight_i / Σ weight_j, j ∈ {enabled=1 AND stock_remain>0}`）
- **UI 参考**（mp ticket，视觉参考不强求逐像素）：doc/12-UI-权威索引.md **§MP-GACHA-DETAIL**（拟物扭蛋机 / 全部奖品网格 / 概率公示折叠区 + "合规 / 实时归一化"双标签外露）
- **设计 token**：doc/tokens.md **§1.4 稀有度色**（`--c-r-ssr` 金 / `--c-r-sr` 紫 / `--c-r-r` 蓝 / `--c-r-n` 灰，四档仅展示用）+ **§1.x 描边/硬投影**（`--c-stroke` / `--c-shadow*` / `--c-red` / `--c-paper`）
- **设计语言**：doc/13-设计语言-C日漫浓墨.md **§3.2 V1.1 待建**（`BizProbBar` 概率条 = 稀有度徽章 + 进度条 + 余量 + 合规实时公示；`RarityBadge` 稀有度徽章占位件）。**禁止引 tokens §9**（不存在；稀有度 / 概率公示权威 = tokens §1.4 + doc/13 §3.2）。

## What

mp 端单台扭蛋机详情页（只读浏览）：拟物扭蛋机视觉 + 全部奖品网格（按稀有度色边框）+ 底部"出现概率公示"折叠区（默认折叠，实时归一化）+ 底部 fixed CTA「单抽」按钮跳支付（→ GACHA-104）。盲盒语义全文严格。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/machine/{id}/detail` 返回机器主体（name / cover_image_id / single_price_cent / ten_pack_price_cent / status / online_time / offline_time / sales_count）+ 奖品列表 + 每条奖品的 `normalizedProbability` 字段（service 层算并返回，前端不重算）。**奖品列表不在后端按库存过滤**（`stock_remain=0` 的奖品也返回，前端灰显「已抽完」）。
- [ ] **AC 2**：归一化算法（service 层算并返回，与 doc/11 §7.2 计算口径一致）：
  - 入池集合 = 该机器下 `enabled=1 AND stock_remain>0` 的奖品；其 `weight` 数组归一化
  - 单条 `normalizedProbability = BigDecimal(weight_i / Σ weight_j) × 100`，HALF_UP 保留 2 位小数（如 `12.34`）
  - **不在入池集合**的奖品（`stock_remain=0` 或 `enabled=0`）`normalizedProbability` 返回 `null`，前端展示 `"—"`，不参与归一化分母
  - 边界：入池集合为空（全部库存 0 / 全部 disabled）→ 全部返回 `null`，CTA 置灰（机器应为 `auto_off` 态）
- [ ] **AC 3**：page `pages/gacha/detail.vue`（路径 `/pages/gacha/detail?id=`，对齐 doc/12 §MP-GACHA-DETAIL）：
  - **顶部 banner**：拟物扭蛋机（玻璃罩 + 胶囊 + 把手 + 出蛋口）— **CSS 实现**（`box-shadow` + `linear-gradient` + `transform`，不引 Lottie/动图）；视觉走 C 系统 `var(--c-*)`（粗墨边 `--c-stroke` + 硬投影 `--c-shadow`），mockup gacha-detail.html 仅布局参考
  - **机器信息条**：名称 + 单抽价（`--c-red` 朱红，价格永远朱红）+ 十连价（`ten_pack_price_cent` 非空才显示）+ 下架倒计时（`offline_time` 非空才显示）
  - **中部"全部奖品"网格（3 列）**：每张奖品卡按 `rarity` 配色边框（SSR `var(--c-r-ssr)` / SR `var(--c-r-sr)` / R `var(--c-r-r)` / N `var(--c-r-n)`）+ 稀有度徽章（`RarityBadge` 占位件，doc/13 §3.2）+ `stock_remain=0` 灰显「已抽完」遮罩 + 图片走 `image_id` 换签名 URL（无 image_id → MOCK 占位色块）
  - **底部"出现概率公示"折叠区**（默认折叠，用 wd-collapse 一层 Biz 包装）：
    - 折叠头部并排两个外露标签：「合规」「实时归一化」
    - 展开内容用 `BizProbBar`（doc/13 §3.2）：逐奖品一行 = 稀有度徽章 + 名称 + 进度条 + `出现概率%`（按概率降序；`stock_remain=0` 显示 `"—"` 排末尾）
    - 公示说明文案："出现概率为按当前在池剩余库存归一化后的实时值，不构成保底承诺"
  - **底部 fixed CTA 条**（BizFixedCta，纸底 `--c-paper` + 顶部粗墨边 + 安全区）：「单抽 ¥X」按钮（`--c-red` 朱红）→ 跳支付（GACHA-104）；入池集合为空时按钮置灰禁用
- [ ] **AC 4**：盲盒语义（仅 gacha 域，硬约束）：mp 可见文案 + `t('gacha.detail.*')` key **禁** "抽奖 / 中奖 / 开奖 / 中奖概率 / 中奖率"；**用** "扭蛋 / 开盒 / 获得 / 出现概率"。概率公示首行金句：「100% 获得，概率为获得对应商品的可能性」。grep 验证无禁用词。
- [ ] **AC 5**：业务组件包一层（`src/components/biz/`，easycom 自动引入）：`BizGachaMachineHero.vue`（拟物机器视觉）+ `BizPrizeGridCard.vue`（奖品卡）+ `BizProbBar.vue`（概率公示条，doc/13 §3.2）；页面不直接撒 `<wd-*>` 标签。
- [ ] **AC 6**：i18n 走 `t('gacha.detail.xxx')` + zh-CN 默认；不混 emoji。
- [ ] **AC 7**：单测 happy + 边界（归一化算法）：① 正常多奖品归一化（和 ≈ 100）；② 仅 1 个奖品有库存（该条 = 100.00）；③ 全部库存=0（全 null）；④ disabled 奖品不入池；⑤ weight 总和巨大不溢出（用 BigDecimal）。
- [ ] **AC 8: Tier 2 入口可达**（mp 强制，CLAUDE.md §8.3）— Kevin 从 **MP-GACHA-LIST 扭蛋机列表（GACHA-102 已建）** 点 1 次任一机器卡 → 进入本详情页。GACHA-102 列表卡跳转 `?id=` 即本页现成入口，**不加临时入口**。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaMachineMpController.java` 加 `getDetail(@PathVariable machineId)`，路由 `/app/gz/gacha/machine/{id}/detail`
  - `service/impl/GzGachaMachineServiceImpl.java` 加 `getDetailForMp(machineId)`：查机器 + 该机器全部奖品（不过滤库存）+ 调归一化器算每条概率
  - `service/internal/ProbabilityNormalizer.java`（独立 Bean）：入参奖品列表，对 `enabled=1 AND stock_remain>0` 子集 `weight` 归一化，返回 `Map<prizeId, BigDecimal>`（不在池的不入 map / 返回 null）。**GACHA-104 抽奖事务内复用同一 Bean** 保证概率口径一致
  - 新增 VO `GzGachaMachineDetailVO`（机器主体 + `List<GzGachaPrizeVO>`，每条含 `normalizedProbability`）
  - **DDL**：本卡为只读详情接口，**无新表 / 无 schema 变更**，不产生 migration 文件（上游表 `gz_gacha_machine` / `gz_gacha_prize` 由 GACHA-101 建）。若实施中确需加索引等 schema 变更，DDL 命名 `V<yyyyMMddHHmm>__GZ-GACHA-103-<desc>.sql`（时间戳 > 当前最大 `V202606051200`；已应用迁移不可改）
- **小程序**：`code/main/miniapp/`
  - `src/pages/gacha/detail.vue`
  - `src/components/biz/BizGachaMachineHero.vue` + `BizPrizeGridCard.vue` + `BizProbBar.vue`（+ 复用 `RarityBadge` 占位件）
  - `src/api/gz-gacha.ts` 加 `getMachineDetail(id)`
- **测试**：mvn（`ProbabilityNormalizer` 纯逻辑单测）+ vitest（前端归一化展示 / 降序排序，如有纯函数）

## 备注

### 强约束

1. **概率公示默认折叠**（doc/12 §MP-GACHA-DETAIL）+「合规」「实时归一化」双标签外露（不引 tokens §9，权威 = doc/12 §MP-GACHA-DETAIL + doc/13 §3.2）。
2. **归一化在 service 层算并返回**（前端不重算）— 避免前端 / 后端 / GACHA-104 三处算法实现不一致。
3. **`ProbabilityNormalizer` 抽独立 Bean** — GACHA-104 抽奖事务内复用同一实现（核心算法一致性是 GACHA-104 的兜底前提）。
4. **入池口径锚定 doc/11 §7.2 计算口径**：`enabled=1 AND stock_remain>0`，**字段名 `stock_remain`（不是 current_stock / left）**；初始库存字段是 `stock_initial`（doc/11 §7.2），不用 stock_total。
5. **盲盒语义全文严格**（D09 README §B）：UI 文案 / i18n key 用扭蛋语义，禁抽奖 / 中奖 / 开奖。
6. **拟物视觉 CSS 实现**（不引 Lottie）— 性能 + 微信兼容。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 归一化算法抽 `ProbabilityNormalizer` 独立 Bean | 详情页展示概率 / GACHA-104 抽奖核心都用同一算法，避免不一致（doc/10 §8 E3/E4 一致性优先）|
| D2 | 详情接口返回全部奖品（含 stock_remain=0 灰显，不后端过滤）| 用户能看到"已抽完"的物品，激励"早抽早赚"心理；前端区分而非后端过滤 |
| D3 | 概率展示 BigDecimal HALF_UP 保留 2 位小数 | 商业惯例；权重归一化精度足够（接受总和 99.9X% 误差）|
| D4 | "100% 获得"金句硬编码到组件 | 合规 + 营销核心金句；en-US 暂不支持（海外业务在合同 §2.3 外）|
| D5 | 概率公示组件用 doc/13 §3.2 `BizProbBar` | 与权威待建组件对齐，GACHA-104/105 复用稀有度徽章口径 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 上游表未建本卡无法实施 | **§0 自检 `grep` migration 目录确认 `gz_gacha_machine` / `gz_gacha_prize` 实际存在**（GACHA-101 落地后），不假设上游已建；不存在 → STOP，挂起等 GACHA-101 |
| R2 | 拟物视觉在不同微信版本兼容 | CSS 用 `box-shadow` + `linear-gradient` + `transform`，主流版本全支持；老版本 fallback 渐变背景 + 文字标签 |
| R3 | 概率归一化精度（如 weight 总和导致末位漂移）| BigDecimal HALF_UP 保留 2 位；接受总和 99.9X% 误差，公示说明文案标注"实时值不构成保底承诺" |
| R4 | `stock_remain=0` 奖品仍参与归一化分母 | 归一化前过滤 `enabled=1 AND stock_remain>0`（doc/11 §7.2 计算口径）；不在池的 `normalizedProbability` 返回 null |
| R5 | mockup gacha-detail.html 文案仍含"抽奖"/双 CTA 立省贴纸 | 实施改 `t()` 文案（盲盒语义），不动 mockup 文件；十连 CTA 视 `ten_pack_price_cent` 是否非空决定是否显示（十连交易在 GACHA-104 决定是否启用，本卡仅展示价格）|

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D09/GZ-GACHA-103 revision 段`：

- 问题 1：<现象> / 期望：<期望>

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
