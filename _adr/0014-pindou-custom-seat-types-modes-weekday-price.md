# ADR-0014 拼豆座位类型「去字典化自定义 + 整桌/按座双模式 + 按星期价格覆盖」

- 日期：2026-06-24
- 状态：Accepted
- 决策人：Kevin（甲方运营诉求；主线程评估 + 落地）
- 关联 ticket：GZ-BEAN-018（DDL + 迁移）/ 019（后端双模式配额 + 周价格）/ 020（admin 自定义类型 + 按星期营业与价格页）/ 021（mp 双模式下单 + 周价格展示）
- 依赖：ADR-0008（座位类型配额模型，本 ADR 取代其「字典化类型」段）/ ADR-0011（1h 区间连续多选，本 ADR 取代其「配额分母单一为 quantity」段，沿用一行存区间 + 逐格 FOR UPDATE + 可约/已满铁律）/ ADR-0007（付费双状态机，不动）

---

## Context

ADR-0008 + ADR-0011 落地后的拼豆模型：座位类型走系统字典 `gz_bean_seat_type`（`single`/`double`/`quad` 写死可扩展），每门店每类型一行 `gz_bean_seat_type_config`（`quantity` 每格配额 + `price_cent` 单一单价），一笔预约 = 1 类型 + 1 个连续 1h 区间，金额 = 单价 × 小时数，防超卖逐格 `COUNT(区间重叠活跃) FOR UPDATE` vs `quantity`，mp 只显「可约/已满」。

甲方提出四点运营诉求，现模型无法表达：

1. **按星期定价**：同一座位类型在一周不同日（如周末）要能配不同单价；现 `price_cent` 是单一固定价。
2. **按星期时段**：一周不同日要能配不同营业/预约时段。（`gz_bean_time_slot_template` 已有 `weekdays` 字段，底层已支持；缺的是 admin 按星期分组的配置体验。）
3. **整桌 vs 按座两种订法**：
   - **双人桌**只能**整桌订**（不可只订其中一个座，强制成对占用）。
   - **四人桌**可以**只订一个位子**（拼桌共享，4 个陌生人各订 1 座）。
   现模型只有「整单位」一种订法（选某类型 = 占该类型 1 个配额），无法区分「整桌」与「按座」。
4. **类型可自定义增删**：座位类型不应写死在字典里，门店应能动态新增类型并自定义显示名（如「靠窗单人位」「四人共享桌」「包间」）。

四点中第 1/4 改的是「类型定义与定价的数据模型」，第 3 改的是「配额计数的分母与下单单位」，第 2 主要是 admin UI（底层已支持）。本 ADR 把四点整合为对 `gz_bean_seat_type_config` 的一次升级 + 一张新价格覆盖表 + booking 引用方式调整，**不动 ADR-0011 的区间/逐格/铁律骨架**。

核心设计问题：**(1) 类型怎么去字典化又保持 booking 引用稳定？(2) 整桌/按座如何用最小改动统一进逐格配额计数？(3) 按星期价格放哪张表、怎么回退基础价？**

---

## Decision

### 1. 去字典化：`gz_bean_seat_type_config` 升级为门店自定义「桌型/座位类型」定义表

`gz_bean_seat_type_config` 从「字典枚举的配额行」升级为**门店自己定义的座位类型主数据**。

新增列：

| 列 | 类型 | 含义 |
|---|---|---|
| `name` | VARCHAR(32) NOT NULL | 自定义显示名（「靠窗单人位」「双人卡座」「四人共享桌」），**取代字典 `gz_bean_seat_type` 的 label**。mp 类型卡 + admin 列表 + booking 名快照都用它 |
| `book_mode` | VARCHAR(8) NOT NULL DEFAULT `'whole'` | 订法：`whole`（整桌订，不可拆座）/ `seat`（按座订，可拼桌） |
| `capacity` | INT NOT NULL DEFAULT 1 | 每张桌的座位数（单人=1 / 双人=2 / 四人=4）；`seat` 模式下与 `quantity` 相乘得总座数 |

保留/复用列：`quantity`（语义见 §2）、`price_cent`（**基础价**，语义见 §3）、`enabled`、`sort_no`。

- `seat_type` 列**保留作门店内稳定 code**（不再受字典约束）：旧行保持 `single`/`double`/`quad`；新行由后端在创建时自动生成门店内唯一短码（如 `st<id>` 或自增序号派生），admin 表单**不暴露此列**（admin 只填 `name` + `book_mode` + `capacity` + `quantity` + `price_cent`）。它的作用仅剩旧数据兼容与历史 booking 反查。
- 唯一约束调整：保留 `UNIQUE(tenant_id, store_id, seat_type)`（code 唯一）；**新增 `UNIQUE(tenant_id, store_id, name)`**（防同店重名）。
- 字典 `gz_bean_seat_type` **退役**：sys_dict 记录保留不删（旧 booking 翻译兜底 + destructive 红线），但新类型不再写字典、admin 不再从字典选类型。座位类型的真源从「字典 + config 行」收敛为「config 行自身」。

### 2. 整桌/按座双模式：配额分母按 `book_mode` 取值，每单恒占 1 个单位

`quantity` 语义保持「**该类型每个 1h 格的物理单位数**」=**桌/单位数量**（不是座数）。每格可订总量按模式推导：

```
slotCapacity(type, 1h格) =
    book_mode = 'seat'  → quantity × capacity      // 按座：总座数
    book_mode = 'whole' → quantity                 // 整桌：桌数
```

**关键简化（每单恒占 1）**：一笔预约对它覆盖的每个 1h 格恒占用 **1 个该模式单位**——
- `whole` 整桌单：占 1 张桌（占 `quantity` 分母里的 1）。
- `seat` 按座单：占 1 个座（占 `quantity × capacity` 分母里的 1）。**一笔按座单只订 1 座**（甲方定：按座类型一单 1 座，多人多次下单；不引入一单多座的座数选择器，故无需 `book_qty` 列，「可约/已满」布尔铁律对两模式都完整保留、不泄漏余量数字）。

防超卖沿用 ADR-0011 §3 的逐格 `FOR UPDATE`，**仅改两点**：
1. **计数维度从字符串 `seat_type` 改为 `seat_type_config_id`**（直接对配置行计数，§4 booking 引用调整后成立）。
2. **比对的分母从 `quantity` 改为上面的 `slotCapacity`**（按 `book_mode` 取 `quantity` 或 `quantity × capacity`）。

逐格计数 SQL（取代 doc/11 §3.6 现版）：
```sql
SELECT COUNT(*) FROM gz_bean_booking
 WHERE store_id=? AND seat_type_config_id=? AND sess_date=?
   AND slot_start <= gi AND slot_end > gi             -- 区间重叠：覆盖 gi 这格
   AND status='pending' AND pay_status IN('paying','paid') AND del_flag='0'
 FOR UPDATE;
-- 任一格 COUNT >= slotCapacity(config) → 整笔回滚拒单（业务码 4011 QUOTA_FULL，无部分成交）
```

> **整桌为何不需要「成对/成组」特判**：整桌单本就是「一单占 1 张桌」，与原模型同构（原模型每单占 1 个 quantity 名额）。所谓「双人桌不可拆座」= 这个类型是 `whole` 模式、根本不提供按座入口，物理上无法只订半张桌，无需额外约束。按座共享（四人桌拼桌）= `seat` 模式、分母放大到总座数、每单占 1 座，也不需要把 4 个座绑定到同一张物理桌（沿用 ADR-0008「无具体座位、纯容量池」哲学，店员现场安排落座）。

### 3. 按星期价格覆盖：新增 `gz_bean_seat_type_price`，稀疏覆盖 + 回退基础价

新建 `gz_bean_seat_type_price`（每「类型 × 星期」最多一行覆盖价，DDL 走 Flyway，强约束 #2/#3）：

| 列 | 类型 | 说明 |
|---|---|---|
| `seat_type_config_id` | BIGINT UNSIGNED NOT NULL | FK → `gz_bean_seat_type_config.id` |
| `weekday` | TINYINT NOT NULL | ISO 8601 星期（1=Mon … 7=Sun） |
| `price_cent` | BIGINT NOT NULL | 该类型该星期的覆盖单价（分）；语义随 `book_mode`：`whole`=整桌/小时，`seat`=每座/小时 |
| — | — | `UNIQUE(tenant_id, seat_type_config_id, weekday)`（强约束 #3 唯一约束含 tenant_id）；IDX `(tenant_id, seat_type_config_id)` |

- **稀疏覆盖**：只对要改的星期插行，没插行的星期下单时回退 `gz_bean_seat_type_config.price_cent` 基础价。
- **生效单价 lookup**：下单 / 余量接口对某 `sess_date`，取其星期 `w`，
  ```
  effectivePrice(config, w) = gz_bean_seat_type_price[config_id, w]?.price_cent ?? config.price_cent
  ```
- **计价**：`amount_cent = effectivePrice(config, weekday(sess_date)) × N`（N = 连续小时数 = 区间格数）。一行区间在同一天 = 同一星期，单价查一次即可，无跨星期歧义。每单恒占 1 单位，故 `seat` 模式不乘座数（每座价 × 小时数即整单价）。
- **节假日特价**：无独立日期维度（甲方定：YAGNI）。节假日临时改对应星期的覆盖价、过后改回，靠「动态可调」覆盖。

### 4. 按星期时段：`gz_bean_time_slot_template` schema 不动，admin UI 改按星期分组

- `gz_bean_time_slot_template.weekdays`（逗号分隔 1-7）**已支持按星期配不同营业窗口**，本 ADR **不改该表 schema**。
- 改的是 admin 配置体验：见 §5「按星期营业与价格」页，把时段按星期分组展示/编辑，让甲方直观看到「周一这些窗口、周六那些窗口」。
- 系统按 1h 切格、午休多窗口断档、整点边界校验等 ADR-0011 §1 口径**全部不变**。

### 5. booking 引用调整：加 `seat_type_config_id`，计数/计价改走配置行

`gz_bean_booking` 新增列：

| 列 | 类型 | 说明 |
|---|---|---|
| `seat_type_config_id` | BIGINT UNSIGNED NOT NULL（新单）| FK → `gz_bean_seat_type_config.id`；**逐格防超卖计数维度**（取代字符串 `seat_type`）；计价/容量从该行取 `book_mode`/`capacity`/`quantity`/价 |
| `book_mode_snapshot` | VARCHAR(8) NOT NULL DEFAULT `'whole'` | 下单时 `book_mode` 快照（历史显示「整桌/按座」，防 config 后续改模式丢信息）|

- 保留 `seat_type`（写入 config 的 code，旧索引/兼容用）+ `seat_type_snapshot`（**写入 config 的 `name`**，显示快照）。**无 `book_qty` 列**（每单恒 1）。
- 新索引：`idx_gz_bean_booking_overlap` 的计数维度列从 `seat_type` 换为 `seat_type_config_id`，即 `(tenant_id, store_id, seat_type_config_id, sess_date, slot_start, slot_end)`（新建更大时间戳迁移加新索引；旧 `seat_type` 索引保留不删）。
- **旧数据迁移**：迁移脚本按旧 `gz_bean_booking.seat_type`（single/double/quad）匹配同 `store_id` 的 `gz_bean_seat_type_config` 行回填 `seat_type_config_id`；`book_mode_snapshot` 回填该 config 当前 `book_mode`（旧单皆退化为 `whole`）。匹配不到的历史单（理论无）置 NULL 并记日志，不阻塞。

### 6. mp 下单流程

- `whole` 类型：选类型 → 选连续时段 → 订整桌（**ADR-0011 现流程不变**）。
- `seat` 类型：选类型 → 选连续时段 → 订 1 座（一单 1 座；类型卡可标注「拼桌·按座」让用户知情可能与陌生人共桌）。
- 余量接口 `GzBeanTypeSlotAvailabilityVO`：`name` 改用 config.`name`；新增 `bookMode` 字段（mp 据此显示「整桌/按座」标签）；`unitPriceCent` 改为 `effectivePrice(config, 该日星期)`（按星期生效价）。**仍只下发布尔 `full`，不下发余量数字**（铁律不变，每单恒占 1 不破铁律）。

---

## 取代关系（明确标注被推翻的具体段落）

本 ADR 修订 ADR-0008 与 ADR-0011 中关于「座位类型字典化」与「配额分母单一为 quantity / 计数维度为字符串 seat_type」的部分；两者其余结论继续有效。

**取代 ADR-0008（座位类型配额模型）：**
- §Decision 2 / §Rationale「`seat_type` 走字典 `gz_bean_seat_type`」「字典化座位类型可扩展（加字典项 + 一行 config）」→ 改为：座位类型 = 门店自定义 config 行（`name` 自定义、`id` 为身份、去字典），字典 `gz_bean_seat_type` 退役（保留不删）。新增 `book_mode` / `capacity` / 重名唯一约束（本 ADR §1）。
- **不变**：废弃 `gz_bean_seat` 用于预约（保留不 DROP）、配置表 store × 类型 → quantity + price_cent + enabled、改现有表而非全新表、旧 booking 原地迁移——沿用。

**取代 ADR-0011（1h 区间连续多选）：**
- §3「逐格 `FOR UPDATE` 比对 `quantity`」「计数维度 `seat_type` 字符串」→ 改为：分母按 `book_mode` 取 `quantity`（整桌）或 `quantity × capacity`（按座）；计数维度改 `seat_type_config_id`（本 ADR §2/§5）。
- §4 计费「amount = price_cent × 小时数」→ 价改为**按星期生效价** `effectivePrice(config, weekday)`（基础价 + 星期覆盖，本 ADR §3）；乘法口径（× 连续小时数、每单恒 1 单位不乘座数）不变。
- **不变**：一行存区间、复用 slot_start/slot_end、逐格区间重叠计数 + 悲观锁 + 固定加锁顺序、单码/单支付/整段取消、`status` × `pay_status` 双状态机、mp「可约/已满」去余量数字铁律、整点窗口 1h 切格、午休多窗口断档——全部沿用。

---

## Rationale

- **去字典 = 类型即数据**：拼豆店的「桌型」是门店运营对象（会增删改名），本就该是 admin 维护的业务数据行，而非系统字典。config 行做身份（`id`）+ booking 引用 `seat_type_config_id`，类型增删改名不影响历史单（名走快照）。
- **双模式 = 一个枚举 + 分母切换，零新计数路径**：整桌/按座的差异收敛为「分母取 quantity 还是 quantity×capacity」一处；每单恒占 1 单位让 `COUNT+1` 校验与「可约/已满」布尔铁律原样复用，不引入座数列、不破铁律、不碰 ADR-0011 区间骨架。「双人桌不可拆」靠 `whole` 模式不提供按座入口天然成立，无需成组约束。
- **按星期价 = 稀疏覆盖 + 基础价回退**：独立覆盖表稀疏存只改的星期，没改的回退基础价；一行区间限定单日 = 单星期，单价查一次，计价口径最小改动（只换 price 取值来源）。节假日用「改星期价过后调回」覆盖，省掉日期维度（YAGNI）。
- **时段按星期零 schema 改动**：`weekdays` 已支持，缺的是 admin 体验；按星期分组的「营业与价格」页把价格 + 时段两轴统一呈现，满足甲方「整体配置」诉求，底层仍是两张干净的表。
- **沿用 ADR-0011 大半结论 = 改动面收窄**：区间/逐格/铁律/双状态机/迁移全不动，只改「类型定义去字典 + 配额分母 + 计数维度 + 价格来源」四处。

---

## Consequences

- ✅ 门店可自定义增删座位类型、自定义显示名，支持「整桌订（双人桌）」与「按座拼桌（四人桌）」两种订法。
- ✅ 单价支持按星期覆盖（基础价 + 周覆盖），节假日靠动态改星期价覆盖。
- ✅ admin「按星期营业与价格」页把时段（已支持）+ 周价格（新增）统一配置。
- ✅ 防超卖沿用逐格悲观锁，仅换计数维度（config_id）+ 分母（按模式），「可约/已满」铁律与区间骨架不变。
- ⚠️ **DDL 改动（GZ-BEAN-018，Flyway，时间戳 > `V202606300003`，建议从 `V202607010001` 起）**：
  - `ALTER gz_bean_seat_type_config` 加 `name` / `book_mode` / `capacity` + 加 `UNIQUE(tenant_id, store_id, name)`；旧三行回填 `name`（单人/双人/四人桌）+ `book_mode`（按现实：double=whole / quad=seat / single=whole 或 seat，**seed 时按甲方意图设**）+ `capacity`（1/2/4）。
  - 新建 `gz_bean_seat_type_price`。
  - `ALTER gz_bean_booking` 加 `seat_type_config_id` / `book_mode_snapshot` + 新 overlap 索引（含 `seat_type_config_id`）；回填旧单 `seat_type_config_id`。
- ⚠️ **后端改写（GZ-BEAN-019）**：`GzBeanSeatTypeConfig` 实体 + CRUD 去字典约束（admin 自由新建）；新增 `GzBeanSeatTypePrice` 实体/mapper/service；逐格计数查询 `countActiveBy*` 改按 `seat_type_config_id` + 分母按 `book_mode`；`submitPaid` 计价改 `effectivePrice(config, weekday)`；`selectTypeSlotAvailability` VO 加 `bookMode`、`unitPriceCent` 取生效价、`name` 取 config.name；`GzBeanPaidBookingSubmitBo` 入参由 `seatType` 改 `seatTypeConfigId`。
- ⚠️ **admin 改造（GZ-BEAN-020）**：①「座位类型配额配置」页改为自定义类型 CRUD（表单加 `name` / `book_mode` 下拉 / `capacity` / `quantity` / `price_cent`，去字典选择器）；② 新增/改造「按星期 营业与价格」页（周一-周日分组：每星期编辑营业窗口 = time_slot_template 的 weekdays 过滤 + 编辑各类型该星期覆盖价 = seat_type_price）。
- ⚠️ **mp 改造（GZ-BEAN-021）**：类型卡用 config.`name` + 显示「整桌/按座」标签；`seat` 类型下单订 1 座；单价显示按星期生效价；`whole` 流程不变。
- ⚠️ **≥80% 配额并发单测（CLAUDE.md §8.1 红线）必须新增覆盖**：`whole` 类型抢同格最后 1 桌只成一笔；`seat` 类型分母 = quantity×capacity，订满总座数后第 N+1 单被拒；同店两类型互不串配额（按 config_id 隔离）；按星期单价 lookup（命中覆盖 / 回退基础价）。
- ⚠️ **doc/11 §3.2/§3.4/§3.5/§3.6 + 附录 A.14（座位类型字典退役标注）需回写**（实施时随 ticket 改字段权威表，CLAUDE.md §9.5 改 doc 优先）。

---

## 待澄清（实施前确认，低风险默认值已给）

- **F14.1 旧三类型迁移的 `book_mode`/`capacity` seed 值**：默认 单人=`whole`/cap 1、双人=`whole`/cap 2、四人桌=`seat`/cap 4（对齐甲方「双人整桌、四人可单座」）。若甲方要单人也按座或四人也整桌，迁移 seed 调对应值即可。
- **F14.2 `seat_type` code 新行生成规则**：默认后端创建 config 时生成门店内唯一短码（不暴露 admin）。实施按最简：`st` + 自增 id 或库内序号。
