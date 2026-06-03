# GZ-ORD-102 完工报告 — mp 预购商品列表 + 筛选 + 排序（接真数据，解 ComingSoon）

> V1.1 D08 波次2 · mp ticket · 与 GZ-PAY-104 同子波次并行（PAY-104 改 gz-common，本卡改 gz-ord + miniapp）

---

## §0 状态自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本目录非 git 仓库，环境约定 "Is directory a git repo: No"） |
| 上游依赖 ORD-101 merge | ✅ migration `V202606060900__GZ-ORD-101-create-gz_ord_product-and-sku.sql` 已落 + gz-ord 模块文件齐 |
| 关键表/字段存在 | ✅ grep migration 确认（见下） |
| 编译/单测通过 | ✅ 后端 16 testcase 0 fail；mp ord vitest 16 pass |
| 关联 ADR | 任务卡标 `—`（无相关 ADR） |
| 构建纪律（无 -am） | ✅ 后端只 `-pl ruoyi-gz-ord` 不带 -am；未触碰 gz-common（PAY-104 占用） |

### grep migration 确认 gz_ord_product 展示字段（R1 风险闭环）

`V202606060900` 内字段全部命中任务卡锚定口径：
- `name` VARCHAR(128) ✅
- `main_image_id` BIGINT UNSIGNED（FK 语义→gz_file_object.id，禁裸 url）✅
- `ip_tag` VARCHAR(64) ✅
- `deadline_time` DATETIME(3)（**非 deadline_at**）✅
- `delivery_date_text` VARCHAR(64) / `delivery_date_exact` DATE（**非 arrival_***）✅
- `status` VARCHAR(16) DEFAULT 'off_shelf'，枚举 `on_shelf`/`off_shelf`/`auto_off` ✅
- `sales_count` BIGINT UNSIGNED（**热度复用，无 view_count**）✅
- `sort_no` INT ✅
- 索引 `idx_ip_status (tenant_id, ip_tag, status)` ✅
- `gz_ord_sku.price_cent` BIGINT（**非 price_fen**）/ `enabled` TINYINT ✅

**结论：零缺字段，本卡零 DDL（符合任务卡强约束 8 + R6）。当前 migration 最大版本 V202606061100（PAY-104），本卡未新增。**

### grep gz_file_object url 解析用法（复用 V1.0 机制）

- `org.dromara.gz.common.service.IGzFileService#getPresignedUrl(Long fileId)` → 返回 `GzFileObjectVO`（`.getUrl()` 带 1h 过期签名 URL，URL 不存裸串）。
- gz-news NEWS-001 同模式（cover 经 fileId 解析）。本卡 `GzOrdProductServiceImpl#resolveImageUrl(mainImageId)` 复用：NULL / 解析失败 → 占位图 `/static/images/mock-product.png`（R4 闭环，不返空串）。

---

## 实现摘要

> **重要发现**：本卡的后端（list/ip-tags 全链路）+ mp 前端（list.vue / BizPreorderCard / useCountdown / api/gz-ord.ts / i18n / 首页 teaser / pages.json / 两组 vitest）在我接手前已由上一轮落地（ORD-101 一并预建了 mp Controller 骨架，控制器注释即标 GZ-ORD-102）。本轮我执行了**完整代码审查（逐文件比对 8 个 AC + 强约束 1-8 + 决策 D1-D5 + 风险 R1-R6）+ Tier 1A 全量自测验证**，确认实现正确且 AC 全覆盖，未发现需返工项。

### 涉及文件（相对 `code/main/`）

**后端 ruoyi-gz-ord**（包 `org.dromara.gz.ord`）：
- `controller/applet/GzOrdProductMpController.java` — 基路径 `/app/gz/ord/product`，`@SaIgnore`（C 端浏览不挂权限）；端点 `GET /list` + `GET /ip-tags`（ORD-103 在本类追加 getDetail/validatePurchase）
- `service/IGzOrdProductService.java` + `service/impl/GzOrdProductServiceImpl.java` — `listForMp(req)` / `listOnSaleIpTags()`
- `domain/dto/applet/OrdProductListReq.java`（pageNum/pageSize=20/sortBy/ipTags）
- `domain/vo/applet/OrdProductCardVO.java`（id ToString / name / mainImageUrl / startPriceCent / ipTag / deadlineTime ISO8601 / deliveryText / salesCount）
- `domain/vo/applet/OrdProductMpListVO.java`（rows / total / serverNow 外层）
- `enums/OrdProductSortEnum.java`（ARRIVAL_ASC / HOT / DEADLINE_ASC + `ofCodeOrDefault` 非法兜底）
- `mapper/GzOrdSkuMapper.java#selectMinPriceByProductIds`（批量 GROUP BY MIN 价，免 N+1）

**mp miniapp**（相对 `miniapp/src/`）：
- `pages/ord/list.vue`（definePage 注册 `pages/ord/list`，navbar「预购日谷」）
- `pages/ord/list.logic.ts`（排序 tab 定义 + formatPriceCent / formatCountdown / formatDelivery 纯逻辑抽出供单测）
- `components/biz/BizPreorderCard.vue`（业务卡组件，BizPanel 包一层，不裸撒 wd-*）
- `composables/useCountdown.ts`（serverNow 校准 + onUnmounted clearInterval + computeRemaining 纯计算抽出）
- `api/gz-ord.ts`（getPreorderList / getPreorderIpTags + OrdProductCardVO/OrdPreorderListResult 类型）
- `locale/ord.zh-CN.ts`（ord.list.* zh + en 同文件，不混 emoji）
- `pages/index/index.vue`（「日谷预购」teaser url → `/pages/ord/list` + 去 soon，解 ComingSoon）
- `pages.json`（声明 pages/ord/list；tabBar 不动维持 3 tab；ord/index 占位页保留）

**测试**：
- `pages/ord/list.logic.test.ts`（9 testcase）
- `composables/useCountdown.test.ts`（7 testcase）
- 后端 `enums/OrdProductSortEnumTest.java`（4 testcase，排序映射 + 非法兜底）

---

## AI 自测（Tier 1A）

### 1. mp vitest — 本卡 ORD-102 相关文件（AC7）

```
 RUN  v2.1.9 .../miniapp
 ✓ src/pages/ord/list.logic.test.ts (9 tests) 3ms
 ✓ src/composables/useCountdown.test.ts (7 tests) 2ms
 Test Files  2 passed (2)
      Tests  16 passed (16)
   Duration  380ms
```

- `computeRemaining`：正常拆分天时分秒 / 不足一天省天段 / **归零分支（diff<=0 → expired 全 0）** / serverNow 校准语义 / parseIsoMs 边界 ✅
- `formatPriceCent`：整元省小数（12900→¥129）/ 角分保留 2 位（12990→¥129.90）/ null→价格待定 ✅
- `formatCountdown`：归零→已截止 / 有剩余天 / 不足一天省天段 ✅
- `ORD_SORT_TABS`：3 tab + 首项 = 默认 deadline_asc（对齐后端兜底）✅

> 全套 `pnpm test` 跑 130 testcase，**唯一 fail = `gz-bean.test.ts > bindMobile`（GZ-BEAN-004，期望 `mobile` 实际发 `code`）—— 非本卡引入的预存失败，与 ORD-102 无关**。本卡 ord 16 testcase 隔离运行全绿。

### 2. 后端单测 gz-ord（无 -am，并行安全；AC7②）

```
[INFO] Running org.dromara.gz.ord.enums.OrdProductSortEnumTest
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0 -- OrdProductSortEnumTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdSkuServiceImplTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdProductServiceImplTest
[INFO] Tests run: 16, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

- OrdProductSortEnumTest 钉死 3 枚举 → ORDER BY 子句映射 + 非法/空/null 兜底 DEADLINE_ASC ✅

### 3. mp 构建 build:mp-weixin（验证 app.json 含 pages/ord/list）

```
DONE  Build complete.
Run method: open Weixin Mini Program Devtools, import dist/build/mp-weixin run.

# app.json pages（grep dist/build/mp-weixin/app.json）：
pages/bean/index
pages/index/index
pages/me/index
pages/ord/index          ← 占位页保留（路由不断）
pages/ord/list           ← 本卡新页 ✅

# pages/ord/ 编译产物：list.js / list.json / list.wxml / list.wxss / list.logic.js ✅

# tabBar 仍 3 tab：pages/index/index | pages/bean/index | pages/me/index ✅（未加第 5 tab）
```

> mem 已知：build 尾部唤 wechat devtools cli 假挂起，dist 实际已生成（"DONE Build complete"），手动 kill cli 进程（已清理，无残留）。build 模式产物在 `dist/build/mp-weixin`（非 dev）。

### 4. list 接口契约 mock 返回（任务卡要求贴）

`GET /app/gz/ord/product/list?pageNum=1&pageSize=20&sortBy=deadline_asc&ipTags=CHIIKAWA`
后端 `R<OrdProductMpListVO>`：

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "rows": [
      {
        "id": "12",
        "name": "CHIIKAWA 毛绒挂件预购",
        "mainImageUrl": "https://cos.../presigned?...   (NULL → /static/images/mock-product.png)",
        "startPriceCent": 12900,
        "ipTag": "CHIIKAWA",
        "deadlineTime": "2026-08-20T23:59:59",
        "deliveryText": "2026-09-15",
        "salesCount": 42
      }
    ],
    "total": 8,
    "serverNow": "2026-06-03T15:37:00"
  }
}
```

mp http 封装解包：最外层 R 无 rows/total（http.ts L109 判断 false）→ 走 L112 `return responseData.data` → 前端 `getPreorderList` 收 `{rows,total,serverNow}` = `OrdPreorderListResult`。契约对齐 ✅
`GET /ip-tags` 返回 `R<List<String>>` = `{code,msg,data:["CHIIKAWA","海贼王"]}` → 解包返回数组 ✅

---

## AC 逐条核对

| AC | 状态 | 证据 |
|---|---|---|
| AC1 list 强约束 + 排序 + ipTags | ✅ | `listForMp` eq(status,on_shelf)+gt(deadline,now)+@TableLogic 软删；排序走枚举白名单 ORDER BY；ipTags 截断 10+warn |
| AC2 VO 字段 + serverNow | ✅ | OrdProductCardVO 8 字段 + OrdProductMpListVO.serverNow；起始价 batch MIN；图片解析+占位 |
| AC3 ip-tags 接口 | ✅ | `listOnSaleIpTags` DISTINCT ip_tag WHERE on_shelf+未截止+非空 |
| AC4 page UI（排序/chip/卡/下拉上拉/倒计时） | ✅ | list.vue + BizPreorderCard（C token，选中 var(--c-red)）+ onPullDownRefresh/onReachBottom + useCountdown 归零置灰禁点 |
| AC5 点卡跳详情 | ✅ | `goDetail` → `/pages/ord/preorder-detail?id=`（**对齐 ORD-103 实际命名**，非任务卡字面的 detail，见下游提示） |
| AC6 i18n zh+en 不混 emoji | ✅ | locale/ord.zh-CN.ts 全 key 双语 |
| AC7 vitest ≥2 | ✅ | 16 testcase（含倒计时归零 + 排序映射非法兜底）后端 4 + 前端 16 |
| AC8 Tier2 入口可达 | ✅ | 首页 teaser「预购」+「日谷预购」卡 → `/pages/ord/list`（去 soon，1 次点达；tabBar 不动；ord/index 保留） |

---

## 风险提示 / 已知 issue

- **R3 翻页跳号**（分页中商品被截止下架）：预购品类少、概率低，接受；卡片倒计时归零本地置灰兜底。
- **R4 主图占位**：`main_image_id` NULL / 解析失败 → `/static/images/mock-product.png`（C 系统 MOCK 水印占位，待甲方正版 IP 商品图替换，CLAUDE.md §7.5）。
- **gz-bean.test.ts 预存失败**（与本卡无关）：`bindMobile` 期望 `mobile` 字段实际发 `code`，属 GZ-BEAN-004 域。建议主线程派给 bean 域 ticket 闭环，不在本卡修。
- **待 Kevin 批量人验关注**（mp 端）：
  1. 首页「预购」teaser / 「日谷预购」卡点击 1 次 → 落预购列表页（不再 ComingSoon）
  2. 三态排序切换（截止紧迫默认 / 到货近 / 热度）列表正确重拉
  3. IP chip 横滑多选 + 「全部」清空，列表筛选生效
  4. 下拉刷新 + 上拉加载分页
  5. 卡片倒计时每秒走动；截止商品置灰 + 「已截止」+ 点击无跳转
  6. 点未截止卡 → 跳 `/pages/ord/preorder-detail`（ORD-103 落地前报"页面不存在"属预期）

---

## 对下游 ORD-103 的接力提示

1. **`GzOrdProductMpController` 已建**（`controller/applet/`，基路径 `/app/gz/ord/product`，`@SaIgnore`）→ ORD-103 在**同一个类追加** `GET /{id}`（getDetail）+ `POST /{id}/validate-purchase`（validatePurchase）。注释里已留 ul 占位。
2. **`api/gz-ord.ts` 已建**（mp 侧）→ ORD-103 在同文件追加 `getPreorderDetail(id)` / `validatePurchase(...)`，复用 `OrdProductCardVO` 风格 + ID string 契约。
3. **`composables/useCountdown.ts` 可直接复用**（详情页同样要截止倒计时；`useCountdown(deadlineIso, serverNowIso)` + `computeRemaining` 纯函数）。
4. **页面命名对齐（重要）**：列表→详情跳转用的是 **`/pages/ord/preorder-detail?id=`**（非任务卡 AC5 字面写的 `/pages/ord/detail`）—— 因 ORD-103 详情页实际命名为 `preorder-detail`。ORD-103 落地详情页时必须 `definePage` 注册路由名 `pages/ord/preorder-detail`，否则点卡跳转 404。
5. **起始价/图片解析机制可复用**：`GzOrdProductServiceImpl#resolveImageUrl` + `batchMinPrice`（详情单商品取 SKU 列表，可改用 `selectList` + 各 SKU enabled MIN，或直接展示全 SKU）。
6. **gallery_image_ids**（图集，逗号分隔 file_id）字段已在 schema，详情页轮播解析时同 `resolveImageUrl` 逐个解析。

---

## §AI 测试段（kevin-qa 完工后追加）

> 本卡运行于 subagent 嵌套限制下，无法 spawn kevin-qa。Tier 1A 已做扎实（vitest 16 + 后端 16 + build app.json 验证 + 接口契约核对）。**Tier 1B（mp 端 E2E / 后端集成 / 可达性验证）交主线程接管。**
