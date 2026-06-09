# GZ-BEAN-013 — 拼豆座位类型配额配置（admin 配数量/单价 + 废弃 A1-A10 具体座位）

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M4 §座位类型配额 SeatTypeConfig（V1.2 推倒 A1-A10）
**关联拆解**: doc/02-需求拆解.md §3.6.2 GZ-BEAN-013 座位类型配额配置（admin 配数量/单价 + 废弃具体座位）
**关联 mockup**: 待补 admin-bean-seat-type（缺口，admin 走 ruoyi/Element Plus 默认审美，不取像素；doc/12 §AD-BEAN-TYPE-CONFIG 页面结构参考）
**关联 ADR**: **doc/_adr/0008-seat-type-quota-model.md（必读，座位类型配额模型 — 废弃具体座位 + 数据模型裁定）**
**依赖**: 无（GZ-BEAN-001 门店 + GZ-BEAN-002 座位/时段已交付，本卡在其上加配额配置 + 停用具体座位）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §11 拼豆付费预约全流程（V1.2 重头，座位类型配额模型 — 本卡建配置地基）+ §3「已被 §11 推倒」标注（A1-A10 具体座位 / Redis 座位锁过时）
- **字段表**：doc/11-字段权威表.md **§3.4 `gz_bean_seat_type_config`**（门店 × 座位类型 → 数量 + 单价，完整字段 + UNIQUE）+ **§3.3 `gz_bean_seat`（V1.2 起废弃用于预约，保留表不 DROP）** + **附录 A.14 `gz_bean_seat_type` 字典**（single/double/quad）+ §10.2 字典 seed 口径
- **ADR**：**ADR-0008**（座位类型配额模型，必读 — §1 废弃 gz_bean_seat / §2 新建 config 表 / §3 预约引类型不引 seat_id / §4 改表+子表取舍 / §5 旧数据迁移在 GZ-BEAN-014）
- **UI 参考**（设计冻结期 admin 走 ruoyi 默认）：`N/A（admin 走 ruoyi/Element Plus 默认审美）`；功能项参考 doc/12 §AD-BEAN-TYPE-CONFIG（每门店每类型：数量 + 单价 + 启用开关），不取像素

## What

新建拼豆座位类型配额配置表 `gz_bean_seat_type_config`（门店 × 座位类型 → 数量 + 单价 + 启用），admin 端把座位配置从「画 A1-A10 座位图」改为「配每类型数量 + 单价」；seed 字典 `gz_bean_seat_type`（single/double/quad）；标注废弃 `gz_bean_seat`（A1-A10 具体座位）用于预约——表物理保留不 DROP，停用其预约用途 + admin 座位图入口下线。**本卡只做地基**（config 表 + 字典 + admin 配置页 + 废弃标注），付费列/子表/防超卖/旧数据迁移在 D12 GZ-BEAN-014。

## AC（验收标准）

- [ ] **AC 1**：Flyway 迁移 `V<时间戳 ≥ 202606190600>__GZ-BEAN-013-create-seat-type-config.sql` 建表 `gz_bean_seat_type_config`，字段严格对齐 doc/11 §3.4：
  - `id` BIGINT PK / `store_id` BIGINT（FK gz_bean_store）/ `seat_type` VARCHAR(16)（字典 `gz_bean_seat_type`）/ **`quantity` INT NOT NULL DEFAULT 0（配额上限 = 余量基础）** / `price_cent` BIGINT NOT NULL DEFAULT 0（单价分）/ `enabled` CHAR(1) DEFAULT '1' / ruoyi 审计列（create_by/create_time/update_by/update_time/create_dept）/ `tenant_id` VARCHAR(20) NOT NULL DEFAULT '1001' / `del_flag` CHAR(1) DEFAULT '0'
  - **`UNIQUE(tenant_id, store_id, seat_type)`**（强约束 #3，唯一约束必含 tenant_id）
  - **`quantity` 即余量基础**：是「该 (门店, 类型) 在每个 (日期, 时段) 档的可约名额上限」，供 D13 GZ-BEAN-015 mp 显示余量（`还剩 N = quantity − 该档活跃 booking 数`）+ D12 GZ-BEAN-014 按 booking 计数防超卖。本卡只配置 quantity，不做计数（计数在 BEAN-014）。
- [ ] **AC 2**：字典 seed `gz_bean_seat_type`（doc/11 附录 A.14 + §10.2）——`sys_dict_type` 一行（`gz_bean_seat_type` / 拼豆座位类型）+ `sys_dict_data` 三行：`single`（单人）/ `double`（双人）/ `quad`（四人桌）。字典可扩展（未来加包厢只加字典项 + 一行 config）。seed 进同迁移或独立 `V<时间戳+1>__GZ-BEAN-013-seed-seat-type-dict.sql`。
- [ ] **AC 3**：后端 CRUD（`ruoyi-gz-bean`，包名 `org.dromara.gz.bean.*`）——`GzBeanSeatTypeConfigController` admin 路径 `/gz/bean/seatTypeConfig`（list 按 store_id 筛 / getInfo / add / edit / remove 软删 / 切 enabled）；service `@Transactional`；entity `@TableLogic del_flag` + `tenant_id` 自动填充；Bo 校验 `quantity ≥ 0` / `price_cent ≥ 0`（`@Min(0)`）/ `seat_type` 必填且属字典。
- [ ] **AC 4**：admin 配置页 `views/gz-bean/seat-type-config/index.vue`（plus-ui BizTable + Element Plus 默认）——门店 select（V1.0 仅成都一店，强约束 #13，多店代码留接口）+ 每类型一行：座位类型（字典翻译 single/double/quad）/ 数量 `quantity`（input number）/ 单价（元，前端元 → 分换算存 `price_cent`）/ 启用 switch / 操作（新增类型行 / 编辑 / 删除）。一个门店配几行即可（取代 A1-A10 座位图）。
- [ ] **AC 5**：**废弃 `gz_bean_seat`（A1-A10）用于预约**（ADR-0008 §1）——① admin 原座位图配置入口（AD-BEAN-CONFIG 的座位 A1-A10 段，GZ-BEAN-002 建）下线/隐藏（菜单隐藏或页面移除座位图 tab）；② `gz_bean_seat` 表**物理保留不 DROP**（旧数据 + 迁移期映射需要）；③ 本卡及后续新代码**禁止** INSERT/依赖 `gz_bean_seat` 做预约分配。reports 记录废弃标注 + `gz_bean_seat` 表仍存在（`SHOW TABLES LIKE 'gz_bean_seat'`）。
- [ ] **AC 6**：金额 `price_cent`（分）——前端元 ↔ 分换算在 UI 层，DB 存分；不用 `_fen`。
- [ ] **AC 7**：admin perm 走 ruoyi RBAC `@SaCheckPermission` — list `gz:bean:seatTypeConfig:list` / add `:add` / edit `:edit` / remove `:remove`；菜单 seed 落 **menu_id 6000 GZ-BEAN 段**（seed 前 `SELECT MAX(menu_id) FROM sys_menu WHERE menu_id BETWEEN 6000 AND 6999` 确认不冲突），仅 owner(100) 授权。
- [ ] **AC 8**：i18n 全覆盖（plus-ui `zh_CN/gz-bean.ts` + `en_US/gz-bean.ts`，key `gz-bean.seatTypeConfig.*`）；默认 zh-CN，不混 emoji。
- [ ] **AC 9**：单测 `GzBeanSeatTypeConfigServiceImplTest` happy path（`insertByBo` / `updateByBo` / `removeByIds` 软删 / 同门店同类型重复 insert 触 UNIQUE 冲突各 1，≥ 60% 核心覆盖）。

> 纯 admin + 后端 ticket，**跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2 — Tech 段无 `miniapp/` 路径 + AC 无微信原生能力 → 不进人验列，AI Tier 1A + 1B 全 ✅ 即终态。mp 选类型下单在 D13 GZ-BEAN-015）。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`（包名 `org.dromara.gz.bean.*`）
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V<时间戳 ≥ 202606190600>__GZ-BEAN-013-create-seat-type-config.sql`（建表）+ `V<时间戳+1>__GZ-BEAN-013-seed-seat-type-dict-menu.sql`（字典 + menu 6000 段 + perm seed）
  - `controller/GzBeanSeatTypeConfigController.java`（admin `/gz/bean/seatTypeConfig`，每端点 `@SaCheckPermission`）
  - `service/IGzBeanSeatTypeConfigService.java` + `impl`（list/queryById/insertByBo/updateByBo/removeByIds/toggleEnabled，`@Transactional`）
  - `domain/GzBeanSeatTypeConfig.java`（entity，`@TableLogic del_flag`）+ `bo/GzBeanSeatTypeConfigBo.java`（`@Min(0)` quantity/price_cent，seat_type 必填）+ `vo/GzBeanSeatTypeConfigVo.java`（含 seatType 字典翻译 + price 元）
  - `mapper/GzBeanSeatTypeConfigMapper.java`
  - **模块 pom 无新增依赖**（用 ruoyi 已有 mybatis-plus / sa-token）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-bean/seat-type-config/index.vue`（门店 select + 类型行配置表）
  - `api/gz-bean/seatTypeConfig.ts`
  - `lang/zh_CN/gz-bean.ts` + `en_US/gz-bean.ts`
  - 原 A1-A10 座位图配置入口（GZ-BEAN-002 建）下线/隐藏
- **小程序**：不动（mp 选类型下单在 D13 GZ-BEAN-015）
- **测试**：单测（AC 9）+ kevin-qa Playwright E2E（登录 owner → 选成都门店 → 配 single 数量5/单价X + double 数量3/单价Y → 切 enabled → 删一行 → 重复类型触 UNIQUE 拒）

## 备注

### 强约束（每条复核）

1. **必读 ADR-0008**（座位类型配额模型）：本卡是 ADR-0008 的 D11 落地（config 表 + admin 配置页 + 废弃 gz_bean_seat）。防超卖并发口径在 ADR-0007 §2（D12 GZ-BEAN-014 落地），本卡**只定/建数据模型**，不做防超卖计数。
2. **`gz_bean_seat` 保留不 DROP**（ADR-0008 §1 + 强约束 #5 destructive 红线）——物理保留作 V1.0 历史数据 + 迁移期 seat→seat_type 映射；逻辑停用于预约；admin 座位图入口下线。
3. **字段严格对齐 doc/11 §3.4**：`seat_type` VARCHAR(16) / `quantity` INT / `price_cent` BIGINT / `UNIQUE(tenant_id, store_id, seat_type)`。偏离 doc/11 → 回改 doc/11 源头，不在卡内私自加字段（§9.5 改源头）。
4. **字典走 sys_dict**（`gz_bean_seat_type`），**不写死枚举常量**；seat_type 值用字典 value（single/double/quad），UI 用字典 label 翻译。
5. **金额 `price_cent`（分）**，不用 `_fen`；前端元 ↔ 分换算在 UI 层。
6. **`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`**；INSERT 不显式赋 tenant_id（自动填充）；**UNIQUE 必含 tenant_id**（`(tenant_id, store_id, seat_type)`）。
7. **`del_flag` 仅 2 值（0/2）** 对齐 ruoyi `@TableLogic`，软删不硬删。
8. **包名 `org.dromara.gz.bean.{controller,service,mapper,domain,dto}`**（CLAUDE.md §6 #4）。
9. **menu_id 6000 段**（GZ-BEAN，CLAUDE.md §6）：复用，不新开段；seed 前 `SELECT MAX(menu_id) ... BETWEEN 6000 AND 6999` 确认。
10. **迁移文件命名** `V<yyyyMMddHHmm>__GZ-BEAN-013-<desc>.sql`，时间戳 **≥ 202606190600**（> 当前最大 V202606190200）；已应用不可改。
11. **不动 ruoyi 自带模块源码**（CLAUDE.md §6 #1）。

### 关键技术决策（承接 ADR-0008）

| # | 决策 | 理由 |
|---|---|---|
| D1 | 改表 + 新建 config 表，非全新一套 booking 表 | ADR-0008 §4：兼容 V1.0 数据 + 改动面可控 + 单一 booking 真源 |
| D2 | `gz_bean_seat` 保留不 DROP | ADR-0008 §1 + 强约束 #5：留历史 + 迁移期映射；占一张停用表可接受 |
| D3 | 座位类型字典化（`gz_bean_seat_type`） | ADR-0008 §5：可扩展（未来加包厢/VIP 桌只加字典 + 一行 config），不写死枚举 |
| D4 | 本卡只建地基，付费列/防超卖计数/余量查询/迁移留 GZ-BEAN-014 | 切 ticket 边界：D11 地基（config+字典+admin）/ D12 业务（付费状态机+按 booking 计数防超卖+余量接口+迁移），互不阻塞 |
| D5 | **单笔单时段，无子表**：`quantity` 配额供「一笔预约 = 一行 booking（1 类型 1 时段）」按 booking 计数 | ADR-0007/0008：不引 `gz_bean_booking_unit` 子表；多类型/多时段 = 多次预约（多行 booking），每笔独立占一个 (类型,日期,时段) 名额 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 上游表未落地（gz_bean_store / gz_bean_seat 由 GZ-BEAN-001/002 建） | §0 自检 `grep -rl 'gz_bean_store\|gz_bean_seat' .../db/migration/` + `SHOW TABLES LIKE 'gz_bean_%'`；缺 → STOP 报 Kevin |
| R2 | 误删 / DROP `gz_bean_seat` | ADR-0008 §1 明令保留不删；迁移文件不得含 `DROP TABLE gz_bean_seat`（QA 打回项） |
| R3 | 字段名偏离 doc/11 §3.4 | §0 自检对照 doc/11 §3.4 逐字段；偏离回改 doc/11 不在卡内 patch |
| R4 | menu_id 6000 段冲突（GZ-BEAN-001/002 已占部分） | seed 前 `SELECT MAX(menu_id) ... BETWEEN 6000 AND 6999`，取下一空位 |
| R5 | admin 座位图入口下线后旧菜单残留 | 同迁移 `UPDATE sys_menu SET visible='0'`（或移除）原 A1-A10 座位配置菜单，reports 记录 |
| R6 | price_cent 误存元 / 误用 _fen | UI 层元→分换算 + 后端 Bo `@Min(0)`；命名严格 `price_cent` |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D11/GZ-BEAN-013 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
