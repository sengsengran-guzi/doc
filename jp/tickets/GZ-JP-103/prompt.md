---
ticket: GZ-JP-103
track: EVENT
phase: D3
size: S
req_refs: [REQ-EVENT-001, REQ-PROD-001]
depends_on: [GZ-JP-101, GZ-JP-102]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/controller/applet/**
blueprint_refs:
  - FLOW:F-JP-02.step1
  - UI:mp.home
  - UI:mp.event_detail
  - UI:mp.product_detail
accept:
  - name: 场列表接口返回结构完整且只含应可见的场
    form: API
    run: |
      RESP=$(curl -s 'http://localhost:8080/app/gz/jp/event/list' -H 'clientid: mp-applet-gz-jp'); \
      echo "$RESP" | jq -e '.rows | length > 0 and (.[0] | has("eventNo") and has("name") and has("startTime") and has("endTime") and has("status"))' >/dev/null && \
      echo "$RESP" | jq -e '[.rows[] | select(.status=="draft")] | length == 0' >/dev/null
  - name: 商品详情返回注意事项与包邮价
    form: API
    run: |
      PID=$(curl -s 'http://localhost:8080/app/gz/jp/product/list?eventId=1' -H 'clientid: mp-applet-gz-jp' | jq -r '.rows[0].id'); \
      curl -s "http://localhost:8080/app/gz/jp/product/$PID" -H 'clientid: mp-applet-gz-jp' \
        | jq -e '.data | has("noticeText") and has("priceCent") and has("deliveryDateText") and (has("stockRemain")|not)' >/dev/null
---

# GZ-JP-103 mp 端场 / 商品查询 API

## §0 状态自检

1. GZ-JP-101/102 已 merge，且 dev 库有至少一个 open 场 + 若干商品（没有则本 ticket 顺带 seed 一批测试数据）。

## What

C 端只读接口，base path `/app/gz/jp/`，`@SaIgnore`（匿名可浏览，下单才要登录）。

- `GET /app/gz/jp/event/list` —— 场列表，按 status 分组返回（进行中置顶），**draft 场不下发**
- `GET /app/gz/jp/event/{id}` —— 场详情
- `GET /app/gz/jp/product/list?eventId=` —— 场内商品分页
- `GET /app/gz/jp/product/{id}` —— 商品详情（含 noticeText）

**场状态读时惰性判定**：查询时用 `end_time` 与当前时间实时比对，过期的即便库里还是 open 也返回 closed。

## AC

- 匿名可调（不带 token 也能浏览）
- draft 场与 off_shelf 商品不下发
- 返回字段命名与 `field-ssot.yaml` 一致（camelCase）
