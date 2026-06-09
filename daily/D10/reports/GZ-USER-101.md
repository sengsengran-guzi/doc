# GZ-USER-101 完工报告 — 订单聚合统一接口（service 层 UNION）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游迁移文件存在（gz_ord_order / gz_gacha_order / gz_pay_transaction） | ✅ V202606061400(ORD-104) / V202606171400(GACHA-104) / PAY-001 + fix 迁移 V202606180000(主线程已补) |
| 上游 entity 字段齐（logistics_status / cn_carrier_code / cn_tracking_no / product_snapshot_json / prize_snapshot_json / machine_snapshot_json / total_amount_cent / paid_time / delivered_time / create_time） | ✅ 逐字段核对 GzOrdOrder + GzGachaOrder |
| 编译通过（gz-user -am offline） | ✅ |
| 单测通过 | ✅ 6/6 |
| 全链 install（common/user/ord/gacha） | ✅ BUILD SUCCESS（生产代码） |
| ADR 已读 | ADR-0004（mp 店员权限底座，影响 AC1 鉴权判定）+ ADR-0005（C1 物流，只读不实施） |

> 不重复主线程做的迁移层校验；未新建任何迁移（本 ticket 纯查询服务，预期无 DDL，符合 Tech 段）。

### §0 raw output（关键摘录）

```
$ ls migration/ | grep -E 'GZ-ORD-104|GZ-GACHA-104'
V202606061400__GZ-ORD-104-create-gz_ord_order.sql
V202606171400__GZ-GACHA-104-create-gz_gacha_draw-order-collection.sql
（PAY 流水 gz_pay_transaction 由 PAY-001 建；主线程补 fix V202606180000__GZ-ORD-101-fix-base-columns.sql）
```

## 实现摘要

服务层 UNION 聚合，**不建 MySQL VIEW / 物化表**（doc/11 §8.1 F8.1）。

新增产物（全部 `org.dromara.gz.user.*`，无新 DDL）：

| 文件 | 作用 |
|---|---|
| `controller/applet/GzUserOrderMpController.java` | mp `GET /app/gz/user/orders`（@SaCheckLogin + user_id 归属） |
| `service/IGzUnifiedOrderService.java` + `service/impl/GzUnifiedOrderServiceImpl.java` | service 层 UNION 合并 + 内存分页 |
| `domain/vo/GzUnifiedOrderVo.java` | 统一 VO（字段对齐 doc/11 §8.1 + README §1） |
| `domain/bo/GzUnifiedOrderQueryBo.java` | bizType / pageNum / pageSize |
| `domain/entity/readonly/OrdOrderRow.java` + `GachaOrderRow.java` | gz_ord_order / gz_gacha_order **只读 entity 投影** |
| `mapper/readonly/OrdOrderRowMapper.java` + `GachaOrderRowMapper.java` | 只读 mapper（BaseMapperPlus，走 ruoyi 租户/软删拦截器） |
| `test/.../GzUnifiedOrderServiceImplTest.java` | 6 个单测（含 AC11 a/b/c） |

改动文件（无 git；新增 9 个文件 + 0 个修改 — 未动任何上游模块代码）。

### 关键设计决策：为何在 gz-user 内建只读 entity/mapper 而非注入上游 service ⭐

ticket Tech 段建议「service impl 注入 `IGzOrdOrderService` + `IGzGachaOrderService`」。但 **`ruoyi-gz-ord` 已 `dependency` 到 `ruoyi-gz-user`**（用 `IGzUserAddressService` 下单写地址 snapshot）。若反过来让 gz-user 依赖 gz-ord，会形成 **Maven 循环依赖（ord → user → ord，编译期 hard-fail）**。

ticket 同时钉死聚合 service 必须落在 `org.dromara.gz.user.*` 包。两约束冲突。**最小且唯一无环的解**：在 gz-user 内建两个 **只读 entity 投影**（`@TableName("gz_ord_order")` / `@TableName("gz_gacha_order")`）+ 只读 mapper（`BaseMapperPlus`），由 ruoyi `TenantLineInnerInterceptor` + `@TableLogic` 自动加 tenant/del_flag 过滤。

- 不新增任何模块间依赖（gz-user 仍只依赖 gz-common）→ 无环
- 仍是「service 层 UNION，不建物理 VIEW」口径（doc/11 §8.1）
- 只读、不写入（写入仍归各自上游模块）
- 全链 install 实测 BUILD SUCCESS，证明无环

> 这是「ticket Tech 实现建议 ↔ 既有模块依赖图」的工程性偏差，按 §9.5 应改源头：**建议在 ticket Tech 段 / doc/11 §8.1 补注「聚合用只读 mapper 镜像，禁注入 gz-ord/gacha service 以免环」**（已在代码 javadoc 钉死，留 product 决定是否回填 doc）。

### AC1 偏差说明（鉴权注解） ⚠️ 待 product 裁定回填源头

ticket AC1 要求 `@SaCheckPermission("gz:user:orders:list")`。但本仓库 **mp 路由上的 `@SaCheckPermission` 是「店员专用门」**（ADR-0004：仅绑定 owner/staff 的 app_user 会话带 `gz:*` 权限；纯顾客 app_user token 不带 → sa-token 403）。

「我的订单」是 **C 端顾客**功能（D10 README §1：「C 端用户在 mp 我的订单…」）。若挂 `@SaCheckPermission`，**所有普通顾客 403，功能不可用**。全仓 C 端「我的 X」路由（ord `/list`、gacha collection `/my`、bean `/my`）一律 `@SaCheckLogin` + user_id 归属。

**已按既有 C 端鉴权模型用 `@SaCheckLogin`** + service 内 `where user_id = 当前登录 id`（AC7 满足）。建议 product 把 doc/11 §8.1 / ticket AC1 的 `gz:user:orders:list` 删除或改注「C 端 @SaCheckLogin」（§9.5 改源头），ADMIN-201 店员端订单查看才走 `@SaCheckPermission`。

### 字段名 camelCase vs snake_case 说明

doc/11 §8.1 表格按文档惯例写 snake_case 列名（`order_no` / `business_type`…），但**全仓 VO wire 格式是 camelCase**（无全局 SNAKE_CASE 配置，Jackson 默认；gz-ord / gz-gacha 现有 VO 均 camelCase）。D10 README §1 也用 camelCase 列字段。故 VO Java 字段名 = wire 字段名 = camelCase，**语义集逐字对齐 §8.1（12 字段不增不减）**。下游 USER-102 / ADMIN-201 按 camelCase 消费。

## AI 自测（≥ 3 代码 block）

### 编译（gz-user -am offline）

```
$ mvn -q -o compile -pl ruoyi-modules/ruoyi-gz-user -am
（无错误输出 = 编译通过）
```

### 单测（6/6）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user -am \
    -Dtest=GzUnifiedOrderServiceImplTest -Dsurefire.failIfNoSpecifiedTests=false
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
[INFO] ruoyi-gz-user ...................................... SUCCESS [  2.200 s]
[INFO] BUILD SUCCESS
```

覆盖：(a) gacha-only 合并 5 字段 + 只查扭蛋表 / (a2) cover image_id 回退 machine.coverImageId / (b) preorder-only 透传原 snapshot + 只查预购表 / (c) all 混合 createdAt DESC 排序（D>B>C>A）/ (d) pageSize 上限 50 截断 + 内存分页第 2 页 / (e) null user 空分页不查库。

### 全链 install（验无循环依赖 + 生产代码全绿）

```
$ mvn -o install -Dmaven.test.skip=true \
    -pl ...gz-common,...gz-user,...gz-ord,...gz-gacha -am
[INFO] ruoyi-gz-common .................................... SUCCESS
[INFO] ruoyi-gz-user ..................................... SUCCESS
[INFO] ruoyi-gz-gacha .................................... SUCCESS
[INFO] ruoyi-gz-ord ..................................... SUCCESS
[INFO] BUILD SUCCESS
```

> 注：首次 `mvn install`（含 test compile）时 `ruoyi-gz-ord` 的 `PreorderFullChainMockTest`（文件日期 Jun 3）testCompile 失败 —— **预先存在、与本 ticket 无关**：该测试对 `GzPayTransactionServiceImpl` 构造器传 raw `PayCallbackDispatcher`，但构造器签名已改为 `ObjectProvider<PayCallbackDispatcher>`。本 ticket 不触碰 gz-ord 任何代码。已用 `-Dmaven.test.skip=true` 验证生产代码全链编译 SUCCESS。**留作对下游/收尾提示**。

## 风险提示 / 已知 issue

- R1：内存分页全量扫两表 — V1.1 数据量小（千级）可接受；上量后 V2 评估物化表 + 分页下推（doc/11 §8.4）。
- R2：gacha `addressSnapshotJson` 开盒时可能为 null（未补地址），VO 原样透传 null，前端需兜底。
- R3（环境 / 非本 ticket）：`ruoyi-gz-ord` 的 `PreorderFullChainMockTest` testCompile 失败（`ObjectProvider` 签名漂移），跑全量 `mvn test` 会被它绊住 —— 需独立修（建议归 D10 收尾或 ord 域 ticket）。

## 对下游 ticket 的提示（USER-102 / ADMIN-201）

1. **统一 VO 字段清单（camelCase，12 字段，钉死）**：
   `orderNo` / `businessType`(`preorder`|`gacha`) / `userId`(string) / `productSnapshotJson`(JSON 字符串) / `totalAmountCent`(分) / `businessStatus` / `logisticsStatus`(`in_japan`|`in_china_dispatching`|`delivered`) / `cnCarrierCode` / `cnTrackingNo` / `addressSnapshotJson`(JSON,可空) / `paidTime` / `deliveredTime` / `createdAt`
2. **business_type 枚举只 `preorder` / `gacha`**（无 `bean`）。
3. **productSnapshotJson 多态**：preorder = 原 product snapshot（`name`/`mainImageId`/`deliveryDateText`…）；gacha = 恰好 5 字段 `{name, cover, spec, machine, rarity}`，`cover` = image_id（FK gz_file_object，**前端换签名 URL**，后端不解析）。USER-102 / ADMIN-201 按 `businessType` 分支渲染。
4. **状态不翻译**：`businessStatus` / `logisticsStatus` 原样透传，UI 状态 chip 映射按 doc/11 §8.2 在前端做。`cnCarrierCode` 走字典 `gz_express_carrier` 渲染中文。
5. **接口路径** `GET /app/gz/user/orders?bizType=&pageNum=&pageSize=`（mp `/app/` 域，非 ticket 卡的 `/api/`）；返标准 `TableDataInfo`（rows/total/code/msg）；`@SaCheckLogin`（C 端，不挂 SaCheckPermission，AC1 偏差见上）。
6. **ADMIN-201 店员端**才用 `@SaCheckPermission`（复用 ADR-0004），且 ADMIN-201 是从 staff 视角看**所有人**订单（非 user_id 归属）—— 不可直接复用本接口的 listByUser，需另开 staff 维度查询。

## §AI 测试段（kevin-qa 自动追加，21:32）

### 后端集成测试（gz-user 全模块）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user -am
[INFO] Tests run: 6   -- GzUserProfileServiceImplTest
[INFO] Tests run: 10  -- GzUnifiedOrderServiceImplTest（USER-101 + USER-102 共 10 个）
[INFO] Tests run: 10  -- GzLogisticsSignServiceImplTest（USER-104）
[INFO] Tests run: 9   -- GzUserAddressServiceImplTest
[INFO] Tests run: 3   -- GzLogisticsSignTxHelperTest（USER-104）
[INFO] Tests run: 38, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
（加上 gz-common 依赖模块 98 个，总计 136 测试全通过）
```

### API 契约回归

```bash
# USER-101: 匿名访问 → 401
curl GET /app/gz/user/orders
# code=401 ✅

# USER-101: 已登录访问 → 200
curl -H "Authorization: Bearer $TOKEN" GET /app/gz/user/orders?pageNum=1&pageSize=5
# code=200, total=0 ✅

# USER-102: 不存在订单 → 403 (无权查看)
curl GET /app/gz/user/orders/PREORD-999999
# code=403 ✅（非本人/不存在统一返回 403，不泄露存在性，AC7 满足）
```

### app 启动 + Flyway（D10 批次头号 gate）

```
[INFO] Successfully validated 55 migrations (execution time 00:00.042s)
[INFO] Schema `ry-vue` is up to date. No migration necessary.
（55 迁移全验证通过，7 个 D10 新迁移已应用；无 checksum 错误、无 Unknown column）
RuoYi-Vue-Plus启动成功
```

DB 验证（gz_logistics_audit 表 + gz_express_carrier 字典）：
```sql
-- gz_logistics_audit 表存在，字段对齐 doc/11 §8.3
DESCRIBE ry-vue.gz_logistics_audit; -- 21 字段 ✅
SELECT COUNT(*) FROM ry-vue.sys_dict_data WHERE dict_type='gz_express_carrier';
-- count=9 ✅（yto/sf/zto/yunda/jd/ems/debang/jitu/other）
```

### 发现并修复的 Bug（Tier 1B 发现，已闭环）

**Bug 1: ConflictingBeanDefinitionException（gz-user 与 gz-ord 均有 GzUnifiedOrderServiceImpl）**
- 现象：`gzUnifiedOrderServiceImpl` bean 名称冲突，app 无法启动
- 修复：gz-user `@Service("gzUserUnifiedOrderServiceImpl")` + gz-ord `@Service("gzOrdUnifiedOrderServiceImpl")`
- 文件：`ruoyi-gz-user/service/impl/GzUnifiedOrderServiceImpl.java` + `ruoyi-gz-ord/service/impl/GzUnifiedOrderServiceImpl.java`

**Bug 2: MyBatis TypeAliasRegistry 冲突（gz-user 与 gz-ord 均有 GzUnifiedOrderVo）**
- 现象：`The alias 'GzUnifiedOrderVo' is already mapped to the value 'org.dromara.gz.user.domain.vo.GzUnifiedOrderVo'`，SqlSessionFactory 初始化失败
- 修复：gz-user VO 加 `@Alias("GzUserUnifiedOrderVo")` + gz-ord VO 加 `@Alias("GzOrdUnifiedOrderVo")`
- 文件：`ruoyi-gz-user/domain/vo/GzUnifiedOrderVo.java` + `ruoyi-gz-ord/domain/vo/GzUnifiedOrderVo.java`

**Bug 3: LambdaQueryWrapper lambda cache miss（GzLogisticsSignServiceImpl 用抽象父类 method ref）**
- 现象：`can not find lambda cache for this entity [GzLogisticsOrderRow]`，USER-104 confirm-receive 500 错误
- 修复：`autoSignTable()` 改用 `new LambdaQueryWrapper<>(clazz)` 传入具体 class（`clazz` 参数），lambda ref 仍用父类方法（继承）
- `confirmReceiveTyped()` 改用 `new QueryWrapper<T>().eq("order_no", orderNo)`（避免同样问题）
- 文件：`ruoyi-gz-user/service/impl/GzLogisticsSignServiceImpl.java`

### 跳过 / 未跑

- USER-104 SnailJob 自动签收任务控制台注册 → 人工操作（代码不自动注册），进 testing-human
- USER-104 mp 真机确认收货端到端（modal 弹窗文案、签收后刷新）→ 真机，进 testing-human
- USER-103 mp 3 态真机人验（需手改 DB 切态）→ Tier 2 人验

### mp vitest（全域回归）

```
$ cd miniapp && pnpm vitest run
 ✓ src/composables/useExpressCarrier.test.ts (19 tests)
 ✓ src/pages/me/order-detail.logic.test.ts (8 tests)
 ✓ src/pages/me/collection.logic.test.ts (25 tests)
 ✓ src/pages/me/orders.logic.test.ts (3 tests)
 ✓ + 30 more test files
 Test Files  34 passed (34)
      Tests  301 passed (301)
   Duration  3.22s
```

### Tier 2 可达性核验（mp tickets）

- USER-101/102/103/104: 会员中心「我的订单」cell → `/pages/me/orders` → 点单卡 → 详情，N=2 可达 ✅
- ADMIN-201: 个人中心门店管理区 → `hasPerm(PERM_ORD_VIEW)` 条件渲染「订单查看」→ `/pages/me/staff-orders/index`，N=2 可达 ✅
- 无 Tier2-entry-temp 标记（所有 D10 mp 票均走业务主线入口或已有入口）✅

### 结论

- ✅ Tier 1B 全通过（3 个 Bug 已 Tier 1B 内闭环修复）
- ✅ ticket 可 close 解锁下游
- mp tickets（USER-101/102/103/104/ADMIN-201）进 progress.md「人验」列待 Kevin 批量人验
- 纯 admin/纯后端（ADMIN-101/102/103）无 Tier 2 人验，AI ✅ 即终态

---

### Tier 1A 补充（coder 已跑，全 ✅）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
[INFO] Tests run: 6  — GzUnifiedOrderServiceImplTest（本 ticket）
[INFO] Tests run: 6  — GzUserProfileServiceImplTest（sibling，未回归）
[INFO] Tests run: 9  — GzUserAddressServiceImplTest（sibling，未回归）
[INFO] Tests run: 21, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

gz-user 全模块 21 测试通过（6 新增 + 15 sibling 无回归）。
