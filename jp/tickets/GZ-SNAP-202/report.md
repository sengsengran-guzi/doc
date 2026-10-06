# GZ-SNAP-202 完工报告

STATUS: DONE

- 实现仓：`code/main/mercari-gateway`，分支 `task/D8`。
- commit：`0feff65`（`feat(jp-snap): GZ-SNAP-202 anonymous reads and sourced replay fixtures`）。未push、未merge、未切分支；提交后工作区干净。
- 新迁移：none。越界：none（报告本身由流程要求落doc，doc未提交）。主miniapp未改。
- 按Kevin最新授权，用2次少量真实采集 + 明确标注合成夹具完成；没有为样本类别重复联网或扩大穷举测试。此前SPEC_CONFLICT历史已留change-log，本报告表示最终当前结果。

## 实现

- JSON匿名search/items/sellers：使用锁定mercapi 0.5.0的DPoP请求构造器、httpx零重试且不跟随跳转，解析原始响应为FLOW:F-JP-12字段。搜索仅在售、Shops原样转述；三种排序映射、category_ids传入；分页沿平台不透明nextPageToken，无前页token时400且不额外爬前页。
- shipping_payer按文案映射seller/buyer，404带`status=deleted`。附加`category_lineage`，兼容真实`parent_category_id/root_category_id`和嵌套合成结构。真实Shops普通详情400 `shops_unsupported`，回放Shops供下游拒绝。
- JSON异常/非业务HTTP失败/解析缺字段降级Playwright匿名新上下文；连续失败2次开路、10秒后自动探测恢复。网页读取渲染JSON状态，缺完整字段503，不猜测。401/403/429和网页验证挑战停当前匿名路径、需人工确认恢复，不绕验证。
- 全局匿名读令牌桶（含unsigned图片），`GATEWAY_READ_RPS`默认10，超限429/Retry-After；当前部署单worker。HTTP CONNECT读代理可配`GATEWAY_READ_PROXY`，不使用采购登录态。
- 图片只放行精确静态域名，禁止任意目标/用户信息/非HTTPS/非443端口/路径穿越；不跟随图片跳转，校验image MIME，限10MiB，带`public, max-age=31536000, immutable`。
- 短链逐跳验证精确Mercari域名、最多3跳；不允许跳出白名单。replay使用同一URL安全约束，零联网。
- `pyproject.toml`默认排除live；唯一live测试需显式GATEWAY_LIVE_ALLOW，仅search+detail，transport hook最多5，本机账本最多2轮，未跑第二轮。

## 文件（按仓）

mercari-gateway：

- `app/read_sources/{live,parsing,security,replay}.py`：匿名适配、原始JSON/HTML解析、安全白名单、replay校验。
- `app/{rate_limit,main,settings}.py`：全局读桶、接线/关闭HTTP client、环境配置。
- `docker-compose.yml`、`.env.example`、`pyproject.toml`、`README.md`：运行配置、默认live排除、来源/分类/下游用法。
- `tests/{test_parse_parity,test_replay_coverage,test_img_proxy,test_resolve,test_live_read}.py`与`test_read_source.py`：关键离线契约、来源场景、白名单/限速/降级/恢复、有限真实契约。上游placeholder测试更新为注入离线API，不触网。
- `fixtures/replay/{README.md,provenance.json,live-budget.json,resolve.json}`，及`raw/`、`items/`、`search/`、`sellers/`、`img/item/synthetic.png`：真实脱敏子集与合成夹具。具体逐件路径见provenance。

## accept 命令与 raw output

#0（从项目根执行原命令）：

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_parse_parity.py tests/test_replay_coverage.py
```

```text
......                                                                   [100%]
6 passed in 0.07s
```

#1：

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_img_proxy.py tests/test_resolve.py
```

```text
....                                                                     [100%]
4 passed in 0.08s
```

#2：先在已授权采集shell设置`export GATEWAY_LIVE_ALLOW=1`，再执行原命令；只执行1轮。

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q -m live tests/test_live_read.py
```

```text
.                                                                        [100%]
1 passed in 1.25s
```

最终默认离线pytest：

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q
```

```text
........................................................................ [ 85%]
............                                                             [100%]
84 passed, 1 deselected in 3.47s
```

无Java改动，无surefire报告。没有0条假绿：上述实际执行数分别6、4、1、84。

## 少量真实采集预算账本

`fixtures/replay/live-budget.json`按底层httpx发送记录，不按业务方法猜测。此次时间`2026-10-06T01:13:07.238157+00:00`。

| 次序 | 方法 | host/path | 结果/用途 |
|---|---|---|---|
| 1 | POST | api.mercari.jp/v2/entities:search | 搜索「ブルーロック 缶バッジ」在售；验证字段，脱敏保存前三件字段子集 |
| 2 | GET | api.mercari.jp/items/get | 首个c2c `m23375959964`；验证shipping_payer/category_id/图片；保存脱敏字段子集 |

live：1轮/最多2轮，实际2/单轮5请求。一次性独立录制：0/15请求，未另起录制；live同时保存子集。总真实请求**2**，跳转0、重试0、fallback真实请求0、真实seller/image/shortlink/browser请求0。没有任何登录/购买/验证绕过。代理和secret未输出/未入git。

真实search子集含`itemType/categoryId/status/thumbnails/price`；真实详情分类`980→745→1328`。详情卖家id替换、描述全文脱敏，个人昵称/照片等未保存。不是完整原始响应存档。

其余八类及关键词/简介/HTML/短链/图片明确标为synthetic；真实JSON结构已验证，**真实网页HTML、真实简介、实际浏览器降级、真实App分享短链未联网验证**。不能把合成HTML一致性视为真实网页已验收。

## Docker真实API验证（0外部请求）

```bash
docker compose -f code/main/mercari-gateway/docker-compose.yml up -d --build gateway
```

实际产物：镜像`sha256:8b150b8a50fa1d7036b9b4aa90bd34e9e22d1518ae01597269f0e05da3ebf33c`；容器`mercari-gateway-gateway-1`重建/启动。随后容器内urllib请求localhost8700，按HMAC签名实际调用search/item/seller/resolve及unsigned image、断返回内容与cache header：

```text
Docker replay+fake: search=7 on_sale; item=buyer; seller=reject_proxy; resolve=m99000000001; unsigned image=200 immutable; external requests=0
```

容器保留在`127.0.0.1:8700`，默认`replay+fake`，后端8080未启动/未动，供独立QA直接使用。无额外重复测试。

## 下游302/303/501/502

| 场景 | external_id | seller_id |
|---|---|---|
| 包邮auto | m99000000001 | 99000001 |
| 到付 | m99000000002 | 99000002 |
| コメント必須 | m99000000003 | 99000003 |
| 拒代购 | m99000000004 | 99000004 |
| 専用 | m99000000005 | 99000005 |
| Shops | SYNTHETICshops01 | 99000006 |
| 已售出 | m99000000007 | 99000007 |
| 白名单外 | m99000000008 | 99000008 |

- 合成搜索关键词：`缶バッジ`、`アクリルスタンド`、`ブルーロック 缶バッジ`；`sort=created_desc&page=1&category_ids=`。
- 真实搜索前三件回放别名：`ブルーロック 缶バッジ 実録`（实际请求不含`実録`，README明示别名）。真实脱敏详情`m23375959964`可回放；没有真实profile。
- 短链：`https://merc.li/synthetic202`→`m99000000001`。图片：`/v1/img/item/synthetic.png`。
- 分类候选：975父745根1328（10-03probe）；980父745根1328（本次真实）。974/10868/7339/7506只是观察ID、未确认全为可售类；勿直接全放1328根。302需复核白名单，303用`category_id/category_lineage`复核，网关不替ruoyi决策准入。
- QA/返工/E2E只读本地样本，真实请求0；不能重跑live或为补类别联网。Shops仅回放拒绝用途，不是支持Shops购买/真实详情承诺。

## 限制与风险

网页状态结构仅合成夹具验证，真实React改版/页面没有完整JSON状态时会503，需要后续在明确授权预算中验证和适配；未伪报为真实HTML绿。商品/卖家真实数据会变，真实采集子集只代表此次契约。token bucket是单进程，跨worker需部署侧分配总速率。分页token存内存，重启后须从第一页开始；无随机页补爬。出现验证停匿名读后人工确认并重启，不自动规避。
