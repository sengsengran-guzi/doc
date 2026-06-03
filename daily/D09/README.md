# D09 — V1.1 扭蛋域全链路（gz_gacha_* 全表 + 抽奖事务防超卖 + 图鉴 ⭐）

> 阶段：V1.1 实施期（不绑日历日期）
> 上一日：[D08](../D08/README.md)（业务支付通道 GZ-PAY-101）｜ 下一日：[D10](../D10/README.md)
>
> **V1.0 真相**：V1.0 已通过 AI 测试，但**未客户验收、未上线**（不是"已上线运行 1-2 周"）。任何回切 V1.0 行为需评估，不假设线上稳定。
> **本域起点真相**：`ruoyi-gz-gacha` 是**空脚手架**（仅 1 个 `GachaHelloController`），`gz_gacha_*` / `gz_user_gacha_collection` 表**全部不存在**，plus-ui 扭蛋域只有 Hello.vue。**扭蛋域从零起。**

---

## 今日目标

扭蛋机（业务线 B）从「配置 → 浏览 → 概率公示 → 投币开盒 → 揭晓 → 历史 → 图鉴」全链路落地，是 V1.1 核心营收模块之一。

- **主线 1**（数据底座）：扭蛋机 + 奖品池数据模型（GZ-GACHA-101）→ 甲方运营能配机器、配奖品池、配概率权重 + 库存
- **主线 2**（C 端浏览）：mp 扭蛋机列表（GZ-GACHA-102）+ 单机详情 + 概率公示（GZ-GACHA-103）→ 用户能逛机器、看每个奖品**实时归一化的出现概率**（合规）
- **主线 3 ⭐**（核心交易）：抽奖事务 + 防超卖（GZ-GACHA-104）→ **V1.1 最复杂 ticket**（L）。DB 事务 + `SELECT FOR UPDATE` + 概率归一化 + 库存扣减 + 图鉴 +1 + 衍生订单，**4 表原子**；库存抢空整事务回滚 + 退款。调 **D08 GZ-PAY-101**（微信支付 V3，mock client 自测全链路）
- **主线 4**（C 端体验 + 收集闭环）：三段分镜动画揭晓（GZ-GACHA-105）+ 抽奖历史（GZ-GACHA-106）+ 图鉴（GZ-GACHA-107）→ 收集驱动闭环

## Ticket 清单（7 个）

| Ticket | 标题 | 复杂度 | 依赖 | 端 | 状态 |
|---|---|---|---|---|---|
| GZ-GACHA-101 | 扭蛋机 + 奖品池数据模型 + admin CRUD | M | GZ-SYS-001 ✅ | 后端 + admin | pending |
| GZ-GACHA-102 | mp 扭蛋机列表 | M | GACHA-101 | 后端 + mp | pending |
| GZ-GACHA-103 | mp 单机详情 + 概率公示（实时归一化） | M | GACHA-102 | 后端 + mp | pending |
| GZ-GACHA-104 ⭐ | 抽奖事务 + 防超卖（4 表原子 + 失败退款） | **L** | GACHA-101 + **PAY-101（待 D08 完工 pending）** | 后端 + mp | pending |
| GZ-GACHA-105 | mp 三段分镜动画 + 揭晓 | M | GACHA-104 | mp | pending |
| GZ-GACHA-106 | mp 抽奖历史 | S | GACHA-104 | 后端 + mp | pending |
| GZ-GACHA-107 | mp 图鉴（按机器分组 + 集齐徽章） | M | GACHA-105 | 后端 + mp | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图（关键路径标 ⭐）**：

```
   GACHA-101 (数据底座 + admin 扭蛋池 CRUD)
       │
       ├─ GACHA-102 (mp 列表) ─── GACHA-103 (mp 详情 + 概率公示)   ← 浏览波（与 104 并行）
       │
       └─ GACHA-104 ⭐ (抽奖事务，依赖 GACHA-101 + PAY-101)        ← 关键路径
              │
              ├─ GACHA-105 (mp 动画揭晓) ─── GACHA-107 (图鉴)       ← 体验波（与 106 并行）
              │
              └─ GACHA-106 (mp 历史)
```

依赖时序口径：
- **GACHA-101 先行**（建表 + admin CRUD），其余全部阻塞在它后面。
- GACHA-101 完工后：**(102 → 103) 与 (104 ⭐) 两条链并行起跑**（104 是 L，越早起跑越好）。
- **104 完工后**：**(105 → 107) 与 (106) 并行**。
- GACHA-104 还依赖 **PAY-101**（D08 业务支付通道）。当前 PAY-101 **待 D08 完工（pending）**，不假设已 ✅。GACHA-104 §0 自检必须 `grep` 出 `IGzPayService` / `IWechatPayClient` 实际存在再开始（见下"特殊约束"）。

## 派单方式

**整日触发**（推荐）：
```
开始 d9
```

**单 ticket 触发**（如某 ticket revision 闭环）：
```
@coder 做 D09/GZ-GACHA-104
```

主线程动作：
1. 读 D09/README.md（本文件）+ 依赖图。
2. **第一波串行**：先派 GZ-GACHA-101（数据底座 + admin CRUD）。
3. **GACHA-101 完工** → 并行 spawn **GACHA-102** + **GACHA-104 ⭐**（104 最长，越早起跑越好；起跑前确认 PAY-101 已完工，否则挂起等 D08）。
4. **GACHA-102 完工** → spawn GACHA-103。
5. **GACHA-104 ⭐ 完工** → 并行 spawn **GACHA-105** + **GACHA-106**。
6. **GACHA-105 完工** → spawn GACHA-107（图鉴依赖揭晓页 N9 埋的"集齐进度 +1"入口）。
7. 7 个 ticket 全部 ✅ → 主线程预填 testing-human.md（仅 mp ticket）+ 日终 closing。

## 今日特殊约束

### A. GZ-GACHA-104 是 V1.1 最复杂 ticket ⭐（L 级，禁止快速过 §0 自检）

引用 **doc/10 §8 扭蛋机抽奖全流程 N6**（不是 §7 = 预购）+ A.6 状态枚举：

- **事务流程（doc/10 §8 N6，4 表原子）**：
  1. `BEGIN TRANSACTION`
  2. `SELECT ... FROM gz_gacha_prize WHERE machine_id=? AND stock_remain > 0 FOR UPDATE` 锁所有候选奖品行
  3. 校验至少 1 个有库存（否则 → ROLLBACK）
  4. **按当前剩余库存的奖品权重一次性归一化**（事务内不重读，与概率公示口径一致）
  5. 随机抽 1 个
  6. `UPDATE gz_gacha_prize SET stock_remain = stock_remain - 1, version = version + 1 WHERE id=? AND version=?`（**乐观锁 version**）
  7. `INSERT gz_gacha_draw`（含中奖物 **snapshot_json**：名称 / image_id / 稀有度 / 公示价值；幂等基于 transaction_id 唯一索引）
  8. **事务内** `INSERT/UPSERT gz_user_gacha_collection`（用户 × 机器 × 奖品 已得 +1，支持重复）
  9. `INSERT gz_gacha_order`（衍生订单，`business_status = pending_ship`）
  10. `COMMIT`
- **库存空整事务回滚**：N6.③ 校验失败 → ROLLBACK（`gz_gacha_draw` **不落**）→ 仅写 `gz_pay_refund` 退款（全额，一笔对一单）→ 用户视感「奖品已抽完，已为您退款」。
- **自动下架**：某奖品 `stock_remain` 扣到 0 或整机所有奖品抽空 → 机器 `status = auto_off`（**不用 off_shelf/archived**）。
- **不做保底**（doc/10 §8 业务规则 + PRD §4.1）— 概率纯随机，不强制 N 抽必中 SR。
- **调 PAY-101（微信支付 V3）**：`IGzPayService.unifiedOrder()` → 业务回调按 `out_trade_no` 前缀 `GACHA-` 分发到抽奖事务（doc/10 §6.N6 / §8.N6）；退款走 `gz_pay_refund`。**禁止** V2 / XML / api-key / 新建 gz_pay_order / amount_fen / /api/wxpay/pay-notify。
- **reports 必须包含并发压测 raw output**：多线程同时抢同一机器最后 1 个 SSR → **仅 1 个用户拿到**，其余整事务回滚 + 退款（证伪超卖）。
- **退款 V1.1 仅全额**：一笔对一单，无金额 input；C 端无退款入口（仅文案"如需退款请联系客服"）；权限 `@SaCheckPermission("gz:pay:refund:apply")`，不用 `@SaCheckRole`。

### B. 盲盒语义纪律（仅 gacha 域，硬约束）

**UI 可见文案 / i18n key**：用 **扭蛋 / 开盒 / 获得 / 出现概率**；**禁** 抽奖 / 中奖 / 开奖 / 抽奖概率 / 中奖率。
- 核心金句：「100% 获得，概率为获得对应商品的可能性」。
- **后端 enum / 数据库字段命名可保留 `draw`**（技术语义，如 `gz_gacha_draw` / `business_status`），但 UI 字符串与 `t('gacha.xxx')` key 全部用扭蛋语义。
- 权威引用：**doc/10 §8**（扭蛋流，**不是 §7 预购**）+ **doc/12 MP-GACHA-DRAW / MP-GACHA-LIST / MP-GACHA-DETAIL / MP-GACHA-HISTORY / MP-ME-COLLECTION** + **doc/tokens.md §1.4 稀有度色** + **doc/13 §3.2 出奖三段动画（`BizGachaDraw` 待建）**。
- **禁止引 tokens §9**（不存在）。出奖动画 / 稀有度光晕权威 = tokens §1.4 + doc/13 §3.2。

### C. mp 端视觉（C 日漫海报浓墨）

- 页面只用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token，**不直接撒 `<wd-*>`**；旧 mockup（gacha-list / gacha-detail / gacha-draw / gacha-history / me-collection.html）仅布局/视觉参考，**不逐像素还原**。
- 扭蛋机用立体迷你机器视觉（不是平面商品图）。
- **三段分镜（doc/13 §3.2 `BizGachaDraw`）**：**转动 → 裂开光爆 → 揭晓稀有度光晕**。集中线爆闪（`.c-burst`）+ 稀有度光晕走 **tokens §1.4**：SSR `var(--c-r-ssr)` / SR `var(--c-r-sr)` / R `var(--c-r-r)` / N `var(--c-r-n)`，**四档，不引第五档**，稀有度仅展示用。
- 低端机微信卡顿 fallback：动画用 CSS `transform`/`opacity`（GPU 友好），不用 `setInterval` 重绘；低端机直接揭晓 + 渐入。

### D. 字段 / 命名硬约束（锚定 doc/11，每张卡都遵守）

- 金额一律 `_cent`（分）：`single_price_cent` / `ten_pack_price_cent`；**不用 `_fen`**。
- snapshot 用 `*_snapshot_json`（JSON 列）：`gz_gacha_draw.prize_snapshot_json`，**不散列成多列**。
- 图片用 `image_id` FK 到 `gz_file_object`：`gz_gacha_machine.cover_image_id` / `gz_gacha_prize.image_id`，**不存裸 url**。
- 库存：`stock_total` / `stock_remain`（**不用 init/left**）；乐观锁 `version`。
- 状态枚举含 `auto_off`（自动下架），**不用 off_shelf/archived**。
- `del_flag` 仅 2 值（0 正常 / 2 删除），对齐 ruoyi `@TableLogic`；**不用 3 值**。
- 业务线分流统一 `business_type` 取值 **`gacha`**，落 `gz_pay_transaction`；**禁** 在业务订单表加 `business_line`/`biz_line`/A/B 列。
- 订单号格式：**`GACHA-yyyyMMdd-6位序号`**，全局唯一 DB 约束（与 D07 已发的 `TEST-20260604-` 单一致口径）。
- `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`；INSERT 不显式赋（走自动填充）；UNIQUE 约束**必含 tenant_id**。
- 包名 `org.dromara.gz.gacha.{controller,service,mapper,domain,dto}`。
- **menu_id 段**：GACHA 业务菜单 **10000-10099**；扭蛋池 admin **10100 段**。
- DDL 命名 `V<yyyyMMddHHmm>__GZ-GACHA-101-<desc>.sql` 放 `ruoyi-admin/src/main/resources/db/migration/`（时间戳 > 当前最大 `V202606051200`；已应用迁移不可改）。

### E. 调度（如有 cron）

- 框架是 **SnailJob**（`com.aizuda @JobExecutor`），仓库**无 sys_job 表**。任何 cron（如本域暂无强制，预留）用 `@Component + @JobExecutor` 薄壳 + 可单测 service；**禁** Quartz / Flyway INSERT sys_job（启动 hard-fail）。
- `ruoyi-gz-gacha` 模块 pom **显式加 `ruoyi-common-job` 依赖**（若引入 executor）；任务名 / CRON 写进 reports + testing-human，由人在 SnailJob 控制台注册。

### F. 通用

- **API 路径前缀**：admin `/system/gz/gacha/...` ｜ mp `/app/gz/gacha/...`。
- **i18n 强制**：mp 端字符串全走 `t('gacha.xxx')` + zh-CN 默认；admin 同；**不混 emoji**。
- **mp 管理权限复用 ADR-0004 底座**（GACHA-104 退款等 mp 管理动作）：加一行 `@SaCheckPermission(<perm key>)` + admin 授权 + 同租户 1001，**不另造平行 RBAC**。
- **图鉴 V1.1 简版**（doc/02 §3.3）：按机器分组 + 已得高亮 + 集齐徽章 + 重复角标足够；**不做**炫耀分享 / NFT / 跨机器套装 / 发实物。
- **不要 commit**：7 个 ticket 全部 ✅（+ mp ticket 进人验列）后再统一 commit。

## 与上游对账（D08 GZ-PAY-101）

GACHA-104 起跑前主线程确认 D08 `summary.md` 抓"对下游 ticket 的提示"段：
- ⏳ **PAY-101 待 D08 完工（pending）** — 不假设已 ✅。GACHA-104 §0 自检 `grep -r "interface IGzPayService" ruoyi-gz-common` + `grep -r "IWechatPayClient" .` 确认接口实际存在再实现；不存在 → STOP，挂起等 D08。
- PAY-101 是**微信支付 V3**：复用 `IWechatPayClient`（`WechatPayV3ClientImpl` / `MockWechatPayClient`）+ apiV3Key + V3 `NotificationParser`(AES-GCM) + 回调 `/api/pay/v3/notify`；支付流水表 `gz_pay_transaction` / `gz_pay_callback_log`（已落地）。
- **推进姿态 = Mock 全链路自测**：dev/staging 用 `gz.pay.client.mode=mock` 跑通"统一下单 → 回调 → 抽奖事务 → 退款"全链路；真实商户号 / 0.01 元端到端列为**外部前置风险**（备注段标注），不当默认就绪。
- `ruoyi-gz-gacha` 模块结构由 D01 GZ-SYS-001 建空壳（仅 HelloController），GACHA-101 起填血肉。

## §0 自检口径（本域全卡，对齐"已交付真相"）

- §0 自检**改为 grep migration 目录实际存在的表**，**不假设上游已建**：
  - GACHA-101：`grep` 确认 `gz_gacha_*` 表**尚不存在**（本卡新建），`gz_file_object` 存在（FK 依赖）。
  - GACHA-102/103/106/107：`grep migration` 确认 `gz_gacha_machine` / `gz_gacha_prize` / `gz_gacha_draw` / `gz_user_gacha_collection` 已建（GACHA-101 落地后）。
  - GACHA-104：`grep` 出 `IGzPayService` / `IWechatPayClient` / `gz_pay_transaction` 实际存在 + `gz_gacha_prize` 已建，再开始。
- **不引 phantom ticket**：本域无 `GZ-USER-201`（已删）；图鉴衍生订单写入对接的是 GACHA-104 建的 `gz_gacha_order`（本域自有衍生订单表），不依赖未存在的 USER 订单表。

## 完成判定（DoD）

- [ ] 7 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 7 个 reports/<T>.md 写完（含 §0 自检表 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] **GACHA-104 reports 必含并发压测 raw output**（多线程同抢最后 1 个 SSR → 仅 1 个拿到，其余整事务回滚 + 全额退款；snapshot_json 落库；订单号 `GACHA-yyyyMMdd-NNNNNN` 唯一）
- [ ] GACHA-104 mock client 全链路自测 raw output（`gz.pay.client.mode=mock`：统一下单 → 回调 → 抽奖事务 → 库存扣减 / 图鉴 +1 / 衍生订单 / 退款分支）
- [ ] mvn install（含 `ruoyi-gz-gacha`）+ plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] 盲盒语义自查：mp 可见文案 + `t('gacha.xxx')` 无"抽奖/中奖/开奖"（grep 验证）
- [ ] mp ticket（102/103/105/106/107）进 progress.md「人验」列（Tier 2 批量人验待批）
- [ ] testing-human.md 由 coder 预填（mp ticket：列表 → 详情 → 投币开盒 → 揭晓 → 历史 → 图鉴 happy path + 入口可达）
- [ ] `cat reports/*.md > summary.md` 已生成

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | GACHA-104 并发抢最后 1 个 SSR 超卖（2 用户同中一物） | `SELECT ... FOR UPDATE` 事务内锁奖品行 + 乐观锁 `version`；reports 必含并发压测 raw output 证伪超卖 |
| R2 ⭐ | 退款分支与库存已扣不一致（钱扣了无货 / 货扣了未退） | 库存抢空走 ROLLBACK（draw 不落、库存自动归还），仅写 `gz_pay_refund`；成功路径 4 表同一事务原子（库存 + draw + 图鉴 + 衍生订单）COMMIT |
| R3 | 概率归一化在库存动态变化时不一致 | 进事务后立即 `SELECT FOR UPDATE` 抓快照 + 一次性归一化，事务内不重读（doc/10 §8 E3 一致性优先）|
| R4 | PAY-101 未完工 GACHA-104 无法实施 | §0 自检 grep `IGzPayService` 实际存在；不存在 → STOP 挂起等 D08；自测用 `gz.pay.client.mode=mock` |
| R5 | 真实微信商户号 / 0.01 元端到端未就绪 | **外部前置风险**：dev/staging 仅 mock 全链路自测；真实端到端备注段标注，不当默认就绪，并行催甲方验收 V1.0 |
| R6 | 三段分镜动画在低端机卡顿 | CSS `transform`/`opacity`（GPU），不用 `setInterval` 重绘；低端机 fallback 直接揭晓 + 渐入 |
| R7 | 盲盒语义在旧 mockup（gacha-draw.html）仍写"抽奖" | mp 实施改 `t()` 文案（扭蛋/开盒/获得/出现概率），不动 mockup（mockup 是历史快照，文案以盲盒语义纪律为准）|
| R8 | 历史 / 图鉴误显示已退款记录 | GACHA-106 历史**不含 refunded**；GACHA-107 图鉴查 `gz_user_gacha_collection`（事务内 +1，退款分支事务回滚不落）|

---

## 日终 closing 命令

```bash
cd doc/daily/D09
cat reports/*.md > summary.md
# mp ticket 进 progress.md「人验」列；AI 全 ✅ 后再统一 commit
git add -A && git commit -m "D09: V1.1 扭蛋域全链路 GACHA-101~107（抽奖事务防超卖 + 图鉴，mock client 自测）⭐"
# 然后写 D10/README.md
```
