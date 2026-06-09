# GZ-GACHA-101 完工报告 — 扭蛋机 + 奖品池数据模型 + admin CRUD

> 端：后端 + admin（无 mp）｜ 复杂度 M ｜ 阻塞 D09 后续 6 个 ticket（102/103/104/105/106/107）
> 完工：Tier 1A 全 ✅（编译 / 17 单测 / DDL 字段 1:1 校验 / 前端 vue-tsc 零错）

---

## §0 自检结果

| 检查项 | 结果 | 说明 |
|---|---|---|
| git clean | N/A | git 在本 agent sandbox 不可用（仓库 .git 在更外层，主线程已做 orchestration §0 + 统一管 commit；本卡不 commit） |
| 上游依赖 merge | ✅ | GZ-SYS-001 空脚手架就位（仅 `GachaHelloController`），本卡起填血肉 |
| `gz_gacha_*` 表不存在（本卡新建） | ✅ | `grep migration` 确认 `gz_gacha_machine` / `gz_gacha_prize` 均不存在 |
| `gz_file_object` 存在（FK 依赖） | ✅ | `V202605281100__GZ-SYS-005-create-gz_file_object.sql` 已落 |
| 最大 migration < 本卡时间戳 | ✅ | 当前最大 `V202606061500`；本卡 `V202606171000`（建表）+ `V202606171001`（menu seed），时间戳更大 |
| 编译通过 | ✅ | `mvn compile -pl ruoyi-gz-gacha -am` BUILD SUCCESS |
| ADR 已读 | 无相关 | 任务卡「关联 ADR: —」；权限走 ADR-0004 同租户 RBAC 底座（仅授 owner 100） |
| 权威蓝图引用完整 | ✅ | doc/10 §8（扭蛋流，非 §7 预购）+ doc/11 §7.1/§7.2 + 附录 A.10 + §10.3，均已 Read 并 1:1 落地 |

**权威蓝图关键约束摘录**（落地依据）：
- doc/11 §7.1 `gz_gacha_machine` 12 字段全集 → DDL 1:1（machine_no / cover_image_id / single_price_cent / ten_pack_price_cent(NULL) / ip_tag / status(默认 off_shelf) / online_time / offline_time / sales_count / version）
- doc/11 §7.2 `gz_gacha_prize` 11 字段全集 → DDL 1:1（machine_id / prize_no / image_id / rarity / weight / stock_initial / stock_remain / reference_value_cent(NULL) / enabled(默认1) / version）+ 索引 `idx_gacha_prize_pool (tenant_id, machine_id, enabled, stock_remain)` 供 GACHA-104 SELECT FOR UPDATE
- 附录 A.10：稀有度 SSR/SR/R/N 四档，字典 `gz_gacha_rarity`，仅展示不影响事务
- §10.3：GACHA menu 段 10000-10099（10000 目录 / 10001 机器 / 10002 奖品池）

---

## 实现摘要

### 改动文件（relative path）

**DDL（2 个，放 ruoyi-admin/.../db/migration/）**
- `V202606171000__GZ-GACHA-101-create-gz_gacha_machine-and-prize.sql` — 建 2 表 + `gz_gacha_rarity` 字典（dict_id/code 9201-9204，tenant_id '000000'，对齐 BEAN-008 系统字典模式）
- `V202606171001__GZ-GACHA-101-menu.sql` — 13 menu 行（10000 目录 + 10001 机器页 + 10010-10014 按钮 + 10002 奖品池页 + 10020-10024 按钮）+ owner(100) 全授权

**后端（ruoyi-modules/ruoyi-gz-gacha/src/main/java/org/dromara/gz/gacha/）**
- `domain/entity/`：`GzGachaMachine.java` / `GzGachaPrize.java`（继承 TenantEntity，@TableLogic / @Version）
- `domain/bo/`：`GzGachaMachineBo` / `GzGachaMachineQueryBo` / `GzGachaPrizeBo` / `GzGachaPrizeQueryBo`（@NotNull/@Min/@NotBlank 校验，AddGroup/EditGroup）
- `domain/vo/`：`GzGachaMachineVo` / `GzGachaPrizeVo`（id/imageId/coverImageId/machineId 全 @JsonSerialize ToStringSerializer → string）
- `enums/`：`GachaMachineStatusEnum`（on_shelf/off_shelf/auto_off + isManualTarget）/ `GachaRarityEnum`（SSR/SR/R/N + isValid）
- `exception/GzGachaErrorCode.java`（8001-8008 段）
- `mapper/`：`GzGachaMachineMapper`（increaseSalesCount / autoOffExpiredMachines 预置给 104/cron）/ `GzGachaPrizeMapper`（**GACHA-104 预留** `selectInPoolForUpdate` SELECT FOR UPDATE + `deductStock` 乐观锁，仅签名，本卡不调用）
- `service/` + `service/impl/`：`IGzGachaMachineService` + impl / `IGzGachaPrizeService` + impl（含 machine_no/prize_no 编号生成器、稀有度/库存/权重校验、机器删除守卫）

**后端测试（src/test/）**
- `GzGachaMachineServiceImplTest.java`（7 例）/ `GzGachaPrizeServiceImplTest.java`（10 例）
- `pom.xml` 加 `spring-boot-starter-test`（test scope，与 gz-ord 同款）

**Admin 前端（plus-ui/src/）**
- `api/gz-gacha/machine.ts` / `api/gz-gacha/prize.ts`（VO/Form/Query 类型镜像后端，全 string id，不写 any）
- `views/gz-gacha/machine/index.vue`（列表 + 新建/编辑弹窗 + 上下架 + 「管理奖品池」跳转带 machineId query）
- `views/gz-gacha/prize/index.vue`（从 query 读 machineId + 列表 + 新建/编辑 + 稀有度 select + 元↔分 + 返回机器列表）
- `lang/zh_CN.ts` / `lang/en_US.ts`（新增 `gzGachaMachine` / `gzGachaPrize` 顶级 key —— plus-ui lang 是单文件结构非模块化，故并入现有文件，对齐 gzOrdProduct 模式）

### 关键设计落地

- **金额** 全 `_cent`（BIGINT）；admin input 以元录入、提交 `Math.round(yuan*100)` 转分（不传浮点分）
- **库存** `stock_initial`/`stock_remain`；新增 `stock_remain` 空 → 默认 = `stock_initial`（决策 D4）
- **稀有度** VARCHAR(8) + service 层 `GachaRarityEnum.isValid` 校验 + 字典 `gz_gacha_rarity`（决策 D2）
- **机器删除守卫**：仍有奖品 → `MACHINE_HAS_PRIZE` 拒删（避免奖品成孤儿）
- **status** 三态含 `auto_off`，admin changeStatus 仅可切 on_shelf/off_shelf（决策 D5，auto_off 留 104/cron）
- **GACHA-104 锁行预留**：`GzGachaPrizeMapper.selectInPoolForUpdate`（FOR UPDATE）+ `deductStock`（乐观锁 WHERE version=? AND stock_remain>0）签名已落，实现/调用留 104

---

## AI 自测（Tier 1A）

### 1. 编译（mvn compile）

```
$ mvn -o compile -pl ruoyi-modules/ruoyi-gz-gacha -am
（-q 静默成功；无 ERROR 输出，BUILD SUCCESS）
```

### 2. 单测（mvn test -DskipTests=false，17 例全过）

```
[INFO] Running org.dromara.gz.gacha.service.impl.GzGachaPrizeServiceImplTest
21:32:54 INFO [gz-gacha-prize] INSERT id=10 prizeNo=PRZ-20260603-000001 ... rarity=SSR weight=5 stock=100/100
21:32:54 INFO [gz-gacha-prize] INSERT id=null prizeNo=PRZ-20260603-000008 ... (序号递增校验)
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0 -- in GzGachaPrizeServiceImplTest
[INFO] Running org.dromara.gz.gacha.service.impl.GzGachaMachineServiceImplTest
21:32:54 INFO [gz-gacha-machine] CHANGE-STATUS id=1 off_shelf → on_shelf
21:32:54 INFO [gz-gacha-machine] INSERT id=7 machineNo=GM-20260603-000001 ... status=off_shelf
21:32:54 INFO [gz-gacha-machine] LOGIC-DELETE ids=[1]
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0 -- in GzGachaMachineServiceImplTest
[INFO] Tests run: 17, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

**覆盖（AC 8）**：稀有度非四档拒绝（INVALID_RARITY）/ weight<0、stock<0 拒绝（NEGATIVE_STOCK_OR_WEIGHT）/ remain>initial 拒绝（REMAIN_EXCEEDS_INITIAL）/ 归属机器不存在拒绝 / 新增 stockRemain 空默认=stockInitial / prize_no、machine_no 同日序号递增不重复 / changeStatus 拒绝 auto_off / 机器仍有奖品拒删（MACHINE_HAS_PRIZE）/ 新增 status 固定 off_shelf。
（gz-common 同 -am 链路 98 例同时全过，无回归。）

### 3. mvn install（jar 重装，供 restart）

```
$ mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-gacha
[INFO] Installing .../ruoyi-gz-gacha-5.6.1.jar to ~/.m2/.../ruoyi-gz-gacha-5.6.1.jar
[INFO] BUILD SUCCESS
```

### 4. DDL 字段 1:1 校验（机械 grep doc/11 canonical 名）

```
--- machine 字段（全 12 命中 doc/11 §7.1）---
machine_no / name / cover_image_id / single_price_cent / ten_pack_price_cent /
ip_tag / status / online_time / offline_time / sales_count / version  ✅
--- prize 字段（全 11 命中 doc/11 §7.2）---
machine_id / prize_no / name / image_id / rarity / weight /
stock_initial / stock_remain / reference_value_cent / enabled / version  ✅
--- 禁用 token（实际字段名 ZERO，仅注释文档化 bans）---
ZERO forbidden field names ✅（_fen/initial_stock/current_stock/cover_url/archived/single_price/public_value）
--- del_flag 2 值 ✅ / UNIQUE 含 tenant_id ✅（uk_gacha_machine_no / uk_gacha_prize_no）
--- idx_gacha_prize_pool (tenant_id, machine_id, enabled, stock_remain) ✅（GACHA-104 锁行索引）
```

### 5. 前端 vue-tsc 类型检查（新文件零错）

```
$ node_modules/.bin/vue-tsc --noEmit -p tsconfig.json
（全工程 72 个 pre-existing 错误均在 ruoyi 脚手架/vendor 组件：DictTag/FileUpload/Process/layout/store/oper-log 等）
gz-gacha/{machine,prize} + api/gz-gacha + lang/{zh_CN,en_US}：NONE in my files ✅
```

### 6. menu / perms 一致性校验

```
--- 13 menu 行全在 10000-10024（∈ 10000-10099 段）✅
--- 13 行全授权 owner role_id=100 ✅
--- 10 个 perms 串 menu seed ↔ controller @SaCheckPermission 严格一致 ✅
    gz:gacha:{machine,prize}:{list,query,add,edit,remove}
    （machine changeStatus 复用 machine:edit，同写能力，预期）
```

> **DB 实跑 / Flyway live 验证延后**：本 agent sandbox 无 MySQL/Redis 容器（`docker ps` 空），DDL 实际跑通 + 字典 Redis 缓存 flush + admin 浏览器 CRUD 由 kevin-qa Tier 1B（Playwright 起后端）或 Kevin restart 时验证。Tier 1A 已用 mvn 编译/单测 + 机械 grep 字段比对 + vue-tsc 覆盖可静态验证部分。

---

## 风险提示 / 已知 issue

- **R1（已缓解）**：DDL 字段已与 doc/11 §7.1/§7.2 机械比对 1:1，未发现不一致，故无需改源头 doc。
- **R2（已缓解）**：配置态负库存 / remain>initial 由 service 层 + BO @Min 双层拦截；并发扣减是 104 的事。
- **README §D vs ticket AC 7 的 menu 口径**：README §D 一处写「扭蛋池 admin 10100 段」，但 ticket AC 7 + doc/11 §10.3 一致写「10001 机器 / 10002 奖品池」（均在 10000-10099 内）。**采纳 doc/11 §10.3 + ticket AC 7（权威），奖品池落 10002**。README §D 那句 10100 是 stray note，不影响落地（建议 daily closing 时校 README，但不属本卡 patch 范围）。
- **DB live 未验**：见上「DB 实跑延后」，kevin-qa Tier 1B 起后端跑 Flyway + Playwright CRUD 兜底。

## 待 Kevin 批量人验关注

- N/A — 本卡纯 admin + 后端，无 mp 端（跳过 Tier 2 可达 AC，CLAUDE.md §8.2）。AI 全 ✅ 即终态 close。

---

## 对下游 ticket 的提示（GACHA-102 / 103 / 104）

### 表名 / 索引

- 表：`gz_gacha_machine`（PK id）/ `gz_gacha_prize`（PK id）
- 唯一键：`uk_gacha_machine_no (tenant_id, machine_no)` / `uk_gacha_prize_no (tenant_id, prize_no)`
- **GACHA-104 锁行索引**：`idx_gacha_prize_pool (tenant_id, machine_id, enabled, stock_remain)` — SELECT FOR UPDATE 走此索引
- 机器筛选索引：`idx_gacha_machine_status (tenant_id, status)` / `idx_gacha_machine_ip (tenant_id, ip_tag)`

### GACHA-104 直接复用的 mapper 方法（已预置签名，本卡未调用）

- `GzGachaPrizeMapper.selectInPoolForUpdate(Long machineId)` → `List<GzGachaPrize>`
  - SQL：`SELECT * FROM gz_gacha_prize WHERE machine_id=? AND enabled=1 AND stock_remain>0 AND del_flag='0' FOR UPDATE`
  - **必须在 `@Transactional` 事务内调用**（FOR UPDATE 行锁随事务释放）；归一化候选 = 此返回列表
- `GzGachaPrizeMapper.deductStock(Long id, int version)` → `int`（affected）
  - SQL：`UPDATE ... SET stock_remain=stock_remain-1, version=version+1 WHERE id=? AND version=? AND stock_remain>0`
  - **affected=0 → 被并发抢空**：104 把该奖品移出候选 + 重新归一化重抽（有界，绝不退款）
- `GzGachaMachineMapper.increaseSalesCount(Long id, long qty)` → 开盒成功累加机器抽奖次数（原子 UPDATE）
- `GzGachaMachineMapper.autoOffExpiredMachines()` → 到 offline_time 自动下架（cron 用；整机售罄自动下架由 104 在扣减后判断置 `status='auto_off'`，本卡未实现转移逻辑）

### 编号生成器接口名（本卡内 private，下游如需可参照模式或抽到 BizNo）

- 机器：`GM-yyyyMMdd-6位序号`（`GzGachaMachineServiceImpl.generateMachineNo`，private）
- 奖品：`PRZ-yyyyMMdd-6位序号`（`GzGachaPrizeServiceImpl.generatePrizeNo`，private）
- 抽奖记录（104 建）：`DRW-yyyyMMdd-6位序号`（doc/11 §7.3 gz_gacha_draw.draw_no）
- 衍生订单（104 建）：`GACHA-yyyyMMdd-6位序号`（doc/11 §7.4 gz_gacha_order.order_no，README §D 钉死）
- 全部「查当日最大 +1」+ DB UNIQUE 兜底，重启不丢号但单实例假设（与 article_no/product_no 一致）

### 概率公示口径（103 / 104 一致）

```
P(prize_i) = weight_i / Σ weight_j,  j ∈ {machine_id=? AND enabled=1 AND stock_remain>0}
```
- weight 存原始整数（本卡不归一化存储，决策 D3）；admin 仅展示权重，mp 端 103 实时归一化展示「出现概率」
- **盲盒语义**（README §B）：mp 用 扭蛋/开盒/获得/出现概率，禁 抽奖/中奖/开奖；后端 enum/字段可保留 draw 技术语义

### 稀有度字典

- `dict_type='gz_gacha_rarity'`，四档 SSR/SR/R/N（dict_value = enum code），仅展示用
- 已随本卡 DDL seed（tenant_id '000000' 系统字典）；mp 稀有度色走 tokens §1.4（`--c-r-ssr/sr/r/n`，105 动画用），admin 用 ElTag effect=dark

### VO id 跨层契约

- 所有 VO 的 id/machineId/imageId/coverImageId 已 `@JsonSerialize(ToStringSerializer)` → JSON string；下游 TS 类型用 `string`（不用 number）

---

## §AI 测试段（kevin-qa Tier 1B，06:00）

> 环境：后端 8080 live（主线程已起）/ docker MySQL:3307 + Redis:6380 / plus-ui 在 8090 起测后已 kill。

### DB 预检（启动前验证）

```
sys_menu 10000-10024: 13 行 ✅
gz_gacha_rarity 字典: 4 行（SSR/SR/R/N） ✅
gz_gacha_machine 表: 0 行（空表，正常） ✅
gz_gacha_prize 表: 0 行（空表，正常） ✅

menu_id | menu_name       | perms
10000   | 扭蛋机          | (目录)
10001   | 扭蛋机管理      | gz:gacha:machine:list
10002   | 奖品池管理      | gz:gacha:prize:list
10010-10014 机器按钮权限 5个 ✅
10020-10024 奖品按钮权限 5个 ✅
```

### admin Playwright E2E

```
环境：plus-ui@8090 (npx vite --port 8090) + 后端@8080
账号：gz_owner / gz_owner123! (tenantId=1001)
路由：登录后动态加载，实际路径 /gz/gz-gacha/machine 和 /gz/gz-gacha/prize

✅ PASS: 登录 gz_owner 成功 → http://localhost:8090/index
✅ PASS: 侧边栏含「扭蛋机管理」菜单 (menu_id=10000/10001 已授 owner)
✅ PASS: 侧边栏含「奖品池管理」菜单 (menu_id=10002 已授 owner)
✅ PASS: 动态路由已注册: /gz/gz-gacha/machine, /gz/gz-gacha/prize
✅ PASS: 机器管理页 /gz/gz-gacha/machine 加载无 404
✅ PASS: 机器表格列「机器编号」✓
✅ PASS: 机器表格列「机器名」✓  (i18n colName)
✅ PASS: 机器表格列「IP 标签」✓
✅ PASS: 机器表格列「单抽价」✓
✅ PASS: 机器表格列「十连价」✓
✅ PASS: 机器表格列「状态」✓
✅ PASS: 机器表格列「操作」✓
✅ PASS: 机器管理页含「新建扭蛋机」按钮 (i18n gzGachaMachine.add)
✅ PASS: 机器管理页含「查询」/「重置」按钮
✅ PASS: 搜索区含「机器名」/「IP 标签」/「状态」筛选条件
✅ PASS: 点击「新建扭蛋机」→ el-dialog 弹窗打开
✅ PASS: 弹窗含「机器名」字段
✅ PASS: 弹窗含「单抽价」字段（元录入）
✅ PASS: 弹窗含 IP 标签字段
✅ PASS: 弹窗含「十连价」字段（可空，提示「留空表示不支持十连」）
  NOTE: 弹窗无「状态」选择器 — 设计决策：新建固定 off_shelf，上下架通过列表操作按钮切换（符合 AC 6 / 决策 D5）
✅ PASS: 奖品池管理页 /gz/gz-gacha/prize 加载无 404
✅ PASS: 奖品表格列「奖品编号」✓
✅ PASS: 奖品表格列「奖品名」✓
✅ PASS: 奖品表格列「稀有度」✓
✅ PASS: 奖品表格列「权重」✓
✅ PASS: 奖品表格列「初始库存」✓
✅ PASS: 奖品表格列「剩余库存」✓
✅ PASS: 奖品表格列「参与抽奖」✓
✅ PASS: 奖品表格列「操作」✓
✅ PASS: 奖品池页含「返回机器列表」按钮
✅ PASS: 奖品池页含「新增奖品」按钮
✅ PASS: 点击「新增奖品」→ 弹窗打开
✅ PASS: 奖品弹窗含「稀有度」字段（下拉，4档 SSR/SR/R/N）
✅ PASS: 奖品弹窗含「权重」字段
✅ PASS: 奖品弹窗含「初始库存」字段

Playwright E2E 总计：PASS 39 / NOTE 1 / FAIL 0（全部 UI 结构断言通过）
截图：/tmp/pw-gacha/acc-0{1-4}-*.png
```

### API 契约回归

```bash
# 1. 登录 gz_owner → 获取 token
POST /auth/login {"username":"gz_owner","password":"gz_owner123!","clientId":"e5cd7e4891bf95d1d19206ce24a7b32e","tenantId":"1001"}
# 期望: 200 + access_token
# 实际: ✅ {"code":200,"data":{"access_token":"eyJ..."}}

# 2. 机器列表（空表）
GET /system/gz/gacha/machine/list?pageNum=1&pageSize=10
# 期望: 200 + rows=[] total=0
# 实际: ✅ {"code":200,"total":0,"rows":[]}

# 3. 奖品列表（按 machineId 过滤）
GET /system/gz/gacha/prize/list?pageNum=1&pageSize=10&machineId=1
# 期望: 200 + rows=[] total=0
# 实际: ✅ {"code":200,"total":0,"rows":[]}

# 4. 权限 403 — gz_staff_chengdu (role=staff, 无 gz:gacha:* 权限)
GET /system/gz/gacha/machine/list  [Bearer staff_token]
# 期望: 403
# 实际: ✅ {"code":403,"msg":"没有访问权限，请联系管理员授权"}

POST /system/gz/gacha/machine  [Bearer staff_token]
# 期望: 403
# 实际: ✅ {"code":403,"msg":"没有访问权限，请联系管理员授权"}

# 5. ❌ 机器新增（FAIL — Bug #1）
POST /system/gz/gacha/machine {"name":"E2E测试扭蛋机","singlePriceCent":1000,"ipTag":"宫崎骏","status":"off_shelf"}
# 期望: 200 + data=新机器 id
# 实际: ❌ {"code":500,"msg":"发生未知异常"}
# 根因: java.sql.SQLSyntaxErrorException: Unknown column 'create_dept' in 'field list'
#       DDL 漏建 create_dept BIGINT 列（BaseEntity.createDept @TableField(fill=INSERT)）

# 6. 分析：GET list 空表正常，GET list 有数据 → 也 500（同根因：MyBatis-Plus SELECT 列名枚举含 create_dept）
```

### Bug #1 — DDL 缺 `create_dept` 列（Tier 1B ❌ 阻断写操作）

**现象**：所有写操作（POST 新建 / PUT 编辑 / DELETE 带 create_dept 的 UPDATE）返回 500，`Unknown column 'create_dept' in 'field list'`。SELECT 有数据时也 500。

**根因**：
- `GzGachaMachine` / `GzGachaPrize` 均继承 `TenantEntity → BaseEntity`
- `BaseEntity` 包含 `createDept Long` 字段（`@TableField(fill = FieldFill.INSERT)`）
- DDL `V202606171000` 建表时漏加 `create_dept BIGINT NULL` 列
- 同时 `create_by` / `update_by` 列类型写错为 `VARCHAR(64)`（应为 `BIGINT`，对齐 BaseEntity Long 类型）

**修复方法**（kevin-coder 闭环）：新建 Flyway 迁移文件，对两张表补列：
```sql
-- 文件名: V202606181000__GZ-GACHA-101-fix-create_dept.sql（时间戳 > 171001）
ALTER TABLE gz_gacha_machine
  ADD COLUMN create_dept BIGINT NULL COMMENT '创建部门' AFTER tenant_id,
  MODIFY COLUMN create_by BIGINT NULL COMMENT '创建者',
  MODIFY COLUMN update_by BIGINT NULL COMMENT '更新者';

ALTER TABLE gz_gacha_prize
  ADD COLUMN create_dept BIGINT NULL COMMENT '创建部门' AFTER tenant_id,
  MODIFY COLUMN create_by BIGINT NULL COMMENT '创建者',
  MODIFY COLUMN update_by BIGINT NULL COMMENT '更新者';
```

**范围**：机器 CRUD 全链路（新建/编辑/删除/上下架）+ 奖品 CRUD 全链路均 blocked。

### 跳过 / 未跑

- 上下架状态切换 E2E（需先有数据，但 INSERT 500 → 无法创建测试数据）
- 机器删除守卫（有奖品拒删）E2E（同上，无数据）
- 「管理奖品池」点击跳转验证（表空，行操作按钮不展示，符合预期）
- 金额元→分换算完整 E2E（前端代码已有 `Math.round(yuan * 100)`，但 INSERT 500 无法端到端验证）
  - DB 字段 `single_price_cent BIGINT` 已确认 ✅（字段命名/类型正确）
  - 前端 `centToYuan()` 展示换算已在 Vue 源码存在 ✅
  - 仅缺"实际写入后读回"一步（Bug #1 修复后自动通过）

### 结论

**Tier 1B ❌ — 1 处 Bug 需 kevin-coder 闭环修**

| # | 项目 | 结果 | 根因 |
|---|---|---|---|
| UI 结构 | admin Playwright E2E（登录/菜单/列表页/弹窗/权限） | ✅ 全通 (39/39) | — |
| 权限控制 | staff 访问 gacha → 403 | ✅ | — |
| DB 预检 | 13 menu / 4 字典 / 2 空表 | ✅ | — |
| GET API | 空表 list → 200 | ✅ | — |
| 写 API | POST/PUT/DELETE → 500 | ❌ | DDL 漏 create_dept 列 |

**失败清单 → 建议 kevin-coder 闭环修**：

1. `gz_gacha_machine` / `gz_gacha_prize` 两张表 DDL 遗漏 `create_dept BIGINT NULL` 列，同时 `create_by` / `update_by` 类型应为 `BIGINT` 而非 `VARCHAR(64)`（参考 `gz_bean_store` DDL 正确写法）。修复 = 新建 `V202606171002__GZ-GACHA-101-fix-base-columns.sql` 补 ALTER TABLE，Flyway 自动跑即可。修复后重跑写操作 curl 确认 200。

---

## §AI 测试段 R1 复测（kevin-qa，Bug#1 修复后，06:40）

> 触发：主线程已落 `V202606171002__GZ-GACHA-101-fix-base-columns.sql`，DB 三列已 BIGINT，后端重启。

### DB fix 验证

```
DESCRIBE gz_gacha_machine:
  create_dept  bigint  YES  NULL  ✅
  create_by    bigint  YES  NULL  ✅
  update_by    bigint  YES  NULL  ✅

DESCRIBE gz_gacha_prize:
  create_dept  bigint  YES  NULL  ✅
  create_by    bigint  YES  NULL  ✅
  update_by    bigint  YES  NULL  ✅
```

### API 契约复测（之前挂的写操作）

```bash
# 1. 机器新增（R1 核心复测）
POST /system/gz/gacha/machine
Body: {"name":"R1复测-宫崎骏联名扭蛋机","singlePriceCent":1000,"tenPackPriceCent":9000,"ipTag":"宫崎骏","status":"off_shelf"}
# 期望：200 + data=machineId
# 实际：✅ {"code":200,"msg":"新建成功","data":2}

# 2. GET list（有数据）
GET /system/gz/gacha/machine/list?pageNum=1&pageSize=10
# 期望：200 + total=1 + rows 含新建机器
# 实际：✅ code=200, total=1, machineNo=GM-20260603-000001, singlePriceCent=1000→10元, tenPackPriceCent=9000→90元, status=off_shelf

# 3. 奖品新增（SSR / weight=5 / stock=100）
POST /system/gz/gacha/prize
Body: {"machineId":"2","name":"R1复测-SSR奖品-宫崎骏周边","rarity":"SSR","weight":5,"stockInitial":100,"enabled":1}
# 期望：200 + prizeId
# 实际：✅ {"code":200,"msg":"新建成功","data":1}

# 4. 奖品列表（按 machineId=2 过滤）
GET /system/gz/gacha/prize/list?machineId=2
# 期望：200 + total=1 + rarity=SSR, stockRemain=stockInitial=100
# 实际：✅ total=1, prizeNo=PRZ-20260603-000001, rarity=SSR, weight=5, stockInitial=100, stockRemain=100, enabled=1
```

### DB 直查（金额单位 + create_dept 有值）

```
gz_gacha_machine id=2:
  machine_no:        GM-20260603-000001
  single_price_cent: 1000  → 10 元 ✅（分=元×100）
  ten_pack_price_cent:9000 → 90 元 ✅
  create_dept:       103   ✅（InjectionMetaObjectHandler 自动填充）
  create_by:         100   ✅（gz_owner user_id）

gz_gacha_prize id=1:
  machine_id:    2 ✅
  rarity:        SSR ✅
  stock_initial: 100 ✅
  stock_remain:  100 ✅（新增 stockRemain 空 → 默认=stockInitial，决策 D4）
  create_dept:   103 ✅
  create_by:     100 ✅
```

### Playwright E2E R1 复测（15/15 PASS）

```
✅ 登录 gz_owner ✓
✅ 机器列表出现「R1复测-宫崎骏联名扭蛋机」✓
✅ 机器编号 GM-20260603-000001 ✓
✅ 单抽价 ¥10.00（1000分÷100）✓
✅ 十连价 ¥90.00（9000分÷100）✓
✅ 机器状态「上架」(on_shelf) ✓ — 上架操作持久化确认
✅ 机器行操作含「管理奖品池」按钮 ✓
✅ 奖品池页（/gz/gz-gacha/prize?machineId=2）加载无 404 ✓
✅ 奖品列表出现「R1复测-SSR奖品-宫崎骏周边」✓
✅ 奖品编号 PRZ-20260603-000001 ✓
✅ 稀有度「SSR」显示 ✓
✅ 权重「5」✓
✅ 初始库存/剩余库存「100」✓
✅ 参与抽奖状态显示 ✓
✅ 奖品池页含「返回机器列表」按钮 ✓

R1 复测 PASS 15 / FAIL 0 / TOTAL 15
```

### 新发现 Bug#2（R1 复测期间发现，非 R1 范围内，需独立修）

**现象**：机器列表点击「管理奖品池」按钮跳转 404。  
**根因**：`plus-ui/src/views/gz-gacha/machine/index.vue` 第 341 行 `handleManagePrize` 调用 `router.push({ path: '/gz-gacha/prize', ... })`，缺少 `/gz` 前缀（动态路由父级）。正确路径应为 `/gz/gz-gacha/prize`。  
**影响**：点击跳转 404；直接用路由或菜单进入奖品池完全正常（奖品 CRUD 无问题）。  
**修复**：`machine/index.vue` 第 341 行 `path` 改为 `/gz/gz-gacha/prize`（或改用 route name 避免 hard-code）。

### 结论

**Tier 1B R1 复测 ✅ — Bug#1 完全闭环**

| # | 项目 | 初测 | R1 复测 |
|---|---|---|---|
| POST 机器新增 | ❌ 500 `create_dept` | ✅ 200 成功 |
| GET list 有数据 | ❌ 500 | ✅ 200 + 数据正确 |
| 金额换算 E2E | ⏭️ 无法测 | ✅ 1000分=¥10.00 / 9000分=¥90.00 |
| DB create_dept 填充 | ⏭️ 无法测 | ✅ create_dept=103, create_by=100 |
| 奖品新增 POST | ⏭️ 无法测 | ✅ 200 成功 + machineId 过滤正确 |
| 上下架切换 | ⏭️ 无数据跳过 | ✅ on_shelf 持久化确认 |

**新增 Bug#2**（需 kevin-coder 独立修）：`machine/index.vue handleManagePrize router.push` 路径缺 `/gz` 前缀 → 点击「管理奖品池」404。修复一行代码即可。
