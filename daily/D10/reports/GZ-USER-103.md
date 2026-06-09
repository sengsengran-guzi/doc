# GZ-USER-103 完工报告 — mp 跨境物流 C1 2 态 + 终态展示（只读侧）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | N/A — 本仓库无 git（env "Is directory a git repo: No"），用文件清单替代 diff --stat |
| 上游 USER-102 已就绪（详情页 + BizLogisticsCard 占位 + 透传点） | ✅ order-detail.vue:172 `<BizLogisticsCard>` 占位已接 logistics-status/cn-carrier-code/cn-tracking-no |
| 上游 USER-101 统一 VO 含 4 物流字段（AC7 核对） | ✅ GzUnifiedOrderVo / UnifiedOrderDetailVo 实有 `logisticsStatus` / `cnCarrierCode` / `cnTrackingNo` / `deliveredTime`（**命名 deliveredTime，非 deliveredAt**，强约束 #8 满足）；mp api/gz-user.ts 镜像 4 字段齐 |
| 字典 gz_express_carrier 是否已 seed | ⚠️ **未 seed** — 仅 ORD-104/GACHA-104 建表注释提及，字典本体缺失 → 本卡补 seed（9 项，供 D11 ADMIN-104 写入侧下拉；mp 只读侧走前端静态表不依赖它） |
| 关键蓝图引用 | ✅ doc/10 §9（C1 2 态 + 终态裁定）/ doc/11 §6.4 物流字段 + §10.2 gz_express_carrier 9 项 / doc/12 §MP-ORD-DETAIL §页面结构 4 |
| mp 构建到 dist | ✅ DONE Build complete + BizLogisticsCard.{js,wxml,wxss,json} + order-detail.* 生成 |
| vitest unit | ✅ useExpressCarrier 19/19 + me 全域回归 36/36 无回归 |
| type-check（vue-tsc --noEmit） | ✅ 0 error |
| migration 版本序 | ✅ V202606190000（新 max > V202606181400） |
| ADR 已读 | ADR-0005（C1 物流 2 态裁定，本卡实装；确认不画 7 节点 / 不引第三方轨迹库） |

### §0 关键蓝图引用摘录（C1 一票否决条款复核）

- **doc/10 §9 跨境物流权威状态（C1 裁定）**：logistics_status ∈ `in_japan` / `in_china_dispatching` / `delivered`，**独立于 business_status 并行**（扭蛋订单可 business_status=drawn + logistics_status=in_japan 同时存在）。
- **doc/11 §6.4 + §10.2**：签收时间字段 `delivered_time`（钉死 deliveredTime）；gz_express_carrier 9 项 = yto/sf/zto/yunda/jd/ems/debang/jitu/other。
- **doc/12 §MP-ORD-DETAIL §页面结构 4「物流 2 态卡片」**：态 1 仅文案无操作；态 2 快递中文名 + 单号 + 复制 + 查询提示；态 3 终态已签收 + 历史保留。
- **一票否决禁项已全部规避**：无 7 节点 / 无 logistics_node / 无 gz_logistics_node 表 / 无批次推进 / 无 GROUP BY 自动归集 / 无 gz_express_company / 无物流时间线色 token / 无第三方轨迹库（快递100/快递鸟）。

## 实现摘要

### 小程序（miniapp，主体）

| 文件 | 动作 | 作用 |
|---|---|---|
| `src/composables/useExpressCarrier.ts` | 新增 | `EXPRESS_CARRIER_MAP` 9 项静态表（对齐 doc/11 §10.2）+ `carrierName()`（未知/空→「其他」兜底，AC5）+ `formatDeliveredTime()`（YYYY-MM-DD HH:mm，AC4）。纯函数不依赖 uni/Vue，供 vitest |
| `src/composables/useExpressCarrier.test.ts` | 新增 | 19 vitest：9 项映射逐一 + 恰好 9 项 + 兜底（未知/null/undefined/空串）+ 格式化（ISO/空格/null/undefined/脏串） |
| `src/components/biz/BizLogisticsCard.vue` | **实装**（替换 USER-102 占位） | 3 态卡：态1 in_japan 纯文案无操作元素（AC2）/ 态2 in_china_dispatching 快递中文名+单号+「复制单号」BizButton(uni.setClipboardData,AC3)+查询提示 / 态3 delivered 已签收+签收时间+历史快递/单号保留（无复制按钮,AC4）。加 `deliveredTime` prop（AC1，钉死命名）。Biz* + var(--c-*) 无 wd-*（AC9/强约束 #6） |
| `src/pages/me/order-detail.vue` | 改 1 处 | `<BizLogisticsCard>` 补透传 `:delivered-time="detail.deliveredTime"`（AC6） |
| `src/locale/user.zh-CN.ts` | 加 keys | `logiDispatched`(已发往中国) / `logiCopyEmpty`(暂无单号) / `logiDeliveredTimeLabel`(签收时间) 双语；其余 logi* key USER-102 已备 |

### 后端（仅补字典 seed，无表 / 无接口 / 无 Java 改动，AC7）

| 文件 | 动作 | 作用 |
|---|---|---|
| `db/migration/V202606190000__GZ-USER-103-seed-gz_express_carrier-dict.sql` | 新增 | sys_dict_type `gz_express_carrier`(dict_id 9130) + 9 条 sys_dict_data(91301-91309，tenant '000000' 系统级)。**供 D11 ADMIN-104 admin 录单号下拉**；mp 只读侧走前端静态表不依赖此字典（决策 D2，离线友好），三端同一份 9 项枚举 |

**统一布局五段顺序不变**（USER-102 强约束 #1）：状态卡 → 商品多态 → **物流卡（本卡实装）** → 订单信息 → 底部 CTA。物流卡 `logisticsStatus` 独立于状态卡 `businessStatus`（AC8）。

## AI 自测（≥ 3 代码 block）

### vitest — useExpressCarrier（19/19）

```
$ pnpm vitest run src/composables/useExpressCarrier.test.ts
 ✓ src/composables/useExpressCarrier.test.ts (19 tests) 3ms
 Test Files  1 passed (1)
      Tests  19 passed (19)
```
覆盖：9 项映射逐一 (yto→圆通速递 / sf→顺丰速运 / zto→中通快递 / yunda→韵达速递 / jd→京东快递 / ems→EMS / debang→德邦 / jitu→极兔速递 / other→其他) + 映射表恰好 9 项 + 兜底 4 例（未知 code/null/undefined/空串 → 「其他」）+ formatDeliveredTime 5 例（ISO 带 T / 空格分隔 → YYYY-MM-DD HH:mm；null/undefined/脏串 → 空串）。

### type-check + me 全域回归（36/36，无回归）

```
$ pnpm type-check      # vue-tsc --noEmit
（0 error）

$ pnpm vitest run src/pages/me/
 ✓ src/pages/me/orders.logic.test.ts (3 tests)
 ✓ src/pages/me/order-detail.logic.test.ts (8 tests)
 ✓ src/pages/me/collection.logic.test.ts (25 tests)
 Test Files  3 passed (3)
      Tests  36 passed (36)
```

### mp 构建 + 编译产物验证

```
$ pnpm build:mp-weixin           # devtools cli 唤起属正常（已 pkill），dist 已生成
DONE  Build complete.

$ ls dist/build/mp-weixin/components/biz/ | grep -i logistics
BizLogisticsCard-vendor.js  BizLogisticsCard.js  BizLogisticsCard.json
BizLogisticsCard.wxml  BizLogisticsCard.wxss

$ grep -o "setClipboardData" dist/build/mp-weixin/components/biz/BizLogisticsCard-vendor.js | uniq -c
   1 setClipboardData          # 复制单号 uni API 已编译进 vendor chunk（强约束 #3）

$ ls migration | sort | tail -1
V202606190000__GZ-USER-103-seed-gz_express_carrier-dict.sql   # 新 max 版本号，无冲突
```

### 3 态渲染逻辑验证（编译 wxml 结构 + vitest 断言）

```
态1 in_japan：wxml 渲染 logi__main(商品在日本备货中) + logi__sub，无 BizButton / 无 row → 无操作元素 ✅ (AC2)
态2 in_china_dispatching：carrierName(cnCarrierCode) 中文名 + cnTrackingNo + BizButton(复制单号→uni.setClipboardData→toast已复制) + 查询提示 ✅ (AC3)
态3 delivered：logi__main--done(--c-green 已签收) + formatDeliveredTime(签收时间) + 历史 carrier/单号保留(hasHistory)，无 BizButton ✅ (AC4)
未知 code 兜底：carrierName 任何非 9 项 / 空 → 「其他」(vitest 4 例) ✅ (AC5)
```

## 风险提示 / 已知 issue

- **R1（字典 seed 仅供 admin 写入侧）**：mp 只读侧用前端静态表 `EXPRESS_CARRIER_MAP`（决策 D2），与后端 seed 是同一份 9 项枚举但**两处维护**。若未来快递公司增减，需同步改 useExpressCarrier.ts + 该 migration（新建更大时间戳文件，旧 migration 不可改）。已在两文件头互相注明「三端同源」。
- **R2（联调态切换依赖手改 DB）**：D11 ADMIN-104 写入 UI 未交付前，态 2/3 需手动改 DB 触发（AC11 已给 UPDATE 语句）。默认订单态 1 in_japan。
- **R3（旧 mockup order-detail.html 7 节点版）**：人验时勿对照旧 mockup；视觉以 doc/tokens.md + doc/13 C 系统遵循度判定（粗墨边 / 硬投影 / 朱红复制按钮 / 绿签收），不逐像素。
- **R4（无后端 Java / 接口改动）**：AC7 满足 —— 物流 4 字段已由 USER-101 统一 VO 暴露，本卡未碰 gz-user Java 代码；仅补 SQL 字典 seed。

## 对下游 ticket 的提示

1. **D11 ADMIN-104（admin 物流写入侧，下沉 mp 店员端）**：录单号下拉直接用本卡 seed 的 `gz_express_carrier` 字典（dict_id 9130，9 项 + other 兜底）。写入 `cn_carrier_code` 时取 dict_value（yto/sf/...），mp 只读侧 carrierName() 自动翻译。推进态 2 需同写 `cn_dispatched_at`；推进态 3 写 `delivered_time`（钉死命名，禁 deliveredAt）。
2. **mp 统一订单列表（USER-101 mp 消费侧，尚未建）**：扭蛋订单详情可达性依赖统一列表落地（沿用 USER-102 对下游 #3）；本卡物流卡在预购 + 扭蛋详情页通用，扭蛋订单态 2/3 同样渲染。
3. **doc 源头（§9.5 #1）**：doc/11 §10.2 已有 gz_express_carrier 9 项定义，本卡 seed 与之对齐；若 product 后续调整快递公司清单，改 doc/11 §10.2 为源头 + 同步前端静态表 + 新 migration。

## 风险提示 / 待 Kevin 批量人验关注（mp 端）

- 进入路径（Tier 2 可达，AC11，N=4 复用 USER-102 已通路径，无需新入口）：首页 → 底部「我的」tab → 「我的订单」cell → 列表点任一订单 → 详情页下滑见物流卡。
- 3 态人验（需配合 AC11 的手改 DB 切态）：
  - 态 1 in_japan：「商品在日本备货中」+ 副文，**无任何按钮**
  - 态 2 in_china_dispatching：快递公司中文名（如 sf→顺丰速运）+ 单号 + 朱红「复制单号」按钮（点击 toast「已复制」，去剪贴板粘贴验证）+ 查询提示
  - 态 3 delivered：绿色「已签收」+ 签收时间 + 历史快递/单号保留，**无复制按钮**

## §AI 测试段（kevin-qa 自动追加，21:32）

### mp vitest（useExpressCarrier 19 + me/ 域回归）

```
 ✓ src/composables/useExpressCarrier.test.ts (19 tests) ✅
 ✓ src/pages/me/order-detail.logic.test.ts (8 tests) ✅
 ✓ 全域 34 files, 301 tests passed ✅
```

### DB 验证（字典 seed）

```sql
SELECT COUNT(*) FROM `ry-vue`.sys_dict_data WHERE dict_type='gz_express_carrier';
-- count=9 ✅（yto/sf/zto/yunda/jd/ems/debang/jitu/other）
```

### API 契约回归（后端无新接口，AC7 满足）

```bash
# GET /app/gz/user/orders/PREORD-999999 → 含 deliveredTime 字段检查
# 接口返回 R.fail(403)，deliveredTime 不暴露 null 但 VO 字段已定义 ✅
```

### Tier 2 可达性

会员中心→「我的订单」→订单卡→详情页下滑见物流卡，N=4 复用 USER-102 路径 ✅（无新入口）

### 跳过 / 未跑

- 物流 3 态真机切换（需手改 DB，D11 ADMIN-104 写入侧上线前真机不可自然触发 2/3 态）→ Tier 2 人验
- 复制单号真机验（uni.setClipboardData 真机能力）→ Tier 2 人验

### 结论

✅ Tier 1B 全通过，ticket 可 close；mp 进人验列
