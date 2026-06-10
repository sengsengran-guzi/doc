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
