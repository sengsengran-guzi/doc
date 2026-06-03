# GZ-GACHA-106 — mp 抽奖历史（"我开过的"）

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M2 §关键页面 §抽奖历史页
**关联拆解**: doc/02-需求拆解.md §3.3 GZ-GACHA-106
**关联 mockup**: design/mockup/gacha-history.html（仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-GACHA-104（`gz_gacha_draw` 表 + 抽奖事务落地后才有历史数据）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（**不是 §7 = 预购**）— N6 落 `gz_gacha_draw` 的 snapshot 口径 / E1 库存抢空整事务回滚（draw 不落）/ E7 改奖品名后 snapshot 历史不受影响
- **字段表**：doc/11-字段权威表.md **§7.3 `gz_gacha_draw`**（`machine_snapshot_json` / `prize_snapshot_json` JSON 结构、`drawn_time`、索引 `(tenant_id, user_id, drawn_time DESC)`）+ §7.4 `gz_gacha_order.business_status`（待发货跳转判定）
- **UI 参考**（mp）：doc/12-UI-权威索引.md §MP-GACHA-HISTORY（列表布局 / 机器筛选 / 详情联动）+ `design/mockup/gacha-history.html`（视觉参考，不逐像素还原）
- **稀有度 token**：doc/tokens.md §1.4（SSR `var(--c-r-ssr)` / SR `var(--c-r-sr)` / R `var(--c-r-r)` / N `var(--c-r-n)`，四档，不引第五档）
- **盲盒语义纪律**：D09/README.md §B（UI 可见文案 / `t('gacha.xxx')` key 用 扭蛋 / 开盒 / 获得 / 出现概率；**禁** 抽奖 / 中奖 / 开奖）

## What

mp 端"我开过的"历史列表：查当前用户 `gz_gacha_draw`（每行 = 一次成功开盒）按 `drawn_time` 倒序展示，可按机器筛选；单条显示机器名 / 获得物 snapshot（名称 + 稀有度 + 封面）/ 时间。后端读 snapshot 而非 join 奖品表。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/gacha/draw/my?machineId=&pageNum=&pageSize=`
  - sa-token mp-client 解析当前 `user_id`，仅查本人记录
  - 查 `gz_gacha_draw` 全部记录（**该表每行即一次成功开盒** — 库存抢空 / 退款分支整事务回滚不落 draw，doc/10 §8.E1 + doc/11 F7.3，**故天然不含 refunded / pending_pay**，无需也无 `draw_status` 列可过滤）
  - 走索引 `(tenant_id, user_id, drawn_time DESC)`，按 `drawn_time` DESC 分页
  - `machineId` 非空 → 追加 `machine_id = ?` 过滤
- [ ] **AC 2**：返回 VO 字段从 snapshot 解析为扁平字段（**不在 mp 端解 JSON**）
  - `drawId` / `drawNo`（`DRW-yyyyMMdd-6位`）
  - `machineId` + `machineName`（解 `machine_snapshot_json`）
  - 获得物：`prizeName` / `rarity`（SSR/SR/R/N）/ `prizeImageUrl`（由 `prize_snapshot_json.image_id` 经 `gz_file_object` 解析为 url，**不返回裸 image_id 给前端拼**）/ `referenceValueCent`（可空，空则前端不显示价值行）
  - `drawnTime`（ISO）
  - `businessStatus`（关联 `gz_gacha_order.business_status` ∈ `pending_ship`/`in_logistics`/`delivered`/`refunded`；用于"待发货"标签与跳转判定；按 `draw_id` 取对应订单状态）
- [ ] **AC 3**：机器筛选下拉/chip 列表来源 = 本人历史 **distinct machine**（`SELECT DISTINCT machine_id, machine_snapshot_json` from 本人 draw），**不全量拉 `gz_gacha_machine` 表**；接口 `GET /app/gz/gacha/draw/my/machines` 返回 `[{machineId, machineName}]`
- [ ] **AC 4**：page `pages/gacha/history.vue`
  - 顶部筛选条：「全部」chip + 历史出现过的机器 chip（数据来自 AC 3）
  - 列表项（`BizDrawHistoryItem`）：左侧获得物封面（直角 `var(--c-radius)` + 稀有度描边走 `var(--c-r-ssr/-sr/-r/-n)`）/ 中间机器名 + 获得物名 + 稀有度徽章（`var(--c-r-*)`，文案如「SSR」）/ 右侧相对时间「3 天前」+ 完整时间小字
  - `business_status='pending_ship'`（待发货）的列表项显示「待发货」标签
- [ ] **AC 5**：点击列表项行为
  - `business_status` ∈ `pending_ship`/`in_logistics` → 跳订单详情 `uni.navigateTo('/pages/me/order/detail?orderType=gacha&orderId=' + ...)`（路由耦合，不耦合下游 order schema；下游 order 详情页未上线则**降级**为本页 popup 展示 snapshot 详情，不报错）
  - 其余（`delivered` / 无衍生订单）→ 弹获得详情 popup（机器名 + 获得物 + 稀有度 + 时间 + 价值）
- [ ] **AC 6**：空数据 friendly —「还没开过扭蛋呢 — 去逛逛」+ CTA 跳扭蛋机列表 `pages/gacha/index.vue`
- [ ] **AC 7**：盲盒语义（D09/README §B）— 页面标题用「我开过的」/「我的获得」，列表用「获得」「开盒」；**grep 验证页面 + i18n key 无「抽奖 / 中奖 / 开奖」**
- [ ] **AC 8**：业务组件包一层 `components/biz/BizDrawHistoryItem.vue`（不直接撒 `<wd-*>`）；i18n 全走 `t('gacha.history.xxx')` + zh-CN / en-US
- [ ] **AC 9**：单测 happy — service `listMyHistory(userId, machineId, pageQuery)` 按 `machineId` 筛选 + 分页 + 按 `drawn_time` DESC；snapshot 解析为扁平 VO；distinct 机器列表查询
- [ ] **AC 10: Tier 2 入口可达**（CLAUDE.md §8.3）— Kevin 从已上线入口点 N 次能到达本页
  - 业务主线入口：会员中心「我开过的 / 扭蛋记录」入口（如该入口在下游 GZ-GACHA-107 图鉴 / GZ-USER 系列才建）
  - 入口未建时**本 ticket 加临时入口**到 `pages/gacha/index.vue`（扭蛋机列表页，GACHA-102 已上线）顶部「我开过的」按钮 + 注释 `<!-- TODO(Tier2-entry-temp): GZ-GACHA-106, remove when 会员中心扭蛋历史入口 merged -->`

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`（包 `org.dromara.gz.gacha.{controller,service,mapper,domain,dto}`）
  - `controller/applet/GzGachaDrawMpController.java` 加 `myHistory(query, pageQuery)` + `myMachines()` 方法（API 前缀 `/app/gz/gacha/...`）
  - service 加 `listMyHistory(userId, machineId, pageQuery)` + `listMyHistoryMachines(userId)`（走 `(tenant_id, user_id, drawn_time DESC)` 索引）
  - DTO：`GzGachaDrawHistoryVo`（扁平字段，含 snapshot 解析后的 machineName / prizeName / rarity / prizeImageUrl / referenceValueCent / businessStatus）
  - snapshot 解析 + `image_id → url` 解析在 controller/service 层完成（mp 端只收扁平字段）
  - **无新建表 / 无 DDL**（复用 GACHA-104 建的 `gz_gacha_draw` / `gz_gacha_order`；本卡纯查询）
- **小程序**：`code/main/miniapp/src/`
  - `pages/gacha/history.vue`
  - `components/biz/BizDrawHistoryItem.vue`
  - `api/gz-gacha.ts` 加 `getMyHistory(query)` / `getMyHistoryMachines()`
  - i18n `locale/zh-CN.ts` / `en-US.ts` 加 `gacha.history.*`
- **测试**：mvn 单测（service）+ vitest（mp）+ 微信开发者工具实操（Tier 2 入口可达 + happy path）

## 备注

### 强约束

1. **`gz_gacha_draw` 每行即成功开盒** — 库存抢空 / 退款分支整事务 ROLLBACK（draw 不落，doc/10 §8.E1 + doc/11 §7.3 F7.3）。**故历史天然不含 refunded / pending_pay**，与库存空回滚模型自洽；**不要臆造 `draw_status` 列做过滤**（该列不存在）。
2. **prize / machine 信息一律读 snapshot**（`prize_snapshot_json` / `machine_snapshot_json`），**不 join `gz_gacha_prize` / `gz_gacha_machine` 实时表** — snapshot 保证历史不受后台改奖品 / 机器下架影响（doc/10 §8.E7）。
3. **机器筛选用本人历史 distinct machine**，不全量拉 `gz_gacha_machine`（用户只关心自己开过的）。
4. **图片走 `image_id → gz_file_object → url`**，后端解析为 url 返回，**不返回裸 url、不返回裸 image_id 给前端拼**（D09 字段硬约束）。
5. **盲盒语义严格**（D09/README §B）：UI / i18n 用 扭蛋 / 开盒 / 获得；后端 enum / 表名 / 字段保留 `draw`（技术语义，如 `gz_gacha_draw` / `drawn_time`）。
6. **稀有度仅展示**（四档 `var(--c-r-*)`，tokens §1.4），不引第五档；不引 tokens §9（不存在）。
7. `tenant_id` 走自动填充（查询天然带租户 1001 上下文，不显式拼）；mp 权限走 sa-token mp-client 当前用户，**只查本人**（不需 `@SaCheckPermission` —— 是 C 端本人数据，非管理端）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | prize / machine 信息读 snapshot 而非 join 实时表 | snapshot 保证历史不受后台改奖品 / 机器下架影响（doc/10 §8.E7，GACHA-104 N6.⑦ 同源决策）|
| D2 | 历史"不含 refunded"靠**回滚模型**实现，不靠状态过滤 | `gz_gacha_draw` 仅成功事务落行（doc/11 F7.3）；查全表即"我开过的"，无需 `draw_status` |
| D3 | 筛选机器列表用本人历史 distinct | 用户只关心自己开过的机器；查全量浪费 + 含未开过机器无意义 |
| D4 | `pending_ship`/`in_logistics` 点跳订单详情走路由，不耦合 order schema | 跳转 `/pages/me/order/detail?orderType=gacha&orderId=`，下游订单详情未上线则降级本页 popup |
| D5 | 时间显示"相对 + 完整"双格式 | 相对时间易读 / 完整时间便于复核 |
| D6 | snapshot JSON 在后端解扁平字段返回 | mp 端不解 JSON（省端侧性能 + 统一口径）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 历史记录数大（活跃用户开几百次）→ 分页性能 | 走 `(tenant_id, user_id, drawn_time DESC)` 索引；分页 size=20 |
| R2 | 上游 `gz_gacha_draw` 表未建（GACHA-104 未完工）则本卡无法实施 | **§0 自检 grep migration 目录确认 `gz_gacha_draw` / `gz_gacha_order` 表实际存在**（不假设上游已建）；不存在 → STOP 挂起等 GACHA-104 |
| R3 | 订单详情页（`/pages/me/order/detail`）在 V1.1 下游才上线，跳转报错 | 跳转走路由不耦合 schema；下游详情页未上线 → 降级本页 popup（AC 5），不 hard-fail |
| R4 | 误以为有 `draw_status` 列做过滤 → 写出永远查不到数据的 WHERE | 不存在该列；查全表即本人成功历史（强约束 1 + D2）|

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D09/GZ-GACHA-106 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
