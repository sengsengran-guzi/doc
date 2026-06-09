# GZ-GACHA-102 完工报告 — mp 扭蛋机列表

> 扭蛋域浏览波第一站。后端 `/app/gz/gacha/machine/list`（仅 on_shelf + stockRemainSum 聚合）
> + mp `pages/gacha/index.vue`（占位 ComingSoon → 真列表，双列立体迷你机器卡）。
> 字段权威 doc/11 §7.1/§7.2 ｜ 业务流 doc/10 §8 N1 ｜ UI doc/12 §MP-GACHA-LIST ｜ 视觉 doc/tokens.md §1.4 + doc/13。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本仓库非 git 仓库，env `Is directory a git repo: No`；无版本控制可查）|
| 上游依赖 GACHA-101 merge | ✅ migration `V202606171000__GZ-GACHA-101-create-gz_gacha_machine-and-prize.sql` + `V202606171002__...-fix-base-columns.sql`（含 create_dept/create_by/update_by BIGINT 修复）实际存在 |
| 关键表存在（grep migration）| ✅ `gz_gacha_machine` / `gz_gacha_prize` 已建（R1 硬探通过）；`gz_file_object`（封面 FK）存在 `V202605281100__GZ-SYS-005-create-gz_file_object.sql` |
| 关键类存在 | ✅ `GzGachaMachineMpController` / `GzGachaMachineMpVo` / `IGzGachaMachineService.listOnShelfForMp` / `GzGachaPrizeMapper.sumStockRemainByMachineIds` 全在位 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-gacha -am -q` 无错（含 GACHA-104 同模块代码一并编过）|
| 后端单测 | ✅ `GzGachaMachineServiceImplTest` 10/10（AC7：on_shelf 过滤 + stockRemainSum 聚合 + 封面解析 + fallback + 空页）|
| mp vitest | ✅ `gz-gacha.test.ts` 3/3 + `list.logic.test.ts` 12/12 = 15/15 |
| 盲盒语义 grep | ✅ mp gacha 全文件可见文案无「抽奖/中奖/开奖/抽奖率/中奖率」（命中项全是注释里描述"禁词"或测试断言）|
| Tier 2 可达 | ✅ 首页「扭蛋」入口格 + teaser 均 `goPage('/pages/gacha/index')`（无 ComingSoon 拦截），本卡占位页替换为真列表 → 天然可达，无需临时入口 |
| ADR 已读 | 无相关（任务卡「关联 ADR: —」；GACHA 域无 ADR）|

> ⚠️ **实现状态说明**：GZ-GACHA-102 全部产物（后端 MP 控制器/VO/service 方法/mapper SUM 查询 + mp 页/卡片/api/locale/逻辑/测试）在接手时已由前序会话落地。本次工作 = 逐条对 AC 复核 + 跑全量自测验证 + 补 §0 硬探 + 写报告。复核结论：实现与 8 条 AC + doc/10/11/12/tokens 权威口径**逐条对齐**，无需返工。

## 实现摘要

**后端**（`ruoyi-modules/ruoyi-gz-gacha/`）：
- `controller/applet/GzGachaMachineMpController.java` — `@RequestMapping("/app/gz/gacha/machine")` + `@SaIgnore`（浏览匿名可读，同 gz-ord/gz-news 列表）；`GET /list` 委托 service。
- `domain/vo/GzGachaMachineMpVo.java` — mp 列表展示子集：`id`(ToStringSerializer→string) / `name` / `coverImageUrl`（**后端解析签名 URL，不暴露裸 file_id**）/ `singlePriceCent` / `tenPackPriceCent` / `ipTag` / `stockRemainSum`。不暴露 machine_no/weight/version/salesCount。
- `service/IGzGachaMachineService#listOnShelfForMp` + impl — `LambdaQueryWrapper` 仅 `status='on_shelf'`（off_shelf/auto_off 排除，del_flag 由 @TableLogic 自动 append）+ `orderByDesc(onlineTime).orderByDesc(id)`（doc/11 §7.1 无 sort_order，决策 D3）；批量 `sumStockRemainByMachineIds` 避 N+1；封面 NULL/解析失败 → 占位图 `/static/images/mock-product.png`。
- `mapper/GzGachaPrizeMapper#sumStockRemainByMachineIds` — `SELECT machine_id, COALESCE(SUM(stock_remain),0) WHERE enabled=1 AND del_flag='0' AND machine_id IN (...) GROUP BY machine_id`，走 `idx_gacha_prize_pool` 索引。

**小程序**（`miniapp/src/`）：
- `pages/gacha/index.vue` — 占位 ComingSoon 替换为真列表；筛选条（V1.1 仅「全部」chip，预留 ip_tag 扩展）+ 双列网格 + `onReachBottom` 分页 + loading/error/empty 态 + 客服浮层。
- `components/biz/BizGachaMachineCard.vue` — 立体迷你机器视觉（纯 CSS box-shadow + linear-gradient 模拟玻璃罩/胶囊/投币旋钮/出蛋口，封面图嵌罩内，GPU 友好无 setInterval）；价格朱红 `var(--c-red)`；库存三档；empty 置灰禁点；IP/已抽完角标走 BizTag。**无裸 wd-***。
- `api/gz-gacha.ts` — `getMachineList(query)` 默认 pageNum=1/pageSize=20；`GachaMachineCardVO`（id:string 契约）。
- `pages/gacha/list.logic.ts` — `formatPriceCent`（整元省小数/角分 2 位）+ `resolveStockLevel`（≥10 normal / 1-9 low / ≤0 empty）+ `formatStockText` + `isStockClickable`。
- `locale/gacha.zh-CN.ts` — `gacha.list.*`（含 en 镜像，`uni.getLocale()==='en'` 切换）。盲盒语义文案。
- `pages/gacha/detail.vue` — GACHA-103 落地前最小占位（保证 AC8 跳转路径不报错）。

> **本卡无新建表 / 无 DDL**（machine/prize 表由 GACHA-101 建；mp 查询走 GACHA-101 已建 `idx_gacha_prize_pool` 索引，未额外补 `idx_machine_status_online`——V1.1 流量 <10 机器无性能压力，R2 缓解）。
>
> **locale 路径偏差说明**：任务卡 Tech 段写 `lang/zh-CN/gacha.ts + lang/en-US/gacha.ts`，但项目实际约定是 `src/locale/<module>.zh-CN.ts` 自包含 t()（与 ord/bean/news 全模块一致，无 `src/lang/` 目录）。遵循**实际代码约定**，en 在同文件内镜像（其余模块亦无独立 en-US 文件）。

## AI 自测（raw output）

### 1. 后端编译 + 单测（mvn）

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-gacha -am -q
（无输出 = BUILD SUCCESS，含 GACHA-104 同模块代码一并编过）

$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am -Dsurefire.failIfNoSpecifiedTests=false ...
# surefire-reports 摘要：
=== GzGachaMachineServiceImplTest.txt ===
Tests run: 10, Failures: 0, Errors: 0, Skipped: 0   ← AC7 列表 service（on_shelf 过滤 + stockRemainSum 聚合 + 封面解析 URL + fallback 占位 + 空页）
=== GzGachaPrizeServiceImplTest.txt ===
Tests run: 12, Failures: 0, Errors: 0, Skipped: 0
=== GzGachaDrawServiceImplTest.txt ===
Tests run:  7, Failures: 0, Errors: 0, Skipped: 0
=== ProbabilityNormalizerTest.txt ===
Tests run:  5, Failures: 0, Errors: 0, Skipped: 0
# 日志佐证 listOnShelfForMp 路径执行：
WARN GzGachaMachineServiceImpl -- [gz-gacha-mp] 封面解析失败 fileId=6001，回退占位图：file not found
  ↑ fallback 分支单测命中（cover_image_id 解析失败 → 占位图，不抛错）
```

### 2. mp vitest（api + 列表逻辑）

```
$ pnpm vitest run src/api/gz-gacha.test.ts src/pages/gacha/list.logic.test.ts

 ✓ src/api/gz-gacha.test.ts (3 tests) 2ms
   ✓ 默认 pageNum=1 pageSize=20，GET /app/gz/gacha/machine/list
   ✓ 自定义分页透传 query
   ✓ TableDataInfo rows/total 结构穿透 + id string 契约
 ✓ src/pages/gacha/list.logic.test.ts (12 tests) 2ms
   ✓ formatPriceCent 整元省小数 / 角分 2 位 / null 防御
   ✓ resolveStockLevel 三档边界（≥10 normal / 1-9 low / ≤0·null·NaN empty）
   ✓ formatStockText 盲盒语义（剩余 X 颗 / 即将售罄 / 已抽完）+ 禁词自查 not.toMatch(/抽奖|中奖|开奖|.../)
   ✓ isStockClickable（empty 不可点）

 Test Files  2 passed (2)
      Tests  15 passed (15)
```

### 3. 盲盒语义 grep 自查（AC4）

```
$ grep -rn "抽奖|中奖|开奖|抽奖率|中奖率" \
    src/pages/gacha/ src/components/biz/BizGachaMachineCard.vue \
    src/locale/gacha.zh-CN.ts src/api/gz-gacha.ts
# 全部命中项均为「注释里描述禁词纪律」或「测试 not.toMatch 断言」，
# 无任何用户可见字符串 / i18n value 含禁词。例：
locale/gacha.zh-CN.ts:9:  ... <b>禁</b>「抽奖 / 中奖 / 开奖 / 抽奖率」...   ← 注释
list.logic.test.ts:77:   expect(texts).not.toMatch(/抽奖|中奖|开奖|抽奖率|中奖率/)  ← 断言
# 实际文案：扭蛋机 / 全部 / 剩余 / 即将售罄 / 已抽完 / 暂无在售扭蛋机 ✅
```

### 4. 后端 list 端点 curl（⚠️ 本环境未执行 — 见风险 R1，主线程接手跑）

```bash
# 期望（待主线程在可连 DB 的环境起 8080 后执行）：
curl --noproxy '*' -s 'http://localhost:8080/app/gz/gacha/machine/list?pageNum=1&pageSize=20' | jq
# 期望结构（GzGachaMachineMpVo / TableDataInfo）：
# {
#   "code": 200, "msg": "查询成功",
#   "rows": [ { "id":"<string>", "name":"...", "coverImageUrl":"https://.../...或/static/images/mock-product.png",
#              "singlePriceCent":<分>, "tenPackPriceCent":<分|null>, "ipTag":"...|null", "stockRemainSum":<剩余合计> } ],
#   "total": <on_shelf 机器数>
# }
# 验收点：rows 仅含 on_shelf（off_shelf/auto_off 不出）；id 为 string；stockRemainSum 与 prize SUM 一致。
```

## 风险提示 / 已知 issue

- **R1（本卡唯一未跑项）**：**live curl 未在本 agent 环境执行** —— 沙箱网络与宿主 Docker 端口隔离，MySQL `3307` / Redis `6380`（host.docker.internal 映射）从本 agent 网络命名空间**不可稳定连通**（5× nc 探测全 closed + Docker daemon socket 不可达；app 起来即 `Could not create connection to database server`）。这是**环境隔离**非代码缺陷——GACHA-101 已在 Kevin 环境实证建表。**主线程接手起 8080（可连 DB 环境）→ 跑上面 §4 curl + 派 kevin-qa**。我已在退出前 kill 掉所有自起的 spring-boot:run（8080 free 已确认）。
- **R2**：`stockRemainSum=0` 的 on_shelf 机器仍会出现在列表（前端 empty 灰态禁点），不是过滤掉——符合 AC2「已抽完」灰态语义；如甲方要求「售罄机器不上墙」属 v2 调整。
- **R3**：「即将售罄」阈值写死 10（`STOCK_LOW_THRESHOLD`）—— V1.1 接受，v2 可改机器粒度配置（任务卡 R4）。
- **R4**：立体机器视觉纯 CSS box-shadow/gradient，老版本微信 fallback 走封面平面图（任务卡 R3，主流微信版本全支持）。

## 待 Kevin 批量人验关注（mp 端）

- 首页「扭蛋」入口格（③ V1.1 badge）+ 红 teaser 卡 → 点任一 → 进扭蛋机列表（双列立体机器卡）✅ 可达
- 列表卡视觉遵循 C 系统（米白纸 + 粗墨边 + 硬投影 + 朱红价格 + 立体迷你机器，非平面图）
- 库存三档文案（剩余 X 颗 / 即将售罄 / 已抽完灰态禁点）
- 触底加载下一页 + 空态「暂无在售扭蛋机」+ 客服入口
- 点在售卡 → 跳 `/pages/gacha/detail?id=`（GACHA-103 落地前为占位页，路径可触发不报错）
- 盲盒语义：全程无「抽奖/中奖/开奖」字样

## 对下游 GACHA-103（mp 单机详情 + 概率公示）的契约提示

1. **路由 + 入参**：列表卡 `goDetail(id)` → `uni.navigateTo({ url: '/pages/gacha/detail?id=' + machineId })`，`id` 为 **string**（机器主键，非业务码 machine_no）。GACHA-103 把 `detail.vue` 占位替换为完整详情，`onLoad` 取 `query.id`（占位页已示范）。
2. **详情后端端点**：建议 `GET /app/gz/gacha/machine/{id}`（同控制器 `GzGachaMachineMpController` 加方法，前缀 `/app/gz/gacha/machine`，`@SaIgnore` 浏览匿名）。返回机器全字段 + **奖品池列表 + 实时归一化概率**（doc/10 §8 N2/N3）。
3. **概率归一化口径**（doc/11 §7.2 计算口径，与 GACHA-104 开盒事务**同口径**）：`P(prize_i) = weight_i / Σ weight_j`，`j ∈ {enabled=1 AND stock_remain>0}`。复用 `ProbabilityNormalizer`（gz-gacha 已有 + 单测 5/5）——**不要前端自算**，由后端按当前在池快照算好下发（合规：展示「当前在池」实时概率，非后台配置原值）。
4. **奖品 VO 字段**（建 `GzGachaPrizeMpVo`）：`name` / `imageUrl`（image_id 解析，复用 `resolveImageUrl` 模式）/ `rarity`（SSR/SR/R/N，稀有度色走 tokens §1.4 `--c-r-ssr/-sr/-r/-n` 四档）/ `referenceValueCent`（可空→不显示价值）/ 归一化后 `probability`（百分比，后端算）/ `stockRemain`（库存条）。**不暴露 weight 裸值**（admin 内部，避免被反推）。
5. **十连价**：`tenPackPriceCent` 列表 VO 已带（可空=不支持十连），详情页「单抽 / 十连」CTA + 立省 chip（`10×single - tenPack`）。十连开盒事务是否启用由 GACHA-104 决（doc/11 F-D25），GACHA-103 仅展示价。
6. **盲盒语义**：详情页文案延续 `gacha.zh-CN.ts` 的 `gacha.*` 命名空间（追加 `gacha.detail.*`），「出现概率」「100% 获得」金句，**禁** 抽奖系词。
7. **封面/图片占位**：`coverImageUrl` / `imageUrl` 后端解析失败已回退 `/static/images/mock-product.png`，前端直接渲染无需再兜底。
8. **金额单位**：全 `_cent`（分），前端 `formatPriceCent`（list.logic.ts 已导出，可复用）÷100 显示元，朱红 `--c-red`。

## §AI 测试段（Tier 1B，主线程在真实 infra 验证，2026-06-04）

> 沙箱 coder 跑不到 DB（docker 当时 down），主线程在真实 infra（MySQL:3307 + 8080）补 live 契约验证。

**API 契约 live（curl --noproxy）**：
```
GET /app/gz/gacha/machine/list?pageNum=1&pageSize=20 → HTTP 200
{"total":1,"rows":[{"id":"2","name":"R1复测-宫崎骏联名扭蛋机","coverImageUrl":"/static/images/mock-product.png",
 "singlePriceCent":1000,"tenPackPriceCent":9000,"ipTag":"宫崎骏","stockRemainSum":100}],"code":200}
```
- ✅ `id` 序列化为 string（"2"）— 与 GACHA-103 契约一致
- ✅ 只返 `status='on_shelf'` 机器（DB 当前唯一机器即 on_shelf；过滤逻辑 service 单测 10/10 覆盖）
- ✅ `stockRemainSum=100` = 该机器 enabled prize 库存聚合正确
- ✅ 金额 `_cent`（singlePriceCent=1000 → ¥10）；封面 fallback 占位图就位
- ✅ 浏览端点无 sa-token 门槛（@SaIgnore，合理）

**vitest**：coder 跑 15/15（gz-gacha.test 3 + list.logic.test 12，含盲盒禁词 not.toMatch）。
**Tier 2 可达**：首页 `pages/index/index.vue` 扭蛋入口 + teaser 卡 → `/pages/gacha/index`，点 1 次即达，**无需临时入口**。

**结论：✅ Tier 1B 通过。** mp 真机 happy path（列表滚动 / 卡片视觉 / 点进详情）进 Tier 2 批量人验。
