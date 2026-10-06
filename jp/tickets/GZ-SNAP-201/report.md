# GZ-SNAP-201 实现报告

STATUS: DONE

实现分支：`mercari-gateway/task/D8`。接手 HEAD `abd19627e`，已有工程骨架；接手时 6 个部署文件未提交，本轮完整核对票据 What / AC 与 `FLOW:F-JP-12`、ADR-0025、OWN 主权边界后完成部署断点并验证。

## 改动与提交

本轮提交：`mercari-gateway@f8b984693fee55e845b4f214600d08f1e28ffa52`。

- `.env.example`：可选构建期 `APT_MIRROR`，给出实际可构建的 HTTPS 镜像示例。
- `Dockerfile`：Python 3.12 / Chromium 常驻 API `gateway` 目标与带 x11vnc / noVNC 的手工登录 `login` 目标；API 目标直接使用基础镜像 Python，登录目标额外安装桌面系统组件。
- `docker-compose.yml`：默认 replay + fake，仅启动 gateway；手工登录在 login profile 独立构建，两个目标共用 `/data` 卷，宿主端口均仅绑定 127.0.0.1。
- `docker/entrypoint.sh`、`docker/login.sh`：使用镜像实际提供的 `python3`；登录入口在独立镜像目标。
- `README.md`：镜像目标、构建参数、部署到阿里云东京与员工通过 SSH 隧道手工登录步骤。

已核对既有实现：HMAC 使用原始路径/查询串与请求体 SHA256，60s 时间窗口，health 必须签名；订单号幂等持久化 SQLite；并发/中途重启返回 unknown，避免第二次点击；fake 五类脚本结果、点击账本、只读对账与交易巡检；disabled 下单 503，real/live 本卡 501 占位；replay 完全离线按查询/ID 加载；采购账号 session 仅摘要，秘密从环境读取。

新迁移：none。新增清单外应用依赖：none。越界代码文件：none（本报告为要求的文档交付）。无 push、无合流、未改主 miniapp、未重启 8080、未访问真煤炉。

## 原样 accept（项目根，以 bash -c 执行）

### #0 HMAC

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_auth.py
```

Raw output，exit 0：

```text
.....................                                                    [100%]
21 passed in 0.28s
```

### #1 fake 幂等

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_fake_driver.py
```

Raw output，exit 0：

```text
.....................................                                    [100%]
37 passed in 2.79s
```

### #2 Docker health

```bash
cd code/main/mercari-gateway && docker compose up -d --build >/dev/null && sleep 5 && \
.venv/bin/python scripts/signed_get.py /v1/health | python3 -c "import json,sys; d=json.load(sys.stdin); \
assert d['driver'] in ('fake','real','disabled'); assert isinstance(d['accounts'], list); \
assert not any(k in json.dumps(d).lower() for k in ('password','cookie','token')); print('ok')"
```

首次沙箱访问 Docker socket 被拒；使用用户已授权的 require_escalated 原样重跑。Raw output，exit 0：

```text
 Container mercari-gateway-gateway-1  Running
ok
```

## 完整测试与补充验证

```bash
cd code/main/mercari-gateway && .venv/bin/pytest -q
```

Raw output（前后工具输出合并），exit 0：

```text
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 3.25s
```

`git diff --check` 与两个 shell 入口 `bash -n` 均 exit 0，无输出。测试运行后仅修正文档/构建注释里的镜像 URL 为 HTTPS，运行代码与测试结果对应提交一致。

容器检查 raw：

```text
3.12.3
image_env_files []
2026-10-06 00:31:35,163 INFO gateway gateway 0.1.0 up driver=fake read_source=replay accounts=2
```

手工登录镜像首次使用本地 HTTP apt 镜像时 universe 索引持续重试，终止该构建；第二次以 HTTPS 同站镜像构建成功：

```bash
docker compose --profile login build --build-arg APT_MIRROR=https://mirrors.aliyun.com/ubuntu-ports/ login
```

Raw 摘录，exit 0：

```text
#14 86.12 Fetched 35.1 MB in 1min 26s (408 kB/s)
#14 193.2 Fetched 32.9 MB in 1min 44s (315 kB/s)
#14 DONE 204.5s
#15 writing image sha256:e9d2b9460d90bf569c25c739cc03caa1f69fe5593555fbc6436e923a4aec9924 done
#15 naming to docker.io/library/mercari-gateway-login:local done
#15 DONE 0.7s
```

登录模式仅用 `about:blank`、临时 `/tmp/gz-snap-201-profiles`、空代理，不碰真实采购登录态：

```bash
docker compose --profile login run -d --rm --name gz-snap-201-login-check --service-ports -e LOGIN_START_URL=about:blank -e LOGIN_MAX_MINUTES=1 -e GATEWAY_PROFILE_DIR=/tmp/gz-snap-201-profiles -e GATEWAY_PURCHASE_PROXY= login snap201_check
```

浏览器及 noVNC 验证 raw：

```text
2026-10-06 00:39:12,255 INFO gateway.login login mode ready for account snap201_check — close the browser window when done (max 1 min)
novnc_http=200
persistent_profile=ok
6080/tcp -> 127.0.0.1:6080
```

测试 login 容器已 `docker stop` 并由 `--rm` 清理，gateway 保留于 127.0.0.1:8700；`git status --porcelain` 空。

## 下游提示与限制

- GZ-SNAP-202 实现 live 读源并录制 replay 样本；目前 fixtures 只有目录占位，未录制商品不会凭空产生数据。
- GZ-SNAP-203/204 实现 real 驱动；复用 `profile_path` 的账号持久化目录，真实账号登录仍等甲方资源与 D13 技术验证。
- GZ-SNAP-305 可调用签名的 `/_fake/script` 和 `/_fake/ledger`；默认 timeout 为 50s，unknown 不再下单；`visible_after_reconciles` 可控制购买记录延迟。
- 登录镜像在本机 arm64 用 HTTPS apt 镜像已构建；本地 `.env` 未改，若它仍配置 HTTP 镜像，后续登录构建应使用上述 build-arg 或由主线程自行更新该本地配置。
- 本报告证明本地容器/空白桌面能力；未声称真实采购账号登录、东京机房部署或真钱下单已验收。
