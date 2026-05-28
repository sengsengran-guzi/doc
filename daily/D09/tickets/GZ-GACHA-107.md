# GZ-GACHA-107 — 集齐特典 / 图鉴模块（V1.1 简版）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md tokens.md §9 收集驱动
**关联拆解**: doc/02-需求拆解.md §3.3 第 832 行（**V1.1 简版，深化推 v2**）
**关联 mockup**: design/mockup/me-collection.html（视觉参考）
**关联 ADR**: —
**依赖**: GZ-GACHA-105

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md §7 扭蛋抽奖流（步骤 9 图鉴 — 与会员中心订单 tab 数据互通）
- **字段表**：doc/11-字段权威表.md §7.2 `gz_gacha_prize` + §7.3 `gz_gacha_draw`（图鉴 = 用户 draw 记录在 machine 维度的聚合 vs prize 全集对比）
- **UI 索引**：doc/12-UI-权威索引.md §MP-ME-COLLECTION（图鉴布局 / 已得 vs 灰显 / 集齐徽章）
- **tokens.md §9 ★**：「收集驱动 > 单抽欲望」是甲方明确诉求；"集齐 → 徽章"是核心激励

## What

会员中心图鉴页：按机器分组展示用户已获得 vs 未获得的奖品全集；集齐显示徽章。**V1.1 简版**：不做炫耀分享 / 收藏 NFT / 跨机器套装（深化推 v2）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/collection/my?machineId=`：
  - sa-token mp-client → 当前 user_id
  - 如 machineId 传 → 仅返回该机器的图鉴；不传 → 返回所有曾抽过的机器图鉴
  - 返回结构：machines 数组，每个 machine 含：machineId / machineName / coverUrl / prizes（含全部奖品）/ ownedPrizeIds（用户已得集合）/ isCompleteSet（是否集齐）
- [ ] **AC 2**：page `pages/me/collection.vue`：
  - 顶部机器筛选条（wd-tabs，第一项「全部」）
  - 按机器分组卡片（折叠头 + 展开内容）：
    - 头：机器封面 + 名称 + 进度「已收集 X/Y」+ 进度条（.stock-bar-track + .stock-bar-fill 走 tokens.md 共享 class）+ 集齐时显示徽章 🏆
    - 内容：奖品网格（3 列）— 已得高亮（彩色 + 稀有度边框）/ 未得灰显（grayscale + 半透明 + 锁标）
  - 已得奖品点击 → 弹 popup 展示获得时间 + 跳对应 draw 记录（GACHA-106 详情）
  - 未得奖品点击 → 弹 popup「还差 X 件集齐」+ CTA「去开盒」跳详情页
- [ ] **AC 3** ⭐ **与会员中心订单 tab 数据互通**（doc/02 §3.3 行 823 + 行 838 V1.1 简版）：
  - 图鉴页头部「我的获得 → 订单」入口跳 `/pages/me/order/list?source=gacha`（筛 pending_delivery 的扭蛋订单）
  - 订单详情可反向跳图鉴对应 machine
- [ ] **AC 4**：集齐徽章 UI：
  - isCompleteSet=true → 进度条满 + 显示金色徽章 🏆 + 动效（淡入 + 旋转 1 圈）
  - 徽章下方 chip「集齐特典 — 已解锁」
  - 不做"特典奖品发放" / "兑换码"（V2 推）
- [ ] **AC 5**：盲盒语义（tokens.md §9）：
  - 页面标题「我的图鉴」/「收藏图鉴」
  - 进度文案「已收集 X/Y 件」（不用"中奖率"等）
- [ ] **AC 6**：业务组件包一层：
  - `components/biz/BizCollectionMachineGroup.vue`（机器分组卡）
  - `components/biz/BizCollectionPrizeCell.vue`（奖品格子 — 已得 vs 灰显）
  - `components/biz/BizCompleteSetBadge.vue`（集齐徽章 + 动效）
- [ ] **AC 7**：i18n 走 `t('me.collection.xxx')`
- [ ] **AC 8**：单测：
  - happy（mock 3 个奖品 / 用户已得 2 个 → isCompleteSet=false，ownedPrizeIds=[1,2]）
  - 集齐 happy（mock 3 个 / 用户已得 3 个 → isCompleteSet=true）
  - 空机器（mock 用户未抽过任何 → 返回空 machines 数组）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/applet/GzGachaCollectionMpController.java`（`/app/gz/gacha/collection`）
  - `service/IGzGachaCollectionService.java` + impl
  - service 内查询逻辑：
    - 1\) 查用户 distinct machine_id（从 gz_gacha_draw 拉）
    - 2\) 按 machine 查全部 prize（含 stock=0）
    - 3\) 按 machine 查用户 distinct prize_id（已得集合）
    - 4\) 装配 + 计算 isCompleteSet（ownedPrizeIds 长度 == prizes 长度）
  - 新增 VO `GzGachaCollectionVO`（含嵌套 MachineGroup → Prize 数组）
- **小程序**：
  - `pages/me/collection.vue`
  - `components/biz/BizCollectionMachineGroup.vue` + `BizCollectionPrizeCell.vue` + `BizCompleteSetBadge.vue`
  - `api/gz-gacha.ts` 加 `getMyCollection(machineId?)`
  - GACHA-105 揭晓页底部「查看图鉴」按钮跳本页（已在 GACHA-105 实现）
- **测试**：mvn 单测 + 微信开发者工具实操图鉴页

## 备注

### 强约束

1. **V1.1 简版**（doc/02 §3.3 行 838 明确）：不做分享 / NFT / 套装；只做「按机器分组 + 已得 vs 灰显 + 集齐徽章」
2. **集齐判定基于 prize 全集**（含 stock=0 的奖品）— 否则用户永远集不齐（最后 1 个 SSR 抽完 stock=0 后理论上仍要在用户图鉴显示并标"已得"）
3. **与会员中心订单 tab 互通入口**（doc/02 §3.3 行 823）— 图鉴顶部「订单」入口 + 订单详情反向跳图鉴
4. **盲盒语义严格**（tokens.md §9）
5. **不发放集齐特典奖励**（仅显示徽章；奖励发放推 V2）— 避免 V1.1 内引入新的奖励发放链路

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 集齐判定基于 prize 表全集而非用户曾见到的 prize | 用户全集集齐 = 该机器所有奖品都得过；否则用户没见过库存=0 的奖品会永远集不齐 |
| D2 | 不做"按 IP 系列" / "跨机器套装" | V1.1 简版（doc/02 行 838）；deepen 在 v2 |
| D3 | 集齐徽章仅显示不发奖 | 避免 V1.1 内引入实物奖励发放链路；徽章本身是社交价值激励 |
| D4 | 灰显未得奖品 + grayscale CSS filter | 视觉上"未拥有"清晰；激发收集欲（tokens.md §9 收集驱动）|
| D5 | 进度条 / 徽章动效复用 tokens.md §6 共享 class | 视觉一致性 + 不引新样式 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 用户抽过 N 个机器 + 每机器 10 奖品 → 接口返回 JSON 大 | 后端只返回曾抽过的机器（distinct machine_id），不返回全机器 |
| R2 | "集齐" 判定的奖品全集与 GACHA-104 抽完即下架冲突（机器被运营手动新增奖品后用户图鉴突然变"未集齐"）| 接受：是预期行为；用户会激励重新抽 — 这正是 collection 驱动；运营层面注意"新增奖品"是合理预期 |
| R3 | 灰显 grayscale 在不同微信版本兼容性 | 主流支持 webkit-filter；老版本 fallback 半透明 + 锁图标 |
| R4 | 订单 tab 入口跳转路径与 V1.1 USER 系列约定不一致 | 实施前确认 GZ-USER-201（订单列表）路径 `/pages/me/order/list?source=` 已就位 |

### 与 V2 的边界（明示）

V1.1 **不做**：
- 集齐特典实物奖励发放（兑换码 / 邮寄）
- 炫耀分享卡片
- 收藏夹 / 收藏点赞
- 跨机器套装 / 季度套装
- 图鉴成就系统（XX 件成就解锁）

→ 全部推 v2，doc/02 §3.3 行 838 已锚定

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
