---
ticket: GZ-SNAP-101
track: SNAP
phase: D7
size: M
req_refs: [REQ-SNAP-041, REQ-SNAP-020, REQ-SNAP-014]
depends_on: []
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - FIELD:gz_jp_snap_item.active_order_item_id
  - FIELD:gz_jp_snap_item.external_id
  - FIELD:gz_jp_snap_purchase.order_item_id
  - FIELD:gz_jp_snap_purchase.purchase_status
  - FIELD:gz_jp_snap_account.account_code
  - FIELD:gz_jp_snap_term.zh_term
  - FIELD:gz_jp_fx_rate.rate_per_100jpy
  - FIELD:gz_jp_order_item.product_id
  - FIELD:gz_jp_order_item.snap_item_id
  - FIELD:gz_jp_refund.refund_type
  - FLOW:F-JP-11
accept:
  - name: 5 张新表建齐且公共字段全集在（含 tenant_id）
    form: DDL
    run: |
      for t in gz_jp_snap_item gz_jp_snap_purchase gz_jp_snap_account gz_jp_snap_term gz_jp_fx_rate; do
        docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
          SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='ry-vue' AND TABLE_NAME='$t'
            AND COLUMN_NAME IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
          | grep -qx 7 || { echo "missing public fields: $t"; exit 1; }
      done
    counterfeit: 任一新表漏 create_dept 或 tenant_id（gz_ord 踩过：INSERT 时才炸）→ 计数 6 不等于 7 → 红
  - name: 一期两表结构改动到位（product_id 可空 + snap_item_id；退款唯一键换成含 refund_type 且存量回填）
    form: DDL
    run: |
      Q() { docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "$1"; }
      Q "SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='ry-vue' AND TABLE_NAME='gz_jp_order_item' AND COLUMN_NAME='product_id'" | grep -qx YES && \
      Q "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='ry-vue' AND TABLE_NAME='gz_jp_order_item' AND COLUMN_NAME='snap_item_id'" | grep -qx 1 && \
      Q "SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='ry-vue' AND TABLE_NAME='gz_jp_refund' AND INDEX_NAME='uk_item_type'" | grep -qx 'tenant_id,order_item_id,refund_type' && \
      Q "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='ry-vue' AND TABLE_NAME='gz_jp_refund' AND INDEX_NAME='uk_order_item'" | grep -qx 0 && \
      Q "SELECT COUNT(*) FROM gz_jp_refund WHERE refund_type IS NULL OR refund_type=''" | grep -qx 0
    counterfeit: 只加新唯一键不删旧 uk_order_item（shipping_diff 第二条插不进去）或存量退款单 refund_type 为空 → 红
  - name: 5 个代切配置键落在租户 1001、定价三项为空、自动下单默认关；二期字典齐
    form: DATA
    run: |
      Q() { docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "$1"; }
      Q "SELECT COUNT(*) FROM sys_config WHERE tenant_id='1001' AND config_key IN ('gz.jp.snap.pricing','gz.jp.snap.filter','gz.jp.snap.gate','gz.jp.snap.auto','gz.jp.snap.trade')" | grep -qx 5 && \
      Q "SELECT JSON_EXTRACT(config_value,'$.enabled') FROM sys_config WHERE tenant_id='1001' AND config_key='gz.jp.snap.auto'" | grep -qx false && \
      Q "SELECT COUNT(*) FROM sys_config WHERE tenant_id='1001' AND config_key='gz.jp.snap.pricing' AND JSON_EXTRACT(config_value,'$.markupRatio') IS NOT NULL AND JSON_TYPE(JSON_EXTRACT(config_value,'$.markupRatio'))<>'NULL'" | grep -qx 0 && \
      Q "SELECT COUNT(DISTINCT d.dict_type) FROM sys_dict_type t JOIN sys_dict_data d ON d.dict_type=t.dict_type WHERE t.dict_type IN ('gz_jp_snap_platform','gz_jp_snap_item_status','gz_jp_snap_shipping_payer','gz_jp_snap_gate','gz_jp_snap_mode','gz_jp_snap_purchase_status','gz_jp_snap_fail_reason','gz_jp_snap_trade_status','gz_jp_snap_account_health','gz_jp_snap_term_type','gz_jp_fx_source','gz_jp_refund_type')" | grep -qx 12 && \
      Q "SELECT COUNT(*) FROM sys_dict_data WHERE dict_type='gz_jp_item_source' AND dict_value='snap'" | grep -qx 1
    counterfeit: sys_config 裸 INSERT 不写 tenant_id（落 '000000'，登录用户读不到，本项目踩过两次）或定价写了占位数值 → 红
---

# GZ-SNAP-101 代切数据底座（DDL + 一期两表改动 + 字典 + 配置种子）

## §0 状态自检

1. 读 ADR-0025 §5、`field-ssot.yaml` 中 5 张新表与 `gz_jp_order_item` / `gz_jp_refund` 两段（`authority_lint.py show FIELD:<表>.<列>` 逐列取）。
2. **迁移时间戳 = 创建当下**：`date +V%Y%m%d%H%M`；已应用迁移 append-only，**不许编辑任何既有迁移**（一期 `V202608070632` / `V202608071102` 都不碰）。
3. 查活库空号（本项目撞过 3 次号）：
   - 字典：`SELECT MAX(dict_id), (SELECT MAX(dict_code) FROM sys_dict_data) FROM sys_dict_type;`
   - 配置：`SELECT config_id FROM sys_config WHERE config_id BETWEEN 14040000 AND 14049999;`（应为空，本卡用 14040001–14040005）
   - 同时 `grep -rn "1404000[0-9]" ruoyi-admin/src/main/resources/db/migration/`。
4. `V202608101050__GZ-JP-201-jp-home-banner-config.sql` 头注释：sys_config **必须显式写 `tenant_id='1001'`**、`config_id` 必须显式指定。
5. 本卡不建菜单（菜单随 admin 页一起建，GZ-SNAP-401~404）。

## What

拆成 4 个迁移文件（每个独立可读，失败好定位）：

1. `…__GZ-SNAP-101-create-snap-tables.sql`：5 张新表，列 / 类型 / 唯一键 / 索引逐字照 field-ssot；公共字段七件套 + `version`；
   `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`，UNIQUE 全含 `tenant_id`。
2. `…__GZ-SNAP-101-alter-order-item-and-refund.sql`：
   - `gz_jp_order_item`：`product_id` 改 `NULL`、加 `snap_item_id BIGINT NULL`、加索引 `idx_snap_item(tenant_id, snap_item_id)`；
   - `gz_jp_refund`：加 `refund_type VARCHAR(20) NOT NULL DEFAULT 'purchase_failed'`（存量行由默认值回填）、
     删 `uk_order_item`、建 `uk_item_type(tenant_id, order_item_id, refund_type)`。
3. `…__GZ-SNAP-101-seed-dict.sql`：12 个新字典（值照 field-ssot 各 dict 列注释）+ 给既有 `gz_jp_item_source` 追加 `snap=代切`。
   ★ `gz_jp_item_source` 已存在：只 INSERT 新 dict_data，**不要** DELETE 再重建（会动一期数据的 dict_code）。
4. `…__GZ-SNAP-101-seed-config.sql`：5 个配置键（值结构见 `FLOW:F-JP-11` body）：
   - `pricing` = `{"markupRatio":null,"fixedFeeCent":null,"estShippingCent":null,"quoteTtlSec":600}`（三项留空，甲方填，REQ-SNAP-061）
   - `filter` = `{"categoryWhitelist":[],"keywordBlacklist":[]}`（白名单初值由 GZ-SNAP-302 实测后另起迁移写入）
   - `gate` = `{"blockKeywords":["専用","様専用","さん専用"],"proxyRefuseKeywords":["代行業者","代行NG","代行不可","代行お断り","代行禁止","越境","転売業者","業者NG","業者お断り","楽一番","公式パートナー"],"manualKeywords":["コメント必須","即購入不可","即購入NG","即購入NO","即購入禁止","購入前コメント"]}`
   - `auto` = `{"enabled":false,"pausedReason":"未上线","pausedAt":null}`（上线前一直关）
   - `trade` = `{"rateDeadlineHours":24,"patrolMinutes":20}`（实测有卖家要求到货 24 小时内评价）

## AC

- 5 表公共字段齐；两表改动到位且存量数据不受损（一期全部单测照旧绿：`mvn test -pl ruoyi-modules/ruoyi-gz-jp -am -DskipTests=false`）。
- 字典 12 个 + `snap` 值；配置 5 键全在 1001 租户。
- 重启应用 Flyway 无失败（`SELECT COUNT(*) FROM flyway_schema_history WHERE success=0` = 0）。

## 口径提示

- `gz_jp_order_item.product_id` 放开可空后，一期代码里所有 `JOIN gz_jp_product` 的查询都要能容忍空值 —— 那是 GZ-SNAP-102 的活，本卡只动结构。
- 改完迁移后本地要 `mvn clean` 再起（避免 target 里残留幽灵副本）。
