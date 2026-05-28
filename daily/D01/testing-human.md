# D01 — Testing-human（Kevin 一人跑）

> 只做 AI 干不了的活：浏览器 UI / 微信开发者工具 / DB 客户端 / 代码 review / 产品 sense 主观判断。
> 命令式 / 可断言为真假的事（mvn / curl / mysql count）→ AI 在 `reports/GZ-SYS-001.md §AI 自测` 里已贴 4 个 raw output block，不在这跑。

**本日特殊**：D01 是脚手架 ticket，没有业务 UI / 业务 mockup 可对照，所以 testing-human 主要是 **环境复跑 + 视觉感官 + R-项决策**，不是常规"业务流验收"。

---

## 0. 环境

> ⚠️ **顺序很重要**：先起基础设施，再起后端，再起前端 / 小程序。

### 0.1 基础设施 — sensenran 自己的本地开发栈

```bash
cd code/main/RuoYi-Vue-Plus
docker compose -f script/docker/dev-compose.yml up -d
# 起 sensenran-dev-mysql / sensenran-dev-redis / sensenran-dev-minio
# 端口：MySQL 3307 / Redis 6380 / MinIO 9000+9001（前两个偏移：Kevin 本机 brew mysql 占 3306 + redis-local 容器占 6379）
# 密码：root/root + ruoyi123 + ruoyi/ruoyi123，application-dev.yml 已同步
```

**自检 3 容器都 Up**：

```bash
docker ps | grep sensenran-dev
# 期望 3 行：sensenran-dev-mysql / sensenran-dev-redis / sensenran-dev-minio，全 Up
```

**首次启动需等 mysql 完全 ready**（约 5-15s 看到 `ready for connections` 后才能跑 spring-boot:run）：

```bash
docker logs sensenran-dev-mysql 2>&1 | tail -5
# 期望最后一行：[System] [MY-010931] [Server] /usr/sbin/mysqld: ready for connections
```

### 0.1.x 重置数据（不需重置就跳过）

```bash
cd code/main/RuoYi-Vue-Plus
docker compose -f script/docker/dev-compose.yml down -v
# -v 会删 named volume sensenran-dev-mysql-data / -redis-data / -minio-data 三个，所有数据清空
# 不带 -v 只是停容器，volume 数据保留下次启动还在
```

### 0.1.y http_proxy 注意（如果 Kevin shell 配了代理）

AI 自测时发现 Kevin 当前 shell 有 `http_proxy=http://127.0.0.1:1081`（Clash 等代理工具），导致 `curl localhost:9000` 走代理失败。如果 Kevin 测 MinIO 健康 / 后端端口时返回 `000` 或 `Empty reply from server`：

```bash
# 解法 1：curl 显式 noproxy
curl --noproxy localhost,127.0.0.1 http://localhost:9000/minio/health/live

# 解法 2：当前 shell 临时 unset
unset http_proxy https_proxy

# 解法 3（推荐）：~/.zshrc 配 no_proxy 永久排除本地
export no_proxy="localhost,127.0.0.1,*.local"
```

curl 6 个后端 hello 端点同理。

### 0.2 三端启动

- 后端跑起来：`cd code/main/RuoYi-Vue-Plus && mvn spring-boot:run -pl ruoyi-admin -P dev`
  - 等到日志出现 `Started DromaraApplication`（约 30s-60s）
  - 如果挂在 datasource 初始化 → 回去看 §0.1 docker 是否起来
- Admin 跑起来：`cd code/main/plus-ui && pnpm dev` → 浏览器 http://localhost:80
- 小程序跑起来：`cd code/main/miniapp && pnpm dev:mp-weixin` → 微信开发者工具自动打开（或手动 import `dist/dev/mp-weixin`）

---

## 1. 今日 ticket 验收清单

### GZ-SYS-001 — 项目脚手架与云服务初始化

**关联 mockup**：—（基础设施 ticket，无 mockup）

**关联 AC**（从 `tickets/GZ-SYS-001.md` 复制 — 只列 AC 1 本次范围；AC 2 / AC 3 非本次验收）：

- [ ] AC 1.1：后端 6 个 ruoyi-gz-\* 模块 + 6 个 HelloController 存在且能跑 — **AI 已在 reports §1 + §2 贴 raw output，Kevin 这里复跑确认本地环境一致**
- [ ] AC 1.2 / 1.3：父 pom + ruoyi-admin/pom 接入 6 模块 — **AI 已贴 git diff stat，Kevin 看 `git diff ruoyi-modules/pom.xml ruoyi-admin/pom.xml` 一眼**
- [ ] AC 1.4-1.6：Admin 7 业务域目录 + 7 api stub + i18n — **AI 已贴 pnpm build:prod 397 chunks，Kevin 浏览器进 admin 看（gz-\* 业务菜单未接 sys_menu，预期看不到，只看 ruoyi 自带菜单能否登录进入）**
- [ ] AC 1.7 / 1.8：miniapp unibest 4.4.0 + 7 占位页 + 业务命名 — **AI 已贴 dev:mp-weixin DONE，Kevin 用微信开发者工具点 7 个占位页确认能看到**
- [ ] AC 1.9：三端能编译 / 启动 — **环境复跑确认（见下面测试动作）**

> AC 2.1-2.7（Kevin 自推进部分：阿里云 ICP/OSS/ECS/RDS/Redis 购买 + 微信小程序账号申请）：**非本次 testing-human 验收范围**。Kevin 当日 D01 同步推进，进度跟踪在 `doc/daily/README.md §当日特殊约束` 或 D02 README。
> AC 3.1 / 3.2（等甲方：微信支付证书 + 小程序 AppID）：**非本次验收范围**，不阻塞 D01 close。

**测试动作**（共 4 项，全部是 AI 干不了 / Kevin 复跑 + 视觉感官）：

#### 动作 1：环境复跑后端 + curl 6 个 hello 端点

> 目的：确认 AI 不是"特殊环境"才跑通；同时验证 6 个业务模块 hello world 真能联通（AI 自己本地 MySQL 密码不对没跑到这步）。

1. 浏览器 / 终端到 §0.1 docker 起 MySQL + Redis 后
2. 跑 `mvn spring-boot:run -pl ruoyi-admin -P dev`，等 `Started DromaraApplication`
3. 用 curl / Postman / IDEA HTTP client 跑 6 个端点：
   - `GET http://localhost:8080/gz/common/hello` → 期望 `{"code":200,"data":{"msg":"gz-common ok"},...}`
   - 同样测 `/gz/{bean,user,news,ord,gacha}/hello`
4. **判定**：6 个端点都返回 200 + 对应 msg → AC 1.1 / 1.2 / 1.3 ✅

#### 动作 2：浏览器进 Admin 确认 build + 登录入口

> 目的：确认 plus-ui 在 Kevin 本地能跑（不只是 build:prod 静态产物，还要 dev server）。

1. `cd code/main/plus-ui && pnpm dev` → 浏览器 http://localhost:80
2. 用 admin / admin123 登录（ruoyi 默认账号；DB 是 docker MySQL 导入 ry_vue_5.X.sql 的基础数据）
3. 进入后台首页 → 能看到 ruoyi 自带菜单（系统管理 / 监控 / 工具 / 工作流 / 演示）
4. **预期看不到 gz-\* 业务菜单**（D01 未接 sys_menu，留给 GZ-ADMIN-MENU 后续 ticket）
5. **判定**：能登录 + 能看到 ruoyi 自带菜单 → AC 1.4-1.6 ✅

#### 动作 3：微信开发者工具看 7 个 sensenran 占位页

> 目的：唯一能验证 miniapp 真出活的方式（AI 只能查 dist 文件存在性）。

1. 微信开发者工具应该已被 `pnpm dev:mp-weixin` 自动唤起；如果没有，手动 import `code/main/miniapp/dist/dev/mp-weixin`
2. 默认进入 `pages/index/index` —— 应该看到"谷子宇宙 — 首页"标题 + 粉色 navbar（`#FF6B81`）+ 4 条后续 ticket 提示
3. **tabbar 暂禁用**（D01 用 `NO_TABBAR` 策略），所以底部没有切 tab 入口。手动改 url 切其他 6 页验证：
   - `pages/login/index` → 谷子宇宙 — 登录
   - `pages/bean/index` → 谷子宇宙 — 拼豆预约
   - `pages/me/index` → 谷子宇宙 — 我的
   - `pages/news/index` → 谷子宇宙 — 资讯
   - `pages/ord/index` → 谷子宇宙 — 预定货品（V1.1）
   - `pages/gacha/index` → 谷子宇宙 — 扭蛋机（V1.1）
4. 每个页面都能看到 hd（粉色顶栏） + body（白色卡片列 + 后续 ticket 提示）
5. **判定**：7 个页面都能展示、文案正确、无白屏 / 无 JS 报错 → AC 1.7 / 1.8 ✅

#### 动作 4：app.json 业务命名复核

> 目的：确认 sensenran 业务字符串没残留 dongjiaoshan / unibest 默认值（除已知 R6）。

1. 打开 `code/main/miniapp/dist/dev/mp-weixin/app.json`
2. 检查 `pages` 数组 7 个 sensenran 路径都在
3. **已知偏差 R6**：`window.navigationBarTitleText: "unibest"` 还没改成"谷子宇宙"，因为 pages.config.ts globalStyle 写死了。这不阻塞 D01 close，留给 D02 GZ-SYS-002 一起改
4. **判定**：除 R6 之外业务命名 clean → 通过

---

## 2. 跨 ticket 联调

D01 只有 1 个 ticket，**无跨 ticket 联调**。

---

## 3. 视觉 / 文案 review（D01 mockup 缺位，主要是 sense 判断）

> D01 脚手架 ticket 没有 design/mockup 对照（基础设施性质），这里只跑 "Kevin 视觉直觉接受度"：

### 3.1 mp 临时视觉

- **navbar 临时色**：占位页用 `#FF6B81`（粉色，倾向谷子文化年轻女性向）—— 你能不能接受？
  - 接受 → 后续 ticket 沿用 / 留给 designer 在 doc/tokens.md 正式定 brand-primary
  - 不接受 → 在本 ticket `§revision` 写"问题 N: navbar 色不对 / 期望：白底深字 / 红字 / xxx"，我会同步改 7 个占位页
- **文案机翻味**：7 个占位页 hd + body 文案纯中文，无 emoji，无 GPT 风 — 应 ✅，但 Kevin 复核一遍
- **间距 / 圆角 / 阴影**：rpx 单位 + 16rpx 圆角 + 微阴影，wot-design-uni 同款，应 ✅

### 3.2 admin 临时视觉

- gz-\*/Hello.vue 7 个占位页都用最简模板（h2 + p + padding 24px），Kevin 进不去因为路由没接 sys_menu —— 这次不做视觉 review，留给 GZ-ADMIN-MENU 后续 ticket

---

## 4. 性能 sense（主观感受）

D01 是脚手架，无业务负载，主要看启动时间：

- 后端 `mvn spring-boot:run` 启动到 `Started DromaraApplication` 时长 ✅ 正常（约 30-60s）/ 异常（> 3 min）
- Admin `pnpm dev` 启动到浏览器秒开 ✅ 正常（约 5-10s）/ 异常
- 小程序 `pnpm dev:mp-weixin` build 时长 ✅ 正常（AI 实测 `ready in 6998ms`）/ 异常
- 6 个 hello 端点响应 < 100ms ✅ 正常 / 异常

---

## 5. R-项 Kevin 决策（D01 特有，因为是首日 + 脚手架风险多）

> reports §风险提示 共 8 项（R1-R8）。其中 R1 / R4 / R7 需要 Kevin 决策处理方式 — **决策结果写到 ticket `§revision` 段 或 D02/README.md，本日完成不阻塞**。

### R1 — docker compose 是否要 sensenran 自己起一份

- **当前**：用 ruoyi 自带 `script/docker/docker-compose.yml`
- **决策项**：是否要让 AI 在 GZ-SYS-002 一起做 sensenran 自己的 `script/docker/dev-compose.yml`（含 mysql + redis + 业务初始 sql script）？
  - 选 A：用 ruoyi 自带的（继续，D02 无新工作）
  - 选 B：起 sensenran 自己的（D02 GZ-SYS-002 一起加 ~30 min）
- **写在哪**：决策后在 D02 README.md 或 D01 GZ-SYS-001 §revision 段记录

### R4 — miniapp 423 untracked commit 拆分

- **当前**：未 commit（按 SOP testing-human 后才 commit）
- **决策项**：
  - 选 A：3 commits（rsync / 清理 / 占位）— 干净易追溯
  - 选 B：1 commit "feat: D01 miniapp scaffolding" — 简单
- **写在哪**：决策后 Kevin 自己在 closing 时执行对应 git 命令

### R7 — App.vue onLaunch 调 `/djs/dict/version` 残留

- **当前**：App.vue 内 `syncDictIfNeeded()` 启动调 djs url → 404 → try-catch 兜底 → 控制台 warn
- **决策项**：
  - 选 A：本 ticket §revision 立刻清掉 App.vue 内 dict 调用 — 5 min
  - 选 B：挪到 GZ-COMMON-DICT 一起做（后续 ticket 会把 dongjiaoshan/djs-common DictController 迁移到 ruoyi-gz-common 改成 /gz/dict/\*） — 自然消化
- **写在哪**：决策后在 D01 GZ-SYS-001 §revision 段（A）或 D02/D03/Dx README.md（B）

---

## 6. 判定

测试动作 1-4 全过 + R-项决策记录到位 → 在 `progress.md` 把 GZ-SYS-001 标 ✅ done。
任一项 NOT OK → 在 `tickets/GZ-SYS-001.md` `§revision` 写"问题 N: 现象 / 期望"，然后跟 AI 说 `@coder 修 D01/GZ-SYS-001 revision`。

---

## 7. ⚠️ Commit 时注意（CI/CD workflows 已就位但 secrets 未配）

D01 实施漏项补全 #2 已落地 6 个 CI/CD workflow，**push staging 会触发自动部署**。但 5 个 GitHub Secrets（`SSH_HOST_*` / `SSH_PRIVATE_KEY_*` / `WECHAT_PRIVATE_KEY`）未配 + 阿里云 ECS 未购，**git push 会 fail**。

**D01 closing 建议**：
- testing-human 全过 → 三端各自 `git add + commit`（**不要 push**）
- 等 Kevin 推进 AC 2（阿里云 ECS / 域名 / ICP / 微信小程序账号）+ 配齐 5 个 secrets 后再首次 push
- 也可以 push 一次让 workflow fail 验证 trigger 走通（无副作用，只是 GitHub Actions 报错告知 secret 缺失）

详见 `progress.md §R9` + `doc/04 v0.3 §5.4.4 secrets 清单`。
