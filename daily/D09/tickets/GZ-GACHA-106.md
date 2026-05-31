# GZ-GACHA-106 — mp 抽奖历史

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M2 §关键页面 §抽奖历史页
**关联拆解**: doc/02-需求拆解.md §3.3 第 818 行
**关联 mockup**: design/mockup/gacha-history.html（仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-GACHA-104

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md §7 扭蛋抽奖流（步骤 8 历史查询）
- **字段表**：doc/11-字段权威表.md §7.3 `gz_gacha_draw`（prize_snapshot JSON 结构）
- **UI 索引**：doc/12-UI-权威索引.md §MP-GACHA-HISTORY（列表布局 / 筛选 / 详情联动）
- **tokens.md §9**：盲盒语义"我开过的" / "已获得"

## What

用户的"我开过的"列表：按时间倒序展示历史 draw 记录，按机器筛选；与会员中心订单 tab 数据互通（pending_delivery 的可点跳订单详情）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/draw/my?machineId=&pageNum=&pageSize=`：
  - sa-token mp-client → 当前 user_id
  - 查 draw_status='drawn' 的记录（不含 pending_pay / refunded）
  - 按 drawn_at DESC 分页
  - 返回字段：drawId / machine_name_snapshot / prize_snapshot(name+rarity+cover_url) / drawn_at / delivery_status
- [ ] **AC 2**：page `pages/gacha/history.vue`：
  - 顶部筛选条（wd-tabs 或自定义 chip 组）：「全部机器」/ 历史出现过的机器列表
  - 列表项：左侧奖品封面（直角 var(--c-radius)=0 + 稀有度边框走 var(--c-r-ssr/-sr/-r/-n)）/ 中间机器名 + 奖品名 + 稀有度徽章（doc/13 §3.2 待建 Biz 组件）/ 右侧时间（相对时间"3 天前"+ 完整时间小字）+ 待发货标签（如 delivery_status='pending_delivery'）
  - 点击列表项 → 如 pending_delivery 则跳订单详情（会员中心订单 tab）；如 delivered 则展示获得详情 popup
- [ ] **AC 3**：空数据 friendly：「还没开过扭蛋呢 — 去看看」+ CTA 跳列表
- [ ] **AC 4**：盲盒语义（tokens.md §9）：页面标题用「我开过的」/「我的获得」，不用「我的中奖」
- [ ] **AC 5**：业务组件包一层 `components/biz/BizDrawHistoryItem.vue`
- [ ] **AC 6**：i18n 走 `t('gacha.history.xxx')`
- [ ] **AC 7**：单测 happy（按 machineId 筛选 + 分页）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaDrawMpController.java` 加 `myHistory(query, pageQuery)` 方法
  - service 加 `listMyHistory(userId, machineId, pageQuery)`（走 `idx_user_drawn_at` 索引）
- **小程序**：
  - `pages/gacha/history.vue`
  - `components/biz/BizDrawHistoryItem.vue`
  - `api/gz-gacha.ts` 加 `getMyHistory(query)`
- **测试**：mvn + vitest + 微信开发者工具实操

## 备注

### 强约束

1. **不返回 pending_pay / refunded 记录**（用户视角"我开过的"仅含成功揭晓的）
2. **机器筛选用 distinct machine_id 拉历史出现的机器**（不全量拉机器表）
3. **走索引 `idx_user_drawn_at`**（GACHA-104 已加）
4. **盲盒语义严格**（tokens.md §9）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | prize 信息读 snapshot 而非 join prize 表 | snapshot 保证历史不受后台改奖品影响（GACHA-104 D3 同源决策）|
| D2 | 筛选机器列表用历史 distinct（不查 machine 表全量）| 用户只关心自己抽过的；查全量浪费 + 包含未抽过机器无意义 |
| D3 | pending_delivery 点跳订单详情走 GZ-USER 订单 tab | 与会员中心订单 tab 数据互通（doc/02 §3.3 行 823） |
| D4 | 时间显示"相对+完整"双格式 | 相对时间易读 / 完整时间方便复核 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 历史记录数大（活跃用户抽几百次）→ 分页性能 | `idx_user_drawn_at (user_id, drawn_at DESC)` 索引；分页 size=20 |
| R2 | prize_snapshot JSON 解析在 mp 端有性能损耗 | 后端 controller 层解析 JSON 转扁平字段返回，mp 端直接用 |
| R3 | 订单 tab schema 在 V1.1 USER 系列变更影响跳转 | 跳转走路由 `/pages/me/order/detail?orderId=`，不耦合 schema |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
