# GZ-RECYCLE-001 完工报告 — 回收价目表 + 区间不重叠校验 + 估价命中 + 字典

> 后端（新建 `ruoyi-gz-recycle` 域）+ admin（plus-ui）。复杂度 M。AI 终态（纯 admin/后端，无 mp 人验）。
> **实施方式**：后端 java（12 文件）由 background subagent 建成（编译通过后崩在写 migration 前）；**migration + admin + 注释修正 + 收尾由主线程接管**（见文末异常留痕）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本路径非独立 git 仓库根） |
| 上游依赖 | ✅ GZ-ADMIN-001/SYS-005 字典基础设施就绪；gz-common 稳定 jar 在 .m2 |
| 关键表/段空闲 | ✅ `gz_recycle_price_rule` 不存在（从零建）；`ruoyi-gz-recycle` 模块新建；menu 13000 段空；dict_id/code 9240-9245 空（避开 COUPON 9220-9236 + PAY-105 9250-9255） |
| 迁移时间戳 | ✅ 用 V202606210200 / V202606210201（> 已有 max 202606200200，与 PAY-105 21010x 不冲突） |
| 编译通过 | ✅ `mvn -o test-compile -pl ruoyi-modules/ruoyi-gz-recycle` BUILD SUCCESS（main + test 全部 java 完整） |
| ADR 已读 | 无相关 ADR（价目表 + 区间校验权威 = doc/11 §12.1） |
| 权威蓝图引用 | ✅ doc/11 §12.1（字段 + 区间不重叠校验末段）+ 附录 A.21（品类字典）+ doc/10 §13（估价口径） |

### 权威蓝图关键约束摘录（doc/11 §12.1）
- 字段：`category`(VARCHAR32) / `qty_min`(INT) / `qty_max`(INT NULL=无上界) / `unit_price_cent`(BIGINT) / `duration_minutes`(INT NOT NULL DEFAULT 0) / `enabled`(TINYINT DEFAULT 1) / `sort_no`(INT)。
- 索引：PK id / **UNIQUE(tenant_id, category, qty_min)** / IDX(tenant_id, category, enabled)。
- **区间不重叠 = 业务层校验**（末段钉死）：admin 保存 assert 同 category 各 [qty_min,qty_max] 不重叠；DB 不加复杂 CHECK。
- 估价命中：`qty_min <= total_qty AND (qty_max IS NULL OR total_qty <= qty_max)` 唯一；命中 0 → 无报价；命中多 → 配置有误。

## 实现摘要

### 后端 `ruoyi-modules/ruoyi-gz-recycle`（新建模块，包名 `org.dromara.gz.recycle.*`，仿 gz-coupon）
- 父 pom 注册：`ruoyi-modules/pom.xml` + `ruoyi-admin/pom.xml` 各加 ruoyi-gz-recycle。依赖仅 ruoyi-gz-common + test。
- 12 java：`GzRecyclePriceRule`(entity, TenantEntity + @TableLogic) / `GzRecyclePriceRuleBo` + `GzRecyclePriceRuleQueryBo` / `GzRecyclePriceRuleVO` + `GzRecycleEstimateVO` / `GzRecyclePriceRuleMapper`(BaseMapperPlus, LambdaQueryWrapper service 层组装无 XML) / `IGzRecyclePriceRuleService` + impl / `GzRecyclePriceRuleController`(7 端点 list/getInfo/add/edit/remove/toggle/estimate)。
- **区间不重叠校验**（service `assertNoOverlap`）：查同 category 全部规则（编辑排除自身）逐个判重叠；重叠判定 `aMin <= b2 AND bMin <= a2`（qtyMax null 视 +∞），相邻不重叠。
- **估价命中**（service `estimate`）：内存过滤命中唯一区间；命中 0 抛「无报价规则」/ 命中多抛「配置有误」；`estimated = unit_price_cent × qty`。
- 2 单测：`GzRecyclePriceRuleOverlapTest`(8) + `GzRecyclePriceRuleEstimateTest`(7)。
- **注释修正（主线程）**：entity `delFlag` + controller remove 注释 `2→1`（本项目 logicDeleteValue=1，对齐 BEAN-014/COUPON-002 实证，memory ruoyi-menu-dict-gotchas；@TableLogic 无 value 走全局功能本就正确，仅注释笔误）。

### 迁移（2 文件，主线程写）
- `V202606210200__GZ-RECYCLE-001-create-price-rule.sql`：建 `gz_recycle_price_rule`（字段/索引对齐 doc/11 §12.1；UNIQUE(tenant_id,category,qty_min)；del_flag 注释 `1=删除` 用项目真实值不抄 COUPON-001 历史笔误）。
- `V202606210201__GZ-RECYCLE-001-seed-dict-menu.sql`：字典 `gz_recycle_category`（5 demo 品类，dict_id 9240 / dict_code 9241-9245）+ menu 13000 段（13000 目录 / 13001 价目表 C / 13010-13014 按钮 F，perm 对齐 controller @SaCheckPermission）+ owner(100) 7 授权 + 4 条 demo 价目规则（card 3 区间 + goods 1，区间不重叠）。

### admin（plus-ui，ruoyi/Element Plus 默认，主线程写）
- `api/gz-recycle/priceRule.ts`（id 全 string，7 函数 + 4 interface）。
- `views/gz-recycle/price-rule/index.vue`（BizTable 风格 el-table + 查询 + 新增/编辑弹窗（元↔分换算、qtyMax 留空=无上界）+ 启停 + **估价试算弹窗**（category+qty → 实时命中显示单价/估价/时长））。
- `lang/{zh_CN,en_US}.ts` append `gzRecyclePriceRule` block（全覆盖，默认 zh-CN 不混 emoji）。

## AI 自测（Tier 1A）

### ① 单测（15 全过：区间重叠 8 + 估价 7）
```
[INFO] Running org.dromara.gz.recycle.service.impl.GzRecyclePriceRuleOverlapTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 -- in GzRecyclePriceRuleOverlapTest
[INFO] Running org.dromara.gz.recycle.service.impl.GzRecyclePriceRuleEstimateTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0 -- in GzRecyclePriceRuleEstimateTest
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖：区间重叠拒绝 / 相邻不重叠通过 / qtyMax NULL 无上界重叠 / 编辑排除自身 / 估价命中唯一 / 命中 0 抛无报价 / 命中多抛配置错 / 上界小于下界拒绝。

### ② migration raw SQL 验证（dev DB ry-vue:3307，不污染 flyway_schema_history）
```
-- demo 价目规则（4 条，区间不重叠）
category  qty_min  qty_max  unit_price_cent  duration_minutes  enabled
card      1        10       500              15                1
card      11       50       800              30                1
card      51       NULL     1200             60                1
goods     1        20       300              20                1

-- 估价命中唯一区间
card qty=5  → [1,10]   unit=500   est_cent=2500  (¥25)
card qty=55 → [51,∞]   unit=1200  est_cent=66000 (¥660)

-- 字典 + menu + owner 授权
dict_data=5  menu=7  owner_grant=7
```

### ③ UNIQUE(tenant_id, category, qty_min) 防重 + admin vue-tsc
```
-- UNIQUE 拦截重复
INSERT ('card', qty_min=1, ...) → ERROR 1062 (23000) Duplicate entry '1001-card-1'
  for key 'gz_recycle_price_rule.uk_tenant_category_qtymin'   ✅

-- plus-ui vue-tsc（gz-recycle 文件 0 TS 错；项目基线 72 pre-existing 不在我的文件）
npx vue-tsc --noEmit | grep -icE 'gz-recycle|priceRule|price-rule' = 0   ✅
```

### ④ 收尾
- dev DB 已应用 RECYCLE migration（raw SQL，未写 flyway_schema_history）→ Tier 1B 启动 app 时 Flyway 幂等应用（CREATE IF NOT EXISTS + DELETE/INSERT seed 幂等）。
- Redis 已 FLUSHDB（dict 缓存 TTL 1h，CLAUDE.md §5）。
- **未 mvn install**（留主线程统一按依赖序）；**未启 spring-boot:run / 8080 free**。

## 风险提示 / 已知 issue
- **R-1 demo 品类/价目为占位**：`gz_recycle_category` 5 品类（卡牌/玩偶/谷子/手办/其他）+ 4 demo 价目规则是 demo，甲方在 admin 字典页 + 价目表页维护实际值。
- **R-2 估价命中多兜底**：service `estimate` 命中多条时抛「配置有误」——正常配置（区间不重叠校验生效）不会命中多；此为防御性兜底（万一历史脏数据）。
- **R-3 duration_minutes DB NOT NULL DEFAULT 0**：entity Integer 可空，admin 表单必填（rules）；DB DEFAULT 0 兜底。
- 待 Kevin 批量人验关注：**N/A — 纯 admin/后端 ticket，无 mp 页、无微信原生能力 → AI Tier 1A+1B 全 ✅ 即终态，无人验**（CLAUDE.md §8.2）。

## 对下游 ticket 的提示
- **D14 GZ-RECYCLE-002（mp 填单 + 估价）**：调 `GET /system/gz/recycle/price-rule/estimate?category&qty`（或新建 applet 镜像端点）拿估价；多品类预约按 doc/11 F12.1「各品类自身命中累加」（`estimated = Σ 各品类 unit_price × 数量`）。`gz_recycle_appointment` 表（doc/11 §12.2）本卡未建 = D14 建。
- **D14 GZ-RECYCLE-003（店员核对 + 触发反向打款）**：核对后 `final_amount_cent` 触发 PAY-105 `transferToUserWallet`（business_type=recycle，business_order_no=appointment_no）；PAY-105 链路 + mock 已就绪。
- 估价命中逻辑（`estimate` service）可被 D14 mp 填单直接复用（已抽 service 方法）。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

**Tier 1B（主线程整批集成验证 2026-06-10）** — subagent 崩溃率高 + kevin-qa 不能子 agent spawn + Playwright 不可用 → 主线程一次启动 app 整批验：
- App `Started DromaraApplication in 10.958s` — **gz-recycle 新模块加载无错**（父 pom + ruoyi-admin 依赖注册生效）
- Flyway 应用 `202606210200/0201 GZ-RECYCLE-001`：`gz_recycle_price_rule` 4 demo seed + dict gz_recycle_category(5) + menu 13000 段（owner 授权 7）
- curl `/system/gz/recycle/price-rule/list` + `/estimate?category=card&qty=5` → HTTP 200（Controller 装配 + 映射注册）
- DB 实测：recycle_rule = 4 / flyway_d13 = 5
- ✅ 纯后端/admin AI Tier 1A+1B 全 ✅ 即终态，8080 已释放

---

## §异常留痕（实施过程）

- 本卡 background subagent **两次崩于 `tool call could not be parsed`**（首发 35 tool_uses / 重做 46 tool_uses，均在后端 java 建完、写 migration/admin 前崩）。
- 第二次崩前已建成后端 12 java + pom + 父 pom 注册（主线程编译验证 EXIT=0 + 15 单测过，质量合格）。
- **主线程接管补全**：migration（2）+ admin（api/vue/i18n）+ entity/controller 注释修正 + 全套自测 + 本 report。
- 根因判定：kevin-coder subagent 在本环境工具调用解析不稳定（同批 PAY-105 首发 + COUPON-003 亦崩）；可靠路径 = 主线程实施或前台 subagent（PAY-105 前台重做成功）。
