# GZ-GACHA-107 完工报告 — mp 图鉴（按机器分组 + 集齐徽章 + 重复角标）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（freelance / sensenran 目录均非 git repo，环境无 git） |
| 上游依赖 merge | ✅ GACHA-105 揭晓页伏笔 `goCollection()` → `/pages/me/collection?machineId=` 实存（draw.vue:209-211）；GACHA-104 `gz_user_gacha_collection` 表 + entity + mapper + UPSERT 实存 |
| 关键类/表存在 | ✅ `gz_user_gacha_collection` / `gz_gacha_machine` / `gz_gacha_prize` 表实存；entity `GzUserGachaCollection` + mapper 实存；`IGzFileService.getPresignedUrl(Long)` 实存 |
| 编译通过 | ✅ 基线 `mvn compile -pl ruoyi-gz-gacha -am` BUILD SUCCESS |
| ADR 已读 | 无相关（任务卡 关联 ADR: —） |

**权威蓝图引用摘录（§0 必读）**：
- **doc/11 §7.5 gz_user_gacha_collection**：图鉴数据源；UNIQUE(tenant_id,user_id,machine_id,prize_id)；drawn_count 重复次数；集齐徽章实时 COUNT 算，**DB 不存「徽章拿到没」字段**。
- **doc/12 §MP-ME-COLLECTION**：按机器分组 + 已得高亮 locked/unlocked + 集齐徽章实时 COUNT。
- **doc/10 §8 N9 + Q8.2/Q8.4**：揭晓后图鉴进度 +1；图鉴 V1.1 简版仅展示徽章、不解锁功能、不发实物。
- **doc/tokens.md §1.4 稀有度色**：SSR `--c-r-ssr` / SR `--c-r-sr` / R `--c-r-r` / N `--c-r-n` 四档。

**关键模型钉死**：图鉴 = 该机器「当前有哪些奖品」全集（实时取 `gz_gacha_prize`，**非历史 snapshot** —— 与 GACHA-106 历史用 snapshot 区分）。集齐判定基于 prize 全集（含 `stock_remain=0` / `enabled=0` / 机器 `auto_off`，**排 `del_flag=2`**）。

## 实现摘要

**后端（ruoyi-gz-gacha，只读，无 DDL / 无菜单）**：
- 新增 `domain/vo/GzGachaCollectionVo.java`（嵌套 MachineGroup → PrizeCell，id 全 `ToStringSerializer`）
- 新增 `service/IGzGachaCollectionService.java` + `impl/GzGachaCollectionServiceImpl.java`（装配逻辑 + 纯方法 `assembleGroup` 供单测）
- 新增 `controller/applet/GzGachaCollectionMpController.java`（`GET /app/gz/gacha/collection/my?machineId=`，`@SaCheckLogin`）
- 改 `mapper/GzUserGachaCollectionMapper.java`（+ `selectDistinctMachineIds`）
- 新增单测 `GzGachaCollectionServiceImplTest.java`（6 case）

**mp（miniapp）**：
- 新增页 `pages/me/collection.vue` + `collection.logic.ts` + `collection.logic.test.ts`（25 case）
- 新增 3 Biz 组件：`BizCollectionMachineGroup` / `BizCollectionPrizeCell` / `BizCompleteSetBadge`
- 改 `api/gz-gacha.ts`（+ 图鉴 VO + `getMyCollection`）、`locale/gacha.zh-CN.ts`（+ `gacha.collection.*` zh+en）、`locale/user.zh-CN.ts`（+ `entryCollection`）、`pages/me/index.vue`（+ 九宫格「我的图鉴」正式入口）

## AI 自测（Tier 1A）

### 1. 后端编译

```
mvn compile -pl ruoyi-modules/ruoyi-gz-gacha -am -DskipTests
[INFO] BUILD SUCCESS
```

### 2. 后端单测（service 装配 + 集齐判定，6 case）

```
mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am \
  -Dtest=GzGachaCollectionServiceImplTest -Dsurefire.failIfNoSpecifiedTests=false

[INFO] Running org.dromara.gz.gacha.service.impl.GzGachaCollectionServiceImplTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.773 s
[INFO] BUILD SUCCESS
```
覆盖：部分集齐(2/3 + ×3 角标) / 全集齐(含 stock_remain=0 已抽空仍计入) / 空 collection→[] / enabled=0 临停计入全集 + del_flag=2 已删不计入 / 纯装配 assembleGroup / machineId 未收集过→[]。

### 3. collection 端点 curl（--noproxy，真实造数 → 查分组 + 集齐进度 + 重复角标）

造数：machine 2（prize 1 在售/2 已抽空/3 临停/4 已删 del_flag=2）+ machine 3（prize 5 已抽空/6 在售）；user 2 collection：machine2 拥有 prize1(×3)+prize3(×1)、machine3 拥有 prize5(×1)+prize6(×2)。

```
GET /app/gz/gacha/collection/my  （Bearer mp-token, user 2）
{
  "code": 200,
  "data": { "machines": [
    { "machineId": "2", "machineName": "...宫崎骏联名扭蛋机",
      "totalCount": 3, "ownedCount": 2, "isCompleteSet": false,    ← 全集排除已删 prize4；部分集齐
      "prizes": [
        { "prizeId":"1", "rarity":"SSR", "owned":true,  "drawnCount":3, "firstDrawnTime":"2026-06-18 20:31:05" },  ← ×3 重复角标
        { "prizeId":"2", "rarity":"SR",  "owned":false, "drawnCount":0, "firstDrawnTime":null },                   ← 已抽空未得，灰显占位
        { "prizeId":"3", "rarity":"N",   "owned":true,  "drawnCount":1, "firstDrawnTime":"2026-06-19 10:00:00" }   ← 临停款仍计入全集且已得
      ] },
    { "machineId": "3", "machineName": "...集齐机-初音机",
      "totalCount": 2, "ownedCount": 2, "isCompleteSet": true,     ← 集齐！含 prize5(stock_remain=0 已抽空)仍计入
      "prizes": [
        { "prizeId":"5", "rarity":"SSR", "owned":true, "drawnCount":1 },
        { "prizeId":"6", "rarity":"N",   "owned":true, "drawnCount":2 }   ← ×2 重复角标
      ] }
  ] }
}
```
边界：
```
GET .../my?machineId=2   → machines数:1 | machineId:2 | X/Y:2/3 | complete:False
GET .../my?machineId=9999（未收集过）→ machines: []
GET .../my（无 token）   → code:401 | msg:认证失败，无法访问系统资源
```
**结论**：全集排除 del_flag=2 ✅；集齐含 stock_remain=0 ✅；重复角标 drawnCount 准确 ✅；id 全 string ✅；图片 NULL→占位 ✅；@SaCheckLogin 401 ✅。

### 4. 稀有度配色复用证据（不另写第三处）

- `collection.logic.ts` 第 17 行：`import { normalizeRarity, rarityColorVar } from '@/pages/gacha/detail.logic'` + re-export（与 `history.logic.ts` 同款，单一真源在 `detail.logic.ts`）。
- vitest 断言：`expect(rarityColorVar).toBe(detailRarityColorVar)`（同一函数引用）+ 四档映射一致（SSR→`var(--c-r-ssr)` 等）。**全项目仅 1 处定义 RARITY_VAR（detail.logic.ts），collection / history 均复用，无第二、第三处。**

### 5. mp vitest（分组 / 集齐徽章 / 重复角标 / 稀有度配色复用 / 盲盒禁词，25 case）

```
npx vitest run src/pages/me/collection.logic.test.ts
 ✓ src/pages/me/collection.logic.test.ts (25 tests) 5ms
 Test Files  1 passed (1)   Tests  25 passed (25)
```
覆盖：buildFilterChips(含「全部」) / progressPercent(2/3=66.67%, 越界裁剪, 除零防御) / duplicateBadge(×N, 1→空) / isCompleteSet / isOwned(灰显判定) / 稀有度配色复用(同函数引用 + 四档一致 + 非法兜底N) / formatFirstDrawnTime / remainToCompleteText / **盲盒禁词自查（断言所有 collection i18n 文案不含「抽奖/中奖/开奖/抽奖率」+ 用「图鉴/已收集/开盒/获得」语义）**。

全量回归（确认未破坏其他）：
```
npx vitest run   →   Test Files 32 passed (32)   Tests 274 passed (274)
```

### 6. mp typecheck + build

```
npx vue-tsc --noEmit   →   EXIT=0, 0 errors
pnpm build:mp-weixin   →   DONE  Build complete.
  dist/build/mp-weixin/app.json 含 "pages/me/collection"
  dist/build/mp-weixin/pages/me/collection.wxml 含 biz-collection-machine-group / filter-chip / popup__title
```
（build 尾部唤 devtools cli 已按 memory 教训 pkill，dist 已正常生成。）

## Tier 2 可达入口说明（AC9）

- **主入口（依赖卡正常路径）**：GACHA-105 揭晓页底部「查看图鉴」`goCollection()` → `navigateTo('/pages/me/collection?machineId=')`（draw.vue 既有，本卡落地该页接通）。
- **会员中心正式入口（N=1）**：本卡在 `pages/me/index.vue` 九宫格新增「我的图鉴」入口（`📔` + `ROUTE_MAP.collection = '/pages/me/collection'`）→ Kevin 从「我的」tab 点 1 次直达图鉴页。
- **可达链**：底部 tab「我的」→ 九宫格「我的图鉴」→ 图鉴页（N=1）✅；揭晓后「查看图鉴」→ 图鉴页（透传 machineId 默认聚焦）✅。

## GACHA-106 临时入口处理（grep `Tier2-entry-temp`）

**保留不清理**。理由：
- GACHA-106 在 `pages/gacha/index.vue:85/115` 留的临时入口注释是 `remove when 会员中心扭蛋历史入口 merged` —— 它要求的是**会员中心直达「开盒历史」入口**（`/pages/gacha/history`）。
- 本卡建的是会员中心「我的图鉴」入口（`/pages/me/collection`），**非** history 直达入口。从会员中心到 history 现需经「图鉴页 → 已得格 popup →『查看记录』」，**空图鉴用户走不到 history** → 106 的清理条件（会员中心 history 直达入口）未满足。
- **结论**：106 临时入口保留，待后续「会员中心补开盒历史九宫格入口」的 ticket 清理。本卡未引入对 history 可达性的回退。

## 关键技术决策偏离记录

- **AC7「进度条复用 BizProbBar」偏离**：BizProbBar 是概率公示条，prop 强类型 = `GachaPrizeDetailVO`（单奖品出现概率%），与图鉴「已收集 X/Y」集齐填充比语义不同。强塞会绑定不相关类型 + 破坏其单一职责。故图鉴集齐进度条在 `BizCollectionMachineGroup` 内用 `view + var(--c-r-ssr)` 金填充实现（仍走 C token，不硬编码 hex）。组件已在注释标注此偏离理由。

## 风险提示 / 已知 issue

- R1（运营给机器新增奖品 → 已集齐用户变未集齐）：**预期行为**（新奖品 = 新收集目标，收集驱动），后端 service 注释 + 任务卡 R3 已锚定，不做历史快照。
- R2（用户抽多机器 JSON 大）：service 只返用户 collection 中 distinct machine（`selectDistinctMachineIds`），不返全平台机器。
- 灰显兼容（R4）：`grayscale(1) opacity(.35)` + 锁标 🔒 双重表达「未得」，老版本微信加 `-webkit-filter` fallback。

## 待 Kevin 批量人验关注（mp 端）

本卡是 mp ticket，进 progress.md 人验列。Kevin 真机批量人验要点：
1. 「我的」tab → 九宫格「我的图鉴」→ 图鉴页可达（happy path）
2. 揭晓后「查看图鉴」→ 图鉴页（machineId 透传默认聚焦）
3. 已得格高亮 + ×N 重复角标 / 未得格灰显锁标视觉
4. 集齐机器显示金色集齐徽章 + 满格进度条 + chip「集齐特典 — 已解锁」
5. 已得格 popup「查看记录」→ 跳开盒历史；未得格 popup「还差 X 件」+「去开盒」→ 跳机器详情
6. 文案盲盒语义（无「抽奖/中奖」）+ C 设计系统遵循度（粗墨边 / 硬投影 / 朱红选中 / 稀有度四档色）

## 对下游 ticket 的提示

- **会员中心补「开盒历史」九宫格入口的 ticket**：实施时 §0 grep `Tier2-entry-temp` → 找到 `pages/gacha/index.vue` GACHA-106 临时入口（`我开过的 →` chip + `goHistory`），加完 me 页 history 正式入口后清理它。
- 后续若做 admin 图鉴看板：另开 ticket 走 menu_id 10100 段（本卡 mp C 端只读，不进 admin menu）。
- `getMyCollection` 端点（`GET /app/gz/gacha/collection/my`）每机器已含 ownedCount/totalCount/isCompleteSet，覆盖「集齐进度 X/Y」语义，下游若需独立 progress 端点可直接复用此结构，无需另建。

## §AI 测试段（Tier 1B，主线程统一调度，2026-06-04）

coder 本轮对真实 infra（MySQL:3307 + 自起 8080）跑 live 验证，主线程 + 收尾 smoke 复核：

- **collection/progress 端点 live**：machine 2 totalCount=3/ownedCount=2 未集齐（del_flag=2 prize 排除）、prize1 drawnCount=3 角标、抽空未得灰显；machine 3 isCompleteSet=true（含 stock_remain=0 仍计入全集）；machineId 筛选 + 空机器 [] + 无 token 401。id string、图片回退占位。
- **稀有度配色复用**：`collection.logic` re-export `detail.logic` 的 `rarityColorVar`，vitest 断言同一函数引用 — **全项目仅 1 处定义**（detail.logic），collection/history 均复用。
- **图鉴语义**：用 prize 当前定义（非历史 snapshot）；只增不减（无系统退款 R8）；偏离记录 AC7（进度条未硬塞 BizProbBar，单一职责，已注释理由）。
- **vitest 25/25**（collection.logic，含分组/集齐徽章/重复角标/配色复用/盲盒禁词）；全量 274 测过（32 文件）；`build:mp-weixin` exit 0；`vue-tsc` exit 0。
- **合并 smoke（收尾）**：`GET /app/gz/gacha/collection/progress` 路由注册（非 404），全 7 ticket 同后端启动绿。
- **Tier 2 可达**：「我的」tab 九宫格「我的图鉴」正式入口 + 揭晓页「查看图鉴」，N=1。

**结论：✅ Tier 1B 通过。** 真机图鉴分组 / 集齐徽章视觉 happy path 进 Tier 2 批量人验。
