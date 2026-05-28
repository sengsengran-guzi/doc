# D01 — Progress

> 今日 ticket 状态表。Kevin testing-human 后更新。

---

| Ticket | 标题 | AI 自测 | testing-human | revision 轮次 | 状态 |
|---|---|---|---|---|---|
| GZ-SYS-001 | 项目脚手架与云服务初始化 | ✅ | ⏳ 待 Kevin | 0 | human-testing |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

**revision 轮次说明**：每次 Kevin 在 ticket 任务卡 `§revision` 写新一批问题 → AI 闭环修一轮 → +1。
revision 轮次 ≥ 3 时应停下来想：是不是 ticket 边界没切对，还是 AC 写得太模糊。

---

## 阻塞 / 风险

> 详见 `reports/GZ-SYS-001.md §风险提示`（R1-R8 完整列表），下面只挑当前阻塞 / 等 Kevin 决策项。

### R1 — MySQL/Redis 凭证与 ruoyi dev profile 不一致 ✅ 已解决（实施漏项补全）

- **原现象**：`mvn spring-boot:run` 启动到 datasource 阶段挂在 `Access denied for user 'root'@'localhost'` — 本机 brew mysql 占 3306 + 密码不是 ruoyi 默认 `root`
- **解决**：实施漏项补全建了 `script/docker/dev-compose.yml`（MySQL+Redis+MinIO 三容器，端口偏移 3307 / 6380 / 9000+9001 避开本机占用，密码对齐 ruoyi dev profile）+ `application-dev.yml` 同步改端口
- **Kevin testing-human 用法**：`cd code/main/RuoYi-Vue-Plus && docker compose -f script/docker/dev-compose.yml up -d`，详见 testing-human.md §0.1
- **AI 自测**：reports §AI 自测 5 已贴 raw output（3 容器 Up + mysql ready + ry-vue 自建 + redis PONG + MinIO 200）
- **额外坑提醒**：Kevin shell 配了 `http_proxy=http://127.0.0.1:1081`，curl localhost 系列必须加 `--noproxy localhost,127.0.0.1`，详见 testing-human.md §0.1.y

### R4 — miniapp 423 untracked 文件 commit 拆分策略 ⚠️ 等 Kevin 决策

- **现象**：miniapp 实施期产生 423 个 untracked + 1 个 modified (README.md)，混在一个 commit 难追溯
- **建议拆 3 commit**：
  1. `feat(mp): rsync unibest 4.4.0 scaffolding from dongjiaoshan`（纯 rsync 内容）
  2. `chore(mp): remove dongjiaoshan business pages/api/components`（清理）
  3. `feat(mp): add 7 sensenran placeholder pages + sensenran branding`（占位 + 改名 + tabbar）
- **决策项**：Kevin 是否采纳 3-commit 方案？还是 1 commit 接受？testing-human §3 R-项决策段提示 Kevin

### R7 — App.vue.onLaunch 残留 `/djs/dict/version` 调用 ⚠️ 等 Kevin 决策放哪个 ticket 清

- **现象**：dongjiaoshan/miniapp 的 App.vue onLaunch 启动调 `syncDictIfNeeded()` → 调 `/djs/dict/version`（djs 业务 url），sensenran 后端无此端点 → 每次启动 console 多一条 warn（不阻塞，dict.ts 内 try-catch 兜底）
- **应对建议**：挪到 **GZ-COMMON-DICT** 后续 ticket，那 ticket 会同时迁移 dongjiaoshan/djs-common 的 DictController 改名为 gz 路由
- **决策项**：testing-human §3 R-项决策段提示 Kevin，决定是本 ticket §revision 立刻清，还是挪到 GZ-COMMON-DICT 一起干

### R2 / R3 / R5 / R6 / R8 — 非阻塞 / 已收敛 / 留作 D02+ 自然消化

详见 `reports/GZ-SYS-001.md §风险提示`。

### R9 — CI/CD GitHub Secrets 待 Kevin 配齐 ⚠️ 阻塞首次自动部署（不阻塞 D01 close）

- **现象**：实施漏项补全 #2 已落地 6 个 workflow + 1 个 deploy compose，1:1 映射 dongjiaoshan，但 GitHub Secrets 未配
- **5 个 secrets 待配（分 repo 配，详见 doc/04 v0.3 §5.4.4）**：
  - RuoYi-Vue-Plus + plus-ui 两个 repo 各配：`SSH_HOST_STAGING` / `SSH_PRIVATE_KEY_STAGING` / `SSH_HOST_PROD` / `SSH_PRIVATE_KEY_PROD`
  - miniapp repo 配：`WECHAT_PRIVATE_KEY`（PEM 多行 RSA）
- **阻塞前置**：
  - SSH 系列等阿里云 ECS 购买（doc §11 Q2 🟡 执行中）
  - WECHAT_PRIVATE_KEY 等甲方主体微信小程序账号申请通过（AC 2.6 + AC 3.2）
- **应对**：D01 testing-human 阶段**不要 git push staging**（会触发 workflow 但 secrets 缺失 fail）。Kevin testing-human OK 后**只 commit 不 push**，等 ECS + 微信账号 ready 再首次 push 跑 CI/CD
- **AI 自测**：reports §自测 6 已贴 diff dongjiaoshan / yml 解析 / 业务字 grep 完整 raw output，确认代码层就绪

### R10 — environment files placeholder 待 Kevin 填实际值 ⚠️ 阻塞首次自动部署（不阻塞 D01 close）

实施漏项补全 #3 已落地 environment 文件链路（详见 reports §自测 7），但 6 个 placeholder 待 Kevin 填实际值后 CI/CD 才能跑通：

| # | 文件 | 字段 | 当前占位 | 待填实际值 | 阻塞 ticket |
|---|---|---|---|---|---|
| 1 | `miniapp/.env.staging` | `VITE_WX_APPID` | `TBD_BY_KEVIN_WX_APPID` | 真实微信 appid（如 `wx1a2b3c...`） | GZ-SYS-001 AC 2.6 / AC 3.2 |
| 2 | `miniapp/.env.staging` | `VITE_SERVER_BASEURL` | `https://api.sensenran-guzi.com` | 实际域名（或公网 IP，待 ICP 备案通过后切 HTTPS） | GZ-SYS-001 AC 2.1 / 2.3 |
| 3 | `RuoYi-Vue-Plus/.github/workflows/deploy-staging.yml` | `REPO_DIR` | `/www/wwwroot/api.sensenran-guzi.com` | ECS 实际部署路径（域名定后） | GZ-SYS-001 AC 2.3 |
| 4 | `RuoYi-Vue-Plus/.github/workflows/deploy-prod.yml` | `REPO_DIR` | `/opt/sensenran-guzi-prod` | 同上（如沿用 dongjiaoshan /opt 范式可不改） | GZ-SYS-001 AC 2.3 |
| 5 | `plus-ui/.github/workflows/deploy-{staging,prod}.yml` | `TARGET` | `/www/wwwroot/admin.sensenran-guzi.com` | admin 子域名（域名定后） | GZ-SYS-001 AC 2.1 |
| 6 | 后端 ECS 上 `.env`（不入库） | `MASTER_DB_URL` / `MASTER_DB_PASSWORD` / `REDIS_HOST` / `REDIS_PASSWORD` 等 | 默认值占位 | 阿里云 RDS endpoint + 密码 / 阿里云 Redis endpoint + 密码 | GZ-SYS-001 AC 2.4 / 2.5 |

**应对**：与 R9 合并处理 — Kevin 在阿里云 ECS + 微信小程序账号 ready 后一次性填齐 R9 secrets + R10 placeholder，然后首次 push 跑 CI/CD。

**AI 自测**：reports §自测 7 已贴跨 3 端 8 文件 diff + grep 业务字 0 命中 + miniapp CI 链路 4 环节完整性验证，确认代码层就绪。

---

## 已挪到明日的 ticket

无。D01 只编排 1 个 ticket（GZ-SYS-001 脚手架本身工作量大且所有后续 ticket 依赖它，单 ticket 排单合理）。

D02 候选 ticket 编排在 `doc/daily/README.md §2`（由 product 排单后定）。
