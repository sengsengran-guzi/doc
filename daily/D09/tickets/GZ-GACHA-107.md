# GZ-GACHA-107 — mp 图鉴（按机器分组 + 集齐徽章 + 重复角标，V1.1 简版）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 扭蛋机（收集驱动）
**关联拆解**: doc/02-需求拆解.md §3.3（**V1.1 简版，深化推 v2**）
**关联 mockup**: design/mockup/me-collection.html（布局 / 视觉参考，不逐像素还原；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-GACHA-105（揭晓页底部「查看图鉴」入口）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。
> UI 索引 V1.0 设计冻结期降级为视觉参考；本 ticket 是 V1.1 新页，mp 视觉走 C 系统。

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程 N9**（揭晓后「图鉴进度 +1」更新 `gz_user_gacha_collection`；本卡是 N9 的查询/展示端）+ **Q8.2 / Q8.4**（图鉴 V1.1 简版仅展示徽章、不解锁功能、不发实物）。**不是 §7（预购流）**。
- **字段表**：doc/11-字段权威表.md **§7.5 `gz_user_gacha_collection`**（图鉴数据源：`user_id` / `machine_id` / `prize_id` / `first_drawn_time` / `drawn_count`；UNIQUE `(tenant_id,user_id,machine_id,prize_id)`）+ **§7.1 `gz_gacha_machine`** + **§7.2 `gz_gacha_prize`**（全集 + 稀有度 + `image_id`）。
- **UI 索引**：doc/12-UI-权威索引.md **§MP-ME-COLLECTION**（V1.1 简版已裁定：按机器分组 + 已得高亮 locked/unlocked + 集齐徽章实时 COUNT；不维护「徽章拿到没」字段）。
- **视觉 token**：doc/tokens.md **§1.4 稀有度色**（SSR `var(--c-r-ssr)` / SR `var(--c-r-sr)` / R `var(--c-r-r)` / N `var(--c-r-n)`，四档不引第五档）+ doc/13-设计语言 **§3.2**（`BizProbBar` 进度条待建组件）。**禁止引 tokens §9（不存在）**。

## What

mp 会员中心「我的图鉴」页：以 `gz_user_gacha_collection` 表为数据源，按机器分组展示用户**已获得 vs 未获得**的奖品全集（已得彩色高亮 + 稀有度边框 + 重复 ×N 角标 / 未得灰显锁标），某机器全集齐时显示集齐徽章。**V1.1 简版**：徽章纯展示、不发实物、不解锁任何功能、无分享 / NFT / 套装（深化推 v2）。

## AC（验收标准）

- [ ] **AC 1**：mp 接口 `GET /app/gz/gacha/collection/my?machineId=`（sa-token mp-client → 当前 user_id）：
  - **数据源是 `gz_user_gacha_collection` 表查询，不是对 `gz_gacha_draw` 做 distinct 聚合**（重复获得靠表上 `drawn_count`；每次开盒必出并在开盒事务内 UPSERT collection +1、无退款回滚，故图鉴数据完整）。
  - 入参 `machineId` 传 → 仅返回该机器分组；不传 → 返回该用户在 collection 中出现过的**所有机器**分组。
  - 返回 `GzGachaCollectionVo`：`machines` 数组，每项含 `machineId` / `machineName` / `coverImageId`（FK，非裸 url）/ `totalCount`（该机器奖品全集数）/ `ownedCount`（已得种类数）/ `isCompleteSet`（boolean）/ `prizes` 数组。每个 prize 含 `prizeId` / `name` / `imageId` / `rarity`（SSR/SR/R/N）/ `owned`（boolean）/ `drawnCount`（已得 = 重复次数，未得 = 0）/ `firstDrawnTime`（未得为 null）。
- [ ] **AC 2**：**集齐判定基于 prize 全集**（含 `stock_remain=0` 已抽空、含 `status=auto_off` 自动下架的奖品；但**排除 `del_flag=2` 已删除**）：`isCompleteSet = (该机器 prize 全集 distinct prize_id 集合) ⊆ (该用户该机器 collection 的 prize_id 集合)`，即 `ownedCount == totalCount` 且 `totalCount > 0`。
- [ ] **AC 3**：page `pages/me/collection.vue`：
  - 顶部机器筛选条（首项「全部」，其余为用户已收集机器名）。
  - 按机器分组卡片：头 = 机器封面（`coverImageId` 解析 gz_file_object）+ 名称 + 进度文案「已收集 X/Y 件」+ 进度条（`BizProbBar`，doc/13 §3.2；填充 `var(--c-r-ssr)` 金 / 描边 `var(--c-bw)`）+ 集齐时徽章。
  - 内容 = 奖品 3 列网格：已得高亮（彩色 + 按稀有度边框 `var(--c-r-ssr/-sr/-r/-n)` + `drawnCount>1` 时右上角 ×N 角标）/ 未得灰显（CSS `filter: grayscale(1) opacity(.35)` + 锁标）。
- [ ] **AC 4**：奖品格子交互：
  - 已得格点击 → popup 展示奖品名 + 稀有度 + `firstDrawnTime`（首次获得时间）+ `drawnCount`（共获得 N 件）+ 「查看记录」CTA → 跳 `pages/gacha/history`（GACHA-106 抽奖历史）。
  - 未得格点击 → popup「还差 X 件集齐该机器」+ 「去开盒」CTA → 跳该机器详情 `pages/gacha/detail?id=<machineId>`（GACHA-103）。
- [ ] **AC 5**：集齐徽章：`isCompleteSet=true` → 进度条满格 + 机器卡头显示集齐徽章（`RarityBadge` 风格，金色 `var(--c-r-ssr)` + 粗墨边）+ chip 文案「集齐特典 — 已解锁」。**仅展示，不发实物 / 不解锁功能 / 不写「徽章拿到没」DB 字段**（doc/10 Q8.4 + doc/11 §7.5）。
- [ ] **AC 6**：盲盒语义（仅 gacha 域硬约束）：页面标题「我的图鉴」；可见文案用 **获得 / 开盒 / 出现概率 / 已收集**；**禁** 抽奖 / 中奖 / 开奖。i18n key 全走 `t('gacha.collection.xxx')`（或 `t('me.collection.xxx')` 命名空间统一二选一，与 GACHA-105/106 对齐），zh-CN 默认，不混 emoji。
- [ ] **AC 7**：业务组件包一层放 `components/biz/`（不直接撒 `<wd-*>`）：
  - `BizCollectionMachineGroup.vue`（机器分组卡）
  - `BizCollectionPrizeCell.vue`（奖品格 — 已得 / 灰显 / ×N 角标）
  - `BizCompleteSetBadge.vue`（集齐徽章）
  - 进度条复用 `BizProbBar`（doc/13 §3.2；若 GACHA-103 已建则复用，未建则本卡建并标注供 103 复用）。
- [ ] **AC 8**：单测（vitest mp + mvn service）覆盖：
  - 部分集齐：mock 机器 3 奖品 / 用户 collection 含 2 条 → `ownedCount=2,totalCount=3,isCompleteSet=false`；其中 1 条 `drawn_count=3` → 该 prize `drawnCount=3`。
  - 全集齐：mock 3 奖品 / 用户 collection 含 3 条（含 1 条对应 `stock_remain=0` 已抽空奖品）→ `isCompleteSet=true`。
  - 空：用户 collection 无任何记录 → `machines=[]`。
  - 含 auto_off 奖品仍计入全集；含 `del_flag=2` 奖品**不计入**全集（删除后不影响集齐判定）。
- [ ] **AC 9: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从已有入口点 1 次到达本页：
  - 主入口：GACHA-105 揭晓页底部「查看图鉴」按钮 → 跳本页（依赖卡，正常路径）。
  - 兜底临时入口：若 GACHA-105 入口尚未 merge，本卡加临时入口到 `pages/index/index.vue`（占位区）+ 注释 `<!-- TODO(Tier2-entry-temp): GZ-GACHA-107, remove when GZ-GACHA-105 揭晓页「查看图鉴」入口 merged -->`。

## Tech（端 + 范围）

- **后端**（只读，无 DDL — 表由 GACHA-104 建）：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaCollectionMpController.java`（前缀 `/app/gz/gacha/collection`，sa-token mp-client 取 user_id；纯顾客可调，无需 `@SaCheckPermission`）
  - `service/IGzGachaCollectionService.java` + `impl/GzGachaCollectionServiceImpl.java`，装配逻辑：
    1. 查用户 distinct `machine_id`（`SELECT DISTINCT machine_id FROM gz_user_gacha_collection WHERE user_id=?`，租户自动过滤）。
    2. 按 machine 查 `gz_gacha_prize` 全集（`del_flag=0`，含 `stock_remain=0` / `status=auto_off`）。
    3. 按 machine 查用户 collection 行（`prize_id` → `drawn_count` / `first_drawn_time` 映射）。
    4. 装配 prize 数组（`owned` = 该 prize_id 在用户 collection map 中）+ 计算 `ownedCount` / `totalCount` / `isCompleteSet`。
  - VO：`domain/vo/GzGachaCollectionVo.java`（含嵌套 `MachineGroupVo` → `PrizeCellVo`）。`coverImageId` / `imageId` 走 image_id FK（前端解析 gz_file_object），**不返回裸 url**。
  - 包名 `org.dromara.gz.gacha.{controller,service,mapper,domain.vo}`。
  - **DDL：本卡无新表 / 无菜单**（mp C 端只读接口，不进 admin menu_id 段；如未来需 admin 图鉴看板另开 ticket 走 10100 段）。
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/collection.vue`
  - `components/biz/BizCollectionMachineGroup.vue` + `BizCollectionPrizeCell.vue` + `BizCompleteSetBadge.vue`（+ 复用 / 建 `BizProbBar`）
  - `api/gz-gacha.ts` 加 `getMyCollection(machineId?)`
- **测试**：mvn 单测（service 装配 + 集齐判定）+ vitest（VO → 视图态映射）+ 微信开发者工具实操图鉴页。

## 备注

### 强约束

1. **数据源 = `gz_user_gacha_collection` 表查询**，**不是** `gz_gacha_draw` distinct 聚合（任务硬铁律）。重复获得靠表上 `drawn_count` 角标；每次开盒必出并在开盒事务内 UPSERT collection +1（失败重抽改派、无退款回滚，doc/11 F7.3），故图鉴数据完整、无缺漏。
2. **集齐判定基于 prize 全集**（含已抽空 `stock_remain=0` / 自动下架 `auto_off`），否则用户抽走最后 1 个 SSR 后该奖品库存归 0 会导致永远集不齐。排除 `del_flag=2`（删除即移出全集）。
3. **V1.1 简版**（doc/02 §3.3 + doc/10 Q8.2/Q8.4）：仅「按机器分组 + 已得高亮 + 集齐徽章 + 重复角标」；徽章纯展示不发实物、不解锁功能。分享 / NFT / 跨机器套装 / 积分兑换 / 成就系统全部推 v2。
4. **不维护「徽章拿到没」DB 字段**（doc/11 §7.5）— 集齐 = mp / service 层对全集与 collection 实时 COUNT 比对。
5. **盲盒语义**（仅 gacha 域）：UI 可见文案 + i18n key 用 获得 / 开盒 / 出现概率 / 已收集；禁 抽奖 / 中奖 / 开奖。后端 enum / 字段保留 `draw`（技术语义）。
6. **mp 视觉走 C 系统**：只用 `Biz*` 原子组件 + `var(--c-*)`；稀有度色锚 tokens §1.4 四档；不硬编码 hex；不引 tokens §9（不存在）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 数据源 `gz_user_gacha_collection`（非 draw 聚合） | 表已在 GACHA-104 N9 开盒事务内 UPSERT 维护「用户×机器×奖品 + drawn_count」（每次必出必落、无退款回滚），直接查即准确完整；draw 聚合还要去重，多此一举（任务硬铁律）|
| D2 | 重复获得用 `drawn_count` 角标（×N）而非多格 | 图鉴是"集齐"语义，同奖品占一格 + 角标显重复数，对齐 doc/11 §7.5 `drawn_count` 显示口径 |
| D3 | 集齐判定含 `stock_remain=0` / `auto_off`、排 `del_flag=2` | 抽空 / 下架的奖品仍是该机全集成员（否则集不齐）；已删除的不再属全集（运营撤掉的奖品不应卡死集齐）|
| D4 | 灰显未得用 `grayscale(1) opacity(.35)` + 锁标 | doc/12 §MP-ME-COLLECTION 裁定的 locked 视觉；激发收集欲 |
| D5 | 徽章仅展示、不写 DB reward 字段 | doc/10 Q8.4 + doc/11 §7.5 明确不发实物 / 不解锁；避免 V1.1 引入新奖励发放链路 |
| D6 | 进度条 / 徽章走 C 系统 Biz 组件 + `var(--c-*)` | 视觉一致 + 不硬编码 hex；`BizProbBar` 与 GACHA-103 概率公示共用 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | §0 自检假设上游表已建 | **§0 自检 grep migration 目录确认 `gz_user_gacha_collection` / `gz_gacha_machine` / `gz_gacha_prize` 实际存在**（GACHA-104/101 落地后），不存在 → STOP 挂起等上游 |
| R2 | 用户抽过多机器 → 接口 JSON 大 | service 只返回用户 collection 中出现过的 distinct machine（不返回全平台机器）|
| R3 | 运营给机器新增奖品 → 已集齐用户突然「未集齐」 | 接受：是预期行为（新奖品 = 新收集目标，正是收集驱动）；不做历史快照 |
| R4 | 灰显 grayscale 在老版本微信兼容性 | 主流支持 `-webkit-filter`；老版本 fallback 半透明 + 锁图标（双重表达"未得"）|
| R5 | i18n 命名空间与 GACHA-105/106 不一致 | 实施前确认 105/106 用的是 `gacha.*` 还是 `me.collection.*`，本卡对齐统一，避免 key 散裂 |

### 与 V2 的边界（明示，doc/02 §3.3 + doc/10 Q8.2/Q8.4 锚定）

V1.1 **不做**：集齐特典实物奖励发放（兑换码 / 邮寄）/ 炫耀分享卡片 / 收藏夹点赞 / 跨机器套装 / 季度套装 / 图鉴成就系统 / 集齐解锁隐藏机器 —— 全部推 v2。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D09/GZ-GACHA-107 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
