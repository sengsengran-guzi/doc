# GZ-ADMIN-107 — 扭蛋火花券店（v2 候选 · 本卡不实施代码）

**优先级**: P2
**复杂度**: —（本卡不实施；如未来 V2 启动重估为 M-L）
**关联 PRD**: doc/02-prd.md §5.2 **"V1.0 / V1.1 均不做扭蛋积分 / 代币 / 火花券兑换"**（PRD 与 mockup 早期不一致，已由 C3 裁定以 PRD 为准）
**关联拆解**: doc/02-需求拆解.md §3.5（火花券店标 v2 候选）
**关联 mockup**: `design/mockup/gacha-spark-shop.html`（**保留作 V2 视觉参考**，早期 designer 出图，未对齐 PRD §5.2）
**关联 ADR**: —（本卡不实施，无需 ADR；如未来 V2 启动再为"火花券店玩法 + 与 4% 分成口径关系"新建 ADR）
**依赖**: —（v2 候选，不进 V1.1 依赖图；若 V2 启动则依赖扭蛋出货 GACHA 域已落地）

---

## 必读权威文档

- **业务流**：doc/10 §8（扭蛋机抽奖全流程 — 火花券若做属此玩法分支；本卡仅作 V2 起点参考，不实施）
- **字段表**：doc/11 **附录 X.1 火花券店**（V2 候选实体字段名级占位：`gz_gacha_spark_balance` / `gz_gacha_spark_log` / `gz_gacha_spark_product` / `gz_gacha_spark_redeem` + sys_dict `gz_spark_change_type`）
- **UI 参考**：`design/mockup/gacha-spark-shop.html`（V2 视觉参考，不实施、不还原）

## What

**本 ticket 不实施任何代码** — 扭蛋火花券店（重复开盒累积火花券 → 火花商店兑换扭蛋奖品 / 实物）为 **V2 候选**，V1.0 / V1.1 均不做（Kevin C3 已裁定 2026-05-26）。本卡仅作 V2 候选占位，记录裁定与后续触发点。

> **盲盒语义提醒**（若未来 V2 实施）：UI 可见文案 / i18n key 用 扭蛋 / 开盒 / 获得 / 出现概率（禁 抽奖 / 中奖 / 开奖）；后端 enum / 字段可保留 draw。

## AC（验收标准）

> 本卡不实施代码，无可测试功能 AC；以下为"占位卡正确性"的客观核验项（可机械检查，非主观）。

- [ ] AC 1：本卡状态标 `deferred (v2)`，正文明确"V1.0 / V1.1 都不实施代码"，不含任何待实现的功能 AC / DDL / 接口。
- [ ] AC 2：mockup `design/mockup/gacha-spark-shop.html` 文件保留在仓库（作 V2 视觉参考），本卡不删、不实施、不还原。
- [ ] AC 3：doc/11 附录 X.1 火花券店占位记录存在且本卡正确引用（5 个 `gz_gacha_spark_*` 占位实体 + `gz_spark_change_type` 字典）。
- [ ] AC 4：本卡不产出 migration 文件、不产出 `org.dromara.gz.gacha.spark.*` 代码、不进 D15 依赖图波次，不阻塞 ADMIN-104 / 105 / 106 / 108 四张实做卡。

## Tech（端 + 范围）

**本卡不实施 → 无端、无范围、无 DDL、无代码。**

- 后端：不写（如 V2 启动落 `ruoyi-gz-gacha`，包名 `org.dromara.gz.gacha.spark.{controller,service,mapper,domain,dto}`）。
- Admin / 小程序：不写（mockup `gacha-spark-shop.html` 仅 V2 视觉参考）。
- DDL：不出。**如未来 V2 实施**，DDL 命名 `V<时间戳>__GZ-ADMIN-107-spark-shop.sql`（时间戳须 > 当前 migration 目录最大版本 V202606051200，按届时实际最大版本取更大值），字段以 doc/11 附录 X.1 升级为正式 §章节后为准。

## 备注

### 裁定与触发点

- **C3 裁定（2026-05-26，已拍板）**：火花券店 = **v2 候选**，V1.0 / V1.1 都不实施。理由：PRD §5.2 明确不做扭蛋积分 / 代币 / 火花券兑换；早期 designer 按"扭蛋常见玩法"出了 mockup（`gacha-spark-shop.html`），未对齐 PRD，矛盾已以 PRD 为准消化（doc/11 §7.6 / 附录 X.1 已记）。
- **触发点（不走会议决策框架）**：在**甲方 V1.0 验收沟通时一并过一句**（告知此玩法为 v2 候选、mockup 已留作参考）。**若甲方明确要求要做** → 走合同 **§8.5 大型新增功能另议**流程（单独评估 + 报价 + 排期，不并入 V1.1 实施位）。
- **与 4% 分成口径关系（V2 实施时必复核）**：火花券兑换不是销售（无 GMV、不计 4% 分成），若未来实施，对账中心（ADMIN-105 域 `gz_recon_*` / `business_type`）须明确将火花券兑换排除在 `preorder` / `gacha` 两条业务线核算之外。

### 强约束

1. 本卡**不阻塞 D15 其余 4 卡**（ADMIN-104 物流 2 态推进 / ADMIN-105 对账中心 / ADMIN-106 看板 / ADMIN-108 回收站），不进依赖图波次。
2. 不动 PRD §5.2（保持"不做火花券兑换"）；不动 doc/11 附录 X.1（保持 V2 占位）；不新建 ADR / migration / 代码。
3. mockup `gacha-spark-shop.html` 保留不删（V2 视觉参考）。

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 误把本卡当实做卡纳入 D15 波次 | D15/README.md 已标 `deferred (v2)`、不进依赖图；本卡 AC 4 客观核验"不产出代码 / 不进波次" |
| R2 | 未来 §0 自检误判仓库"已有火花券表" | §0 自检 **grep migration 目录确认上游表实际存在**（不假设）；火花券 `gz_gacha_spark_*` 表当前**应查不到 = 正常**（v2 候选未实施） |
| R3 | 甲方看 mockup 误以为 V1.1 含火花券店 | 甲方 V1.0 验收沟通时明确告知此为 v2 候选；如要做走合同 §8.5 另议 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!-- 本卡不实施代码，不进 Kevin testing-human 流程，无测试对象；如未来 V2 启动再新建实做卡。 -->
