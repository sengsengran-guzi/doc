# 交接 · GZ-JP 二期代切（煤炉）—— /xuqiu 需求拆解进行中

> **✅ 已执行完毕（2026-10-03）**：3b–7 步已做完，任务计划已重排为 D7–D15（技术验证改为 D13、等账号插队）。
> 现状以 [phase-plan.md](phase-plan.md)、[18-代切二期方案.md](18-代切二期方案.md)、[change-log.md](change-log.md) 为准；本文下面的分支状态、D 编号与 lint 命令已过时，不要再照做。

> 写给接手的 AI。写于 2026-10-03。上一个会话已完成需求澄清、蓝图、设计门；**还没拆 ticket**。
> 读完本文即可接着干，不需要上一个会话的聊天记录。所有拍板都已落在文件里，**不要重新问 Kevin 已答过的问题**。

---

## 0. 一句话现状

甲方要在「谷子宇宙拼团」小程序（`code/main/miniapp-jp/`，一期已验收、未上线）里加**煤炉代切**：客人搜煤炉在售商品 → 付款 → 系统自动在煤炉下单 → 没抢到全额退款。煤炉官方合作与接入官方合作代购商都已失败，走**自建直连**。
`/xuqiu` 走到了**第 3 步之后**：REQ 清单 ✅、权威蓝图 ✅、ADR ✅、设计门 ✅（三个关键页已选定）。**下一步：3b 设计权威抽取 → 4 拆 ticket → 5 任务计划 → 6 lint → 7 确认单**。

## 1. 先读这些（按顺序）

| # | 文件 | 为什么读 |
|---|---|---|
| 1 | `.claude/CLAUDE.md`（项目根下） | 项目铁律：不动 ruoyi 自带模块、tenant_id、Flyway 命名与 append-only、menu_id 分段、i18n、测试分层。**违反直接打回** |
| 2 | `doc/jp/18-代切二期方案.md` | 二期总方案：实测结论、架构、主链路、**任务计划 D7–D13**、风险、上线卡点 |
| 3 | `doc/_adr/0025-jp-snap-mercari-gateway.md` | 架构决策（accepted）：两系统分工、同步调用 + 订单号幂等、结果三态、读写技术、风险边界、一期表改动 |
| 4 | `doc/jp/requirements.yaml` 中 `REQ-SNAP-*` 段 + `REQ-ORDER-011` / `REQ-FULFILL-008` | 需求真源。带 `decided_by: kevin` 的已拍板，**不许改 text**（改了 `decided_text_sha` 会告警） |
| 5 | `doc/jp/authority/flows.yaml` 的 `FLOW:F-JP-05`~`F-JP-11` | 业务流到步，ticket 的 `blueprint_refs` 锚这里 |
| 6 | `doc/jp/authority/field-ssot.yaml` 后半段 | 5 张新表 + 一期两表改动（`gz_jp_order_item` / `gz_jp_refund`） |
| 7 | `doc/jp/authority/ui-index.yaml` 的 `UI:*snap*` | 10 条 UI 记录，已写入设计门选定结果 |
| 8 | `doc/jp/authority/ownership.yaml` | 领域主权表（两系统必做，已冻结 9 条） |
| 9 | `doc/jp/design-options/snap-review.html` + 三份 md | 设计门选定结果与理由 |
| 10 | `~/claude-config/skills/xuqiu/SKILL.md` | /xuqiu 方法论本体（Claude Code 与 DSH 共用同一份实体文件） |

背景调研（需要时再看）：`doc/jp/_evidence-代切-乐一番对标调研.md`。

## 2. 已拍板事项（不要再问）

| 事项 | 结论 | 落点 |
|---|---|---|
| 交付形态 | 完整一次交付（搜索 + 贴链接 + 自动下单 + 人工兜底 + 自动退款），内部先做下单引擎后做搜索，与拼团一期一起上线 | REQ-SNAP-011 |
| 部署 | ruoyi 在**阿里云**（不是腾讯云）；日本服务 = 新仓 `code/main/mercari-gateway/`，Python，阿里云东京 | REQ-SNAP-017 |
| 定价 | 人民币价 = 日元价 × 实时汇率 × (1 + 加价比例) + 每件固定服务费；参数后台配，数值甲方填 | REQ-SNAP-020 |
| 锁价 | 下单锁价，报价 10 分钟有效 | REQ-SNAP-021 |
| 准入 | 「専用」屏蔽；需先留言 / 到付 → **转人工代买**；到付加后台可配的预估运费，多退少不补 | REQ-SNAP-022~025 |
| 改价 | 涨价 → 失败全额退；降价 → 照买差价不退 | REQ-SNAP-027/028 |
| 结果不明 | 不退款、不重试，三次对账，仍不明转人工 | REQ-SNAP-029 |
| 风控 | 触发验证 → 停号 + 自动下单总开关关 + 全转人工，只能 admin 手动恢复；不打码、不伪装指纹、不批量注册 | REQ-SNAP-030/056、ADR-0025 §4 |
| 验货 | 系统只记录；煤炉上的评价与退货由员工手工做 | REQ-SNAP-033 |
| 翻译 | 词表优先 + **阿里云机器翻译**兜底（新依赖，Kevin 已批准） | REQ-SNAP-014/015 |
| 下单形态 | 不进购物车，一单一件，立即购买；失败退款含服务费；抢到后不可取消 | REQ-SNAP-035~037 |
| 一期表改动 | `gz_jp_order_item.product_id` 改可空 + 加 `snap_item_id`；`gz_jp_refund` 唯一键改 `(tenant_id, order_item_id, refund_type)` | ADR-0025 §5 |
| 设计门 | mp 搜索 **B**（tabbar 三格：首页 = 拼团 / 煤炉 = 代切 / 我的）· mp 详情 **A**（到手价 + 日元原价，价格说明抽屉不显示汇率与加价比例）· admin 代切下单 **A**（独立页三 tab） | design-options/*.md |
| 明确不做 | 订阅消息、收藏、降价提醒、议价留言、自动评价、自动退货、多账号对抗风控 | REQ-SNAP-050~056（deferred） |

**未决（甲方侧，不阻塞拆 ticket）**：REQ-SNAP-009（甲方一句没写完的话）、010（账号类型与付款方式）、060（转运仓与日本负责人）、061（定价三参数初值）、062（封号风险书面确认，上线卡点）。都写在 `doc/jp/confirmation/二期代切确认单.md`，等 Kevin 发给甲方。

## 3. 仓库与分支

项目根不是 git 仓；以下各自独立。**四个相关仓都已切到 `feat/jp-snap`**：

| 仓 | 起点 | 现状 |
|---|---|---|
| `doc/` | `feat/jp-daigou-requirements`（JP 一期文档都在这条，未合 main） | ★ 本次全部产出都在这里，**未 commit**（见下方清单）。无远程 |
| `code/main/RuoYi-Vue-Plus` | `staging` | 无改动（staging 本身领先 origin 1 个 commit，与本次无关） |
| `code/main/plus-ui` | `staging` | 无改动 |
| `code/main/miniapp-jp` | `main` | 无改动。无远程 |
| `code/main/mercari-gateway` | — | **尚不存在**，由 D9 第一张 ticket 新建（独立 git 仓） |

主线小程序 `code/main/miniapp` 本期不涉及，不要动。

doc 仓未提交的改动：`jp/requirements.yaml`、`jp/authority/{flows,field-ssot,ui-index}.yaml`、新增 `jp/authority/ownership.yaml`、`jp/authority/_snapshot.json` 与 `_rendered/`、`jp/change-log.md`、`jp/_manifest.json`、`jp/design-options/{README.md, mp-snap-search.md, mp-snap-detail.md, admin-snap-purchase.md, snap-review.html}`、`jp/18-代切二期方案.md`、`jp/confirmation/二期代切确认单.md`、`jp/_spike/mercari-probe/`、`_adr/0025-…md`、本文件。**commit 前先问 Kevin**（他的规矩：只在他要求时提交）。

## 4. 接下来怎么做

工作区根 = `doc/jp/`（拍平布局）。**所有 lint 都在 `cd doc/jp` 后运行**，脚本会自动识别工作区。

### 4.1 第 3b 步：设计权威抽取（模板 `~/claude-config/skills/xuqiu/templates/design-authority.md`）

- **token**：沿用 `code/main/miniapp-jp/src/style/c-tokens.scss`，不新建主题。
- **内容块回流**：上一个会话预判了草图里会变的内容块，逐个确认它们都能算出来或已有来源；查出新需求就补 REQ，再重跑 coverage_lint：

  | 内容块 | 判定 |
  |---|---|
  | 煤炉 tab 空态的热门词 chips | 来源 = 词表 `term_type=ip`、按 `sort_no` 取前 12 条，已有 REQ-SNAP-014，不需要新配置 |
  | 「实时价格 · x 秒前」 | 由 `gz_jp_snap_item.fetched_at` 算出，禁止手填 |
  | 「需人工确认」角标 | 由 `gate_result=manual` 算出 |
  | admin 各 tab 的数字角标、今日下单数 / 上限、评价期限剩余时间 | 都能算出（count / `today_count` / `rate_deadline_at`） |
  | **煤炉 tab 图标** | **新素材需求**：`static/tabbar/mercari.png` / `mercariHL.png`，要补一条 REQ（来源：设计门 B），素材找谁出要问 Kevin |
  | 代切协议条款文案 | 已有 `UI:mp.agreement.snap`，需甲方过目（确认单第三部分 #6） |

- **误导料**：`snap-review.html` 里没被选中的方案（搜索 A / C，详情 B / C，admin B / C）属于被否决方向，不是依据。

### 4.2 第 4 步：拆 ticket

格式照抄一期：`doc/jp/tickets/<ID>/prompt.md` = YAML front-matter（`ticket / track / phase / size / req_refs / depends_on / touches / blueprint_refs / accept`）+ 正文（§0 状态自检 / What / AC / 口径提示）。范例看 `tickets/GZ-JP-107/prompt.md`。accept 写法按 `~/claude-config/skills/xuqiu/templates/accept-assertion-forms.md`，**每条 accept 都配一行 `counterfeit`**（写明实现被改成什么样时这条会红）；写不出来就说明 accept 太松。

**建议的拆法**（上一个会话的草案，可以调整，但调整后要保证 coverage 零漏拆）：

| 任务 | ticket | 内容 | 主要 req_refs |
|---|---|---|---|
| D7 | GZ-SNAP-001 | 技术验证（spike）：东京服务器 + 固定 ISP 出口 + 甲方账号，结论写回 ADR-0025 §3 | SNAP-064 / 006 / 010 / 026 / 029 |
| D8 | GZ-JP-110 | 未付款超时关单（释放孤品锁） | ORDER-011 |
| D8 | GZ-JP-111 | 退款卡单补偿 | FULFILL-008 |
| D8 | GZ-SNAP-101 | 5 张新表 + 一期两表 ALTER + 字典 + 菜单 + sys_config 种子 | SNAP-004 / 041 / 020 / 014 |
| D8 | GZ-SNAP-102 | 实体 / 枚举扩展（source=snap、快照 snap 段、状态机放开 `await_seller_ship→purchase_failed`，仅限 snap） | SNAP-004 / 021 / 032 / 033 |
| D9 | GZ-SNAP-201 | gateway 仓初始化 + Docker 部署 + HMAC + `/v1/health` | SNAP-017 / 042 |
| D9 | GZ-SNAP-202 | 读：`/v1/search` `/v1/items/{id}` + 降级无头浏览器 + `/v1/img` | SNAP-005 / 012 / 013 / 018 |
| D9 | GZ-SNAP-203 | 写：`POST /v1/purchases`（幂等、核价、证据、风控信号） | SNAP-006 / 026 / 027 / 030 / 043 |
| D9 | GZ-SNAP-204 | 对账 `/reconcile` + 交易巡检 `/v1/trades` | SNAP-029 / 032 |
| D10 | GZ-SNAP-301 | ruoyi 侧 gateway 客户端（HMAC / 超时 / 熔断）+ 心跳 + 主动探测 | SNAP-017 / 042 / 044 |
| D10 | GZ-SNAP-302 | 搜索 / 详情 API：归一化（词表 + 阿里云机翻）+ 过滤 + 标题翻译 + 缓存 + 图片 CDN 改写 | SNAP-002 / 003 / 012~016 / 018 / 019 / 040 |
| D10 | GZ-SNAP-303 | 准入判定 + 汇率抓取 + 报价 | SNAP-007 / 020~025 / 061 |
| D10 | GZ-SNAP-304 | 提交订单 + 孤品锁 + 支付回调写任务 | SNAP-004 / 035 / 037 / 041 |
| D10 | GZ-SNAP-305 | 下单调度 + 三态 + 对账 + 风控熔断 | SNAP-026~030 / 036 / 038 / 039 |
| D10 | GZ-SNAP-306 | 人工代买 API + 到付多退 | SNAP-023~025 / 031 |
| D10 | GZ-SNAP-307 | 交易巡检落账 + 到仓 / 验货 / 评价 / 退货 API + 评价提醒 | SNAP-032~034 |
| D11 | GZ-SNAP-401~405 | admin：代切下单页 / 采购账号页 / 配置页（含汇率）/ 词表页 / 履约看板代切行 | 见 `UI:admin.*snap*` 的 related_reqs |
| D12 | GZ-SNAP-501~504 | mp：tabbar 三格 + 煤炉搜索页 / 详情页 / 下单确认 snap 模式 + 协议条款 / 订单详情与列表的代切状态 | 见 `UI:mp.*snap*` 的 related_reqs |
| D13 | GZ-SNAP-601 | 联调与全链路演练（故障注入：断网 / 超时 / 重启） | SNAP-001 / 011 / 038 / 039 |

要点：

- D9 的 ticket 属于另一个系统：front-matter 写 `system: mercari-gateway`，`touches` 指向 `code/main/mercari-gateway/**`。Python 栈，没有 DDL，不受公共字段断言约束。
- D7 的结论决定 D9 / D10 的工作量：no-go 时 GZ-SNAP-203 删除，305 的执行器只做"转人工"。拆的时候在 prompt 里写明这条分支。
- **menu_id**：二期规划用 14040–14099（14040 代切目录 · 14050 代切下单 · 14060 采购账号 · 14070 词表 · 14080 配置）。一期迁移里已占用 14000–14039 和 14999。**动手前按 CLAUDE.md §6 grep 活库与迁移文件**，这个项目撞过 3 次号。
- **sys_config** 的 config_id 用 1404xxxx 段，`tenant_id` 必须显式写 `'1001'`（原因见 `V202608101050__GZ-JP-201-jp-home-banner-config.sql` 头注释）。
- **定时任务**：prod 没部署 SnailJob，要走 `GzLocalSchedulerConfig` + `@Scheduled`，参照 `ruoyi-gz-bean/.../job/GzLocalBeanScheduler.java`。
- **退款**：复用 jp 独立退款链路（`GzJpRefundServiceImpl` / `gz_jp_refund`），**不碰** `PayRefundController` / `PayRefundTxService`，那是拼豆和回收在用的线上资金链路。

### 4.3 第 5~7 步

- 把 D7–D13 补进 `doc/jp/phase-plan.md`。本项目是**旧版工作流**（`waves/state.json` 没有 `workflow_version` 字段），用 md 版任务计划，**不要迁移到 v2、不要建 workflow.json**。拆完先跑一次 `dag_lint`，确认它能读到新的 phase。每个任务写清 QA 范围，再写一份全链路演练剧本。
- 跑 lint，全绿才算就绪：
  ```bash
  cd doc/jp
  python3 ~/claude-config/skills/xuqiu/scripts/coverage_lint.py --write-back
  python3 ~/claude-config/skills/xuqiu/scripts/authority_lint.py check
  python3 ~/claude-config/skills/zhixing/scripts/dag_lint.py
  ```
- 更新 `_manifest.json` 的 coverage 与 `next: zhixing`；确认单状态等 Kevin 发给甲方后再改。

## 5. 当前 lint 状态与已知坑

| 现象 | 说明 |
|---|---|
| coverage_lint：漏拆 43 条 | **预期**，二期 ticket 还没拆。拆完应降到 0 |
| coverage_lint：「做了明确不做的事」1 条（GZ-JP-102 → REQ-PROD-007） | 一期遗留，与二期无关，不要顺手改 |
| authority_lint：拒绝 snapshot | 有未消化的变更时会拒绝。先跑 `impact`，确认受影响的 ticket 都处理过、在 change-log 记一行，再 `snapshot --force` |
| adr_check 直接跑会显示「无 ADR 目录」 | 项目 ADR 在 `doc/_adr/`，而且 0001–0024 是旧格式（无 frontmatter），整目录跑会全部报错。只校验 0025：只把 0025 拷到临时目录，`--adr <临时目录> --repo-root <项目根> --ws doc/jp`。此时会报一条「A2: amends 指向不存在的 ADR-0020」，这是隔离校验造成的，可以忽略（上一个会话实测其余检查项全部通过） |
| `UI:global.theme` 写的主色是 `#c8452f` 朱红 | **与现实不符**：miniapp-jp 实际 token 是品牌绿 `#33b36b`。改这条会让一期 ticket 进 impact，修之前先问 Kevin |
| `doc/jp/_spike/mercari-probe/` | 2026-10-01 的只读探测脚本（`probe.py` 搜索 + 详情，`probe2.py` 测热缓存耗时，`pw.py` 无头浏览器）。重建环境：`python3 -m venv .venv && .venv/bin/pip install mercapi playwright && .venv/bin/python -m playwright install chromium`。**不要用 Kevin 本机代理出口做批量压测**，那是他个人上网用的 IP（东京 Sakura 机房），被拦会影响他。D7 用独立的东京服务器 |

## 6. Kevin 的工作偏好

- 中文交流，技术术语保留英文；不写空话和铺垫；给"选项 + 推荐 + 理由"，让他能反驳。
- 一次只问一个问题，优先出选择题。只问他答得上来的（目的 / 取舍 / 边界），读代码能查到的自己定，并写进 REQ 的 `note`。
- **不主动计算商业口径或分成**；定价数值由甲方填，我们只定公式结构。
- 文档只写最终状态，不写"原来是 X 现在改成 Y"（ADR 和 change-log 除外）。
- 发给甲方的文档不带内部编号与术语（REQ-xxx、表名、API 名）。
- 完成任务后关掉自己启动的后台进程（dev server 等）。
