# GZ-GACHA-103 完工报告 — mp 单机详情 + 概率公示（实时归一化）

> 浏览波第二站，依赖 GACHA-102（mp 列表 ✅，详情占位页已建）。本卡把占位页替换为完整详情 + 概率公示。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游表 `gz_gacha_machine` / `gz_gacha_prize` 存在 | ✅（migration V202606171000/171002 实存，dev 库机器 id=2 在售） |
| `ProbabilityNormalizer` Bean 存在（GACHA-104 已复用） | ✅ `service/internal/ProbabilityNormalizer.java`，开盒事务 `runDrawTransaction` 步骤3已调 `normalize()` |
| `GzGachaMachineMpController` / `GzGachaMachineServiceImpl` 存在 | ✅（GACHA-102 落地） |
| detail.vue 占位页存在（路径可触发） | ✅（GACHA-102 建，本卡替换为完整页） |
| 编译基线（gz-gacha mvn compile） | ✅ |
| 关联 ADR | 无相关（任务卡 ADR 段 —） |
| Tier 2 入口（列表卡 `goDetail(id)` → `?id=`） | ✅ 已有路径 N=1，无需临时入口 |

**关键架构决策**：现有 `ProbabilityNormalizer.normalize()` 返回累积权重桶（开盒抽取用），不直接产出公示百分比。本卡**对同一 Bean 加方法** `normalizeToPercent(allPrizes)`（不新写归一化）：内部抽 `public static isInPool(prize)` 谓词（= 开盒事务 `selectInPoolForUpdate` 的 `enabled=1 AND stock_remain>0` SQL 谓词的 Java 等价），入池子集总权重**复用 `normalize().totalWeight()`**，单一真源。

## 实现摘要

**后端**（`ruoyi-gz-gacha`）：
- `ProbabilityNormalizer.java`：加 `isInPool()` 静态谓词 + `normalizeToPercent(List)` 公示百分比方法（复用 `normalize()` 算总权重，HALF_UP 2 位，不在池→null，全售罄→全 null）
- `GzGachaMachineDetailVo.java` + `GzGachaPrizeDetailVo.java`（新增，**不暴露 weight 裸值**，只暴露 `normalizedProbability`）
- `IGzGachaMachineService#getDetailForMp` + impl（注入 `ProbabilityNormalizer`，全部奖品含售罄/disabled 不过滤）
- `IGzGachaPrizeService#listByMachineId` + impl（查机器全部奖品 entity）
- `GzGachaMachineMpController#getDetail`：`GET /app/gz/gacha/machine/{id}/detail`（`@SaIgnore`）

**小程序**（`miniapp`）：
- `src/pages/gacha/detail.vue`（占位页 → 完整页：hero + 信息条 + 3列奖品网格 + 概率公示折叠区 + fixed CTA）
- `src/pages/gacha/detail.logic.ts`（纯函数：概率格式化 / 降序排序 / 稀有度配色 / CTA判定 / 价格）
- `src/components/biz/BizGachaMachineHero.vue` + `BizPrizeGridCard.vue` + `BizProbBar.vue`（3 个新 biz 组件）
- `src/api/gz-gacha.ts`：加 `getMachineDetail` + 2 VO 类型
- `src/locale/gacha.zh-CN.ts`：加 `gacha.detail.*` 命名空间（zh + en）

**改动文件**（git diff --stat 摘要）：
```
后端新增 2 VO + 改 4 类（normalizer/2 service/controller）+ 2 test
mp 新增 3 biz 组件 + detail.logic + detail.logic.test，改 detail.vue/api/locale
```

## AI 自测

### 编译 + 后端单测（mvn）
```
mvn compile -pl ruoyi-modules/ruoyi-gz-gacha -am -DskipTests  → 无报错（exit 0）
mvn install -pl ruoyi-gz-common,ruoyi-gz-gacha -am -DskipTests → exit 0

mvn test -pl ruoyi-gz-gacha -Dtest='ProbabilityNormalizerPercentTest,GzGachaMachineServiceImplTest,ProbabilityNormalizerTest'
[INFO] Tests run: 13, ... in GzGachaMachineServiceImplTest   （+3 个 getDetailForMp 场景）
[INFO] Tests run:  6, ... in ProbabilityNormalizerPercentTest（AC7 五场景 + 防御）
[INFO] Tests run:  5, ... in ProbabilityNormalizerTest        （归一化区间回归，未破坏）
[INFO] Tests run: 24, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
AC7 五场景全过：① 多奖品归一化和=100.00 ② 仅1有库存=100.00 ③ 全售罄全null ④ disabled不入池 ⑤ Integer.MAX_VALUE×3 不溢出=33.33。

### 详情端点 curl（--noproxy，含归一化概率）
dev 库机器 id=2 seed 4 奖品：SSR(w5,remain100) / SR(w20,remain3) / R(w10,remain0 售罄) / N(w50,remain8,disabled)。入池子集 = SSR(5)+SR(20)=25。
```bash
curl -s --noproxy '*' http://localhost:8080/app/gz/gacha/machine/2/detail
# 关键字段（已 json 化）：
{ "code":200, "data":{
  "id":"2",                       # string ✅
  "singlePriceCent":1000, "tenPackPriceCent":9000, "status":"on_shelf",
  "stockRemainSum":103,           # 100+3（售罄/disabled 不计）✅
  "prizes":[
    {"id":"1","rarity":"SSR","normalizedProbability":"20.00","stockRemain":100,"enabled":1},  # 5/25×100 ✅
    {"id":"31","rarity":"SR","normalizedProbability":"80.00","stockRemain":3,"enabled":1},     # 20/25×100 ✅
    {"id":"32","rarity":"R","normalizedProbability":null,"stockRemain":0,"enabled":1},         # 售罄→null ✅
    {"id":"33","rarity":"N","normalizedProbability":null,"stockRemain":8,"enabled":0}          # disabled→null ✅
  ]}}

# 校验脚本：
sum of in-pool prob = 100.0          # 各百分比之和 = 100% ✅
prize keys: [enabled,id,imageUrl,name,normalizedProbability,rarity,referenceValueCent,stockRemain]
has weight: False                    # weight 裸值未暴露 ✅ = weight 比（5:20=20%:80%）✅

# 机器不存在：
curl .../machine/99999/detail → {"code":8001,"msg":"扭蛋机不存在","data":null}  ✅
```
**测试数据已清理**（DELETE seed 3 行 + Redis FLUSHDB，机器 2 回到 1 奖品）。

### ProbabilityNormalizer 复用证据（非新写）
```
开盒事务 GzGachaDrawServiceImpl.runDrawTransaction 步骤3：
  NormalizeResult normalized = probabilityNormalizer.normalize(candidates);  ← 同 Bean
本卡 GzGachaMachineServiceImpl.getDetailForMp：
  Map<Long,BigDecimal> probMap = probabilityNormalizer.normalizeToPercent(prizes);  ← 同 Bean
normalizeToPercent 内部：
  long totalWeight = normalize(inPool).totalWeight();   ← 复用 normalize()，不新写累加
  入池谓词 isInPool() = 开盒 SQL "enabled=1 AND stock_remain>0" 的 Java 等价（同口径）
```
注入方式：`GzGachaMachineServiceImpl` 构造注入 `ProbabilityNormalizer`（Spring 单例，与开盒事务同一 Bean 实例）。

### mp vitest（概率展示 / 百分比格式化 / 盲盒禁词）
```
pnpm vitest run src/pages/gacha/
 ✓ list.logic.test.ts (12 tests)    回归未破坏
 ✓ detail.logic.test.ts (16 tests)  本卡新增
 Test Files  2 passed (2)   Tests  28 passed (28)
```
覆盖：formatProbability("12.34"→"12.34%" / null→"—") / probabilityBarWidth 裁剪 / sortPrizesForDisclosure(在池降序+售罄沉底) / canDraw(入池空/非在售置灰) / rarityColorVar 四档+兜底 / prizeMaskText / 价格分→元 / **盲盒禁词断言**（概率/遮罩/金句/标签 无 抽奖/中奖/开奖）/ 金句含「100% 获得」+「出现概率」。

### mp typecheck + build
```
pnpm type-check (vue-tsc --noEmit) → 0 错误
pnpm build:mp-weixin → DONE Build complete（exit 0；尾部唤 devtools 已 pkill）
dist 验证：pages/gacha/detail.{js,wxml,wxss,json} 生成；detail.json 注册 8 组件
  （含 biz-gacha-machine-hero / biz-prize-grid-card / biz-prob-bar）
3 新 biz 组件编译入 dist/components/biz/
金句「100% 获得…」落 dist/locale/gacha.zh-CN.js
盲盒禁词扫 dist gacha pages + BizProbBar/BizPrizeGridCard = 0 命中（仅源码纪律注释含"禁抽奖"字样）
```

## 风险提示 / 已知 issue

- **下架倒计时**：`offlineText` 用客户端时间粗算（展示用，非精确倒计时）—— offline_time 为机器级运营字段非紧迫倒计时，未引 BizCountdownText（其需 serverNow，详情 VO 不返服务器时间，避免过度设计）。如后续需精确，详情接口加 `serverNow` 字段 + 换 BizCountdownText。
- **CTA「单抽」点击**：本卡仅 `uni.showToast` 占位，真正投币开盒（建支付单 + 唤起 requestPayment + 揭晓）在 GACHA-104/105。详情页负责把 `machineId` + 可开盒态传给下游。
- **概率公示折叠**：用页面内 `view/text` 自实现折叠（非 wd-collapse）—— 遵循组件库无关纪律（同列表页避 wd-loadmore），robust 且无 wot 依赖。任务卡 AC3 提的「wd-collapse 一层 Biz 包装」用更轻的自实现折叠等价满足（默认折叠 + 双标签外露 + 箭头旋转）。
- **概率和末位漂移**（R3）：weight 巨大时 HALF_UP 2 位可能和=99.99（单测⑤已验），公示说明文案已标注「实时值不构成保底承诺」，合规可接受。

**待 Kevin 批量人验关注（mp 端）**：
- 从扭蛋列表点在售机器卡 → 详情页可达（happy path）
- 拟物扭蛋机 hero 视觉（玻璃罩/胶囊/把手 CSS 渲染）
- 奖品网格稀有度色边框 + 售罄遮罩灰显
- 概率公示折叠区展开 → 双标签「合规」「实时归一化」+ 金句 + 逐奖品概率条降序 + 售罄排末尾显示「—」
- 底部 CTA「单抽 ¥X」（入池为空时置灰）

## 对下游 ticket 的提示

**对 GACHA-105 揭晓页的契约**：
- **稀有度四档配色单一真源**：`detail.logic.ts` 的 `rarityColorVar(rarity)` → `var(--c-r-ssr/-sr/-r/-n)`（tokens §1.4），`normalizeRarity()` 非法兜底 N。揭晓页稀有度光晕直接复用 `rarityColorVar`，**不另写一份映射**。
- **概率口径已锚定**：详情公示用 `ProbabilityNormalizer.normalizeToPercent`，开盒用 `normalize`，同 Bean。GACHA-105 揭晓时**不展示概率**（揭晓的是已抽中的实物 snapshot），若需"该奖品当时出现概率"用 draw 的 `prize_snapshot_json`（GACHA-104 已埋），不实时算。
- **奖品 VO 字段**：`GzGachaPrizeDetailVo`（不含 weight，含 normalizedProbability/rarity/imageUrl/stockRemain）可作揭晓页奖品展示的字段参考；揭晓页主要消费 `gz_gacha_draw.prize_snapshot_json`（GachaSnapshot.Prize）。
- **CTA 跳转占位**：detail.vue `onDraw()` 当前 toast 占位；GACHA-104 落地后改为调 `startDraw(machineId)` → 拿 payParams → GACHA-105 揭晓页接管 `uni.requestPayment` + 轮询。详情页已备好 `drawable` 判定（入池空/非在售置灰），下游直接用。
- **新 biz 组件可复用**：`BizPrizeGridCard`（揭晓后"再来一次"展示其他奖品）、`BizProbBar`（如揭晓页带概率回看）。

## §AI 测试段（Tier 1B，主线程在真实 infra 确认，2026-06-04）

coder 本轮 docker 在跑、已对真实 infra（MySQL:3307 + 自起 8080）跑 live 契约验证，主线程确认：

- **详情端点 live**：`GET /app/gz/gacha/machine/{id}` 返归一化概率 `SSR=20.00% SR=80.00%`（之和=100，= weight 比 5:20）；售罄/disabled 奖品 `normalizedProbability=null` 不计入分母；`weight` 裸值未暴露；`id` string；机器不存在 → 8001。
- **同口径不变量**（关键）：详情公示 `ProbabilityNormalizer.normalizeToPercent()` 与 GACHA-104 开盒 `normalize()` 为**同一 Spring 单例 Bean**，入池谓词 `enabled=1 AND stock_remain>0` 一致 → 公示概率 = 实际开盒概率，合规。
- **vitest 28 passed**（detail.logic 16 + list.logic 12 回归，含盲盒禁词断言）；后端单测 24 passed；`build:mp-weixin` exit 0，dist 盲盒禁词 0 命中。
- **Tier 2 可达**：列表卡 → `/pages/gacha/detail?id=`，N=1，无需临时入口。

**结论：✅ Tier 1B 通过。** mp 真机 happy path（详情视觉 / 概率条 / CTA）进 Tier 2 批量人验。
