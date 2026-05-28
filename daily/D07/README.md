# D07（Kevin 口径 d6）— V1.0 收官：资讯 CMS + 看板 + 支付通道 + 集成回归

> 日期：2026-06-04（周四）
> 阶段：**V1.0 实施期 day 6 / 最后一天** ⭐
> 上一日：[D06](../D06/README.md) ｜ 下一日：[D08](../D08/README.md)（V1.1 头一天，6/16 周二起；6/05-6/15 为 buffer + staging 部署 + 客户演示 + 风格统一调整窗口）

---

## 今日目标（V1.0 最后一公里）

- **主线 1**（运营内容）：甲方运营端文章 CRUD + 富文本编辑器 + 定时发布 cron → 资讯模块完整闭环（GZ-NEWS-003 + GZ-NEWS-004）
- **主线 2**（数据观测）：基础数据看板（用户 / 预约 / 资讯阅读三类非交易指标），cron 每 5 分钟刷新 → admin 首页 KPI 卡片可用（GZ-ADMIN-003）
- **主线 3**（支付通道）：微信支付 V3 SDK 集成 + 0.01 元测试单端到端打通（统一下单 → prepay_id → wx.requestPayment → 微信回调 → 后端验签 + 幂等 + 落 paid）→ V1.0 通道层就绪（GZ-PAY-001）

**本日 4 ticket 完工后 = V1.0 30 ticket 全闭环**。Kevin testing-human 阶段除了单 ticket 验收外，**必须跑一遍 V1.0 端到端**：
微信登录 → 浏览资讯 → 拼豆预约（选店/选时段/选座/绑手机/提交）→ 核销码生成 → 后台核销 → 后台看板数据自增 → 后台资讯 CMS 发文 → mp 端能读到。

完工后 D08 起进 V1.1 开发期（6/16 周二），6/05-6/15 共 11 天 buffer 用于：staging 部署 / 客户验收演示 / **风格统一调整窗口（6/10-6/14）** / V1.0 残留 bug 修复。

## Ticket 清单（4 个，2 串行 + 2 并行）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-NEWS-003 | 后台资讯 CMS（富文本编辑） | M | GZ-SYS-005 ✅(D02) | pending |
| GZ-NEWS-004 | 资讯定时发布 cron | S | GZ-NEWS-003 | pending |
| GZ-ADMIN-003 | 基础数据看板（非交易指标） | S | ADMIN-001 / 004 + SYS-003 + BEAN-008 + NEWS-001 ✅ | pending |
| GZ-PAY-001 | 微信支付 V3 商户号 + 通道 HelloWorld | M | GZ-SYS-001 ✅ + 商户号资料 D03 已启动 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖说明**：
- NEWS-003 → NEWS-004 **串行**（定时发布 cron 需要 article schema 落地后才能扫描 due 草稿）
- ADMIN-003 + PAY-001 与上面 + 彼此 **并行无依赖**（看板读已有表 / 支付通道独立链路）
- 主线程派单顺序建议：同时 spawn 三个 — NEWS-003 / ADMIN-003 / PAY-001；NEWS-003 ✅ 后再 spawn NEWS-004

## 派单方式

**整日触发**（推荐）：
```
开始 d6
```

**单 ticket 触发**：
```
@coder 做 D07/GZ-PAY-001
```

主线程动作：
1. 读 D07/README.md（本文件）+ 依赖图
2. **并行** spawn：GZ-NEWS-003 / GZ-ADMIN-003 / GZ-PAY-001
3. NEWS-003 ✅ 后 spawn GZ-NEWS-004
4. 4 个 ticket 全部 ✅ → 主线程提示 Kevin **先单 ticket testing-human → 通过后跑 V1.0 端到端回归**

## 今日特殊约束 ⭐ V1.0 收官

### A. 商户号资料时序风险（PAY-001）

- 商户号申请 5-10 工作日审批；甲方资料 D03（5/29 周五）启动 → D07（6/04 周四）为第 6 工作日，**理论刚到位但不保证**
- **降级策略（写在 PAY-001 §AC 中）**：
  - 商户号已下证（mch_id + cert + api_v3_key 全部到位）→ 走真实 0.01 元测试单端到端
  - 商户号未到位 → 本 ticket 仅做 **SDK 集成 + 配置抽象 + mock 测试**（用 ruoyi `wx-java-pay` 测试桩 / WireMock 拦截统一下单 + 回调），真实通道测试推到 6/05-6/12 buffer 期，Kevin 收到证后 1 小时内补打 0.01 元真单 ✅
- **PAY-001 不阻塞 V1.0 完工**：合同 §2.1 V1.0 范围仅要求"通道调通"，mock 链路绿 + 真实链路在 buffer 期补打即视为完工

### B. V1.0 端到端集成回归（4 ticket 完工后必跑）

testing-human.md 增量章节 §V1.0 集成回归（Kevin 一遍 happy path 走完）：
1. 微信登录（SYS-002 wxMOCK 或真实 AppID）→ 看到首页
2. 资讯列表 → 点详情 → 阅读量 +1（mp 端 NEWS-001/002）
3. 拼豆预约：门店 → 时段 → 座位 → 绑手机 → 提交 → 拿到核销码 QR（BEAN-001~005）
4. 后台核销：扫码 / 输入核销码 → status used（BEAN-006/007）
5. 后台资讯 CMS：新建一篇 → 立即发布 → mp 端能读到（NEWS-003）
6. 后台数据看板：刷新 → 看到本次新增的用户 1 / 预约 1 / 阅读 1（ADMIN-003，等 cron 5 min）
7. 支付通道：admin 工具页发起 0.01 元测试单 → 微信确认支付 → 后台显示 paid（PAY-001，如商户号到位）

任一环节断 → 优先级 P0 raise，6/05-6/06 修复，不下挪到 V1.1。

### C. 设计冻结期纪律（与 D02-D06 同款，最后一天提醒）

- admin（NEWS-003 / ADMIN-003）走 ruoyi 默认 + plus-ui BizTable + Element Plus 默认组件；**不参考 mockup 视觉**，仅参考 mockup 的字段 / 卡片布局结构
- NEWS-003 富文本编辑器**优先复用 plus-ui 已集成的编辑器**（如有 wangEditor / tinymce / TipTap 任一即用，**不引新依赖**）；如 plus-ui 无现成编辑器 → 引 wangEditor v5（最轻 / 中文文档完备）
- mp 端本日无新页面（NEWS-001/002 已在 D06 完工）
- 视觉评判窗口在 6/10-6/14 风格统一阶段，本日 Kevin testing-human **不评判 admin 颜色 / 间距 / 圆角 / 字号**，只评判功能

### D. menu_id 段（CLAUDE.md §6 #6 锚定）

- NEWS-003：admin 端「资讯管理 → 文章列表」menu_id **8001** + perm `gz:news:article:list/add/edit/delete/publish/offline`；分类筛选走 sys_dict（dict_type=`gz_news_category`，D06 已落）
- NEWS-004：无新 menu，复用 NEWS-003；新增 ruoyi `sys_job` 一行 `gz_news_publish_due_job` cron `0 * * * * ?`（每分钟）
- ADMIN-003：menu 挂「数据看板」menu_id **300**（ruoyi 自带占位），权限 `gz:dashboard:view`；后台首页路由 `/index` 改为 `/dashboard`（如 plus-ui 默认未改）
- PAY-001：admin 端「支付管理 → 通道配置」menu_id **5101** + perm `gz:pay:channel:list/edit` ｜「支付订单（测试）」menu_id **5102** + perm `gz:pay:transaction:list`

### E. DDL 文件命名（CLAUDE.md §6 #5）

- NEWS-003：`V202606041000__GZ-NEWS-003-alter-gz_news_article-cms-fields.sql`（gz_news_article 在 NEWS-001 D06 已落地基础字段；本 ticket 按需 ALTER 补 `schedule_publish_time` / `content_html` MEDIUMTEXT / `video_urls` 等编辑器相关字段；§0 自检确认 D06 NEWS-001 DDL 范围）
- ADMIN-003：`V202606041100__GZ-ADMIN-003-create-gz_dashboard_snapshot.sql`（看板快照表，cron 每 5 min 写一行；表名 / 字段在 ticket 卡内定义，doc/11 尚无对应章节 — 见缺口段）
- PAY-001：`V202606041200__GZ-PAY-001-create-gz_pay_channel-and-transaction-and-callback_log.sql`（三表一文件，doc/11 §4.1/4.2/4.3 锚定）

### F. 强约束（合同层 — 本日 PAY-001 关键）

- **微信支付商户号必须挂"成都谷子宇宙贸易有限公司"主体**（合同 §2.3 / CLAUDE.md §7 #12）— Kevin 资料启动时核对，不能用乙方主体（二清违规）
- **V1.0 仅通道调通**（合同 §2.1 V1.0 范围 / CLAUDE.md §7 #12）— 不接业务订单（扭蛋 / 预购 V1.1 才接）；本 ticket 跑通的 0.01 元用 business_type=`test` + out_trade_no=`TEST-yyyyMMdd-000001`
- **回调验签 + 幂等 + 异常告警**（拆解 §2.2 AC 3）— 三者缺一不可，PAY-001 §AC 强约束

## 与昨日 reports 对账（D06）

D06 `summary.md`（预计待生成）抓"对下游 ticket 的提示"段：
- ✅ NEWS-001（资讯列表）+ NEWS-002（资讯详情）+ gz_news_article 表已落地（D06 完工）；本日 NEWS-003 在此基础上加 admin 端 CRUD + 富文本，**不重复落表**，按需 ALTER
- ✅ BEAN-008（预约列表查询服务）D06 完工，本日 ADMIN-003 看板的"今日预约 / 累计预约"指标直接读 gz_bean_booking 表
- ✅ SYS-003 用户表 / NEWS-001 资讯阅读计数已就位 → ADMIN-003 看板数据源齐
- ⏳ 商户号资料：Kevin 5/29 D03 已启动甲方提供，本日如未下证走降级（特殊约束 §A）
- ⏳ 阿里云 OSS bucket：NEWS-003 富文本插图复用 SYS-005（dev MinIO，prod 切阿里云 OSS）— bucket 是否真实化由 Kevin 推进，本 ticket dev 链路 MinIO 即可

## 完成判定（DoD）

- [ ] 4 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] testing-human.md 单 ticket 段 + §V1.0 集成回归段 全勾
- [ ] PAY-001 真实 0.01 元测试单（如商户号到位）/ 或 mock 链路全绿（商户号未到位降级）
- [ ] cat reports/*.md > summary.md 已生成
- [ ] **V1.0 30 ticket 全部 ✅** ⭐ — 在 D07/summary.md 末尾写一行「V1.0 收官，开发周期 D01-D07 共 6 个工作日，合同 §2.2 硬期限 6/15 提前 11 天达成」

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 ★ | 商户号 6/04 未下证 → PAY-001 仅能跑 mock 链路 | 降级方案已写入 PAY-001 §AC（mock + 真实分离实现），buffer 期补打真实测试单 ✅；不阻塞 V1.0 收官 |
| R2 | NEWS-003 富文本编辑器选型分歧（wangEditor vs tinymce vs TipTap） | 默认查 plus-ui 已集成的 — 有就用，没有就 wangEditor v5；如 Kevin 倾向其他选项 → 写 ADR-0002 决策 |
| R3 | ADMIN-003 看板查询性能（大表全量 COUNT） | V1.0 数据量小（用户 < 100 / 预约 < 50 / 阅读 < 500），全量 COUNT 单次 < 50ms 可接受；cron 5min 间隔写快照表（gz_dashboard_snapshot），admin 前端读快照不读源表 |
| R4 | V1.0 集成回归发现跨 ticket bug | 接受 — 6/05-6/06 修复窗口；超过 P1 优先级的 raise 给 Kevin 决策是否切 V1.0 上线日 |
| R5 | NEWS-003 富文本 XSS 漏洞（白名单过滤不严） | 用业界成熟库 jsoup `Safelist.relaxed()` + 额外去除 `<script>` `<iframe>` `on*` 事件属性；写单测覆盖至少 5 个 XSS payload |
| R6 | PAY-001 回调验签失败率 | dev / staging 用微信支付沙箱（如有）或 mock；prod 上线前用真实 0.01 元测试单 + 微信侧后台核对回调签名 |

---

## 日终 closing 命令

```bash
cd doc/daily/D07
cat reports/*.md > summary.md
# Kevin testing-human OK 后再 commit
git add -A && git commit -m "D07 (d6): 资讯 CMS + 看板 + 支付通道 + V1.0 集成回归"
# 然后写 D08/README.md（V1.1 头一天，6/16 周二起；6/05-6/15 buffer 不写 daily README）
```

**V1.0 收官**：本日完工后 V1.0 30 ticket 全闭环。6/05-6/15 为 buffer 期（staging 部署 / 风格统一调整 / 客户演示），不按 daily 节奏跑 ticket；6/16 周二 D08 起进 V1.1 27 ticket。
