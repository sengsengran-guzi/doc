# D09 — Progress（扭蛋域全链路 GACHA-101~107）

> AI 测试（Tier 1A + 1B）全 ✅ → ticket close 解锁下游。mp ticket 另进「人验」列待 Kevin Tier 2 批量人验。

---

| Ticket | 标题 | 端 | Tier 1A | Tier 1B | 人验(Tier2) | 状态 |
|---|---|---|---|---|---|---|
| GZ-GACHA-101 | 扭蛋机+奖品池数据模型+admin CRUD | 后端+admin | ✅ 17测 | ✅ E2E（R1 create_dept / R2 路由前缀 已修）| — 纯admin无人验 | ✅ close |
| GZ-GACHA-104 ⭐ | 开盒事务+防超卖（4表原子+失败重抽，必出无退款）| 后端 | ✅ 29测+并发压测证伪超卖 | ✅ 集成+契约+无退款=0 | — 纯后端无人验 | ✅ close |
| GZ-GACHA-102 | mp 扭蛋机列表 | 后端+mp | ✅ 10服务测 | ✅ 端点live200+15vitest | ⬜ 待批 | ✅ close |
| GZ-GACHA-103 | mp 单机详情+概率公示（实时归一化）| 后端+mp | ✅ 24测 | ✅ 端点live（同口径normalizer）+28vitest | ⬜ 待批 | ✅ close |
| GZ-GACHA-105 | mp 三段分镜动画揭晓 | 后端+mp | ✅ draw/status 4场景 | ✅ +229vitest+build绿 | ⬜ 待批 | ✅ close |
| GZ-GACHA-106 | mp 抽奖历史 | 后端+mp | ✅ history 9场景 | ✅ 端点live+20vitest | ⬜ 待批 | ✅ close |
| GZ-GACHA-107 | mp 图鉴（按机器分组+集齐徽章）| 后端+mp | ✅ collection 9场景 | ✅ 集齐进度live+25vitest | ⬜ 待批 | ✅ close |

**revision 轮次**：GACHA-101 = 2 轮（R1 漏 create_dept 列 500 / R2 奖品池路由缺 /gz 前缀 404，均当场闭环修）；其余 0 轮。

---

## Tier 2 批量人验清单（mp ticket，Kevin 自定节奏集中跑）

待验 ⬜：102 列表 / 103 详情概率 / 105 揭晓动画 / 106 历史 / 107 图鉴。
建议一条龙 happy path（真机）：**首页扭蛋入口 → 列表 → 点机器进详情（看概率条）→ 投币开盒（真实 wx.requestPayment 0.01元）→ 三段动画揭晓 → 抽奖历史 → 我的→我的图鉴（看集齐进度）**。
重点验：微信原生支付真机唤起 / C 设计系统遵循度（粗墨边·硬投影·朱红·稀有度光晕四档）/ 盲盒文案语感（扭蛋·开盒·获得·出现概率，无抽奖中奖）。

人验入口可达性（dev 已接通）：
- 列表：首页「扭蛋」入口 + teaser 卡（已上线，N=1）
- 详情：列表点机器卡（N=1）
- 揭晓：详情「投币开盒」（N=1，dev wxMOCK 短路；真机走真实支付）
- 历史：列表 filter-bar「我开过的 →」**临时入口**（`Tier2-entry-temp: GZ-GACHA-106`，待会员中心开盒历史正式入口 merge 后清理）
- 图鉴：「我的」tab 九宫格「我的图鉴」正式入口 + 揭晓页「查看图鉴」（N=1）

---

## 阻塞 / 风险（D09 实战暴露，已闭环）

1. **支付回调 SPI 构造期循环依赖**（D08/ORD 遗留，阻 app 启动 + 阻 GACHA-104 SPI）→ 已修 `ObjectProvider` 断环，98 gz-common 测过，app 启动绿。
2. **gz_gacha 表漏 create_dept + create_by/update_by 误 VARCHAR**（GACHA-101）→ `V202606171002` ALTER 修，已应用。
3. **gz_ord 三表（product/sku/order）同源潜伏 create_dept bug**（D06，从未对真实 MySQL 跑过 admin E2E）→ **非 D09 范围，flag Kevin**（见 summary；将来 ORD admin CRUD 会 500，建议补同型 ALTER fix + 审 create_by 类型/seed）。
4. **本机 docker daemon 本会话掉过 2 次** → 已 2 次拉起恢复（named volume 数据无损）；若频繁掉建议查 Docker Desktop 稳定性。

## 已挪到明日的 ticket

无。D09 七个 ticket 全部 close。
