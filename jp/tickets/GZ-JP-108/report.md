# GZ-JP-108 完工报告 — admin 履约看板（店员侧最重要的页）

> **accept 三条全 PASS**（菜单结构 / getRouters 真下发 / **Playwright 6 用例全绿 40.1s**）。
> ⚠️ 本卡经历 **3 次 API 503 中断**（server-side，非代码问题），由主线程接手收尾。下面标注了「接手前已有」与「主线程补的」。

## 交付分工（诚实标注）

| 部分 | 谁做的 |
|---|---|
| `src/views/gz-jp/fulfill/index.vue`（43KB 看板主页）| 中断前的 subagent |
| `src/api/gz-jp/fulfill.ts`（277 行 API 层）| 中断前的 subagent |
| `V202608071157__GZ-JP-108-seed-menu.sql`（菜单 14030 段 + 7 权限位）| 中断前的 subagent |
| `e2e/gz-jp/fulfill-fixtures.ts`（夹具，7.9KB）+ `playwright.config.ts` | 中断前的 subagent |
| **`e2e/gz-jp/fulfill-board.spec.ts`（accept #3 本体，6 用例）** | **主线程补** |
| 跑通验收 + 修 spec 里 4 处错误假设 | 主线程 |
| i18n `gzJpFulfill` 块 | subagent 写，主线程从 Kevin 的在飞改动里**摘干净**后单独提交 |

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 菜单 14030 段空闲 → 已 seed | ✅ 14030 履约看板(C) + 14031-14036 六个按钮位 |
| 迁移已真库应用 | ✅ `flyway_schema_history` 202608071157 `success=1` |
| 上游 106/107 接口可调 | ✅ 后端 8080 健康，`/system/gz/jp/fulfill/*` 全部就绪 |
| 父目录 14000 复用不重建 | ✅ parent_id=14000（101 已建） |
| ⚠️ 工作区有**非本卡**的 gz-bean-053 在飞改动 | ✅ 全程未碰、未提交（见「提交纪律」） |

**权限位**（含 107 建了端点但按约定不 seed 的两个）：
`gz:jp:fulfill:{list,advance,ship,markFailed}` + `gz:jp:refund:{list,retry}`

## accept 三条

### #1 菜单 path/component 非空且父级有效 ✅
```
$ docker exec ... "SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14030 AND 14039
    AND ( (menu_type IN ('M','C') AND (path IS NULL OR path='')) OR ... )" | grep -qx 0 &&
  docker exec ... "SELECT COUNT(*) ... BETWEEN 14030 AND 14039" | grep -qE '^[1-9]'
ACCEPT1 PASS

14030 履约看板   C 14000 fulfill gz-jp/fulfill/index  gz:jp:fulfill:list
14031 看板查询   F 14030                              gz:jp:fulfill:list
14032 批量推进   F 14030                              gz:jp:fulfill:advance
14033 批量发货   F 14030                              gz:jp:fulfill:ship
14034 标记购买失败 F 14030                            gz:jp:fulfill:markFailed
14035 退款单查询 F 14030                              gz:jp:refund:list
14036 退款重新发起 F 14030                            gz:jp:refund:retry
```

### #2 getRouters 真下发本页路由 ✅
```
ACCEPT2 PASS
```
（⚠️ 该 accept 原文把 `clientId` 写成 header，跑起来必 500 —— **主线程已在 GZ-JP-106 收尾时统一修正 108/109 两张卡的 prompt.md**，`clientId` 是 body 字段。）

### #3 按客人聚合 + 批量推进 + 批量发货 E2E ✅
```
$ npx playwright test e2e/gz-jp/fulfill-board.spec.ts --reporter=line
[1/6] ★ 按客人聚合：组头显示客人 + 款数，展开后是该客人的商品行（跨订单同组）
[2/6] ★ 终态行（已发货）不可勾选
[3/6] ★ 跨客人勾选 → 批量发货置灰并提示
[4/6] ★ 批量推进（跳过中间态：购买中 → 清关中），UI 与库双断言
[5/6] ★ 批量发货：跨订单同客人共用一个运单号，UI 与库双断言
[6/6] ★★ 批量标记购买失败必须二次确认（会触发真实退款，不可逆）
  6 passed (40.1s)
```

**每个写操作都是 UI + 库双断言** —— 页面弹「操作成功」而库里没变过，是这类看板最典型的假绿：
- 推进后 `queryItemStatus(99101).status === 'customs'`（跳过了 await_seller_ship / jp_shipped 两个中间态）
- 发货后两行都 `delivered` 且 `tracking` 是**同一个**新单号（跨订单 A1+A2 → 同包裹）
- 标记失败**点确认框之前**先断言库里仍是 `purchasing`（证明二次确认不是摆设），确认后才变 `purchase_failed`

夹具跑完硬删，验证 `gz_jp_order_item WHERE id BETWEEN 99101 AND 99199` → **0 行残留**。

## 主线程写 spec 时踩到并修正的 4 处错误假设

这 4 处都是**我的 spec 写错**、不是产品缺陷，记下来免得下次重犯：

1. **`orderNo` 筛选是精确匹配不是前缀**（GZ-JP-106 契约写明「精确」）。原本想用 `JPO-E2E108-` 前缀收敛看板，结果一条都匹配不上、拿到空看板还以为是聚合坏了。改用 `filter-event` 按夹具场筛。
2. **登录不能走 UI 表单**。改用仓里既有的注入 token 法（`test/e2e/lib.mjs` 的做法），并踩到它注释里写死的坑：plus-ui 的 `useStorage('Admin-Token', null)` 默认值是 null ⇒ VueUse 用 'any' 序列化器，**必须写原始 token，`JSON.stringify` 加的引号会让后端 401**。
3. **一张订单有 2 个商品行时，订单号列本来就出现 2 次** —— 我的 `getByText(orderNo)` 撞 strict mode。加 `.first()`（这是正确渲染，不是重复）。
4. **★ 全成功时页面只弹绿条、不弹结果弹窗** —— 页面刻意的设计（源码注释：「有被拒的行才值得打断店员；全成功时一个绿条就够了」）。我原本断言 `result-dialog` 可见，是把「好设计」当成了 bug。改断言 `.el-message--success` + 库状态。
   （对照：**标记购买失败恒弹弹窗**，因为涉及真实退款，值得每次打断。）

## 提交纪律（★ 本次特殊情况）

工作区里有**不属于本卡**的 `GZ-BEAN-053 day-pass weekday price` 在飞改动（`ruoyi-gz-bean/**`、`src/api/gz-bean/seatTypeConfig.ts`、`src/views/gz-bean/seat-type-config/index.vue`、`V202608082021__GZ-BEAN-053-*.sql`）。

**麻烦的地方**：`src/lang/zh_CN.ts` / `en_US.ts` 里，我的 `gzJpFulfill` 块与 Kevin 改的 4 行 gz-bean 文案**在同一个文件**。处置：把两个 lang 文件退回 HEAD 版本、只嫁接我的 `gzJpFulfill` 块进去后提交，提交完再把 Kevin 的完整版本还原回工作区。

核验结果：
```
提交里 gz-bean 文件数 = 0（两个仓都是）
Kevin 的 gridColDayPass 已还原到工作区 = 1 处
我的 gzJpFulfill 已进 HEAD = 1 处
Kevin 剩余未提交改动：gz-bean 4 个源文件 + 2 个 lang 文件的 9 行 + 1 个迁移 —— 完好无损
```

另：`.gitignore` 加了 `/test-results/` 与 `/playwright-report/`（Playwright 失败截图与 trace，不该入库）。

## 风险提示 / 已知 issue

1. **本卡页面未经人眼看过**。6 个 E2E 用例覆盖的是功能与数据流；**视觉（列宽、分组展开的观感、操作条位置）没有人或截图 diff 看过一眼**。建议 Kevin 抽验时重点看这一页 —— 它是店员每天要用最久的页。
2. **`playwright.config.ts` 的 webServer 自动起 dev server 在本机会超时**（240s 打不住）。实测原因：health-check 的 `http://localhost:8090/index` 探测被本机 clash 代理吞掉，而 dev server 本身 2.5s 就起来了。**跑法**：先手工 `BROWSER=none pnpm dev --port 8090 --host 127.0.0.1 &`，再 `unset *_PROXY; export NO_PROXY='*'` 后跑 playwright（`reuseExistingServer: true` 会直接复用）。已在本报告写明，未改 config（改 config 要动 Kevin 可能在用的开发流）。
3. **107 报告建议「支付管理页对 jp 交易禁用退款按钮」本卡未做** —— 那是支付域的页面，不在本卡 touches 内。仍是待办（107 报告风险 #1）。
4. **E2E 会改真库**：夹具 id 段 99101-99199，跑完硬删。`KEEP_E2E_FIXTURES=1` 可保留现场排查。config 里 `workers: 1` 强制串行（并发跑会互相踩状态）。
5. **待 Kevin 残留人验**：本卡是纯 admin 页，**不碰真机微信原生能力** → 按项目约定 Tier 2 人验 N/A；但因为它是店员主战场且视觉未验（见风险 1），建议纳入下次抽验菜单。

## 对下游的提示

- **GZ-JP-301（联调回归上线）**：本页的 6 个 Playwright 用例可直接纳入上线前回归；跑法见风险 2。
- **退款失败重试入口已有权限位**（`gz:jp:refund:retry`，14036）与抽屉（`refund-drawer` / `refund-retry-${row.id}`），107 的重试端点已接上。
- **看板筛选项**（供排查用）：客人关键词（★ 只匹配昵称/openid，**搜不了手机号** —— 109 报告已登记，改它要动 gz-common 检索实现）、履约状态多选、场、订单号（精确）、运单号、下单时间段。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

建议覆盖：重跑本卡 6 个 Playwright 用例（注意风险 2 的 dev server 起法）；权限矩阵（非超管角色进本页应看得到但按钮按权限位隐藏）；与 106/107 后端的契约回归（4108/4109/4110/4111 各错误码在 UI 上的表现）；**跨客人勾选拦截**与**标记失败二次确认**这两条是本页最不能退化的护栏。
