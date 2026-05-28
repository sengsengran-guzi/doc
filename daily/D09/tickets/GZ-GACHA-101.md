# GZ-GACHA-101 — 扭蛋机 + 奖品池数据模型

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §关键字段（GachaMachine / GachaPrize）
**关联拆解**: doc/02-需求拆解.md §3.3 第 744 行
**关联 mockup**: design/mockup/admin-gacha-pool.html ⚠️ 设计冻结期 admin 走 ruoyi 默认 + plus-ui BizTable，不参考 mockup 视觉
**关联 ADR**: —
**依赖**: GZ-SYS-001 ✅（ruoyi-modules/ruoyi-gz-gacha 空模块已就位）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§7 扭蛋抽奖流**（如不全 → STOP，回 @product 巡检后再实施；可临时参考 §3 拼豆并发结构作类比）
- **字段表**：doc/11-字段权威表.md
  - **§7.1 `gz_gacha_machine`**（机器主表 — 完整 DDL 来源）
  - **§7.2 `gz_gacha_prize`**（奖品池 — 完整 DDL 来源 + 库存字段）
  - §1 全局公共字段（tenant_id / create_by / del_flag 等）
- **UI 参考**（设计冻结期）：admin 走 ruoyi 默认 + plus-ui BizTable，**不**逐像素还原 admin-gacha-pool.html
- **CLAUDE.md §6 #6**：menu_id 段 GACHA 10000-10099

## What

落地两张表 + entity + mapper + service；admin 端提供机器 CRUD + 奖品池 CRUD（嵌套在机器详情下），让甲方运营能配机器、增删奖品、调权重、调库存。

## AC（验收标准）

- [ ] **AC 1**：DDL 文件 `V202606171000__GZ-GACHA-101-create-gz_gacha_machine-and-prize.sql` 落两张表：
  - `gz_gacha_machine`（id / name / cover_url / single_price 分 / status enum(`on_shelf`/`off_shelf`) / sort_order int / store_id 可空 / + 全局公共字段）
  - `gz_gacha_prize`（id / machine_id / name / cover_url / rarity enum(`SSR`/`SR`/`R`/`N`) / weight int / initial_stock int / current_stock int / public_value 分 可空 / + 全局公共字段）
  - UNIQUE `uk_tenant_machine_prize_name (tenant_id, machine_id, name)`（同机器内奖品名唯一）
  - 索引 `idx_machine_id (machine_id)` `idx_machine_stock (machine_id, current_stock)`（GACHA-104 SELECT FOR UPDATE 走此索引）
- [ ] **AC 2**：Entity 严格按 doc/11 §7.1/§7.2：
  - `GzGachaMachine.java`（继承 `TenantEntity`）
  - `GzGachaPrize.java`（继承 `TenantEntity`）
  - 对应 VO / BO
- [ ] **AC 3**：admin 端 Controller `GET/POST/PUT/DELETE /system/gz/gacha/machine`（perm `gz:gacha:machine:*`）+ `GET/POST/PUT/DELETE /system/gz/gacha/prize`（perm `gz:gacha:prize:*`）
- [ ] **AC 4**：admin 端 `views/gz-gacha/machine/index.vue` + `views/gz-gacha/prize/index.vue`（plus-ui BizTable）：
  - 机器列表：名称 / 封面缩略图 / 单抽价格 / 状态 / 操作（编辑 / 上下架 / 管理奖品池）
  - 点「管理奖品池」跳奖品池页（带 machine_id query）
  - 奖品池页：奖品列表 + 新增 / 编辑 / 删除（初始库存 + 当前剩余 + 权重）
- [ ] **AC 5**：sys_menu 插入 GACHA 一级菜单（10000）+ "扭蛋机管理"（10001）+ "奖品池管理"（10002）`V202606171001__GZ-GACHA-101-menu.sql`
- [ ] **AC 6**：单测覆盖：
  - happy path（INSERT 机器 + 嵌套 INSERT 奖品）
  - 同机器内奖品重名 → DuplicateKeyException
  - current_stock < 0 校验（service 层拒绝）
- [ ] **AC 7**：所有写操作加 `@Log`

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-gacha/`
  - `controller/GzGachaMachineController.java` + `GzGachaPrizeController.java`
  - `domain/GzGachaMachine.java` + `GzGachaPrize.java` + VO / BO
  - `mapper/GzGachaMachineMapper.java` + `GzGachaPrizeMapper.java`
  - `service/IGzGachaMachineService.java` + impl + 同样的 prize service
  - DDL × 2 文件（表 + menu）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-gacha/machine/index.vue` + `views/gz-gacha/prize/index.vue`
  - `api/gz-gacha/machine.ts` + `prize.ts`
  - `lang/zh_CN/gz-gacha.ts` + `en_US/gz-gacha.ts`
- **小程序**：无（mp 列表 / 详情在 GACHA-102 / 103）
- **测试**：mvn 单测 + admin 浏览器 CRUD 实操

## 备注

### 强约束

1. **DDL 字段必须 1:1 对齐 doc/11 §7.1 / §7.2**（任何不一致 → STOP 改源头 doc，CLAUDE.md §9.5 复盘优先级 #1）
2. **稀有度仅 SSR/SR/R/N 四档**（doc/02 §3.3 行 748）— enum DDL 严格四档，不预留第五档
3. **UNIQUE 必含 tenant_id**（CLAUDE.md §6 #3）
4. **INSERT 不显式赋 tenant_id**（CLAUDE.md §6 #3 InjectionMetaObjectHandler 自动）
5. **库存扣减必走 `SELECT FOR UPDATE`**（本 ticket 落 DDL + Mapper 方法签名；实际锁定逻辑在 GACHA-104）
6. **price / public_value 用 INT 存分**（不用 DECIMAL；统一与 PAY-101 一致）
7. **menu_id**：10000-10002（CLAUDE.md §6 #6 GACHA 段）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 机器 + 奖品两表分离（不内嵌 JSON） | 奖品需独立 SELECT FOR UPDATE / 单条 UPDATE 库存，JSON 字段不支持行锁 |
| D2 | rarity 用 enum 而非 dict | 仅 4 档固定，enum 性能 + 强约束优于 dict；dict 用于"可扩展"场景 |
| D3 | weight 用 INT（不归一化存储）| 归一化在 GACHA-103 / 104 运行时按当前在池有库存的奖品重算（doc/02 §3.3 行 778）|
| D4 | initial_stock + current_stock 两字段 | 概率公示要展示初始总量（"100 中 1"），历史库存数据不丢失 |
| D5 | machine.store_id 可空 | V1.1 仅成都店；多门店预留接口但 UI 隐藏（合同 §2.3） |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | doc/11 §7.1/§7.2 字段表是否已写 | 实施前 §0 自检；不全 → STOP 让 @product 写完 |
| R2 | 甲方运营误把 current_stock 直接改成负数 | service 层校验 + UI input min=0 + admin DB 层 CHECK 约束 |
| R3 | weight=0 的奖品仍在池里参与归一化 | service 层校验 weight ≥ 1（0 视为下架，应改 current_stock=0 而非 weight=0） |

### ADR 候选

- 无

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
