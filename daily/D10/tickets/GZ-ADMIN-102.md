# GZ-ADMIN-102 — 扭蛋池管理

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.2 扭蛋池管理 + M2 §概率算法
**关联拆解**: doc/02-需求拆解.md §3.5 第 921-932 行
**关联 mockup**: design/mockup/admin-gacha-pool.html ⚠️ V1.0/V1.1 设计冻结期：admin 走 ruoyi 默认 + plus-ui BizTable / Element Plus 默认组件，**不参考 mockup 视觉**；mockup 仅作页面结构 / 功能项参考
**关联 ADR**: —
**依赖**: GZ-GACHA-101 ✅(D08/D09 — 机器 + 奖品 schema 已落)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程** §业务规则（概率算法 / 库存）+ §并发与防超卖
- **字段表**：doc/11-字段权威表.md **§7.1 `gz_gacha_machine` 扭蛋机** + **§7.2 `gz_gacha_prize` 奖品**（概率权重 weight 字段 + 库存 stock_current / stock_initial 字段 + 稀有度 rarity 字段）+ §A.6 状态字典 + §10.2 sys_dict_data §稀有度字典
- **UI 参考**（设计冻结期）：doc/12 §AD-GACHA-POOL §页面结构（机器列表 + 奖品池编辑视图 + 实时归一化概率预览）

## What

admin 端扭蛋池管理：扭蛋机器 CRUD + 上下架开关 + 奖品池可视化编辑（添加奖品 / 设置稀有度 / 概率权重 / 库存 / 实时归一化%预览）。**概率权重不强制总和 100，系统自动归一化**；后台前端 reactive 计算"实时归一化后概率"列展示给运营 sense check。

## AC（验收标准）

- [ ] **AC 1**：admin 端 plus-ui 页 `views/gz-gacha/pool/index.vue`（菜单路径 `/gacha/pool`），plus-ui BizTable + Element Plus 默认风格
- [ ] **AC 2**：机器列表 toolbar：搜索 + "新建扭蛋机"按钮；列表列：thumb（机器封面）/ 机器名 / 单抽价（display 元）/ 奖品池数 / 总库存（sum prizes stock_current）/ 状态 switch（上下架）/ 操作（编辑机器 / 进入奖品池 / 删除软删）
- [ ] **AC 3**：新建 / 编辑机器 抽屉：机器名 / 封面（OSS 上传）/ 单抽价（分）/ 描述（短文本，不富文本）/ 排序 / 上下架 switch
- [ ] **AC 4**：选中机器（点列表"进入奖品池"按钮）→ 切到奖品池编辑视图（同页 tab 切换 or 路由 `?machineId=`），显示奖品列表表格：
  - 列：thumb / 奖品名 / 稀有度 chip（按 doc/11 §A.6 字典渲染：N / R / SR / SSR / UR）/ 概率权重（input number，admin 可编辑） / **实时归一化%（reactive 计算预览，readonly）** / 初始库存 / 当前剩余 / 库存进度条 / 操作（编辑 / 删除）
  - "添加奖品"按钮 → 抽屉表单（奖品名 / 稀有度 select / 封面 / 概率权重 / 初始库存）
- [ ] **AC 5**：**概率权重不强制总和 100**：admin 输入任意 weight 数字（≥ 0）；前端表格右侧"实时归一化%"列 reactive 计算：`prize.weight / sum(allPrizes.filter(stock_current > 0).weight) * 100`，保留 2 位小数显示
- [ ] **AC 6**：归一化%预览仅统计 `stock_current > 0` 的奖品（库存空奖品不参与抽奖，doc/10 §8 业务规则 + doc/11 §7.2 落地一致）；表格底部显示"当前归一化基数：sum=XX，参与奖品数=Y"
- [ ] **AC 7**：admin perm：list `gz:gacha:pool:list` / edit `gz:gacha:pool:edit` 等；菜单插入 menu_id 段 **10100-10199**（CLAUDE.md §6 #6 GZ-GACHA admin 段）
- [ ] **AC 8**：奖品 weight / stock 修改保存 → 后端 UPDATE + 写 ops log（ruoyi 自带 `@Log` 注解）
- [ ] **AC 9**：i18n 全覆盖（`gz-gacha.pool.*`）
- [ ] **AC 10**：单测 `GzGachaMachineServiceImplTest` + `GzGachaPrizeServiceImplTest` 各 happy + 库存为 0 prize 不参与归一化预览（前端逻辑可用 vitest 单测 useNormalizedProbability composable）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/GzGachaMachineController.java`（admin 路径 `/system/gz/gacha/machine`）
  - `controller/GzGachaPrizeController.java`（admin 路径 `/system/gz/gacha/prize`，按 machineId 查列表）
  - `service/IGzGachaMachineService.java` + impl
  - `service/IGzGachaPrizeService.java` + impl
  - `domain/bo` + `domain/vo`
  - DDL 已在 D08/D09 落；menu SQL `V<时间戳>__GZ-ADMIN-102-menu.sql`（menu_id 10100-10120 段）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-gacha/pool/index.vue`（机器列表 + 进入奖品池视图）
  - `views/gz-gacha/pool/components/MachineDrawer.vue`
  - `views/gz-gacha/pool/components/PrizeTable.vue`（奖品池表格 + 归一化预览）
  - `views/gz-gacha/pool/components/PrizeDrawer.vue`
  - `composables/useNormalizedProbability.ts`（reactive 计算归一化%）
  - `api/gz-gacha/machine.ts` + `api/gz-gacha/prize.ts`
  - `lang/zh_CN/gz-gacha.ts` + `en_US/gz-gacha.ts`
- **小程序**：不动
- **测试**：单测 + admin 端走完整流（建机器 / 加 5 个奖品 / 不同 weight / 验证归一化%和为 100）

## 备注

### 强约束

1. **概率权重不强制总和 100**：AC 5 锚定；admin UI 不做总和校验报错；归一化在后端抽奖逻辑（GACHA-103 抽奖实现，本 ticket 不动）+ 前端预览展示
2. **库存空奖品不参与归一化**：AC 6 锚定；与 doc/10 §8 业务规则 + doc/11 §7.2 stock 字段口径一致
3. **稀有度走字典 `gz_gacha_rarity`**（doc/11 §A.6）：N / R / SR / SSR / UR 五档；前端按字典渲染 chip 颜色
4. **menu_id 10100-10199 段**（CLAUDE.md §6 #6 GZ-GACHA admin）
5. **设计冻结期：admin 走 ruoyi 默认**：el-table / el-drawer / el-form 默认组件；不调样式
6. **包名 `org.dromara.gz.gacha.*`**

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 归一化预览前端 reactive 计算 | 用户输入 weight 即时刷新预览；不需要后端实时返回 |
| D2 | 库存为 0 prize 不参与预览归一化 | 与运行时抽奖逻辑一致（GACHA-103）；运营心智一致 |
| D3 | 机器和奖品池同页（tab 切换 or 子视图）| 强相关业务对象；分页跳转打断思路 |
| D4 | 奖品权重独立保存（不批量保存机器+奖品）| 奖品列表 inline 编辑保存粒度小；批量保存易冲突 |
| D5 | weight 字段类型 INT | 整数权重足够（运营理解友好）；doc/11 §7.2 已锁 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | D08/D09 prize schema 字段不全（缺 rarity / stock_current / stock_initial） | §0 自检 `DESC gz_gacha_prize` 字段对齐 doc/11 §7.2；缺则回 D08/D09 修 |
| R2 | weight 修改后运行中抽奖请求拿旧 weight | 抽奖逻辑（GACHA-103）每次查 DB；weight 修改即时生效（V1.1 不加 Redis 缓存） |
| R3 | 归一化%预览精度（浮点）| 保留 2 位小数 + 显示"实时归一化%"明确不是后端最终判定 |
| R4 | 运营误把权重总和理解为必须 100 | UI 文案明确"权重比例制（无需总和 100，系统自动归一化）"+ 表格底部显示当前 sum |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
