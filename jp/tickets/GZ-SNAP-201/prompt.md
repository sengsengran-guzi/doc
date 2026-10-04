---
ticket: GZ-SNAP-201
track: SNAP-GW
phase: D8
size: M
system: mercari-gateway
req_refs: [REQ-SNAP-017, REQ-SNAP-039]
depends_on: []
touches:
  - code/main/mercari-gateway/**
blueprint_refs:
  - FLOW:F-JP-12
  - FLOW:F-JP-12.step0
  - FLOW:F-JP-12.step1
  - FLOW:F-JP-12.step5
  - FLOW:F-JP-12.step6
  - FLOW:F-JP-12.step7
  - OWN:mercari_account_session
  - OWN:snap_money
accept:
  - name: HMAC 鉴权：错签 / 超时戳 / 缺头一律 401，正确签名放行
    form: API
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_auth.py
    counterfeit: 只校验签名不校验时间戳（重放可过），或 /v1/health 免签 → 用例「ts 偏差 >60s 拒」「health 无签名 401」红
  - name: fake 驱动按 order_no 幂等——同一 order_no 第二次调用返回首次结果，账本里只记一次购买
    form: STATE
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_fake_driver.py
    counterfeit: fake 驱动每次调用都「点一次购买」（账本计数 2）或第二次返回不同结果 → 红
  - name: 容器构建可起，health 返回驱动模式与账号摘要（不含任何凭据字段）
    form: API
    run: |
      cd code/main/mercari-gateway && docker compose up -d --build >/dev/null && sleep 5 && \
      .venv/bin/python scripts/signed_get.py /v1/health | python3 -c "import json,sys; d=json.load(sys.stdin); \
      assert d['driver'] in ('fake','real','disabled'); assert isinstance(d['accounts'], list); \
      assert not any(k in json.dumps(d).lower() for k in ('password','cookie','token')); print('ok')"
    counterfeit: health 把 cookie / 密码透出给 ruoyi（违反 OWN:mercari_account_session）或不返回 driver → 红
---

# GZ-SNAP-201 日本服务 mercari-gateway：仓库初始化 + 部署 + 鉴权 + 健康检查 + fake 驱动

## §0 状态自检

1. `ls code/main/mercari-gateway` 应不存在（本卡新建）。新建后 `git init -b main`，再 `git switch -c feat/jp-snap`；**暂无远程**，同 miniapp-jp。
2. 通读 ADR-0025 全文与 `FLOW:F-JP-12`（接口契约的唯一真源，字段名逐字照抄）。
3. 参考 `doc/jp/_spike/mercari-probe/`（mercapi / playwright 的最小用法）。

## What

1. 工程：Python 3.12 + FastAPI + uvicorn + httpx + mercapi + playwright + pytest。
   ★ 依赖只限这份清单（Kevin 已批准的 Python 栈范围）；需要清单外的包先停下问。
   结构：`app/main.py`（路由）/ `app/auth.py`（HMAC）/ `app/drivers/{fake,real,disabled}.py` / `app/settings.py`（环境变量）/ `tests/` / `scripts/signed_get.py`。
2. HMAC 中间件，算法与头名逐字照 `FLOW:F-JP-12.step0`；`/v1/img` 豁免；secret 只从环境变量读。
3. `GET /v1/health`：driver / version / egress_ok / accounts[]（`account_code` 列表来自环境变量配置；fake 模式下 session 恒 ok）。
4. 驱动抽象：`purchases` / `reconcile` / `trades` / `health_session` 四个方法。
   - **fake**：内存（或 SQLite）账本 + 脚本化结果：按 `external_id` 后缀或 `POST /v1/_fake/script`（仅 fake 模式挂载）预设
     success / failed:<reason>（含 account_unpayable）/ unknown / timeout（睡 50s）/ risk 五种结果；提供 `GET /v1/_fake/ledger` 返回每个 order_no 的「点击购买次数」——这是 GZ-SNAP-305 故障注入断言的数据源。
   - **disabled**：purchases 恒 503 `driver_disabled`。
   另一个正交开关 **读源** `GATEWAY_READ_SOURCE=live|replay`（`FLOW:F-JP-12` body）：本卡实现读源抽象与 replay 加载器（按查询串 / 商品 ID 从 `fixtures/replay/` 取 JSON），
   `docker-compose.yml` 默认 `replay` + `fake`；样本本身由 GZ-SNAP-202 录制。
   - **real**：本卡只留占位（返回 501），真实现见 GZ-SNAP-203 / 204。
   - 幂等：任何驱动都先查本地幂等表（SQLite，`order_no → 首次结果`），命中直接返回。
5. Dockerfile + `docker-compose.yml`（单服务，端口经环境变量；playwright 浏览器装进镜像）；`README.md` 写部署到阿里云东京的步骤与环境变量清单。
5b. **远程登录工具**（纸面推演 P12）：采购账号要由日本员工手工登录（含短信验证），而浏览器跑在东京服务器上。
   容器内提供一个「登录模式」：以有界面方式（Xvfb）打开该账号的持久化浏览器目录，经 noVNC 暴露一个网页远程桌面，
   只监听 127.0.0.1，员工通过 SSH 隧道访问；登录完成后关闭登录模式，下单驱动复用同一个持久化目录。
   README 写清员工操作步骤（截图级）。D13 技术验证就要用它，所以放在本卡。不做任何自动填写密码 / 验证码。
6. 测试：`tests/test_auth.py`、`tests/test_fake_driver.py`。

## AC

- 三条 accept 绿；`pytest -q` 全绿。
- 日志与响应里不出现任何凭据；镜像不含 secret。
- 只读接口（search / items / img）的真实现在 GZ-SNAP-202，本卡可先返回 501。

## 口径提示

- 部署目标是甲方采购的阿里云东京服务器（REQ-SNAP-065，未到位）；本卡只要求本地 docker 能起。
- **不要**用 Kevin 本机代理出口做任何批量请求；本卡不访问真煤炉。
