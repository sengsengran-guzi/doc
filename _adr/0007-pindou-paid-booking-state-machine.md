# ADR-0007 拼豆付费预约的双状态机（预约生命周期 status × 支付状态 pay_status 正交，单笔单时段）

- 日期：2026-06-09
- 状态：Accepted
- 决策人：Kevin（kevin-product 评估，kevin-coder 落地）
- 关联 ticket：GZ-BEAN-014（单笔单时段付费预约 + 付费状态机 + 防超卖计数 + 旧数据迁移）/ GZ-BEAN-015（mp 付款链路）；依赖 ADR-0008（座位类型配额模型）+ ADR-0003（支付通道）
- 落地批次：D13（BEAN-014 后端/admin）+ D14（BEAN-015 mp）

---

## Context

拼豆预约在 V1.0 是**免费模块**：用户只「约时段 + 座位」，不付钱，核销即用。状态字段 `gz_bean_booking.status` 单独管预约生命周期：

```
pending（已约待用） → used（已核销） / cancelled（取消） / no_show（爽约）
```

V1.2 甲方要求**付费前置**，且明确预约粒度为**单笔单时段**：**一笔预约 = 1 座位类型 + 1 时段**（座位类型配额模型见 ADR-0008），单笔金额 = 该座位类型单价（`gz_bean_booking.amount_cent`）。用户如需多类型 / 多时段 = **多次预约（多行 booking）**，**不引入多单元子表**。付款成功后预约才成立。于是 `gz_bean_booking` 要同时承载两套语义——「预约处于生命周期哪一步」和「钱付了没 / 核销了没」。

核心设计问题：**支付语义是塞进现有 `status` 单状态机，还是另立一列？**

- 塞进 `status`（单状态机）：取值会爆炸成 `pending_pay / paid_pending / used / cancelled / refunded / ...`，且「已付款但未核销」「已核销」「已付款已取消待退款」等组合维度互相纠缠，状态边定义极易漏 case，未来加退款/改期更乱。
- 另立 `pay_status`（双状态机正交）：预约生命周期与支付状态各管各的维度，组合由两列笛卡尔积表达，边清晰、可扩展。

## Decision

### 1. `pay_status` 独立列管支付，`status` 保留预约生命周期，两者正交但有前置约束

新增 `gz_bean_booking.pay_status`（独立枚举，与 ADR-0008 的 booking 主单 ALTER 一并落地）：

**支付状态机 `pay_status`：**

| 取值 | 含义 | 进入条件 |
|---|---|---|
| `unpaid` | 已下单、待支付 | 创建预约单（占用配额，见 §2） |
| `paid` | 已支付成功 | 微信收款回调 `onPaid`（ADR-0003 链路） |
| `verified` | 已核销（钱已收 + 实际到店使用） | 店员核销，**前置必须 `paid`** |
| `closed` | 已关闭（旁路终态） | 超时未支付 / 取消 → 释放配额 |

> **DB 枚举落地以 doc/11 §3.8 + 附录 A.15 为准**（字段层权威）：本表是「钱 + 履约」的概念生命周期视图；落库 `pay_status` 枚举为 `unpaid` / `paying`（发起 JSAPI 后、回调前）/ `paid` / `pay_closed`（= 本表 `closed`）/ `refunded`（V2）。**「核销」在 DB 用 `status: pending→used` 表达，`pay_status` 仍停 `paid`**（本表 `verified` 是对「已付且已核销」这一概念态的命名，不单独落一个 `pay_status` 值——核销只推 `status`）。实施按 doc/11 枚举写库，本 ADR 提供状态边与前置约束的裁判口径。

**预约生命周期 `status`（V1.0 沿用，语义微调）：**

| 取值 | 含义 |
|---|---|
| `pending` | 预约有效、待到店 |
| `used` | 已使用（与 `pay_status=verified` 对应核销动作） |
| `cancelled` | 用户/店员取消 |
| `no_show` | 爽约 |

**两者关系（明确口径，杜绝双状态漂移）：**

1. **正交**：`pay_status` 只描述钱，`status` 只描述预约履约，两列各自独立流转，不互相覆盖。
2. **唯一硬前置**：`pay_status` 推进到 `verified` **必须先满足 `pay_status=paid`**（没付款不能核销）。核销动作同时把 `status` 推到 `used`。
3. **下单初态**：`status=pending` + `pay_status=unpaid`（已占配额、待支付）。
4. **支付成功**：`onPaid` 仅推 `pay_status: unpaid→paid`，**不动 `status`**（仍 `pending`，等到店核销）。
5. **超时未付**：SnailJob 关单推 `pay_status: unpaid→closed` + `status: pending→cancelled`，**释放配额**。
6. **核销**：店员核销推 `pay_status: paid→verified` + `status: pending→used`（一个事务）。
7. **爽约**：到店未核销且过期 → `status: pending→no_show`，`pay_status` 停在 `paid`（钱已收，是否退款属 V2 退款流，本批不做）。

> **口径锁定**：实施只允许这 7 条边。任何「在 `status` 里塞支付语义」或「在 `pay_status` 里塞履约语义」的写法 = 双状态漂移，§0 自检 / QA 直接打回。退款 (`refunded`) 不在本批范围（合同 §2.3 V2 清单）。

### 2. 配额防超卖：下单事务内对 (店,类型,日期,时段) COUNT 活跃 booking FOR UPDATE 比对配额

座位类型配额模型（ADR-0008）下，可用量 = 某 `(store, seat_type, date, slot)` 的配置 `quantity` − 该组合下当前活跃 **booking** 计数。**一笔预约 = 一行 booking（1 类型 1 时段）**，无子表。下单防超卖：

1. 下单在**单个数据库事务**内，对本笔预约的 `(store, seat_type, date, slot)` 组合：
   - `SELECT COUNT(*) FROM gz_bean_booking WHERE store_id=? AND seat_type=? AND sess_date=? AND slot_start=? AND <活跃> FOR UPDATE`（悲观锁锁住该组合的活跃 booking 行）。
   - 「活跃」= booking 的 `pay_status IN (unpaid, paid, verified)`（`closed`/`cancelled`/`no_show` 释放配额，不计数）。
2. `活跃计数 >= quantity`（已满）→ **拒单、事务回滚**。
3. 校验通过（`活跃计数 < quantity`）→ INSERT 一行 booking，`pay_status=unpaid`。

> **单笔单时段 = 无「部分成交」问题**：一笔预约只占一个 (类型,时段) 名额；约满即拒单，不存在「多单元里某单元满了要不要整单回滚」的纠结。用户要多类型 / 多时段 → 各自单独下单（多行 booking），每行独立校验配额。

**`unpaid` 也占配额的取舍**：下单即占（而非付款后才占），防止「下单后慢慢付、配额被别人抢走、付款时才发现没位」的体验崩塌；代价是「占而不付」会临时压库存——靠 §1.5 超时关单（SnailJob，建议 15 分钟）释放回收。

### 3. 旧 booking 数据迁移（V1.0 免费单 → V1.2 付费模型）

V1.0 免费单本就是「单类型单时段」结构（无 pay_status）。V1.2 单笔单时段模型与之同构，**无子表迁移**，原地 ALTER 即可（GZ-BEAN-014 内随 Flyway 做，强约束 #5 新建更大时间戳迁移文件）：

- 旧 booking 原地补 `seat_type`（按旧 `seat_id` → `gz_bean_seat` 映射，或统一置默认 `single`）+ `seat_type_snapshot` + `amount_cent=0`（历史免费单）。
- `pay_status` 标记为**历史免费单**——置 `paid`（视同已付 0 元，不卡核销前置）；已核销的历史单 `status=used` 保持（`pay_status` 同为 `paid`/`verified` 视 §1 口径）。
- 迁移后做**回归**：历史单仍可在 admin / mp 正常查询、核销不报错（ADR-0003 mock + memory `admin-test-tenant-account` 登 gz_owner 验）。

## Rationale

- **双状态机正交 = 维度解耦**：钱和履约是两个独立维度，强行揉进一列必然组合爆炸 + 漏 case。两列笛卡尔积 + 一条硬前置（verified 需 paid），边数最少、语义最清、最易扩展（未来退款只动 `pay_status` 维度）。
- **明确口径杜绝漂移**：双状态机最大风险是「两列说法打架」（如 status=used 但 pay_status=unpaid）。本 ADR 把允许的 7 条边和唯一前置写死，让实施与 QA 有单一裁判。
- **悲观计数足够（V1 单店小量）**：成都单店 + 拼豆并发量低，事务内 `COUNT ... FOR UPDATE` 悲观锁简单可靠、无额外组件；不引 Redis 预占（YAGNI）。量大再升级（见 Consequences）。
- **单笔单时段简化模型**：贴合甲方真实诉求（一次约一个类型一个时段），数据结构最简（一行 booking，无子表）；多类型 / 多时段用「多次预约」表达，每笔独立计费、独立配额、独立核销，无跨单元事务复杂度。
- **下单即占配额**：保护用户支付体验（不会付款时才发现没位），代价用超时关单兜底。

## Consequences

- ✅ 拼豆从免费升付费，状态语义清晰（钱 / 履约两条线），未来加退款/改期只在对应维度扩边。
- ✅ 配额防超卖在事务 + 悲观锁内闭环：单笔预约约满即拒，无「部分成交 / 残缺单」问题。
- ✅ 旧 V1.0 免费单与 V1.2 单笔单时段模型同构，原地 ALTER 平滑迁移为「已付 0 元」历史单（无子表迁移），不破坏既有核销与查询。
- ✅ 拼豆接入收款（`PayBusinessType.PINDOU` 激活，ADR-0003 链路），`onPaid` 仅动 `pay_status`，核销事务同时动两列。
- ⚠️ **并发口径上限**：悲观 `COUNT FOR UPDATE` 在高并发下会串行化同组合下单（锁竞争）。V1 单店量级无虞；若未来多店/大促放量 → 升级 Redis 预占（下单先 Redis 扣减、异步落库、DB 唯一约束兜底），**届时另 raise，不在本批**。
- ⚠️ **超时关单时长**需与甲方确认（建议 15 分钟）：太短伤慢付用户，太长压库存。SnailJob 注册（无 sys_job 表，控制台手工注册，同 ADR-0003 §4 / memory `scheduler-is-snailjob`）。
- ⚠️ **退款不在本批**（合同 §2.3 V2）：`no_show` 后钱停 `paid` 不自动退；如甲方坚持要退款流 = 新功能，走 §8.5 协商。
- ⚠️ **对账感知新口径**（顺延 D16 ADMIN-105）：拼豆 `business_type=pindou` 正向流水是否入 GMV / 4% 分成留待 D15 对账定（doc/11 §4.6）；券面额不计 GMV（见 ADR 优惠券口径 / doc/11 §11.3）；单笔实付 = `amount_cent`（该类型单价）− 券抵扣（下限 0）。
