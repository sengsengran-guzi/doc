# GZ-ADMIN-107 ⚠️ — 扭蛋火花券店（placeholder / 待甲方决策）

**优先级**: P2（暂） — 默认 v2 推迟
**复杂度**: M（如确认升 V1.1 实施）
**关联 PRD**: doc/02-prd.md §5.2 **"不做扭蛋积分 / 代币兑换"** ⚠️ vs `design/mockup/gacha-spark-shop.html` 已存（早期 designer 出图未对齐 PRD）
**关联拆解**: doc/02-需求拆解.md §3.5 第 998 行（明确标注 placeholder + §8.1 待确认事项）
**关联 mockup**: `design/mockup/gacha-spark-shop.html`（已存但暂不实施 — 留作 5/31 甲方决策参考素材）
**关联 ADR**: —（如甲方决策升 V1.1 → 新建 ADR-V1.1-GACHA-SPARK 记录"为何 PRD vs mockup 不一致仍要做" + 工时影响 + 合同 §8.5 变更评估）
**依赖**: GZ-GACHA-104（扭蛋出货 + 火花券积累 — 如甲方确认升 V1.1，本 ticket 才有数据源）

---

## ⚠️ 本 ticket 状态：placeholder / 暂不实施

**本 ticket 暂不实施代码**，仅产出占位任务卡，等 Kevin × 甲方决策后定调。

### 矛盾来源

- **PRD §5.2 明确**："V1.0 / V1.1 均不做扭蛋积分 / 代币 / 火花券兑换；扭蛋出货价值由 SKU 直接交付，无二次兑换中间态"
- **mockup 已出**：`design/mockup/gacha-spark-shop.html` 早期 designer（V1.0 设计初期）按"扭蛋常见玩法"画了火花券兑换店，未与 PRD 对齐就出图
- **二者矛盾未消化**：02-需求拆解 §8.1 记录待确认事项；本 ticket 占位等决策

### 5/31 PRD v1.0 签字会议带去对甲方的话术

> "扭蛋火花券兑换店这个功能 mockup 早期画了一版，但 PRD 里明确不做（理由：火花券积累 + 兑换池运营成本高，V1.1 工期 6/16-7/31 装不下）。要不要做你拍板：
>
> 选项 A：**默认 v2 推迟**（推荐）— PRD 不动 / mockup 在备注里加"v2 候选"标记 / 本 ticket 标 archived
> 选项 B：**升 V1.1** — 需要 +1.5 天工时（合同 §8.1 月 40h 范围内可吸收）+ V1.1 上线日从 7/31 推到 8/05（建议保守报 8/15）/ 走合同 §8.5 变更评估流程出补充协议
>
> 你倾向？"

### 甲方决策路径

| 甲方选择 | 后续动作 |
|---|---|
| A（默认 v2 推迟） | 本 ticket 标 `archived` / mockup 文件改名 `gacha-spark-shop.v2-candidate.html` / PRD §5.2 不动 / 02-需求拆解 §8.1 该项关闭 |
| B（升 V1.1） | 新建 ADR-V1.1-GACHA-SPARK 记录决策 / PRD §5.2 改"V1.1 做火花券兑换店" / 02-需求拆解 §3.5 第 998 行从 P2 改 P1 / 本 ticket 任务卡补 What/AC（参见下方"如升 V1.1 补的 AC 草稿"）/ 拍板 D12 或合并到 D11 收尾 / 合同 §8.5 出补充协议 |

---

## What（如升 V1.1 实施 — 仅草稿，待决策后补完）

C 端用户在扭蛋玩法中积累的"火花券"（不重复中奖时累积的代币）可在专门的"火花券店"兑换商品 SKU（消耗火花券 + 配送实物或虚拟卡密）。

## AC 草稿（如升 V1.1，待决策后补完）

- [ ] 待补 — 占位
- [ ] 待补 — 占位
- [ ] 待补 — 占位

## Tech 草稿（如升 V1.1 — 仅范围预估）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - 新建 `gz_spark_token_balance`（用户火花券余额）
  - 新建 `gz_spark_shop_sku`（兑换 SKU 池）
  - 新建 `gz_spark_redeem_order`（兑换订单）
  - GZ-GACHA-104 扭蛋出货时同步发火花券（不重复中奖时累 N 券）
- **mp 前端**：`pages/gacha/spark-shop/` 列表 + 详情 + 兑换提交（参考 mockup `gacha-spark-shop.html`）
- **admin 端**：火花券店 SKU CRUD + 兑换订单管理

---

## 备注

### 强约束（如升 V1.1）

1. **必须先消化 PRD vs mockup 矛盾**（9.5 §1 改源头）— PRD §5.2 改"V1.1 做" / 02-需求拆解 §8.1 关闭
2. **合同 §8.5 变更评估流程** — 出补充协议 / 工时 +1.5 天 / V1.1 上线日延期
3. **ADR-V1.1-GACHA-SPARK 必写** — 记录决策原因 + 工时影响 + 风险
4. **火花券兑换订单 vs 业务线 A/B 归属** — 兑换不是销售（无 GMV，无 4% 分成）→ ADMIN-105 对账中心需要排除 spark_redeem_order

### 风险提示（如升 V1.1）

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 工时挤压 6/22 起 staging 期 | 合同 §8.5 出补充协议 / V1.1 上线日延期 |
| R2 | 火花券兑换被算到对账中心（误入业务线 B GMV）| ADMIN-105 聚合 SQL 排除 spark_redeem_order |
| R3 | mockup 已存但 PRD 字段不全（火花券发放规则不明） | Kevin × 甲方补 PRD §5.x 章节 / 不能直接照 mockup 画 |

### 默认路径（最可能场景）

**默认 v2 推迟（选项 A）**：本 ticket 5/31 会议后标 archived，mockup 改名加"v2-candidate"后缀，02-需求拆解 §8.1 关闭。

---

## §revision（Kevin testing-human 后填，初始空）

⚠️ 本 ticket 不进 Kevin testing-human 流程 — 暂不实施代码，无测试对象。
