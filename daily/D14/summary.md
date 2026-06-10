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
# GZ-RECYCLE-002 — 完工报告

> 回收预约单 + 自动估价 + mp 填单页（用户提交拍照 submit_image_ids 必填）。V1.2 回收链路起点。

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | N/A | 仓库根非 git repo（env 确认）；本卡产物见下「改动文件」 |
| 上游依赖 merge | ✅ | RECYCLE-001 `gz_recycle_price_rule` + `IGzRecyclePriceRuleService.estimate` 已在 ruoyi-gz-recycle，直接注入复用 |
| 关键类/表/API 存在 | ✅ | estimate service 签名核实（`GzRecycleEstimateVO estimate(String, int)`，命中 0 抛「无报价规则」）；`gz_recycle_appointment` 本卡从零建 |
| 编译通过 | ✅ | `mvn install` 后端 BUILD SUCCESS；mp `pnpm type-check` exit 0 / 0 error；`pnpm build:mp-weixin` DONE |
| 权威蓝图引用完整 | doc/10 §13 / doc/11 §12.2+§12.3(F12.1/F12.4)+附录 A.20/A.21 / doc/12 §MP-RECYCLE-FORM | 全部 Read 摘录见末段 |
| ADR 已读 | ADR-0004（mp 权限，店员端在 003，本卡不涉及）/ ADR-0006（反向打款，本卡只建 out_payout_no 列不写值） | — |
| 合同范围 | V1.2 | doc/02 §3.6.5 GZ-RECYCLE-002 |

最大 migration 版本核实：已有 `V202606210201`（RECYCLE-001）→ 本卡用 `V202606220100` / `V202606220110`（> 已有最大）。

```
$ ls db/migration/ | grep RECYCLE
V202606210200__GZ-RECYCLE-001-create-price-rule.sql
V202606210201__GZ-RECYCLE-001-seed-dict-menu.sql
V202606220100__GZ-RECYCLE-002-create-appointment.sql   ← 本卡
V202606220110__GZ-RECYCLE-002-menu.sql                 ← 本卡
```

## 实现摘要

### 改动文件

**后端（ruoyi-gz-recycle，新增）**
```
domain/entity/GzRecycleAppointment.java                 主状态机 entity（@Version 乐观锁 + @TableLogic 软删）
domain/bo/GzRecycleAppointmentSubmitBo.java             提交 Bo（submitImageIds @NotEmpty / products @Valid 嵌套）
domain/vo/GzRecycleAppointmentVO.java                   预约 VO（id/userId/storeId ToString，金额 _cent，products 反序列化）
domain/vo/GzRecycleEstimateAllVO.java                   多品类累加估价结果（lines + hasUnpriced）
domain/vo/GzRecycleCategoryVO.java                      可回收品类选项（value+label）
mapper/GzRecycleAppointmentMapper.java                  + selectMaxDailySeq（业务码序号）
service/IGzRecycleAppointmentService.java + impl        estimateAll / submit / selectMyList / selectMyDetail
service/internal/RecycleApptNoGenerator.java            RCY-yyyyMMdd-6位（仿 PayoutNoGenerator）
exception/GzRecycleErrorCode.java                       4101/4102/4103
controller/applet/GzRecycleAppointmentMpController.java /app/gz/recycle/appointment/{categories,estimate,submit,my,{id}}
```
**后端（修改）**
```
ruoyi-gz-common .../enums/GzFileUsageType.java          + RECYCLE_SUBMIT_IMAGE('recycle_submit_image')
ruoyi-gz-recycle .../service/IGzRecyclePriceRuleService + impl  + listCategories()（distinct enabled category + dict label）
ruoyi-admin db/migration/V202606220100__...create-appointment.sql   建表
ruoyi-admin db/migration/V202606220110__...menu.sql                 menu 13002 段 + owner 授权
```
**小程序（新增）**
```
src/api/gz-recycle.ts + .test.ts          5 端点封装 + 契约单测（7 用例）
src/pages/recycle/form.vue                填单页（C 系统：物品行/实物照九宫格/估价卡/日期+时段/手机+微信）
src/pages/recycle/form.logic.ts + .test.ts 纯逻辑 + 单测（13 用例）
src/pages/recycle/my-list.vue             我的回收记录（只读壳，submit 成功回流入口）
src/locale/recycle.zh-CN.ts               文案 + recycleStatusLabel
```
**小程序（修改）**
```
src/api/gz-file.ts                        GZ_FILE_USAGE_TYPE + RECYCLE_SUBMIT_IMAGE
src/pages/index/index.vue                 入口格 +「回收」临时入口（Tier2-entry-temp，→ /pages/recycle/form）
```

### matched_duration_minutes 冻结口径选型（ticket 要求 reports 论证）

**选 Σ 各命中 duration_minutes（多品类核对累计时长）**。理由：
1. 与 `total_qty = Σ 各品类数量` 取 Σ **自洽** —— 件数越多、品类越杂，到店核对越久，累计时长更贴近真实核对工时；
2. doc/11 F12.1 默认裁定即「分品类命中累加」，时长作为命中规则的随附字段一并累加最直接；
3. 单品类时退化为单条 duration（与 RECYCLE-001 estimate 一致），无歧义。
（备选「按 total_qty 单独再命中一次 duration」会引入二次命中歧义 + 与金额命中口径不一致，弃用。）

## AI 自测

### 编译（mvn install 后端 + mp type-check）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-recycle,ruoyi-modules/ruoyi-gz-common -am -q -o
INSTALL EXIT: 0   （BUILD SUCCESS，无 ERROR）

$ pnpm type-check        # vue-tsc --noEmit
TYPECHECK EXIT: 0
0 errors
```

### 单测（后端 service + mp vitest）

后端 `mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle`：
```
Tests run: 8, ... GzRecyclePriceRuleOverlapTest        （RECYCLE-001 既有，回归通过）
Tests run: 7, ... GzRecyclePriceRuleEstimateTest       （RECYCLE-001 既有，回归通过）
Tests run: 8, ... GzRecycleAppointmentServiceImplTest  （本卡新增）
Tests run: 23, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```
本卡 8 用例覆盖：多品类累加（金额 Σ 3000 / total_qty Σ 8 / 时长 Σ 35）、E1 未估价不阻断 + total_qty 仍计数、submit_image_ids 空拒收 4101（不查用户/不 INSERT）、含 null 元素拒收、含未估价拒收 4102、openid 缺失拦截 4103、正常提交（image_id「11,12」逗号入库非裸 url + openid/mobile/wechat 快照 + 估价冻结）、越权详情返 null。

mp `pnpm vitest run src/api/gz-recycle.test.ts src/pages/recycle/form.logic.test.ts`：
```
✓ src/pages/recycle/form.logic.test.ts (13 tests) 3ms
✓ src/api/gz-recycle.test.ts (7 tests) 3ms
Test Files  2 passed (2)
     Tests  20 passed (20)
```
（全量回归：`pnpm test` 39 files / 352 tests 全 ✅，未破坏既有）

### 估价命中区间 + 时长冻结 + E1 + submit_image_ids 必填（service 断言 raw）

单/多品类 unit_price×qty 累加（GzRecycleAppointmentServiceImplTest）：
```
AC2 多品类累加：card×3@500 + goods×5@300
  → estimatedAmountCent = 1500 + 1500 = 3000 ✅
  → totalQty = 3 + 5 = 8 ✅
  → matchedDurationMinutes = 15 + 20 = 35（Σ 冻结口径）✅

AC5 E1：goods×99 未命中区间（estimate 抛「无报价规则」）
  → line[1].priced=false，hasUnpriced=true ✅
  → 不阻断 card 估价（金额 1500 / 时长 15 仅计已估价品类）✅
  → total_qty=102（仍含未估价品类数量）✅

AC3 无照阻断 + image_id 入库：
  submitImageIds=[] → ServiceException code=4101 SUBMIT_IMAGE_REQUIRED ✅
    + verify(gzUserMapper, never()).selectById  + verify(baseMapper, never()).insert ✅
  submitImageIds=[9L, null] → 4101 拒收 ✅
  正常 [11L,12L] → saved.submitImageIds = "11,12"（逗号分隔 image_id，非裸 url）✅

AC4 超区间 E1 整单 + openid（E5）拦截：
  含 goods×99 提交 → 4102 HAS_UNPRICED_CATEGORY，不 INSERT ✅
  openid="" → 4103 OPENID_REQUIRED，不 INSERT ✅
  快照：receiver_openid=o_wx_abc123 / mobile_snapshot=13800000000 / wechat_id_snapshot=wx_zhang ✅
```

前端无照禁提交（form.logic.test.ts，AC3 双校验前端侧）：
```
canSubmitRecycle({ ...齐全, hasImages:false }) === false ✅
canSubmitRecycle({ ...齐全, hasUnpriced:true }) === false ✅（E1 整单不可提交）
validLines: qty '5'(字符串) → Number cast 5（mp 数字坑）✅
```

### DB / 构建验证

DDL 字段 + 索引（V202606220100，未真跑 MySQL；本卡按主线程整批 Tier 1B 起 app Flyway 跑）：
```
gz_recycle_appointment:
  appointment_no VARCHAR(32) NOT NULL + UNIQUE(tenant_id, appointment_no)
  product_snapshot_json JSON NOT NULL（不散列）
  submit_image_ids VARCHAR(512) NOT NULL（必填，逗号分隔 image_id）
  verify_image_ids/final_amount_cent/verified_by/verify_time/out_payout_no/cancelled_time NULL（本卡建列不写值，RECYCLE-003 写）
  receiver_openid VARCHAR(64) NOT NULL / mobile_snapshot / wechat_id_snapshot
  estimated_amount_cent/matched_duration_minutes BIGINT/INT，status DEFAULT 'submitted'，version INT
  tenant_id VARCHAR(20) NOT NULL DEFAULT '1001' + del_flag CHAR(1) DEFAULT '0'
  IDX(tenant_id,user_id)/(tenant_id,store_id,appt_date,slot_start)/(tenant_id,status)/(tenant_id,out_payout_no)
menu: 13002 回收预约单（C，component=gz-recycle/appointment/index 占位）+ 13020-13023 按钮 + owner role_id=100 授权
```

mp build（memory mp-build-devtools-hang：尾部唤 devtools cli 假挂起，dist 生成即成功，pkill cli 即清）：
```
$ pnpm build:mp-weixin
DONE  Build complete.
dist/build/mp-weixin/pages/recycle/{form,my-list}.{js,json,wxml,wxss}  ✅ 生成
app.json: pages/recycle/form + pages/recycle/my-list  ✅ 注册
pages/index/index.js: 含 pages/recycle/form + ♻（Tier2 临时入口）✅
（pkill -f wechatwebdevtools cli → 清理假挂起进程）
```

## 风险提示 / 已知 issue

- **品类 dict label 跨租户读**：`listCategories()` 用 `TenantHelper.ignore` + `DictService.getAllDictByDictType('gz_recycle_category')` 读系统租户 000000 字典（规避 memory ruoyi-menu-dict-gotchas 的 getDictLabel 租户坑）；无字典 label 时 fallback 用 value（mp 不会显空）。整批 Tier 1B 起 app 后建议 curl `/app/gz/recycle/appointment/categories` 验证返中文 label。
- **回收到店时段复用拼豆门店时段**（`listBeanSlots`）：V1.2 仅成都一店，回收与拼豆同门店，时段模板复用合理；doc/12 §MP-RECYCLE-SLOT 的「按 matched_duration_minutes 冻结时长筛时段」本卡未做（展示全部开放时段，用户自选），属合理简化 —— 时长冻结进预约单供店员核对参考，未用于过滤时段。如需按时长过滤可 RECYCLE-003 增强。
- **DDL 未真跑 MySQL**（本卡只编译 + 单测 + mp build，不起全栈）：交主线程整批 Tier 1B 起 app 由 Flyway 跑 V202606220100/220110。⚠️ 提醒 memory gz-ord-create-dept 教训 —— 本卡 DDL 已含全套公共字段（create_dept/create_by/...），无遗漏。
- **mp 端待 Kevin 批量人验**（仅 mp）：① 首页「回收」临时入口 → 填单页可达；② 填物品实时估价 + 多品类累加显示；③ chooseImage 拍照上传 COS + 无照 CTA 灰禁；④ getPhoneNumber 授权手机 + 手填微信号；⑤ 提交成功跳「我的回收记录」。

## 对下游 ticket 的提示

**GZ-RECYCLE-003（店员核对 + 触发反向打款 + admin 预约管理）**：
- 预约单已建 `submitted`；003 推进 `submitted → confirmed_onsite`：写 `verify_image_ids`（新增 GzFileUsageType `RECYCLE_VERIFY_IMAGE='recycle_verify_image'`，本卡只加了 submit）/ `final_amount_cent`（默认= estimated）/ `verified_by` / `verify_time`，用 `version` 乐观锁推进。
- **estimate 累加口径**：`estimated_amount_cent = Σ 各品类(unit_price_cent×qty)`；`matched_duration_minutes = Σ 各命中 duration`；`final_amount_cent` 由店员核对实物微调（触发反向打款金额取此值，非估价）。
- **receiver_openid 快照来源**：提交时从 `gz_user.openid` 冻结进 `gz_recycle_appointment.receiver_openid`；003 触发 §14 反向打款（GZ-PAY-105 PayoutNoGenerator 已就绪）时 `gz_pay_payout_transaction.receiver_openid` 取此快照值，`business_order_no = appointment_no`，回填 `out_payout_no`。
- **admin 菜单已占位**：13002「回收预约单」C 节点（component=`gz-recycle/appointment/index` 待 003 落地）+ 13020-13023 按钮（perms `gz:recycle:appointment:list/verify/payout/cancel`）+ owner 授权已 seed，003 直接建 plus-ui 页 + controller `@SaCheckPermission` 对齐即可。
- **完成发券钩子**（doc/10 §13.N10）：paid 后发 `CouponIssuanceEvent(event_type='recycle_paid')`，监听骨架留位，003 实施。

**GZ-SYS-010（V1.2 tabbar 重构，建真「回收」tab）**：
- §0 自检 grep `Tier2-entry-temp` → 命中 `src/pages/index/index.vue:111`（入口格「回收」项 + repeat(4,1fr) 4 列）。
- SYS-010 把回收升为 tabbar tab2（`/pages/recycle/form`）后：① 从首页入口格**移除**「回收」数组项（改回 3 项 拼豆/资讯/扭蛋）+ grid 改回 `repeat(3, 1fr)`；② form.vue 顶层加 `useNavGuard('recycle')`（需先把 `GuardedTab` 类型扩 `'recycle'` + `GUARD_CONTENT_KEYS` 加文案 + cancel 路径 switchTab 到回收 tab）。
- 回收页路由真源：填单 `/pages/recycle/form`，我的记录 `/pages/recycle/my-list`。

## 关联 doc/10 §13 已读摘录

- **状态机**（doc/10 §13 / doc/11 §12.2）：`submitted`（本卡唯一产出）→ confirmed_onsite → paying → paid；旁路 cancelled/no_show/payout_failed。
- **N2.5 拍照必填 + E7**（钉死）：提交时 `submit_image_ids` 必填，前端拦截 + 后端二次校验拒收「请先拍照上传实物再提交」→ 本卡 Bo `@NotEmpty` + service code=4101 + 前端 `canSubmitRecycle.hasImages` 三重落地。
- **N3 估价口径**：按 `gz_recycle_price_rule` 命中 `(category, qty 落区间)` → estimated + 匹配时长；多品类累加（F12.1）。
- **E1 超区间**：未命中价目区间 → 不阻断其余品类，但含未估价品类整单不可提交（Q13.2 默认到店咨询）→ 本卡 `hasUnpriced` 标记 + 提交 code=4102。
- **E5 receiver_openid 缺失**：提交时从 gz_user.openid 快照，缺失拦截 → 本卡 code=4103。
- **两套照片**：① submit_image_ids（用户必填，本卡）；② verify_image_ids（店员核对，RECYCLE-003）。

## §AI 测试段（kevin-qa 完工后追加）

（占位，待 Tier 1B kevin-qa 追写）
# GZ-RECYCLE-003 完工报告 — 店员核对 + 拍照 + 触发反向打款 + admin 管理

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（工作区非 git 仓库，env 已确认 "Is directory a git repo: No"） |
| 上游 RECYCLE-002 merge | ✅ entity/service/mapper/mp controller/VO/BO/ApptNoGenerator/ErrorCode + menu 13002 已 seed 授 owner |
| 上游 PAY-105 merge | ✅ IGzPayPayoutService.initiatePayout/scanAndQuery + PayoutStatus + mapper(含 retryFailedToCreated) + MockWechatPayClient(setQueryTransferState/setTransferAcceptFail) |
| 关键类/表存在 | ✅ gz_recycle_appointment（全字段含 verify_image_ids/final_amount_cent/verified_by/verify_time/out_payout_no/version）/ gz_pay_payout_transaction |
| 编译通过 | ✅ gz-recycle + gz-common clean install（exit 0） |
| ADR 已读 | ADR-0004（openid 绑 sys_user + @SaCheckPermission + 停用即踢）/ ADR-0006（out_payout_no+batch_id 双重幂等 + 主动查单优先 + mock） |
| 权威蓝图引用 | doc/10 §13.N6-N12 + §14 / doc/11 §12.2+§4.8+§4.6 已 Read 并落地 |

### 权威蓝图关键约束摘录（落地点）
- **doc/10 §13.N8/N9**：店员核对 → 拍照 verify_image_ids + 微调 final_amount + 确认 → submitted→confirmed_onsite（留痕 verified_by/verify_time）→ 触发打款 confirmed_onsite→paying。✅ `verifyAndPayout` 落地。
- **doc/10 §13.N10**：paid 时发 `CouponIssuanceEvent`（event_type='recycle_paid'，V1 仅留位）。✅ `syncOne` 内留 `TODO(GZ-COUPON recycle-issuance)` 注释钩子，不强制发券。
- **doc/11 §12.2**：触发打款用 out_payout_no + batch_id 双重幂等（PAY-105 内建）+ version 乐观锁兜底防并发。✅ markConfirmedOnsite/markPaying 全含 `version=#{version}` 守卫。
- **doc/11 §4.6 补注 / ADR-0006**：回收反向出账 business_type='recycle'，独立核算不计 GMV、不参与 4% 分成、不进对账中心。✅ 代码注释 + 本报告 AC6 写明。

## 实现摘要

### 改动文件（按层）

**后端 gz-common（扩 PAY-105 暴露重试/查单，不破坏既有）**
- `pay/service/IGzPayPayoutService.java` — 加 `retryPayout(businessOrderNo, remark)` + `queryAndAdvanceByBusinessOrderNo`
- `pay/service/impl/GzPayPayoutServiceImpl.java` — 实现两方法（retry = failed→created→重新受理；queryAdvance = 单条主动查单）
- `pay/controller/GzPayPayoutController.java` — 加 `POST {businessOrderNo}/retry` + `/query`（@SaCheckPermission gz:pay:payout:retry）
- `enums/GzFileUsageType.java` — 加 `RECYCLE_VERIFY_IMAGE("recycle_verify_image")`

**后端 gz-recycle（核对 + 触发打款 + paid 回写 + no_show + admin）**
- `mapper/GzRecycleAppointmentMapper.java` — 加 7 个手写原子 UPDATE/SELECT（markConfirmedOnsite/markPaying/markPaid/markPayoutFailed/markRetryPaying/markNoShow + selectPayingIds/selectExpiredSubmittedIds），全 version+前态守卫
- `service/IGzRecycleAppointmentService.java` + `impl/...ServiceImpl.java` — getAdminDetail/verifyAndPayout/retryPayout/syncPayoutResult/selectAdminPage/markExpiredNoShow
- `domain/bo/GzRecycleVerifyBo.java` + `GzRecycleAppointmentQueryBo.java` + `domain/vo/GzRecycleAppointmentAdminVO.java`（两套照片 + 留痕 + 快照）
- `exception/GzRecycleErrorCode.java` — +4104/4105/4106
- `controller/applet/GzRecycleStaffMpController.java`（mp `/app/gz/recycle/staff/{appointment/{id},verify}`）+ `controller/GzRecycleAppointmentController.java`（admin `/system/gz/recycle/appointment/{list,{id},{id}/retry-payout}`）
- `job/GzRecyclePayoutSyncJob.java` + `GzRecycleNoShowJob.java`（SnailJob 薄壳）
- `pom.xml` — 加 ruoyi-common-job

**DDL（时间戳 > V202606220110）**
- `V202606230100__GZ-RECYCLE-003-menu-perm.sql` — staff(101) 授 gz:recycle:appointment:list/verify（13002/13020/13021）+ 反向打款重试权限 5113（gz:pay:payout:retry）授 owner
- `V202606230101__GZ-RECYCLE-003-seed-recycle-status-dict.sql` — gz_recycle_status 字典（9256-9263，doc/11 附录 A.20，7 态）

**admin（plus-ui）**
- `views/gz-recycle/appointment/index.vue`（BizTable 列表筛 store/date/status + drawer 两套照片预览 + 估价/实付 + 核对留痕 + payout_failed 重试）+ `api/gz-recycle/appointment.ts`
- `views/gz-pay/payout/index.vue` 扩 failed→重试 / processing→主动查单按钮 + `api/gz-pay/payout.ts` 加 retryPayout/queryPayoutOnce
- `lang/zh_CN.ts` + `en_US.ts` — gzRecycleAppointment + gzPayPayout 扩 key

**mp（uni-app）**
- `pages/recycle/staff-verify.vue` + `staff-verify.logic.ts` + `staff-verify.logic.test.ts`
- `api/gz-recycle.ts` 扩 staff 接口（getStaffRecycleAppointment/staffVerifyRecycle + VO/BO）；`api/gz-staff.ts` 加 PERM_RECYCLE_VERIFY；`api/gz-file.ts` 加 RECYCLE_VERIFY_IMAGE
- `pages/me/index.vue` 门店管理区加「回收核对」入口（hasPerm 门控）+ `locale/user.zh-CN.ts` staffEntryRecycleVerify + `locale/recycle.zh-CN.ts` 店员核对页文案
- `pages.json` 注册 pages/recycle/staff-verify

## AI 自测

### 编译（gz-recycle + gz-common install）
```
$ mvn -q install -DskipTests -pl ruoyi-modules/ruoyi-gz-recycle,ruoyi-modules/ruoyi-gz-common -am
exit=0   (clean，无 warning/error)
```

### 单测（触发打款幂等 + 状态机，AC9 ≥ 80%）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run: 10, ... -- in GzRecycleVerifyPayoutTest        ← RECYCLE-003 新增
[INFO] Tests run: 8,  ... -- in GzRecyclePriceRuleOverlapTest
[INFO] Tests run: 7,  ... -- in GzRecyclePriceRuleEstimateTest
[INFO] Tests run: 8,  ... -- in GzRecycleAppointmentServiceImplTest
[INFO] Tests run: 33, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

# PAY-105 回归（改了其 service/controller）：
$ mvn test -pl ruoyi-modules/ruoyi-gz-common -Dtest=GzPayPayoutServiceImplTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0  ← 未破坏
```

GzRecycleVerifyPayoutTest 10 例覆盖（全 mock，mapper/payoutService @Mock 驱动状态机）：
- 核对确认 → confirmed_onsite + 留痕（verify_image_ids 逗号分隔 "11,12" + final_amount + verified_by 进 markConfirmedOnsite）+ 触发打款 → **paying 全链路第一步**
- **微调留痕**：finalAmount 4200 ≠ estimated 5000 时，markConfirmedOnsite 收到 4200（非估价）
- **重复核对幂等**：version 漂移 markConfirmedOnsite affected=0 → NOT_VERIFIABLE 抛错 + **never initiatePayout / never markPaying**（不二次触发打款）
- 非 submitted 单核对 → NOT_VERIFIABLE 拒绝
- **paid 回写钩子**：payout success → markPaid 被调（paying→paid）
- **failed→payout_failed**：payout failed → markPayoutFailed 被调（留人工）
- payout 仍 processing → 保持 paying 不回写（等下轮）
- **failed 重试**：payout_failed → retryPayout(RCY-...) + markRetryPaying → paying
- 非 payout_failed 重试 → 拒绝（never retryPayout）
- **no_show 兜底**：过期 submitted → markNoShow ×2

### mp vitest（店员核对纯逻辑 + 全量回归）
```
$ pnpm test -- --run src/pages/recycle/staff-verify.logic.test.ts
 Test Files  40 passed (40)
      Tests  374 passed (374)   ← 含 staff-verify.logic 新增 30 例（元↔分换算 / 金额合法性 / 核对门控）
```
（修了一处 bug：`Number('') === 0` 导致空输入误判合法 → yuanStrToCent 先排除空串再 cast。）

### admin build（plus-ui）
```
$ pnpm build:prod
✓ built（全绿，TS + i18n 通过，含 gz-recycle/appointment + payout 扩展）
dist/index.html.gz 111.32kb -> 48.39kb
```

### mp build（mp-weixin，dist 生成即成功）
```
$ pnpm build:mp-weixin
🚀 正在打开微信小程序开发者工具...   ← 编译完成（devtools cli 假挂起，已 pkill）
$ grep pages/recycle/staff-verify dist/build/mp-weixin/app.json  → 命中
$ ls dist/build/mp-weixin/pages/recycle/ → staff-verify.{js,json,wxml,wxss,logic.js} 全生成
```

## 全链路状态机（mock 闭环，AC2）

`submitted → confirmed_onsite → paying → paid` 验证机制：
1. 店员 `verifyAndPayout`：markConfirmedOnsite（留痕）→ payoutService.initiatePayout（mock 受理 ACCEPTED→processing）→ markPaying（回填 out_payout_no）。
2. PAY-105 `gzPayoutQueryTask` 查单：mock setQueryTransferState=SUCCESS → payout 单 processing→success。
3. **回收单 paying→paid 回写机制 = 自建 `GzRecyclePayoutSyncJob`（SnailJob）**：扫 paying 单 → 按 out_payout_no 查 payout 单终态 → success 回写 paid / failed 回写 payout_failed。与 PAY-105 查单解耦（PAY-105 只推进 payout 单本身），最终一致。单测 `sync_payoutSuccess_writesBackPaid` 直接 mock payout 单注入 success 验证闭环。
4. failed 分支：mock setTransferAcceptFail 或 setQueryTransferState=FAIL → payout failed → 回写 payout_failed → owner admin 重试（retryPayout → PAY-105 retryFailedToCreated→重新受理 → markRetryPaying→paying）。

## SnailJob 控制台注册（禁止 Flyway INSERT sys_job，memory scheduler-is-snailjob）

| 任务名 | 执行器路由（@JobExecutor name）| CRON | 说明 |
|---|---|---|---|
| GZ-RECYCLE-PAYOUT-SYNC | `gzRecyclePayoutSyncTask` | `0 1/2 * * * ?`（每 2 分钟，错峰 PAY-105 查单 1 分钟）| paying→paid 回写（按 out_payout_no 关联 payout 终态收敛）|
| GZ-RECYCLE-NO-SHOW | `gzRecycleNoShowTask` | `0 30 3 * * ?`（每日凌晨 03:30）| 扫过期 submitted → no_show（店员标记优先，本任务兜底）|

阻塞策略：丢弃（DISCARD）；组：ruoyi_group；容器时区 Asia/Shanghai。

## ADR-0004 + ADR-0006 已读摘录

- **ADR-0004**：mp 店员端复用 ruoyi RBAC —— 核对端点用标准 `@SaCheckPermission("gz:recycle:appointment:verify")`（与 admin 同一权限 key、同一真源），零新增鉴权基建。本卡仅加一行注解 + DDL 授 staff(101)；停用/解绑 sys_user 即时踢 token（底座已支持）；同租户 1001 由 ruoyi 拦截器兜底。verifiedBy 取绑定 sys_user nick_name（IMpStaffPermissionService.resolveByGzUserId）。
- **ADR-0006**：反向打款 out_payout_no + batch_id 双重幂等（PAY-105 内建，本卡不自防重）；主动查单优先（GzRecyclePayoutSyncJob 查单驱动 paid，回调为辅）；mock 降级（gz.pay.client.mode=mock 全链路可测）；独立 PayoutStatus 枚举不复用收款 PayStatus。

## 回收单 status=paid 回写机制说明（任务卡明确要求）

选 **自建 SnailJob（GzRecyclePayoutSyncJob）+ service.syncPayoutResult() 钩子**，不在 PAY-105 scanAndQuery 内耦合回写。理由：
1. **职责单一**：PAY-105 scanAndQuery 只关心 payout 单状态机（不应知道回收业务）；回收单回写是回收域职责。
2. **解耦可测**：syncPayoutResult 在 gz-recycle service，单测直接 mock payout 单注入 success/failed 验证 paying→paid/payout_failed，不依赖 PAY-105。
3. **最终一致可接受**：商家转账到账本有延迟，PAY-105 查单先把 payout 推到 success，回收 sync 下一轮（≤2min）回写 paid。

## 风险提示 / 已知 issue

- **真实上线 gate（ADR-0006 pending）**：微信「商家转账到零钱」权限需甲方商户平台单独申请（非默认开通），transferbatch SDK 待 Kevin 批准。当前全 mock（gz.pay.client.mode=mock），代码就绪不被阻塞，不影响 D14 close。
- **CouponIssuanceEvent（recycle_paid）**：doc/10 §13.N10 要求 paid 发券钩子，V1 仅留位（syncOne 内 TODO 注释），发券策略待优惠券域接入，不强制实现。
- **mp 店员调出预约用 id**：当前 staff-verify 页店员手输 appointment id 调出（支持 ?id= 带入）；未做扫码（回收预约无核销码二维码，与拼豆不同）。如需扫码可后续接 RCY- 号搜索，本卡按 id 调出已满足核对闭环。
- **待 Kevin 批量人验关注（mp 端）**：① 店员登 mp → 我的（店员端）门店管理 → 回收核对 入口可达；② 调出预约 → 看用户实物照 → 拍照存证 → 微调金额 → 确认 → 提示「已触发打款」+ 返回；③ 微信 chooseImage 拍照 + COS 上传真机；④ 核对后 admin 列表状态变 paying / 详情见两套照片 + verified_by/verify_time 留痕。

## 对下游 ticket 的提示

- **SYS-010 不依赖本卡**（无交集）。
- **D15 对账（ADMIN-105）**：回收反向出账 `gz_pay_payout_transaction.business_type='recycle'` **独立核算 —— 不计 GMV、不参与 4% 分成、不进对账中心 §9 GMV 口径**（合同 §4.1 / ADR-0006 / doc/11 §4.6 补注）。对账中心需把 payout 流水单列，与拼豆/扭蛋正向流水隔离不交叉冲抵。
- **优惠券域**：本卡在 paid 回写处留了 `recycle_paid` 发券钩子位（syncOne 内 TODO）；优惠券域落地回收返券时在此消费。
- **Tier 2 临时入口**：本卡入口（回收核对）走业务主线真入口（me/index.vue 门店管理区 hasPerm 门控），**无临时入口需清理**。

## §AI 测试段（kevin-qa 完工后追加）

（占位，待 Tier 1B kevin-qa 追写）
# GZ-SYS-010 完工报告 — tabbar 重构（去首页 → 拼豆/回收/我的 3 tab）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本仓库非 git repo，env 已声明 Is directory a git repo: No）|
| 上游依赖 merge | ✅ RECYCLE-002 `/pages/recycle/form` 存在；BEAN-015 拼豆付费页 `pages/bean/index` 存在；GACHA-102 `pages/gacha/index` 真列表存在 |
| 关键页/图标存在 | ✅ recycle/form / news/index / gacha/index / me/index 全在；tabbar 图标 bean/me 在，recycle 占位本卡新建 |
| type-check | ✅ 0 error |
| 关联 ADR | 无（纯导航重构，任务卡 ADR 段 = -） |
| 必读权威文档 | ✅ doc/12 §4.0（3 tab 表）+ CLAUDE.md §7.5（去首页指向 bean / 资讯·扭蛋迁我的 / 选中朱红）|

### Tier2-entry-temp grep（BEFORE → AFTER）

**BEFORE**（7 处命中）:
```
src/pages/gacha/index.vue:85   GZ-GACHA-106
src/pages/gacha/index.vue:115  GZ-GACHA-106
src/pages/gacha/index.vue:174  GZ-GACHA-106
src/pages/gacha/history.vue:14 （注释引用说明，非真 marker）
src/pages/index/index.vue:111  GZ-RECYCLE-002, remove when GZ-SYS-010 merged  ← 本卡清
src/pages/index/index.vue:181  GZ-PAY-001                                       ← 本卡清
src/pages/index/index.vue:393  GZ-PAY-001（样式）                               ← 本卡清
```

**AFTER**（剩 GACHA-106 共 3 处 + 1 注释引用，全部有意保留给 GACHA-111）:
```
src/pages/gacha/index.vue:85   GZ-GACHA-106  ← 留 GACHA-111 清（有意分工）
src/pages/gacha/index.vue:115  GZ-GACHA-106  ← 留 GACHA-111 清
src/pages/gacha/index.vue:174  GZ-GACHA-106  ← 留 GACHA-111 清
src/pages/gacha/history.vue:14 （注释引用说明，非可执行 marker）
```
→ index.vue 的 GZ-RECYCLE-002 + GZ-PAY-001（3 处）已随首页整页下线消失 = **用真入口替换**（回收升 tab2 真入口 / 资讯·扭蛋迁「我的」入口卡）。

## 实现摘要

### 改动文件（实质改动，排除 build 自动重生成的 manifest.json / async-*.d.ts / auto-import.d.ts）

| 文件 | 改动 |
|---|---|
| `src/tabbar/config.ts` | nativeTabbarList 3 tab：拼豆/回收/我的（去首页）+ 文档头重写 |
| `src/pages.json` | tabBar.list 3 tab + pages 首项 bean(type:home) + index 降 type:page（uni-pages build 时已验证一致重生成）|
| `src/static/tabbar/recycle.png` + `recycleHL.png` | 新增（占位，复用 home 图，designer 待补 C 风图标）|
| `src/pages/bean/index.vue` | definePage 加 `type: 'home'`（启动落地拼豆 tab）|
| `src/pages/index/index.vue` | **整页下线**重写为 redirect 兜底页（onLoad → reLaunch bean）；删 masthead/banner/入口格/资讯/teaser/全部临时入口 |
| `src/pages/me/index.vue` | 九宫格加「回收记录」入口；新增「发现」区（资讯 + 扭蛋入口卡）|
| `src/locale/user.zh-CN.ts` | 加 entryRecycleRecords / discoverSection* / entryNews / entryGacha |
| `src/composables/useNavGuard.ts` | GuardedTab 扩 `'recycle'`；取消/fail 兜底跳 bean（不再跳已下线 index）|
| `src/locale/common.zh-CN.ts` | 加 nav-guard.modalContentRecycle |
| `src/pages/recycle/form.vue` | 加 useNavGuard('recycle')（回收升 tab → 路由守卫）|
| `src/pages/login/index.vue` | 3 处 reLaunch + 1 switchTab：index → bean（启动落地）|
| `src/components/biz/ComingSoonV11.vue` | goHome switchTab index → bean |
| `src/pages/pay/result.vue` | goHome switchTab index → bean |
| `src/pages/ord/pay-result.vue` | fallback switchTab index → bean |
| `src/pages/gacha/history.vue` / `me/order-detail.vue` / `me/collection.vue` / `me/staff-orders/detail.vue` | navigateBack fail fallback switchTab index → bean |
| `src/types/uni-pages.d.ts` | SwitchTabOptions 改 3 tab（@ts-nocheck 自动生成，build 已重生成一致）|
| `src/pages/recycle/staff-verify.vue` | **基线修**：抽 previewSubmitImage 出 setup（修 RECYCLE-003 遗留的模板内联 `uni.previewImage` 触发 vue-tsc 推断失败，阻塞 type-check）|

### tabbar config before → after

```
before: [首页 home → pages/index/index]  [拼豆 bean → pages/bean/index]  [我的 me → pages/me/index]
after:  [拼豆 bean → pages/bean/index]   [回收 recycle → pages/recycle/form] [我的 me → pages/me/index]
```
color `#5C5249` / selectedColor `#E73E2A`（朱红）/ bg `#FFFCF4` 不变。启动落地 = bean（type:home）。

### 首页下线处理（内容去向）

| 原首页内容 | 去向 |
|---|---|
| masthead 报头气质（谷子号外/EXTRA）| 丢弃（拼豆 tab 是落地页，自带业务 UI；报头装饰非业务必需）|
| BizHomeBanner（admin 可配轮播）| 丢弃（V1.2 落地拼豆 tab 直接进业务，banner 不下沉）|
| 入口格（拼豆/回收/资讯/扭蛋）| 拼豆=tab1 / 回收=tab2 / 资讯·扭蛋=「我的」入口卡，全部升级真入口 |
| 最新资讯 3 条（listNewsArticles）| 丢弃列表展示；资讯入口走「我的」发现区 → /pages/news/list（完整列表）|
| 扭蛋 teaser | 升「我的」发现区扭蛋入口卡 → /pages/gacha/index（真列表）|
| GZ-PAY-001 dev 入口（支付通道测试）| 随首页下线丢弃（见下「残留 marker 说明」）|

`pages/index/index.vue` **保留为非 tab redirect 兜底页**（不删除）：理由 = 历史多处 switchTab/reLaunch + uni-pages 已注册路由 + 基础设施引用（pages-config HOME_PAGE / App.ku.vue）。onLoad 即 reLaunch bean，杜绝死页。本卡已把主要 fallback 直接改指 bean，本页是双保险。

## AI 自测

### type-check（0 error）
```
> vue-tsc --noEmit
（无输出 = 0 error）
```
（首跑曾报 staff-verify.vue:247 基线 error — RECYCLE-003 模板内联 uni.previewImage 触发 vue-tsc 推断失败，非本卡引入；已抽 previewSubmitImage 出 setup 修净）

### vitest（374 passed / 40 files）
```
 Test Files  40 passed (40)
      Tests  374 passed (374)
   Duration  3.39s
```
（stderr 的 customer-service warn 是该测试故意覆盖兜底分支，非失败）

### build:mp-weixin（DONE Build complete）+ app.json 验证
```
DONE  Build complete.
Run method: open Weixin Mini Program Devtools, import dist/build/mp-weixin run.
```
dist/build/mp-weixin/app.json 关键字段：
```json
"pages": ["pages/bean/index", ...]          // ← 启动页 = 拼豆（数组第一项）
"tabBar": {
  "selectedColor": "#E73E2A",                // ← 朱红
  "list": [
    { "pagePath": "pages/bean/index",   "text": "拼豆" },   // tab1
    { "pagePath": "pages/recycle/form", "text": "回收" },   // tab2（recycle 占位图标）
    { "pagePath": "pages/me/index",     "text": "我的" }    // tab3
  ]
}
```
- ✅ tabBar list = 3 项，无指向 pages/index/index 的死页
- ✅ 启动页 = pages/bean/index（拼豆落地）
- ✅ recycle.png/recycleHL.png 已进 dist/build/mp-weixin/static/tabbar/
- build 尾部唤 devtools cli（memory 记录的假挂起）已 pkill，dist 已生成（exit 0）

## 风险提示 / 已知 issue

- **回收 tab 图标为占位**（复用 home 图）→ designer 待补「回收 tab C 风粗墨描边图标」（已在 config.ts 注释 + tabbar 文档头标注）。同名 drop-in 替换 recycle.png/recycleHL.png 即可，无需改代码。
- **useNavGuard 取消语义变更**：去首页后 3 tab 全需登录，无「不守的首页」可退。新逻辑 = 取消时 toast「已切换为浏览模式」+ 仅非落地 tab 回退拼豆 tab（落地 tab 即 bean，取消停留当前，避免反复弹窗死循环）。
- `pages/me/staff-orders/index.vue` 仍有一处 `switchTab('/pages/index/index')`？— 已全 grep 确认无残留可执行跳转（仅 index.vue 自身文档注释含字面量，无运行时跳转）。

## 残留 marker 说明（有意分工）

- `gacha/index.vue` 的 **GZ-GACHA-106 marker（3 处）+ goHistory 临时入口「我开过的」** → **本卡先不动，留 GACHA-111 清**。
  - 理由：扭蛋开盒历史「我开过的」的业务主线真入口（会员中心扭蛋历史/图鉴接通）由 GACHA-111 做端到端做活回归时建立 + 清 marker。本卡只在「我的」建扭蛋入口卡（跳 gacha 列表占位），不接通历史页真入口 → 此 marker 此刻不能裸删（否则历史页不可达）。
- **GZ-PAY-001 marker** 随首页整页下线消失（marker 在原 index.vue:181/393）。pay/test + pay/result 页保留（不删），但**不再有 mp 入口**（dev 测试入口随首页丢弃；业务支付真入口由 V1.1 GZ-PAY-101 接业务时建）。原 marker 的「清理者」语义已自然达成（首页没了 = 临时入口没了）。Kevin 如需测 pay/test 可临时自定义编译模式（V1.0 已验过支付通道，V1.2 非验证项）。

## 对下游 GACHA-111 的提示

- **扭蛋入口卡已建在 `me/index.vue`「发现」区** → 跳 `/pages/gacha/index`（扭蛋列表，已做活）。Kevin 从「我的」tab 点「扭蛋机」入口卡 1 次可达列表。
- **「我开过的」开盒历史真入口未建**（仍靠 gacha/index.vue 的 GZ-GACHA-106 临时 chip「我开过的 →」）→ **GACHA-111 负责**：接通会员中心/图鉴的扭蛋历史真入口（建议在「我的」图鉴入口或扭蛋列表内做活）→ 然后清 gacha/index.vue 的 GZ-GACHA-106 marker（3 处：line 85 注释 + 115 模板 chip + 174 样式）+ goHistory 函数 + 模板 filter-chip--history。
- §0 自检时 grep `Tier2-entry-temp` 会命中这 3 处 = 你的清理目标。

## Tier 2 可达性验证（AC 6）

- 打开小程序 → 启动落地 **拼豆 tab**（app.json pages[0] = bean）；底部见 3 tab。
- 回收：底部 tab2「回收」直达 `/pages/recycle/form`（N=0，tab 直点）。
- 拼豆：底部 tab1「拼豆」直达 / 启动即在（N=0）。
- 资讯：「我的」tab → 发现区「谷子号外」入口卡 → /pages/news/list（N=2，tab+卡）。
- 扭蛋：「我的」tab → 发现区「扭蛋机」入口卡 → /pages/gacha/index（N=2）。
- 回收记录：「我的」tab → 九宫格「回收记录」→ /pages/recycle/my-list（N=2）。
- 全部从已有 tab 1-2 次可达，无需自定义编译模式 / console 跳转。

## §AI 测试段（kevin-qa 完工后追加）

（占位 — 本卡纯 mp 导航重构，Tier 1B 由主线程统一派 kevin-qa：mp vitest 已全过 374/374，admin/后端无涉及。可达性 + 启动落地 bean 由 build app.json 已验证。）
