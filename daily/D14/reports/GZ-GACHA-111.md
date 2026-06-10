# GZ-GACHA-111 完工报告 — 扭蛋入口迁「我的」+ 端到端做活回归

> 纯 mp，无新增后端/表/menu/DDL。本日最后一项（P2）。
> R10 纠正点：**降开发优先级 = 仅入口迁移 + 做活回归，零 weight/概率/抽奖事务改动**（原 GACHA-110 权重卡已删）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 工作目录 / 依赖现状 | ✅ SYS-010 已在 me/index.vue 发现区建扭蛋入口卡 → `/pages/gacha/index`（真列表，非 ComingSoon） |
| 上游依赖 merge | ✅ SYS-010（入口卡 + tabbar 3 tab）+ GACHA-101~104（V1.1 gacha 全链路已交付） |
| 关键页存在 | ✅ gacha/{index,detail,draw,history}.vue + me/{index,collection}.vue + api/gz-gacha.ts |
| 临时入口 marker 现状 | ✅ grep 命中 GZ-GACHA-106 临时入口（gacha/index.vue line 85/115/174 + goHistory + filter-chip--history） |
| type-check 基线 | ✅ 0 error |
| ADR 已读 | 无相关（任务卡关联 ADR 为 `-`） |

**必读权威文档摘录**：
- PRD M2 §V1.2 定位调整：扭蛋**降开发优先级 = 入口迁「我的」+ 做活回归，不改概率/weight**。
- doc/12 §MP-GACHA-LIST（扭蛋机大厅 V1.2 做活）+ §4.0「我的」扭蛋入口卡 → MP-GACHA-LIST。

## 实现摘要

**本卡精确改动 4 个文件**（mtime 12:45-12:46 隔离；整仓 `git diff --stat` 含 18 文件，其余 14 个是 staging 分支 SYS-010 等前序未提交卡的导航重构，**非本卡**）：

| 文件 | 改动 | 性质 |
|---|---|---|
| `src/pages/me/index.vue` | 九宫格新增「我开过的」入口（key `gachaHistory` → `/pages/gacha/history`，icon 📜） | mp 真入口接通 |
| `src/locale/user.zh-CN.ts` | 新增 `entryGachaHistory: '我开过的'`（盲盒语义，禁抽奖系词） | i18n |
| `src/pages/gacha/index.vue` | 清理 GZ-GACHA-106 临时入口：删 `goHistory` 函数 + filter-chip--history 模板 + 样式 + 3 处 marker 注释（-16 行） | 临时入口清理 |
| `src/pages/gacha/history.vue` | 顶注释同步：临时入口归宿 → 改为会员中心九宫格正式入口说明 | 注释同步 |

**入口归宿决策（history 真入口）**：
- collection（GZ-GACHA-107，📔「我的图鉴」）= 按机器分组的奖品全集（数据源 `gz_user_gacha_collection`），语义「收藏图鉴」。
- history（GZ-GACHA-106，📜「我开过的」）= 按时间倒序的每次开盒流水（数据源 `gz_gacha_draw`），语义「开盒记录」。
- **两者不同语义、不同数据源 → history 需独立真入口**。故在 me 九宫格 collection 之后插入「我开过的」（3×3 九宫格刚好填满 9 格），用真入口替换 gacha/index 临时入口，可达不断。

## AI 自测（Tier 1A）

### type-check（0 error）
```
> vue-tsc --noEmit
（无任何输出 = 通过）
```

### vitest（374 tests passed，gacha 既有单测不破坏）
```
 ✓ src/api/gz-gacha.test.ts (3 tests) 3ms
 ✓ src/pages/me/orders.logic.test.ts (3 tests) 2ms
 ... (含 detail.logic / draw.logic / history.logic / list.logic 既有 gacha 单测全过)
 Test Files  40 passed (40)
      Tests  374 passed (374)
   Duration  3.66s
```
（stderr 中的 `[customer-service] ... failed` 是测试有意构造的兜底失败场景 console 输出，非测试失败）

### git diff 自证无 weight/概率/抽奖事务改动（AC3 硬条目）
```
$ git diff | grep -iE "weight|probability|概率|gz_gacha_prize"
-  font-weight: 900   ×7   ← 全是 CSS 字重（index/index.vue 前序删除），零 gz_gacha_prize.weight / 概率逻辑

$ git diff --name-only | grep -E "draw|prize"
(未触碰任何 draw/prize 文件 — 抽奖事务零改动)
```
draw.vue / draw.logic.ts / prize 相关文件 mtime 仍为 Jun 9 14:13（V1.1 交付时间），**本卡未触碰**。

### build:mp-weixin（dist 含全部 gacha 页 + me 页）
```
DONE  Build complete.

$ ls dist/build/mp-weixin/pages/gacha/   (全 12:47 新鲜编译)
detail.js/json/logic.js/wxml/wxss
draw.js/json/logic.js/wxml/wxss
history.js/json/logic.js/wxml/wxss
index.js/json/wxml/wxss

$ grep -oE "pages/(gacha|me)/[a-z-]+" app.json | sort -u
pages/gacha/detail / draw / history / index
pages/me/index / collection / coupons / ... (全注册)
```
（devtools cli 假挂起已 `pkill -f 'cli -o'`；后台 build 进程已清，无端口残留）

## 扭蛋端到端做活回归（静态链路走查 + build 验证）

SYS-010 改了导航 + 8 处 index→bean redirect，本卡验证 gacha 链路无回归：

| 步 | 路由 | 验证 |
|---|---|---|
| 1 入口 | me 发现区扭蛋卡 → `/pages/gacha/index` | ✅ SYS-010 已建，DISCOVER_ROUTE_MAP.gacha 命中 |
| 2 列表→详情 | index `goDetail` → `/pages/gacha/detail?id=`（BizGachaMachineCard @tap） | ✅ |
| 3 详情→投币 | detail line 112 → `/pages/gacha/draw?machineId=` | ✅ |
| 4 投币→mock 支付 | draw line 73 `wxMOCK` 短路（appId.startsWith('wxMOCK')）→ 跳过真实 uni.requestPayment 直走支付成功分支（toast 提示 + showToast mockPayHint） | ✅ mock 路径通 |
| 5 出奖→进订单/history | draw line 189/220 出奖后 `redirectTo /pages/gacha/history`；BizGachaDraw 动画出 1 件；衍生订单按 draw_id 落待发货（后端 GACHA-104 既有事务，本卡未动） | ✅ |
| 6 history 真入口 | me 九宫格「我开过的」→ `/pages/gacha/history`（N=1 真入口） | ✅ 本卡新建 |

**SYS-010 的 8 处 index→bean redirect 对 gacha 链路零影响**：gacha 链路自成闭环（me 发现区 → gacha/index → detail → draw → history），不经过 index/index.vue。grep gacha 页全部 navigateTo/switchTab/reLaunch/redirectTo 无指向旧 index 死链。history 兜底 `navigateBack fail → switchTab /pages/bean/index`（bean/index 仍是 SYS-010 重构后有效 tab，已核 pages.json line 296）。

## gacha 临时入口清理 grep before/after

**BEFORE**（3 处 GZ-GACHA-106 marker）：
```
src/pages/gacha/index.vue:85:// TODO(Tier2-entry-temp): GZ-GACHA-106, remove when 会员中心扭蛋历史入口 merged
src/pages/gacha/index.vue:115:  <!-- TODO(Tier2-entry-temp): GZ-GACHA-106, remove when 会员中心扭蛋历史入口 merged -->
src/pages/gacha/index.vue:174:/* TODO(Tier2-entry-temp): GZ-GACHA-106, remove when 会员中心扭蛋历史入口 merged */
+ goHistory() 函数 + filter-chip--history 模板 chip + 样式
```

**AFTER**（全仓清零）：
```
$ grep -rn "Tier2-entry-temp" src/        → exit 1（无匹配）
$ grep -rn "goHistory|filter-chip--history" src/pages/gacha/index.vue  → 无匹配
```
（draw.vue 的 `goHistory`(line 219/282) 是揭晓页「查看记录」**正常业务跳转**，非临时入口，保留正确。）

## 已知 issue / 风险

- **history 待发货项跳订单详情仍走降级 popup**（history.vue line 127-128 跳 `/pages/me/order/detail?orderType=gacha&orderId=drawId`，有 `fail → openPopup` 兜底，不崩）。**本卡有意不改**：order-detail（GZ-USER-102）按 `id=orderNo` 查 `getUnifiedOrderDetail`，而 `GachaMyHistoryItemVO` 无 `orderNo` 字段（仅 drawId/drawNo/machineId）。修正需后端 VO 加 orderNo → 违反本卡「无新增后端」硬约束，且非 SYS-010 引入的回归（GACHA-106 当时下游 order 未上线有意降级）。建议留 V1.2 后端 VO 扩字段单卡处理。
- 风险：me 页九宫格现 9 项（3×3 满格），后续若再加入口需注意第 4 行布局。

## 对下游 ticket 的提示

- gacha 临时入口已全清，**下游清理者无需再处理 GZ-GACHA-106 marker**（全仓 Tier2-entry-temp 已清零）。
- 若后续要让 history 待发货项直跳订单详情：需后端 `GachaMyHistoryItemVO` 加 `orderNo` 字段 + history.vue 改跳 `/pages/me/order-detail?id=${orderNo}`（注意是连字符 order-detail，非 order/detail 子目录）。

## §0 自检 / AC 对照

| AC | 满足 |
|---|---|
| AC1 入口接通 + 清理历史临时入口 | ✅ me 发现区扭蛋卡（SYS-010）已接通 + GZ-GACHA-106 临时入口已清，me 九宫格真入口替换 |
| AC2 端到端做活回归 | ✅ 列表→详情→投币→mock 支付→出 1 件→history 全链路静态走查 + build 验证无回归 |
| AC3 降优先级硬约束（无 weight/概率/事务改动） | ✅ git diff + mtime 双重自证，draw/prize 文件零触碰 |
| AC4 Tier 2 可达 | ✅ Kevin 从「我的」点扭蛋入口卡 1 次到扭蛋机列表；「我开过的」九宫格 N=1 到 history |
