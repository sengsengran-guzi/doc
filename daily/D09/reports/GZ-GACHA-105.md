# GZ-GACHA-105 完工报告 — mp 三段分镜开盒动画 + 揭晓稀有度

## §0 状态自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | N/A（cwd 在 RuoYi-Vue-Plus 子目录，git 顶层在仓库上层，本卡不 commit） |
| 上游 GACHA-104 表/接口已就绪 | ✅ `gz_gacha_draw` 表存在（V202606171400 migration）；`IGzGachaDrawService` / `GzGachaDrawServiceImpl` / `GzGachaDrawMpController`（applet 子目录）/ `GachaSnapshot.Prize/Machine` 实存 |
| 关键 prize_snapshot_json 契约 | ✅ `GachaSnapshot.Prize{prizeId,prizeNo,name,imageId,rarity,referenceValueCent}` + `Machine{coverImageId}`；落库口径 `GzGachaDraw.prizeSnapshotJson` |
| GACHA-103 稀有度真源 | ✅ `detail.logic.ts` 导出 `rarityColorVar/normalizeRarity`（四档 SSR/SR/R/N → `var(--c-r-*)`），本卡揭晓光晕直接复用不另写 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-gacha` exit 0 + mp `vue-tsc --noEmit` exit 0 |
| 稀有度 token | ✅ tokens §1.4 四档（`--c-r-ssr/-sr/-r/-n`）+ `.c-burst`（c-tokens.scss:306）实存 |
| ADR 已读 | 无相关（任务卡 ADR 段 = —） |

**权威蓝图引用摘录（§0 自检卡）**：
- doc/10 §8 N7-N9：draw 轮询态 `pending`→`drawing`→`drawn`，付款必出 1 件，只会 drawing→drawn，**不含 refunded 揭晓分支**。
- doc/11 §7.3：`prize_snapshot_json` 结构（奖品名/封面 image_id/稀有度/公示价值 cent）；F7.5 公示价值单位 = 分，UI ÷100。
- doc/12 §MP-GACHA-DRAW：三段分镜 Frame1 转动 / Frame2 裂开光爆 / Frame3 揭晓稀有度光晕 + 揭晓操作区（大图 + 稀有度大角标 + 图鉴进度伏笔 + 双 CTA）。
- doc/13 §3.2：`BizGachaDraw`（转动 → 光爆 → 揭晓；集中线爆闪 `.c-burst` + 稀有度光晕 + 大字结果）。
- tokens §1.4：SSR 金 / SR 紫 / R 蓝 / N 灰，四档不引第五档，光晕走 token 不硬编码 hex/rgba。

## 实现摘要

**后端**（`ruoyi-gz-gacha`）：
- [新增] `domain/vo/GzGachaDrawStatusVo.java` — drawing/drawn 轮询态 VO（machineId 序列化 string，Prize 子结构 name/imageUrl/rarity/referenceValueCent）
- [改] `mapper/GzGachaDrawMapper.java` — `selectByPayTransactionId` / `selectByDrawNo`（整行查，仅查不改）
- [改] `service/IGzGachaDrawService.java` + `impl/GzGachaDrawServiceImpl.java` — `getStatusForMp(payTransactionId, drawNo, userId)`：查到 draw ⇒ drawn（解 prize_snapshot_json + 图片签名 URL）；查不到 ⇒ drawing；非本人 ⇒ DRAW_FORBIDDEN。图片解析 prize imageId → 空回退机器封面 coverImageId → 占位图
- [改] `controller/applet/GzGachaDrawMpController.java` — `GET /app/gz/gacha/draw/status?outTradeNo=|drawNo=`
- [改] `exception/GzGachaErrorCode.java` — `DRAW_FORBIDDEN = 8011`
- [改] `domain/dto/GachaSnapshot.java` — Prize/Machine 加 `@NoArgsConstructor @AllArgsConstructor`（GACHA-104 仅序列化，本卡反序列化需无参构造器，非破坏改动）
- [改] 测试 `GzGachaDrawServiceImplTest.java` — +5 getStatus 用例 + fileService mock + 构造器签名同步

**mp**（`miniapp/src`）：
- [新增] `pages/gacha/draw.vue` — 揭晓页（onLoad 取 machineId → 唤支付 → 轮询 → 三段动画 → 揭晓/超时；onBackPress 轮询期屏蔽物理返回）
- [新增] `pages/gacha/draw.logic.ts` + `draw.logic.test.ts` — 三段动画状态机（fullStageSequence）+ 低端机判定（isLowEndDevice）+ 稀有度光晕复用（rarityGlowVar=detail.logic.rarityColorVar）+ 揭晓金句（revealHeadline）+ 参考价格式化
- [新增] `components/biz/BizGachaDraw.vue` — 三段分镜动画容器（纯 CSS transform/opacity 关键帧 + `.c-burst` 集中线 + 稀有度光晕 var(--c-r-*) 注入）
- [新增] `composables/useDrawPolling.ts` + `useDrawPolling.test.ts` — 轮询编排（1s×12 → 5s 退化，60s 超时；setTimeout 链式不用 setInterval；注入 sleep/now 便于单测）
- [改] `api/gz-gacha.ts` — `getDrawStatus` + 类型（GachaDrawStatusVO/GachaRevealPrize）
- [改] `locale/gacha.zh-CN.ts` — `gacha.draw.*` 命名空间（盲盒语义：开盒/获得，禁中奖/抽奖；zh-CN + en）
- [改] `pages/gacha/detail.vue` — `onDraw()` 从 toast 占位 → `navigateTo('/pages/gacha/draw?machineId=')`（接通 Tier 2 可达链路）

## AI 自测（Tier 1A）

### 后端单测（mvn test，12/12 通过，含 5 个新 getStatus 用例）

```
Tests run: 12, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.904 s -- in org.dromara.gz.gacha.service.impl.GzGachaDrawServiceImplTest
```

新增 5 用例：
- `getStatus_drawNotYet_returnsDrawing` — draw 未落 → drawing，不解 snapshot / 不查图片
- `getStatus_drawn_ownUser_revealsPrize` — 本人 drawn → 解 prize_snapshot_json + 稀有度 + 图片签名 URL
- `getStatus_drawn_imageFail_fallbackPlaceholder` — prize 图 + 机器封面图都失败 → 占位图（不抛错）
- `getStatus_drawn_otherUser_forbidden` — 非本人 → DRAW_FORBIDDEN 8011，不解图片
- `getStatus_byDrawNo_drawn` — 按 drawNo 查 + prize imageId 为 null → 回退机器封面图

### draw/status 端点 curl（AC1，--noproxy，造 draw 后按 out_trade_no / draw_no 查）

```
=== ① drawn（本人 outTradeNo）===
{"code":200,"data":{"status":"drawn","drawNo":"DRW-20260617-900001","machineId":"2",
  "prize":{"name":"R1复测-SSR奖品-宫崎骏周边","imageUrl":"/static/images/mock-product.png",
           "rarity":"SSR","referenceValueCent":12900}}}
   ↑ machineId 序列化为 string（跨层契约）；prize_snapshot_json 解出 SSR + name + 参考价 12900；
     imageId=8012 file 不存在 → 回退占位图（解析路径不抛错）

=== ② drawing（不存在 outTradeNo）===
{"code":200,"data":{"status":"drawing","drawNo":null,"machineId":null,"prize":null}}
   ↑ draw 未落 → drawing（付款后异步开盒中），无 refunded 揭晓态

=== ③ 他人 draw（user_id=999）===
{"code":8011,"msg":"无权查看该开盒记录","data":null}
   ↑ 归属校验：非本人 → DRAW_FORBIDDEN

=== ④ 按 drawNo 查（本人）===
{"code":200,"data":{"status":"drawn","drawNo":"DRW-20260617-900001","machineId":"2",
  "prize":{"name":"R1复测-SSR奖品-宫崎骏周边","imageUrl":"/static/images/mock-product.png",
           "rarity":"SSR","referenceValueCent":12900}}}
```
（验证后清理测试 draw 数据：`DELETE WHERE pay_transaction_id IN (...)` → remaining=0；kill 后端 8080 释放）

### mp vitest（全量 30 文件 229 通过，含本卡新增 26 个用例）

```
 ✓ src/composables/useDrawPolling.test.ts (8 tests) 3ms
 ✓ src/pages/gacha/draw.logic.test.ts (18 tests) 7ms
 Test Files  30 passed (30)
      Tests  229 passed (229)
```

本卡覆盖点：
- **三段动画状态机**：`fullStageSequence` 顺序 spin→burst→reveal，reveal 终态 delay=0
- **轮询编排**：首次 drawn 即停（不 sleep）/ drawing N 次→drawn / 退化（前 11 次 1s，第 12 次起 5s）/ 累计超时→timeout（停 fetch）/ fetch 抛错不中断重试到超时
- **稀有度光晕映射复用**：`rarityGlowVar(r) === rarityColorVar(r)` 四档逐一断言（单一真源，不另写映射）；非法 → 兜底 N（不引第五档）
- **低端机 fallback**：benchmarkLevel 0/1 → 低端 / CPU<4 → 低端 / 判定不到 → 默认完整动画
- **盲盒禁词**：`gacha.draw.*` 全 16 个 key 扫无「抽奖/中奖/开奖/抽中」+ 金句「获得 SSR · {name}」+ 关键文案「开盒/获得/扭蛋记录」

### mp 构建 + 类型检查（build:mp-weixin exit 0）

```
DONE  Build complete.
（dist/build/mp-weixin/pages/gacha/draw.{js,json,wxml,wxss} + draw.logic.js 已生成）
（dist/build/mp-weixin/components/biz/BizGachaDraw.{js,json,wxml,wxss} 已生成）
（app.json 已注册 pages/gacha/draw；draw.json easycom 引入 BizGachaDraw/BizScreen/BizButton）
vue-tsc --noEmit exit 0
```
（build 尾部「正在打开微信小程序开发者工具」假挂起，dist 已生成，pkill cli -o，进程自然 exit 0 — memory: mp-build-devtools-hang）

## Tier 2 可达性（AC9，N=1）

✅ **可达链路**：扭蛋机详情页（GACHA-103）「投币开盒」CTA → `onDraw()` `navigateTo('/pages/gacha/draw?machineId=')` → 揭晓页 → dev wxMOCK 短路跳过真实支付直走「支付成功」→ 轮询 → 三段动画。

- 详情页 → 列表 → 首页扭蛋 teaser 全链路已上线（GACHA-102/103 已交付），无需临时入口。
- **dev wxMOCK 短路**（draw.vue `isMockPay()`：`VITE_WX_APPID.startsWith('wxMOCK')`）：占位 AppID 跳过 `uni.requestPayment`，toast「开发模式：跳过真实支付」后直走支付成功分支 → 让 Kevin 在 devtools 能走通揭晓动画（无需真实商户号）。memory 同款短路（useAuth.ts wxMOCK）。
- **本卡未加临时入口**（detail.vue 真入口已接通，无需 `Tier2-entry-temp` 标记）。

> ⚠️ **轮询揭晓依赖真实开盒事务**：dev wxMOCK 走「支付成功」后，draw 由支付回调异步落库。devtools 真机走通需 mock 支付回调触发开盒事务（GACHA-104 mock client 链路）。Kevin 批量人验时若 mock 回调未触发，轮询 60s 后走超时兜底跳扭蛋记录（符合 AC2 唯一兜底分支，不报错）。已揭晓动画本身（三段分镜 + 稀有度光晕）的视觉 + 状态机已由 vitest + curl 双层验证。

## 风险提示 / 已知 issue

- **R-动画视觉**：纯 CSS 三段动画（spin 晃动 / burst 集中线爆闪 + flash / reveal 稀有度光晕脉冲），不引 Lottie/GSAP（铁律 8）。视觉可接受度 V1.1 简版足够；低端机 benchmarkLevel≤1 或 CPU<4 跳段 1/2 直 reveal 渐入。
- **R-占位素材**：揭晓大图当前全回退占位图 `/static/images/mock-product.png`（测试 prize image_id 均 NULL）+ 右下角「来自谷子宇宙」水印（合规 R3）。正式 IP 商品图到位后自动经 image_id 签名 URL 渲染。
- **R-图鉴伏笔降级**：GACHA-107 未上线 → 伏笔条仅展示「已收入图鉴 / 查看图鉴」CTA，不显 X/Y 数字（AC4 强约束 #6），点击跳 `/pages/me/collection?machineId=`（GACHA-107 落地后该页接管）。
- **待 Kevin 批量人验关注（mp 端）**：① 详情页投币 → 揭晓页可达（dev wxMOCK）；② 三段分镜动画完整播放（转动→光爆→揭晓）；③ 稀有度光晕四档配色（SSR 金 / SR 紫 / R 蓝 / N 灰）；④ 揭晓金句「获得 {稀有度} · {名称}」盲盒语义；⑤ 双 CTA「再开一次」回详情 /「去看扭蛋记录」跳历史；⑥ 超时兜底跳扭蛋记录。

## 对下游 ticket 的提示

**对 GACHA-107（图鉴，依赖本卡）的契约**：
- **揭晓后「集齐进度 +1」入口**：本卡揭晓页底部图鉴伏笔条已埋 `goCollection()` → `uni.navigateTo('/pages/me/collection?machineId={machineId}')`，GACHA-107 实现该页接管。
- **图鉴进度数字 X/Y**：本卡 status 端点**不返回**集齐进度（那是 GACHA-107 契约，AC4 强约束 #6 降级口径）。GACHA-107 需新建 `GET /app/gz/gacha/collection/progress?machineId=`（查 `gz_user_gacha_collection`）；本卡伏笔条已预留位置，GACHA-107 上线后把「已收入图鉴」文案替换为「已获得 X/Y 件」即可（locale key `gacha.draw.collectionHint`，或图鉴页自取）。
- **集齐徽章数据源**：`gz_user_gacha_collection`（开盒事务内 UPSERT +1，本卡揭晓后该用户该机器该商品 drawn_count 已 +1）。
- **稀有度配色单一真源**：图鉴卡稀有度色继续复用 `detail.logic.ts` 的 `rarityColorVar/normalizeRarity`（GACHA-103 导出，本卡 draw.logic 也复用），不另写第三处映射。

## §AI 测试段（Tier 1B，主线程统一调度，2026-06-04）

coder 本轮对真实 infra（MySQL:3307 + 自起 8080）跑 live 验证，主线程 + 收尾合并 smoke 复核：

- **draw/status 端点 live**：4 场景过（本人 drawn 解 SSR snapshot / 不存在 drawing / 他人 8011 / by drawNo）；揭晓走 `prize_snapshot_json` 非实时算。
- **三段动画**：`BizGachaDraw` 纯 CSS transform/opacity（无 setInterval），稀有度光晕 `rarityGlowVar===rarityColorVar`（复用 103 单一真源，四档逐一断言）。
- **vitest 229 passed**（30 文件，含三段动画状态机 / 轮询超时 / 低端机 fallback / 盲盒禁词）；`build:mp-weixin` exit 0；`vue-tsc` exit 0。
- **合并 smoke（收尾）**：全 7 ticket 代码同一后端启动绿（SPI `[gacha,preorder]`），`GET /app/gz/gacha/draw/status` 路由注册（非 404）。
- **Tier 2 可达**：详情「投币开盒」→ draw 揭晓页 N=1，dev wxMOCK 短路可走通。

**结论：✅ Tier 1B 通过。** 真机支付→揭晓动画 happy path（含真实 requestPayment）进 Tier 2 批量人验。
