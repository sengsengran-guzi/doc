# GZ-GACHA-101 — 扭蛋机 + 奖品池数据模型 + admin CRUD

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §关键字段（GachaMachine / GachaPrize）+ §4.1 扭蛋规则（概率公示 / 不保底 / 抽完即下架）
**关联拆解**: doc/02-需求拆解.md §3.3（GZ-GACHA-101）
**关联 mockup**: design/mockup/admin-gacha-pool.html ⚠️ admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统）+ plus-ui BizTable，不参考 mockup 视觉
**关联 ADR**: —
**依赖**: GZ-SYS-001 ✅（`ruoyi-modules/ruoyi-gz-gacha` 空脚手架已就位，仅 `GachaHelloController`）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。
> admin ticket：UI 在设计冻结期走 ruoyi 默认（不卡逐像素）。

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（**不是 §7 = 预购**）
  - §8.N1/N2（机器列表 / 单机详情 + 奖品池）、§8.N3（概率公示口径，本卡只落 `weight` 字段供 GACHA-103 归一化）、§8.N6（库存扣减 `SELECT FOR UPDATE`，本卡落 DDL + 索引供 GACHA-104 锁行）
  - **§8.E1**（库存抢空整事务回滚，本卡只保证 `stock_remain` 不出现负值的约束基础）
- **字段表**：doc/11-字段权威表.md（**DDL 完整字段来源，1:1 对齐**）
  - **§7.1 `gz_gacha_machine`**（机器主表 — 12 字段全集）
  - **§7.2 `gz_gacha_prize`**（奖品池 — 11 字段全集 + 库存 / 乐观锁 / 索引）
  - §1 全局公共字段（`id` / `tenant_id` / `create_by` / `create_time` / `update_by` / `update_time` / `del_flag` 等）
  - 附录 A.10 稀有度字典 `gz_gacha_rarity`（SSR/SR/R/N）
  - §10.3 menu_id 段表（GACHA 10000-10099）
- **CLAUDE.md §6 #2/#3/#4/#5**：租户 / UNIQUE 含 tenant_id / 包名 / DDL 命名

## What

落地 `gz_gacha_machine` + `gz_gacha_prize` 两张表 + entity / mapper / service / VO / BO，并在 admin 端提供机器 CRUD + 奖品池 CRUD（奖品池嵌套在机器详情下），让甲方运营能配机器、增删奖品、调概率权重、调库存。

## AC（验收标准）

- [ ] **AC 1**：DDL 文件 `V202606171000__GZ-GACHA-101-create-gz_gacha_machine-and-prize.sql` 落两张表，字段 **1:1 对齐 doc/11 §7.1 / §7.2**：
  - **`gz_gacha_machine`**（§7.1）：`machine_no` VARCHAR(32) / `name` VARCHAR(128) / `cover_image_id` BIGINT UNSIGNED NULL（FK→`gz_file_object.id`）/ `single_price_cent` BIGINT / `ten_pack_price_cent` BIGINT NULL / `ip_tag` VARCHAR(64) NULL / `status` VARCHAR(16) DEFAULT `'off_shelf'` / `online_time` DATETIME(3) NULL / `offline_time` DATETIME(3) NULL / `sales_count` BIGINT UNSIGNED DEFAULT 0 / `version` INT DEFAULT 0 + §1 全局公共字段
    - UNIQUE `uk_gacha_machine_no (tenant_id, machine_no)`
    - IDX `idx_gacha_machine_status (tenant_id, status)` / `idx_gacha_machine_ip (tenant_id, ip_tag)`
  - **`gz_gacha_prize`**（§7.2）：`machine_id` BIGINT UNSIGNED（FK→`gz_gacha_machine.id`）/ `prize_no` VARCHAR(32) / `name` VARCHAR(128) / `image_id` BIGINT UNSIGNED NULL（FK→`gz_file_object.id`）/ `rarity` VARCHAR(8) / `weight` INT / `stock_initial` INT / `stock_remain` INT / `reference_value_cent` BIGINT NULL / `enabled` TINYINT DEFAULT 1 / `version` INT DEFAULT 0 + §1 全局公共字段
    - UNIQUE `uk_gacha_prize_no (tenant_id, prize_no)`
    - IDX `idx_gacha_prize_pool (tenant_id, machine_id, enabled, stock_remain)`（doc/11 §7.2 索引 — GACHA-104 `SELECT FOR UPDATE` 查在池有库存奖品走此索引）
- [ ] **AC 2**：字段命名严格用 canonical 写法（错一个 → STOP 改源头 doc）：
  - 金额 `_cent`（**禁** `_fen` / `single_price` / `public_value`）
  - 库存 `stock_initial` / `stock_remain`（**禁** `initial_stock` / `current_stock` / `init` / `left`）
  - 图片 `cover_image_id` / `image_id` FK→`gz_file_object`（**禁** `cover_url` 裸 url 列）
  - `status` 枚举含 `auto_off`（**禁** `off_shelf` 写成 `archived` / 漏 `auto_off`）
  - `del_flag` 仅 2 值（0 正常 / 2 删除），对齐 ruoyi `@TableLogic`（**禁** 3 值）
- [ ] **AC 3**：Entity 严格按 doc/11 §7.1 / §7.2：
  - `GzGachaMachine.java` + `GzGachaPrize.java`（均继承 `TenantEntity`，`tenant_id` 不手动赋值走 `InjectionMetaObjectHandler` 自动填充）
  - 对应 `GzGachaMachineVo / Bo` + `GzGachaPrizeVo / Bo`（不写 `any`，BO 加 `@NotNull` / `@Min` 校验）
- [ ] **AC 4**：admin 端 Controller（perm 走 `@SaCheckPermission`，**不用** `@SaCheckRole`；同租户 1001）：
  - `GzGachaMachineController`：`GET /system/gz/gacha/machine/list`（分页）/ `GET .../{id}` / `POST` / `PUT` / `DELETE .../{ids}`，perm `gz:gacha:machine:{list,query,add,edit,remove}`
  - `GzGachaPrizeController`：同上 `/system/gz/gacha/prize/...`，perm `gz:gacha:prize:{list,query,add,edit,remove}`；`list` 必须支持按 `machineId` 过滤（查某机器奖品池）
- [ ] **AC 5**：编号生成器在 service 层注册：机器 `machine_no = GM-yyyyMMdd-6位序号`、奖品 `prize_no = PRZ-yyyyMMdd-6位序号`（前缀对齐 doc/11 §附录单号前缀清单 + D07 已发 `TEST-20260604-` 单口径，全局唯一走 DB UNIQUE 兜底）
- [ ] **AC 6**：admin 端 `views/gz-gacha/machine/index.vue` + `views/gz-gacha/prize/index.vue`（plus-ui BizTable）：
  - 机器列表：机器编号 / 名称 / 封面缩略图 / 单抽价（元）/ 十连价 / IP 标签 / 状态 / 操作（编辑 / 上下架 / 管理奖品池）
  - 点「管理奖品池」跳奖品池页（带 `machineId` query）
  - 奖品池页：奖品列表（编号 / 名称 / 封面 / 稀有度 / 权重 / 初始库存 / 剩余库存 / 是否参与抽奖）+ 新增 / 编辑 / 删除
  - 单抽价 / 十连价 / 公示价 input 以"元"录入，提交转"分"存（前端 ×100 取整，不传浮点分）
- [ ] **AC 7**：sys_menu seed `V202606171001__GZ-GACHA-101-menu.sql` 插入（menu_id 严格落 GACHA 10000-10099 段，doc/11 §10.3）：
  - `10000` 一级目录「扭蛋机」/ `10001` 菜单「扭蛋机管理」（含 5 个按钮权限 `gz:gacha:machine:*`）/ `10002` 菜单「奖品池管理」（含 5 个按钮权限 `gz:gacha:prize:*`）
  - 仅授权 `gz_owner`（100）角色（甲方运营），对齐 ADR-0004 同租户 RBAC
- [ ] **AC 8**：单测覆盖（`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am`）：
  - happy path：INSERT 机器 + 同机器嵌套 INSERT 多个奖品，查询回读字段一致
  - 同租户内 `machine_no` / `prize_no` 重复 → `DuplicateKeyException`
  - service 层校验：`stock_initial < 0` / `stock_remain < 0` / `weight < 0` 拒绝（抛业务异常，不静默吞）
  - 编号生成：同日多次生成序号递增不重复

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`（包名 `org.dromara.gz.gacha.{controller,service,mapper,domain,dto}`）
  - `controller/`：`GzGachaMachineController.java` + `GzGachaPrizeController.java`
  - `domain/`：`GzGachaMachine.java` + `GzGachaPrize.java` + `domain/vo/` + `domain/bo/`
  - `mapper/`：`GzGachaMachineMapper.java` + `GzGachaPrizeMapper.java`（GACHA-104 用的 `SELECT FOR UPDATE` 方法签名本卡**可预留**，实现留 GACHA-104）
  - `service/`：`IGzGachaMachineService` + impl / `IGzGachaPrizeService` + impl（含编号生成器）
  - DDL × 2 文件（建表 + menu seed），放 `ruoyi-admin/src/main/resources/db/migration/`
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-gacha/machine/index.vue` + `views/gz-gacha/prize/index.vue`
  - `api/gz-gacha/machine.ts` + `api/gz-gacha/prize.ts`（TS 类型对齐 VO，**不写 `any`**）
  - `lang/zh_CN/gz-gacha.ts` + `lang/en_US/gz-gacha.ts`（admin 可见字符串走 `t()`，**不混 emoji**）
- **小程序**：无（mp 列表 / 详情在 GACHA-102 / 103，本卡纯 admin + 后端 → **跳过 Tier 2 可达 AC**，CLAUDE.md §8.2）
- **测试**：mvn 单测 + admin 浏览器 CRUD 实操（kevin-qa Playwright E2E：登录 → 机器 CRUD → 进奖品池 → 奖品 CRUD → 权限 403 校验）

## 备注

### 强约束

1. **DDL 字段必须 1:1 对齐 doc/11 §7.1 / §7.2**（任何不一致 → STOP 改源头 doc，CLAUDE.md §9.5 复盘优先级 #1，不在 ticket patch）
2. **稀有度仅 SSR / SR / R / N 四档**（doc/11 §7.2 + 附录 A.10）— `rarity` VARCHAR(8) 配字典 `gz_gacha_rarity` 校验，**仅展示用，不影响抽奖事务**，不预留第五档
3. **UNIQUE 必含 tenant_id**（CLAUDE.md §6 #3）；**INSERT 不显式赋 tenant_id**（走 `InjectionMetaObjectHandler` 自动）
4. **金额一律 `_cent`（分），用 BIGINT**（不用 DECIMAL / `_fen`）；admin input 以元录入、提交 ×100 转分
5. **库存扣减走 `SELECT FOR UPDATE`** 是 GACHA-104 的事，本卡只落 DDL + `idx_gacha_prize_pool` 索引让 104 锁行高效；本卡 service 校验仅拦"配置态负库存"，不做并发扣减
6. **menu_id**：10000（目录）/ 10001（机器）/ 10002（奖品池）— 严格落 GACHA 10000-10099 段（doc/11 §10.3）
7. **权限走 ADR-0004 底座**：admin / mp 管理动作统一 `@SaCheckPermission(perm key)` + admin 授权 + 同租户 1001，**不另造平行 RBAC**

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 机器 + 奖品两表分离（不内嵌 JSON） | 奖品需独立 `SELECT FOR UPDATE` / 单条 UPDATE 库存（GACHA-104），JSON 字段不支持行锁 |
| D2 | `rarity` 用 VARCHAR(8) + 字典校验（不用 DB enum） | 对齐 ruoyi 字典体系（`gz_gacha_rarity`），便于 i18n / UI chip 渲染；仅 4 档固定但与全库字典口径一致 |
| D3 | `weight` 存原始整数（不归一化存储） | 归一化在 GACHA-103 / 104 运行时按"当前在池（enabled=1 且 stock_remain>0）"奖品重算（doc/11 §7.2 计算口径），存储不冗余 |
| D4 | `stock_initial` + `stock_remain` 两字段 | 概率公示要展示初始总量（"100 中 1"），扣减只动 `stock_remain`，历史不丢 |
| D5 | 机器 status 三态（含 `auto_off`） | `on_shelf` 运营手动上架 / `off_shelf` 手动下架 / `auto_off` 库存抢空或到 `offline_time` 系统自动下架（GACHA-104 / cron 写）；本卡建枚举，自动转移逻辑留下游 |
| D6 | `enabled`（奖品级）独立于机器 status | 运营可临时下掉单个奖品（`enabled=0`）不参与抽奖，无需删库；与机器上下架解耦 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | doc/11 §7.1 / §7.2 字段表已就位但本域表尚未建 | **§0 自检 grep migration 目录确认 `gz_gacha_machine` / `gz_gacha_prize` 实际不存在（本卡新建）、`gz_file_object` 实际存在（FK 依赖）**；不假设上游已建 |
| R2 | 甲方运营误把 `stock_remain` 改成负数 | service 层校验 `stock_remain ≥ 0` + UI input `min=0`；并发扣减保护是 GACHA-104 的 SELECT FOR UPDATE，本卡不兜并发 |
| R3 | `weight=0` 的奖品仍在池参与归一化 | doc/11 §7.2 计算口径已限定 `weight` 仅对 `enabled=1 且 stock_remain>0` 求和；运营下架奖品应置 `enabled=0` 而非 `weight=0`；UI 文案提示 |
| R4 | `ten_pack_price_cent` 可空被前端当 0 渲染十连入口 | 可空表示"不支持十连"，admin 列表 / 后续 mp 详情判 null 隐藏十连，不显示 ¥0 |

### 外部前置风险

- 无（本卡纯数据模型 + admin CRUD，不依赖微信支付 / 真实商户号；支付链路是 GACHA-104 的事，本卡完成不阻塞）

### ADR 候选

- 无

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D09/GZ-GACHA-101 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
