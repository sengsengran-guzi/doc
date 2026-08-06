---
ticket: GZ-JP-106
track: FULFILL
phase: D5
size: L
req_refs: [REQ-FULFILL-001, REQ-FULFILL-002, REQ-FULFILL-003, REQ-FULFILL-004, REQ-FULFILL-006, REQ-FULFILL-007, REQ-EVENT-002]
depends_on: [GZ-JP-105]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FLOW:F-JP-03.step2
  - FLOW:F-JP-03.step3
  - FIELD:gz_jp_order_item.fulfill_status
  - FIELD:gz_jp_order_item.tracking_no
accept:
  - name: 非法状态转移被拒 + 合法链路全程可达
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpFulfillStateMachineTest 2>&1 | tail -5
  - name: 批量发货后同批行共用一个单号且均为 delivered
    form: DATA
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(DISTINCT fulfill_status) FROM gz_jp_order_item
        WHERE tracking_no IS NOT NULL AND tracking_no<>'' AND del_flag='0'" | grep -qx 1 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM gz_jp_order_item
        WHERE fulfill_status='delivered' AND (tracking_no IS NULL OR tracking_no='' OR carrier_code IS NULL)
        AND del_flag='0'" | grep -qx 0
  - name: 置 delivered 未填单号被拒
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpShipRequireTrackingTest 2>&1 | tail -5
---

# GZ-JP-106 履约状态机 + 批量推进 / 批量发货 API

## §0 状态自检

1. GZ-JP-105 已 merge，`gz_jp_order_item` 有数据可推。
2. `grep -rn "gz_express_carrier" ruoyi-admin/src/main/resources/db/migration/` —— 
   确认快递字典已存在（9 项，dict_id 9130），**直接复用不新建**。

## What

状态链（挂在 `gz_jp_order_item` 上，**不是订单上**）：

```
purchasing 购买中
  ├─ purchase_failed 购买失败   ← 分支终态（退款由 GZ-JP-107 处理）
  └─ await_seller_ship 等待官方发货
       → jp_shipped 日本仓库已发货 → customs 清关中
       → cn_sorting 国内分拣中 → delivered 发货完毕
```

**批量推进接口**：`POST /system/gz/jp/fulfill/advance`，入参 `{itemIds: [], targetStatus}`。
- ★ **允许跳过中间态** —— 线下现货没有「等待官方发货」这一步（REQ-EVENT-002），
  校验只拒**倒退**和**跨越终态**，不强制逐级
- 一个客人可能 30+ 行，接口做单次条数上限（建议 200）并分批事务

**批量发货接口**：`POST /system/gz/jp/fulfill/ship`，入参 `{itemIds: [], carrierCode, trackingNo}`。
- 置 `delivered` + 写 `carrier_code` / `tracking_no` / `shipped_at`
- ★ `carrierCode` 与 `trackingNo` **必填**，缺一即拒
- ★ **不建包裹表** —— `tracking_no` 本身就是包裹标识，同单号的行天然属同一包裹

## AC

- 倒退被拒（如 customs → purchasing）
- 跳过中间态被允许（purchasing → jp_shipped）
- 置 delivered 未填单号被拒
- 一期**不做回退功能**（甲方未要求，砍在极简包里）

## ⚠️ 不写 cron

SnailJob 在 prod 未部署，所有 `@JobExecutor` 都不会跑。本域任何"自动推进"需求一律做成
读时惰性判定或 admin 手动批量，不要依赖定时任务。
