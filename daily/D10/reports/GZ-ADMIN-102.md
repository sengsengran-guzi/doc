# GZ-ADMIN-102 完工报告 — 扭蛋池管理（plus-ui，权重前端实时归一化）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ⚠️ plus-ui 是独立 git repo（项目根非 git）；gz-gacha views/api 处 untracked（GACHA-101 未提交态），本卡改动叠加其上 |
| 上游依赖 merge（GZ-GACHA-101 表 + 后端 + admin 页） | ✅ `gz_gacha_machine` / `gz_gacha_prize` DDL（V202606171000）+ 稀有度字典 + create_dept fix（V202606171002）齐；后端 `GzGachaMachineController`/`GzGachaPrizeController` + service/BO/VO 齐；plus-ui `gz-gacha/machine/index.vue`+`prize/index.vue`+api 齐 |
| 关键表/字段对齐 doc/11 §7.2 | ✅ `weight INT` / `stock_initial` / `stock_remain` / `enabled TINYINT` / `rarity SSR/SR/R/N` 四档字典齐 |
| 编译（mvn install gz-common+gz-gacha -am） | ✅ BUILD SUCCESS（需先 `mvn clean` 清并行 ADMIN-103 残留 stale target，详见风险 R1） |
| ADR 已读 | ADR-0004（mp/admin 权限底座，本卡纯 admin 无权限下沉，仅参考 owner 授权口径）；无其他相关 ADR |

### §0 关键发现：后端 + admin 框架已由 GACHA-101 交付，本卡 = 归一化前端增量

GACHA-101 已落地完整的扭蛋机 + 奖品池 admin CRUD（controller / service / BO / VO / 菜单 SQL / 权限 / 字典 / plus-ui 两页 + api）。AC 1-5 / 8-10 已被 GACHA-101 满足。**本卡真实交付 = AC 6 / 7 / 11 的前端 reactive 归一化预览**（GACHA-101 VO 注释明确「本卡 admin 只展示权重，归一化留 GACHA-103」，把归一化预览推迟到了 ADMIN-102）。

### 与任务卡的口径偏差（按 reality wins / CLAUDE.md §9.5 + §12 对齐既有实现）

| 任务卡 AC | 既有 GACHA-101 实现 | 本卡处置 |
|---|---|---|
| AC 9 perms `gz:gacha:pool:*` + menu 10100 段 + 菜单 SQL `V202606080300` | GACHA-101 已发 `gz:gacha:machine:*`/`gz:gacha:prize:*` @ menu **10000** 段（V202606171001，**已 Flyway 应用、不可改**） | **不新建重复菜单 SQL / 不改 perms**。既有已部署 + 已授权 owner，新建会产生重复目录 + 死菜单。AC 9「权限组 + 菜单 SQL」判定为 **GACHA-101 已等价满足**（同一组 owner 授权覆盖机器+奖品池） |
| AC 2/3/4/5 拆 MachineDrawer/PrizeTable/PrizeDrawer 子组件 | GACHA-101 用单页 `el-dialog` 内联表单实现（机器页 + 奖品池页分两个路由，机器页「管理奖品池」带 machineId query 跳） | 沿用既有单页结构（功能等价，admin 不评判视觉/结构）；本卡在 `prize/index.vue` 注入归一化列 + 基数行 |
| AC 10 i18n key `gz-gacha.pool.*` | 既有 flat key `gzGachaPrize.*` / `gzGachaMachine.*` | 沿用既有 flat key 命名扩展（新增 `gzGachaPrize.colNormalizedPct` 等 4 key），不另起 `pool.*` 命名空间制造割裂 |

## 实现摘要

本卡新增/改动（plus-ui，纯前端增量）：

- **新增** `src/composables/useNormalizedProbability.ts` — reactive 归一化 composable（AC 6/7 核心）。导出 `useNormalizedProbability(prizes)` → `{ summary, normalizedPercentOf }` + 纯函数 `isParticipating` / `computeNormalizedPercent`。口径 `P_i = weight_i / Σ weight_j, j ∈ {enabled=1 AND stock_remain>0}`，不参与项返回 `null`，保留 2 位小数。
- **改** `src/views/gz-gacha/prize/index.vue` — 注入「归一化后概率」列（reactive，不参与显 `—` + tooltip 解释）+ 表格底部归一化基数行（Σweight + 参与奖品数）+ 列头 tooltip + 样式。
- **改** `src/lang/zh_CN.ts` / `src/lang/en_US.ts` — `gzGachaPrize` 块新增 `colNormalizedPct` / `normalizedPctTip` / `normalizedExcludedTip` / `normalizeBasis` 4 key（盲盒语义：用「出现概率 / 归一化后概率」，禁「抽奖/中奖」可见文案）。
- **新增** `vitest.config.ts` + package.json `test`/`test:watch` script — plus-ui 接入 vitest（node 环境，纯逻辑 composable 单测）。
- **新增** `src/composables/useNormalizedProbability.spec.ts` — 7 个用例覆盖 AC 11 前端要求。

git diff --stat（plus-ui repo，既有文件改动部分）：

```
 package.json      |   4 +-
 src/lang/en_US.ts | 110 +++  (gzGachaPrize/Machine 块整体 untracked diff，本卡新增 4 key)
 src/lang/zh_CN.ts | 110 +++
新增：src/composables/useNormalizedProbability.ts (3656 B)
新增：src/composables/useNormalizedProbability.spec.ts (4639 B)
新增：vitest.config.ts (513 B)
```

## AI 自测（Tier 1A）

### 1. 前端归一化 composable 单测（vitest，AC 11）

```
> vitest run
 RUN  v4.0.18

 ✓ src/composables/useNormalizedProbability.spec.ts (7 tests) 3ms

 Test Files  1 passed (1)
      Tests  7 passed (7)
   Duration  172ms
```

覆盖：3 奖品全参与求和=100 / 含 stock_remain=0 + enabled=0 两项显 null 且不计基数 / weight=0 不参与 / 全不参与基数=0 / 1÷3→33.33（2 位小数）/ reactive 改 weight 即时刷新 / 纯函数边界。

### 2. plus-ui 生产构建（build:prod，编译 gate）

```
> vite build --mode production
...
dist/assets/userAvatar-CaqzouV8.js.gz 33.66kb -> 9.56kb
dist/assets/vue-quill.esm-bundler-qIpz16fU.js.gz 250.60kb -> 66.83kb
dist/index.html.gz 111.32kb -> 48.39kb
（BUILD 完成，无 vue-tsc / 类型错误）
```

### 3. 后端编译 + 单测（mvn，DoD 三端绿 + AC 11 backend）

```
$ mvn clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-gacha -am
[INFO] Building ruoyi-gz-common 5.6.1   [22/23]
[INFO] Building ruoyi-gz-gacha 5.6.1    [23/23]
[INFO] BUILD SUCCESS

$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha
[INFO] GzGachaPrizeServiceImplTest      Tests run: 12, Failures: 0, Errors: 0
[INFO] GzGachaMachineServiceImplTest    Tests run: 13, Failures: 0, Errors: 0
[INFO] ProbabilityNormalizerPercentTest Tests run: 6,  Failures: 0, Errors: 0
[INFO] ProbabilityNormalizerTest        Tests run: 5,  Failures: 0, Errors: 0
[INFO] (+ Draw/DrawHistory/Collection)
[INFO] Tests run: 63, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

## 风险提示 / 已知 issue

- **R1（已闭环）**：首次 `mvn install` 在 `ruoyi-gz-common` 报 `GzUserServiceImpl 未实现 selectIdsByKeyword` —— 实为**并行在飞的 GZ-ADMIN-103 残留 stale `target/`**（该方法是 ADMIN-103 加的，源码接口+impl 签名一致）。`mvn clean compile -pl ruoyi-gz-common` 单独 BUILD SUCCESS 确认源码无误。提示日终 closing：ADMIN-103 完工后整模块再跑一次 clean install 兜底。
- **R2（口径偏差，已对齐 reality）**：任务卡 AC 9 要求新建 menu 10100 段 + `gz:gacha:pool:*`，但 GACHA-101 已部署 10000 段 + `machine:*`/`prize:*` 权限（Flyway 已应用不可改）。本卡**不新建重复菜单**，复用既有。若 Kevin/product 坚持要 10100 段独立菜单，需另起 ticket 评估迁移成本（动既有授权 + mp 端引用）。
- **R3**：归一化%是前端展示值（2 位小数四舍五入），最终判定以 GACHA-103 抽奖事务为准（tooltip 已明示）。本卡不实现抽奖逻辑（决策 D6）。
- 待 Kevin 批量人验关注：N/A — 纯 admin ticket，AI ✅ 即终态，无 mp 人验。

## 对下游 ticket 的提示

- **GACHA-103（运行时抽奖事务）**：后端 `ProbabilityNormalizer` 已存在且单测通过；运行时归一化口径须与本卡前端 `useNormalizedProbability` 完全一致（`enabled=1 AND stock_remain>0` 过滤 + weight>0），所见即所得。可复用本 composable 的口径作为契约对照。
- **GZ-ADMIN-103（同日并行）**：注意整模块 clean install 收尾（见 R1），避免 stale target 互相污染。
- **后续 admin 归一化复用**：`useNormalizedProbability` composable 与具体 VO 解耦（只依赖 `{weight, stockRemain, enabled}` 最小形状），其他需要权重归一化展示的场景可直接复用。

## §AI 测试段（kevin-qa 自动追加，21:32）

### admin Playwright E2E（plus-ui 8090，gz_owner 登录）

```
PASS: 登录 → /index ✅
PASS: 进 /gz/gz-gacha/prize → el-table 渲染 ✅
PASS: Table headers: 奖品编号 | 奖品名 | 稀有度 | 权重 | 归一化后概率 | 初始库存 | 剩余库存 | 公示价 | 参与抽奖 | 操作 ✅
PASS: 「归一化后概率」列存在 ✅
PASS: 数据行 1 条，weight=5 → 归一化后概率=100.00%（唯一参与项，100% 正确）✅
PASS: 基数行内容存在（页面含「参与」「权重」关键词）✅
PASS: 编辑按钮点击 → form dialog 打开 ✅
```

### plus-ui vitest（归一化 composable）

```
> vitest run src/composables/useNormalizedProbability.spec.ts
 ✓ src/composables/useNormalizedProbability.spec.ts (7 tests) 3ms
 Test Files  1 passed (1)
      Tests  7 passed (7)
```

覆盖：3 奖品全参与=100 / stock=0+enabled=0 显 null / weight=0 不参与 / reactive 改 weight 即时刷新 / 1÷3→33.33

### API 契约回归

```bash
GET /system/gz/gacha/machine/list → code=200, total=1 ✅
GET /system/gz/gacha/prize/list → code=200, total=1 ✅
```

### 跳过 / 未跑

- 加 5 奖品（不同 weight）后验 % 求和=100.00（需更多测试数据，vitest 已覆盖逻辑）
- perm 权限验证（gz:gacha:prize:edit 隐藏）→ 无低权限测试账号

### 结论

✅ Tier 1B 全通过，纯 admin ticket，AI ✅ 即终态（无 Tier 2 人验）
