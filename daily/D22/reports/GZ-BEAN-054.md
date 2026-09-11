# GZ-BEAN-054 完工报告 — 拼豆临时桌型（看板可见 / 小程序不可订）

**状态**：✅ Tier 1A 全绿（未 commit）
**ADR 已读 / 产出**：ADR-0023（本 ticket 产出）· ADR-0016（核销现场分座）· ADR-0014（去字典自定义桌型）· ADR-0017（包天）· ADR-0018 §2（排位）

---

## §0 状态自检

| 项 | 结果 |
|---|---|
| 四仓 git 状态 | `RuoYi-Vue-Plus` / `plus-ui` / `miniapp` 均 `staging` 且 clean（动手前）；`doc` 在 `feat/jp-daigou-requirements` |
| 迁移最大号 grep 全部历史 | `GZ-BEAN-053`（`V202608082021`）· 全库最大时间戳 `V202608150951` → 本批取 **054 / V202608261522**（> 全库最大，正常递增） |
| menu 空号 | 无需新增（开关落在既有桌型表单，沿用 `gz:bean:seatTypeConfig:edit`） |
| 编译健康 | `mvn -o compile -pl ruoyi-modules/ruoyi-gz-bean -am` 通过 |
| 关键类硬检查 | `GzBeanSeatTypeConfig` / `GzBeanBookingServiceImpl`（`selectBoard` / `walkInCreate` / 5 处桌型闸）/ `GzBeanSeatServiceImpl.upsertSeatUnit` 全部存在 |

---

## 改了哪些文件

**后端**（`code/main/RuoYi-Vue-Plus/`）
- `ruoyi-admin/src/main/resources/db/migration/V202608261522__GZ-BEAN-054-seat-type-config-mp-visible.sql`（新）
- `ruoyi-modules/ruoyi-gz-bean/.../domain/entity/GzBeanSeatTypeConfig.java`（+`mpVisible`）
- `.../domain/vo/GzBeanSeatTypeConfigVO.java` / `.../bo/GzBeanSeatTypeConfigBo.java` / `.../bo/GzBeanSeatTypeConfigQueryBo.java`
- `.../domain/vo/GzBeanBoardRowVO.java`（+`mpVisible`）· `.../domain/vo/GzBeanSeatVO.java`（+`temp`）
- `.../domain/vo/GzBeanSeatBatchGenerateResultVO.java`（新）
- `.../service/impl/GzBeanBookingServiceImpl.java`（6 处 mp 过滤 + 5 处桌型闸放开 + 余量表过滤 + 看板 VO 回填 + `toBoardRow` 桌型档来源修正）
- `.../service/impl/GzBeanSeatTypeConfigServiceImpl.java`（`toEntity` 补字段 + `buildWrapper` + `validateMpVisible`）
- `.../service/impl/GzBeanSeatServiceImpl.java`（`batchGenerate` 返回结构升级）
- `.../service/impl/GzBeanSlotQuotaCloseServiceImpl.java`（临时桌配额关闭防呆）
- `.../service/IGzBeanSeatService.java` / `.../controller/GzBeanSeatController.java`

**前端**（`code/main/plus-ui/`）
- `src/views/gz-bean/seat-type-config/index.vue`（用途单选 + 渠道列/筛选 + 包天禁用 + 保存后一键生格）
- `src/views/gz-bean/board/index.vue`（临时组 tag + 垫底排序 + 分座候选放开与打标）
- `src/views/gz-bean/seat/index.vue`（typeName tag + 下拉后缀 + 撞号 warning）
- `src/views/gz-bean/slot-availability/index.vue`（alert 文案）
- `src/api/gz-bean/{seatTypeConfig,seat,board}.ts` · `src/lang/{zh_CN,en_US}.ts`

**文档**
- `doc/_adr/0023-pindou-internal-temp-seat-type.md`（新）
- `doc/11-字段权威表.md` §3.4（+`mp_visible` 行 + 过滤边界与分座闸放开说明）

---

## AI 自测 raw output

### 1) 编译 + clean install（必须 clean —— 非 clean 既不重打 jar 也不重编译测试）

```
$ mvn -o clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-bean,ruoyi-modules/ruoyi-gz-recycle -am
[INFO] BUILD SUCCESS
-rw-r--r--  1 wkui  staff  257773 Aug 26 16:30 ~/.m2/.../ruoyi-gz-recycle-5.6.1.jar
```

### 2) 单测（264 通过，含本 ticket 新增 13 条）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-bean
[INFO] Tests run: 118, ... GzBeanBookingServiceImplTest      （原 113，+5）
[INFO] Tests run:  25, ... GzBeanSeatServiceImplTest          （原 23，+2）
[INFO] Tests run:  30, ... GzBeanSeatTypeConfigServiceImplTest（原 25，+5）
[INFO] Tests run:   8, ... GzBeanSlotQuotaCloseServiceImplTest（原 7，+1）
[INFO] Tests run: 264, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

新增用例（AC 对应）：
- `submitPaid_tempSeatType_rejected` — 临时桌线上下单 → 4013（AC6）
- `submitPaid_nullMpVisible_treatedAsVisible` — 迁移前存量行零行为变化（AC2）
- `verify_crossTypeOntoTempSeat_allowed` — 跨桌型分座放行且 **booking 桌型快照不变**（AC12/AC14）
- `selectAssignableSeats_includesTempLast` — 候选含临时桌且垫底 + `temp` 标（AC13）
- `selectTypeSlotAvailability_filtersMpVisible` — wrapper SQL 断言带 `mp_visible`（AC3）
- `insertByBo_nullMpVisible_defaultsToOne` / `_tempSeatType_persistsZero` / `_tempWithDayPassQuota_throws` / `_tempWithDayPassPrice_throws` / `_normalWithDayPass_ok`（AC16/AC17）
- `upsert_tempSeatType_throws` — 配额关闭防呆（AC10）
- `batchGenerate_crossTypePrefixConflict_reported` / `_sameTypeRerun_noConflict`（AC18）

### 3) 迁移实跑（真起 app，Flyway 自动执行）

```
$ mvn -o spring-boot:run -pl ruoyi-admin
Migrating schema `ry-vue` to version "202608261522 - GZ-BEAN-054-seat-type-config-mp-visible" [out of order]
Successfully applied 5 migrations to schema `ry-vue`, now at version v202608261548
Started DromaraApplication in 13.247 seconds
```

### 4) DB 断言 — 存量零行为变化（AC2 核心）

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "..."
=== 054: mp_visible 列 + 存量全 1 ===
total=6 mp_visible=1 的行数=6
```

6 行存量桌型全部 `mp_visible=1` → mp / 看板 / 余量表 / 营业额行为与迁移前完全一致。

---

## 已知 issue / 风险提示

1. **`toBoardRow` 的桌型档来源被本 ticket 修正**：它原本取 **booking 的** `seat_type_config_id`，而 `selectBoard` 取的是**座位的**。改造前两者恒等所以没暴露；跨桌型分座后会分叉 → 单行刷新（放座/延时/改派后）会把座位归进错误分组甚至凭空多出分组。已统一为座位视角。**这是本次放开分座闸激活的潜伏 bug，不是新引入的。**
2. **临时桌上勾「免费」的 walk-in 单照常吃掉当期前 N 名免费名额**（既有行为，非本次引入）。交付说明须写明；甲方不认可再单开 ticket。
3. **切换已有桌型为临时桌不做级联清理**：已有未来线上单不受影响，仍在看板、仍可核销。前端已加静态确认说明。
4. `derivePrefix` 对纯中文名恒回退 `"X"` —— admin「一键生成计时格」的 prompt 默认值给 `T`+序号绕开，未动后端。

## 对下游的提示

- 甲方加临时桌的完整路径：桌型配置 → 新建（名称「临时四人桌」/ 订法按座 / 每桌 4 座 / 数量 1 / 用途「仅后台临时桌」）→ 保存后弹窗一键生成 4 个计时格 → 看板底部出现带「临时桌」标的一组。
- **前缀撞号是唯一真坑**（`seat_no` 全店唯一）：后端已回传 `conflictSeatNos`，前端 warning 列出被跳过的编号并提示换前缀。

## 残留人验

**无**。纯 admin + 后端 ticket，不碰真机微信原生能力、非新业务页首版视觉 → 按 CLAUDE.md §8.2，Tier 1A + 1B 全 ✅ 即终态。

---

## §AI 测试段（kevin-qa 对抗性追加，20:50）

**目标不是确认能跑，是把它跑坏。** 逐条 AC 用真库 + 真 API（非 mock）复测，全部通过；顺带验证了一个 ADR 提到的"潜伏 bug"确实被本 ticket 修好。

### 环境

后端 8080 / admin 8090 均复用主线程已起实例；admin token 走 `/auth/login`（superadmin，tenant 1001）；mp 侧用 `/app/gz/common/auth/wx-login`（mock adapter，`mock-stable-openid` 配置下恒返 userId=13，见 learnings 新记录）。

### 1) 建临时桌 + 一键生格（AC1/AC18）

```
$ curl -X POST /system/gz/bean/seatTypeConfig -d '{"storeId":1,"name":"QA临时四人桌","bookMode":"seat","capacity":4,"quantity":1,"mpVisible":0,...}'
{"code":200,"msg":"操作成功"}  → DB: id=7, mp_visible=0

$ curl -X POST /system/gz/bean/seat/batchGenerate -d '{"seatTypeConfigId":7,"prefix":"QAT"}'
{"code":200,"msg":"成功生成 / 复活 4 个座位单元（已存在的跳过）",
 "data":{"created":4,"skipped":0,"conflictSeatNos":[],"hasConflict":false}}
```
返回结构与 AC18 一致，4 = capacity(4) × quantity(1)。✅

### 2) AC3/4/5/6：mp 三处过滤 + submitPaid 直拒 —— 全部命中

```
$ curl "/app/gz/bean/booking/type-slots?storeId=1&sessDate=2026-12-15"
→ distinct names: {'四人桌','双人','单人'}  distinct configIds: {'1','3','2'}   ← config7 不在内 ✅

$ curl "/app/gz/bean/booking/day-pass-options?storeId=1&sessDate=2026-12-15"
→ 无 config7（AC17 联动：临时桌被 validateMpVisible 挡住不能配 dayPassQuota，天然不会出现在这张表）✅

$ curl "/app/gz/bean/booking/seat-map?storeId=1&sessDate=2026-12-15"
→ total seats=20, temp seats leaked=0 ✅

$ curl -X POST /app/gz/bean/booking/paid-submit -d '{"storeId":1,"seatTypeConfigId":7,...}'
{"code":4013,"msg":"该座位类型已停用，请重选"}   ← 直接命中 AC6 ✅
```

### 3) AC7/AC12/AC13/AC14：看板可见 + 跨桌型分座 3 处闸全放行 + 快照不变（核心正确性）

真造一笔线上「四人桌」(config3) 付费单 → `assignable-seats` 候选核对顺序 → 核销分到临时桌 → 断言快照：

```
候选顺序（AC13）: [Q1-1..Q2-4 (temp:false) ×8, QAT1-1..QAT1-4 (temp:true) ×4]   ← 正常在前、临时垫底、打标正确 ✅

$ curl -X POST "/system/gz/bean/booking/7779141/verify?seatId=58"   (58=临时桌座位)
→ seatId=58, seatNoSnapshot="QAT1-1", seatTypeConfigId="3", seatTypeSnapshot="四人桌", status=used

DB: seat_type_config_id=3, seat_type_snapshot=四人桌   ← 钱仍算在客人买的桌型上，AC14 精确成立 ✅
```

**追加验证 toBoardRow 的"潜伏 bug 修复"是否真生效**（ADR-0023 §3 提到的"本次放开分座闸激活的潜伏 bug"）：

```
release-seat 后单行刷新返回:
{"seatId":"58","seatTypeConfigId":"7","typeName":"QA临时四人桌", ...}   ← 座位视角，不是 booking 的 config3 ✅
```
若这里没修，release/extend/reassign 后单行刷新会把该座归错分组或凭空多出分组——真库验证确认**已修好，不是嘴上说说**。

再验第 3 处闸 `preAssignSeat`（`assignSeatAtVerify` / 改派 helper 已在上面覆盖）：
```
preassign-candidates → 同样 8 正常 + 4 temp(垫底) 顺序
POST /pre-assign?seatId=61 → 200，seatTypeConfigId 仍是原桌型(1/单人)，未被污染成 7 ✅
```

### 4) AC10 判断项：两个方向都对——余量表排除 + 配额关闭防呆

```
$ curl "/system/gz/bean/booking/availability/detail?storeId=1&sessDate=2026-12-15"
→ distinct configIds={'1','2','3'}，config7 不在内 ✅

$ curl -X POST /system/gz/bean/slotQuotaClose -d '{"seatTypeConfigId":7,...}'
{"code":500,"msg":"临时桌不参与小程序配额关闭（它本就不对小程序开放）：seatTypeConfigId=7"}   ← 防呆命中 ✅
```

### 5) AC11：营业额聚合方向相反——必须**含**临时桌现金

```
walk-in 在临时桌开 88.88 元现金单 → /system/gz/bean/revenue/aggregate?...&storeId=1
{"summary":{"totalCent":8888,"cashCent":8888,"cashCount":1,"onlineCent":0},
 "byCategory":[{"key":"st7|0","typeName":"QA临时四人桌","totalCent":8888,"orderCount":1}]}
```
真钱正确入账、按桌型名正确拆分类目。✅

### 6) AC17：包天互斥闸——insert 和 edit 两条路径都拦

```
新建临时桌带 dayPassQuota=1 → {"code":500,"msg":"临时桌不支持包天套餐...请把包天名额与包天价置 0"}
编辑已有临时桌加 dayPassQuota=1 → 同错误，两条路径都拦住 ✅
```

### 7) admin Playwright 视觉核对（0 console error 全程）

- 座位管理 → 桌型配置 tab：临时桌行「用途」列渲 `临时桌` tag，正常行留空；**临时桌行「星期×时段价格」按钮消失**（AC19 隐藏逻辑），编辑/删除仍在 —— 逐一在 UI 上核对属实，非只查 API。

### 结论

GZ-BEAN-054 的 29 条 AC **全部命中**，包括最容易漏测的"两个方向相反"的判断项（AC10 排除 / AC11 包含）和三处服务端强校验闸。未发现真 bug。

**清理**：测试用临时桌配置(id=7)、4 个座位(58-61)、4 笔 booking(7779141-44)、1 条 quota-close 控制行，测毕全部物理删除，门店 1/2 座位类型配置已确认恢复为原始 6 条。
