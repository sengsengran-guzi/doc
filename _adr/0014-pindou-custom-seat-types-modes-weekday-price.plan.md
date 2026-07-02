# ADR-0014 拼豆自定义桌型 + 整桌/按座 + 按星期价格 — 实施计划

> **For agentic workers:** 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐 ticket 执行。步骤用 `- [ ]` 勾选跟踪。本计划是 ADR-0014 的落地，4 个 ticket（GZ-BEAN-018/019/020/021）。

**Goal:** 拼豆座位类型去字典化（门店自定义增删 + 自定义名）、支持整桌(whole)/按座(seat)两种订法、单价支持按星期覆盖；时段按星期改 admin 体验。

**Architecture:** 在现有 `gz_bean_seat_type_config` 上加列（name/book_mode/capacity）使其成为自定义类型主数据；新建 `gz_bean_seat_type_price`（类型×星期→覆盖价，稀疏，回退基础价）；`gz_bean_booking` 加 `seat_type_config_id` FK 作配额计数维度。沿用 ADR-0011 一行存区间 + 逐格 `FOR UPDATE`，仅改「计数维度 seat_type→config_id」「分母按 book_mode 取 quantity 或 quantity×capacity」「价取按星期生效价」三处。

**Tech Stack:** RuoYi-Vue-Plus 5.5（Spring Boot 3 / MyBatis-Plus / Flyway）· plus-ui（Vue3 + Element Plus）· miniapp（uni-app Vue3 + wot-design-uni）· JUnit5 + vitest + uni-automator E2E。

## Global Constraints（每个 task 隐含遵守，CLAUDE.md §6/§7）

- 业务表 `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`；INSERT 不显式赋（自动填充）；UNIQUE 必含 tenant_id。
- 包名 `org.dromara.gz.bean.*`；不动 ruoyi 自带模块。
- DDL 命名 `V<yyyyMMddHHmm>__<TICKET>-<desc>.sql`，放 `ruoyi-admin/src/main/resources/db/migration/`，**时间戳 > `V202606300003`，本批从 `V202607010001` 起递增**；已应用迁移不可改。
- 不写 `any`(TS) / 不吞异常 / 不留无说明 TODO；可见字符串走 i18n（zh_CN/en_US）。
- 改 `ruoyi-gz-*` 模块代码后必须 **`mvn clean install`**（非 clean 不重打 jar、不重编译测试），再重启 `spring-boot:run -pl ruoyi-admin`。
- mp 业务组件包一层 `src/components/biz/`（Biz 前缀），页面不直接撒 `<wd-*>`；走 `var(--c-*)` token（注：mp 已换清爽风皮，c-tokens.scss 是真源）。
- 测试分工：kevin-coder 写单测（happy + 2-3 error path）+ Tier 1A 机械自测；Tier 1B（admin Playwright + mp 模拟器 E2E）由主线程统一派 kevin-qa 串行跑。
- 软删 `del_flag`：本项目 `logicDeleteValue=1`（entity `@TableLogic`），但**历史 SQL/DDL 沿用 `DEFAULT '0'`**；回填 UPDATE 用 `del_flag='0'` 过滤。

---

## File Structure（改动地图）

**后端 `ruoyi-modules/ruoyi-gz-bean/.../gz/bean/`：**
- `domain/entity/GzBeanSeatTypeConfig.java` — 加 name/bookMode/capacity
- `domain/entity/GzBeanBooking.java` — 加 seatTypeConfigId/bookModeSnapshot
- `domain/entity/GzBeanSeatTypePrice.java` — **新建**
- `mapper/GzBeanSeatTypePriceMapper.java` — **新建**
- `domain/bo/GzBeanSeatTypeConfigBo.java` — 加 name/bookMode/capacity（去字典校验）
- `domain/bo/GzBeanSeatTypePriceBo.java` — **新建**（批量按星期存价）
- `domain/bo/GzBeanPaidBookingSubmitBo.java` — `seatType` → `seatTypeConfigId`
- `domain/vo/GzBeanSeatTypeConfigVO.java` — 加 name/bookMode/capacity
- `domain/vo/GzBeanTypeSlotAvailabilityVO.java` — 加 bookMode；name/unitPriceCent 取 config + 生效价
- `mapper/GzBeanBookingMapper.java` — 3 个 count 方法 `seatType`→`seatTypeConfigId`
- `service/IGzBeanSeatTypeConfigService.java` + impl — CRUD 去字典 + 周价格读写
- `service/IGzBeanBookingService.java` + impl（`GzBeanBookingServiceImpl`）— submitPaid / selectTypeSlotAvailability 改写
- `controller/GzBeanSeatTypeConfigController.java` — 加周价格 get/save 端点

**DDL `ruoyi-admin/.../db/migration/`：** 3 个新迁移（018-a/b/c）

**Admin `plus-ui/src/views/gz-bean/`：**
- `seat-type-config/index.vue` — 表单去字典 + 加 name/book_mode/capacity
- `weekly-schedule/index.vue` — **新建**「按星期 营业与价格」页
- `plus-ui/src/api/gz-bean/seatTypeConfig.ts`（或现有 api 文件）— 加周价格 api
- i18n `zh_CN.ts` / `en_US.ts`

**mp `miniapp/src/`：**
- `pages/bean/index.vue` — 类型卡用 name + book_mode 标签；提交用 seatTypeConfigId
- `api/bean.ts`（或现有）— submit 入参字段调整
- `test/e2e/flows/bean*.mjs` — flow 适配

---

## Task 拆分与依赖

```
GZ-BEAN-018 (DDL+迁移)  ──>  GZ-BEAN-019 (后端)  ──┬──>  GZ-BEAN-020 (admin)
                                                    └──>  GZ-BEAN-021 (mp)
```
020 与 021 在 019 完成后可并行。

---

### Task 1 — GZ-BEAN-018：DDL + 数据迁移

**Files:**
- Create: `ruoyi-admin/src/main/resources/db/migration/V202607010001__GZ-BEAN-018-seat-type-config-custom-modes.sql`
- Create: `ruoyi-admin/src/main/resources/db/migration/V202607010002__GZ-BEAN-018-create-seat-type-price.sql`
- Create: `ruoyi-admin/src/main/resources/db/migration/V202607010003__GZ-BEAN-018-booking-config-id-overlap-index.sql`

**Interfaces — Produces:** 表结构：`gz_bean_seat_type_config` 加 `name/book_mode/capacity` + `UNIQUE(tenant_id,store_id,name)`；新表 `gz_bean_seat_type_price`；`gz_bean_booking` 加 `seat_type_config_id/book_mode_snapshot` + `idx_gz_bean_booking_overlap_cfg`。

- [ ] **Step 1: 写迁移 1（config 升级 + 回填旧三类型）**

```sql
-- V202607010001__GZ-BEAN-018-seat-type-config-custom-modes.sql
SET NAMES utf8mb4;

ALTER TABLE gz_bean_seat_type_config
    ADD COLUMN name      VARCHAR(32) NOT NULL DEFAULT '' COMMENT '自定义显示名（取代字典 label）' AFTER seat_type,
    ADD COLUMN book_mode VARCHAR(8)  NOT NULL DEFAULT 'whole' COMMENT '订法 whole=整桌/seat=按座' AFTER name,
    ADD COLUMN capacity  INT         NOT NULL DEFAULT 1 COMMENT '每桌座位数（seat 模式 quantity*capacity=总座数）' AFTER book_mode;

-- 回填旧三类型（ADR-0014 §1 / 待澄清 F14.1 默认值）
UPDATE gz_bean_seat_type_config SET name='单人',   book_mode='whole', capacity=1 WHERE seat_type='single' AND del_flag='0';
UPDATE gz_bean_seat_type_config SET name='双人',   book_mode='whole', capacity=2 WHERE seat_type='double' AND del_flag='0';
UPDATE gz_bean_seat_type_config SET name='四人桌', book_mode='seat',  capacity=4 WHERE seat_type='quad'   AND del_flag='0';

-- 防同店重名（回填后 name 已就绪）
ALTER TABLE gz_bean_seat_type_config
    ADD UNIQUE KEY uk_gz_bean_stc_name (tenant_id, store_id, name);
```

- [ ] **Step 2: 写迁移 2（新建按星期价格覆盖表）**

```sql
-- V202607010002__GZ-BEAN-018-create-seat-type-price.sql
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS gz_bean_seat_type_price (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT          COMMENT '主键',
    seat_type_config_id BIGINT UNSIGNED NOT NULL                         COMMENT 'FK → gz_bean_seat_type_config.id',
    weekday             TINYINT         NOT NULL                         COMMENT 'ISO 星期 1=Mon..7=Sun',
    price_cent          BIGINT          NOT NULL                         COMMENT '该类型该星期覆盖单价（分）；语义随 book_mode',
    tenant_id           VARCHAR(20)     NOT NULL DEFAULT '1001'          COMMENT '租户 ID',
    create_dept         BIGINT          NULL                             COMMENT '创建部门',
    create_by           BIGINT          NULL                             COMMENT '创建者',
    create_time         DATETIME        NULL                             COMMENT '创建时间',
    update_by           BIGINT          NULL                             COMMENT '更新者',
    update_time         DATETIME        NULL                             COMMENT '更新时间',
    del_flag            CHAR(1)         NOT NULL DEFAULT '0'             COMMENT '软删 0=正常 / 1=删除',
    remark              VARCHAR(500)    NULL                             COMMENT '备注',
    PRIMARY KEY (id),
    UNIQUE KEY uk_gz_bean_stp (tenant_id, seat_type_config_id, weekday),
    KEY idx_gz_bean_stp_config (tenant_id, seat_type_config_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '拼豆座位类型按星期价格覆盖（doc/11 §3.4b，ADR-0014 §3）';
```

- [ ] **Step 3: 写迁移 3（booking 加列 + 回填 + overlap 索引）**

```sql
-- V202607010003__GZ-BEAN-018-booking-config-id-overlap-index.sql
SET NAMES utf8mb4;

ALTER TABLE gz_bean_booking
    ADD COLUMN seat_type_config_id BIGINT UNSIGNED NULL COMMENT 'FK → gz_bean_seat_type_config.id（V1.2.x 配额计数维度）' AFTER seat_type_snapshot,
    ADD COLUMN book_mode_snapshot  VARCHAR(8) NOT NULL DEFAULT 'whole' COMMENT '下单时订法快照 whole/seat' AFTER seat_type_config_id;

-- 回填历史单：按 store_id + seat_type 匹配 config 行（ADR-0014 §5）
UPDATE gz_bean_booking b
    JOIN gz_bean_seat_type_config c
      ON c.tenant_id = b.tenant_id AND c.store_id = b.store_id AND c.seat_type = b.seat_type AND c.del_flag = '0'
   SET b.seat_type_config_id = c.id,
       b.book_mode_snapshot  = c.book_mode
 WHERE b.seat_type_config_id IS NULL AND b.del_flag = '0';

-- 逐格重叠计数新索引（计数维度改 config_id）
ALTER TABLE gz_bean_booking
    ADD INDEX idx_gz_bean_booking_overlap_cfg (tenant_id, store_id, seat_type_config_id, sess_date, slot_start, slot_end);
```

- [ ] **Step 4: 起后端验证 Flyway 自动跑 + DB 校验**

```bash
cd code/main/RuoYi-Vue-Plus && mvn clean install -DskipTests \
  -pl ruoyi-modules/ruoyi-gz-bean -am
mvn spring-boot:run -pl ruoyi-admin   # 后台起；观察 Flyway migrate 日志无 checksum/语法错
```
DB 校验（dev MySQL 3307，见 memory dev-infra-run-recipe）：
```bash
mysql -h127.0.0.1 -P3307 -uroot -p... ry-vue -e "
  SHOW COLUMNS FROM gz_bean_seat_type_config LIKE 'book_mode';
  SHOW COLUMNS FROM gz_bean_booking LIKE 'seat_type_config_id';
  SELECT seat_type,name,book_mode,capacity FROM gz_bean_seat_type_config;
  SELECT COUNT(*) bk, COUNT(seat_type_config_id) filled FROM gz_bean_booking WHERE del_flag='0';
"
```
Expected: book_mode 列存在；旧 config 行 name/book_mode/capacity 已回填；`filled = bk`（所有历史单回填成功）。

**AC:** 3 迁移 Flyway 自动跑通无报错；旧三类型回填正确；历史 booking 全部回填 `seat_type_config_id`；新索引存在。
**Tier 1A 自测（reports/GZ-BEAN-018.md）:** 贴 Flyway migrate 日志 + 上述 DB 校验 raw output（≥3 block）。
**测试归属:** 纯 DDL，无单测；Tier 1B 不涉及。

---

### Task 2 — GZ-BEAN-019：后端（实体/BO/VO/mapper/service/controller）

**Files:**
- Modify: `domain/entity/GzBeanSeatTypeConfig.java`、`domain/entity/GzBeanBooking.java`
- Create: `domain/entity/GzBeanSeatTypePrice.java`、`mapper/GzBeanSeatTypePriceMapper.java`、`domain/bo/GzBeanSeatTypePriceBo.java`
- Modify: `domain/bo/GzBeanSeatTypeConfigBo.java`、`domain/bo/GzBeanPaidBookingSubmitBo.java`、`domain/vo/GzBeanSeatTypeConfigVO.java`、`domain/vo/GzBeanTypeSlotAvailabilityVO.java`
- Modify: `mapper/GzBeanBookingMapper.java`（3 count 方法）
- Modify: `service/impl/GzBeanSeatTypeConfigServiceImpl.java`、`service/impl/GzBeanBookingServiceImpl.java`、对应 interface
- Modify: `controller/GzBeanSeatTypeConfigController.java`
- Test: `ruoyi-modules/ruoyi-gz-bean/src/test/java/.../GzBeanBookingQuotaTest.java`（新建）

**Interfaces:**
- Consumes（Task 1）：`gz_bean_seat_type_config{name,book_mode,capacity}`、`gz_bean_seat_type_price`、`gz_bean_booking{seat_type_config_id,book_mode_snapshot}`。
- Produces（Task 3/4）：
  - 余量接口 `GET /app/gz/bean/booking/type-slots?storeId&sessDate` → `GzBeanTypeSlotAvailabilityVO{ seatTypeConfigId:Long, seatType:String, name:String, bookMode:String, unitPriceCent:Long, slotStart, slotEnd, full:Boolean, active:Boolean }`
  - 下单 `POST /app/gz/bean/booking/paid-submit` 入参 `GzBeanPaidBookingSubmitBo{ storeId, seatTypeConfigId:Long, sessDate, slotStart, slotEnd, couponId?, dedupClientToken? }`（`seatType` 移除）
  - config CRUD：`GzBeanSeatTypeConfigBo{ id?, storeId, name, bookMode, capacity, quantity, priceCent, enabled, sortNo, remark? }`（无 seatType 入参）
  - 周价格：`GET /gz/bean/seat-type-config/{id}/weekday-prices` → `List<{weekday:Integer, priceCent:Long}>`；`PUT /gz/bean/seat-type-config/{id}/weekday-prices` 入参 `GzBeanSeatTypePriceBo{ configId, items:List<{weekday,priceCent}> }`（覆盖式：传入即 upsert，未传星期视为删除该覆盖→回退基础价）

- [ ] **Step 1: 实体加列**

`GzBeanSeatTypeConfig.java` 在 `seatType` 后加：
```java
/** 自定义显示名（取代字典 label） */
private String name;
/** 订法：whole=整桌 / seat=按座 */
private String bookMode;
/** 每桌座位数（seat 模式 quantity*capacity=总座数） */
private Integer capacity;
```
`GzBeanBooking.java` 加：
```java
/** FK → gz_bean_seat_type_config.id（V1.2.x 配额计数维度） */
private Long seatTypeConfigId;
/** 下单时订法快照 whole/seat */
private String bookModeSnapshot;
```

- [ ] **Step 2: 新建 `GzBeanSeatTypePrice` 实体 + mapper**

```java
@Data @Builder @NoArgsConstructor @AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@TableName("gz_bean_seat_type_price")
public class GzBeanSeatTypePrice extends TenantEntity {
    @Serial private static final long serialVersionUID = 1L;
    @TableId(value = "id", type = IdType.AUTO) private Long id;
    private Long seatTypeConfigId;
    private Integer weekday;          // 1..7
    private Long priceCent;
    private String remark;
    @TableLogic private String delFlag;
}
```
```java
public interface GzBeanSeatTypePriceMapper extends BaseMapperPlus<GzBeanSeatTypePrice, GzBeanSeatTypePrice> {
    @Select("SELECT * FROM gz_bean_seat_type_price WHERE seat_type_config_id = #{configId} AND del_flag='0'")
    List<GzBeanSeatTypePrice> selectByConfig(@Param("configId") Long configId);
}
```
（项目 mapper 基类按现有 `GzBeanSeatTypeConfigMapper` 写法对齐——确认是 `BaseMapperPlus` 还是 `BaseMapper`，照抄同包惯例。）

- [ ] **Step 3: mapper 3 个 count 方法计数维度 `seatType` → `seatTypeConfigId`**

`GzBeanBookingMapper.java`：`countActiveCoveringSlotForUpdate` / `countActiveCoveringSlot` / `countActiveUserOverlap` 的 SQL 把 `seat_type = #{seatType}` 改为 `seat_type_config_id = #{seatTypeConfigId}`，参数同步改名。例（ForUpdate 版）：
```java
@Select("SELECT COUNT(*) FROM gz_bean_booking " +
    "WHERE tenant_id = #{tenantId} AND store_id = #{storeId} AND seat_type_config_id = #{seatTypeConfigId} " +
    "  AND sess_date = #{sessDate} AND slot_start <= #{slot} AND slot_end > #{slot} " +
    "  AND status = 'pending' AND pay_status IN ('paying','paid') AND del_flag = '0' " +
    "FOR UPDATE")
long countActiveCoveringSlotForUpdate(@Param("tenantId") String tenantId,
                                      @Param("storeId") Long storeId,
                                      @Param("seatTypeConfigId") Long seatTypeConfigId,
                                      @Param("sessDate") LocalDate sessDate,
                                      @Param("slot") LocalTime slot);
```

- [ ] **Step 4: BO/VO 改字段**

- `GzBeanPaidBookingSubmitBo`：删 `@NotBlank String seatType`，加 `@NotNull Long seatTypeConfigId`。
- `GzBeanSeatTypeConfigBo`：删 seatType 的字典校验（admin 不传 code），加 `@NotBlank String name`、`@NotBlank String bookMode`（whole/seat，加 `@Pattern` 或枚举校验）、`@NotNull @Min(1) Integer capacity`。
- `GzBeanSeatTypeConfigVO`：加 `name/bookMode/capacity`。
- `GzBeanTypeSlotAvailabilityVO`：加 `Long seatTypeConfigId`、`String bookMode`；`name` 改取 config.name；`unitPriceCent` 改取生效价（Step 6）。mp 提交回传 `seatTypeConfigId`。
- 新建 `GzBeanSeatTypePriceBo`（configId + `List<Item{Integer weekday, Long priceCent}>`，weekday 1-7 校验）。

- [ ] **Step 5: config service CRUD 去字典 + seat_type code 自动生成 + 周价格读写**

`GzBeanSeatTypeConfigServiceImpl`：
- 新增 config 时**自动生成门店内唯一 `seatType` code**（admin 不传）：取该 store 现有 config 数 +1 或时间序，生成如 `st` + 序号；保证 `UNIQUE(tenant,store,seat_type)` 不撞（重试或用 id 回填二次 update 亦可）。`name` 由 admin 传、校验同店不重名（DB uk 兜底 + service 友好报错）。
- 编辑：`name/bookMode/capacity/quantity/priceCent/enabled/sortNo` 可改；`seatType` code 不可改。
- `book_mode` 改动影响余量/计价，无需迁移历史单（历史走 book_mode_snapshot）。
- 周价格读：`selectWeekdayPrices(configId)` → mapper.selectByConfig。
- 周价格存（覆盖式 upsert）：`saveWeekdayPrices(bo)` —— 对传入 items 按 (configId,weekday) upsert；传入集合中**未出现的 weekday 删除其覆盖行**（回退基础价）。事务内做。

- [ ] **Step 6: booking service 改 submitPaid + selectTypeSlotAvailability（核心）**

`GzBeanBookingServiceImpl`，新增私有助手：
```java
// 该类型每 1h 格的配额分母
private long slotCapacity(GzBeanSeatTypeConfig c) {
    return "seat".equals(c.getBookMode())
        ? (long) c.getQuantity() * c.getCapacity()
        : c.getQuantity();
}
// 按星期生效价：覆盖价命中则用，否则回退基础价
private long effectivePrice(GzBeanSeatTypeConfig c, LocalDate sessDate, Map<Integer,Long> overrideByWeekday) {
    int w = sessDate.getDayOfWeek().getValue();   // 1=Mon..7=Sun
    Long ov = overrideByWeekday.get(w);
    return ov != null ? ov : c.getPriceCent();
}
```
`submitPaid(bo, userId)` 改动：
1. 入参由 `seatType` 改 `seatTypeConfigId`；按 id 查 config（校验属本 store + enabled）。
2. 逐格 `countActiveCoveringSlotForUpdate(..., seatTypeConfigId, ...)`，比对 **`slotCapacity(config)`**（不是 quantity），任一格满 → 抛 `QUOTA_FULL`（4011）整笔回滚。
3. 同用户重叠校验 `countActiveUserOverlap(..., seatTypeConfigId, ...)`。
4. 金额 `amountCent = effectivePrice(config, sessDate, prices) × hours`（hours = `ChronoUnit.HOURS.between(slotStart, slotEnd)`），prices 来自 `seatTypePriceMapper.selectByConfig(configId)`。
5. INSERT booking 写 `seatTypeConfigId`、`seatType=config.seatType`、`seatTypeSnapshot=config.name`、`bookModeSnapshot=config.bookMode`。
   > seat 模式每单恒 1 座（不引座数选择），故计数 +1、金额不乘座数——与 whole 同构。

`selectTypeSlotAvailability(storeId, sessDate)` 改动：
- 遍历 store 下 `enabled=1` 的 config（不再按字典）；批量取各 config 的周价格覆盖。
- 每 config × 每 1h 格：`full = countActiveCoveringSlot(..., config.id, ...) >= slotCapacity(config)`。
- VO 填 `seatTypeConfigId / seatType / name=config.name / bookMode / unitPriceCent=effectivePrice(config,sessDate,prices) / slotStart / slotEnd / full / active=true`。

- [ ] **Step 7: controller 加周价格端点**

`GzBeanSeatTypeConfigController`：
```java
@SaCheckPermission("gz:bean:seatTypeConfig:query")
@GetMapping("/{id}/weekday-prices")
public R<List<...>> weekdayPrices(@PathVariable Long id) { ... }

@SaCheckPermission("gz:bean:seatTypeConfig:edit")
@PutMapping("/{id}/weekday-prices")
public R<Void> saveWeekdayPrices(@PathVariable Long id, @RequestBody @Validated GzBeanSeatTypePriceBo bo) { ... }
```

- [ ] **Step 8: 单测（≥80% 覆盖配额/锁 + 周价格）**

`GzBeanBookingQuotaTest`（happy + error path，CLAUDE.md §8.1 红线）：
```
test_whole_mode_quota: book_mode=whole, quantity=2 → 第3单同格被拒(QUOTA_FULL)
test_seat_mode_quota:  book_mode=seat, quantity=2 capacity=4 → 总座8，第9单同格被拒
test_two_types_isolated: 同店两 config，A 满不影响 B（按 config_id 隔离）
test_concurrent_last_unit: 两线程抢同格最后名额只成一笔（逐格 FOR UPDATE）
test_partial_slot_full_rollback: 区间内任一格满 → 整笔回滚
test_weekday_price_hit: sess_date 命中周覆盖 → amount=覆盖价×hours
test_weekday_price_fallback: 未配该星期 → amount=基础价×hours
```

- [ ] **Step 9: Tier 1A 机械自测**

```bash
cd code/main/RuoYi-Vue-Plus
mvn clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-bean -am   # 单测全绿
mvn spring-boot:run -pl ruoyi-admin   # 起服务
# curl 余量接口 + 下单接口（whole / seat 各一），贴 raw output 到 reports/GZ-BEAN-019.md
```

**AC:** config CRUD 去字典可自由增删类型；余量/下单按 config_id 计数、分母按 book_mode、价按星期生效；单测 ≥80% 覆盖配额锁路径全绿；编译 + 启动 + curl 通。
**Tier 1B（kevin-qa）:** 后端集成 + API 契约回归（余量 VO 新字段、submit 入参改 seatTypeConfigId）。

---

### Task 3 — GZ-BEAN-020：Admin（自定义类型 CRUD + 按星期营业与价格页）

**Files:**
- Modify: `plus-ui/src/views/gz-bean/seat-type-config/index.vue`
- Create: `plus-ui/src/views/gz-bean/weekly-schedule/index.vue`
- Modify/Create: `plus-ui/src/api/gz-bean/*.ts`（seatTypeConfig 加 name/bookMode/capacity + 周价格 api；time-slot 复用）
- Modify: `plus-ui/src/lang/package/zh_CN.ts` / `en_US.ts`
- Modify: 菜单迁移（如新增「按星期营业与价格」菜单项，走 Flyway menu seed，GZ-BEAN 6000 段；时间戳接 018 之后）

**Interfaces — Consumes（Task 2）:** config CRUD（无 seatType 入参，加 name/bookMode/capacity）；`GET/PUT /gz/bean/seat-type-config/{id}/weekday-prices`；现有 time-slot CRUD（含 weekdays）。

- [ ] **Step 1: 座位类型配额页去字典 + 加字段**

`seat-type-config/index.vue` 表单：删座位类型字典 `<el-select>`（dict `gz_bean_seat_type`），改为：
- `name` 文本输入（必填，placeholder「如 靠窗单人位 / 双人卡座」）
- `book_mode` 下拉（整桌 whole / 按座拼桌 seat，**前端本地选项不走字典**——用常量；或加最小本地 dict）
- `capacity` 数字（≥1）
- 保留 quantity / price_cent(元↔分换算) / enabled / sort_no / remark
列表列：去 seatType dict-tag，改显示 `name` + book_mode 标签（整桌/按座）+ capacity + quantity + 单价 + 启用 + 排序。

- [ ] **Step 2: 新建「按星期 营业与价格」页**

`weekly-schedule/index.vue`：顶部门店选择器；下面周一~周日 7 个分组（tab 或纵向卡）。每个 weekday 分组：
- **营业窗口**：列出 `time_slot_template` 中 weekdays 命中该天的窗口（start-end），可增删改（复用 time-slot CRUD，weekdays 写单个该天值或多选）。整点校验沿用现有。
- **各类型当天价**：表格 行=该店启用类型(config) 列=该星期覆盖价输入（占位显示基础价，留空=回退基础价）。保存调 `PUT /{id}/weekday-prices`（按 config 逐个 or 汇总）。
> 实现取最简：价格矩阵按「类型行 × 7 天列」一张表也可（与按天分组二选一，择 admin 体验顺手者）。时段编辑复用现有 time-slot 组件。

- [ ] **Step 3: api + i18n**

api 加 `getWeekdayPrices(id)` / `saveWeekdayPrices(id, bo)`；config api dto 去 seatType 加 name/bookMode/capacity。i18n 补所有可见串（zh_CN + en_US，键 `gzBean.*`）。

- [ ] **Step 4: Tier 1A 自检**

```bash
cd code/main/plus-ui && pnpm dev --port 8090   # 起 admin
# 手点：新建一个自定义类型(seat 模式) / 编辑 / 删除；按星期给四人桌周六配特殊价
```
贴截图/操作记录到 reports/GZ-BEAN-020.md。

**AC:** admin 可新增/编辑/删除自定义类型（名/模式/容量/数量/价）；可按星期配营业窗口 + 各类型周覆盖价；保存后 mp 余量接口生效。
**Tier 1B（kevin-qa Playwright）:** 登录(gz_owner) → 座位类型页 CRUD（建 seat 类型）→ 按星期价页配周六价 → 断言保存成功；列表渲染正确。

---

### Task 4 — GZ-BEAN-021：mp（双模式下单 + 周价格展示）

**Files:**
- Modify: `miniapp/src/pages/bean/index.vue`
- Modify: `miniapp/src/api/bean.ts`（或现有 bean api 封装）
- Modify: `miniapp/src/test/e2e/flows/bean*.mjs`

**Interfaces — Consumes（Task 2）:** 余量 VO 加 `seatTypeConfigId/bookMode`，`name=config.name`，`unitPriceCent=`按星期生效价；submit 入参 `seatTypeConfigId`。

- [ ] **Step 1: 类型卡用 name + book_mode 标签**

`bean/index.vue`：类型卡标题用 `item.name`（不再 dict 翻译 seatType）；加小标签：`bookMode==='seat'` → 显「拼桌·按座」，`whole` → 显「整桌」。单价用 `unitPriceCent/100`（已是按星期生效价，无需前端再算）。

- [ ] **Step 2: 提交改 seatTypeConfigId**

下单请求体 `seatType` → `seatTypeConfigId`（取选中类型卡的 `seatTypeConfigId`）。seat 类型流程与 whole 一致（选类型→选连续时段→提交），后端按 1 座/1 桌处理；mp 无座数选择器（每单 1 单位，铁律「可约/已满」不变）。

- [ ] **Step 3: E2E flow 适配 + 构建**

更新 bean flow（reLaunch 到 bean 页 → 断言类型卡渲染 name/标签 → 选时段 → 提交打真后端）。
```bash
cd code/main/miniapp && pnpm build:mp-weixin   # 注意尾部 cli 假挂起，pkill cli -o（memory mp-build-devtools-hang）
```

**AC:**（mp ticket 强约束）
- AC(a) AI 模拟器可达：kevin-qa run.mjs 程序化导航到 bean 页断言类型卡渲染（name + book_mode 标签 + 生效价）。
- AC(b) 真机可达：本 ticket **不碰真机微信原生能力**（下单支付的真机部分另属支付链路，已有人验积压）→ 纯功能页，AI 模拟器 E2E 即终态，无新增临时入口。
**Tier 1B（kevin-qa）:** mp vitest（类型卡渲染/提交体构造）+ 模拟器 E2E（导航 + 渲染 + 提交打后端，whole/seat 各一）。

---

## 收尾（4 ticket 全绿后）

- [ ] doc/11 §3.2/§3.4/§3.5/§3.6 + 附录 A.14 回写（字典退役标注 + 新列 + 双模式分母 + 周价格表 §3.4b + 计数维度 config_id）。
- [ ] `cat D<N>/reports/*.md > summary.md`。

---

## Self-Review（写完计划对照 ADR）

**Spec coverage：** ADR §1 去字典→Task2 Step1/5 + Task3 Step1；§2 双模式分母→Task2 Step6 slotCapacity + Task1 capacity；§3 周价格→Task1 迁移2 + Task2 Step2/5/6 + Task3 Step2；§4 时段按星期→Task3 Step2（无 schema 改）；§5 booking 引用→Task1 迁移3 + Task2 Step1/3/6；§6 mp→Task4。覆盖完整。
**Placeholder：** 无 TBD；count 方法/实体/VO 字段名均给真签名（已对齐现有代码 `countActiveCoveringSlot*` / `GzBeanPaidBookingSubmitBo` / `GzBeanTypeSlotAvailabilityVO`）。
**Type consistency：** 计数维度统一 `seatTypeConfigId:Long`；分母 `slotCapacity(config)`；价 `effectivePrice(config,date,overrides):long`；VO/BO 字段名贯穿一致（seatTypeConfigId/bookMode/name/capacity）。
