# GZ-SYS-001 — 项目脚手架与云服务初始化

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M1 §微信登录 / 合同 §3 启动费 / 合同 §2.1（三）云服务环境
**关联拆解**: doc/02-需求拆解.md §2.1 GZ-SYS 系统底座 / 第 175 行
**关联 mockup**: — （基础设施，无 mockup）
**关联 ADR**: — （sensenran/doc/_adr/ 初期为空，无相关 ADR）
**依赖**: 无（首要 ticket）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 本 ticket 是脚手架性质，主要参考"代码结构 / 包名规则 / 模块切分 / 公共字段约定"的 doc/04 架构，不涉及具体业务流 / UI / 字段。

- **业务流**：doc/10-业务流权威图.md §3 拼豆（一带而过，仅为后续 GZ-BEAN-* ticket 准备模块占位）
- **字段表**：doc/11-字段权威表.md §1 全局公共字段（脚手架阶段不写实体类，但要确保后续 entity 注解约定满足）
- **UI 索引**：doc/12-UI-权威索引.md §1.1 mp 22 页 / §1.2 admin 业务页（脚手架阶段建空目录，不实际渲染业务页）
- **架构**：doc/04-架构.md v0.2 §1（代码结构）/ §2（后端模块切分）/ §3（Admin 分包）/ §4（小程序分包）/ §5（git 分支策略）

## What

搭建后端 / Admin / 小程序三端工程骨架，达到三端能跑 hello world 的状态；同时启动 Kevin 自推进的云服务采购线 + 等甲方推进的微信账号申请线（**这两线 AI 不参与，本 ticket 只标记状态**）。

## AC（验收标准）

### AC 1 — AI 可干部分（本 ticket 这次做这个）

- [ ] AC 1.1：后端 RuoYi-Vue-Plus 新增 **6 个 ruoyi-gz-\* 业务模块**（common / bean / user / news / ord / gacha），每个模块 pom.xml + 包名 `org.dromara.gz.<域>.{controller,service,mapper,domain,dto}` + 一个 hello world Controller（如 `GET /gz/<域>/hello` 返回 `{"msg":"gz-<域> ok"}`）+ resources/mapper 空目录占位
- [ ] AC 1.2：父 pom（`pom.xml` 和 `ruoyi-modules/pom.xml`）接入 6 个新 module
- [ ] AC 1.3：`ruoyi-admin/pom.xml` dependencies 接入 6 个 ruoyi-gz-\*（按 dongjiaoshan 的 ruoyi-admin/pom.xml 同款做法）
- [ ] AC 1.4：Admin plus-ui 创建 `src/views/gz-{common,bean,user,news,ord,gacha,admin}/` 7 个业务域目录 + 各一个占位页（如 `Hello.vue` 显示 "gz-bean ok"）
- [ ] AC 1.5：Admin 创建 `src/api/gz-*.ts` 7 个 API 调用层 stub（空函数即可）
- [ ] AC 1.6：~~Admin 创建 `src/router/modules/gz.ts` 路由分包~~ **实施期修正**：ruoyi 用"后端菜单表 → 前端动态路由"机制（doc/04 §3.4），前端不应该写死路由分包文件。改为"占位 Hello.vue 文件 + 路由配置等到 GZ-ADMIN-MENU 后续 ticket 在 sys_menu 表插入业务菜单时自动生成"。本 ticket 不创建 router/modules/gz.ts
- [ ] AC 1.7：小程序 miniapp 从 dongjiaoshan/miniapp（unibest 4.4.0 模板）rsync 同款脚手架，业务字 djs → gz / dongjiaoshan → sensenran 重命名，业务页清空成 `src/pages/{login,index,bean,me,news,ord,gacha}/index.vue` 7 个占位
- [ ] AC 1.8：小程序 package.json name 改为 `sensenran-guzi-miniapp`
- [ ] AC 1.9：三端能编译 / 启动：
  - 后端：`mvn -DskipTests=true install` 整套绿
  - 后端：`mvn spring-boot:run -pl ruoyi-admin` 启动后 `curl localhost:8080/gz/bean/hello` 返回 `{"msg":"gz-bean ok"}`
  - Admin：`pnpm install && pnpm build:prod` 绿
  - 小程序：`pnpm install && pnpm dev:mp-weixin` 能产出 `dist/dev/mp-weixin`
- [ ] AC 1.10：本地开发 docker compose 就位 `script/docker/dev-compose.yml`（CLAUDE.md §5 规约），能起 MySQL + Redis + MinIO 三个容器：
  - 容器名 `sensenran-dev-{mysql,redis,minio}`（与 dongjiaoshan 隔离，可共存）
  - 端口偏移已避免与 Kevin 本机已用端口冲突：MySQL 3307:3306 / Redis 6380:6379 / MinIO 9000+9001（本机原 brew mysql 占 3306、redis-local 占 6379）
  - `application-dev.yml` datasource.url + redis.port 同步配到偏移端口
  - 密码与 ruoyi dev profile 对齐（mysql root/root + redis ruoyi123 + minio ruoyi/ruoyi123）

### AC 2 — Kevin 自推进部分（本 ticket 不做，只标）

- [ ] AC 2.1：阿里云域名购买 + ICP 备案启动（**甲方主体** — 李茂森提供营业执照、法人身份证）
- [ ] AC 2.2：阿里云 OSS bucket 创建（建议 bucket name：`sensenran-guzi-{env}`，region：成都/华东，公共读私有写）
- [ ] AC 2.3：阿里云 ECS 服务器购买（V1.0 配置：2C4G + 4M 带宽 + 50G SSD；V1.1 视需求扩容）
- [ ] AC 2.4：阿里云 RDS MySQL 8.0 创建（V1.0 配置：1C2G + 20G；可暂用 ECS 上自建 MySQL Docker 节约成本）
- [ ] AC 2.5：阿里云 Redis 创建（V1.0 配置：1G 内存；同上可自建）
- [ ] AC 2.6：微信小程序账号申请提交（**甲方主体** — 提交《公众平台服务协议》+ 法人身份认证）
- [ ] AC 2.7：微信公众平台开通"客服消息"能力 + 配置企业微信账号（用于 GZ-SYS-004 客服入口）

### AC 3 — 等甲方部分（本 ticket 不做，本 ticket 阻塞不到这里）

- [ ] AC 3.1：微信支付 V3 商户号证书（**甲方申请 + 提供** — apiclient_cert.pem / apiclient_key.pem / API V3 密钥）
  - 备注：合同 §2.3 已明确商户号挂甲方公司主体（避免二清违规）。V1.0 仅通道调通（拿 prepay_id），不接业务订单（合同 §2.1 V1.0 范围）
- [ ] AC 3.2：微信小程序 AppID + AppSecret（**甲方申请通过后提供**）

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-{common,bean,user,news,ord,gacha}/`
  - 6 个 Maven 子模块
  - 每模块只有 pom.xml + 一个 HelloController + 一个 application 占位
  - **本 ticket 不写 DDL**（DDL 是后续业务 ticket 工作）
- **Admin**：`code/main/plus-ui/src/views/gz-{common,bean,user,news,ord,gacha,admin}/` + `src/api/` + `src/router/modules/gz.ts`
- **小程序**：`code/main/miniapp/`（unibest 4.4.0 同款，rsync from dongjiaoshan，清残留 + 改名 + 替换业务页占位）
- **测试**：本 ticket 不写业务单测（脚手架 hello world 不需要）

## 备注

### 强约束（CLAUDE.md §6 + §10）

1. **不动 ruoyi 自带模块源码** — `ruoyi-admin` / `ruoyi-common-*` / `ruoyi-modules/ruoyi-{system,generator,job,workflow,demo,resource}` 全部不动
2. **业务包名严格 `org.dromara.gz.<域>.*`**（区分 `org.dromara.system` 等 ruoyi 自带）
3. **表前缀 `gz_<域>_<表>`** — 本 ticket 不写 SQL，但 entity 注解约定要符合（@TableName 用 gz\_ 前缀）
4. **不引未澄清新依赖** — 6 个新模块用 dongjiaoshan djs-common 同款基础 deps（ruoyi-common-core / -doc / -mybatis / -tenant / -translation / -log / -security / -web / -idempotent / -sensitive / -encrypt / -redis / -json），不冒加（如 oss / excel 等业务依赖等到具体 ticket 时加）
5. **不写 SQL DDL**（脚手架阶段）
6. **i18n**：plus-ui 业务页占位字符串走 `t('gzHello.xxx')` + `zh-CN.ts`（即使是 Hello 也走 i18n，养成习惯）
7. **不动 dongjiaoshan 任何文件**（只读 + rsync 复制）
8. **DDL 文件命名规范留好**：`ruoyi-admin/src/main/resources/db/migration/V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`（本 ticket 不创建文件，但确认目录结构 OK）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 6 个 ruoyi-gz-\* 模块一次性建（含 ord / gacha） | doc/04 v0.2 §2.1 已明确；先建模块但保持 hello world 状态，到 V1.1 ticket 时再填业务，避免后续改 root pom 反复挪动 |
| D2 | ruoyi-gz-common 暂只引基础 deps，不抄 dongjiaoshan/djs-common 业务代码 | djs-common 已含 wechat / oss-sts / encoder 等多服务，那是后续 GZ-SYS-002 / GZ-PAY-001 等 ticket 各自负责迁移的工作。本 ticket 保持脚手架最小 |
| D3 | miniapp 用 unibest 4.4.0 模板（dongjiaoshan 同款） | doc/04 v0.2 §4.1 已记 unibest 候选；既然 dongjiaoshan 已跑通 + Kevin 熟悉，直接复用 |
| D4 | 小程序业务页全部新建占位（不沿用 dongjiaoshan 的 breed/plant/store/warehouse） | dongjiaoshan 业务页（养殖/种植/仓储）与 sensenran（拼豆/扭蛋/资讯）业务完全不同，沿用反而误导 |
| D5 | `application-prod.yml` 占位云配置不连真实云 | Kevin 当日裁定 C1（阿里云）+ C3（阿里云购买执行中），真实凭证等 AC 2 完成 |
| D6 | hello world Controller 加 @Anonymous 或路由跳过鉴权 | sa-token 默认拦截所有路由，hello world 不接 token 否则 401 影响验证 |

### 合同 / 商业层关联

- 合同 §3：启动费 ¥3000 覆盖云服务采购 + 域名 ICP 备案 + 小程序账号（AC 2 全部由 Kevin 用启动费推进）
- 合同 §2.1（三）：云服务环境就绪是 V1.0 开发的前置条件
- 合同 §2.2：V1.0 6/15 硬期限 — 本 ticket 在 D01（5/27）完成不影响

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | JDK 20 与 ruoyi 5.6.1 父 pom source/release=17 不兼容 | 先试编译；若不通过 STOP 报 Kevin（不自行切 jdk） |
| R2 | dongjiaoshan miniapp rsync 后业务残留清不干净 | 实施时按"清单 + grep"双重清理（清单删目录 / grep 删字符串） |
| R3 | unibest 4.4.0 与 sensenran 业务实际不兼容 | D01 仅验证 hello world，深度兼容性留给 D02+（GZ-SYS-002 微信登录时验证） |
| R4 | ruoyi-gz-ord / ruoyi-gz-gacha V1.1 才用，但 D01 就建会拖累 ruoyi-admin 启动时间 | 接受 — doc/04 v0.2 §2.1 已明确，且 hello world 无业务实际负载 |

---

## §实施漏项补全（2026-05-27）

- 漏：CLAUDE.md §5 规定 `script/docker/dev-compose.yml`，初版 D01 GZ-SYS-001 实施漏建（Kevin 反馈"本地需要启动的内容太多"时识别）
- 补：本次补齐，基于 dongjiaoshan `docker-compose-dev.yml` 模板 + sensenran 命名/端口隔离
  - 容器名 `sensenran-dev-{mysql,redis,minio}` 与 dongjiaoshan 隔离
  - 端口冲突自检后强制偏移：MySQL `3307:3306`（本机 brew mysql 占 3306）/ Redis `6380:6379`（本机 redis-local 占 6379）/ MinIO `9000+9001`（空闲，保持）
  - `application-dev.yml` datasource.url 端口 3306 → 3307 + redis.port 6379 → 6380 同步
  - 顺手把 datasource.url `useSSL=true` 改为 `useSSL=false`（docker mysql 自签证书，false 更干净）
- 影响：
  - 加 AC 1.10
  - `testing-human.md §0` 命令改用 sensenran 自己的 `dev-compose.yml`（删原 ruoyi 自带 `docker-compose.yml` 指引）
  - `reports/GZ-SYS-001.md §AI 自测` 追加自测 5（docker 三容器健康 + curl noproxy 提醒）
  - `progress.md §阻塞` 把 R1（MySQL/Redis 凭证不一致）标为已解决
- 不影响：reports 之前 4 项自测 / mvn install / pnpm build / mp dev 全部仍 valid

---

## §实施漏项补全 #2（2026-05-27）

- 漏：CI/CD workflows + 部署 compose 初版未建。Kevin 反馈"完全参考 dongjiaoshan 的配置实现三端 staging 分支自动部署"时识别。doc/04 v0.2 §5.4 已描述但未落地代码
- 补：本次 1:1 映射 dongjiaoshan，三端 staging/prod workflow 全就位
  - 新建 6 文件：后端 `.github/workflows/deploy-{staging,prod}.yml` + `script/docker/docker-compose.deploy.yml` / plus-ui `.github/workflows/deploy-{staging,prod}.yml` / miniapp `.github/workflows/upload-mp-staging.yml`（覆盖 D01 rsync 的 stale 版本）
  - 删除 3 个 dongjiaoshan 同源但 sensenran 不需要的 workflow：`auto-merge-to-aliyun.yml`（aliyun gitee mirror，sensenran github 单源）/ `auto-merge.yml.disabled`（unibest 多语言分支同步）/ `deploy.yml`（VitePress 文档站点部署）
  - 业务字替换：`dongjiaoshan` → `sensenran-guzi`（域名 + 路径）/ `djs` → `gz`（container_name + image）
  - diff dongjiaoshan：仅 9 行差异（全部业务字），其他 1:1
  - yml 语法验证：ruby YAML.load_file 6 文件全 ✅
- 加 AC 1.11
- 影响：
  - doc/04-架构.md v0.2 → v0.3（§5.4 / §5.6 / §11 Q2 / Changelog 更新）
  - `reports/GZ-SYS-001.md §AI 自测` 追加自测 6（CI/CD diff 验证 + secrets 清单）
  - `progress.md §阻塞` 加 R8（GitHub Secrets 待 Kevin 在 3 repo Settings 配齐）

## §AC 1.11

- [ ] AC 1.11：三端 CI/CD workflows 就位（6 文件 1:1 映射 dongjiaoshan，业务字隔离）+ docker-compose.deploy.yml 就位 + sensenran 不需要的 3 个 dongjiaoshan 同源 workflow 已删

---

## §实施漏项补全 #3（2026-05-27）

- 漏：环境文件不完整 + 上下游配套未自查。Kevin 反馈"小程序 dongjiaoshan 环境变量分成 3 个，你这里却只有 1 个，其他端请自行检查"时识别。深查后发现影响范围超出 miniapp，跨 3 端：
  - **miniapp**：缺 `.env.development` + `.env.staging`（**这是阻塞项** — upload-mp-staging.yml 第 49-66 行强制校验 `.env.staging` 存在，无此文件 CI 立即 fail）
  - **miniapp**：缺 `build:mp:staging` script + 旧版 `scripts/upload-weixin.js` 不支持 `--mode=staging` 参数（CI workflow 第 89 行 `pnpm upload:mp --mode=staging` 会因脚本不识别参数而退回 `build:mp:prod` 模式失败）
  - **miniapp**：原 `.env` 含 mode-specific 字段（VITE_SERVER_BASEURL 应在 .env.development 不在 .env），结构错位
  - **plus-ui**：`.env.development` + `.env.production` 仍是 ruoyi 原版默认 `VITE_APP_TITLE = RuoYi-Vue-Plus多租户管理系统`，未 sensenran 化（甲方登录看到不专业）
  - **后端 application-prod.yml**：硬编码 `localhost:3306/ry-vue` + `password: root` + `boot.admin.enabled: true` + `snail-job.enabled: true`，生产环境如不改会启动失败（boot admin 找不到 9090）
- 补：本次跨 3 端 8 文件补齐
  - **miniapp 3 个 env 文件重组**：新建 `.env.development`（VITE_SERVER_BASEURL=127.0.0.1 + VITE_WX_APPID=wxMOCK 短路）+ 新建 `.env.staging`（VITE_SERVER_BASEURL=占位 https://api.sensenran-guzi.com + VITE_WX_APPID=TBD_BY_KEVIN_WX_APPID 占位）+ 重写 `.env`（只保留 mode 共享字段：VITE_APP_TITLE / VITE_UNI_APPID / VITE_APP_CLIENT_ID / VITE_APP_TENANT_ID 等）
  - **miniapp package.json**：加 `"build:mp:staging": "uni build -p mp-weixin --mode staging"` script
  - **miniapp scripts/upload-weixin.js**：用 dongjiaoshan 最新版覆盖（支持 `--mode=<env>` 参数 + 按 mode 加载 .env.<mode> + 按 mode 调 build:mp:<mode> + wxMOCK 前缀防误用校验）
  - **plus-ui 2 个 env 文件**：改 `VITE_APP_TITLE = 谷子宇宙数字化系统` + `VITE_APP_LOGO_TITLE = 谷子宇宙`
  - **application-prod.yml**：沿用 dongjiaoshan `${ENV:default}` 占位符模式 — boot admin 默认 false / snail-job 默认 false / master.url 走 MASTER_DB_URL / master.username 走 MASTER_DB_USERNAME / master.password 走 MASTER_DB_PASSWORD / redis 5 字段走 REDIS_HOST/PORT/DATABASE/PASSWORD/SSL_ENABLED
- 加 AC 1.12 / 1.13
- 影响：
  - doc/04-架构.md v0.3 → v0.4（§5.4 / 附录 A 加 environment files 清单 / Changelog 更新）
  - `reports/GZ-SYS-001.md §AI 自测` 追加自测 7（全量 diff + grep 残留 / 上下游 audit 链路完整性验证）
  - `progress.md §阻塞` 加 R10（环境文件 placeholder 待 Kevin 填实际值清单）
- 不影响：之前 §自测 1-6 全部仍 valid

## §AC 1.12

- [ ] AC 1.12：环境文件链路完整（miniapp 3 文件 / plus-ui 2 文件 / 后端 application-prod 走 env var 占位符），grep dongjiaoshan|djs|东角山 全 0 命中

## §AC 1.13

- [ ] AC 1.13：miniapp CI 工具链完整（package.json `build:mp:staging` script + scripts/upload-weixin.js 支持 `--mode=staging` 参数 + wxMOCK 校验），与 upload-mp-staging.yml workflow 调用契约一致

---

## §revision（Kevin testing-human 后填，初始空）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D01/GZ-SYS-001 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
