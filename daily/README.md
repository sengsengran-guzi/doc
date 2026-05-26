# sensenran-guzi daily 任务跟踪

> 主入口看 [doc/09-执行手册.md](../09-执行手册.md)（每天怎么干的 SOP）。
> 本文件聚焦"daily 文件夹结构 + 怎么用模板 + 单人闭环原则"。
>
> **单人 + AI 自闭环**：Kevin 一个人 + Claude Code，不做 multi-person closing / cross-day issue 跟踪。
> **不估时、不开 standup**：合同按交付物计价（启动费 + 分成），不按工时；执行端每天 ticket 推进，干完算完。

---

## 0. sensenran 单人模式硬约束（vs dongjiaoshan 多人模式）

| 维度 | dongjiaoshan 多人版 | sensenran 单人版 |
|---|---|---|
| 派单 | 复制 prompt 全文 → spawn AI | `@coder 做 D<N>/<TICKET>` 一行指令 |
| prompt 模板 | 4 份（prompt-fe / be / fullstack / min） | **0 份**，流程纪律在 [.claude/agents/kevin-coder.md](../../.claude/agents/kevin-coder.md) |
| ticket 描述 | prompts/<T>.md 自带流程段 | tickets/<T>.md 任务卡（只 What/AC，无流程） |
| 测试人力 | ABC 三人各跑 testing-human | Kevin 一人跑 testing-human |
| 当 testing 不过 | append `_open-issues.md` → 日终多人决策 | 在 ticket 任务卡 `§revision` 段就地写 → AI 闭环修 |
| 跨日 issue 跟踪 | `_open-issues.md` + 日终 closing 会 | **不存在**（问题不出 ticket） |
| 日终 closing | 0-5 步（汇总 + 决策 + 批量改文档 + ADR）| `cat reports/*.md > summary.md` + `git commit` + 写明日 README |
| 工程自检 | 每天跑 daily-engineering-audit 8 维 | **移到每周一次**（周末做一次） |
| 三段式（§0 / 实现 / §N）| 写在 4 份 prompt 模板里 | 写在 agent.md 里强制 |

---

## 1. 怎么用这份计划

**cwd 推荐**：在 `sensenran-guzi/` 根目录起 Claude Code（会自动加载 `.claude/CLAUDE.md` 项目引导）。

### 1.1 Kevin 开工（每天早上 1 分钟）

1. `cd doc/daily/D<N>/`（D01 起，6/01 创建第一个）
2. 打开 `README.md` 看今日目标 + ticket 清单（2-4 个）
3. 一行派单：
   ```
   @coder 做 D<N>/GZ-BEAN-002
   ```
   主线程读任务卡（`tickets/GZ-BEAN-002.md`）+ spawn `kevin-coder` subagent，自动带项目纪律。

### 1.2 AI 跑（每个 ticket 自闭环 — 强制流程）

每个 ticket 由 `.claude/agents/kevin-coder.md` 强制 3 段：

1. **§0 状态自检**（开干前必跑 6 步：git / 上游 / 关键类表 / 编译 / ADR / 合同范围）
   - 任一项不通过 → STOP 报 Kevin

2. **实现 ticket 主体**
   - 写代码 / 改 DB / 跑 Flyway
   - 复杂任务自行 spawn subagent

3. **§N 完工总结 + AI 自测**
   - 自测：编译 / 单测 / curl / DB count，**必须贴 ≥ 3 个代码 block 的 raw output**
   - 写 `reports/<TICKET>.md`（含 §0 自检结果 + 自测 raw + 风险 + ADR 已读 + 对下游提示）

**强制约束**（来自 dongjiaoshan D02 翻车经验）：
- ❌ 不允许"已通过 / ok / 全部跑通"五字了事 — verification gap 翻车前兆
- ✅ 必须 ≥ 3 个代码 block 的 raw output
- ✅ §0 自检 6 步任一失败 → STOP，不要"绕过去"
- ✅ ADR 已读行强制写（找不到关联 ADR 写"无相关"也算）

### 1.3 Kevin testing-human（5-15 分钟）

1. 打开 `testing-human.md` — 今日 ticket 的测试清单（你自己维护，按 mockup + AC 写）
2. 浏览器 / 微信开发者工具 / DB 客户端 跑一遍
3. 判断：
   - ✅ OK → ticket close（写 `progress.md` 标 ✅）
   - ❌ NOT OK → 在 ticket 任务卡 `§revision` 段写"问题 1: 现象 / 期望"

### 1.4 §revision 闭环（AI 自闭环修）

```
"@coder 修 D<N>/GZ-BEAN-002 revision 段"
```

AI 动作：
1. 读 `§revision` 段每条问题
2. 定位 + 修
3. 自测：贴新 raw output 到 `reports/<T>.md` 末尾追加
4. 在任务卡 `§revision` 每条后追加"已修 / 改了 <文件>"
5. 通知 Kevin 重测

循环到 OK。**不出 ticket 边界**，不写 `_open-issues.md`。

### 1.5 日终 closing（3-5 分钟）

```bash
cd doc/daily/D<N>
cat reports/*.md > summary.md   # 一行汇总
git add -A
git commit -m "D<N>: <主线>"
# 写 D<N+1>/README.md（列 2-4 个明日 ticket）
```

---

## 2. 文件夹结构（每天开工时 `cp -r _templates D<N>` 即可）

```
doc/daily/
├── README.md                         本文件
├── _templates/                       模板（不动）
│   ├── daily-README.md               D<N>/README.md 模板
│   ├── daily-progress.md             D<N>/progress.md 模板
│   ├── daily-summary.md              D<N>/summary.md 模板（实际由 cat reports/*.md 生成）
│   ├── daily-testing-human.md        D<N>/testing-human.md 模板
│   ├── ticket.md                     D<N>/tickets/<T>.md 模板
│   └── report.md                     D<N>/reports/<T>.md 模板
│
├── D01/                              6/01 创建（V1.0 开干）
│   ├── README.md                     今日目标 + ticket 清单 + 依赖
│   ├── progress.md                   今日 ticket 状态表（pending / in-progress / ✅ / blocked）
│   ├── testing-human.md              Kevin 一人测试清单（含 mockup 引用 + AC + 通过/失败标记）
│   ├── tickets/                      今日所有 ticket 任务卡
│   │   ├── GZ-SYS-001.md
│   │   ├── GZ-BEAN-001.md
│   │   └── ...
│   ├── reports/                      AI 完工报告（per ticket 一文件，避免并发写冲突）
│   │   ├── GZ-SYS-001.md
│   │   └── ...
│   └── summary.md                    日终 cat reports/*.md 生成
│
├── D02/
└── ...
```

**注意**：
- `_open-issues.md` 不建（问题在 ticket 内 `§revision` 闭环）
- `prompts/` 目录不建（一行派单替代）
- `testing-ai.md` 不单独建（AI 自测段已在 reports/<T>.md 内）
- `daily-engineering-audit.md` 不建（移到每周末）

---

## 3. ticket 任务卡颗粒度（_templates/ticket.md）

每个任务卡 8-15 行，不要再多。包含：

```markdown
# <TICKET-ID> — <一句话标题>

**优先级**: P0 | P1 | P2
**复杂度**: S | M | L | XL
**关联 PRD**: M4 §<段>
**关联 mockup**: booking-select.html
**依赖**: GZ-SYS-001（如有）

## What
（1-2 句描述做什么）

## AC（验收标准）
- [ ] AC 1：...
- [ ] AC 2：...
- [ ] AC 3：...

## Tech（端 + 范围）
- 后端：ruoyi-gz-bean 模块 / 表 gz_bean_booking
- 前端：miniapp/pages/bean/select.vue

## 备注
（如有特殊约束 / ADR 关联 / 合同条款，写在这）

---

## §revision（Kevin testing-human 后填，初始空）

<!-- 例：
- 问题 1：座位锁住了但 UI 没刷新 / 期望：选中态变灰
- 问题 2：返回首页时进度条还在转 / 期望：清掉
-->
```

**反例**（不要这样写）：
- ❌ 详尽到字段级（那是 PRD / 02-需求拆解 的事）
- ❌ 写实现细节（那是 coder 的事）
- ❌ 写流程纪律（那在 agent.md）

---

## 4. 周末工作（每周日做一次）

1. **跑工程自检**（A-H 维度 grep，参考 dongjiaoshan/_templates/daily-engineering-audit.md，但每周一次而非每天）
2. **curator 周巡**（21:30 自动触发，或手动 `@curator`）
   - 抽 skill 候选
   - 整合 facts/learnings
   - 刷新 SKILLS_INDEX.md
   - 提示是否 sync USER.md
3. **本周 commit 整理**（写一句"本周做了 X"到 `doc/daily/W<N>.md`，可选）

---

## 5. V1.0 / V1.1 阶段适配

| 阶段 | daily 频次 | 重点 |
|---|---|---|
| 筹备期（5/26-5/31） | 不开 daily | PRD 签字 / mockup 缺口 / .claude 骨架 |
| V1.0（6/01-6/15）| 每天 D<N> | 拼豆 / 微信登录 / 资讯 / 会员占位 / 后台基础 |
| V1.0 验收（6/15-6/20）| 不开 daily | 客户对照 02-需求拆解 §5 签字 |
| V1.1（6/16-7/31）| 每天 D<N> | 业务支付 / 预定 / 扭蛋 / 物流 / 对账 |
| V1.1 验收（8/01+）| 不开 daily | 客户对照 02-需求拆解 附录 A 签字 |
| 维护期（8/01+）| 按需 | 月维护工时 40h，超时另算 |

---

## 6. 不在 daily 做的事

- ❌ 重新设计架构（用 04-architecture.md 已定的，回 agent-lab 决策）
- ❌ 跨 ticket 的大重构（拆成新 ticket 排进未来 D<N>）
- ❌ 跨日 issue 跟踪（问题在 ticket 内闭环，超出 ticket 边界的写新 ticket）
- ❌ 业务审查会 / 标准会 / 站会（单人不需要）
- ❌ 复制 prompt 全文派单（一行 `@coder 做 D<N>/<T>` 就够）
