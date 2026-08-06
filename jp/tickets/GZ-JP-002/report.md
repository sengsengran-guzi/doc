# GZ-JP-002 完工报告 — 新小程序登录打通 + E2E harness

**结论：accept #1（后端 wx-login）PASS；accept #2（`run.mjs smoke`）卡在本机 devtools 环境 —— IDE 登录过期需人扫码，非代码问题。**

已把根因**精确定位并落成 preflight 阻塞项**：preflight 7 项里 **6 项全绿，唯一红的是 `devtools-login`**。
harness 与 flow 代码本身用零环境依赖的 `self-test.mjs` 证明可用（7/7 通过，含 4 个 negative 用例）。

---

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 后端已起且健康 | ⚠️→✅ 起手时 8080 **没在跑**（curl exit 7），本会话自行 `mvn spring-boot:run -pl ruoyi-admin` 拉起（见「残留进程」） |
| GZ-SYS-020/023 已 merge | ✅ RuoYi-Vue-Plus `staging` @ `82af7f60f`「D1: 后端多 appid 底座」，工作区 clean |
| `~/.m2` 的 gz-common jar 是当前码 | ✅ jar mtime `Aug 6 23:20` > commit `23:16` → **无需 clean install**（本卡也没改后端） |
| clientid 已登记 | ✅ `application-dev.yml` `wx.miniapp.apps` 含 `mp-applet-gz-jp`（`mock-stable-openid: jp-tester` / `register-source: mp_wechat_jp`） |
| devtools cli 存在 | ✅ `/Applications/wechatwebdevtools.app/Contents/MacOS/cli` |
| devtools 服务端口 | ✅ **本次是开的**（`127.0.0.1:26863` 有响应）—— 与上一轮 D1 的报错原因**不同**，见「环境阻塞」 |
| devtools 登录态 | ❌ `cli islogin` → `{"login":false}` ← **唯一阻塞项** |
| dist 是当前代码产物 | ✅ 本卡重建（`--mode development`），dev profile 指纹齐全 |
| miniapp-jp 工作区 | ✅ 起手 clean @ `637d7d6`（GZ-JP-001） |
| 兄弟仓未污染 | ✅ miniapp `59635d4` / RuoYi-Vue-Plus `82af7f60f` / plus-ui `eb1d47a`，均 0 改动 |

**蓝图关键约束摘录**
- `FLOW:F-JP-00.step1`：请求带 `clientid`，本小程序恒为 `mp-applet-gz-jp`；纯字符串比对不查 `sys_client`
  → 写错直接报「未配置的小程序客户端」。**已实测护栏生效**（见自测 §2）。
- `FLOW:F-JP-00.step3`：同一自然人在两个小程序下各自独立 `gz_user` 行。**已用真 DB 唯一键正反探针背书**（自测 §3）。

---

## 实现摘要

```
 M eslint.config.mjs
 A test/e2e/README.md            并发约束 + 环境坑 + 加 flow 指南
 A test/e2e/run.mjs              入口：flow 注册表 / 退出码语义 / 硬超时 / 产物自愈
 A test/e2e/preflight.mjs        硬 gate 体检 7 项
 A test/e2e/mp-e2e.mjs           automator 驱动 + 登录态治具
 A test/e2e/build-dist.mjs       dev profile 产物构建
 A test/e2e/flows/smoke.mjs      6 页可达 + 渲染
 A test/e2e/flows/login.mjs      登录全链路 + 合规闸门
 A test/e2e/self-test.mjs        ★ 零环境依赖的 flow 逻辑体检
 A test/e2e/package.json / package-lock.json
11 files changed
```

**commit**：miniapp-jp 本地仓 `fccd504`「feat: mp E2E harness + 登录链路验证 (GZ-JP-002)」，工作区 clean。
**未向** doc / RuoYi-Vue-Plus / plus-ui / miniapp 任何仓提交（本报告文件也未 commit）。

### 1. 登录链路（没写新代码 —— 验证既有链路）

GZ-JP-001 已把 `useAuth` / `store/token` / `http/interceptor` 原样带过来，本卡**一行业务代码没改**，
职责是**证明它通**：请求头 `clientid: mp-applet-gz-jp`（`interceptor.ts` 注入，值取自 `.env`）→
后端 `WxAdapterDispatcher` 按 clientid 选中本小程序的 mock 通道 → `WxMockLoginAdapter` 用
`mock-stable-openid` 派生固定 openid `mock-jp-tester` → 发 sa-token。

### 2. E2E harness（从 `code/main/miniapp/test/e2e/` 移植 + 3 处本工程特有加固）

四件套按源 harness 逐行移植（三道已解决的坑注释原样保留：清代理 / checkVersion monkeypatch /
`trustProject: true`）。flows 全部重写。**相对源 harness 的差异都是有理由的**：

| 改动 | 为什么 |
|---|---|
| preflight 增【阻塞】**devtools 登录态**（`cli islogin`） | ★ 本卡最贵的一课，见下节。IDE 登录过期时报错方向完全错，前置探明把半天排查压成一句话 |
| preflight 增【阻塞】**dist 是不是 dev profile** | 本工程 `pnpm build:mp`（无 `--mode`）= production profile，`VITE_SERVER_BASEURL` 指向**线上** `guzi.tianda.studio`。拿它跑本地 E2E 会**静默打到线上后端**——不报错、断言却漂，最贵的一类假绿 |
| preflight 增【阻塞】**后端认不认 jp clientid** | 否则 GZ-SYS-020 没部署时每条 flow 都以「登录失败」形态挂，看不出根因在后端配置 |
| `run.mjs` 产物自愈 | accept 命令是**裸** `node test/e2e/run.mjs smoke`（不带 `--build`）。产物缺失或 profile 不对 → 自动补一次 dev 构建（`--no-auto-build` 可关） |
| build-dist **默认不 pkill 微信开发者工具** | 源 harness 为冷启动会杀 IDE。这台机器上 IDE 通常是 Kevin 本人开着的（且登录态只能人扫码恢复），杀掉等于抢工位。需冷启动时 `MP_E2E_KILL_DEVTOOLS=1` |
| 截图落 `/tmp/gz-jp-e2e-shots/` | 与现有小程序 `/tmp/gz-e2e-shots/` 分开，两套不互相覆盖 |
| 新增 `self-test.mjs` | 见下节 |

**eslint**：`test/e2e/**` 加进 ignores（独立 node 包、非 app 源码、不在 tsconfig 里；且风格需与兄弟工程
`miniapp/test/e2e/` 逐行对齐以便长期互相 cherry-pick）。lint 保持 GZ-JP-001 的 **0 problems**。

### 3. flows

- **smoke**：GZ-JP-001 交付的全部 6 页（= `app.json` pages 全集）reLaunch 可达 + 渲染 + 标志元素。
  `pages/agreement/index` 带 `?type=service|privacy` 两种 query 各测一次；`pages/login/index` 已登录态
  会 `switchTab` 回首页 —— 这条已知重定向**显式写进 accept 锁进回归**。
  → 后续 mp 卡加新页只需往 `PAGES` 加一行，这就是「AC X(a) AI 模拟器可达」的落点。
- **login**：走**真实用户路径**（首页 CTA → 协议 sheet → 勾选 → 登录），不走后门注 storage。顺带锁住三条：
  1. **合规**：协议勾选框默认**不勾选**、未勾选时登录按钮 `disabled`（这正是微信审核驳回过的点）
  2. **clientid 没串号**：登录后持久化 `username === 'wx:mock-jp-tester'`（现有小程序是 `wx:mock-dev-tester`）
  3. **「同意一次」**：`gz_privacy_agreed` 落地（下次启动才允许 `silentLogin`）

  ⚠️ 前置拨回游客态**不能只 `clearStorageSync`**：pinia 持久化只在 store 创建时 hydrate 一次，清 storage
  清不掉**内存里**的 token → 页面仍是已登录态、首页 CTA 变「个人资料」、flow 等于测了个寂寞。
  所以走 app 自己的登出路径（`me/index` 的 `.logout-btn` + mock `showModal` 恒确认），
  它同时清内存 token / storage / 已同意 flag。这条已封成 `logoutIfLoggedIn()`，后续 flow 直接复用。

---

## AI 自测（raw output）

### 1. accept #1（逐字，纯后端不受 devtools 影响）

```
$ RESP=$(curl -s -X POST http://localhost:8080/app/gz/common/auth/wx-login \
    -H 'Content-Type: application/json' -H 'clientid: mp-applet-gz-jp' \
    -d '{"code":"e2e-jp-login"}'); \
  echo "$RESP" | jq -e '.data.token != null and .data.userId != null' >/dev/null
ACCEPT#1 exit=0
```
```json
{ "code": 200, "msg": "操作成功",
  "data": { "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "expiresIn": 2592000, "userId": "14",
            "openid": "mock-jp-tester", "nickName": "SYS023 回归" } }
```
token 解出的 payload（证明 clientid 真的进了会话，不是「碰巧返回了个 token」）：
```
"loginId":"app_user:14", "clientid":"mp-applet-gz-jp", "tenantId":"1001",
"userId":14, "userName":"wx:mock-jp-tester"
```

> ⚠️ **复跑这条 accept 时注意 shell 代理**（本机 clash：`http_proxy=http://127.0.0.1:1081`）。
> accept 命令逐字写法**没带** `--noproxy '*'`，在设了 `http_proxy` 且 `no_proxy` 不含 localhost 的
> shell 里，curl 会把 `localhost:8080` 送进代理 → `Empty reply from server` → `$RESP` 为空 →
> `jq -e` 退 **4**。这是**本机代理配置**问题，不是后端/代码问题。三组对照：
>
> | shell 环境 | 逐字 accept #1 |
> |---|---|
> | 无 `http_proxy` | `EXIT=0` ✅ PASS |
> | 有 `http_proxy` + `no_proxy` 含 localhost | `EXIT=0` ✅ PASS |
> | 有 `http_proxy` + `no_proxy` 为空（本 agent 沙箱默认） | `EXIT=4`（curl 空响应；同时刻后端 `health=401` 活着、`java` 在 listen 8080） |
>
> 复跑前 `unset http_proxy https_proxy all_proxy` 或 `export no_proxy=localhost,127.0.0.1` 即可。
> 这条与 memory「dev infra 启动配方 —— http_proxy 坑（curl 加 --noproxy '*'）」是同一个坑。

### 2. 两个小程序互不干扰 + clientid 护栏（对照组）

```
$ curl -s ... -H 'clientid: mp-applet-sensenran-guzi' -d '{"code":"e2e-guzi-login"}'
{ "userId": "13", "openid": "mock-dev-tester" }          # 现有小程序 → 另一个人

$ curl -s ... -H 'clientid: mp-applet-not-exist'  -d '{"code":"e2e-bad"}'
{ "code":500, "msg":"未配置的小程序客户端 clientid=mp-applet-not-exist，请在 wx.miniapp.apps
  中登记（已配置：[mp-applet-sensenran-guzi, mp-applet-gz-jp]）" }   # 护栏：不静默串号
```

### 3. AC「gz_user 落独立一行」——真 DB 正反探针

```
mysql> SELECT id, app_id, openid, register_source, tenant_id FROM gz_user
       WHERE openid='mock-jp-tester' ORDER BY id;
+----+---------------------+----------------+------------------+-----------+
| id | app_id              | openid         | register_source  | tenant_id |
+----+---------------------+----------------+------------------+-----------+
| 12 | wx2f8b93e09703f07d  | mock-jp-tester | mp_wechat        | 1001      |
| 14 | wxMOCK              | mock-jp-tester | mp_wechat_jp     | 1001      |
+----+---------------------+----------------+------------------+-----------+
↑ 同一 openid、不同 app_id → 两行独立并存（正是 AC 要的「互不干扰」）

mysql> SHOW INDEX FROM gz_user WHERE Non_unique=0;   -- 唯一键定义
uk_tenant_app_openid = (tenant_id, app_id, openid)   -- 3 列

-- 负向探针（事务内，已 ROLLBACK）：同 (tenant, app_id, openid) 再插一行
ERROR 1062 (23000): Duplicate entry '1001-wxMOCK-mock-jp-tester'
                    for key 'gz_user.uk_tenant_app_openid'        <- 唯一键生效

-- 正向探针（事务内，已 ROLLBACK）：同 openid 换 app_id
+---------------+
| inserted_rows |
+---------------+
|             1 |            <- 换 app_id 即可共存 = 真 appid 到位后自动分家
+---------------+
```

> dev 期两个小程序的 `appid` 都是占位 `wxMOCK`，所以 `app_id` 列此刻**分不出来源** ——
> 这是 GZ-SYS-020 yml 注释里写明的已知状态，靠 `mock-stable-openid`（openid 不同）与
> `register_source`（`mp_wechat` vs `mp_wechat_jp`）区分。唯一键是 3 列的，
> 真 appid 回补后 `app_id` 维度自动生效，无需改表。

### 4. accept #2（逐字）—— preflight 6/7 绿，卡 devtools 登录

```
$ cd code/main/miniapp-jp && node test/e2e/run.mjs smoke
[preflight] 硬 gate 体检（无降级）
  ✓ devtools cli: /Applications/wechatwebdevtools.app/Contents/MacOS/cli
  ✓ devtools 服务端口开着 (http://127.0.0.1:26863)
  ✗ devtools 未登录（cli islogin → {"login":false}）—— 模拟器 runtime 起不来，表象会是
    launch 报「http port is open」或每条命令 10s 超时，都不是代码问题
    -> 修复：打开微信开发者工具 -> 用手机微信扫码登录（本机一次性人工动作，脚本代不了），然后重跑
  ✓ dist 完整: .../dist/build/mp-weixin/app.json
  ✓ dist = dev profile（本地后端 + wxMOCK + jp clientid）
  ✓ 后端可达: http://localhost:8080 (HTTP 401)
  ✓ 后端认 clientid=mp-applet-gz-jp（openid=mock-jp-tester）
[preflight] ❌ 阻塞（devtools-login）—— 硬 gate 无降级，修好上面再跑
EXIT=2                       # 2 = preflight 阻塞，符合退出码语义
```

### 5. flow 逻辑体检（零环境依赖，证明「代码没问题」）

```
$ node test/e2e/self-test.mjs
  ✓ smoke / 全部页面正常 -> 通过
  ✓ smoke / 首页缺 .jp-hero__cta 标志元素 -> 必须 fail
  ✓ smoke / 某页渲染空壳(view 数不足) -> 必须 fail
  ✓ login / 已登录起步（先登出再重登）-> 通过
  ✓ login / 游客起步 -> 通过
  ✓ login / 协议框默认已勾选（合规回归）-> 必须 fail
  ✓ login / 登成了另一个小程序的用户（串号）-> 必须 fail

[self-test] 7/7 通过
SELFTEST_EXIT=0
```
7 个用例里 **4 个是 negative**（断言必须真的会 red）——只写 happy 的断言常年恒真，等于没写。

### 6. 工程健康（GZ-JP-001 的绿线全部保持）

```
$ pnpm type-check   -> exit=0
$ pnpm lint         -> exit=0      # 仍是 0 problems
$ pnpm test         -> exit=0      # Test Files 6 passed, Tests 43 passed (43)
$ node test/e2e/self-test.mjs -> exit=0
```

---

## ⚠️ 环境阻塞（如实上报，未绕过）

**症状**：`node test/e2e/run.mjs smoke` 起初 launch 成功，但**每条** App 层命令 10s 超时
（`timeout waiting for automator response`）—— 看着像小程序代码崩了。

**真因**：微信开发者工具 **IDE 登录已过期**。挖到 cli 的 stderr 才看得见：

```
$ cli islogin
{"login":false}

$ cli auto --project <dist> --auto-port 9422
[error] { message: 'Error: 错误 Error: 需要重新登录 (code 10)Error: 需要重新登录 ...' }
```

**与上一轮 D1 的差别**（重要，别沿用旧结论）：上轮报的是「服务端口没开」。
**本轮服务端口是开的**（`127.0.0.1:26863` 有响应，preflight 第 2 项 ✓），换成了登录过期。
两者报错文案会互相冒充，所以我把两条都做进了 preflight。

**为什么表象这么误导**（已写进 `preflight.mjs` / README 注释）：

| 工程 appid | `cli auto` | automator 表现 | 误导方向 |
|---|---|---|---|
| 真 appid（如现有 miniapp） | **失败** | `Failed to launch wechat web devTools, please make sure http port is open` | 让你去查服务端口，但端口开着 |
| `touristappid`（本工程一期占位被自动切成它） | **成功** | ws 端口起来、`connect()` 秒连，之后每条命令 10s 超时 | 让你去查小程序代码，但代码是好的 |

**控制实验**（证明与本卡代码无关）：拿**现有小程序**（`code/main/miniapp`，成熟 harness + 成熟工程）
走完全相同路径，同样失败：

```
$ cd code/main/miniapp && node test/e2e/run.mjs smoke
[preflight] ✓ 通过
[run] launch/run 异常: Failed to launch wechat web devTools, please make sure http port is open
```

**处置**（严格按「不绕过」）：
- ❌ 没有 kill / 重启 Kevin 正在用的 IDE 进程（还顺手把 build-dist 里源 harness 的 `pkill wechatwebdevtools` 改成了默认不杀）
- ❌ 没有注释 preflight、没有假装通过、没有降级
- ✅ 反过来把它做成 **preflight 阻塞项 + 精确修复指引**，并在 `run.mjs` 的 launch catch 里对
  "http port is open" 这句误导性报错补了指向真因的提示
- ✅ 用等效手段覆盖同一份契约面：后端 curl（自测 §1/§2）+ 真 DB（§3）+ flow 逻辑 self-test（§5）

**解除条件**：Kevin 打开微信开发者工具用手机微信扫码登录 -> 重跑
`cd code/main/miniapp-jp && node test/e2e/run.mjs all` 即可（无需改任何代码）。预计 30 秒。

---

## 风险提示 / 已知 issue

1. **accept #2 未真跑通** —— 6 页可达性、登录 flow 的**真实模拟器**执行尚未发生。self-test 只证明
   flow 逻辑自洽（选择器名字若与真实渲染结构不符，self-test 照不出来）。**IDE 登录恢复后必须补跑一次**，
   这是本卡唯一的实质残留。
2. **选择器依赖**：flows 用了 `.jp-hero__cta` / `.me-header__top` / `.logout-btn` / `.login-sheet` /
   `.login-agree__box`(`.is-on`) / `.login-sheet__cta`。这些都是 GZ-JP-001 页面里的真实 class，
   但 **scoped scss 不会改 class 名、`virtualHost` 组件的宿主 class 会被吞** —— 首次真跑时若
   `.login-sheet` 类选择器查不到（BizLoginSheet 挂在 BizScreen 内），可能要退到子节点选择器。
   已在 flow 里给出明确报错文案，不会静默通过。
3. **登录态跨 flow 传染**：`all` 顺序是 smoke -> login。smoke 只 reLaunch 不改登录态，但 login 跑完
   会留下已登录态 -> 下次 smoke 的 `pages/login/index` 会重定向到首页（已进 accept 列表，不算 fail）。
4. **后端 8080 是本会话拉起的**（见「残留进程」）。
5. **`gz_user` 里有 GZ-SYS-023 遗留的过渡行**（id=12：`app_id=wx2f8b93e09703f07d` + `openid=mock-jp-tester`），
   是 D1 回归测试的产物、不是本卡造的。它恰好成了「同 openid 不同 app_id 可共存」的活证据，暂不清理；
   真 appid 回补时建议一并核对这批 dev 数据。
6. **accept #1 对 shell 代理敏感**：逐字命令没带 `--noproxy '*'`，在带 `http_proxy` 且 `no_proxy`
   不含 localhost 的 shell 里会以 `jq` 退 4 的形态假 FAIL（见自测 §1 的对照表）。若要让这条命令
   在任何 shell 都稳，可在任务卡 accept 里给 curl 补 `--noproxy '*'`；本卡未擅自改任务卡。
7. **`dist/build/mp-weixin/project.config.json` 的 appid 会被 harness 改写成 `touristappid`**
   （占位 appid 非法，devtools 打不开工程）。dist 已 gitignore，无副作用；appid 回补后此逻辑自动不触发。

## 残留进程（需要 Kevin 处置）

本会话**自行拉起了后端**（起手时 8080 没在跑，否则 accept #1 无法执行），**且刻意保留运行**，
以便主线程/Kevin 复跑 accept：

```bash
# 后端 mvn spring-boot:run -pl ruoyi-admin（日志 /tmp/gzjp-backend.log）
lsof -ti:8080 | xargs kill        # 不需要时收掉
```

docker 的 MySQL/Redis/MinIO 是原本就在跑的，未动。
另：本会话通过 `cli auto` 在 devtools 里开过 jp 工程（automation 端口 9420/9421/9422），
IDE 未登录所以无实际效果，重启 IDE 即清。

## 对下游 ticket 的提示

**所有后续 mp 卡（GZ-JP-101/102/103/201/202/205 …）通用**：

1. **新页只是要可达性** -> 不用新开 flow，往 `test/e2e/flows/smoke.mjs` 的 `PAGES` 加一行即可：
   ```js
   { path: '/pages/xxx/index', accept: ['pages/xxx/index'], must: '.xxx-标志元素' }
   ```
   这就是任务卡「AC X(a) AI 模拟器可达」的落点。`must` 建议填一个该页独有的语义 class，
   光靠 view 数会把「渲染成空壳」放过去。
2. **有交互 / 有状态的流程** -> 新建 `flows/<name>.mjs` 导出 `async run(mp)`，在 `run.mjs` 的
   `FLOWS` 注册表加一行，**并在 `self-test.mjs` 补 1 个 happy + >=1 个 negative 场景**。
3. **需要登录态**：直接用 `mp-e2e.mjs` 的治具 —— `logoutIfLoggedIn(mp)`（确定性拨回游客态）/
   `readPersistedUser(mp)`（读 `wx:<openid>` 验没串号）/ `hasAgreedPrivacy(mp)`。
   **别自己写 `clearStorageSync` 当登出用**（清不掉内存里的 pinia token，见「实现摘要 §3」）。
4. **别用 `pnpm build:mp` 产 E2E 产物**（production profile -> 打线上后端）。裸跑 `run.mjs` 会自动
   建 dev profile 产物；手动重建用 `--build development`。
5. **并发**：devtools 自动化端口共享单例。两个小程序的 E2E **必须互相串行**，
   主线程统一派**一个** kevin-qa 把整批串着跑完，别一卡一个。已写进 `test/e2e/README.md`。
6. **环境不通先看 preflight 那 7 行**，尤其 `devtools 未登录` —— 它的原生报错会把你带去查服务端口或查小程序代码。

**GZ-JP-201（首页）**：`.jp-hero__cta` 是 smoke flow 的断言锚点，重写首页时要么保留这个 class，
要么同步改 `flows/smoke.mjs`（不同步会以「首页缺标志元素」形态 red，不会静默）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1B 提示**：本卡交付的 harness 已就绪，但 mp 模拟器 E2E **需先由 Kevin 扫码恢复
devtools 登录**才能真跑（硬 gate 无降级，不要为了变绿改 preflight）。登录恢复后跑：

```bash
cd code/main/miniapp-jp && node test/e2e/run.mjs all
```

在此之前 kevin-qa 可先跑不依赖 devtools 的部分：`pnpm test`（vitest 43）+
`node test/e2e/self-test.mjs`（7）+ 后端 curl 契约回归。

---

**一句话结论：accept #1（curl wx-login）PASS**（在无代理 / `no_proxy` 含 localhost 的 shell 里 `EXIT=0`；
带 clash 代理的 shell 会假 FAIL 退 4，见风险 6）**；accept #2（`run.mjs smoke`）卡在本机 devtools IDE
登录过期**（需 Kevin 扫码，30 秒）**，preflight 7 项已精确隔离到这唯一一项，代码侧 self-test 7/7 +
type-check / lint / vitest(43) 全绿。**
