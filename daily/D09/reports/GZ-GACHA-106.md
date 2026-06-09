# GZ-GACHA-106 完工报告 — mp 抽奖历史（「我开过的」开盒记录）

> 复杂度 S ｜ 依赖 GACHA-104（`gz_gacha_draw` 表 + IDX 已建）｜ 后端 + mp ｜ 纯查询无建表

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | ✅ git root = RuoYi-Vue-Plus；gz-gacha 全模块 D09 未提交（正常，7 卡全 ✅ 后统一 commit） |
| 上游依赖 GACHA-104 merge | ✅ `gz_gacha_draw` / `gz_gacha_order` 表已建（`V202606171400` migration），entity/mapper/snapshot DTO 全在 |
| 关键类/表存在 | ✅ `GachaSnapshot.Machine/Prize`、`IDX (tenant_id,user_id,drawn_time DESC)`、`IGzFileService.getPresignedUrl`、`detail.logic.ts` 稀有度真源 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-gacha` 无错；mp `build:mp-weixin` exit 0 |
| ADR 已读 | 无相关 ADR（任务卡 ADR 段为 `—`） |
| 权威蓝图引用 | ✅ doc/12 §MP-GACHA-HISTORY ／ doc/11 §7.3 gz_gacha_draw ／ doc/tokens.md §1.4 四档稀有度色 ／ doc/10 §8.E7 snapshot 口径 |

**关键约束摘录（自检阶段确认）**：
- 强约束 #1：`gz_gacha_draw` 每行即一次成功开盒 → 历史天然全部成功、**无退款记录、无 `draw_status` 列过滤**（不臆造）。
- 强约束 #2：prize/machine 信息一律读 snapshot（`*_snapshot_json`），**不 join 实时表**（防后台改商品后历史失真，doc/10 §8.E7）。
- 强约束 #3：机器筛选用本人历史 **distinct machine**，不全量拉 `gz_gacha_machine`。
- 强约束 #4：图片走 `image_id → gz_file_object → url` 后端解析，不返裸 image_id。
- R8：扭蛋域无系统退款 → 正常路径无 `refunded` 记录。

## 实现摘要

### 改动文件

**后端**（`ruoyi-modules/ruoyi-gz-gacha/`，纯查询无 DDL）：
- 新增 `domain/vo/GzGachaDrawHistoryVo.java`（历史列表项扁平 VO，snapshot 已解）
- 新增 `domain/vo/GzGachaDrawMachineFilterVo.java`（机器筛选 chip VO）
- `mapper/GzGachaDrawMapper.java`：加 `selectMyHistoryMachines`（distinct machine + 取最近 snapshot）
- `mapper/GzGachaOrderMapper.java`：加 `selectStatusByDrawIds`（按 draw_id 批量取 business_status，避免 N+1）
- `service/IGzGachaDrawService.java` + `impl/GzGachaDrawServiceImpl.java`：加 `listMyHistory` + `listMyHistoryMachines`（复用现有 `presignedOrNull` / `readJson` 图片解析口径）
- `controller/applet/GzGachaDrawMpController.java`：加 `GET /my` + `GET /my/machines`
- 新增 `src/test/.../GzGachaDrawHistoryServiceTest.java`（9 场景）

**mp**（`code/main/miniapp/src/`）：
- `api/gz-gacha.ts`：加 `getMyHistory` / `getMyHistoryMachines` + VO 类型
- `locale/gacha.zh-CN.ts`：加 `gacha.history.*`（zh + en + t() 路由分支）
- 新增 `pages/gacha/history.logic.ts`（相对时间 + 稀有度配色复用 + 业务态判定，纯逻辑）
- 新增 `pages/gacha/history.logic.test.ts`（20 测试）
- 新增 `components/biz/BizDrawHistoryItem.vue`（列表项，仅 view/text/image + var(--c-*)）
- 新增 `pages/gacha/history.vue`（筛选 chip + 列表 + 分页 + 空态 + popup）
- `pages/gacha/index.vue`：加 Tier2 临时入口（`TODO(Tier2-entry-temp): GZ-GACHA-106`）

## AI 自测

### 编译 + 后端单测

```
$ mvn test -pl ruoyi-modules/ruoyi-gz-gacha
[INFO] Tests run: 9, Failures: 0, Errors: 0 -- GzGachaDrawHistoryServiceTest
[INFO] Tests run: 12, Failures: 0, Errors: 0 -- GzGachaDrawServiceImplTest（GACHA-104 无回归）
...
[INFO] Tests run: 57, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

GzGachaDrawHistoryServiceTest 9 场景覆盖：snapshot 解扁平 VO + businessStatus 批量映射 + drawn_time DESC ／ machineId 筛选 + 空页短路（不查 order/file）／ userId null 空分页 ／ referenceValueCent 可空 ／ 图片回退占位 ／ **无衍生订单匹配 → businessStatus null（不臆造 refunded，R8）** ／ distinct machine 解 snapshot ／ machineName null 兜底。

### history 端点 curl（造 3 draw 后按 user 查，验 DESC + snapshot + businessStatus）

```
# 1) 全部历史 GET /app/gz/gacha/draw/my  →  total=3，drawn_time DESC，snapshot 扁平 + 各自 businessStatus
{
  "total": 3,
  "rows": [
    { "drawId":"132","drawNo":"DRW-20260618-000003","machineId":"1003",
      "machineName":"咒术回战立牌机","prizeName":"SR-五条悟亚克力","rarity":"SR",
      "prizeImageUrl":"/static/images/mock-product.png","referenceValueCent":5900,
      "drawnTime":"2026-06-18 09:15:00","businessStatus":"in_logistics" },
    { "drawId":"131","drawNo":"DRW-20260617-000002","machineId":"2",
      "machineName":"R1复测-宫崎骏联名扭蛋机","prizeName":"R-龙猫挂件","rarity":"R",
      "referenceValueCent":null,"drawnTime":"2026-06-17 21:30:00","businessStatus":"delivered" },
    { "drawId":"130","drawNo":"DRW-20260617-000001","machineId":"2",
      "prizeName":"SSR-无脸男手办","rarity":"SSR","referenceValueCent":12900,
      "drawnTime":"2026-06-17 20:00:00","businessStatus":"pending_ship" }
  ], "code":200
}
# ✅ DESC 正确（132→131→130）；snapshot 扁平（machineName/prizeName/rarity）；
#    businessStatus 各自映射（in_logistics/delivered/pending_ship）；referenceValueCent 可空（R 款 null）；
#    id 全 string；图片 NULL → 后端已回退占位图

# 2) GET /app/gz/gacha/draw/my?machineId=2  →  total=2，全是机器 2（R + SSR）✅
# 3) GET /app/gz/gacha/draw/my/machines  →  [{"machineId":"1003",...},{"machineId":"2",...}] distinct 2 台，最近 DESC ✅
# 4) GET /app/gz/gacha/draw/my?pageSize=2  →  total=3 rows=2 first=DRW-20260618-000003（DESC 分页）✅
```

### 稀有度配色复用证据（单一真源，不另写第三处）

```
# history.logic.ts re-export detail.logic 的 rarityColorVar / normalizeRarity：
export { normalizeRarity, rarityColorVar } from './detail.logic'

# vitest 断言「同一实现」（对象引用相等）：
✓ rarityColorVar 与 detail.logic 同一实现（re-export 证据）   expect(rarityColorVar).toBe(detailRarityColorVar)
✓ 四档映射 var(--c-r-ssr/-sr/-r/-n)
✓ 非法/空 → N 兜底（不引第五档）
```

### mp vitest + build

```
$ npx vitest run src/pages/gacha/history.logic.test.ts
✓ src/pages/gacha/history.logic.test.ts (20 tests)
# 覆盖：相对时间五档边界（刚刚/分钟/小时/天/完整日期）+ 未来漂移 + 空格分隔兼容
#      + 稀有度配色复用证据 + 参考价可空 + 待发货标签 + 跳转判定 + 盲盒禁词自查

$ npx vitest run   （全量）
Test Files  31 passed (31)
     Tests  249 passed (249)   ← 含 history.logic 20，全域无回归

$ pnpm build:mp-weixin
DONE  Build complete.   （exit 0）
# dist/build/mp-weixin/pages/gacha/history.{js,json,wxml,wxss,logic.js} 生成
# history.json usingComponents 含 biz-draw-history-item / biz-screen / biz-customer-service-fab
# pages.json 自动注册 "pages/gacha/history"
```

### 盲盒语义自查（grep + vitest）

```
$ vitest: 盲盒语义自查 — history i18n 文案无「抽奖/中奖/开奖」系词  ✓
#   断言 all.not.toMatch(/抽奖|中奖|开奖|抽奖率|中奖率/) 通过
#   正向 all.toMatch(/扭蛋|开盒|获得/) 通过
# 页面标题「我开过的」/ 列表「获得」/ popup「获得详情」/ 空态「还没开过扭蛋呢」— 全盲盒语义
# 后端字段保留 draw 技术语义（gz_gacha_draw / drawn_time），不影响 UI
```

## 风险提示 / 已知 issue

- **下游订单详情未上线降级**（AC5 / R3）：`pending_ship`/`in_logistics` 点击跳 `/pages/me/order/detail?orderType=gacha&orderId=`；该页 V1.1 下游才建 → `uni.navigateTo` 的 `fail` 回调降级为本页 popup，不 hard-fail。
- **占位图**：seed 的 prize snapshot `imageId=null` → 后端回退占位图 `/static/images/mock-product.png`（待甲方素材；正式 prize 配图后真图自动显示）。
- 待 Kevin 批量人验关注（mp 端）：
  1. 从 `pages/gacha/index`（扭蛋机列表）顶部「我开过的 →」临时入口点进历史页（Tier2 可达）
  2. 历史列表 happy path：按时间倒序、机器筛选 chip 切换、触底加载下一页
  3. 点「待发货」项 → 跳订单详情（下游未上线则弹 popup）；点其余项 → 弹获得详情 popup
  4. 空态（新账号无开盒）→「还没开过扭蛋呢 — 去逛逛」CTA 跳扭蛋机列表
  5. 微信原生：未登录进页 → `ensureLoggedIn` 引导登录（取消则回退）

## 对下游 ticket 的提示

- **GACHA-107 图鉴 / 会员中心扭蛋历史入口**（业务主线真入口）实施时：§0 自检 `grep -rn "Tier2-entry-temp.*GZ-GACHA-106"` 找到 `pages/gacha/index.vue` 的临时入口（filter-bar 内「我开过的 →」chip + `goHistory()` + `.filter-chip--history` 样式），用会员中心真入口替换后**清理**这 3 处临时标记（注释 + 模板 + 样式 + 函数）。可达路径不断 —— 替换前 Kevin 走临时入口，替换后走真入口。
- 订单详情页 `/pages/me/order/detail?orderType=gacha` 上线后：本页跳转 `fail` 降级 popup 自动失效（navigateTo 成功即跳），无需改本页。
- `selectStatusByDrawIds`（OrderMapper）按 draw_id 批量取 business_status 的口径可被 GACHA-107 图鉴 / 订单聚合复用。

## §AI 测试段（Tier 1B，主线程统一调度，2026-06-04）

coder 本轮对真实 infra（MySQL:3307 + 自起 8080）跑 live 验证，主线程 + 收尾 smoke 复核：

- **history 端点 live**：`GET /app/gz/gacha/draw/my` total=3 `drawn_time` DESC、snapshot 扁平、businessStatus 各自映射、分页（pageSize=2→rows=2）、`/my/machines` distinct DESC；id string、图片 NULL 回退占位。
- **稀有度配色复用**：`history.logic` `export { rarityColorVar } from './detail.logic'`，vitest 断言对象引用相等 — 单一真源无第三处。
- **盲盒/无退款不变量**：文案「开盒记录」无禁词；无衍生订单 → businessStatus null（不臆造 refunded，R8）。
- **vitest 20/20**（history.logic，含相对时间五档 + 配色复用 + 盲盒禁词）；全量 249 测过；`build:mp-weixin` exit 0；后端 gz-gacha 57 测过无回归。
- **合并 smoke（收尾）**：`GET /app/gz/gacha/draw/my` 路由注册（非 404），全模块同后端启动绿。
- **Tier 2 可达**：本卡加临时入口 `pages/gacha/index.vue` filter-bar「我开过的 →」chip（`Tier2-entry-temp: GZ-GACHA-106`），N=1；待会员中心开盒历史正式入口 merge 后清理（GACHA-107 建的是图鉴入口，语义不同未清理，正确）。

**结论：✅ Tier 1B 通过。** 真机历史列表 happy path 进 Tier 2 批量人验。
