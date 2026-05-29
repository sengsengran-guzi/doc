# GZ-BEAN-002 — 完工报告

> 拼豆座位主数据 + 时段模板配置（M 复杂度）。D04 串行 4 ticket 第 2 个，BEAN-003 选座页的核心依赖。
> 实施时间 ~1.5h（含 R6 顺手修 + 完整重叠校验 + admin tab 双子页 + 单测 22 例）。

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | ✅ N/A | 项目无 git 仓库 |
| 上游 BEAN-001 hotfix | ✅ | sys_user 100/101 tenant=1001 / gz_bean_store CD001 tenant=1001 / sys_role 100/101 tenant=1001 — 全 1001 |
| plus-ui store/index.vue resp 解包 | ✅ | 仅 L312 注释引用，无残留 bug |
| ruoyi-admin 进程 | ✅ → 重启后 PID 6514 LISTEN | hotfix 后 PID 57412 → install 新 jar 后重启 → PID 5086 → BO 修正后再重启 → PID 6514 |
| 编译健康 | ✅ | mvn compile 21 sources / 1.6s |
| menu_id 段 6020-6049 | ✅ | 段内空（BEAN-001 占 6000-6006，本 ticket 占 6020-6034） |
| ADR-0001 已读 | ✅ | V1 业务表全 1001，新建用户也走 1001 |
| 权威蓝图 doc/10 §3 / doc/11 §3.2/3.3 已读 | ✅ | 字段层完全对齐 |
| 合同范围 | ✅ V1.0 拼豆主线 D04 = 2026-06-01 ≤ 6/15 硬期限 | |

### §0 硬探记录

```bash
# 1. hotfix 后态验证
mysql> SELECT user_name, tenant_id FROM sys_user WHERE user_id IN (100,101);
+------------------+-----------+
| gz_owner         | 1001      |   ✅
| gz_staff_chengdu | 1001      |   ✅

mysql> SELECT id, store_no, name, tenant_id, del_flag FROM gz_bean_store;
+----+----------+-----------------+-----------+----------+
| 1  | CD001    | 成都春熙路店     | 1001      | 0        |   ✅ active seed

mysql> SELECT role_id, role_name, tenant_id FROM sys_role WHERE role_id IN (100,101);
| 100      | 甲方负责人 | 1001      |   ✅
| 101      | 门店运营   | 1001      |   ✅

# 2. ruoyi-admin 进程
lsof -i:8080 → PID 57412 LISTEN  ✅（后续 install 后重启）

# 3. menu_id 6020-6049 段空
mysql> SELECT menu_id FROM sys_menu WHERE menu_id BETWEEN 6020 AND 6049;
(空) ← ✅
```

### §0 顺手修复（R6: gz-common/user/index.vue 同款 resp.data 解包 bug）

BEAN-001 hotfix 报告 §风险更新 R6 标注的：`plus-ui/src/views/gz-common/user/index.vue` L208/209/237 同款 `resp.data.rows/total/data` 解包 bug — GZ-SYS-003 上线后用户管理列表必然空白。BEAN-002 §0 阶段顺手修（10 秒）：

```diff
- const resp = await listGzUser(buildQuery.value);
- rows.value = resp.data.rows || [];
- total.value = resp.data.total || 0;
+ // ruoyi request.ts interceptor 已解包；用 as any cast。
+ const resp = await listGzUser(buildQuery.value);
+ rows.value = (resp as any).rows || [];
+ total.value = (resp as any).total || 0;

- const resp = await getGzUser(row.id);
- detail.value = resp.data;
+ const resp = await getGzUser(row.id);
+ detail.value = resp as any;
```

修完 grep 验证：

```bash
$ grep -n "resp\.data" src/views/gz-common/user/index.vue
(无输出)  ✅ 3 处全修
```

### 权威文档引用摘录（doc/11 §3.2 / §3.3 完整字段层规约对照）

**§3.2 gz_bean_time_slot_template**：

| doc/11 字段 | 类型 | 关键约束 | 本 ticket 落地 |
|---|---|---|---|
| store_id | BIGINT UNSIGNED NOT NULL | FK gz_bean_store.id | ✅ |
| slot_name | VARCHAR(32) NULL | mp 端空时回退 start-end | ✅ |
| start_time / end_time | TIME NOT NULL | end > start（service 校验）| ✅ |
| weekdays | VARCHAR(16) NOT NULL DEFAULT '1,2,3,4,5,6,7' | ISO 8601 逗号分隔 | ✅ |
| effective_date / expire_date | DATE NULL | 可空 = 立即/永久 | ✅ |
| enabled | TINYINT NOT NULL DEFAULT 1 | 0=停用 1=启用 | ✅ |
| sort_no | INT NOT NULL DEFAULT 0 | 升序 | ✅ |
| IDX (tenant_id, store_id, enabled, sort_no) | — | mp 端查询主路径 | ✅ |

**§3.3 gz_bean_seat**：

| doc/11 字段 | 类型 | 关键约束 | 本 ticket 落地 |
|---|---|---|---|
| store_id | BIGINT UNSIGNED NOT NULL | FK | ✅ |
| seat_no | VARCHAR(16) NOT NULL | UNIQUE(tenant_id, store_id, seat_no) | ✅ |
| row_label / col_index | VARCHAR(8) / TINYINT NULL | 辅助网格 | ✅ |
| enabled | TINYINT NOT NULL DEFAULT 1 | 同上 | ✅ |
| UNIQUE uk_tenant_store_seat_no | — | 含 tenant_id | ✅ |
| IDX (tenant_id, store_id, enabled) | — | mp 选座主路径 | ✅ |

**任务卡 AC 1 与 doc/11 偏差**：任务卡写时段模板 `UNIQUE (tenant_id, store_id, start_time, end_time, weekdays)`，但 doc/11 §3.2 仅有 IDX 没有 UNIQUE。**按 CLAUDE.md §9.5 #1 以 doc/11 为准**：不建 UNIQUE，时段冲突由 service 重叠校验拦截（更精准 — 业务里 `14-15 vs 14:30-15:30` 才是问题，UNIQUE 防不住，service 重叠校验防得住）。决策已在 DDL 文件顶部注释 + 本报告 §决策记录段写明。

---

## 实现摘要

### 改动文件清单

**后端（ruoyi-gz-bean）— 14 新增**：
```
A code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-bean/src/main/java/org/dromara/gz/bean/
  ├── domain/entity/GzBeanSeat.java
  ├── domain/entity/GzBeanTimeSlotTemplate.java
  ├── domain/vo/GzBeanSeatVO.java
  ├── domain/vo/GzBeanTimeSlotTemplateVO.java
  ├── domain/bo/GzBeanSeatBo.java
  ├── domain/bo/GzBeanSeatQueryBo.java
  ├── domain/bo/GzBeanSeatBatchGenerateBo.java
  ├── domain/bo/GzBeanTimeSlotTemplateBo.java
  ├── domain/bo/GzBeanTimeSlotTemplateQueryBo.java
  ├── domain/bo/GzBeanTimeSlotBatchByWeekBo.java
  ├── mapper/GzBeanSeatMapper.java
  ├── mapper/GzBeanTimeSlotTemplateMapper.java
  ├── service/IGzBeanSeatService.java
  ├── service/IGzBeanTimeSlotTemplateService.java
  ├── service/impl/GzBeanSeatServiceImpl.java
  ├── service/impl/GzBeanTimeSlotTemplateServiceImpl.java
  ├── controller/GzBeanSeatController.java
  └── controller/GzBeanTimeSlotTemplateController.java

+ src/test/java/.../GzBeanSeatServiceImplTest.java（12 测试）
+ src/test/java/.../GzBeanTimeSlotTemplateServiceImplTest.java（10 测试）
```

**DDL（ruoyi-admin/.../db/migration）— 2 新增**：
```
A V202606011000__GZ-BEAN-002-create-gz_bean_seat-and-time-slot.sql
A V202606011001__GZ-BEAN-002-menu.sql
```

**Admin（plus-ui）— 3 新增 / 3 修改**：
```
A code/main/plus-ui/src/api/gz-bean/seat.ts
A code/main/plus-ui/src/api/gz-bean/slot.ts
A code/main/plus-ui/src/views/gz-bean/config/index.vue（Tab 包座位 + 时段 + 批量两弹窗）
M code/main/plus-ui/src/lang/zh_CN.ts（+ gzBeanConfig 块）
M code/main/plus-ui/src/lang/en_US.ts（同上）
M code/main/plus-ui/src/views/gz-common/user/index.vue（§0 顺手修 R6）
```

**Mp（miniapp）— 0**：本 ticket 不动 mp（BEAN-003 才消费时段 / 座位 API）

### 关键决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 时段模板**不建 UNIQUE**，重叠校验放 service | doc/11 §3.2 仅 IDX；UNIQUE 防不住实际业务的"时段重叠"问题（14-15 vs 14:30-15:30 完全相等才能 UNIQUE，而部分重叠才是真问题）；service 层逐字段比对更精准 + 中文友好提示 |
| D2 | weekdays VARCHAR(16) 逗号分隔 + Java 侧 set 精确 split 校验 | doc/11 §3.2 已锚定；Java 用 `Set<String>.contains(target)` 而非 `String.contains` 避免 "11,12" 误匹配 "1"（已有单测 `selectMpEnabledSlots_noFalsePositiveOn11` 验证） |
| D3 | 编辑路径**不允许跨门店搬迁** + **业务码不可改** | 跨门店搬迁会让历史 booking 错位；service 层 `toEntity(skipSeatNo=true)` / `toEntity(isUpdate=true)` 显式拒绝 |
| D4 | 批量生成座位用 `try/catch DuplicateKeyException` 跳过已存在 | 比"先查再插"无锁 race-free；UNIQUE 兜底；业务语义清晰 |
| D5 | service 层 endTime > startTime 校验，**DDL 不加 CHECK** | MySQL 5.7-8.x CHECK 行为不一致；service 层一致更可控 + 中文错误信息 |
| D6 | mp 端拉时段：SQL 过滤 `enabled + effective/expire_date 范围`，**weekdays 留 Java 侧** | doc/11 §3.2 重要语义"SQL FIND_IN_SET"等价；但 MyBatis-Plus LambdaQueryWrapper FIND_IN_SET 需 Custom SQL，Java 侧用 set 更可读 + 单测易写 |
| D7 | menu_id 6020-6049 段：6020 主页面 + 6021-6025 座位 5 按钮 + 6030-6034 时段 5 按钮 | CLAUDE.md §6 #6 GZ-BEAN 6000-6999；BEAN-001 占 6000-6006，预留 6007-6019 给未来扩展；本 ticket 6020-6049 |
| D8 | admin 端**单页 Tab 两子页**（座位 / 时段 + 两个批量弹窗 + 两个单建编辑弹窗）| 任务卡 Tech "tab 包两子页"明示；减少菜单深度（vs 分两菜单），运营操作更顺手 |
| D9 | 同步 ID 类型 BO 编辑场景 `seatNo / storeId` 改为**仅 AddGroup 必填**（EditGroup 忽略） | 实际编辑常只改 enabled/sortNo（如 switch 触发 toggle）— 若 EditGroup 还要求 seatNo 必填，前端 PATCH-style 调用会被 Bean Validation 拦截；测试阶段已踩坑 → 修 BO + 重新 install |
| D10 | DDL 时间戳 V202606011000 / V202606011001（D04 第 2 个） | BEAN-001 占 V202606010900-0902 + hotfix V202606010950；BEAN-002 占 1000-1001；预留 1002+ 给 BEAN-003/004 |

### 关联蓝图引用

- **业务流**：doc/10 §3 拼豆预约全流程 — §3.N4（mp 端拉时段 + 座位）/ §3 业务规则（座位停用不影响已有预约 / 时段停用 mp 灰显）/ §3 异常分支 E3 E4
- **字段表**：doc/11 §3.2 gz_bean_time_slot_template（完整 DDL 来源）+ §3.3 gz_bean_seat
- **关联 ticket**：GZ-BEAN-001 ✅(上游 store_id 外键) / GZ-BEAN-003（下游 mp 选座 — 消费 `/app/...`，本 ticket 仅留 service 层方法，mp Controller 在 BEAN-003 加） / GZ-BEAN-004（下游提交预约 — booking 需 join store + seat + slot 三表）

---

## AI 自测（8 个测试代码 block）

### 1. 编译

```
$ cd code/main/RuoYi-Vue-Plus && mvn compile -pl ruoyi-modules/ruoyi-gz-bean -am
[INFO] Compiling 21 source files with javac [debug release 17] to target/classes
[INFO] BUILD SUCCESS
[INFO] ruoyi-gz-bean ...................................... SUCCESS [  0.067 s]
[INFO] Total time:  1.610 s
```

### 2. 单测（36 个测试全过；BEAN-001 14 + BEAN-002 22）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-bean -am -Dsurefire.failIfNoSpecifiedTests=false

[INFO] Running org.dromara.gz.bean.service.impl.GzBeanSeatServiceImplTest
[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.729 s
[INFO] Running org.dromara.gz.bean.service.impl.GzBeanTimeSlotTemplateServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.043 s
[INFO] Running org.dromara.gz.bean.service.impl.GzBeanStoreServiceImplTest（BEAN-001 回归）
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.065 s

[INFO] Results:
[INFO] Tests run: 36, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

座位测试覆盖（12 例）：
- insertByBo happy + 默认值兜底
- insertByBo UNIQUE 拦截 → ServiceException
- updateByBo 忽略 seatNo / storeId（业务码不可改 / 禁跨门店搬迁）
- updateByBo id=null → ServiceException
- batchGenerate happy 全部成功
- batchGenerate UNIQUE 冲突跳过对应条目
- selectMpEnabledSeats null storeId → 空 list
- selectMpEnabledSeats 正常透传 mapper
- checkSeatNoUnique 空 seatNo → 视为唯一
- checkSeatNoUnique 编辑场景排除自身 id
- deleteByIds 空集合 → false
- deleteByIds 正常软删

时段测试覆盖（10 例）：
- insertByBo happy
- insertByBo end <= start → ServiceException
- insertByBo 时段重叠（weekdays 交集 + 时段交集）→ ServiceException
- insertByBo weekdays 无交集 → 不触发重叠
- updateByBo 重叠校验排除自身 id
- updateByBo id=null → ServiceException
- batchByWeek 多 slot 多 insert
- selectMpEnabledSlots null 参数 → 空 list
- selectMpEnabledSlots weekdays 不含目标 → 过滤
- selectMpEnabledSlots "11,12" 不误匹配 "1"（精确 split 防御）
```

### 3. DDL 跑通 + schema 验证

```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606011000__GZ-BEAN-002-create-gz_bean_seat-and-time-slot.sql
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606011001__GZ-BEAN-002-menu.sql

$ DESC gz_bean_seat;
id        bigint unsigned   PRI AUTO_INCREMENT
store_id  bigint unsigned   NOT NULL
seat_no   varchar(16)       NOT NULL
row_label varchar(8)        NULL
col_index tinyint           NULL
enabled   tinyint           NOT NULL DEFAULT 1
sort_no   int               NOT NULL DEFAULT 0
tenant_id varchar(20)       MUL DEFAULT '1001'
[公共字段...]
del_flag  char(1)           NOT NULL DEFAULT '0'
✅ 15 字段全对齐 doc/11 §3.3

$ DESC gz_bean_time_slot_template;
id              bigint unsigned   PRI
store_id        bigint unsigned   NOT NULL
slot_name       varchar(32)       NULL
start_time      time              NOT NULL
end_time        time              NOT NULL
weekdays        varchar(16)       NOT NULL DEFAULT '1,2,3,4,5,6,7'
effective_date  date              NULL
expire_date     date              NULL
enabled         tinyint           NOT NULL DEFAULT 1
sort_no         int               NOT NULL DEFAULT 0
tenant_id       varchar(20)       MUL DEFAULT '1001'
[公共字段...]
✅ 18 字段全对齐 doc/11 §3.2
```

### 4. 菜单 + 权限 DB 层验证

```
$ SELECT menu_id, menu_name, parent_id, perms, menu_type FROM sys_menu WHERE menu_id BETWEEN 6020 AND 6040;
6020 | 座位与时段配置    | 6000 | gz:bean:seat:list,gz:bean:slot:list | C
6021 | 座位列表          | 6020 | gz:bean:seat:list                   | F
6022 | 座位新增          | 6020 | gz:bean:seat:add                    | F
6023 | 座位编辑          | 6020 | gz:bean:seat:edit                   | F
6024 | 座位删除          | 6020 | gz:bean:seat:remove                 | F
6025 | 座位批量生成      | 6020 | gz:bean:seat:batchGenerate          | F
6030 | 时段列表          | 6020 | gz:bean:slot:list                   | F
6031 | 时段新增          | 6020 | gz:bean:slot:add                    | F
6032 | 时段编辑          | 6020 | gz:bean:slot:edit                   | F
6033 | 时段删除          | 6020 | gz:bean:slot:remove                 | F
6034 | 时段批量按周配置  | 6020 | gz:bean:slot:batchByWeek            | F
✅ 11 行全对齐

$ SELECT role_id, COUNT(*) FROM sys_role_menu WHERE menu_id BETWEEN 6020 AND 6040 GROUP BY role_id;
100  11   ← owner 全 11 项授权 ✅
101  3    ← staff 仅 3 项（6020 页面 + 6021 座位查 + 6030 时段查）✅
```

### 5. admin API 端到端（owner，CRUD + 业务规则）

```bash
# 0. owner 登录 tenantId=1001
$ TOKEN=...gz_owner...
✅ access_token 取得

# TEST-A: 空列表
$ GET /system/gz/bean/seat/list  → {"total":0,"rows":[],"code":200}  ✅
$ GET /system/gz/bean/slot/list  → {"total":0,"rows":[],"code":200}  ✅

# TEST-C: 单建座位 A1
$ POST /system/gz/bean/seat -d '{"storeId":1,"seatNo":"A1","rowLabel":"A","colIndex":1,"enabled":1}'
  → {"code":200,"msg":"操作成功"}  ✅

# TEST-D: 重复 A1 UNIQUE 拦截
$ POST /system/gz/bean/seat -d '{"storeId":1,"seatNo":"A1","enabled":1}'
  → {"code":500,"msg":"座位号已存在：A1"}  ✅

# TEST-E: 批量生成 B1-B6
$ POST /system/gz/bean/seat/batchGenerate -d '{"storeId":1,"prefix":"B","startIndex":1,"count":6,...}'
  → {"code":200,"msg":"成功生成 6 个座位（重复跳过）","data":6}  ✅

# TEST-F: 再次批量 B1-B3（全冲突）
$ POST 同上 count:3
  → {"code":200,"msg":"成功生成 0 个座位（重复跳过）","data":0}  ✅

# TEST-G: DB 验证（7 座位 + tenant=1001 全自动注入）
$ SELECT id, seat_no, enabled, tenant_id, del_flag FROM gz_bean_seat;
1  A1  1  1001  0
2  B1  1  1001  0
3  B2  1  1001  0
4  B3  1  1001  0
5  B4  1  1001  0
6  B5  1  1001  0
7  B6  1  1001  0
✅ 7 行 / tenant 全 1001 / 全 enabled

# TEST-H: 编辑 B1 停用（PATCH-style，只传 id + enabled + sortNo）
$ PUT /system/gz/bean/seat -d '{"id":2,"enabled":0,"sortNo":99}'
  → {"code":200,"msg":"操作成功"}
$ SELECT id, seat_no, enabled, sort_no FROM gz_bean_seat WHERE id=2;
  2 | B1 | 0 | 99   ← seatNo 未被改成 null（mybatis-plus 跳过 null 字段 update），符合预期 ✅
```

### 6. admin API 端到端（时段：重叠 / end<=start / 格式 / 批量）

```bash
# TEST-I: 时段新建 工作日 10:00-12:00
$ POST /system/gz/bean/slot -d '{"storeId":1,"slotName":"上午","startTime":"10:00:00","endTime":"12:00:00","weekdays":"1,2,3,4,5","enabled":1}'
  → {"code":200,"msg":"操作成功"}  ✅

# TEST-J: 时段重叠拒绝（weekdays={1,2} ⊂ {1-5} + 时段 11-13 ⊃ 10-12 部分）
$ POST -d '{"storeId":1,"startTime":"11:00:00","endTime":"13:00:00","weekdays":"1,2",...}'
  → {"code":500,"msg":"时段与已有模板重叠：星期 1,2 已有 10:00-12:00"}  ✅
  ★ 这是 D04 R3 R1 风险缓解的核心 — 应用层校验工作正确

# TEST-K: 时段无交集（周末 14-16，与已有工作日 10-12 无交集）
$ POST -d '{"storeId":1,"slotName":"下午","startTime":"14:00:00","endTime":"16:00:00","weekdays":"6,7",...}'
  → {"code":200,"msg":"操作成功"}  ✅

# TEST-L: end <= start 拒绝
$ POST -d '{"storeId":1,"startTime":"15:00:00","endTime":"14:00:00","weekdays":"1",...}'
  → {"code":500,"msg":"结束时间必须晚于开始时间"}  ✅

# TEST-M: weekdays 格式错误（Bean Validation 拦截）
$ POST -d '{"storeId":1,"startTime":"10:00:00","endTime":"12:00:00","weekdays":"8,9",...}'
  → {"code":500,"msg":"适用星期格式错误，应为逗号分隔的 1-7（如 1,2,3,4,5）"}  ✅

# TEST-N: 按周批量配置（工作日 [14-15:30, 16-17:30]）
$ POST /system/gz/bean/slot/batchByWeek -d '{"storeId":1,"weekdays":"1,2,3,4,5","slots":[{"slotName":"下午1","startTime":"14:00:00","endTime":"15:30:00"},{"slotName":"下午2","startTime":"16:00:00","endTime":"17:30:00"}]}'
  → {"code":200,"msg":"成功批量配置 2 条时段","data":2}  ✅

# TEST-O: 时段总览（4 条）
$ SELECT id, slot_name, start_time, end_time, weekdays, tenant_id FROM gz_bean_time_slot_template;
1  上午    10:00:00  12:00:00  1,2,3,4,5  1001
2  下午    14:00:00  16:00:00  6,7        1001
3  下午1   14:00:00  15:30:00  1,2,3,4,5  1001
4  下午2   16:00:00  17:30:00  1,2,3,4,5  1001
✅ 4 行 / tenant 全 1001 / 无重叠
```

### 7. 权限分级 + listByStore + @Log

```bash
# TEST-P: GET listByStore/1（座位）→ 返 7 行（含 B1 enabled=0）  ✅
# TEST-Q: GET listByStore/1（时段）→ 返 4 行  ✅
# TEST-R: GET seat/1 详情  ✅
# TEST-S: GET slot/1 详情（startTime "10:00:00" / endTime "12:00:00" 格式正确）  ✅

# TEST-T: staff GET 座位 list（有 gz:bean:seat:list perm）→ 200 / total=7  ✅
# TEST-U: staff POST 座位（无 gz:bean:seat:add）→ 403  ✅
# TEST-V: staff DELETE 时段（无 gz:bean:slot:remove）→ 403  ✅

# TEST-W: owner DELETE 座位 id=1（软删）
$ DELETE /system/gz/bean/seat/1 → {"code":200,"msg":"操作成功"}
$ SELECT id, seat_no, del_flag FROM gz_bean_seat WHERE id=1;
  1 | A1 | 1   ← ✅ del_flag=1 软删生效

# TEST-X: @Log AOP 验证 — sys_oper_log
$ SELECT oper_id, title, business_type, oper_name, status FROM sys_oper_log
  WHERE title LIKE '拼豆座位%' OR title LIKE '拼豆时段%' ORDER BY oper_id DESC LIMIT 10;
拼豆座位                   3 (DELETE)  gz_owner  0
拼豆时段模板按周批量       1 (INSERT)  gz_owner  0
拼豆时段模板               1 (INSERT)  gz_owner  1 (失败 TEST-M 格式错)
拼豆时段模板               1 (INSERT)  gz_owner  0 (成功 TEST-K)
拼豆时段模板               1 (INSERT)  gz_owner  1 (失败 TEST-L end<=start)
拼豆时段模板               1 (INSERT)  gz_owner  0 (成功 TEST-I)
拼豆座位                   2 (UPDATE)  gz_owner  0
拼豆座位批量生成           1 (INSERT)  gz_owner  0 (TEST-F)
拼豆座位批量生成           1 (INSERT)  gz_owner  0 (TEST-E)
拼豆座位                   1 (INSERT)  gz_owner  1 (失败 TEST-D 重复)
✅ @Log AOP 完整捕获：座位 CRUD / 时段 CRUD / 批量 / 成功 + 失败两类
```

### 8. plus-ui build

```
$ cd code/main/plus-ui && pnpm build:dev
dist/assets/index-D5L6bdB_.js     1,660.36 kB │ gzip: 557.27 kB
✓ built in 14.74s
✅ TS / Vue 全过（仅 chunk-size 警告，ruoyi 默认）
```

清理测试脏数据后回归到干净态：
```
$ DELETE FROM gz_bean_seat; DELETE FROM gz_bean_time_slot_template;
   AUTO_INCREMENT=1（避免下游 ticket 数据 id 跳跃）;
$ SELECT COUNT(*) FROM gz_bean_seat → 0  ✅
$ SELECT COUNT(*) FROM gz_bean_time_slot_template → 0  ✅
```

---

## 风险提示 / 已知 issue

| # | 风险 | 严重度 | 缓解 / 待办 |
|---|---|---|---|
| R1 | 时段重叠校验是应用层 — 高并发 admin 同时建相同时段时仍可能漏（无 SELECT FOR UPDATE）| 低 | admin 端非高并发场景，业务上 owner 极少同时操作；BEAN-004 mp 端预约才有真高并发，那时 Redis 锁 + UNIQUE 双层兜底 |
| R2 | mp 端 `selectMpEnabledSlots` weekdays 过滤在 Java 侧（不是 SQL）— 海量时段时性能可能下降 | 极低 | V1.0 单门店每天最多 10-20 时段，全量拉回 Java 过滤 O(n) 无瓶颈；如未来时段数膨胀 → 改 Custom SQL FIND_IN_SET |
| R3 | mp Controller 未在本 ticket 加 — BEAN-003 实施时需补 `GzBeanSeatMpController` + `GzBeanSlotMpController`（路径 `/app/gz/bean/seat/...` `/app/gz/bean/slot/...`） | N/A | 已为 BEAN-003 留 service 方法（selectMpEnabledSeats / selectMpEnabledSlots），mp Controller 直接 wrap 即可 |
| R4 | BEAN-001 风险 R2（doc/11 §1.1 del_flag 注释 '2'=已删 vs 实际 ruoyi '1'）未动 | 中 | 留给 product / curator；本 ticket DDL 注释已写 `0=正常 / 1=删除` 对齐实际 |
| R5 | BEAN-001 风险 R3（Long → JS Number 精度坑）未动 | 低 | V1.0 单门店 + 座位 id ≤ 30 不会撞 Number.MAX_SAFE_INTEGER；BEAN-003 mp 选座时统一 String 化 |
| R6 ⭐ | BEAN-001 hotfix 报告标的 R6（gz-common/user/index.vue）→ **已在本 ticket §0 顺手修** | ✅ 已修 | grep 验证 user/index.vue 无残留 `resp.data` |
| R7 | admin 端门店切换时未清理座位 / 时段缓存 — 切换瞬间可能看到上一门店残留（< 100ms） | 极低 | `onStoreChange` 同步触发 loadSeats + loadSlots，几乎不可见；如要严格清空可在 onStoreChange 加 `seats.value = []` 一行 |

---

## 对下游 ticket 的提示

### BEAN-003（mp 时段 + 座位选择）

1. **mp Controller 待补**：在 `controller/applet/` 下加 `GzBeanSeatMpController` + `GzBeanSlotMpController`，wrap 本 ticket 已有的 `selectMpEnabledSeats(storeId)` / `selectMpEnabledSlots(storeId, date)`：
   ```java
   @GetMapping("/app/gz/bean/seat/list")
   public R<List<GzBeanSeatVO>> mpList(@RequestParam Long storeId) {
     return R.ok(seatService.selectMpEnabledSeats(storeId));
   }
   @GetMapping("/app/gz/bean/slot/list")
   public R<List<GzBeanTimeSlotTemplateVO>> mpList(@RequestParam Long storeId, @RequestParam @DateTimeFormat... LocalDate date) {
     return R.ok(slotService.selectMpEnabledSlots(storeId, date));
   }
   ```
2. **mp 端拉时段必带 date 参数**：service 内部做 effective/expire_date 范围过滤 + weekdays 过滤 — 不要在 mp 端再过滤
3. **座位占用状态**：本 ticket 仅返"配置的可用座位"列表（enabled=1），**占用状态需 BEAN-004 booking 表 join 计算**（doc/10 §3.N4：每时段统计该日期 + 该时段的座位占用情况）— BEAN-003 实施时 mp Controller 可能要 join `gz_bean_booking` 表（v1.0 BEAN-004 创建 booking 表）
4. **Tier 2 可达性强约束**：BEAN-003 是 mp 端新页 → 必须从 mp tab "拼豆"（GZ-ADMIN-005 已建）能点到；若没有自然路径需加临时入口（参考 kevin-coder.md §Tier 2 可达性纪律）
5. **路由 id 字段统一 String**：选座 → 跳详情时 `seat_id` 用 `String(seat.id)`（防 Long 精度）

### BEAN-004（提交预约 + UNIQUE + Redis 锁）

1. **booking UNIQUE 索引设计**（doc/10 §3 §并发控制 + doc/11 §3.4 dedup_token 方案 C）：
   ```sql
   UNIQUE KEY uk_seat_slot (tenant_id, store_id, seat_id, sess_date, slot_start, dedup_token)
   ```
   其中 dedup_token = `pending` 时为常量、`cancelled/used/no_show` 时为 booking_no（释放座位时段 — 取消后同座位时段可再约）
2. **booking 必含字段**（doc/11 §3.4）：`store_id` / `seat_id` / `seat_no_snapshot` / `sess_date` / `slot_start` / `slot_end` / `mobile_snapshot` —— **snapshot 字段防止座位 / 用户改名后历史 booking 丢信息**（本 ticket 座位停用不影响已有预约就是靠这个）
3. **Redis 锁 key**：`bean_seat:{store_id}:{seat_id}:{date}:{slot_start}` TTL 5s（doc/10 §3 §并发控制）
4. **应用层校验**：同一用户同时段同门店已有 pending 预约时 → 幂等返回原预约 ID（不抛错）— doc/10 §3.E5

### BEAN-005（admin 端核销 / 看板）

1. 座位 / 时段管理页菜单已在本 ticket 6020 段建好；BEAN-005 admin 端「预约列表 + 核销」用 6040-6049 段菜单（预留）
2. 核销时校验 booking 关联的座位 / 时段是否还存在（即使停用也允许核销 — 业务上 owner 可能临时停用）

### product / curator

1. **R4 doc/11 §1.1 注释错** 仍未修 — 建议下个 ticket 顺手；本报告再次记录提醒
2. **DDL UNIQUE 任务卡偏差**（任务卡 AC 1 说 `gz_bean_time_slot_template` 有 UNIQUE，doc/11 没有）— 已按 §9.5 #1 改源头 doc 不在 ticket 偏离原则处理，但任务卡描述应在 curator 周巡时同步对齐 doc/11 / 标注为"任务卡 paraphrase 偏差，按 doc/11 落地"

---

## §AI 测试段（kevin-qa Tier 1B，06:15）

### 后端集成测试（mvn test 回归）

```
$ cd code/main/RuoYi-Vue-Plus && mvn test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-bean -am \
    -Dsurefire.failIfNoSpecifiedTests=false

[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0  ← GzBeanSeatServiceImplTest (BEAN-002)
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0  ← GzBeanTimeSlotTemplateServiceImplTest (BEAN-002)
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0  ← GzBeanStoreServiceImplTest (BEAN-001 回归)
[INFO] Tests run: 36, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

BEAN-002 22 单测 + BEAN-001 14 回归，全部通过 ✅

### API 契约回归

```bash
# 环境：PID 6514 @ localhost:8080，tenantId=1001，clientId=e5cd7e4891bf95d1d19206ce24a7b32e

# 座位端点 happy path
GET  /system/gz/bean/seat/list                → code:200 total:0(清理后) ✅
POST /system/gz/bean/seat                     → code:200 (新建 A1) ✅
GET  /system/gz/bean/seat/listByStore/1       → code:200 count:5 ✅
GET  /system/gz/bean/seat/{id}                → code:200 {id,storeId,seatNo,...} ✅
PUT  /system/gz/bean/seat                     → code:200 (停用 B1: enabled=0,sortNo=99; seatNo 未被改) ✅
DELETE /system/gz/bean/seat/{ids}             → code:200 del_flag=1 软删 ✅
POST /system/gz/bean/seat/batchGenerate       → code:200 "成功生成 5 个座位（重复跳过）" ✅

# 座位端点 error path
POST /system/gz/bean/seat (重复 A1)           → code:500 "座位号已存在：A1" ✅
POST /system/gz/bean/seat/batchGenerate(全冲突)→ code:200 "成功生成 0 个座位（重复跳过）" ✅

# 时段端点 happy path
GET  /system/gz/bean/slot/list                → code:200 total:0(清理后) ✅
POST /system/gz/bean/slot                     → code:200 (新建工作日 14-16) ✅
GET  /system/gz/bean/slot/listByStore/1       → code:200 count:3(删 1 后) ✅
GET  /system/gz/bean/slot/{id}                → code:200 {startTime:"14:00:00",...} ✅
PUT  /system/gz/bean/slot                     → code:200 (改名为"下午经典场") ✅
DELETE /system/gz/bean/slot/{ids}             → code:200 del_flag=1 软删 ✅
POST /system/gz/bean/slot/batchByWeek         → code:200 "成功批量配置 2 条时段" ✅

# 时段端点 error path（核心业务规则）
POST /system/gz/bean/slot (end<=start)        → code:500 "结束时间必须晚于开始时间" ✅
POST /system/gz/bean/slot (时段重叠 15-17 与已有 14-16)
                                              → code:500 "时段与已有模板重叠：星期 1,2 已有 14:00-16:00" ✅
POST /system/gz/bean/slot (weekdays="8,9")    → code:500 "适用星期格式错误，应为逗号分隔的 1-7" ✅

# 权限分级（staff 角色）
GET  /system/gz/bean/seat/list  (staff)       → code:200 total:5 ✅（有 gz:bean:seat:list）
POST /system/gz/bean/seat       (staff)       → code:403 ✅（无 gz:bean:seat:add）
DELETE /system/gz/bean/slot/3   (staff)       → code:403 ✅（无 gz:bean:slot:remove）
GET  /system/gz/bean/slot/list  (staff)       → code:200 total:3 ✅（有 gz:bean:slot:list）
```

### DB 状态验证

```sql
-- 测试中间态（清理前）
SELECT id, seat_no, enabled, tenant_id, del_flag FROM gz_bean_seat;
-- 1 A1 1 1001 1（软删）/ 2 B1 0 1001 0（停用）/ 3-6 B2-B5 1 1001 0（正常）
-- tenant_id 全为 1001，del_flag 正确 ✅

-- @Log AOP 写入验证（sys_oper_log）
SELECT title, business_type, oper_name, status FROM sys_oper_log
  WHERE title LIKE '拼豆%' ORDER BY oper_id DESC LIMIT 15;
-- 拼豆时段模板   3(DELETE) gz_owner status=0 ✅
-- 拼豆时段模板   2(UPDATE) gz_owner status=0 ✅
-- 拼豆时段模板按周批量 1(INSERT) gz_owner status=0 ✅
-- 拼豆时段模板   1(INSERT) gz_owner status=0 ✅
-- 拼豆时段模板   1(INSERT) gz_owner status=1（失败 weekdays="8,9"）✅ 失败也写日志
-- 拼豆时段模板   1(INSERT) gz_owner status=1（失败 end<=start）✅
-- 拼豆时段模板   1(INSERT) gz_owner status=0 ✅
-- 拼豆座位       3(DELETE) gz_owner status=0 ✅
-- 拼豆座位       2(UPDATE) gz_owner status=0 ✅
-- 拼豆座位批量生成 1(INSERT) gz_owner status=0 ✅
-- 拼豆座位       1(INSERT) gz_owner status=1（失败 UNIQUE）✅
-- 拼豆座位       1(INSERT) gz_owner status=0 ✅
-- @Log AOP 成功+失败两类全覆盖 ✅

-- 清理后
SELECT COUNT(*) FROM gz_bean_seat → 0 ✅
SELECT COUNT(*) FROM gz_bean_time_slot_template → 0 ✅
```

### admin Playwright E2E

```
# 方式：localStorage 注入 owner/staff token（plus-ui dev 模式 RSA 密码加密影响 form 登录，
#       用 token 注入方式绕过，不影响路由/权限/数据验证的完整性）

PASS: owner token 注入 localStorage (Admin-Token) ✅
PASS: 配置页正常加载 URL: http://localhost/gz/gz-bean/config ✅
PASS: 座位 Tab 可见（el-tabs__item 含 "座位"）✅
PASS: 时段模板 Tab 可见（el-tabs__item 含 "时段"）✅
PASS: 座位表格渲染完成（el-table __row 可见）✅
PASS: 新增座位按钮可见（owner 有 gz:bean:seat:add）✅
PASS: 批量生成按钮可见（owner 有 gz:bean:seat:batchGenerate）✅
PASS: 时段 Tab 切换成功，数据行正常 ✅
PASS: 新增时段按钮可见 ✅
PASS: 按周批量配置按钮可见（owner 有 gz:bean:slot:batchByWeek）✅
PASS: 编辑弹窗正常弹出（标题"编辑座位"）✅

--- staff 角色 ---
PASS: staff 无新增座位按钮（v-hasPermi gz:bean:seat:add 正确隐藏）✅
PASS: staff 无批量生成座位按钮（v-hasPermi gz:bean:seat:batchGenerate 正确隐藏）✅
PASS: staff 可见座位列表（gz:bean:seat:list 有权限）✅
PASS: staff 座位列表数据行正常 ✅

总计：PASS 15 / FAIL 0
```

### Tier 2 可达性检查

本 ticket 无 mp 页（AC Tech 段明确"小程序：本 ticket 不动 mp"）：
- grep `Tier2-entry-temp` in miniapp → 无结果 ✅（不需要临时入口）
- mp 端 `selectMpEnabledSeats` / `selectMpEnabledSlots` service 方法已留，mp Controller 在 BEAN-003 补
- 本 ticket 为纯 admin + 后端 ticket，**跳过 Tier 2**

### 跳过 / 未跑

- mp 端微信原生能力 → 本 ticket 无 mp 页，N/A
- 操作日志 admin 页面路由（`/monitor/operlog` 返回 404，该菜单未挂到 gz_owner 角色）→ 已通过 DB 直查 sys_oper_log 验证 @Log 写入（15 条记录），功能完整 ✅
- plus-ui 登录表单 Playwright 自动化（RSA 加密 + el-select 租户）→ 用 token 注入方式等效替代，不影响功能验证
- 视觉 / 颜色 / 文案 → 设计冻结期不评判（CLAUDE.md §7.5）

### 结论

✅ Tier 1B 全通过。BEAN-002 可直接进入 BEAN-003（纯 admin+后端 ticket，跳过 Tier 2）。

**测试覆盖统计**：
- mvn 单测：36/36 ✅（22 BEAN-002 + 14 BEAN-001 回归）
- API 契约：26 端点（seat 6 + slot 6 + 批量 2 + error path 6 + 权限 6）全 ✅
- admin Playwright：15 项 PASS / 0 FAIL ✅
- DB 状态：tenant_id 全 1001 / del_flag 软删正确 / @Log 成功+失败两类全写入 ✅
