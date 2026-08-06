# 任务计划 —— 谷子宇宙拼团（日本代购一期）

24 个 ticket 编成 7 个任务，**串行执行**，每个任务末一道干净 QA 门（全绿才进下一任务）。

设计方案见 [design-options/](design-options/)（5 个关键页，3 页已选定 / 2 页待选）。

需求真源 [requirements.yaml](requirements.yaml) · 权威蓝图 [authority/](authority/) · ticket [tickets/](tickets/)

---

## 总览

| 任务 | 主题 | ticket 数 | 估时 | 阻塞后续？ |
|---|---|---|---|---|
| **D0** | 文档与决策沉淀 | 3 | 1d | ★ 必须先于 D1 |
| **D1** | 后端多 appid 底座 | 4 | 3.5d | ★ 阻塞一切 |
| **D2** | 新小程序脚手架 | 2 | 2d | 阻塞 D3 前端 |
| **D3** | 场与商品 | 5 | 3d | 阻塞 D4 |
| **D4** | 购物车 · 下单 · 支付 | 4 | 3d | 阻塞 D5 |
| **D5** | 履约 · 发货 · 退款 | 5 | 4d | 阻塞 D6 |
| **D6** | 联调回归上线 | 1 | 1.5d | — |

**合计 18 人日**（不含甲方侧备案 / 类目 / 商户号绑定的等待时间）

---

## D0 · 文档与决策沉淀

**目标**：把架构级决策落成 ADR，把 CLAUDE.md 更新到位。

**为什么必须排在 D1 之前**：CLAUDE.md 是每个 subagent 开工必读的约定文件。开发期间它要是过时的，
派出去的 subagent 会读到错的 menu 段位约定 —— **本项目 menu_id 已经撞过 3 次号**
（GZ-BEAN-036 误用 6051-6055 删掉核销权限，FLUSHDB 后才暴露，看板/核销/放座/延时全线 403）。
这不是理论风险。

| ticket | 内容 | size |
|---|---|---|
| GZ-DOC-001 | ADR-0019 多小程序（多 appid）支持 | S |
| GZ-DOC-002 | ADR-0020 日本拼团履约模型 | S |
| GZ-DOC-003 | CLAUDE.md 更新（menu 段 / 代码位置 / 商业口径纪律） | S |

**QA 范围**：
- 两份 ADR 存在、状态 Accepted、被否决方案的理由与复活条件写明
- CLAUDE.md 三处改动 grep 断言全过，且未破坏现有段位表其他行

---

## D1 · 后端多 appid 底座

**目标**：让后端能同时服务两个小程序。这是一期唯一硬阻塞——不做完，新小程序连登录都不通，更调不起支付。

| ticket | 内容 | size |
|---|---|---|
| GZ-SYS-020 | 微信小程序配置多 appid 化 + real/mock 运行时分派 | L |
| GZ-SYS-021 | access_token 按 appid 隔离 | S |
| GZ-SYS-022 | 微信支付多 appid（配置 + 下单 + **调起签名**） | L |
| GZ-SYS-023 | gz_user 加 app_id 维度 | M |

**QA 范围（★ 本任务的 QA 门最重）**：
- **现有小程序全量 Tier 1B 回归**：登录 / 拼豆下单支付核销 / 回收 / 店员权限 —— 必须与改造前**完全一致**
- 现有小程序**真机 1 分钱支付**（GZ-SYS-022 动了线上收款链路，单测照不出签名问题）
- 新 clientid 可独立登录、落独立 gz_user 行
- 两 appid 的 access_token 互不覆盖

> ⚠️ 这个任务改的是线上正在跑的登录与收款核心。任何一条现有回归红了，**不许往下走**。

---

## D2 · 新小程序脚手架

**目标**：`code/main/miniapp-jp/` 能构建、能登录、E2E 能跑。

| ticket | 内容 | size |
|---|---|---|
| GZ-JP-001 | miniapp-jp 工程初始化（复制裁剪 + env + appid + tabbar） | M |
| GZ-JP-002 | 新小程序登录打通 + E2E harness | M |

**QA 范围**：
- `pnpm build:mp` 出 dist、`type-check` / `lint` 绿
- 全仓 grep 不到旧小程序 appid / clientid 残留
- `node test/e2e/run.mjs smoke` 绿
- 新旧小程序 E2E **串行**跑通（devtools 端口共享单例，禁并发）

---

## D3 · 场与商品

**目标**：店员能开场上架，客人能浏览到商品详情。

| ticket | 内容 | size |
|---|---|---|
| GZ-JP-101 | 场建表 + admin 场管理（menu 14000 段） | M |
| GZ-JP-102 | 商品建表 + admin 商品管理（menu 14010 段） | M |
| GZ-JP-103 | mp 场 / 商品查询 API | S |
| GZ-JP-201 | 小程序首页（聚合：banner + 场 + 订单入口） | M |
| GZ-JP-202 | 小程序场详情 + 商品详情 | M |

**QA 范围**：
- DDL：两表公共字段全集齐（create_by/create_time/update_by/update_time/create_dept/del_flag/tenant_id）
- MENU：14000/14010 段 path 与 component 非空、父级有效
- 场状态读时惰性判定正确（过 end_time 即便库里是 open 也返回 closed）
- draft 场与 off_shelf 商品不下发给 C 端
- mp E2E：首页 → 场 → 商品详情 三跳可达，**注意事项区块默认展开且在 CTA 之上**

---

## D4 · 购物车 · 下单 · 支付

**目标**：客人能一次买 30 款并付款成功。

| ticket | 内容 | size |
|---|---|---|
| GZ-JP-104 | 购物车建表 + API | S |
| GZ-JP-105 | 订单 + 订单行建表 + 下单事务 + 支付回调 | L |
| GZ-JP-203 | 小程序购物车 | M |
| GZ-JP-204 | 小程序下单确认 + 支付 | M |

**QA 范围**：
- 下单金额**后端重算**，前端传假价不生效
- 支付回调**幂等**（重复回调不重复推进）
- 一单可含多场商品
- 全链路无运费行（购物车 / 下单确认页 grep 不到运费字样）
- mp E2E：加购 → 结算 → 下单 → mock 支付 → 订单生成

---

## D5 · 履约 · 发货 · 退款

**目标**：店员能批量推状态、批量填单号；没抢到的能自动退款；客人能看到每款货走到哪。

| ticket | 内容 | size |
|---|---|---|
| GZ-JP-106 | 履约状态机 + 批量推进 / 批量发货 API | L |
| GZ-JP-107 | 行级退款（购买失败 → 微信部分退款） | L |
| GZ-JP-108 | admin 履约看板（按客人聚合） | L |
| GZ-JP-109 | admin 订单管理（只读） | S |
| GZ-JP-205 | 小程序订单列表 + 详情（按状态分组） | M |

**QA 范围**：
- STATE：状态倒退被拒 / 跳过中间态被允许 / 置 delivered 未填单号被拒
- DATA：退款金额恒等于该行 `amount_cent`（不是整单）；订单 rollup 正确（部分 vs 全部）
- 退款回调幂等
- admin E2E：按客人聚合视图 + 跨订单勾选发货 + 批量标记失败的二次确认
- mp E2E：30 款订单详情分组渲染，同一运单号只出现一次，全页无「包裹」字样

> ★ **GZ-JP-107 开工第一步是硬查** `PayRefundController` 是否支持指定退款金额。
> 不支持 → STOP 报 Kevin，不要闷头实现（doc/17 §6 R3）。

---

## D6 · 联调回归上线

| ticket | 内容 | size |
|---|---|---|
| GZ-JP-301 | 联调回归与上线 | M |

**QA 范围**：
- 新旧两个小程序全量 E2E（**串行**）
- 新旧各跑一次真机 1 分钱支付
- 微信发货信息上报验证
- Flyway 无失败迁移
- staging 双小程序并跑后再灰度 prod

---

## 交给 /zhixing 前的项目侧约定

### 多仓拓扑（★ zhixing 默认假设单仓，本项目不是）

| 仓 | 路径 | 分支 | 远程 |
|---|---|---|---|
| 文档 | `doc/` | main | 无远程（纯本地） |
| 后端 | `code/main/RuoYi-Vue-Plus/` | staging | github:sengsengran-guzi/RuoYi-Vue-Plus |
| Admin | `code/main/plus-ui/` | staging | github:sengsengran-guzi/plus-ui |
| 现有小程序 | `code/main/miniapp/` | staging | github:sengsengran-guzi/miniapp |
| **新小程序** | `code/main/miniapp-jp/` | 待建 | **待建** github:sengsengran-guzi/miniapp-jp |

**对执行的影响**：
- 分支模型（`integration` + `task/D<N>`）**要在每个受影响仓各建一套**，不是一套管全部
- 跨仓 ticket（如 GZ-JP-101 同改后端 + plus-ui）合流有顺序：**后端先合，前端后合**（前端依赖接口）
- `touches` 合流对账 `git diff --name-only` **按仓分别跑**，不能只在一个仓里对
- 三个代码仓的部署流水线会**自动 commit + push 到 staging**，动手前先 `git status` 确认基线

### appid 策略：一期用 wxMOCK

Kevin 2026-08-06 定：**先用 `wxMOCK` 占位跑通全流程**，真 appid 到位后回补。

⚠️ **给 QA subagent 的口径**（不写清会卡在 L2 的「反 mock」门上）：
- 被 mock 的只有**微信 appid 通道**（登录 jscode2session / 支付调起），这是外部依赖不是业务数据
- **业务数据仍须真 seed + 真 DB 对账**，L1 的禁自造数据自证照常适用
- L2 端侧 UI 门照跑（模拟器 E2E 打真后端），只是拉不起真微信收银台

**appid 回补清单**（真 appid 到位后补做，不阻塞一期 close）：

| # | 回补项 | 关联 ticket |
|---|---|---|
| 1 | 三套 env 的 `VITE_WX_APPID` 换真值 | GZ-JP-001 |
| 2 | 放 `private.<appid>.key` 上传私钥（不进 git） | GZ-JP-001 |
| 3 | 后端 `wx.miniapp.apps` 配真 appid + secret | GZ-SYS-020 |
| 4 | `gz_pay_channel` 落新 appid，商户号绑定 | GZ-SYS-022 |
| 5 | **新旧两个小程序各跑一次真机 1 分钱支付** | GZ-SYS-022 / GZ-JP-301 |
| 6 | `gz_user.app_id` 默认值与存量回填复核 | GZ-SYS-023 |

### 项目侧配置（已就位）

| 文件 | 用途 |
|---|---|
| `doc/jp/lint-profile.yaml` | dag_lint 的公共字段全集（消 DDL form 误报）；GZ-SYS-023 列入豁免（ALTER 非建表） |
| `doc/jp/verify.sh` | L1 回归包原子：反 stale 守卫 + 5 表公共字段 + 6 条跨表对账 + C 端契约 |

**zhixing 调度命令（路径非默认，必须带参数）**：
```bash
S=doc/jp/waves/state.json
python3 <zhixing>/scripts/task_state.py --state $S init --tickets doc/jp/tickets
python3 <zhixing>/scripts/task_state.py --state $S next
python3 <zhixing>/scripts/task_state.py --state $S set --ticket GZ-DOC-001 --status done
```

---

## lint 状态

| lint | 结果 |
|---|---|
| `coverage_lint` | 见下（24 ticket 重跑后）—— 唯一未覆盖 REQ-SNAP-009 是二期待澄清项，不算漏拆 |
| `authority_lint check` | ✅ 145 条权威 × 24 ticket，锚点全部有效、无悬空 |
| `dag_lint` | ✅ 无结构性错误 |

### 已知 lint warning 与处置

- **REQ-SYS-004 被 5 个 ticket 认领**（阈值 4）：该需求原文「新建独立小程序，后端共用现有 admin」
  本身就是一条粗需求，天然横跨 4 个 SYS 改造点 + 新小程序登录。非 req_refs 乱贴，保留。
- **MENU 断言 C5 warning**：C5 按关键词找 `getRouters` 字面量。本项目 4 处 MENU 断言实际断的是
  path 非空 + component 非空 + **父级存在于 sys_menu**（防错父级），实质强于只调 getRouters；
  另在 GZ-JP-108 补了一条真调 `getRouters` 的断言。
- **STATE / API 断言 C5 warning**：run 是 `mvn test -Dtest=X` 与 `node run.mjs x`，
  C5 对这类命令天然失明（skill 自述的已知盲区）。真实强度检验走变异测试，见下。

### 建议的变异测试（蓝图冻结后）

抽 20% accept 注入已知类事故看是否仍绿，优先这三条：
1. GZ-JP-106：故意允许一次状态倒退 → 断言应红
2. GZ-JP-107：故意把退款金额改成整单总额 → 断言应红
3. GZ-JP-101：故意把菜单 path 置空 → 断言应红
