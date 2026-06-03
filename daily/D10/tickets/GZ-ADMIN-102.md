# GZ-ADMIN-102 — 扭蛋池管理（plus-ui，权重前端实时归一化）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §扭蛋规则（必中 / 概率公示 / 不保底 / 抽完即下架）
**关联拆解**: doc/02-需求拆解.md §3.5 GZ-ADMIN-102 扭蛋池管理（admin 端）
**关联 mockup**: design/mockup/admin-gacha-pool.html ⚠️ admin 走 ruoyi/Element Plus 默认审美（**不套用 C 系统**），mockup 仅作页面结构 / 功能项参考，不参考视觉像素
**关联 ADR**: —
**依赖**: GZ-GACHA-101（扭蛋机 + 奖品池数据模型，D08 — `gz_gacha_machine` / `gz_gacha_prize` 表 + DDL 由其建）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（§8.N2 单机详情含奖品池 + 实时归一化概率 / §8.N3 概率公示口径 / §8.N6 抽奖事务库存扣减 / §8.E3 运营改概率配置并发 / §8.E7 改奖品名图后历史 snapshot 不受影响 / Q8.3 不做保底字段不出）
- **字段表**：doc/11-字段权威表.md **§7.1 `gz_gacha_machine`** + **§7.2 `gz_gacha_prize`**（含 §7.2「计算口径」框：`P(prize_i) = weight_i / Σ weight_j where j ∈ {enabled=1 AND stock_remain>0}`）+ **附录 A.10 稀有度字典 `gz_gacha_rarity`（SSR/SR/R/N 四档）** + 附录 §dict 表 `gz_gacha_rarity` 行
- **UI 参考**：admin 走 ruoyi/Element Plus 默认审美（**不套用 C 系统**），不引用 mockup 像素；mockup `admin-gacha-pool.html` 仅作页面结构 / 功能项参考

## What

admin 端（plus-ui）扭蛋池管理：扭蛋机 CRUD + 上下架开关 + 奖品池可视化编辑（添加奖品 / 设稀有度 / 概率权重 / 库存 / **每行实时显示归一化后概率 %**）。**概率权重不强制总和 100，系统自动归一化**；前端 reactive 计算「归一化后概率%」列展示给运营 sense check，归一化基数**仅统计在池可参与抽奖的奖品**（`enabled=1 AND stock_remain>0`）。本卡只做 admin 配置 + 展示侧，**运行时抽奖归一化由 GACHA-103 抽奖事务实现，本卡不动**。

## AC（验收标准）

- [ ] **AC 1**：后端 `org.dromara.gz.gacha.controller.GzGachaMachineController`（admin 路径 `/system/gz/gacha/machine`）+ `GzGachaPrizeController`（admin 路径 `/system/gz/gacha/prize`，按 `machineId` 查列表），CRUD 走 ruoyi 标准范式（BO/VO + `IGzGachaMachineService` / `IGzGachaPrizeService` + impl + mapper），包名 `org.dromara.gz.gacha.{controller,service,mapper,domain,dto}`。
- [ ] **AC 2**：plus-ui 机器列表页 `views/gz-gacha/pool/index.vue`（菜单路径 `/gacha/pool`），plus-ui BizTable + Element Plus 默认组件。toolbar：搜索（机器名 / `ip_tag`）+「新建扭蛋机」按钮；列表列：封面（`cover_image_id` 解析）/ 机器名 / 单抽价（`single_price_cent` → 元 display）/ 奖品数（count prizes）/ 池内总剩余库存（Σ `stock_remain`）/ 状态（`status` 三态 `on_shelf`/`off_shelf`/`auto_off`；`on_shelf↔off_shelf` 用 switch 切，`auto_off` 只读 tag 不可手动设）/ 操作（编辑 / 进入奖品池 / 删除软删 `del_flag=2`）。
- [ ] **AC 3**：新建 / 编辑机器抽屉（el-drawer + el-form）：机器名 `name` / 封面 `cover_image_id`（OSS 上传，存 FK 不存裸 url）/ 单抽价 `single_price_cent`（前端元 input，提交转分）/ 十连价 `ten_pack_price_cent`（可空）/ IP 标签 `ip_tag`（可空）/ 上架时间 `online_time` / 计划下架时间 `offline_time`（可空）/ 上下架 switch（`status`）。`machine_no` 后端按 `GM-yyyyMMdd-6位序号` 生成，不在表单录入。
- [ ] **AC 4**：点机器行「进入奖品池」→ 切奖品池编辑视图（同页子视图，路由 `?machineId=` 或本地 state 切换），表格列：封面（`image_id` 解析）/ 奖品名 `name` / 稀有度 chip（按 `gz_gacha_rarity` 字典渲染 **SSR/SR/R/N 四档**，对应 `--r-ssr/--r-sr/--r-r/--r-n` 色，admin 端用 el-tag 默认色即可不强求 C token）/ 概率权重 `weight`（el-input-number，admin 可编辑，≥0 整数）/ **归一化后概率%（reactive 计算预览，readonly）** / 初始库存 `stock_initial` / 当前剩余 `stock_remain` / 库存进度条（`stock_remain/stock_initial`）/ 参与开关 `enabled`（0 临时下架 / 1 参与）/ 操作（编辑 / 删除）。
- [ ] **AC 5**：「添加奖品」抽屉表单：奖品名 `name` / 稀有度 select（字典 `gz_gacha_rarity` 四档）/ 封面 `image_id`（OSS 上传，存 FK）/ 概率权重 `weight`（≥0 整数）/ 初始库存 `stock_initial`（新增时 `stock_remain = stock_initial`，后端落库）/ 参考价 `reference_value_cent`（可空，元 input 转分）/ 参与开关 `enabled`（默认 1）。`prize_no` 后端按 `PRZ-yyyyMMdd-6位序号` 生成。
- [ ] **AC 6**：**概率权重不强制总和 100，系统自动归一化**——admin 输入任意 `weight`（≥0 整数）保存不报「总和≠100」错；前端「归一化后概率%」列 reactive 计算：`prize.weight / Σ(参与奖品 weight) × 100`，保留 2 位小数。归一化基数**仅统计 `enabled=1 AND stock_remain>0` 的奖品**（口径锚定 doc/11 §7.2 计算框 + doc/10 §8.N3），与 GACHA-103 运行时抽奖归一化同口径。
- [ ] **AC 7**：表格底部显示「当前归一化基数：Σweight=XX，参与奖品数=Y（仅统计可参与抽奖：enabled=1 且 有库存）」；当某奖品 `enabled=0` 或 `stock_remain=0` 时其归一化%列显示 `—`（不参与），且 `weight` 改动即时刷新全表归一化%（reactive，不需后端往返）。
- [ ] **AC 8**：奖品 `weight` / `stock` / `enabled` 修改保存 → 后端 UPDATE（带乐观锁 `version`），写 ruoyi 操作日志（`@Log(title="扭蛋池配置", businessType=UPDATE)`，落 `sys_oper_log`，对齐 doc/11 附录 §dict「概率改动」审计语义）。
- [ ] **AC 9**：admin 权限：list `gz:gacha:pool:list` / query `gz:gacha:pool:query` / edit `gz:gacha:pool:edit`（机器 + 奖品共用 pool 权限组）；菜单 SQL `V202606080300__GZ-ADMIN-102-menu.sql` 插入 **menu_id 10100-10120 段**（GZ-GACHA admin 段，CLAUDE.md §6 #6）。
- [ ] **AC 10**：i18n 全覆盖（`gz-gacha.pool.*`），UI 可见文案遵循**盲盒语义**——用「扭蛋 / 奖品 / 出现概率 / 归一化后概率」，**禁** 「抽奖 / 中奖 / 开奖」字样（后端 enum / 字段保留 `draw` 不受此限）。
- [ ] **AC 11**：单测——`GzGachaMachineServiceImplTest`（建机器 + machine_no 生成 + 软删 happy）+ `GzGachaPrizeServiceImplTest`（加奖品 stock_remain=stock_initial + weight 更新带 version happy）；前端归一化 composable `useNormalizedProbability.ts` 用 vitest 单测：3 奖品不同 weight 求和=100%、含 1 个 `stock_remain=0` / 1 个 `enabled=0` 时该两项显示 `—` 且不计入基数。

> 纯 admin / 后端 ticket，无 mp 端改动，**跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/GzGachaMachineController.java` / `controller/GzGachaPrizeController.java`
  - `service/IGzGachaMachineService.java` + `service/impl/GzGachaMachineServiceImpl.java`
  - `service/IGzGachaPrizeService.java` + `service/impl/GzGachaPrizeServiceImpl.java`
  - `domain/bo`（`GzGachaMachineBo` / `GzGachaPrizeBo`）+ `domain/vo`（`GzGachaMachineVo` / `GzGachaPrizeVo`）
  - `mapper/`（MyBatis-Plus，`@TableLogic del_flag`）
  - **表 DDL 已由 GZ-GACHA-101 落地**（`gz_gacha_machine` / `gz_gacha_prize`）——本卡**不新建表 DDL**，只新增菜单 SQL `ruoyi-admin/src/main/resources/db/migration/V202606080300__GZ-ADMIN-102-menu.sql`（menu_id 10100-10120 段；时间戳 > 当前最大 `V202606051200`）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-gacha/pool/index.vue`（机器列表 + 进入奖品池子视图）
  - `views/gz-gacha/pool/components/MachineDrawer.vue`
  - `views/gz-gacha/pool/components/PrizeTable.vue`（奖品池表格 + 归一化预览 + 底部基数行）
  - `views/gz-gacha/pool/components/PrizeDrawer.vue`
  - `composables/useNormalizedProbability.ts`（reactive 归一化%，过滤 enabled=1 && stock_remain>0）
  - `api/gz-gacha/machine.ts` + `api/gz-gacha/prize.ts`
  - `lang/zh_CN/gz-gacha.ts` + `lang/en_US/gz-gacha.ts`（`gz-gacha.pool.*`）
- **小程序**：不动
- **测试**：service 单测 + 前端 composable vitest + admin Playwright（kevin-qa：建机器 → 加 5 奖品不同 weight → 验归一化%求和=100、含 0 库存项显 `—`）

## 备注

### 强约束

1. **概率权重不强制总和 100，系统自动归一化**（AC 6/7 锚定）：admin UI **不做总和=100 校验报错**；归一化基数 = `weight_i / Σ weight_j`，`j ∈ {enabled=1 AND stock_remain>0}`，与 doc/11 §7.2 计算框 + doc/10 §8.N3 一字不差。运行时抽奖归一化在 GACHA-103 事务（SELECT FOR UPDATE 锁快照后归一），本卡只做配置 + 前端预览，**不实现抽奖逻辑**。
2. **库存空 / 临时下架奖品不参与归一化**（AC 7）：`stock_remain=0` 或 `enabled=0` 的奖品归一化%列显 `—`、不计入 Σ 基数——口径与 doc/10 §8.N6 抽奖事务「校验至少 1 个有库存 → 归一化在池奖品权重」一致，运营心智统一。
3. **稀有度走字典 `gz_gacha_rarity`，四档 SSR/SR/R/N**（doc/11 附录 A.10）——**不是五档，无 UR**；admin 端 chip 用 el-tag 默认色即可（C 稀有度 token `--r-ssr` 等是 mp 侧用，admin 不套 C 系统）。
4. **库存字段命名钉死**：`stock_initial`（初始库存）/ `stock_remain`（当前剩余）——**不用 stock_current / stock_total / init / left**（doc/11 §7.2 已锁；扭蛋奖品用 initial/remain，与预购商品 stock_total/stock_remain 是各自表口径，本卡用 prize 的 initial/remain）。
5. **状态枚举 `on_shelf` / `off_shelf` / `auto_off`**（doc/11 §7.1）——`auto_off`（库存抢空 / 到 `offline_time` 自动下架）只读不可手动设；**不用 off_shelf 之外的 archived / closed**。
6. **金额 `_cent`（分）**：`single_price_cent` / `ten_pack_price_cent` / `reference_value_cent`——前端元 input 提交转分，**不用 `_fen`**。
7. **图片走 FK**：机器 `cover_image_id` / 奖品 `image_id` → `gz_file_object`，**不存裸 url**。
8. **`del_flag` 仅 2 值**（0 正常 / 2 删除），对齐 ruoyi `@TableLogic`；删除走软删。
9. **`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`**：INSERT 不显式赋 tenant_id（走自动填充）；查询走 ruoyi 租户拦截。
10. **menu_id 10100-10120 段**（GZ-GACHA admin，CLAUDE.md §6 #6）；GACHA 业务表段是 10000-10099，本卡 admin 菜单在 10100 段。
11. **admin 走 ruoyi/Element Plus 默认审美**：el-table / el-drawer / el-form / el-input-number / el-tag，不调样式，不引用 mockup 像素（admin 不评判视觉）。
12. **盲盒语义（AC 10）**：UI 可见文案 / i18n key 用「扭蛋 / 奖品 / 出现概率 / 归一化后概率」，禁「抽奖 / 中奖 / 开奖」；后端 `draw` enum / 字段不改。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 归一化预览前端 reactive 计算（`useNormalizedProbability.ts`）| 运营改 weight 即时刷新，无需后端往返；后端只存 raw weight |
| D2 | 归一化基数仅含 `enabled=1 AND stock_remain>0` | 与运行时抽奖（GACHA-103 / doc/10 §8.N6）同口径，运营 sense check 所见即抽奖所得 |
| D3 | 机器 + 奖品池同页（子视图切换）| 强相关业务对象；分页跳转打断配置思路（mockup 同结构） |
| D4 | 奖品 inline 编辑独立保存（带 version 乐观锁）| 保存粒度小不易冲突；对齐 doc/10 §8.E3 并发改概率（事务侧已 SELECT FOR UPDATE 锁快照，配置侧只需乐观锁兜底） |
| D5 | `weight` INT 整数 | doc/11 §7.2 已锁；整数权重运营理解友好，归一化在展示/抽奖时算百分比 |
| D6 | 本卡不实现抽奖事务 | 抽奖归一化 + 扣库存是 GACHA-103 范围；本卡只配置 + 预览 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | GACHA-101 表 schema 未落 / 字段不全（缺 rarity / weight / stock_initial / stock_remain / enabled）| **§0 自检 grep migration 目录确认上游表实际存在**：`ls .../db/migration/ \| grep GZ-GACHA-101` + `grep -rl 'gz_gacha_machine\|gz_gacha_prize' .../db/migration/`，并 `DESC gz_gacha_prize` 核字段对齐 doc/11 §7.2；缺则 STOP 回 D08 GACHA-101 收尾，本卡不开工 |
| R2 | 误把权重总和理解为必须 100 | UI 文案明确「权重比例制（无需总和 100，系统自动归一化）」+ 表格底部显当前 Σweight + 参与奖品数（AC 7） |
| R3 | 归一化%浮点精度 | 保留 2 位小数 + 文案「归一化后概率」明确是展示值，最终判定以 GACHA-103 抽奖事务为准 |
| R4 | 改 weight 后运行中抽奖拿旧值 | 非本卡责任：doc/10 §8.E3 已裁定「事务已 SELECT FOR UPDATE 锁住快照 → 用旧权重抽（一致性优先）」；配置侧即时落库即可 |
| R5 | 稀有度档数搞错（误加 UR / 五档）| 锚定 doc/11 附录 A.10 = **四档 SSR/SR/R/N**，字典 `gz_gacha_rarity` 渲染，不硬编码档位 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D10/GZ-ADMIN-102 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
