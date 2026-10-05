# GZ-SNAP-101 完工报告：代切数据底座

> 主线程代为落盘（impl subagent 写 .md 被 hook 拦截，原文回传）。

## §0 状态自检
| 检查项 | 结果 |
|---|---|
| 分支 | RuoYi-Vue-Plus task/D7，开工前 git status 干净 |
| 已读权威 | field-ssot.yaml 中 gz_jp_snap_item / snap_purchase / snap_account / snap_term / gz_jp_fx_rate / gz_jp_order_item / gz_jp_refund 各段；flows.yaml FLOW:F-JP-11；ADR-0025 §5 |
| 迁移最大号（开工前） | V202609262135；flyway 失败数 0 |
| 字典空号 | 活库 MAX(dict_id)=9285，MAX(dict_code)=92821 |
| 配置空号 | 活库 config_id 14040000-14049999 为空；全部迁移 grep `1404000[0-9]` 无结果 |
| sys_config tenant | 按 V202608101050 头注释与 SysConfigMigrationTenantGuardTest，显式写 config_id 与 tenant_id='1001' |
| 字典 tenant | 照 V202608070633（GZ-JP-105）写法用 '000000'（sys_dict_* 在 tenant.excludes） |
| 菜单 | 本卡不建 |
| 既有迁移 | 未修改 |

## 改动文件（RuoYi-Vue-Plus，commit f4240ae1f，全部新增）
- `V202610050723__GZ-SNAP-101-create-snap-tables.sql`：5 张新表（CREATE TABLE IF NOT EXISTS）
- `V202610050724__GZ-SNAP-101-alter-order-item-and-refund.sql`
- `V202610050725__GZ-SNAP-101-seed-dict.sql`
- `V202610050726__GZ-SNAP-101-seed-config.sql`

越界文件：无。

## 实现要点
- 类型按 field-ssot type_map（datetime→DATETIME(3)，text→MEDIUMTEXT，decimal→DECIMAL(12,6)，bool→TINYINT(1)）；公共字段七件套沿用一期。四个 UNIQUE 都含 tenant_id：uk_platform_external、uk_order_item（snap_purchase）、uk_account_code、uk_zh_term。
- 退款表换键：每步先查 information_schema 再 PREPARE 条件执行；加 refund_type（NOT NULL DEFAULT，存量回填）→ 兜底 UPDATE → 先建 uk_item_type → 再删 uk_order_item。任一步失败中间态仍有唯一约束，重跑可达终态。
- gz_jp_item_source 只按 (dict_type, dict_value='snap') 先删后插一条。
- 字典 dict_id 9286-9297、dict_code 92822-92865；config_id 14040001-14040005。

## 临时库预演
临时库 snap101_scratch（LIKE 复制相关表 + 7 条存量退款 + 全部字典），4 个迁移连跑两遍无错：7 条退款单 refund_type=purchase_failed；dict_code 44 条；5 个配置键 JSON_VALID=1 / tenant=1001；同一 order_item_id 再插 shipping_diff 成功。预演后 DROP DATABASE snap101_scratch。

## 应用迁移
```
$ bash .../scratchpad/restart-backend.sh ruoyi-modules/ruoyi-gz-jp
BACKEND UP (commit 676dd3012, branch task/D7)
 - Migrating schema `ry-vue` to version "202610050723 - GZ-SNAP-101-create-snap-tables" [out of order]
 - Migrating schema `ry-vue` to version "202610050724 - GZ-SNAP-101-alter-order-item-and-refund" [out of order]
 - Migrating schema `ry-vue` to version "202610050725 - GZ-SNAP-101-seed-dict" [out of order]
 - Migrating schema `ry-vue` to version "202610050726 - GZ-SNAP-101-seed-config" [out of order]
 - Successfully applied 4 migrations to schema `ry-vue`, now at version v202610050726
```
```
flyway_schema_history（倒序）：
186 202610050726 GZ-SNAP-101-seed-config 1
185 202610050725 GZ-SNAP-101-seed-dict 1
184 202610050724 GZ-SNAP-101-alter-order-item-and-refund 1
183 202610050723 GZ-SNAP-101-create-snap-tables 1
182 202609262135 GZ-BEAN-057-fix-long-close-comment 1
success=0 → 0
```

## accept（项目根原样执行）
```
### accept #0  exit=0
### accept #1  exit=0
### accept #2  exit=0
```
断言值：
```
product_id IS_NULLABLE → YES
uk_item_type → tenant_id,order_item_id,refund_type
refund_type 分布 → purchase_failed 7
14040001 gz.jp.snap.pricing 1001 {"markupRatio":null,"fixedFeeCent":null,"estShippingCent":null,"quoteTtlSec":600}
14040002 gz.jp.snap.filter  1001 {"categoryWhitelist":[],"keywordBlacklist":[]}
14040003 gz.jp.snap.gate    1001 {"blockKeywords":["専用","様専用","さん専用"],"proxyRefuseKeywords":[11 词],"manualKeywords":[6 词]}
14040004 gz.jp.snap.auto    1001 {"enabled":false,"pausedReason":"未上线","pausedAt":null}
14040005 gz.jp.snap.trade   1001 {"rateDeadlineHours":24,"patrolMinutes":20}
字典值数：platform 1 / item_status 4 / shipping_payer 2 / gate 3 / mode 2 / purchase_status 6 / fail_reason 6 / trade_status 7 / account_health 5 / term_type 3 / fx_source 2 / refund_type 2
```

## AC：一期单测
```
mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am → exit 0
ruoyi-gz-jp     : tests=217 failures=0 errors=0 skipped=0
ruoyi-gz-common : tests=260 failures=0 errors=0 skipped=0（含 SysConfigMigrationTenantGuardTest）
```

## 对下游的提示
- GZ-SNAP-102：product_id 可空，所有 JOIN gz_jp_product 的查询要容忍空值；实体加 GzJpOrderItem.snapItemId、GzJpRefund.refundType（加之前 INSERT 走列默认 purchase_failed）。
- GzJpRefundTxService 约 261 行注释与 GzJpRefundFixture 异常文案仍写 uk_order_item，实际键为 uk_item_type（只捕获 DuplicateKeyException，语义不变，改文案即可）。
- 下一个空号：dict_id 9298 / dict_code 92866 / config_id 14040006。
- filter.categoryWhitelist 为空，初值由 GZ-SNAP-302 另起迁移；pricing 三项为 null 时报价必须拒绝。

## 已知风险
- 共享脚本 `-am` 装 gz-jp 时会把 gz-common 按工作区装入（含当时 GZ-PAY-106 未提交改动），8080 当时跑的是该状态。
- `[out of order]` 仅为 outOfOrder=true 标记；4 个版本均大于原最大号。
