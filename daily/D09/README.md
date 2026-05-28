# D09（Kevin 口径 d8）— V1.1 扭蛋机全链路（V1.1 重头 ⭐）

> 日期：2026-06-17（周三）
> 阶段：V1.1 实施期 day 2（D08 业务支付通道 GZ-PAY-101 ✅）
> 上一日：[D08](../D08/README.md) ｜ 下一日：[D10](../D10/README.md)

---

## 今日目标

- **主线 1**（数据底座）：扭蛋机 + 奖品池数据模型（GZ-GACHA-101）→ 让甲方运营能配机器、配奖品池
- **主线 2**（C 端浏览）：mp 扭蛋机列表（GZ-GACHA-102）+ 单机详情 + 概率公示（GZ-GACHA-103）→ 用户能看见、能挑机器、能知道每个奖品出现概率
- **主线 3 ⭐**（核心交易）：抽奖事务 + 防超卖（GZ-GACHA-104）→ **V1.1 最复杂 ticket**，DB 事务 + SELECT FOR UPDATE + 概率归一化 + 库存扣减 + 失败回滚退款全链路
- **主线 4**（C 端体验）：扭蛋动画 + 结果展示（GZ-GACHA-105）+ 扭蛋历史（GZ-GACHA-106）+ 集齐特典图鉴（GZ-GACHA-107）→ 收集驱动闭环

完工后扭蛋机业务从「配置 → 浏览 → 付款 → 扭蛋 → 揭晓 → 历史 → 图鉴」7 环全通，是 V1.1 的核心营收模块。

## Ticket 清单（7 个，按依赖顺序）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-GACHA-101 | 扭蛋机 + 奖品池数据模型 | M | GZ-SYS-001 ✅ | pending |
| GZ-GACHA-102 | mp 扭蛋机列表 | M | GACHA-101 + ADMIN-005 ✅ | pending |
| GZ-GACHA-103 | mp 单机详情 + 概率公示 | M | GACHA-102 | pending |
| GZ-GACHA-104 ⭐ | 抽奖事务 + 防超卖 | L | GACHA-101 + PAY-101 ✅(D08) | pending |
| GZ-GACHA-105 | mp 抽奖动画 + 结果展示 | M | GACHA-104 | pending |
| GZ-GACHA-106 | mp 抽奖历史 | S | GACHA-104 | pending |
| GZ-GACHA-107 | 集齐特典 / 图鉴模块 | M | GACHA-105 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图（关键路径标 ⭐）**：

```
   GACHA-101 (数据底座)
       │
       ├─ GACHA-102 (mp 列表) ─── GACHA-103 (mp 详情)        ← 可并行第一波
       │
       └─ GACHA-104 ⭐ (抽奖事务，依赖 PAY-101)              ← 关键路径
              │
              ├─ GACHA-105 (mp 动画揭晓) ─── GACHA-107 (图鉴) ← 可并行第二波
              │
              └─ GACHA-106 (mp 历史)
```

## 派单方式

**整日触发**（推荐）：
```
开始 d8
```

**单 ticket 触发**（如某 ticket revision 闭环）：
```
@coder 做 D09/GZ-GACHA-104
```

主线程动作：
1. 读 D09/README.md（本文件）+ 依赖图
2. **第一波串行**：先派 GZ-GACHA-101（数据底座）→ 完工后并行 spawn GACHA-102 + GACHA-104 ⭐（最长 ticket，越早起跑越好）
3. **GACHA-102 完工** → spawn GACHA-103
4. **GACHA-104 ⭐ 完工** → 并行 spawn GACHA-105 + GACHA-106
5. **GACHA-105 完工** → spawn GACHA-107（图鉴依赖揭晓页埋的入口）
6. 7 个 ticket 全部 ✅ → 主线程提示 Kevin testing-human + 日终 closing

## 今日特殊约束

- **GZ-GACHA-104 是 V1.1 最复杂 ticket ⭐**（L 级思考密度，禁止快速过 §0 自检）：
  - DB 事务 + `SELECT FOR UPDATE` 锁候选奖品行
  - 概率权重实时归一化（按当前剩余库存重算）
  - 任何一步失败 → 整事务回滚 + 退款（PAY-101 退款接口）
  - **不做保底**（PRD §业务规则 4.1）— 概率纯随机，不强制 N 抽必中 SR
  - 抽奖记录字段含**中奖物 snapshot**（防止后台改奖品名 / 改稀有度后历史记录错乱）
  - **reports 必须包含并发压测 raw output**（同时抽同一机器最后一个 SSR → 仅 1 个用户拿到，其他人退款）
- **盲盒语义纪律**（doc/tokens.md §9 盲盒大修订）：
  - ❌ 抽奖 / 中奖 / 开奖 / 抽奖概率 / 中奖率
  - ✅ 扭蛋 / 开盒 / 获得 / 出现概率 / 出现率
  - 核心金句：「100% 获得，概率为获得对应商品的可能性」
  - 后端 enum / 数据库字段命名可保留 `draw`（技术语义），但 UI 可见字符串与 i18n key 全部用扭蛋语义
- **mp 端 tokens.md §9 趣味性约束**（设计冻结期 mp 仍走 wot 默认 + tokens.md）：
  - 扭蛋机用立体迷你机器视觉（不是平面商品图）
  - 三段分镜：**转动 → 裂开光爆 → 揭晓稀有度光晕**（SSR/SR/R/N 各自光晕 token）
  - 稀有度仅展示用 SSR/SR/R/N 四档（不引入第五档）
- **GACHA-107 与会员中心订单 tab 数据互通**：中奖即建 status='pending_delivery' 待发货订单写入 GZ-USER 订单表
- **GACHA-107 V1.1 简版**（doc/02 §3.3 行 838 明确"V1.1 简版，深化推 v2"）：图鉴页按机器分组 + 已得高亮 + 集齐徽章足够，**不做**炫耀分享 / 收藏 NFT / 跨机器套装等
- **API 路径前缀**：admin `/system/gz/gacha/...` ｜ mp `/app/gz/gacha/...`
- **i18n 强制**：mp 端字符串全走 `t('gacha.xxx')` + zh-CN 默认，admin 同
- **menu_id 段**（CLAUDE.md §6 #6）：GACHA 10000-10099
- **DDL 命名严格**：`V<yyyyMMddHHmm>__GZ-GACHA-101-<desc>.sql` 放 `ruoyi-admin/src/main/resources/db/migration/`
- **不要 commit**：7 个 ticket 全部 ✅ + Kevin testing-human 通过后再统一 commit

## 与昨日 reports 对账（D08）

D08 `summary.md` 抓"对下游 ticket 的提示"段：
- ✅ GZ-PAY-101 业务支付通道已 ✅（统一下单 / 支付回调 / 退款接口），GACHA-104 直接调 `IGzPayService.unifiedOrder()` + `refund()`
- ✅ ruoyi-modules/ruoyi-gz-gacha 模块结构已就位（D01 GZ-SYS-001 已建空 module，本日 GACHA-101 起填血肉）
- ⏳ doc/10-业务流权威图.md §7 扭蛋抽奖流是否完整 —— **本日实施前由 @product 确认**（不全则 ticket 备注标 "需要回 doc/10 §7 补"，按 §3 拼豆并发结构类比写）
- ⏳ ruoyi-gz-gacha 数据库表前缀 `gz_gacha_*` / 包前缀 `org.dromara.gz.gacha.*`（CLAUDE.md §6）

## 完成判定（DoD）

- [ ] 7 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 7 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] **GACHA-104 reports 必含并发压测 raw output**（多线程同抽最后 1 个 SSR → 仅 1 个拿到，其他自动退款）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] testing-human.md 全勾（Kevin 用微信开发者工具完整体验「列表 → 详情 → 扭蛋 → 揭晓 → 历史 → 图鉴」）
- [ ] cat reports/*.md > summary.md 已生成

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | GACHA-104 并发抢最后 1 个 SSR 时超卖（2 个用户都中同一物） | 强制 `SELECT FOR UPDATE` 在事务内锁奖品行；reports 必含 `wrk -t10 -c50` 压测 raw output 证伪超卖 |
| R2 ⭐ | GACHA-104 退款失败但库存已扣 → 用户钱扣了无货 | 库存扣减 + 抽奖记录 + 待发货订单**同一 DB 事务**；事务提交后才调支付退款（如有失败）；退款接口失败重试 3 次 + 失败入死信队列报警 |
| R3 | 概率归一化算法在库存动态变化时不一致 | 进入事务后立即 `SELECT FOR UPDATE` 抓快照 + 一次性归一化，整事务内不重读 |
| R4 | doc/10 §7 扭蛋流程文档不全 | 本日实施前 @product 巡检；不全则 GACHA-104 任务卡 §备注 标"参考 §3 拼豆并发结构类比"+ ticket 完工时反哺 doc/10 §7 |
| R5 | tokens.md §9 三段分镜动画在低端机微信卡顿 | mp 端动画用 CSS transform/opacity（GPU 友好），不用 setInterval 重绘；低端机 fallback 直接揭晓 + 渐入透明度 |
| R6 | GACHA-107 与会员中心订单 tab 数据互通需要 GZ-USER 订单表 schema | GZ-USER 订单表 schema 由 V1.1 GZ-USER 系列 ticket 落（如 GZ-USER-201 已 ✅），本日 GACHA-107 仅写订单 INSERT 不动 schema |
| R7 | "盲盒语义"在已有 mockup（gacha-draw.html）里仍写"抽奖" | mp 实施时改 t() 文案，不动 mockup 文件（mockup 是历史快照，文案以 doc/tokens.md §9 为准）|

---

## 日终 closing 命令

```bash
cd doc/daily/D09
cat reports/*.md > summary.md
# Kevin testing-human OK 后再 commit
git add -A && git commit -m "D09 (d8): V1.1 扭蛋机全链路 GACHA-101~107 ⭐"
# 然后写 D10/README.md
```
