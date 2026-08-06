# GZ-JP-104 完工报告 — 购物车（gz_jp_cart_item）建表 + API

> 在 `ruoyi-gz-jp` 模块内继续加表与端点，**未动任何 pom**、**未改任何既有文件**（13 个文件全是新增）。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（RuoYi 在 staging） | ✅ | 开工前 `git status --short` 空输出 |
| **上游 GZ-JP-102 已 merge** | ✅ | `7dc1d98a1 D3/GZ-JP-102: 商品（gz_jp_product）建表 + admin 商品管理`；活库 `gz_jp_product` 3 行 fixture 在 |
| GZ-JP-103 + 可见性放宽也已 merge | ✅ | `a598165e4`（103）/ `66b6b58bc`（可见性放宽）—— `isBookable` / `isVisible` 两条闸可直接复用 |
| 迁移时间戳 = 当下真实时间 | ✅ | `date +V%Y%m%d%H%M` → `V202608070548`；已应用最大 `V202608070233` |
| Flyway append-only 自检 | ✅ | migration 目录 `git status --short` 只有 `??`（新增 1 个），**无 M/D/R** |
| 编译健康（基线） | ✅ | `mvn -o compile -pl ruoyi-gz-jp -am` → EXIT=0 |
| 权威蓝图已读 | ✅ | field-ssot `gz_jp_cart_item` 段 / flows `F-JP-02.step2` / ui-index `UI:mp.cart`+`.group`+`.summary` / requirements `REQ-ORDER-005` / `_visibility-extension-pre-201.md` |
| ADR | 无相关（doc/jp 无 ADR 目录；沿用 101/102/103 骨架与跨层契约） |

### 权威蓝图关键约束摘录

- `FIELD:gz_jp_cart_item` —「客人一次可选几十款，**跨场共存**」；字段仅 `id / user_id / product_id / qty`，唯一键 `uk_user_product`，索引 `idx_user(tenant_id, user_id)`，`id_range: 无 menu（纯 C 端）`。
- `FLOW:F-JP-02.step2` —「加入购物车 / 改数量 / 删除 → **购物车项。跨场可共存于同一购物车**」。
- `UI:mp.cart` —「按场分组…**失效项（场已结束 / 商品已下架）置灰并标「已失效」，不计入合计、不可勾选**」。
- `UI:mp.cart.summary` —「★ 只有商品合计一行，**无运费行**（全包邮）」。
- `REQ-ORDER-005` —「一个客人比如买了 30 款商品」，我方推导：逐款单独下单不可用，必须有购物车。
- `_visibility-extension-pre-201.md` —「**写路径纪律：加购 / 提交订单 / 支付一律继续用 `isBookable`，不要因为「列表能查到」就放行下单**」；「购物车失效项同一套字段够用」。

---

## 实现摘要

### 改动文件（13 个全新增，0 个修改）

```
?? ruoyi-admin/src/main/resources/db/migration/V202608070548__GZ-JP-104-create-gz_jp_cart_item.sql
?? ruoyi-gz-jp/.../controller/applet/GzJpCartMpController.java
?? ruoyi-gz-jp/.../domain/entity/GzJpCartItem.java
?? ruoyi-gz-jp/.../domain/enums/GzJpCartInvalidReason.java
?? ruoyi-gz-jp/.../domain/bo/{GzJpCartAddBo,GzJpCartQtyBo}.java
?? ruoyi-gz-jp/.../domain/vo/{GzJpCartVO,GzJpCartGroupVO,GzJpCartItemVO}.java
?? ruoyi-gz-jp/.../mapper/GzJpCartItemMapper.java
?? ruoyi-gz-jp/.../service/IGzJpCartService.java
?? ruoyi-gz-jp/.../service/impl/GzJpCartServiceImpl.java
?? ruoyi-gz-jp/src/test/.../GzJpCartServiceTest.java   (38 用例)
```

**未碰 plus-ui / miniapp / miniapp-jp**（购物车是纯 C 端数据，admin 不管理 —— field-ssot 标注「无 menu」，故**无菜单 / 无字典 / 无权限**迁移）。

### mp 端点（**全部需登录态**，本类刻意无 `@SaIgnore`）

| Method | Path | 说明 |
|---|---|---|
| GET | `/app/gz/jp/cart/list` | 购物车（**按场分组** + 实时标失效项） |
| POST | `/app/gz/jp/cart` | 加购（同商品已存在 → **数量累加**），返回累加后数量 |
| PUT | `/app/gz/jp/cart` | 改数量（**绝对赋值**，1..99） |
| DELETE | `/app/gz/jp/cart/{ids}` | 删除（逗号分隔批量），返回实际删除行数 |

`userId` 一律取 `LoginHelper.getUserId()`（= `gz_user.id`），**任何入参里都没有 userId 字段**。未登录 → sa-token 全局拦截 401。这也是本项目 mp「先逛后登录」的分界线：逛场 / 看商品匿名（GZ-JP-103 `@SaIgnore`），加购起要登录。

### 关键实现决策

1. **★★ 物理删，不软删** —— 实体刻意不声明 `delFlag` 字段（MyBatis-Plus 无 `@TableLogic` → `deleteByIds` 走物理 DELETE）。理由：`uk_user_product(tenant_id, user_id, product_id)` **覆盖软删行**，一旦软删，「删掉再重新加购同款」必撞 409 DuplicateKey（本项目 `gz_bean_booking` 的 `uk_booking_no` 已因同款问题炸过）。购物车是纯暂存数据、无审计价值、未注册 `RecycleEntityRegistry`。DB 里 `del_flag` 列仍在（公共字段七件套 / accept #1），恒 `'0'`。已实测「删 → 重加同款」不撞库（§4.11）。

2. **★★ `addItem` 刻意跑在事务之外（`Propagation.NOT_SUPPORTED`）** —— 详见下面「§6 一次被真并发压测推翻的设计」。这是本卡最贵的一条经验，已写进方法 javadoc + 一条专门的单测锁死。

3. **★ 累加走原子自增 SQL**（`GzJpCartItemMapper.increaseQty`：`SET qty = qty + #{add} WHERE ... AND qty + #{add} <= #{max}`），不是「读出来 + 内存加 + updateById」—— 后者在并发下丢更新（20 个并发 +2 会落成 +2 而不是 +40）。上限守卫下沉进 WHERE，超限时影响 0 行 → 转明确报错，**绝不静默截断成 99**。

4. **★ 加购走严格闸 `isBookable`，不是 `isVisible`** —— 遵守可见性契约的写路径纪律：已结束场里的在架商品「看得到但加不进车」（实测 §4.8）。只读的列表接口才用宽闸口径。

5. **失效判定读时惰性、不落库** —— 不设 status 列、不跑 cron（本项目 prod 未部署 SnailJob，任何 `@JobExecutor` 都不会执行）。场重开 / 商品重新上架 → 购物车项**自动恢复可用**，没有需要清理的脏标记。实测：关场 → invalid，重开场 → 恢复（§4.5/§4.6）。

6. **失效项照常下发但不计入合计** —— 客人要看得见自己加过什么。`invalid=true` + `invalidReason`（code）+ `invalidText`（中文）三件套；行金额 `amountCent` 照给（前端展示划线价），但不进 `validAmountCent` / `validQty`。

7. **失效优先级** `product_removed` → `product_off_shelf` → `event_closed`（商品都没了就没必要再说场怎么样）。**文案刻意不区分「商品被删」与「商品下架」**（对客人是同一件事，且不向 C 端泄漏后台删除动作），两个 code 分开只为服务端排障与 203 埋点。

8. **孤儿组** —— 商品已被删的项归不到任何场（本表不存 `event_id`），统一进 `eventId=null` 的「已失效商品」组并**排到最后**。分组排序：可下单场 → 已结束场 → 孤儿组沉底（别让客人为了点「去结算」先滚过一堆买不了的）。

9. **不存 event_id / 不存价格快照** —— 场归属跟着商品走（店员可能移场），存一份会漂移；价格实时读商品表，购物车不是价格承诺，真正锁价在下单那一刻的 `product_snapshot_json`（GZ-JP-105）。

10. **不维护勾选态** —— 勾选是纯前端交互，落库只会产生「勾选态与商品状态不一致」的脏数据。后端只给「全选口径」的 `validAmountCent`，实际勾选合计由前端按 `amountCent` 累加。

11. **改数量不校验商品是否仍可下单** —— 购物车是暂存区，失效在读时标、在下单时拦（105）。在这里拦会让客人对着一个既改不动、又看不懂为什么的行发懵；他仍然可以删。

12. **上限**：单款 99 件（防误触长按刷出天量数字 —— 下游订单金额 = 单价 × 数量，6 位 qty 能让订单金额变成客服事故）；全车 50 款（REQ-ORDER-005 场景是 30 款，留足余量；同时给列表接口的预签名扇出封顶）。款数上限**只管新增行**，对车里已有商品累加不受限。

13. **`msg` 不区分「不存在」与「不是你的」** —— 改 / 删别人的项统一报「购物车项不存在」，不泄漏别人车里有什么。

---

## AI 自测（Tier 1A）

### 1. 编译 + 单测（95 用例全绿：38 新增 + 57 上游回归）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dsurefire.failIfNoSpecifiedTests=false
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductServiceTest
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.810 s
[INFO] Running org.dromara.gz.jp.service.impl.GzJpEventStatusTest
[INFO] Tests run: 17, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.053 s
[INFO] Running org.dromara.gz.jp.service.impl.GzJpCartServiceTest
[INFO] Tests run: 38, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.090 s
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductMpQueryTest
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.025 s
[INFO] Tests run: 95, Failures: 0, Errors: 0, Skipped: 0
[INFO] ruoyi-gz-common .................................... SUCCESS
[INFO] ruoyi-gz-jp ........................................ SUCCESS
[INFO] BUILD SUCCESS

（上游 ruoyi-gz-common 220 用例同批全绿，未受影响）
```

`GzJpCartServiceTest`（`@Tag("dev")`，38 例）覆盖：**重复加购累加不新增行** / **累加走原子自增 SQL 而非读改写** / **addItem 必须 NOT_SUPPORTED（反射断言传播行为）** / 首次加购 insert 且不显式赋 tenant_id / qty 缺省为 1 / **并发撞唯一键转累加** / 撞键后自增打不中→明确报错 / 商品不存在·off_shelf·场不可下单三类拒绝 / **加购不许用 isVisible**（`verify(never()).isVisible`）/ 未登录 / 累加超 99 不截断 / 单次超 99 / 款数上限 50 / 款数满时累加仍放行 / 改数量绝对赋值 / 改别人的项 / 同值幂等不打 UPDATE / qty=0 拒绝 / 改数量不回查商品 / **删除条件必含 user_id**（断言 SqlSegment）/ 空 ids 拒绝 / 空车返空数组不返 null / 有效项合计 / **场已结束标 invalid 且不计入合计** / 商品下架 / 商品已删入孤儿组+名称回落 / 场被删当作已结束 / **跨场共存两组且可下单场在前** / 三级分组排序 / 组内最近加购在前 / **列表查询必含 user_id + id 倒序** / 同图只签一次 / 图片失败回落占位图 / selectByUserAndIds 空 ids 不打库 + 必含 user_id / **ID 序列化为 string** / **VO 无运费字段**。

### 2. Flyway 迁移（启动自动跑）

```
DbMigrate - Migrating schema `ry-vue` to version "202608070548 - GZ-JP-104-create-gz jp cart item" [out of order]
DbMigrate - Successfully applied 1 migration to schema `ry-vue`, now at version v202608070548
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功   ლ(´ڡ`ლ)ﾞ
```

### 3. DB 结构验证（七件套齐 + 唯一键 + 索引）

```
mysql> SELECT column_name,column_type,is_nullable,column_default FROM information_schema.columns
       WHERE table_schema='ry-vue' AND table_name='gz_jp_cart_item' ORDER BY ordinal_position;
id            bigint        NO   NULL
user_id       bigint        NO   NULL
product_id    bigint        NO   NULL
qty           int           NO   1
tenant_id     varchar(20)   NO   1001     ┐
create_dept   bigint        YES  NULL     │
create_by     bigint        YES  NULL     │ 七件套（create_dept 没漏）
create_time   datetime      YES  NULL     │
update_by     bigint        YES  NULL     │
update_time   datetime      YES  NULL     │
del_flag      char(1)       NO   0        ┘  ← 恒 '0'，本表物理删
remark        varchar(500)  YES  NULL

mysql> SHOW INDEX FROM gz_jp_cart_item;
PRIMARY          id                                  unique
uk_user_product  tenant_id / user_id / product_id    unique   ← 唯一约束含 tenant_id
idx_user         tenant_id / user_id                 non-unique

-- 公共字段自动注入实测（mp app_user 建的行）
mysql> SELECT id,user_id,product_id,qty,del_flag,tenant_id,create_by FROM gz_jp_cart_item;
5   14   1   2   0   1001   14      ← tenant_id / create_by 均由框架自动注入，业务代码未显式赋值
```

### 4. API 端到端（真起应用打真库，mp token 走 `clientid: mp-applet-gz-jp`）

```bash
# ── 1. 空车（groups 是空数组不是 null，mp 对 null 做 v-for 会崩）
$ GET /app/gz/jp/cart/list
{ "code":200, "data":{ "groups":[], "itemCount":0, "invalidCount":0, "validQty":0, "validAmountCent":0 } }

# ── 2. ★ AC1：加购商品1 ×2 → 再 ×3 = 累加 5，不新增行
$ POST /app/gz/jp/cart {"productId":"1","qty":2}   → {"code":200,"data":2}
$ POST /app/gz/jp/cart {"productId":"1","qty":3}   → {"code":200,"data":5}
mysql> SELECT COUNT(*), SUM(qty) FROM gz_jp_cart_item;   →   1 行, qty=5      ★ 一行不是两行

# ── 3. ★ AC3：跨场共存（B 场另建一个 open 场 + 在架商品）
$ POST /app/gz/jp/cart {"productId":"67","qty":1}  → {"code":200,"data":1}
$ GET  /app/gz/jp/cart/list
  组 event=22 GZ-JP-104跨场共存对照场 status=open bookable=True
     item#40 p=67 单价=6800  qty=1 行金额=6800  invalid=False
  组 event=1  8月上旬快闪场    status=open bookable=True
     item#39 p=1  单价=12800 qty=5 行金额=64000 invalid=False
  itemCount=2 invalidCount=0 validQty=6 validAmountCent=70800      ★ 两场两组，合计 64000+6800

# ── 4. 改数量（绝对赋值）
$ PUT /app/gz/jp/cart {"id":"39","qty":4}          → {"code":200}
$ PUT 同值再发一次（弱网重发）                       → {"code":200}   幂等，不打 UPDATE

# ── 5. ★★ AC2：关闭 B 场 → 该项标失效且不计入合计
$ POST /system/gz/jp/event/close/22                → {"code":200}
$ GET  /app/gz/jp/cart/list
  组 event=1  8月上旬快闪场  status=open   bookable=True
     item#39 qty=4 行金额=51200 invalid=False reason=None
  组 event=22 ...           status=closed bookable=False           ★ 已结束场排到后面
     item#40 qty=1 行金额=6800  invalid=True  reason=event_closed  text=本场已结束
  itemCount=2 invalidCount=1 validQty=4 validAmountCent=51200
                                          ↑★ 6800 被排除，只算有效项 4×12800

# ── 6. 重开场 + 下架商品 → 失效原因换成 product_off_shelf（场可下单但商品下架）
  组22(bookable=True) item#40 invalid=True reason=product_off_shelf
  validAmountCent=51200    ← 仍不计入

# ── 7. 软删商品 → product_removed + 孤儿组沉底 + 名称回落
$ DELETE /system/gz/jp/product/67                  → {"code":200}
  组1  (8月上旬快闪场) item#39 '柯南 吧唧 一番赏 A赏' invalid=False
  组None(已失效商品)   item#40 '商品已下架'          invalid=True reason=product_removed
                                                      （priceCent=0 / mainImageUrl=占位图）

# ── 8. 加购的各条拒绝路径
已关场的商品      → 500 该商品已下架          （商品已软删，优先命中商品闸）
off_shelf (id=3) → 500 该商品已下架
draft 场 (id=4)  → 500 本场已结束，无法加入购物车   ★ 写路径走 isBookable，不是 isVisible
不存在的商品      → 500 该商品已下架          （不泄漏「不存在」）
未登录 GET/POST  → 401 认证失败，无法访问系统资源  ★ 本类无 @SaIgnore

# ── 9. ★ 用户隔离（直接往库里注入一条 user_id=1 的行）
我的列表含别人的行?  False   (我的 ids=['39','40'])
改别人的项           → 500 购物车项不存在        （不区分「不存在 / 不是你的」）
删别人的项           → 删除数=0
别人的行还在?        → 1 行 qty=9               ★ 未被改动也未被删

# ── 10. 数量上限（不静默截断）
PUT qty=100      → 500 单款商品最多 99 件
98 再 +5         → 500 该商品数量已达上限（99 件）
库里仍是          → 98                          ★ 没被截断成 99
98 再 +1         → 200 qty=99                   ★ 恰好 99 放行

# ── 11. ★★ 物理删验证：删除 → 无残留 → 重加同商品不撞 409
$ DELETE /app/gz/jp/cart/39                        → {"code":200,"data":1}
mysql> SELECT COUNT(*) ... WHERE user_id=14 AND product_id=1;  →  0
       （软删模型这里会留一行 del_flag=1 占着 uk_user_product）
$ POST /app/gz/jp/cart {"productId":"1","qty":2}   → {"code":200,"data":2}   ★ 未撞 DuplicateKey

# ── 12. 参数校验
缺 productId → 500 请选择商品          qty=0    → 500 数量至少为 1
PUT 缺 id    → 500 购物车项 ID 不能为空  PUT qty=0 → 500 数量至少为 1，如需移除请删除该商品

# ── 13. 批量删除
$ DELETE /app/gz/jp/cart/40,42                     → {"code":200,"data":2}
非本人 / 不存在的 id 静默忽略（删除数小于传入数）
```

### 5. ★★ 真并发压测（本卡最重要的一段 —— 逮出并修掉一个 deadlock）

```bash
# ── A. 30 个请求同时对同一 (user, product) 加购 +1（全新行竞争）
for i in $(seq 1 30); do curl -X POST /app/gz/jp/cart -d '{"productId":"1","qty":1}' & done; wait

  30 × code=200 msg=操作成功                    ★ 无一失败
  rows_total=1   qty_sum=30                     ★ 恰好一行、一件不多一件不少
  日志「并发加购撞唯一键，转累加」× 29          ★ 兜底路径被真实走了 29 次

# ── B. 20 个请求同时在已有行上 +2（纯丢更新场景）
for i in $(seq 1 20); do curl -X POST /app/gz/jp/cart -d '{"productId":"1","qty":2}' & done; wait

  20 × code=200 msg=操作成功
  rows_total=1   qty_sum=70                     ★ 30 + 20×2 = 70，一次更新都没丢
                                                  （读改写实现这里会落成 32）
# ── 死锁计数
$ grep -c "Deadlock" backend.log   →   0        ★
```

---

## §6 一次被真并发压测推翻的设计（这段值得单独看）

**中途版本**（已废弃）：`addItem` 包 `@Transactional`，`INSERT` 撞唯一键后用 `SELECT ... FOR UPDATE` 加锁读重查再累加。

推理是对的：MySQL 隔离级别 `REPEATABLE READ`（已实测 `SELECT @@transaction_isolation`），事务内普通读的一致性快照在第一次读时就固定，「先查（没有）→ INSERT 撞键 → 普通重查」的重查**永远返回 null**，兜底逻辑当场失效；加锁读才能读到对手刚提交的行。**我按这个推理改完，单测 37/37 全绿。**

**然后真并发压测把它打回来了**：

```
10 并发 → 7 × 500「发生未知异常」+ 3 × 200，库里 qty=3（应为 10）
org.springframework.dao.DeadlockLoserDataAccessException:
  Deadlock found when trying to get lock; try restarting transaction
```

根因：**失败的 INSERT 会在冲突的唯一索引记录上留一把 S 锁，并在事务里持有到事务结束**。多个并发请求各持一把 S 锁后再去要 X 锁（`FOR UPDATE`）→ 锁升级互等 → 死锁。

**最终版**：`addItem` 用 `Propagation.NOT_SUPPORTED` 跑在事务之外 + 累加走单条原子自增 UPDATE。
- 非事务下失败 INSERT 的隐式事务当场结束、**S 锁立即释放**，后续语句是全新事务 → 锁不跨语句累积 → 无死锁；
- 每条语句自成事务 → 每次读都是最新已提交 → 快照问题一并消失；
- 单条 `SET qty = qty + ?` 直接取 X 锁、无锁升级，且天然不丢更新。

这么做的**正当性**：本方法每条路径只有一次写（要么 INSERT 要么自增 UPDATE），没有需要事务保护的跨语句不变量 —— 事务在这里只带来坏处。用 `NOT_SUPPORTED` 而不是「不写注解」，是为了将来被某个带事务的上层方法调用时（如 105 下单流程顺手加购）会**挂起**外层事务，而不是静默加入它、让上面两个坑原样复活。

**两条防回归**：方法 javadoc 写明「别顺手加回 `@Transactional`」+ 一条单测用反射断言 `propagation == NOT_SUPPORTED`。

⚠️ **顺带一条给全项目的经验**：本卡并行派了 `code-reviewer` 静态评审，它读到的正是中途那版，结论是「**correctly handles the MySQL REPEATABLE READ concurrency pitfall via a FOR UPDATE locking read**」——**评审背书的恰恰是压测证伪的那版**。锁顺序 / 死锁这类问题静态评审看不出来，**只有真并发跑得出来**。gz-bean 的座位防超卖当初也是靠真库并发才立住的（mock 单测照不出），同一条教训。

---

## accept 两条结果

| # | name | form | 结果 |
|---|---|---|---|
| 1 | 建表且公共字段全集齐 | DDL | ✅ **PASS**（逐字执行，EXIT=0） |
| 2 | 同商品重复加购合并数量而非新增行 | STATE | ✅ **PASS**（逐字 + `-Dsurefire.failIfNoSpecifiedTests=false`，EXIT=0，38 例全绿） |

```
════════ accept #1（逐字）════════
docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema='ry-vue' AND table_name='gz_jp_cart_item'
  AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
  | grep -qx 7
EXIT=0

════════ accept #2（逐字 + -Dsurefire.failIfNoSpecifiedTests=false）════════
cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
  -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpCartServiceTest -Dsurefire.failIfNoSpecifiedTests=false 2>&1 | tail -5
EXIT=0
[INFO] Tests run: 38, Failures: 0, Errors: 0, Skipped: 0
```

> accept #2 需要加 `-Dsurefire.failIfNoSpecifiedTests=false`：`-am` 会带上 `ruoyi-gz-common` 等上游模块，它们没有名叫 `GzJpCartServiceTest` 的用例，不加这个参数 surefire 会在上游模块直接判失败。

---

## 上游契约回归（fixture 已逐条还原）

```
event/list          total=1 rows=[('1','open')]           ← draft 仍不下发
product/list ev=1   total=1 rows=[('1','on_shelf',True)]
event/2 (draft)     code=500 msg=该场不存在
product/3 (off)     code=500 msg=该商品已下架

gz_jp_cart_item  0 行          ← 测试数据全 HARD DELETE 清掉
gz_jp_event      2 行（id=1 open / id=2 draft，本卡建的 id=22 已物理删）
gz_jp_product    3 行（id=1/3/4，本卡建的 id=67 已物理删）
软删残留(product) 0             ← 项目铁律：测试数据不留软删残留
```

---

## 风险提示 / 已知 issue

1. **★ 别给 `addItem` 加回 `@Transactional`**（详见 §6）。有单测反射断言守着，但改的人要看得懂为什么。
2. **本卡无 mp 页面**（购物车页是 GZ-JP-203）。所有验证走 curl + 真库，**没有任何 UI 被人或机器看过一眼**。
3. **dev mock 登录恒返回同一个用户**（`wx.miniapp.mock-stable-openid` 在 application-dev.yml 置了非空，换 code 也是同一个 openid / userId=14）。所以「换个 code 登录成用户 B」测不了用户隔离 —— 本卡改用**直接往库里注入一条 `user_id=1` 的行**来验（§4.9），结论有效。dev 期要造多用户只能改配置或直接写库。
4. **购物车不锁价**。客人加购时 ¥128，店员改成 ¥168，客人下单付的是 ¥168（列表里也实时显示 ¥168，不会骗人）。这是刻意设计（`UI:mp.order_confirm` 要求下单前复校价格），但**目前没有「价格已变动」的提示**——105 做下单校验时若发现价格与客人看到的不一致，需要一个明确回退提示，不能默默按新价扣款。
5. **失效项不会自动清理**。客人不删就一直躺在车里（每次列表都实时判定，不占合计）。没有「一键清除失效商品」的独立端点 —— 203 收集失效项 id 调批量 DELETE 即可，不必新增端点。
6. **50 款上限是拍的**（REQ-ORDER-005 说 30 款）。触顶时报「请先结算或删除部分商品」。若甲方真出现一次买 60 款的客人，改 `CART_ROWS_MAX` 一个常量即可，但同时要重新评估列表接口的预签名扇出（每款主图一次 `getPresignedUrl`）。
7. **商品图是 MinIO 预签名 URL，1h 过期**（同 202 已知项）。购物车停留超 1 小时再看，图会 404。
8. **`create_dept` 对 mp 建的行恒为 NULL**（app_user 无部门）。列存在（accept #1 过），只是没值 —— 与本项目其他 mp 建的业务表一致，不是本卡引入的。
9. **迁移是 `[out of order]` 应用的**（既有配置 `out-of-order=true`），`success=1`，不影响。
10. **staging / prod 未部署**，只在本地 dev 库验证；上线时 Flyway 自动补跑这 1 条。
11. **未 commit 任何 git**（主线程统一收尾）。

### 残留进程（需要处置）

后端**是本卡重启的**（原 GZ-JP-201/202 会话起的实例已被 kill，本卡 `mvn clean install` 后重起），当前**保留运行** —— 下游 kevin-qa 跑 Tier 1B 需要它：

```bash
# mvn spring-boot:run -pl ruoyi-admin（日志 /tmp/gzjp-104-backend.log）
lsof -ti:8080 | xargs kill        # 不需要时收掉
```

docker 的 MySQL / Redis / MinIO 原本就在跑，未动。本会话起的临时脚本与 token 文件在 `/tmp/gzjp104-*`，无常驻进程。

---

## 对下游 ticket 的提示

### 给 GZ-JP-105（订单 + 下单事务）—— 你要从购物车勾选项转下单

**取数口已备好**（本卡刻意为你留的，别直接裸用 Mapper）：

```java
List<GzJpCartItem> selectByUserAndIds(Long userId, Collection<Long> ids);
```
- 只返回**确实属于该用户**的行；ids 为空 → 空列表（不打库）。
- **不做任何可下单性校验** —— 那是下单事务自己的事，你必须在**同一个事务里**重新校验场 `isBookable` + 商品 `on_shelf` + 价格，别信购物车列表接口给的 `invalid`（那是几秒前的读时快照）。
- 实体字段只有 `id / userId / productId / qty` —— **价格要自己查 `gz_jp_product.price_cent`**（购物车不存价格快照，故意的）。

**下单成功后清购物车**：调 `IGzJpCartService.deleteItems(userId, ids)`（物理删，幂等）。⚠️ 你的下单方法是 `@Transactional` 的，而 `deleteItems` 是普通 `@Transactional(REQUIRED)` → 会加入你的事务，随你一起回滚，这是**对的**（下单失败不该清车）。**但注意 `addItem` 是 `NOT_SUPPORTED`**，如果你在下单流程里顺手调它，它会挂起你的事务、独立提交 —— 别在下单事务里调 `addItem`。

**金额口径**：`amountCent = priceCent × qty`，`priceCent` **已是包邮终价**（REQ-ORDER-004），订单不得再加运费行。后端重算不信前端（本卡的 `validAmountCent` 只服务展示，别拿它当下单金额）。

**一单可含多场商品**（AC 3 已验），所以下单事务不要按场拆单、也不要校验「勾选项必须同场」。

### 给 GZ-JP-203（mp 购物车页）—— 契约照抄

**端点 + 返回结构**（`R<GzJpCartVO>`，读 `res.data`）：

```jsonc
GET /app/gz/jp/cart/list        // 需登录
{
  "code": 200,
  "data": {
    "groups": [                                    // 空车时为 [] 不是 null
      {
        "eventId": "1",                            // ★ 可能为 null（孤儿组「已失效商品」），渲染分组头要判空
        "eventNo": "EVT-20260807-000001",
        "eventName": "8月上旬快闪场",
        "eventStatus": "open",                     // "open" | "closed" | null
        "eventBookable": true,                     // false → 本组整组失效，分组头可显示「本场已结束」
        "items": [
          { "id": "39",                            // ★ 购物车项 id：改数量 / 删除 / 结算勾选都用它
            "productId": "1", "productNo": "JPP-20260807-000001",
            "name": "柯南 吧唧 一番赏 A赏",
            "mainImageUrl": "https://...",         // 恒非 null（无图回落占位图）
            "priceCent": 12800, "qty": 4,
            "amountCent": 51200,                   // 行金额，后端算好
            "eventId": "1",
            "invalid": false,                      // ★ true → 置灰 + 不可勾选 + 不计入合计
            "invalidReason": null,                 // "event_closed" | "product_off_shelf" | "product_removed"
            "invalidText": null }                  // "本场已结束" | "商品已下架" —— 直接展示，别自己维护映射
        ]
      }
    ],
    "itemCount": 2,          // 款数（含失效），tabbar 角标用这个
    "invalidCount": 1,       // 失效款数，> 0 可提示「N 件商品已失效」
    "validQty": 4,           // 有效项总件数（Σ qty）
    "validAmountCent": 51200 // ★ 有效项合计（分）—— 全选口径
  }
}
```

- **「能不能勾选」只看 `item.invalid`**。别拿 `eventBookable` 或场的 `endTime` 跟本地时钟比来自己判（判不出店员手动关场，客户端时钟也不可信）。
- **合计**：`validAmountCent` 是**全选口径**。用户实际勾选后的合计由你按选中项的 `amountCent` 累加（后端不维护勾选态）。**底部只有商品合计一行，不出现运费行**（你的 accept #2 直接 grep 这个）。
- **未勾选任何项时「去结算」置灰**（你的 AC 4）—— 纯前端状态。
- **分组已排好序**（可下单场 → 已结束场 → 孤儿组），照数组顺序渲染即可，别再自己排。
- **孤儿组**：`eventId === null`、`eventName === "已失效商品"`、`eventBookable === false`，组内全是 `product_removed`。
- 金额单位是**分**，展示除 100 —— 复用 202 建的 `src/api/gz-jp/format.ts`。

**写端点**：

| 动作 | 请求 | 成功返回 | 主要业务错误（`code=500` + `msg`，直接 toast） |
|---|---|---|---|
| 加购 | `POST /app/gz/jp/cart` `{productId, qty}` | `data` = 累加后数量 | 该商品已下架 / 本场已结束，无法加入购物车 / 该商品数量已达上限（99 件）/ 购物车最多放 50 款商品… |
| 改数量 | `PUT /app/gz/jp/cart` `{id, qty}` | `data: null` | 购物车项不存在 / 数量至少为 1，如需移除请删除该商品 / 单款商品最多 99 件 |
| 删除 | `DELETE /app/gz/jp/cart/{ids}` 逗号分隔 | `data` = 实际删除行数 | 请选择要删除的商品 |

- **stepper 是绝对赋值**（传目标值不是增量）；**减到 0 请走 DELETE**，PUT 最小值是 1（前端 clamp 别误发 0）。
- **加购按钮置灰判 `eventBookable === false`**（202 已实现 `buildAddToCartState`，直接复用；把里面的占位 toast 换成真调 `POST /cart` 即可 —— 202 报告里点名说这事归你）。
- **「清除失效商品」不需要新端点**：收集 `invalid === true` 的 `item.id` 调一次批量 DELETE。
- 全部端点**需登录**：未登录返 `401`。走项目既有的 `ensureLoggedIn` / `BizLoginSheet` 流程（游客优先、按需登录，不要做登录墙）。
- **改数量 / 删除后建议整车重拉**（`GET /list`）而不是本地改数：失效状态是后端实时算的，本地改数会让「刚被店员关场」的项在页面上仍显示可勾选。

### 编号 / 段位现状（下一 ticket 直接接着用）

| 资源 | 已占 | **下一个空号** |
|---|---|---|
| `sys_menu` GZ-JP 段 | 14000-14005（场）、14010-14014（商品）；**本卡未占**（纯 C 端无菜单） | 场按钮 **14006**；商品按钮 **14015**；订单管理 **14020** 段；履约看板 **14030** 段 |
| `sys_dict_type.dict_id` | 9280、9281；**本卡未占** | **9282** |
| `sys_dict_data.dict_code` | 92801-92805；**本卡未占** | **92806** |
| Flyway 版本 | …V202608070548 | 用 `date +V%Y%m%d%H%M` 当下真实时间 |

### 全 jp 域通用（101/102 已提，仍成立）

- **改 `ruoyi-gz-jp` 任何代码后必须 `mvn clean install`**（非 clean 的 install 既不重打 jar 也不重编译测试，`exit 0` 会骗人）。
- 单测类必须 `@Tag("dev")`，否则 surefire `<groups>` 直接跳过、静默「通过」。
- 纯 mock 单测断言 `LambdaQueryWrapper.getSqlSegment()` 时，`@BeforeAll` 必须
  `TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), ""), Entity.class)`。
- **涉及并发的实现，单测全绿不算数**（§6）——必须真库并发跑一轮。

---

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

Tier 1B 建议覆盖：
- **后端集成**：`/app/gz/jp/cart/*` 四端点全链路 + 401（未登录）+ 用户隔离（改 / 删非本人项）
- **API 契约回归**：`GzJpCartVO` / `GzJpCartGroupVO` / `GzJpCartItemVO` 字段名与本报告「给 203」段一致；id 全 string；**无运费字段**；`groups` 空车为 `[]`
- **并发回归**：同一 (user, product) N 并发加购 → 1 行 + qty 精确 + 0 死锁（本卡已跑 30/20 并发，建议纳入回归包）
- 本卡**无 admin 页面**（购物车不进后台）、**无 mp 页面**（归 203）→ 无 Playwright / 模拟器 E2E 对象
- ⚠️ 跑之前确认 8080 上是**本卡 clean install 后的 jar**（`grep "gz-jp-cart"` 日志能看到本卡的 log 前缀）

---

**结论：accept 两条全 PASS（两条 EXIT=0）。**
