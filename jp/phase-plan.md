# 任务计划 —— 谷子宇宙拼团（一期拼团 + 二期代切）

一期 24 个 ticket 编成 D0–D6（已全部 `qa_passed`）；二期代切 27 个 ticket 编成 D7–D15。
**串行执行**，每个任务末一道干净 QA 门（全绿才进下一任务）。

设计方案见 [design-options/](design-options/)（一期 5 页 + 二期 3 页，全部已选定）。二期总方案 [18-代切二期方案.md](18-代切二期方案.md)。

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
| **D7** | 支付通道堵洞 + 一期缺口 + 代切数据底座 | 5 | 3.5d | ★ 阻塞二期一切 |
| **D8** | 日本服务骨架 + 只读接口 | 2 | 2.5d | 阻塞 D9 |
| **D9** | ruoyi 找货 · 报价 · 提交订单 | 4 | 3.5d | 阻塞 D10 |
| **D10** | ruoyi 下单引擎（对 fake 驱动） | 3 | 3.5d | 阻塞 D11 |
| **D11** | admin 五页 | 5 | 3d | 阻塞 D12 |
| **D12** | mp 四页 | 4 | 3.5d | — |
| **D13** | 技术验证 go / no-go | 1 | 2–3d | ★ 外部阻塞（甲方账号 / 服务器 / 代理），**到位即插队** |
| **D14** | 日本服务真下单 + 真对账 | 2 | 3d | no-go 时关闭 |
| **D15** | 联调与全链路演练 | 1 | 1.5d | — |

**一期合计 18 人日**（不含甲方侧备案 / 类目 / 商户号绑定的等待时间）；**二期合计约 26 人日**（不含甲方侧账号 / 服务器 / 代理 / CDN 域名 / 书面确认的等待时间）。

**二期排序原则**（Kevin 2026-10-03）：技术验证要等甲方的账号、东京服务器和 ISP 代理，不让它卡住前面的工作。
凡是不依赖真账号的（数据底座、只读接口、下单引擎对 fake 驱动、admin、mp）先做；D13 只依赖 D8，**账号一到即可插队提前跑**；
只有 D14（真下单 / 真对账）等它的结论。fake 驱动是日本服务的正式模式之一（`FLOW:F-JP-12`），既让 ruoyi 侧提前联调，也是故障注入的数据源。

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

> ★ **该硬查已于 D0 执行完毕（2026-08-06），结论：不支持。** 现有 GZ-PAY 退款链路只支持
> 「一单一次全额」（`RefundApplyBo` 无金额入参、`createRefunding` 的 `countActiveByTransactionId>0` 即拒、
> `gz_pay_transaction.refunded` 是终态），但通道层 `IWechatPayClient.refund` 本就支持指定金额。
>
> **路线已定（Kevin 拍板）：jp 域开独立退款入口，只共用通道层** —— 新建 jp 专用退款 Service + 退款单表，
> **拼豆/回收的资金链路一行不动**。GZ-JP-107 工作量按「新建一套退款链路」估，不是调现成接口。
> 详见 ADR-0020 §3。

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

# 二期 · 代切（煤炉）

需求 REQ-SNAP-* / REQ-ORDER-011 / REQ-FULFILL-008 · 架构 [ADR-0025](../_adr/0025-jp-snap-mercari-gateway.md) ·
蓝图 `FLOW:F-JP-05`~`12` / `gz_jp_snap_*` / `UI:*snap*` / [ownership.yaml](authority/ownership.yaml)。

**贯穿二期的三条不变量**（每个任务的 QA 门都要守）：
1. 钱只在 ruoyi；日本服务没有用户个人信息，只认订单号、商品 ID、锁定日元价。
2. 结果不明不动钱：只有拿到交易号算成功；对账只会自动得出「成功」，其余转人工；不明状态下绝不再次下单。
3. 遇验证即停：停号、关自动下单总开关、全转人工，只能 admin 手动恢复；不打码、不伪装指纹、不批量注册。

---

## D7 · 一期缺口 + 代切数据底座

**目标**：堵上共享支付通道「过期后仍可付、付了被吞」的洞（纸面推演 K1，现网三条业务线都受影响）；一期两个缺口补上（代切下它们是主路径）；代切的表、字典、配置、实体就位，一期行为零变化。

| ticket | 内容 | size |
|---|---|---|
| GZ-PAY-106 | 支付单带过期时间（微信侧到点拒付）+ 本地超时同时关微信单 + 迟到付款不再被吞（共享支付通道） | M |
| GZ-SNAP-101 | 5 张新表 + 订单行 / 退款表 ALTER + 12 个字典 + 5 个配置键 | M |
| GZ-SNAP-102 | 实体 / 枚举 / 快照 snap 段 / 状态机放开（仅代切）/ 一期查询兼容空 product_id | M |
| GZ-JP-110 | 未付款 15 分钟关单（查单 → 关微信单 → 关本地单） | M |
| GZ-JP-111 | 退款卡单补偿 + 通道层新增退款查单 | M |

**QA 范围**：
- DDL：5 张新表公共字段全集（含 `tenant_id`）；`gz_jp_refund` 旧唯一键已删、新唯一键含 `refund_type`、存量回填
- DATA：5 个配置键全在 1001 租户；定价三项为空；自动下单默认关
- STATE：按来源判定的状态机入口——snap 行 `await_seller_ship→purchase_failed` 允许；batch 行在全部状态对上与一期 `checkAdvance(from,to)` 结果逐一相同（一期本就允许任意非终态→purchase_failed）
- **一期全量回归**：gz-jp 全部单测 + miniapp-jp `run.mjs all` + plus-ui `e2e/gz-jp` 全绿（ALTER 一期表之后最容易伤到的就是一期）
- `git diff` 证明 `IWechatPayClient` / `GzPayTransactionServiceImpl` 既有方法签名不变、`PayRefund*` 三个类零改动（拼豆 / 回收线上资金链路）
- **支付回归**：gz-common / gz-bean / gz-recycle / gz-jp 全部单测 + 现有小程序 `code/main/miniapp` 支付相关 E2E 不回归；统一下单请求体带 time_expire；timeout 单收到成功回调记 late_paid 不被吞
- Flyway 无失败迁移

---

## D8 · 日本服务骨架 + 只读接口

**目标**：新仓 `code/main/mercari-gateway/` 能本地 docker 起，鉴权、健康检查、fake 驱动、搜索 / 详情 / 图片代理可用。

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-201 | 仓库初始化 + Docker + HMAC + `/v1/health` + fake / disabled 驱动 | M |
| GZ-SNAP-202 | 搜索 / 详情 / 图片代理 + 无头浏览器降级 + 限速 | L |

**QA 范围**：
- 鉴权：错签 / 超时戳 / 缺头 401；`/v1/img` 白名单外 403
- fake 驱动按 order_no 幂等（账本计数）
- 解析一致性：JSON 接口与浏览器降级两条路径对同一样本字段一致
- live 只读契约测试（≤5 次请求，**不在 Kevin 本机代理上做任何循环或压测**）
- 健康检查与日志不含任何凭据

---

## D9 · ruoyi 找货 · 报价 · 提交订单

**目标**：小程序能搜到、看到报价、提交代切订单并付款；付款后下单任务落库（不执行）。

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-301 | 日本服务客户端（HMAC / 超时 / 熔断 / 独立线程池）+ 心跳 + 主动探测 + 风控熔断方法 | M |
| GZ-SNAP-302 | 搜索 / 详情 API：链接识别、词表 + 阿里云机翻、过滤、标题翻译、缓存与合并、出图改写 | L |
| GZ-SNAP-303 | 准入三态 + 中国银行汇率抓取 + 报价器 | L |
| GZ-SNAP-304 | 提交订单 + 孤品锁 + 支付回调写下单任务 + 统一释放锁 | L |

**QA 范围**：
- 跨系统：ruoyi 签名被真实日本服务（fake 模式）接受
- STATE：准入按序判——拒代购（标题 / 描述 / 卖家简介）先于转人工；过滤在 ruoyi 侧执行，详情直开也拦；白名单为空 = 全拒
- DATA：拿 `_spike/mercari-probe/READ-PROBE-2026-10-03.md` 记录的真实样本（拒代购描述、到付、Shops）各验一次准入结果
- DATA：报价公式（向上取整、预估运费不乘加价）；定价未配 / 汇率超 6 小时拒报价
- API：mp 任何接口响应不含汇率与加价比例
- DATA（真并发）：同一商品 10 个并发提交只产生 1 张订单（`_accept/snap-submit-race.sh`）
- 提交时实时复查：报价后已售出 / 涨价在付款前就被拦下（不产生「先收钱再退款」）
- 限流：同一 IP 超限后不再打日本服务；merc.li 分享短链能直达详情
- 支付回调重复推送只写一条任务；回调里零日本服务调用
- 一期拼团下单 / 支付回调回归

---

## D10 · ruoyi 下单引擎（对 fake 驱动）

**目标**：付款后自动下单、三态结果、对账、风控熔断、人工代买、交易跟踪、退款全部跑通（日本服务用 fake 驱动）。

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-305 | 调度 + 账号选择（冷却=等待）+ 三态 + 对账（只自动得出成功）+ 重启恢复 + 证据 + 熔断 | L |
| GZ-SNAP-306 | 人工代买 API + 到付运费差价退款（不碰订单行、不参与汇总） | M |
| GZ-SNAP-307 | 交易巡检 + 手工标记卖家发货 / 取消 + 到仓 / 评价 / 退货 + 评价提醒 + 履约看板后端守卫 | L |

**QA 范围**（★ 二期最重的门）：
- **故障注入**：断网 / 超时 / 进程重启三场景，每单在 fake 账本里至多点击一次购买；不明单零退款（`_accept/snap-fault-injection.sh`）
- STATE：对账查不到（不论是否已售出）只排下一轮，满 3 轮转人工，从不自动判失败；第 2 轮查到按成功；对账路径零 POST
- STATE：余额不足（account_unpayable）→ 转人工 + 暂停该账号，不退款、不关全局开关
- STATE：冷却中留队列；无健康账号 / 到日限转人工；风控信号 → 停号 + 关总开关 + queued 全转人工
- DATA：到付商品「已到仓」填运费后差价退款，订单仍是 paid、行 `refund_status` 为空；之后验货不通过退款额 = 实付中未退部分；
  SQL 对账：每行非失败退款单金额之和 ≤ `amount_cent`
- STATE：交易状态只进不退；未评价代切行混进一期批量操作整批拒绝
- REQ-SNAP-038：fake success 场景下 `result_at − paid_time` < 60s
- 一期履约 / 退款全部单测回归

---

## D11 · admin 五页

**目标**：日本员工能在后台处理人工代买、跟交易、管账号与总开关、改配置与词表；国内店员在履约看板看得到代切行。

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-401 | 代切下单页（待人工 / 交易跟踪 / 自动任务）+ 菜单 14040 目录 / 14050 段 | L |
| GZ-SNAP-402 | 采购账号页 + 自动下单总开关（恢复需二次确认）+ 菜单 14060 段 | M |
| GZ-SNAP-403 | 代切配置页（定价 / 过滤 / 准入 / 交易 / 汇率）+ 菜单 14080 段 | M |
| GZ-SNAP-404 | 代切词表页 + 「试一试」+ 菜单 14070 段 | S |
| GZ-SNAP-405 | 履约看板代切行（来源标签 + 未评价不可勾选） | S |

**QA 范围**：
- MENU：14040–14089 path / component 非空、父级有效、getRouters 下发；动手前查活库与全部迁移的占用（本项目撞过 3 次号）
- admin Playwright E2E 五个 spec + 一期 `fulfill-board.spec.ts` 回归
- 会触发退款的操作（卖家取消 / 退货完成 / 填失败）都有二次确认
- 配置保存后立即生效（Caffeine + Redis 两级缓存都清）
- 纯 admin，无人验

---

## D12 · mp 四页

**目标**：客人从「煤炉」tab 搜到商品、看详情、下单付款、在订单里看到抢购结果。

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-501 | tabbar 三格 + 煤炉图标（AI 画）+ 搜索页 | L |
| GZ-SNAP-502 | 代切商品详情（到手价 + 煤炉原价 + 价格说明三行） | M |
| GZ-SNAP-503 | 下单确认 snap 模式（勾选默认不勾）+ 协议代切条款 | M |
| GZ-SNAP-504 | 订单列表 / 详情代切状态 + 抢购中轮询 + 运费差价行 | M |

**QA 范围**：
- mp 模拟器 E2E：`snap-search` / `snap-detail` / `snap-checkout` / `snap-order` + 一期 `all` 回归（与现有小程序**串行**跑）
- vitest：确认页 snap 逻辑、订单详情状态映射（不暴露「结果不明」）
- 详情页源码与文案不出现汇率与加价比例
- token 走 `c-tokens.scss`，组件不硬编码 hex
- **人验列（Tier 2）**：501 / 502 新页首版视觉；503 真机微信支付（随 D15 演练一起跑）

---

## D13 · 技术验证 go / no-go（外部阻塞，到位即插队）

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-001 | 东京服务器 + ISP 代理 + 甲方账号：6 项实测，结论回填 ADR-0025 §3 | M |

**前置**：REQ-SNAP-065（服务器 + 代理）、REQ-SNAP-010 / 060（账号、付款方式、转运仓）。缺一不开工，**不许拿 Kevin 本机代理凑**。

**QA 范围**：
- 报告 6 项都有实测数字；ADR §3 有 `S0 结论：go|no-go` 行
- 报告与证据里无密码、Cookie、完整地址
- 验证中触发验证码即停，未尝试绕过

**no-go 分支**：日本服务部署 `GATEWAY_DRIVER=disabled`；D14 两张卡关闭；巡检改日本员工手工标记（D10 已实现 `F-JP-09.step1b`）；
自动下单总开关永久关闭，代切全部走人工代买。D9–D12 的产出不受影响。

---

## D14 · 日本服务真下单 + 真对账

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-203 | Playwright 真下单驱动（幂等持久化 / 前置核价 / 点击后一律 unknown / 证据 / 风控即停） | L |
| GZ-SNAP-204 | 真对账（购买记录）+ 交易巡检 | M |

**QA 范围**：
- 用 D13 录下的页面样本跑判定测试：点击前停下才可能 failed，点击后拿不到交易页一律 unknown
- 幂等表进程重启不丢；同 order_no 不二次点击
- 对账 / 巡检代码路径不可能触发购买
- 不引入任何验证码识别、指纹伪装类依赖

---

## D15 · 联调与全链路演练

| ticket | 内容 | size |
|---|---|---|
| GZ-SNAP-601 | 演练剧本 R1–R8 + 代切上线卡点进 GO-LIVE-CHECKLIST 桶 2 | M |

**QA 范围**（演练剧本 `snap-rehearsal.md`，Kevin 在场）：

| # | 场景 | 断言 |
|---|---|---|
| R1 | 真机：中文搜 → 详情 → 付款最便宜商品 | 1 分钟内「已抢到」（no-go：「人工处理中」）|
| R2 | 被抢（fake sold_out） | 「未抢到·已退款」，退款到账 |
| R3 | 人工代买 + 到付差价 | 填成功（实际价不高于锁定价）→ 已到仓填运费 → 差价退款到账，订单仍 paid |
| R4 | 交易取消（卖家取消 / 已发货后丢件） | 全额退清（取消只发生在到仓前，此时无差价）|
| R5 | 验货不通过 | 退货完成后全额退清 |
| R6 | 风控 | 停号 + 关总开关 + queued 全转人工 → admin 恢复 |
| R7 | 未付款 15 分钟 | 关单、锁释放、原支付单不可再付 |
| R8 | 故障注入 | 断网 / 超时 / 重启下零重复下单、零错误退款 |

另：miniapp-jp `run.mjs all`、plus-ui `e2e/gz-jp`、现有小程序 E2E（串行）全绿；Flyway 无失败迁移。

---

## 交给 /zhixing 前的项目侧约定

### 多仓拓扑（★ zhixing 默认假设单仓，本项目不是）

| 仓 | 路径 | 二期工作分支 | 远程 |
|---|---|---|---|
| 文档 | `doc/` | `feat/jp-snap` | github:sengsengran-guzi/doc |
| 后端 | `code/main/RuoYi-Vue-Plus/` | `feat/jp-snap` | github:sengsengran-guzi/RuoYi-Vue-Plus |
| Admin | `code/main/plus-ui/` | `feat/jp-snap` | github:sengsengran-guzi/plus-ui |
| 现有小程序 | `code/main/miniapp/` | 不涉及（二期不动） | github:sengsengran-guzi/miniapp |
| 拼团小程序 | `code/main/miniapp-jp/` | `feat/jp-snap`（主干 main） | 无远程 |
| **日本服务** | `code/main/mercari-gateway/` | 由 GZ-SNAP-201 新建（`main` → `feat/jp-snap`） | 无远程 |

> 后端 / Admin 的 `feat/jp-snap` 起点比 `staging` 少一个拼豆提交（`feat: new check`，与代切无关）；合回 staging 前先 rebase / merge staging。

**对执行的影响**：
- 分支模型（`integration` + `task/D<N>`）**要在每个受影响仓各建一套**，不是一套管全部
- 跨仓 ticket（如 GZ-JP-101 同改后端 + plus-ui）合流有顺序：**后端先合，前端后合**（前端依赖接口）
- `touches` 合流对账 `git diff --name-only` **按仓分别跑**，不能只在一个仓里对
- 三个代码仓的部署流水线会**自动 commit + push 到 staging**，动手前先 `git status` 确认基线

### 二期执行口径（★ 给 zhixing 与 QA subagent）

**执行范围**：甲方的东京服务器、ISP 代理、煤炉账号暂时都拿不到（2026-10-05）。**本轮只跑 D7–D12**，跑完 D12 的 QA 门即停；
D13（技术验证）/ D14（真下单）/ D15（联调演练）保持 pending，等甲方资源到位再开新会话跑。D13 只依赖 D8，资源一到可以直接插队。

**本轮执行调整（Kevin 2026-10-06）**：减少重复与穷举测试，保留关键功能、权限、订单金额、幂等、资金与并发不变量的验证；每阶段仍由独立QA判断通过。样本不足、测试范围和类似技术口径问题由执行者在既定红线内自行调整并落盘，不因这类问题停下来等人。202在≤15次一次性录制预算内取得少量真实响应，缺类/HTML/简介可用明确标注的合成夹具补齐；报告区分真实平台已验证与合成场景已验证。外部请求上限、QA/返工/E2E零真煤炉、不改主miniapp、不push、不合staging、停于D12均不变。

**外部替身白名单**（与一期 wxMOCK 同一口径——被替换的是外部依赖，不是业务数据）：

| 外部依赖 | dev / QA 用什么 | 开关 |
|---|---|---|
| 煤炉读（搜索 / 详情 / 卖家简介 / 短链 / 图片） | 日本服务**回放样本集**（GZ-SNAP-202 录制） | `GATEWAY_READ_SOURCE=replay` |
| 煤炉写与登录态读（下单 / 对账 / 交易巡检） | 日本服务 **fake 驱动**（可脚本化结果 + 账本） | `GATEWAY_DRIVER=fake` |
| 阿里云机器翻译 | mock 翻译实现 | `gz.jp.snap.translate.provider=mock` |
| 微信支付 | 一期已有的 mock 通道 + simulate-callback | 现有 |

- 业务数据仍须真 seed + 真库对账，L1「禁自造数据自证」照常适用；fake 账本、回放样本、mock 翻译**不算**自造业务数据。
- **真煤炉请求预算**：只有 GZ-SNAP-202 的 live 测试（单次 ≤5 次）与回放样本录制（一次性 ≤15 次）可以打真煤炉，出口是 Kevin 的个人代理 IP。
  **QA 门、返工循环、E2E 一律不打真煤炉**；不许写任何循环或批量请求。
- D9 起 QA 需要日本服务在本地跑着：`cd code/main/mercari-gateway && docker compose up -d`（默认 replay + fake）。

**提交**：每个仓在各自的 `feat/jp-snap` 上按 zhixing 的分支模型做；**不 push、不合 staging**（Kevin 自己决定何时推）。
`mercari-gateway` 由 GZ-SNAP-201 `git init` 新建，无远程。

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

| lint | 结果（2026-10-03，二期拆完） |
|---|---|
| `coverage_lint` | ✅ 51 ticket × 91 条需求，在范围 80 条，**漏拆 0 / 镀金 0**；待澄清 3 条（REQ-SNAP-009 / 060 / 062，甲方侧，见二期确认单） |
| `authority_lint check` | ✅ 345 条权威 × 51 ticket，锚点全部有效、无悬空；快照已打 |
| `dag_lint` | ✅ 无结构性错误（exit 2，仅 C5 启发式 warning） |

**lint 运行方式**（本工作区路径非默认，必须带参数；需要装了 PyYAML 的 python，本机为 `/opt/homebrew/bin/python3.11`）：
```bash
cd doc/jp
python3.11 ~/claude-config/skills/xuqiu/scripts/coverage_lint.py --req requirements.yaml --tickets tickets --write-back
python3.11 ~/claude-config/skills/xuqiu/scripts/authority_lint.py --authority authority --tickets tickets --req requirements.yaml check
python3.11 ~/claude-config/skills/xuqiu/scripts/authority_lint.py --authority authority --tickets tickets --req requirements.yaml render --out authority/_rendered
python3.11 ~/claude-config/skills/zhixing/scripts/dag_lint.py tickets
```
（`render` 不带 `--out` 会写到 `doc/jp/doc/authority/_rendered`，是错的位置。）

### 已知 lint warning 与处置

- **REQ-SYS-004 被 5 个 ticket 认领**（阈值 4）：该需求原文「新建独立小程序，后端共用现有 admin」
  本身就是一条粗需求，天然横跨 4 个 SYS 改造点 + 新小程序登录。非 req_refs 乱贴，保留。
- **MENU 断言 C5 warning**：C5 按关键词找 `getRouters` 字面量。本项目 4 处 MENU 断言实际断的是
  path 非空 + component 非空 + **父级存在于 sys_menu**（防错父级），实质强于只调 getRouters；
  另在 GZ-JP-108 补了一条真调 `getRouters` 的断言。
- **STATE / API 断言 C5 warning**：run 是 `mvn test -Dtest=X` 与 `node run.mjs x`，
  C5 对这类命令天然失明（skill 自述的已知盲区）。真实强度检验走变异测试，见下。
- **二期 accept 的写法约定**：
  - mvn 单测类断言统一「先删旧 surefire 报告 → 跑 → grep 报告 `tests≥1 且 failures=0`」，不用 `| tail` 管道（管道会吞掉 mvn 的退出码，
    且 `-Dsurefire.failIfNoSpecifiedTests=false` 下测试类不存在也会绿——实现前必须是红的）。
  - 每条 accept 带一行 `counterfeit`：写明实现被改成什么样时这条会红。写不出来 = accept 太松。
  - `bash doc/jp/_accept/*.sh` 两条（304 并发、305 故障注入）是本 ticket 产出的脚本，C5 看不见内容；脚本必须自带反 stale 前置
    （8080 上的 jar = 当前 commit），断言要打在两侧独立数据上（fake 账本 vs `gz_jp_refund` / 接口返回 vs 库）。

### 建议的变异测试（蓝图冻结后）

抽 20% accept 注入已知类事故看是否仍绿，优先这三条：
1. GZ-JP-106：故意允许一次状态倒退 → 断言应红
2. GZ-JP-107：故意把退款金额改成整单总额 → 断言应红
3. GZ-JP-101：故意把菜单 path 置空 → 断言应红

二期优先（照各 accept 的 `counterfeit` 行注入）：
4. GZ-SNAP-305：对账把「not_found + sold_out」改回判失败退款 → 对账断言应红
5. GZ-SNAP-305：超时后把 executing 重置为 queued → 故障注入脚本应红（账本点击 2 次）
6. GZ-SNAP-306：shipping_diff 回调走一期落账 → 差价退款断言应红
7. GZ-SNAP-304：去掉 `FOR UPDATE` → 并发脚本应红
