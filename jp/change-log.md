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

