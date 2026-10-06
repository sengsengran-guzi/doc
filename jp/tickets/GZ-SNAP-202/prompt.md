---
ticket: GZ-SNAP-202
track: SNAP-GW
phase: D8
size: L
system: mercari-gateway
req_refs: [REQ-SNAP-005, REQ-SNAP-013, REQ-SNAP-018, REQ-SNAP-047, REQ-SNAP-048]
depends_on: [GZ-SNAP-201]
touches:
  - code/main/mercari-gateway/**
blueprint_refs:
  - FLOW:F-JP-12.step2
  - FLOW:F-JP-12.step3
  - FLOW:F-JP-12.step4
  - FLOW:F-JP-12.step3b
  - FLOW:F-JP-05.step3
  - OWN:mercari_item_live
accept:
  - name: 搜索 / 详情解析：JSON 接口与浏览器两条路径对已标明来源的夹具解析出相同字段，回放覆盖关键场景
    form: DATA
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_parse_parity.py tests/test_replay_coverage.py
    counterfeit: 降级路径漏解析 shipping_payer 或 status（两边结果不一致），或回放样本集缺了某一类（如没有拒代购样本，下游 303 / 502 无法测）→ 红
  - name: 图片代理与短链解析只放行煤炉域名（其余 403），图片带长缓存头
    form: API
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_img_proxy.py tests/test_resolve.py
    counterfeit: 图片代理放行任意 URL（成了开放代理）、短链解析跟随到非煤炉域名、或不带 Cache-Control → 红
  - name: 真煤炉契约（只读、≤5 次请求）：搜索返回在售且字段齐、详情含运费承担
    form: API
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q -m live tests/test_live_read.py
    counterfeit: 返回了非在售商品，或详情缺 shipping_payer / category_id → 红
---

# GZ-SNAP-202 日本服务只读接口：搜索 / 详情 / 图片代理 + 降级 + 限速

## §0 状态自检

1. GZ-SNAP-201 已完工，`pytest -q` 绿。
2. 读 `FLOW:F-JP-12.step2~4`（字段名逐字照抄）与 `_spike/mercari-probe/probe.py` / `pw.py`。
3. 确认运行环境出口：本地开发经 Kevin 的东京代理，**只允许 live 测试那几次请求**，不许循环、不许压测。

## What

1. `GET /v1/search`：mercapi 搜索（只要在售；`category_ids` 原样作为煤炉搜索的分类条件），映射为契约字段（含 `item_type: c2c|shops`，原样转述、不在这里过滤）；
   字段映射照 `FLOW:F-JP-12.step2` 末尾的实测来源表（`doc/jp/_spike/mercari-probe/READ-PROBE-2026-10-03.md`）；`sort` 三种映射到煤炉排序参数；`page` 分页。
2. `GET /v1/items/{external_id}`：mercapi 详情 → 契约字段（`shipping_payer` 由运费承担文案判定：`送料込み(出品者負担)` → seller，其余 → buyer）；不存在 → 404 + `{status: deleted}`。
3. 降级：JSON 接口连续失败（异常 / 非 200 / 解析失败）→ 自动切 Playwright 渲染网页解析，响应 `via=browser`；接口恢复后自动切回。
4. 全局令牌桶限速（每秒请求数经环境变量配置），超限 429。
5. `GET /v1/img/{path}`：只代理煤炉静态图域名白名单，`Cache-Control: public, max-age=31536000, immutable`。
5a. `GET /v1/sellers/{seller_id}`：mercapi `profile` → `{seller_id, intro, num_ratings}`（`FLOW:F-JP-12.step3b`），只读匿名。
5b. `GET /v1/resolve?url=`：跟随煤炉 App 分享短链（`merc.li` 等）的跳转解析出商品 ID；只跟随煤炉域名白名单内的跳转、最多 3 跳；解析不出 404（`FLOW:F-JP-12.step3`）。
6. 样本：预算内取得少量真实匿名响应并脱敏保存；JSON / HTML 解析一致性用带来源说明的夹具验证，缺少真实 HTML 时可构造合成 HTML，不冒充网页录制。不要求每件商品两种格式都实际采集。
6b. **回放样本集** `fixtures/replay/`（dev / QA 默认读源）：2~3 个关键词的搜索结果 + 下列每类至少一件商品的详情与卖家简介——
   包邮 auto、到付（shippingPayerId=1）、「コメント必須」、拒代购（描述含「代行業者は即購入不可」类）、「専用」、Shops、已售出、白名单外分类；
   再加一个 `merc.li` 短链映射。八类覆盖及关键词结果、卖家简介可用明确标注的合成夹具补齐；已有真实响应可复用，不为凑齐类别反复访问煤炉。
   一次性录制 ≤15 次真实请求，live 单次 ≤5 次；底层网络请求与跳转均计数。卖家昵称等个人信息脱敏。README / 来源清单逐件写清真实或合成、用途与未实测范围，供 302/303/501/502 引用。不得把合成夹具测试作为真实煤炉结构已验收的证据。
7. live 测试 `tests/test_live_read.py` 打 `@pytest.mark.live`，默认不跑，accept 显式 `-m live`。

## AC

- 三条 accept 绿；默认 `pytest -q`（不含 live）全绿。
- 搜索结果只含在售；详情字段齐全；降级路径字段一致。

## 口径提示

- 日本服务**不做**翻译、过滤、准入（那是 ruoyi 的规则，OWN:snap_runtime_config）——原样转述煤炉数据。
- 分类白名单要用的煤炉 category_id：本卡顺手把「动漫周边」相关分类 ID 列表整理进 `README.md`（GZ-SNAP-302 据此写初值）。
