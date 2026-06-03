# GZ-GACHA-105 — mp 三段分镜开盒动画 + 揭晓稀有度

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §用户操作流程 §抽扭蛋主路径 步骤 5-7 + §用户故事
**关联拆解**: doc/02-需求拆解.md §3.3 GZ-GACHA-105
**关联 mockup**: design/mockup/gacha-draw.html（**布局参考**；视觉以 C 系统为准 doc/13；动画落地用 doc/13 §3.2 待建 `BizGachaDraw`，不逐像素还原）
**关联 ADR**: —
**依赖**: GZ-GACHA-104（抽奖事务 + 防超卖 + `gz_gacha_draw` 落库，含 `prize_snapshot_json`）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机开盒全流程**（**§8 业务本质：付款必出 1 件 / 失败重抽不退款 / 扭蛋域无系统自动退款**；N7 拉结果 / N8 出奖动画揭晓 / N9 推图鉴进度；draw 轮询态 `pending`→`drawing`→`drawn`——付款后 @Async 开盒必出，只会 drawing→drawn，**不含 refunded**）+ 附录 A.6 状态枚举。**不是 §7（= 预购）。**
- **字段表**：doc/11-字段权威表.md **§7.3 `gz_gacha_draw`**（`prize_snapshot_json` JSON 结构：奖品名 / 封面 `image_id` / 稀有度 / 公示价值；`machine_snapshot_json`；`draw_no` / `pay_transaction_id`）+ §7.4 `gz_gacha_order`（衍生订单号 `GACHA-yyyyMMdd-6位`，伏笔历史/图鉴）+ §7.5 `gz_user_gacha_collection`（图鉴进度数据源）+ F7.5（公示价值单位 = 分，UI ÷100）。
- **UI 索引**：doc/12-UI-权威索引.md **§MP-GACHA-DRAW**（三段分镜 Frame1 转动 / Frame2 裂开光爆 / Frame3 揭晓稀有度光晕；揭晓后操作区：奖品大图 + 稀有度大角标 + 图鉴进度伏笔 + 集齐特典徽章 + CTA）。
- **设计语言**：doc/13-设计语言-C日漫浓墨.md **§3.2 出奖三段动画 `BizGachaDraw`**（转动 → 光爆 → 揭晓；集中线爆闪 `.c-burst` + 稀有度光晕 + 大字结果）。
- **稀有度色**：doc/tokens.md **§1.4 稀有度色**（SSR `--c-r-ssr` 金 / SR `--c-r-sr` 紫 / R `--c-r-r` 蓝 / N `--c-r-n` 灰，**四档不引第五档**，光晕走 token 不硬编码 hex/rgba）。

> ⚠️ **不引 tokens §9**（不存在）。出奖动画 / 稀有度光晕 / 收集驱动伏笔的权威 = tokens §1.4 + doc/13 §3.2 + doc/12 §MP-GACHA-DRAW。

## What

支付成功后 mp 端轮询 draw 状态 → 拿到 `drawn` 即播三段分镜开盒动画（转动 → 裂开光爆 → 揭晓稀有度光晕）→ 揭晓获得物大图 + 稀有度角标 + 图鉴进度伏笔（伏笔 GACHA-107 图鉴）。**付款必出 1 件**（开盒事务失败走重抽改派，扭蛋域无系统退款），故轮询只会 `drawing`→`drawn` 必达揭晓，**无 refunded 揭晓分支**；仅保留超时兜底（结果稍后到账跳扭蛋记录）。盲盒语义（获得 / 开盒 / 出现概率）。

## AC（验收标准）

- [ ] **AC 1**：mp 状态查询端点 `GET /app/gz/gacha/draw/status`（按 `payTransactionId` 或 `drawNo` 查，仅查询不改库）返回当前 draw 轮询态枚举（doc/10 A.6 子集：`pending` / `drawing` / `drawn`——付款后开盒必出，**不返回 refunded 作为揭晓态**）；状态 = `drawn` 时附 `prize_snapshot_json` 解出的揭晓数据（获得物名 / 封面 `image_id` / 稀有度 / 公示价值 `_cent`）+ `drawNo` + `machineId`。service 校验 draw 归属当前 `user_id`（非本人 → 403/空），复用 GACHA-104 的 `IGzGachaDrawService`，**不新建表、无 DDL**。
- [ ] **AC 2**：page `pages/gacha/draw.vue`：
  - 入参：`payTransactionId`（或 `orderId` / `machineId`，从 GACHA-104 投币流跳转 query 透传）。
  - 初始进入：全屏占位 + 轮询期屏蔽物理返回键（防误操作打断动画），揭晓后恢复。
  - 轮询 `status` 接口：起始 1s/次，12 次后退化为 5s/次；累计超 60s 仍未 `drawn` → 弹「已支付，结果稍后到账，请到扭蛋记录查看」并跳 `/pages/gacha/history`（GACHA-106）。**这是唯一兜底分支**（付款必出，开盒事务失败走重抽改派；无系统退款故无 refunded 揭晓分支）。
  - 拿到 `drawn` → 停轮询 → 播三段分镜（见 AC 3）。
- [ ] **AC 3**：三段分镜动画（doc/13 §3.2 `BizGachaDraw` + doc/12 §MP-GACHA-DRAW）：
  - **段 1 转动**（约 0~1.5s）：扭蛋机晃动 + 胶囊滚动（CSS `transform: rotate/translate` 关键帧）。
  - **段 2 裂开光爆**（约 1.5~2.5s）：胶囊裂开 + 集中线爆闪（`.c-burst` + CSS `radial-gradient` + `scale` + `opacity` 关键帧）。
  - **段 3 揭晓**（约 2.5s~）：中奖物居中放大 + 对应稀有度光晕 —— SSR `var(--c-r-ssr)` / SR `var(--c-r-sr)` / R `var(--c-r-r)` / N `var(--c-r-n)`，**光晕色严格走 token，禁硬编码 hex/rgba**。
- [ ] **AC 4**：揭晓后 UI：
  - 获得物大图（`image_id` 经签名 URL 渲染，非裸 url；空回退机器封面 `machine_snapshot_json.cover_image_id`）+ 稀有度大角标（走 `var(--c-r-*)`）+ 名称 + 公示价值（`_cent ÷ 100`，为空不展示，F7.5）。
  - **图鉴进度伏笔条**（doc/12 §MP-GACHA-DRAW 收集驱动）：底部条「已获得 X/Y 件 — 查看图鉴」点击跳 `/pages/me/collection?machineId={machineId}`（GACHA-107；X/Y 来自 AC 1 返回或 `/app/gz/gacha/collection/progress`，GACHA-107 提供，未上线则伏笔条仅展示 CTA 不显数字，不报错）。
  - 双 CTA：「再开一次」（跳回该机详情 GACHA-103，透传 `machineId`）/「去看扭蛋记录」（跳 GACHA-106）。
- [ ] **AC 5**：动画性能：
  - 仅用 CSS `transform` / `opacity` 关键帧（GPU 友好），**禁用 `setInterval` 逐帧重绘**。
  - 低端机 fallback：`navigator.hardwareConcurrency < 4`（或微信 `wx.getDeviceInfo` 等价判定）→ **跳过段 1/2，直接段 3 揭晓 + 渐入**（不卡死老机型）。
- [ ] **AC 6**：盲盒语义（D09 README §B）：mp 可见文案 + `t('gacha.draw.*')` key 用**扭蛋 / 开盒 / 获得 / 出现概率**；**禁** 抽奖 / 中奖 / 开奖。揭晓金句「获得 SSR · {prizeName}」（不是「中奖：XX」）。grep `t('gacha.*')` 与模板字符串无违禁词。
- [ ] **AC 7**：组件库无关纪律 —— 三段动画封装为 `components/biz/Biz*`（如 `BizGachaDraw` 或拆 `BizGachaSpinStage` / `BizGachaBurstStage` / `BizPrizeRevealCard`），不直接撒 `<wd-*>`；可见字符串走 `t('gacha.draw.xxx')` + zh-CN 默认（en 补齐），不混 emoji。
- [ ] **AC 8**：单测：① 后端 `getDrawStatusForMp` happy（drawn → 解 `prize_snapshot_json` 返揭晓数据 / 非本人 → 拒）；② mp vitest 轮询编排（mock 连续 `drawing` N 次 → `drawn` → 触发揭晓 callback；超时未 `drawn` → 跳 history 兜底分支）。**无 refunded 揭晓分支单测**（付款必出，无系统退款）。
- [ ] **AC 9: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从扭蛋机详情页（GACHA-103，含投币开盒 CTA）走「点开盒 → mock 支付成功 → 自动进本揭晓页」可达；GACHA-104 投币流已跳本页，本卡承接其 query。**若 §0 自检发现 GACHA-104 投币 CTA 尚未跳本页**：在 `pages/gacha/draw.vue` 顶部加临时调试入口仅 dev（`#ifdef` 调试态用 mock drawNo 直进揭晓），注释 `<!-- TODO(Tier2-entry-temp): GZ-GACHA-105, remove when GZ-GACHA-104 投币流跳转接通 -->`。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaDrawAppController.java` 加 `getStatus(...)` 只读方法（mp 前缀 `/app/gz/gacha/...`）。
  - service 复用 GACHA-104 `IGzGachaDrawService`，加 `getStatusForMp(payTransactionId/drawNo, userId)`（校验归属 + 解 `prize_snapshot_json`）。
  - **无 DDL**（不新建表）；如确需新增列再走 `V<yyyyMMddHHmm>__GZ-GACHA-105-<desc>.sql`（时间戳 > 当前最大 `V202606061500`，已应用迁移不可改）。
- **小程序**：`code/main/miniapp/src/`
  - `pages/gacha/draw.vue`
  - `components/biz/BizGachaDraw.vue`（或拆 `BizGachaSpinStage` / `BizGachaBurstStage` / `BizPrizeRevealCard`）
  - `composables/useDrawPolling.ts`（轮询编排 + 退化 + 超时）
  - `api/gz-gacha.ts` 加 `getDrawStatus(...)`
  - i18n `gacha.draw.*`（zh-CN / en_US）
- **测试**：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am`（status service 单测）+ `pnpm test`（vitest 轮询逻辑）+ 微信开发者工具实跑三段动画 + 低端机 fallback 截图。

## 备注

### 强约束

1. **draw 轮询态锚 doc/10 A.6 子集**（`pending`/`drawing`/`drawn`）——付款后 @Async 开盒必出 1 件（失败重抽改派，无系统退款），轮询只会 drawing→drawn，**不把 refunded 当揭晓主流程态**；**禁**自造 `pending_pay`/`paid`/`pending_draw`/`stock_empty_refunded`，**禁**任何"抢空→退款揭晓分支"。
2. **snapshot 取 `prize_snapshot_json`**（JSON 列，doc/11 §7.3）——不散列成多列；图片用 `image_id` FK `gz_file_object`，前端换签名 URL，**不存裸 url**。
3. **稀有度光晕严格走 C 稀有度 token**（`var(--c-r-ssr/-sr/-r/-n)`，tokens §1.4）——四档，不引第五档，不硬编码 hex/rgba。
4. **三段分镜节奏**（doc/13 §3.2）：转动 → 裂开光爆 → 揭晓，不省略段；低端机才走 fallback 直揭晓。
5. **盲盒语义严格**（D09 README §B）：扭蛋 / 开盒 / 获得 / 出现概率；后端 enum/字段（`gz_gacha_draw` / `drawn` / `draw_no`）可保留 `draw` 技术语义，UI 字符串不许出现违禁词。
6. **图鉴进度伏笔不可省略**（doc/12 §MP-GACHA-DRAW 收集驱动）；GACHA-107 未上线时伏笔条降级（仅 CTA，不报错）。
7. **mp 管理权限复用 ADR-0004 底座**（本卡为纯 C 端读取，无需 `@SaCheckPermission`；status 端点按当前 `app_user` 会话校验 draw 归属即可）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 轮询查 status 而非 ws 推送 | V1.1 简单可靠；微信小程序 ws 维护成本高；起始 1s 退化 5s 延迟可接受 |
| D2 | 动画纯 CSS（不引 Lottie / GSAP） | 性能 + 兼容 + 不引未澄清依赖（铁律 8）；视觉可接受度足够（V1.1 简版） |
| D3 | 低端机 fallback 用 hardwareConcurrency / wx.getDeviceInfo | 简单有效；判定不到时默认走完整动画 |
| D4 | 揭晓数据后端从 `prize_snapshot_json` 解出回传 | 历史抽奖即便机器改名 / 下架也不丢信息（doc/10 §8.E7 snapshot 口径） |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R0 | 上游表/接口未就绪即开工 | **§0 自检 `grep` migration 目录确认 `gz_gacha_draw` 实际存在**（GACHA-104 落地后）+ `grep` 出 `IGzGachaDrawService` 实际存在，不假设上游已 merge；不存在 → STOP 报 Kevin |
| R1 | 用户动画中切后台 / 关闭 mp | 重进时再查 status，已 `drawn` 直接进揭晓态（不重播段 1/2） |
| R2 | 轮询浪费流量 | 1s × 12 次后退化 5s；超 60s 跳扭蛋记录页（不卡死） |
| R3 | 揭晓截图分享 IP 占位 emoji 不雅 | 占位期右下角加「来自谷子宇宙」水印 + 不用真实 IP 图（合规）；正式素材到位后替换占位 |
| R4 | 低端机 fallback 判定不准 | 判定不到设备信息时默认完整动画；段 1/2 自然降级（CSS 动画卡顿不阻塞揭晓） |
| R5 | GACHA-107 图鉴未上线导致进度条取数失败 | 伏笔条降级仅展示「查看图鉴」CTA，不显 X/Y、不报错 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
