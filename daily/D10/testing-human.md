# D<N> — Testing-human（Kevin 一人跑）

> 只做 AI 干不了的活：浏览器 UI / 微信开发者工具 / DB 客户端 / 代码 review / 产品 sense 主观判断。
> 命令式 / 可断言为真假的事（mvn / curl / mysql count）→ AI 在 reports/<T>.md 里贴 raw output，不在这跑。

---

## 0. 环境

- 后端跑起来：`mvn spring-boot:run -pl ruoyi-admin`
- Admin 跑起来：`cd code/main/plus-ui && pnpm dev` → 浏览器 http://localhost:80
- 小程序跑起来：`cd code/main/miniapp && pnpm dev:mp-weixin` → 微信开发者工具打开 `dist/dev/mp-weixin`

---

## 1. 今日 ticket 验收清单

### GZ-XXX-001 — <标题>

**关联 mockup**：design/mockup/<page>.html

**关联 AC**（从 tickets/GZ-XXX-001.md 复制）：
- [ ] AC 1：...
- [ ] AC 2：...
- [ ] AC 3：...

**测试动作**：
1. 浏览器打开 `<URL>` / 微信开发者工具 → 小程序首页
2. 操作：点击 X → 检查 Y
3. DB 验证：mysql 客户端 `SELECT * FROM gz_xxx WHERE ...`
4. 视觉对照 mockup：颜色 / 间距 / 文案

**判定**：
- ✅ OK → 在 progress.md 标 ✅
- ❌ NOT OK → 在 `tickets/GZ-XXX-001.md` 的 `§revision` 段写"问题 N: 现象 / 期望"

---

### GZ-XXX-002 — <标题>

（同上格式）

---

### GZ-ADMIN-201 — mp 店员端订单查看（只读，双下沉）

**关联 mockup**：design/mockup/me-orders.html（视觉参考，不强求逐像素）

**前置数据**：
- 店员账号：先用 `gz_staff_chengdu` 对应的微信 openid 登 mp（或 owner `gz_owner`）；该 openid 需已绑 staff_user_id（SYS-007 绑定流，或 admin「店员绑定管理」绑）。
- DB 需有预购单（gz_ord_order）+ 扭蛋单（gz_gacha_order）各至少 1 条已支付（gz_pay_transaction 有对应流水）才能看到列表。

**关联 AC**（从 tickets/GZ-ADMIN-201.md 复制）：
- [ ] AC11 Tier2 可达：店员登 mp → 「我的」tab → 个人中心「门店管理」区出现「订单查看」入口（纯顾客 / 未授权店员**不显示**）→ 点入到达列表页（N=2）
- [ ] AC1/AC7 列表：3 tab（全部/预购/扭蛋）切换正常；预购卡显商品名+规格+数量+金额；扭蛋卡显获得物名+扭蛋机+稀有度色边框；时间倒序；下拉刷新 + 上拉加载更多
- [ ] AC7 详情：点卡进详情 → 预购显商品 snapshot+规格+收货信息；扭蛋显获得物+扭蛋机+稀有度（盲盒语义：无「抽奖/中奖/开奖」字样）；物流 2 态只读（在日本 / 已发往中国+快递中文名+单号+复制 / 已签收）
- [ ] AC3 只读：详情页**无**「申请退款」「发往中国」「确认收货」「改单号」等写按钮（仅「复制单号」+ 底部只读说明）
- [ ] AC5 停用即踢（关键安全）：店员登 mp 看到订单列表 → owner 在 admin 把该 sys_user 停用（或「店员绑定管理」解绑 staff_user_id）→ 店员 mp 再进订单查看 → 应被踢（401 / 提示重新登录），订单查看入口消失

**测试动作**：
1. 微信开发者工具 → mp → 店员 openid 登录 → 底部「我的」tab
2. 门店管理区找「订单查看」→ 点入 → 切 3 tab 看列表 → 点预购卡 / 扭蛋卡看详情差异块
3. 详情页确认无任何写按钮（只读）
4. 物流为 in_china_dispatching 的单：点「复制单号」→ 确认 toast「已复制单号」
5. 停用即踢：admin（gz_owner 登 plus-ui）→ 系统管理 → 停用该店员 / 解绑 → 回 mp 重进订单查看 → 应 401 被踢
6. 反向：用纯顾客 openid 登 mp → 「门店管理」区不应有「订单查看」入口（或整个门店管理区不显示）

**AI 已覆盖（不用人验）**：bizType 映射 / 权限注解契约 / 委托逻辑（controller 单测 4/4）；编译 + build + type-check 全绿。人验聚焦：mp 真机入口可达 + 多态渲染观感 + 停用即踢端到端 + 盲盒语义文案。

---

### GZ-USER-102 — mp 订单详情统一页（预购 + 扭蛋多态）

**关联 mockup**：design/mockup/order-detail.html（7 节点版作废，仅结构参考；以 doc/12 §MP-ORD-DETAIL 五段为准）

**关联 AC**（节选）：
- [ ] AC1：`GET /app/gz/user/orders/{orderNo}` @SaCheckLogin + 非本人 403
- [ ] AC2/AC3：扭蛋 5 字段 / 预购 7 字段差异块，snapshot 直读不 join，图走 image_id 换签名
- [ ] AC4：统一布局五段顺序（状态卡→商品→物流→订单信息→底部 CTA）
- [ ] AC5：盲盒语义（获得物 / 获得时间 / 稀有度，禁 中奖/抽奖/开奖）
- [ ] AC6：确认收货仅 in_china_dispatching 态（本卡置灰）+ 退款仅纯文案无按钮
- [ ] AC7：终态（已签收/已退款/已取消）只读
- [ ] AC10：Tier 2 可达 — 会员中心「我的订单」→ 点单卡 → 本详情页（N=1）

**测试动作**（mp happy path）：
1. 微信开发者工具 → mp → 顾客 openid 登录 → 底部「我的」tab → 点「我的订单」cell → 列表页
2. 点一张**预购**订单卡 → 进详情：看顶部状态卡颜色 + 商品块（商品图 / 名 / 规格 / 数量 / 单价元）/ 物流占位 / 订单信息（订单号 / 时间 / 地址）/ 底部「如需退款请联系客服」纯文案（确认**无退款按钮**）
3. 物流为 in_china_dispatching 的预购单：底部出现「确认收货」按钮（**当前置灰**，点击 toast「确认收货功能即将上线」—— USER-104 才真实化，预期如此）
4. 已签收 / 已退款单：详情只读，底部无操作按钮
5. **扭蛋详情**：当前 orders.vue 列表 gacha tab 还是占位（统一列表 ticket 才接），暂用 curl 验或等统一列表上线；详情页扭蛋分支本身已实现（获得物图带稀有度边框 + 扭蛋机名 + 稀有度 + 获得时间），盲盒文案全用「获得物 / 获得时间 / 稀有度」无「中奖/抽奖/开奖」

**AI 已覆盖（不用人验）**：状态映射 / 终态 / CTA 可见 / 地址解析 / 多态取图（logic 单测 8/8）+ 后端归属 403 + 差异块字段（service 单测 4/4）+ mp build + type-check 全绿。人验聚焦：真机入口可达（N=1）+ 多态渲染观感 + C 设计系统遵循 + 盲盒语义文案语感。

---

### GZ-USER-103 — mp 跨境物流 C1 2 态 + 终态展示（只读侧）

**关联 mockup**：design/mockup/order-detail.html（7 节点版作废，**不对照**；以 doc/12 §MP-ORD-DETAIL §页面结构 4「物流 2 态卡片」为准，C1 一票否决 7 节点时间线）

**前置数据**（态切换走手改 DB，D11 ADMIN-104 写入 UI 未交付前）：
```sql
-- 态2：已发往中国
UPDATE gz_ord_order SET logistics_status='in_china_dispatching', cn_carrier_code='sf', cn_tracking_no='SF1234567890', cn_dispatched_at=NOW() WHERE order_no='PREORD-...';
-- 态3：已签收
UPDATE gz_ord_order SET logistics_status='delivered', cn_carrier_code='sf', cn_tracking_no='SF1234567890', delivered_time=NOW() WHERE order_no='PREORD-...';
-- 默认即态1 in_japan（建单初始态）
```

**关联 AC**（节选）：
- [ ] AC2 态1 in_japan：「商品在日本备货中」+ 副文，**无任何按钮 / 无时间线 / 无节点 UI**
- [ ] AC3 态2 in_china_dispatching：「已发往中国」+ 快递公司**中文名**（sf → 顺丰速运，非显示 code）+ 单号 + 朱红「复制单号」按钮 + 查询提示
- [ ] AC4 态3 delivered：绿色「已签收」+ 签收时间（YYYY-MM-DD HH:mm）+ 历史快递/单号保留可见，**无复制按钮**
- [ ] AC5 快递映射兜底：未知 / 空 code → 显示「其他」
- [ ] AC9 一票否决：**无 7 节点时间线 / 无第三方轨迹查询**（仅复制单号自查）
- [ ] AC11 Tier2 可达：会员中心 →「我的订单」→ 点单卡 → 详情页下滑见物流卡（N=4，复用 USER-102 已通路径，无新入口）

**测试动作**（3 态各看一遍 + 复制单号）：
1. 默认进一张订单详情（态1）→ 物流卡只「商品在日本备货中」+ 副文，确认**无任何按钮**
2. 手改 DB 为态2（上面 SQL，sf）→ 重进详情 → 物流卡显「已发往中国」+「顺丰速运」（确认是中文名不是 `sf`）+ 单号 + 朱红「复制单号」按钮 → 点击 → toast「已复制」→ 去输入框粘贴验证剪贴板是单号
3. 手改 DB 为态3 → 重进详情 → 绿色「已签收」+ 签收时间 + 历史快递/单号仍可见 → 确认**无复制按钮**
4. （可选）改 cn_carrier_code 为未知值（如 'xxx'）态2 → 快递公司显「其他」（兜底）
5. 视觉：复制按钮朱红 + 粗墨边 + 硬投影（C 套），「已签收」绿色；无任何 7 节点时间线 / 进度条

**AI 已覆盖（不用人验）**：useExpressCarrier 9 项映射 + 兜底 + 签收时间格式化（vitest 19/19）+ me 全域回归 36/36 + type-check 0 error + mp build 绿 + 复制单号 uni.setClipboardData 编译入 vendor。人验聚焦：3 态真机渲染观感 + 复制单号端到端（剪贴板）+ 快递中文名显示正确 + C 设计系统遵循（朱红复制按钮 / 绿签收）。

---

### GZ-USER-104 — 用户确认收货 + 自动签收（SnailJob）

**关联 mockup**：design/mockup/order-detail.html（底部「确认收货」CTA — 旧 mockup 仅布局参考，视觉以 C 系统为准）

**⚠️ SnailJob 控制台注册（自动签收 cron，须人工注册一次 — 代码不自动注册）**：
- 任务名称：`GZ-LOGISTICS-AUTO-SIGN`
- 执行器路由名（executor_info）：`gzLogisticsAutoSignExecutor`（= `@JobExecutor(name)`）
- 触发类型：CRON，表达式 `0 0 * * * ?`（每小时整点，容器时区 Asia/Shanghai）
- 阻塞策略：丢弃（DISCARD）；组：`ruoyi_group`
- 注册后可在控制台「手动执行一次」触发验证（见下方自动签收测试）

**前置数据**（确认收货态切换走手改 DB，D11 ADMIN-104 写入 UI 未交付前）：
```sql
-- 造一张「已发往中国」态（仅此态显示「确认收货」按钮）
UPDATE gz_ord_order SET logistics_status='in_china_dispatching', cn_carrier_code='sf', cn_tracking_no='SF1234567890', cn_dispatched_at=NOW() WHERE order_no='PREORD-...';
-- 自动签收 7 天边界验证：把 cn_dispatched_at 调到 8 天前（满 7 天 → cron 应签）
UPDATE gz_ord_order SET logistics_status='in_china_dispatching', cn_dispatched_at=DATE_SUB(NOW(), INTERVAL 8 DAY) WHERE order_no='PREORD-...';
-- 边界内对照（6 天前，不应被自动签）
UPDATE gz_gacha_order SET logistics_status='in_china_dispatching', cn_dispatched_at=DATE_SUB(NOW(), INTERVAL 6 DAY) WHERE order_no='GACHA-...';
```

**关联 AC**（节选）：
- [ ] AC3/AC6 主动确认：`in_china_dispatching` 态详情底部见朱红「确认收货」CTA → 点击弹 confirm modal「确认已收到货物？签收后无法回退」→ 确认 → toast「已签收」→ 页面刷新（CTA 消失、状态变「已签收/已完成」绿色）
- [ ] AC4 幂等 / 不可回退：签收后该订单不再显示「确认收货」CTA；非 `in_china_dispatching` 态（in_japan / 已 delivered）**不显示** CTA
- [ ] AC2/AC5 自动签收：SnailJob 控制台手动触发 `GZ-LOGISTICS-AUTO-SIGN` 一次 → 8 天前的订单（预购 + 扭蛋）变「已签收」；6 天前的订单**保持** in_china_dispatching（未到 7 天）
- [ ] AC8 Tier2 可达：会员中心 →「我的订单」→ 点一条 `in_china_dispatching` 态订单进详情（复用 USER-102 已通路径）→ 底部见「确认收货」CTA → 点击签收成功（无需自定义编译模式 / console navigateTo）

**测试动作**：
1. 手改 DB 造一张 `in_china_dispatching` 预购订单 → 进详情 → 底部见朱红「确认收货」按钮 → 点 → confirm modal 弹出（标题/内容/确认/取消文案正确）
2. 点「再想想」→ modal 关，订单态不变；再点「确认收货」→「确认收货」→ toast「已签收」→ 详情自动刷新为「已签收」绿色 + CTA 消失
3. 重复点（若有残留）/ 再进该订单 → 无 CTA（幂等不可回退）
4. 扭蛋订单同样流程跑一遍（GACHA- 单，盲盒语义：文案不出现「抽奖/中奖/开奖」）
5. 自动签收：SnailJob 控制台注册任务后「手动执行一次」→ 查 DB：8 天前的预购 + 扭蛋单 `logistics_status=delivered` + `business_status=delivered` + `delivered_time` 非空 + `gz_logistics_audit` 各一条 `auto_delivered`（operator_id=`system`）；6 天前的单仍 `in_china_dispatching`
6. 确认收货审计：步骤 2 签收后查 `SELECT * FROM gz_logistics_audit WHERE business_order_no='PREORD-...'` → 一条 `action_type=user_confirmed` / `operator_type=user` / `operator_id=`你的 user_no / `from_status=in_china_dispatching` / `to_status=delivered`

**AI 已覆盖（不用人验）**：自动签收 service 单测 10（7 天边界阈值 / 天数走 config / 一单失败不阻塞同批 / 幂等不计数）+ txHelper 单测 3（条件命中写审计 / 未命中不写 / 审计字段对齐 §8.3）+ confirmReceive 单测（happy / 状态非法 / 越权 / 已签 / 非法前缀）+ 编译三端绿 + mp build 绿（showModal + confirm-receive API 编译入 dist）。人验聚焦：① SnailJob 控制台注册并手动触发自动签收（cron 注册是人工动作）② mp 真机确认收货端到端（modal → 签收 → 刷新）③ 审计行落库正确。

---

## 2. 跨 ticket 联调（如有）

如果今日 ticket 之间有协作（如 GZ-SYS-001 微信登录 → GZ-USER-001 个人资料读取），单独跑一次：

1. 微信登录走通
2. 进入个人资料页 → 数据显示
3. 退出登录 → 再进入 → 应跳登录页

---

## 3. 视觉 / 文案 review（C 设计系统对齐）

- mp 视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红 / 网点 / 报头风），以 doc/tokens.md + doc/13 为准；admin 不评判视觉 ✅ / 偏离
- emoji 没乱用 ✅ / 滥用
- 中文文案没机翻味 ✅ / 像 GPT 风
- 不逐像素，但 C 套气质到位（朱红主色 / 直角硬朗 / 报头风）✅ / 偏差

---

## 4. 性能 sense（主观感受）

- 小程序首页打开秒开？✅ / 卡
- API 响应 < 1s？✅ / 慢（哪个接口）
- DB 数据量级符合预期？✅ / 异常（如本该 10 条结果出来 1000 条）
