# GZ-GACHA-104 ⭐ — 抽奖事务 + 防超卖（V1.1 最复杂 ticket）

**优先级**: P1
**复杂度**: L（V1.1 最复杂 ticket — 思考密度比 BEAN-004 更高，禁止快速过 §0 自检）
**关联 PRD**: doc/02-prd.md M2 §概率算法 + §并发与防超卖 + §异常分支
**关联拆解**: doc/02-需求拆解.md §3.3 第 787 行
**关联 mockup**: design/mockup/gacha-draw.html（结果展示页 — 仅布局参考；视觉以 C 系统为准，doc/13；出奖动画为 doc/13 §3.2 待建 Biz 组件。本 ticket 仅后端，UI 在 GACHA-105）
**关联 ADR**: 如本日实施时涉及"是否引入分布式锁框架 / 异步事件解耦" → 新建 ADR-0003
**依赖**: GZ-GACHA-101 + GZ-PAY-101 ✅(D08)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 重点反复读）

- **业务流**：doc/10-业务流权威图.md **§7 扭蛋抽奖流** **全文**，特别是：
  - §状态机（gacha_draw 状态：`pending_pay` → `paid` → `drawn` → `pending_delivery` → `delivered` / 失败态 `refunded`）
  - §并发控制（**SELECT FOR UPDATE** 锁奖品行 + DB 事务 + 退款补偿 三层防线）
  - §概率算法（归一化逻辑 — 与 GACHA-103 ProbabilityNormalizer 同一实现）
  - §异常分支（库存竞争 / 退款失败 / 支付回调延迟 / 网络中断 全场景）
  - §业务规则（**不做保底** PRD §4.1 / 抽完即下架）
  - 如 §7 不全 → STOP @product 巡检；临时参考 §3 拼豆并发结构作类比
- **字段表**：doc/11-字段权威表.md
  - §7.1 `gz_gacha_machine`
  - §7.2 `gz_gacha_prize`
  - **§7.3 `gz_gacha_draw`**（核心抽奖记录表 — 完整 DDL 来源 + 中奖物 snapshot 字段定义）
  - §1 全局公共字段
  - GZ-USER 订单表（V1.1 USER 系列已落，本 ticket 仅 INSERT 不动 schema）
- **UI 索引**：doc/12-UI-权威索引.md §MP-GACHA-DRAW（前端调用时序参考）
- **支付集成**：D08 PAY-101 reports（`IGzPayService.unifiedOrder()` + `refund()` 接口签名 / 错误码）

## What

mp 端用户在详情页（GACHA-103）点「单抽 ¥X」CTA 后到付款成功的核心后端业务逻辑：
1. 创建 pending_pay 抽奖记录（占位，关联机器 / 用户 / 待扣奖品池快照）
2. 调 PAY-101 `unifiedOrder()` 拉起微信支付（mp 端唤起）
3. 支付回调到达 → 进入抽奖事务：
   - DB 事务开启
   - `SELECT FOR UPDATE` 锁该机器全部 current_stock > 0 的奖品行
   - 校验库存（如为空 → 标记 draw status='refunded' + 异步退款）
   - 概率归一化（复用 `ProbabilityNormalizer`）
   - 随机抽取（`SecureRandom` + 权重区间）
   - 扣减中奖奖品 `current_stock -= 1`
   - 写中奖物 snapshot 到 draw 表（防后台改奖品后历史错乱）
   - 建待发货订单（INSERT GZ-USER 订单表 status='pending_delivery'）
   - 提交事务
4. 任何一步失败 → 整事务回滚 + 异步退款（PAY-101 `refund()` + 失败重试 3 次 + 失败入死信队列）

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606171100__GZ-GACHA-104-create-gz_gacha_draw.sql` 落表：
  - `gz_gacha_draw`（id / user_id / machine_id / machine_name_snapshot / prize_id 可空 / **prize_snapshot** JSON 字段(name+rarity+cover_url+public_value) / single_price 分 / out_trade_no 支付单号 / pay_status enum(`pending`/`paid`/`refunded`) / draw_status enum(`pending_draw`/`drawn`/`stock_empty_refunded`) / delivery_status enum(`pending_delivery`/`delivered`/`n/a`) / refund_reason 可空 / drawn_at 可空 / + 全局公共字段）
  - UNIQUE `uk_tenant_out_trade_no (tenant_id, out_trade_no)`
  - 索引 `idx_user_drawn_at (user_id, drawn_at DESC)`（GACHA-106 历史查询）
  - 索引 `idx_user_machine (user_id, machine_id)`（GACHA-107 图鉴查询）
- [ ] **AC 2**：mp 端 `POST /app/gz/gacha/draw/start`（参数 machine_id）：
  - sa-token mp-client → 拿 user_id
  - 校验机器 status='on_shelf' + 至少 1 奖品 stock > 0（否则返回 `MACHINE_EMPTY`）
  - INSERT `gz_gacha_draw`（status `pending_pay` + 价格 snapshot + machine_name_snapshot）
  - 调 `IGzPayService.unifiedOrder(outTradeNo, single_price, openid, ...)` → 返回 mp 支付参数 jsApiPayload
  - 返回 `{drawId, jsApiPayload}` 给前端唤起支付
- [ ] **AC 3**：支付回调（GZ-PAY-101 已建回调入口 `/external/gz/pay/wx-notify`）→ payService 处理签名 + 幂等校验后回调注册的 `GachaDrawPayCallback` Handler：
  - 把 draw.pay_status='paid'
  - 异步触发抽奖事务（`@Async("gachaExecutor")` 调 `executeDrawTransaction(drawId)`）
- [ ] **AC 4** ⭐ **核心抽奖事务**：`@Transactional(rollbackFor=Exception.class)` 在 `GzGachaDrawServiceImpl.executeDrawTransaction(drawId)`：
  1. 重读 draw（应为 paid + pending_draw 状态；其他状态返回幂等跳过）
  2. **`SELECT * FROM gz_gacha_prize WHERE machine_id=? AND current_stock>0 FOR UPDATE`**（锁所有候选奖品行）
  3. 如结果为空 → draw.draw_status='stock_empty_refunded' + INSERT refund 任务 + return（事务提交，异步退款）
  4. 用 `ProbabilityNormalizer.normalize(prizes)` 算归一化权重
  5. `SecureRandom` 抽取（生成 0~totalWeight 的随机 long，落在哪个奖品区间就中哪个）
  6. `UPDATE gz_gacha_prize SET current_stock = current_stock - 1 WHERE id=? AND current_stock > 0`（带 stock > 0 条件防超卖兜底；affected rows = 0 → throw 触发回滚）
  7. UPDATE draw（prize_id + prize_snapshot JSON + draw_status='drawn' + drawn_at=NOW + delivery_status='pending_delivery'）
  8. INSERT GZ-USER 订单表（status='pending_delivery'，引用 draw_id + prize_snapshot）
  9. 事务提交
- [ ] **AC 5** ⭐ **失败回滚 + 退款**：
  - 事务内任何 throw → 自动回滚（库存不扣 / draw 不变 / 订单不建）
  - 事务回滚后异步触发退款：`refundService.refund(outTradeNo, single_price, 'gacha_draw_failed')`
  - 退款失败重试 3 次（间隔 5s/30s/2min）；3 次仍失败 → 入死信队列 + 报警邮件给 Kevin
  - 退款成功 → UPDATE draw.pay_status='refunded' + draw_status='stock_empty_refunded'
- [ ] **AC 6** ⭐ **不做保底**（PRD §业务规则 4.1）：纯权重随机，不强制 N 抽必中 SR；不在 service 加任何"保底计数器"
- [ ] **AC 7** ⭐ **抽完即下架**：奖品 current_stock 扣到 0 时**自动从抽奖池剔除**（步骤 2 `WHERE current_stock > 0` 自然过滤；同步：如机器所有奖品 stock=0 → 异步标 machine.status='off_shelf' + 通知运营）
- [ ] **AC 8**：单测覆盖 6 个场景（每个 raw assertion）：
  - happy path（mock 锁 + 抽到非空奖品 + 库存扣 1 + draw 状态 drawn）
  - 库存空（mock SELECT FOR UPDATE 返回空 → status='stock_empty_refunded' + 触发退款）
  - 库存竞争（mock UPDATE affected=0 → throw + 回滚）
  - 退款失败重试 3 次（mock pay 抛 3 次 → 入死信）
  - 幂等（drawId 已 drawn → 跳过）
  - 概率随机性（10000 次抽样，每个奖品出现频次贴近权重比，χ² 检验 P > 0.05）
- [ ] **AC 9** ⭐ **reports 必须包含并发压测 raw output**：
  - 工具：`wrk -t10 -c50 -d10s` 或 `ab -n 200 -c 50`
  - 场景：机器只剩 1 个 SSR + 50 并发用户同时支付回调到达
  - 期望：DB 最终 SSR.current_stock = 0；恰好 1 个 draw 是 drawn 状态；其他 49 个 draw 是 stock_empty_refunded + 触发退款
  - reports/<T>.md 贴 raw SQL 验证 + wrk 输出 + 退款 log 摘录
- [ ] **AC 10**：写操作加 @Log；GachaDrawPayCallback 加幂等保护（基于 out_trade_no UNIQUE 兜底）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaDrawMpController.java`（`POST /app/gz/gacha/draw/start`）
  - `service/IGzGachaDrawService.java` + `service/impl/GzGachaDrawServiceImpl.java`（**核心事务方法 `executeDrawTransaction(drawId)`**）
  - `service/internal/GachaDrawPayCallback.java`（PAY-101 回调注册）
  - `service/internal/GachaRefundService.java`（退款 + 重试 + 死信）
  - `service/internal/ProbabilityNormalizer.java`（GACHA-103 已建，本 ticket 复用）
  - `service/internal/SecureRandomDrawer.java`（权重区间抽取，便于测试 mock）
  - `domain/GzGachaDraw.java` + VO + BO（含 PrizeSnapshot 内嵌结构）
  - `mapper/GzGachaDrawMapper.java`（含 `SELECT ... FOR UPDATE` 自定义方法）
  - `config/GachaExecutorConfig.java`（`@Async("gachaExecutor")` 线程池配置）
  - DDL × 1
  - `application-dev.yml` + `application-staging.yml` + `application-prod.yml` 加 `gz.gacha.refund-retry-intervals: [5s, 30s, 2m]` + `gz.gacha.alert-email: kevin@example.com`
- **小程序**：仅 `api/gz-gacha.ts` 加 `startDraw(machineId)` 调用 + 唤起 wx.requestPayment(jsApiPayload)；UI（动画 + 揭晓）在 GACHA-105
- **测试**：mvn 单测（6 场景）+ wrk / ab 并发压测 raw output + DB 客户端验证

## 备注

### 强约束 ★

1. **三层防超卖是不可绕过的兜底**（doc/10 §7 权威）：DB 事务 / `SELECT FOR UPDATE` / `UPDATE current_stock WHERE current_stock > 0` 三层缺一不可
2. **UNIQUE `uk_tenant_out_trade_no` 兜底支付回调幂等**（CLAUDE.md §6 #3）
3. **中奖物 snapshot 必须落 JSON 字段**（doc/02 §3.3 行 794）— 防后台改奖品名 / 改稀有度 / 删除奖品后历史 draw 记录读不到准确信息
4. **不做保底**（PRD §业务规则 4.1）— 任何"保底计数器" / "N 抽必中 X" 都禁止；纯权重随机
5. **抽完即下架**（doc/02 §3.3 行 792）— 库存=0 的奖品自动从池中剔除；机器所有奖品=0 时标 off_shelf
6. **退款失败重试 3 次 + 死信报警** — 不允许"用户钱扣了无货"出现
7. **`@Async("gachaExecutor")` 独立线程池** — 不占用 ruoyi 默认 task executor；线程数 = max(8, cores × 2)
8. **盲盒语义**（tokens.md §9）— 错误码 / 日志可保留 `draw` 技术语义，但用户可见的 toast / 邮件文案用扭蛋语义

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | `SELECT FOR UPDATE` 锁奖品行（不锁机器行）| 锁粒度小 — 并发抽不同奖品互不干扰；锁机器行会让所有用户串行 |
| D2 | 抽奖事务异步触发（支付回调线程不阻塞）| 微信支付回调要求 < 3s 响应；抽奖事务 SELECT FOR UPDATE + 多步 UPDATE 可能 > 1s |
| D3 | 抽奖记录 snapshot 用 JSON 字段而非冗余字段 | JSON 字段灵活兼容 prize 表 schema 变更（如 V2 加属性）|
| D4 | `SecureRandom` 而非 `Random` | SecureRandom 不可预测；防止用户通过种子推测中奖序列（虽然概率极低，但合规要求）|
| D5 | 退款重试用 `@Scheduled` + DB queue 表，不用 MQ | V1.1 流量小，DB 轮询足够；引入 MQ 增加运维复杂度 |
| D6 | "抽完即下架" 在事务内 UPDATE current_stock 后异步检测，不在事务内 | 检测全 prize stock=0 涉及二次 SELECT，增加事务时长；异步检测可接受秒级延迟 |
| D7 | machine.status 自动改 off_shelf 后**不**通知 mp 端 | 用户下次进列表自然看不到（GACHA-102 已过滤 on_shelf）；不引入 ws 推送 |
| D8 | 不引入 Redisson 分布式锁 | DB 行锁 + UNIQUE 已足够；引入 Redisson 增加依赖 + 增加超时风险 |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ★ | 并发抢最后 1 个 SSR 时超卖（2 个用户都中同一物） | 三层防线 + reports 强制贴并发压测 raw output 证伪 |
| R2 ★ | 退款失败但库存已扣 → 用户钱扣了无货 | 失败重试 3 次 + 死信队列 + 报警；最坏场景 Kevin 收到报警手动退款（合同 §维护流程内）|
| R3 | 概率归一化算法在 GACHA-103 详情页与 GACHA-104 抽奖事务中实现不一致 | 抽 `ProbabilityNormalizer` Bean，两处复用同一实例；单测两处共用 fixture |
| R4 | 支付回调延迟 > 30s（微信高并发抖动）→ 用户在 mp 端等待动画超时 | 前端轮询 `/app/gz/gacha/draw/{drawId}/status` 接口（GACHA-105 实现）；超时 60s 弹"已支付，结果稍后到账" |
| R5 | `@Async` 抽奖事务线程池打满 | 线程池配置 max=20 + 队列 1000；满了触发 RejectedExecutionHandler 入 DB queue 再异步消费 |
| R6 | SecureRandom 随机性偏差 | AC 8 单测中 10000 次抽样 + χ² 检验保证随机性；CI 中跑 |
| R7 | UPDATE current_stock affected=0 但 SELECT FOR UPDATE 之前刚查时是 > 0（理论不可能，但...）| AC 4 步骤 6 用 `WHERE id=? AND current_stock > 0` 兜底；affected=0 → throw 触发回滚（即使两次查询之间被其他事务抢，行锁也保证不会发生）|
| R8 | 支付回调签名校验绕过 | PAY-101 已实现微信支付签名校验 + 商户号绑定；本 ticket 不自实现，依赖 PAY-101 |
| R9 | 死信队列入库后 Kevin 不知道 | 邮件报警 + 后台「异常退款」面板（admin-005 已建占位，本 ticket 仅写数据，不做 UI） |

### ADR 候选

- **ADR-0003**：是否引入 MQ（RabbitMQ / RocketMQ）解耦支付回调与抽奖事务 — 默认 D5 不引；如压测发现 `@Async` 线程池频繁打满 → 新建 ADR-0003 评估

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
