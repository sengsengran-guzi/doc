# 变更记录 —— 谷子宇宙拼团

一行一次改动。「波及 ticket」列粘 `authority_lint.py impact` 的输出，不手填。

| 日期 | 改了什么 | 波及 ticket | 谁提的 |
|---|---|---|---|
| 2026-08-03 | 初始需求：拼团 + 代切两块业务 | — | 甲方 |
| 2026-08-04 | Q1-Q5 答复：运费店员手填 / 每款显示状态 / 原路退款 / 自建直连 / 自动下单；分类改「按场」 | — | 甲方 |
| 2026-08-05 | **推翻运费改全包邮**；砍线下代客下单；代切降二期；确认打包客人不可见 | REQ-ORDER-002 dropped | 甲方 |
| 2026-08-05 | 仓库位置定同 repo `code/main/miniapp-jp/`；范围定「极简包 + 保留自动退款」 | 全量 | Kevin |
| 2026-08-05 | UI 拍板：履约看板按客人聚合 / 订单详情按状态分组 / 首页做聚合 | UI:mp.home, UI:mp.order_detail | Kevin |
| 2026-08-06 | 设计方案两层全部选定：视觉基调 A（延续现有）/ 商品详情 A / 购物车 A；新增权威锚 UI:global.theme | GZ-JP-001（加锚）| Kevin |
| 2026-08-06 | 补 D0 文档任务：ADR-0019 / ADR-0020 / CLAUDE.md 更新（原 21→24 ticket）| 新增 GZ-DOC-001/002/003 | Kevin |
| 2026-08-06 | D0 实测修正权威：① 「8 处 @ConditionalOnExpression」措辞不准，实为 real 侧 4 处 Expression + mock 侧 4 处 Property ② 补明 `gz.pay.client-mode` 是**进程级全局**开关、与 appid 无关，一期不 Map 化 | impact 反查 8 个：GZ-DOC-003 已完工但产出已含新口径且 accept 无关→**不重做**；余 7 个未开工，自然读新版 | subagent 实测回流 |
| 2026-08-06 | **GZ-PAY 退款链路实测**：只支持「一单一次全额」（RefundApplyBo 无金额入参 / createRefunding 重复退款闸 / refunded 终态），通道层 IWechatPayClient.refund 本就支持指定金额 | GZ-DOC-002（产出已含此发现，非受害者，不重做）· GZ-JP-107（工作量 L→XL，按新建一套退款链路估） | D0 subagent 硬查回流 |
| 2026-08-06 | **行级退款路线拍板：jp 域独立退款入口，只共用通道层**（不动拼豆/回收的资金链路） | GZ-JP-107 · ADR-0020 §3 · phase-plan D5 三处口径已收敛 | Kevin |
| 2026-08-06 | D0 QA 门 FAIL 修复：ADR-0019 删除「切 wxMOCK 会让真支付失效」的假陈述 + 补 §5（gz.pay.client-mode 保持全局的决策与推翻条件）；ADR-0020 补 §4（order_item.source 预留维度）；field-ssot 的 menu 子段与 CLAUDE.md/ticket accept 对齐；GZ-SYS-020 §0 的 grep 路径补 pay/shipping/（原路径只覆盖 6/8 处，会触发假 STOP） | GZ-SYS-020（§0 修正）· GZ-JP-101/102/109/108（menu 子段口径） | 干净 QA subagent |
| 2026-08-07 | GZ-JP-101 实测发现 4 张卡的 MENU accept 引用 `sys_menu.del_flag`，ruoyi 官方基线该表无此列（菜单物理删非软删）——去掉 3 处 `del_flag='0'` 后语义等价 | GZ-JP-101/102/108/109（accept 段修正） | GZ-JP-101 impl subagent 实测回流 |
| 2026-08-07 | mp 可见性模型放宽：101/103 完工时只让 open 场可浏览，与 201/202 已拍板的「三态分组」「已结束仍可浏览、加购置灰」不符——201 开工前补齐 isVisible(open\|closed) 双闸 + eventBookable 字段，isBookable(仅open) 不变继续供下单用；避开「窗口已过的 draft 惰性判定成 closed 而漏出去」陷阱 | GZ-JP-101/103（服务层扩展，accept 断言未改）· GZ-JP-201/202（前端契约新增 status='closed' / eventBookable） | 主线程 + kevin-coder 实测回流，详见 doc/jp/tickets/_visibility-extension-pre-201.md |

| 2026-08-07 | GZ-JP-107 完工回写 `FLOW:F-JP-04.step3`：退款回调走独立端点 `/api/gz/jp/pay/refund-notify`（jp 退款单在 `gz_jp_refund`，共享回调路径会 404） | impact 反查 GZ-JP-107 —— 它就是这处改动的产出方，非受害者，**不重做**（2026-10-03 二期拆解前补登并打快照） | GZ-JP-107 impl 回流 |
| 2026-10-03 | **CR-20261003-01 二期代切启动**（A1 官方合作 / A2 接入官方合作商均失败 → 自建直连）。REQ：SNAP-001~007 转 pending、008 dropped、010 转 clarify；新增 SNAP-011~044 / 060~062 / 064（33 条，含 7 条明确不做 deferred）+ ORDER-011 / FULFILL-008（一期缺口）。权威：+FLOW:F-JP-05~11、+5 表（gz_jp_snap_item / _purchase / _account / _term / gz_jp_fx_rate）、补登 gz_jp_refund、+10 UI 记录、+ownership.yaml（9 条 OWN）；ADR-0025（proposed） | impact 反查 GZ-JP-105 ← `FIELD:gz_jp_order_item.source` / REQ-SNAP-004：变更为纯增量（source 加值 snap、product_id 改可空待确认），105 的 3 条 accept 不涉及 source / product_id 约束 → **不重做** | Kevin（§0.3 七问 + 最终想法） |
| 2026-10-03 | **设计门通过**：mp 代切搜索选 B（tabbar 三格 首页 / 煤炉 / 我的）· mp 代切详情选 A（到手价 + 日元参考）· admin 代切下单选 A（独立页三 tab）· ADR-0025 §5 一期两表结构改动（订单行 product_id 可空 + snap_item_id；退款表唯一键加 refund_type）确认 → ADR-0025 accepted | impact 反查 0 个 ticket（二期 ticket 未拆） | Kevin |
| 2026-10-03 | **交接审查拍板 + 蓝图补洞**（Kevin 五问全按推荐）：① 对账「查不到 + 已不在售」改为立即转人工，对账只自动得出成功、从不自动得出失败（REQ-SNAP-029 note / F-JP-07.step5）② 排期：技术验证等甲方账号插队，不阻塞前面的工作（REQ-SNAP-064 note）③ 新增 REQ-SNAP-065 东京服务器 + ISP 代理甲方采购付费（clarify）④ 新增 REQ-SNAP-045 煤炉 tab 图标 AI 先画 ⑤ `UI:global.theme` 主色订正为实际的品牌绿 #33b36b（原写朱红 #c8452f，与代码不符）。工程补洞：冷却中=等待而非转人工（F-JP-07.step1）· 下单前运费改到付→failed(shipping_changed)→转人工不退款（F-JP-07.step2）· shipping_diff 退款不碰订单行、不参与 rollup（F-JP-08.step2 / FIELD:gz_jp_refund.refund_type）· 卖家取消可手工标记（+F-JP-09.step1b）· 代切行评价前后端拒绝推进（F-JP-09.step3）· 关单先 closeOrder（F-JP-10.step1）· IWechatPayClient 补退款查单（F-JP-10.step2）· +FLOW:F-JP-12 日本服务接口契约（含 fake / disabled 驱动）· UI:mp.snap_detail 删去与方案 A 矛盾的「汇率」字样 | impact 反查 GZ-JP-001 ← `UI:global.theme`：纯文档追认现实（代码 c-tokens 本就是 #33b36b），其 accept 不涉及色值 → **不重做**；其余变更锚均为二期内容，由本轮新拆 ticket 锚上 | Kevin |
| 2026-10-03 | **纸面推演**（[19-代切链路纸面推演.md](19-代切链路纸面推演.md)）回流：提交订单时实时复查（已售出 / 涨价拦在付款前）· 对账查不到不论是否已售出都等满 3 轮再转人工 · 新增失败原因 account_unpayable（余额不足：转人工 + 该账号暂停，不关全局开关）· 账号可派单条件加「pause_reason 为空」· 到付实际运费改在「已到仓」时填并退差价（着払い到仓才付）· 人工填成功实际价不得高于锁定价 · 交易取消可从已发货出发（丢件 / 事务局取消）· 履约守卫只拦 admin 入口、系统退款路径走内部方法 · 支持 merc.li 分享短链（+`/v1/resolve`）· ruoyi 侧按用户 / IP 限流 · 日本服务带远程登录工具。待拍板：K1 支付单超时后仍可付款（现存，波及拼豆 / 回收 / 拼团）· K2 煤炉 Shops 商品 | impact 反查 12 个：GZ-SNAP-001 / 201 / 202 / 203 / 302 / 304 / 305 / 306 / 307 / 401 / 405 / 504 —— 均未开工，正文与 accept 已同步改，**无需置 stale** | 纸面推演（Kevin 批准做 A） |
| 2026-10-03 | **纸面推演拍板 K1 / K2**：K1 修共享支付通道「过期后仍可付、付了被吞」——新增 REQ-ORDER-012 + `FLOW:F-JP-06.step4b` 迟到付款兜底 + D7 新卡 GZ-PAY-106（统一下单带 time_expire、本地超时同时 closeOrder、迟到付款记 late_paid 不吞）；prod 只读核查 2664 笔支付单无历史损失。新增 REQ-SNAP-046 本人再提交返回原订单继续支付（`F-JP-06.step3`）。K2 这一期只卖个人卖家：新增 REQ-SNAP-047，搜索 / 详情过滤 item_type=shops、粘贴 Shops 链接提示暂不支持（`F-JP-05.step1/4`、`F-JP-12.step2/3`） | impact 反查 5 个：GZ-JP-110 / GZ-PAY-106 / GZ-SNAP-202 / 302 / 304 —— 均未开工，已同步；另 GZ-SNAP-501 / 001 手工同步（`UI:mp.snap_search.input` 的 note 改动 impact 未捕捉，UI 区块 note 不进 hash） | Kevin |
| 2026-10-04 | **煤炉只读探测回流 + Kevin 选 A**（[READ-PROBE-2026-10-03.md](_spike/mercari-probe/READ-PROBE-2026-10-03.md)，10 次匿名请求全部成功）：新增 REQ-SNAP-048 卖家写明拒绝代购的商品不可购买（扫标题 / 描述 / 卖家简介，先于转人工判；+`FLOW:F-JP-12.step3b` 卖家简介接口）· 分类白名单可配任意层级、作为搜索条件下推、详情按末级 / 父级 / 根复核 · 评价期限默认 48h→24h（卖家要求到货 24 小时内评价）· 契约补实测字段来源（itemType / shippingPayerId 编码 / 图片域名）· REQ-SNAP-010 补「采购账号须有交易记录与评价」 | impact 反查 10 个：GZ-SNAP-101 / 202 / 302 / 303 / 403 / 502 内容已同步；301 / 306 / 307 / 402 仅被父级描述改动连带，内容无需改 —— 均未开工 | 只读探测 + Kevin |
| 2026-10-05 | **执行前复审**（甲方三样资源暂时拿不到 → 本轮只跑 D7–D12）：日本服务加读源开关 `GATEWAY_READ_SOURCE=live|replay`，dev / QA 默认回放录制样本（样本覆盖 auto / 到付 / コメント必須 / 拒代购 / 専用 / Shops / 已售出 / 白名单外），避免开发与 QA 反复经 Kevin 个人代理 IP 打真煤炉、也让 E2E 数据确定；翻译做成 aliyun / mock 可切换，dev 无 AccessKey 不阻塞；phase-plan 补「二期执行口径」（外部替身白名单、真煤炉请求预算、只跑 D7–D12、不 push） | impact 反查 10 个（均因 `FLOW:F-JP-12` body 改动连带）：GZ-SNAP-201 / 202 内容已同步，302 / 501 / 502 手工同步（翻译 mock、E2E 用回放样本）；001 / 203 / 204 / 301 / 303 / 304 / 305 / 307 内容无需改 —— 均未开工 | 复审 |

## 2026-10-05 — GZ-SNAP-102 状态机口径（Kevin 定方案 A）
- 一期 GZ-JP-106 状态机本就允许任意非终态→purchase_failed（拼团行亦然，`purchaseFailedIsBranch` 守着），原口径「await_seller_ship→purchase_failed 仅对代切行放开、拼团行仍被拒」与「一期行为零变化」矛盾。
- 改为：按来源判定的状态机入口——snap 行允许该转移；batch 行全部状态对与一期结果逐一相同，不收紧。
- 落点：`authority/flows.yaml` FLOW:F-JP-09.step1、`phase-plan.md` D7 QA 范围、`tickets/GZ-SNAP-102` What #5 + accept #0。impact 波及 GZ-SNAP-102（返工）/ 204 / 307（均未开工，正文无旧口径）。

## 2026-10-06 — 样本预算与验证范围（Kevin授权继续、自行调整类似技术问题）
- 202的完整双份真实录制无法保证≤15请求，改为预算内少量真实响应+缺类/HTML等明确标注的合成夹具；保留八类回放覆盖及来源清单，报告列未实测范围。真实请求预算和所有外部红线不变。
- 回流 FLOW:F-JP-12 body、202 What#6/#6b/accept#0名称、phase-plan执行口径。impact反查10张：001/201/202/203/204/301/303/304/305/307。202尚未实现，按修订口径续做；201读取器本就加载本地JSON，接口/鉴权/幂等/accept未受影响，不重做；其余未开工且接口契约不变，无需改业务实现。302/501/502消费样本，派单需告知来源区分。
- 减少重复和穷举测试，保留关键功能与资金不变量，阶段独立QA门仍执行。类似样本/测试/技术口径问题在用户红线内自行决策并记录，不停等确认。
- 交接已记的304图片兜底缺字段一并补齐：FIELD:gz_jp_order_item.product_snapshot_json.snap 增可空mainImageUrl，304声明字段锚；转存失败保留原图，读侧改写备案CDN/自有代理，不暴露外网直链。102只被字段说明增补连带，旧快照兼容不重做；304负责落新字段和读侧兜底，其他读取方维持旧快照可空兼容。

## 2026-10-06 — D9 回放查询接入调整（用户授权自行处理）
- 302 下推分类参数后，202 回放按完整查询匹配，原无分类样本无法命中。主线程在 gateway task/D9 增加三关键词 × 三排序 × `[745,975,980]` 的9个纯离线样本变体，逐件登记 synthetic，不增加真实请求，不改外部接口或权威业务口径。
- 保留 Shops / 分类外卡片作为 ruoyi 过滤的对抗输入；9个本地回放与排序检查通过，镜像已重建。该改动为 D9 测试资产（gateway@7f115a8），超出302后端touches由主线程负责，D9 QA一并审计；不影响D8产品代码，未重跑D8全套。
- 搜索卡片仅给末级 category_id，无 ancestry；初始白名单在父745外补已确认975/980供独立过滤。未知搜索分类保守拒绝，详情用完整lineage核对，不以“上游带了分类条件”代替ruoyi过滤。
- D9图片回放补9个本地JPEG占位路径（gateway@45dfa95），原样复制既有miniapp-jp头像并标为synthetic placeholder，不改真实采集JSON/不冒充煤炉照片。实际本地代理200、image/jpeg、有效940×940；真实请求新增0。
- D9实际联调首次因本地启动脚本未传GZ_JP_GATEWAY_SECRET返回上游不可用；共享restart脚本现从既有未跟踪gateway.env按数据读取单个键（不source、不打印、不提交密钥，显式环境变量优先）。重启仍指纹bc01498f1，187迁移验证通过，继续联调。

## 2026-10-06 — 303搜索参考价兼容调整
- 搜索摘要契约没有shipping_payer，严格详情报价校验使列表参考价为空。按用户授权，摘要未知运费承担时仅计算商品价+固定费参考值，不臆测到付费用；详情与提交仍要求完整payer并锁定总报价，实际成交口径不变。补1个报价用例及实际列表检查，不扩大重复回归。

## 2026-10-06 — 本地后端进程生命周期修复
- 已复现工具会话结束会清理nohup子进程，人工keeper虽能保活但无法满足D10自动故障重启。共享restart脚本保持唯一入口，macOS改为专用launchd标签托管此开发后端；精选环境由权限600的临时JSON传递，secret不入argv/日志/git；Linux保留原nohup分支。修正mkdir锁必须实际取得才允许继续，防止等超时后误当持锁。收尾只移除此专用任务。

## 2026-10-06 — 304提交复查保守准入
- 报价后出现需人工条件时，提交仍可按锁定金额建单，但快照准入取报价/实时复查的保守结果（任一manual则manual；实时blocked拒单），防止付款后误入自动购买。同步字段说明和FLOW:F-JP-06.step3；不改金额、汇率或旧batch快照。
- impact反查仅102/304：102已完成的来源字段约束和batch快照均不变，无历史snap订单需迁移，不重跑；304在当前实现和关键准入检查中落实，独立D9 QA核对该权威说明。

## 2026-10-06 — D9验收装置调整
- 宿主审批出现多次超时（未执行，不是安全拒绝或产品FAIL）；用直接工具命令继续。race反stale确认生产9f6aec33a，首次快照因MySQL IN字面量collation混合失败，尚未创建数据，现明确二进制UTF8排序规则。test-only提交不重启后端，反stale核生产路径提交+源码/jar/JVM时间。
- 独立QA发现302 Filter测试宽泛config stub污染303 gate配置，产品fail-closed正常；375621d34仅将fixture限定filter key。按最新授权只复跑该失败类和一轮真实10并发/付款竞争，复用已绿证据，不机械三轮/变异。

## 2026-10-06 — 305证据上传接线
- 现有公共上传只接受图片且缺snap_evidence usage，无法持久化权威已要求的文本/HTML/JSON证据。305范围补gz-common的GzFileUsageType及GzFileServiceImpl两文件，限定该usage的后缀/MIME白名单，文档对象按application/octet-stream供下载，既有admin图片上传限制维持并验证。只补实现与touches，无新增依赖或业务蓝图变化。

## 2026-10-06 — 305故障装置卡点修复
- 本地ThreadingHTTPServer创建时getfqdn反向DNS阻塞，发生在restart/造数前；测试代理改用固定localhost名字并即时输出。首次中断实例已结束后才续跑，不并发造数。
- 共享restart一次停旧服务后launchd标签消失，等待8080超时；主线程补交同一次启动任务后新JVM启动，脚本增加等待旧标签退出，避免remove/submit重叠。此为本地运行装置修复，无真实煤炉请求。
