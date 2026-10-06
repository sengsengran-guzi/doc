# impl subagent 通用任务书（GZ-JP 二期代切 · /zhixing）

## Kevin 最新执行授权（2026-10-06，优先于本文旧 STOP / 全量重复测试要求）

Kevin 已要求继续到 D12，减少不必要测试，遇到类似样本缺口、工具链或可兼容技术问题自行判断并调整，不因重复尝试次数单独停工。调整须记入报告；涉及蓝图则同步权威、impact 与 change-log。每期保留独立 QA，验证本期实际变更及关键权限、资金、幂等、并发不变量；已有有效证据可复用，避免重复全项目测试、无关 UI 回归与机械变异验证。真实煤炉请求预算、不 push、不合 staging、主 miniapp 只读等红线不变。QA / 返工 / E2E 不调用真实煤炉，202 live 命令不在 QA 重跑。


你是一个全新上下文的实现者，只负责**一张 ticket**。项目根 = `/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi`（下文相对路径都相对它）。

## 必读（按序）
1. ticket 全文：`doc/jp/tickets/<TICKET>/prompt.md`（front-matter 的 accept / touches / blueprint_refs + 正文 §0 / What / AC）。
2. 项目铁律：`.claude/CLAUDE.md`（不动 ruoyi 自带模块 / 业务表 tenant_id / INSERT 不显式赋 tenant_id / Flyway append-only、文件名时间戳取 `date +V%Y%m%d%H%M` 当下真实时间 / menu_id 先查活库 + 全部迁移 / i18n 走 t() / 不写 any / 不吞异常 / 不留无说明 TODO / 不引未批准依赖）。
3. `blueprint_refs` 锚到的权威：`doc/jp/authority/{flows,field-ssot,ui-index,ownership}.yaml`（人读版 `doc/jp/authority/_rendered/*.md`），需求 `doc/jp/requirements.yaml`，架构 `doc/_adr/0025-jp-snap-mercari-gateway.md`，纸面推演 `doc/jp/19-代切链路纸面推演.md`，执行口径 `doc/jp/phase-plan.md`「二期执行口径」一节。
4. 记忆中与本 ticket 相关的坑：`~/.claude/projects/-Users-wkui-Project-profile-project-freelance-projects-sensenran-guzi/memory/MEMORY.md`（索引，按需点开）。

## 环境
- PATH 先 `export PATH=/opt/homebrew/bin:$PATH`（mvn / pnpm / python3.11 都在那）。
- dev MySQL：`docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue`（宿主 3307）；Redis：`sensenran-dev-redis`（宿主 6380，密码 ruoyi123）。
- 本机有 http 代理：curl 打 localhost 一律 `curl --noproxy '*'`。
- admin 测试账号 `gz_owner / gz_owner123!`（租户 1001）；`admin/admin123` 超管。
- **后端 8080 是共享单例**。改了任何 `ruoyi-gz-*` 或加了迁移、需要后端跑新代码时，**只能**用共享脚本重启（带锁、会 clean install、清迁移幽灵副本、等启动成功）：
  `bash /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/_run/restart-backend.sh [模块列表，默认全部 gz-*]`
  不要自己 kill 8080 或另起 spring-boot:run。脚本退出码非 0 = 起不来，看输出。
- 单测：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-<域> -am`（根 pom 默认 skip）。
- **新增 JUnit 测试类必须加 `@Tag("dev")`**（根 pom surefire `<groups>${profiles.active}</groups>`，不加 = 0 条、无报告 XML、accept 的 grep 必红）。
- **accept.run 一律用 `bash -c` 跑**（zsh 下 `rm -f *X*` 无匹配会 exit 1）。
- **改动 gz 模块后必须 `mvn clean install`**（非 clean 不重打 jar、不重编测试，exit 0 骗人）。
- 可能有另一个 impl subagent 同时在同一仓的另一片目录工作：**只 `git add` 你自己改的路径**，别 `git add -A`、别 stash / reset / checkout 别人的文件；撞到 `index.lock` 等几秒重试。

## 本项目已踩实的并发 / 事务坑（D7 QA 真库逮到，写代码时就避开）
- 守卫 UPDATE（`... WHERE status='x'`）affected=0 后若要再 SELECT 区分原因：**同事务内一律当前读（`FOR UPDATE`）**。MySQL 是 REPEATABLE-READ，普通 SELECT 读的是事务快照，会看到旧状态。
- 「先推进主单、再同步从表」的两步写：从表那一步**必须看主单那步的 affected**，affected=0 不写从表。
- mock 单测照不出上面两条；涉及先读后写同一行的改动，自测里至少做一次真库双连接验证。

## 外部依赖口径（硬性）
- 煤炉读 = 日本服务回放样本；煤炉写 = fake 驱动；翻译 = mock；微信支付 = mock 通道 + simulate-callback。
- **绝不打真煤炉**（唯一例外是 GZ-SNAP-202 ticket 里写明的 live 测试 ≤5 次 / 回放录制一次性 ≤15 次，且只有那张 ticket 可以）。不写任何循环或批量外部请求。
- 不跑 migration 之外的 destructive SQL（DROP / TRUNCATE / 大量 DELETE）。清自己造的测试数据用精确 WHERE 的硬删。
- 不动 `code/main/miniapp/`（现有小程序，本轮只读）。

## git
- 代码仓（`code/main/RuoYi-Vue-Plus` / `code/main/plus-ui` / `code/main/miniapp-jp` / `code/main/mercari-gateway`）都在 `task/D<N>` 分支上（主线程已建好；你先 `git -C <仓> branch --show-current` 确认）。在该分支上 commit 你的改动，消息形如 `feat(jp-snap): GZ-XXX-NNN <一句话>`，末尾加一行
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。不 push、不合并、不切别的分支。
- `doc/` 仓**不要 commit**（主线程统一提交）。**若写 .md 被 hook 拦截（Claude Code 子 agent 常见）**：完工报告全文放在最终回复里，主线程代为落盘到 `doc/jp/tickets/<TICKET>/report.md`。
- 迁移文件一经 commit 永不修改；需要改 schema 一律新建迁移。

## 交付标准
1. 实现 ticket 的 What，满足 AC。只改 `touches` 声明的路径；确需越界（如 i18n 词表、某个 mapper xml）就改，但在报告里**逐个列出越界文件和理由**。
2. **从项目根逐条原样执行 front-matter 里每条 accept.run**（必要时先重启后端），全部 exit 0 才算完。不许改 accept 的 run 来迁就实现。
3. 报告（放最终回复末尾，「==== 报告全文 ====」之后）：改了哪些文件（按仓）、commit sha、新迁移文件名、每条 accept 的命令与 **raw output**（含 surefire 报告里的 tests/failures 数）、对下游 ticket 的提示、已知风险。
4. 收工前确认各代码仓 `git status --porcelain` 只剩不属于你的改动（理想为空）。

## STOP 规则（不许自行变通）
- **spec_conflict**：你认为 ticket 某条要求技术上不合理 / 与蓝图或别处冲突 / 不该做 → **不许跳过或自改口径**，停下，最终回复第一行写 `STATUS: SPEC_CONFLICT`，说明哪条、为什么、你建议怎么改。
- **env 障碍**：同一环境 / 工具链障碍（服务起不来、连不上、产物路径不对、GUI 开关）连续 2 次尝试无进展 → 停，`STATUS: BLOCKED_ENV` + 现象与已尝试。
- accept 自修 2 次仍红 → `STATUS: FAILED` + 失败输出。

## 最终回复格式（给主线程，简洁）
```
STATUS: DONE | FAILED | SPEC_CONFLICT | BLOCKED_ENV
TICKET: <id>
COMMITS: <仓>@<sha> ...
MIGRATIONS: <文件名或 none>
ACCEPT: #0 pass|fail（一句 raw 摘要，如 tests=6 failures=0）; #1 ...; #2 ...
OUT_OF_TOUCHES: <越界文件或 none>
REPORT: 见下方报告全文
NOTES: <≤5 行：下游提示 / 风险 / 需要主线程知道的事>
```
