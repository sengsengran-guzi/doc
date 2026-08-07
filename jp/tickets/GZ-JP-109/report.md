# GZ-JP-109 完工报告 — admin 订单管理（只读）

> **结论：accept 两条全 PASS**（ACCEPT1_EXIT=0 / ACCEPT2_EXIT=0）。gz-jp 单测 **167 全绿**（本卡新增 14）。
> **真库端到端已实跑**（重启后的 `:8080`，admin 超管 token）：列表 12 组筛选 + 详情 4 类订单 + **写端点全部打不通**。
> **1 个迁移**（菜单 14020 段）、**无字典**、**无新表**。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（RuoYi `staging` HEAD `47110b805` / plus-ui `staging` HEAD `f313c41`） | ✅ | 开工前两仓 `git status --porcelain` 均空 |
| 上游 GZ-JP-105 已 merge | ✅ | `6618054d6 D4/GZ-JP-105: 订单+订单行建表 + 下单事务 + 支付回调` |
| 上游 GZ-JP-106 已 merge（口径对照方） | ✅ | `47110b805 D5/GZ-JP-106: 履约状态机 + 批量推进/批量发货 API` |
| dev 库有已支付订单（accept[2] 要 `.rows[0]`） | ✅ | 8 张单：6 张 `paid` + 2 张 `created`；10 条商品行 |
| menu 14020 段空闲 | ✅ | `COUNT(*) WHERE menu_id BETWEEN 14020 AND 14029` → **0**；`MAX(menu_id)=14014`（101 占 14000-14005 / 102 占 14010-14014） |
| Flyway append-only | ✅ | `git status --short -- db/migration/` 只有一行 `??`（新增），**无 M/D/R**；时间戳取 `date +V%Y%m%d%H%M` = `V202608071027` |
| dict 不新建 | ✅ | 复用 105 已 seed 的 `gz_jp_order_status`(9282) / `gz_jp_fulfill_status`(9284) / `gz_jp_refund_status`(9285) + 既有 `gz_express_carrier`(9130)。**本卡零 dict**（重 seed 会撞 `dict_code` 主键） |
| 编译基线 | ✅ | 动手前 `mvn -o compile -pl ruoyi-gz-jp -am` → BUILD SUCCESS |
| 权威蓝图已读 | ✅ | `ui-index.yaml` `UI:admin.order`；`field-ssot.yaml` `gz_jp_order`（含 `id_range: "menu 14020 订单管理 + 14021-14029 按钮"`）；`requirements.yaml` REQ-ORDER-006 / REQ-FULFILL-001 / REQ-ORDER-004 |
| ADR | 本域无 ADR；沿用 106 的「服务层批量补人信息」范式与 105 的快照读法 |

**蓝图关键约束摘录**：
- `UI:admin.order`「**只读**查询列表 + 详情抽屉。列：订单号 / 客人 / 款数 / 实付 / 订单状态 / 下单时间。详情抽屉展示订单头 + 逐行商品及其履约状态（**只读，推进操作在履约看板做**）」
- `field-ssot gz_jp_order`「`id_range: menu 14020 订单管理 + 14021-14029 按钮`」「`total_amount_cent` = Σ 行金额，**★ 无运费项**」
- `REQ-ORDER-006`「后台客人付款过后（要可以看到货品的状态）」；`REQ-ORDER-004`「系统中彻底不做运费概念」

**开工时踩到的一个环境坑（记下来省下一个人的时间）**：`sys_menu` **没有 `tenant_id` 列**（菜单是全局的）。§0 自检拿旧模板套 `SELECT ... tenant_id FROM sys_menu` 会报 `ERROR 1054 Unknown column`，而 `docker exec ... 2>/dev/null` 会把这个错吞掉、**只剩一个空白输出**——看起来就像「14000 段一条菜单都没有」。差点据此误判段位全空。查 `sys_menu` 别带 `tenant_id`，且排查阶段**先别急着 `2>/dev/null`**。

## 实现摘要（2 改 + 10 新增）

```
后端 RuoYi-Vue-Plus
 M domain/enums/GzJpOrderStatus.java              +18   ← 加 isValid()（筛选值校验，镜像 GzJpFulfillStatus.isValid）
 M mapper/GzJpOrderItemMapper.java                +25   ← 加 selectStatsByOrderIds（款数/件数聚合）
?? db/migration/V202608071027__GZ-JP-109-seed-menu.sql   ← 菜单 14020/14021 + 角色 100/101 授权
?? controller/GzJpOrderController.java                   ← ★ 只有 2 个 @GetMapping
?? service/{IGzJpOrderAdminService, impl/GzJpOrderAdminServiceImpl}.java
?? domain/bo/GzJpOrderQueryBo.java
?? domain/dto/GzJpOrderItemStat.java
?? domain/vo/{GzJpOrderAdminVO, GzJpOrderAdminDetailVO, GzJpOrderAdminItemVO}.java
?? test/.../GzJpOrderAdminQueryTest.java                 ← 14 个用例

前端 plus-ui
 M src/lang/zh_CN.ts   +50   ← gzJpOrder 块
 M src/lang/en_US.ts   +50
?? src/api/gz-jp/order.ts
?? src/views/gz-jp/order/index.vue
```

**零改动区**：`GzJpOrderServiceImpl`（客人写路径）/ `GzJpFulfillServiceImpl` / `JpPayCallbackHandler` / 任何既有迁移 / 任何 GZ-PAY 代码 / 拼豆·回收·预购·扭蛋一行未动。

### ★ 本卡唯一容易翻的车：口径与履约看板相反

106 反复强调「查 `gz_jp_order_item` **必须**过滤 `isPaidLike`，漏了 = 店员拿没付钱的单去日本下单」。
**本页刻意不加这道闸**，因为两页服务的是不同问题：

| | GZ-JP-108 履约看板 | GZ-JP-109 订单管理（本卡） |
|---|---|---|
| 视角 | 店员**采购**视角 | **资金**视角查单 |
| 行 = | 商品行 | 订单 |
| 付款态过滤 | **硬编码只出 paid/partial_refunded/refunded**，不可关 | **无过滤**，created / cancelled 必须出 |
| 漏了会怎样 | 拿没付钱的单去日本下单（赔钱） | 客人问「我那单怎么不见了」后台答不出（那单往往正是没付成功的） |

这条口径在三个地方各钉了一遍，防后来者顺手抄：`GzJpOrderQueryBo` 类注释、`GzJpOrderItemMapper.selectStatsByOrderIds` 方法注释、单测 `listMustIncludeUnpaidAndCancelledOrders`（**不但断言 created/cancelled 能出，还断言生成的 SQL 里根本没有 `business_status`** —— 有条件才可能是偷偷加的闸）。

### 三个实现决定

1. **不复用 mp 的 `GzJpOrderListItemVO` / `GzJpOrderDetailVO`，另建 admin VO**。admin 要客人身份（昵称/手机/编号）+ 支付流水（商户单号/微信交易号/手续费）+ 内部备注 + 取消时间，**这些一个字节都不能给客人**；mp 要的商品缩略图 admin 列表又用不上。混一个 VO 加开关，迟早漏内部字段给客人。
2. **分页只查订单表，客人信息与款数事后批量补**（`selectVoMapByIds` ×1 + `selectStatsByOrderIds` ×1）。join 用户表会把 total 算复杂，而用户表在 gz-common —— 跨模块写 JOIN 是本项目一贯避免的。款数走 `GROUP BY order_id` 聚合而不是把行捞回来数：一单可 30+ 款，20 条一页就是 600 行白读，而列表只显示两个数字。
3. **订单号用 LIKE 不用精确**（与 106 看板的 `orderNo` 精确匹配不同）。真实场景是客人在电话里报「后面几位是 000123」，店员记不住 `JPO-20260807-` 前缀。拼团单量级不大，不为这点索引效率牺牲查单页最主要的使用方式。

### AC「列表与详情均只读，无写操作按钮」的四道落点

不是靠「我没写」，而是四处可验证：

1. `GzJpOrderController` 只有 2 个 `@GetMapping`，无 POST/PUT/DELETE/PATCH，也不用裸 `@RequestMapping`
2. `IGzJpOrderAdminService` 只有 `selectAdminPage` / `getAdminDetail`
3. 迁移只 seed 一个权限位 `gz:jp:order:list`（**没有 add/edit/remove**）—— 前端就算写了写按钮也没权限位可挂
4. Vue 页面唯一的行操作是「详情」，抽屉里全是 `el-descriptions` / 只读 `el-table`
5. **单测把 1、2 变成断言**（`controllerExposesNoWriteEndpoint` / `serviceExposesNoWriteMethod`）—— 以后谁加写方法立刻红

## AI 自测（Tier 1A）

### 1. 编译 + 全量单测（167 绿，本卡新增 14）

```
$ mvn -o compile -pl ruoyi-modules/ruoyi-gz-jp -am
[INFO] BUILD SUCCESS

$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp
Tests run: 13, ... GzJpShipRequireTrackingTest
Tests run: 14, ... GzJpOrderAdminQueryTest          ← ★ 本卡
Tests run: 21, ... GzJpOrderSubmitTest
Tests run: 20, ... GzJpProductServiceTest
Tests run: 17, ... GzJpEventStatusTest
Tests run: 38, ... GzJpCartServiceTest
Tests run: 18, ... GzJpFulfillStateMachineTest
Tests run: 20, ... GzJpProductMpQueryTest
Tests run:  6, ... GzJpPayCallbackTest
[INFO] Tests run: 167, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

本卡 14 个用例的自述输出：
```
[★口径] 未加任何筛选 → 返回 [paid, created, cancelled]（待支付 / 已取消都在，没有被 isPaidLike 吃掉）
[★口径] 生成 SQL 片段不含 business_status： ORDER BY id DESC
[筛选] SQL 片段 = (order_no LIKE #{...MPGENVAL1} AND business_status IN (#{...2},#{...3})
                  AND create_time >= #{...4} AND create_time <= #{...5}) ORDER BY id DESC
[非法值] 非法的订单状态筛选值：shipped（未读库）
[批量] 2 单 → selectStatsByOrderIds ×1 / selectVoMapByIds ×1（无 N+1）
[兜底] 无商品行订单 itemCount=0 / totalQty=0
[关键词] 无匹配 → total=0 且未读订单表（不退化成全量）
[交集] userId=14 不在 keyword 命中的 [15,16] 里 → 空结果
[详情] JPO-20260807-000003 | 客人=小王 | 商户单号=JPO-20260807-000004
       | 行=柯南 吧唧 A赏（发货完毕 / 顺丰速运 SF7654321000）
[降级] 快照损坏 → 行名回落「商品」，详情照常打开
[未支付] 详情可打开，商户单号为空且未去查流水
[降级] 支付流水读失败 → 详情主体仍可用（店员至少看得到货和地址）
[不存在] 订单不存在
[★AC] IGzJpOrderAdminService 方法 = [selectAdminPage, getAdminDetail]（全读）
[★AC] GzJpOrderController 只有 2 个 GET，零写端点
```

### 2. accept[1] 菜单 path/component 非空且父级有效 ✅

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
    SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14020 AND 14029
    AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
       OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
       OR (m.parent_id<>0 AND NOT EXISTS
           (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)) )" | grep -qx 0 &&
  docker exec ... "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14020 AND 14029" | grep -qE '^[1-9]'
ACCEPT1_EXIT=0
```
落库明细 + 全 jp 菜单树（确认挂对父级、不侵占 108 的 14030 段）：
```
menu_id  menu_name  parent_id  order_num  path   component           menu_type  visible  perms
14020    订单管理    14000      3          order  gz-jp/order/index   C          0        gz:jp:order:list
14021    订单查询    14020      1          ''     ''                  F          0        gz:jp:order:list

sys_role_menu: (100,14020) (100,14021) (101,14020) (101,14021)

14000 日本拼团  (M)                14010 商品管理 gz:jp:product:list
14001 场管理   gz:jp:event:list    14011-14014 商品按钮
14002-14005 场按钮                 14020 订单管理 gz:jp:order:list   ← 本卡
                                   14021 订单查询 gz:jp:order:list   ← 本卡
```
Flyway 真应用（非手工建）：
```
202608071027  V202608071027__GZ-JP-109-seed-menu.sql  success=1
启动日志: Migrating schema `ry-vue` to version "202608071027 - GZ-JP-109-seed-menu" [out of order]
          Successfully applied 1 migration to schema `ry-vue`, now at version v202608071027
          Started DromaraApplication in 12.246 seconds
```

### 3. accept[2] 订单列表返回行内容完整 ✅

```
$ TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"admin123","grantType":"password","tenantId":"1001",
         "clientId":"e5cd7e4891bf95d1d19206ce24a7b32e"}' | jq -r '.data.access_token'); \
  curl -s 'http://localhost:8080/system/gz/jp/order/list' \
    -H "Authorization: Bearer $TOKEN" -H 'clientid: e5cd7e4891bf95d1d19206ce24a7b32e' \
    | jq -e '.rows[0] | has("orderNo") and has("totalAmountCent") and has("businessStatus") and has("itemCount")'
ACCEPT2_EXIT=0
```
`.rows[0]` 全字段（ID 全 string、金额整数分、状态中文后端已给）：
```json
{ "id": "29", "orderNo": "JPO-20260807-000046", "userId": "14",
  "userNickname": "JP105 测试", "userMobile": "13800000000", "userNo": "U20260806000003",
  "itemCount": 1, "totalQty": 20, "totalAmountCent": 100000,
  "businessStatus": "created", "businessStatusLabel": "待支付",
  "createTime": "2026-08-07 09:30:04", "paidTime": null, "cancelledTime": null }
```

### 4. ★ 真库端到端（重启后的 `:8080`，admin 超管 token）

**A) 默认列表 —— 待支付单正常出现在第一位**
```
total=8
  JPO-20260807-000046  待支付   款数=1 件数=20  实付=100000  客人=JP105 测试  下单=2026-08-07 09:30:04
  JPO-20260807-000044  待支付   款数=2 件数=2   实付=11000   ...
  JPO-20260807-000042  已支付   款数=1 件数=3   实付=15000   ...
  JPO-20260807-000040 / 000038 / 000036 / 000003 / 000001  已支付
```

**★ B) 已取消单必须查得到 —— 与履约看板同数据对照**（临时造一张 `cancelled` 单，验完硬删）
```
订单管理:  JPO-20260807-909109  已取消  款数=2 件数=3 实付=7700 取消于=2026-08-07 09:59:00   ← 查得到
履约看板:  total=0   ← 同一张单在 /system/gz/jp/fulfill/list?orderNo=... 查不到
          （未支付/已取消的行不进采购清单 —— 两页口径不同，正是本卡设计意图）
```

**C) 筛选 12 组**
```
状态多选（三种线格式都要能绑，因为 plus-ui tansParams 发的是索引式）：
  索引式 businessStatus[0]=created&businessStatus[1]=cancelled → total=3  ["cancelled","created"]
  重复名 businessStatus=created&businessStatus=cancelled       → total=3  ["cancelled","created"]
  逗号式 businessStatus=created,cancelled                      → total=3  ["cancelled","created"]
  只看 paid                                                    → total=6  ["paid"]
  非法值 shipped                                               → code=500 非法的订单状态筛选值：shipped
订单号 / 客人 / 时间段 / 分页：
  orderNo=909109（后 6 位模糊）        → total=1  ["JPO-20260807-909109"]
  orderNo=20260807-0000（前缀）        → total=8
  keyword=JP105（命中客人）            → total=9
  keyword=查无此人（★ 不退化成全量）    → total=0
  beginDate=endDate=2026-08-07         → total=9
  beginDate/endDate=2026-08-01..02     → total=0
  pageNum=2&pageSize=3                 → total=9 本页=[000042, 000040, 000038]
```

**D) 详情 4 类订单**
```
已支付单 id=2（一单跨两场 + 已发货行 + 支付流水）:
  orderNo=JPO-20260807-000003  已支付  itemCount=2 totalQty=5 totalAmountCent=46000
  客人=JP105 测试 / 13800000000 / U20260806000003
  payTransactionId=33  outTradeNo=JPO-20260807-000004  wxTransactionId=mock_wx_txn_...  payStatus=paid
  地址快照: 张三 13800000000 四川省 成都市 锦江区 春熙路 1 号
  行1: JPP-20260807-000001 柯南 吧唧 一番赏 A赏 | 场=8月上旬快闪场 | ×2 | 25600
       | 发货完毕 | 顺丰速运 SF7654321000 | 2026-08-07 10:05:23
  行2: JPP-TMP105-000001 GZ-JP-105 第二场商品 | 场=GZ-JP-105 第二场（多场同单验证） | ×3 | 20400
       | 发货完毕 | 顺丰速运 SF7654321000
       ★ 该商品与场都已被 105 软删，名称仍完整 —— 读快照不回查商品表，抗删除

未支付单 id=27:  待支付 / paidTime=null / payTransactionId=null / outTradeNo=null
                 且【未去查支付流水】；2 行均「购买中」、无运单号 → 详情照常打开
已取消单 id=9109: 已取消 / cancelledTime / userNote / remark 都在；含 mainImageId=null 的行（前端渲染占位）
不存在 id=999999: {"code":500,"msg":"订单不存在"}
```

**★ E) AC「无写操作」—— 写端点全部打不通，数据零变化**
```
  POST   /system/gz/jp/order    → 404 请求地址不存在
  PUT    /system/gz/jp/order    → 404 请求地址不存在
  DELETE /system/gz/jp/order    → 404 请求地址不存在
  PATCH  /system/gz/jp/order    → 404 请求地址不存在
  DELETE /system/gz/jp/order/2  → 405 Request method 'DELETE' is not supported

写尝试后：gz_jp_order 行数=9 / del_flag=1 的行数=0
          gz_jp_order_item 行数=12 / version 之和=12   ← 一行没被碰过
```

**F) 权限三处一致 + 未登录 401**
```
controller  @SaCheckPermission("gz:jp:order:list")  ×2（list / getInfo）
sys_menu    menu_id=14020 perms=gz:jp:order:list
            menu_id=14021 perms=gz:jp:order:list
plus-ui     v-hasPermi="['gz:jp:order:list']"
未登录访问  → 401 认证失败，无法访问系统资源
```

**G) 临时验证数据已硬删（★ 不软删 —— 软删行会被 accept 的全表扫描看到，且 105 的 booking_no 教训同理）**
```
残留临时订单=0 / 残留临时行=0 / 软删残留=0
清理后回到基线: gz_jp_order=8 / gz_jp_order_item=10（与开工前一致）
```

### 5. 前端

```
$ npx vue-tsc --noEmit
本卡 4 个文件（views/gz-jp/order/index.vue、api/gz-jp/order.ts、lang/zh_CN.ts、lang/en_US.ts）→ 0 错误
（仓库存量 72 个 TS 错误全在 workflow / system / components 等本卡未碰的文件里，与本卡无关）

$ npx eslint <本卡 4 文件>
MY_FILES_ESLINT_EXIT=0
（另有 en_US.ts:896 一处 prettier 报错在 gz-bean 既有文案里，本卡 diff 从第 2360 行才开始，非本卡引入）

$ pnpm build:prod
构建成功；grep 产物确认本卡页面已打进 dist：
  dist/assets/index-BFPAMfs4.js 含 "system/gz/jp/order/list" 与 "GZ-JP-109"
```

## 风险提示 / 已知 issue

1. **列表的「实付」列名义上是订单成交额，未支付 / 已取消的单同样有金额但钱没到账**。这是资金视角页天然的歧义点，已在 VO 注释与页面顶部 `el-alert` 里写明「判断有没有收到钱看订单状态」。若甲方反馈店员看混了，最小改法是给非 `paid*` 状态的金额加灰色/删除线，**不要改成 0**（那会让「这单本来该收多少钱」这个信息消失）。
2. **`keyword` 匹配的是昵称 / openid，不含手机号**（`IGzUserService.selectIdsByKeyword` 的既有实现口径）。列表里**显示**了手机号但**搜不了**手机号，店员大概率会试着搜。要支持得改 gz-common 的检索实现（会同时影响 106 看板与其他域），**属独立小 ticket，不在本卡偷偷改**。
3. **订单号用 LIKE `%?%`，`uk_order_no` 索引在「后几位模糊」时用不上**。拼团单量级（当前 8 单，一期预期百量级）下无所谓；若将来单量上万且查单变慢，改成「纯数字输入自动加 `JPO-%` 前缀」即可命中索引，不必改接口契约。
4. **`payFeeCent` 目前恒为 null**：mock 支付通道不回传手续费，真实微信回调才有值。页面显示 `-`，不是 bug。
5. **Flyway 判本卡迁移为 `[out of order]`** —— 因为仓里存在 14 位时间戳的既有迁移（`V20260703162955__GZ-BEAN-*`），数值上大于 jp 域一贯的 12 位（`V202608071027`）。**这是本仓存量的位数不一致，不是本卡引入**（105/106 的迁移同样被判 out of order）；`out-of-order: true` 已开（CLAUDE.md §5），正常补跑。**下游 jp ticket 继续用 `date +V%Y%m%d%H%M` 即可，不要为了「排到最大」手填 14 位**——那会把不一致扩散得更远。
6. **本卡重启了 `:8080`**。重启前该实例跑的是 07:18 启动的**旧 jar**，连 GZ-JP-106 的 `/system/gz/jp/fulfill/*` 都是 404，所以不存在并行 agent 依赖它的可能。已 `mvn -o clean install`（gz-common + gz-user + gz-jp）后重启，**现在 8080 上同时有 106 与 109 的最新代码**，对并行的 108 只会更好用。实例保持运行（本来就在跑）。
7. **待 Kevin 残留人验：N/A** —— 纯 admin 页，不碰真机微信原生能力，非 mp 新页首版视觉。按 CLAUDE.md §8.2「纯 admin ticket → 仅 Tier 1A + 1B，close 即终态」。

## 对下游 ticket 的提示

### 给 GZ-JP-108（admin 履约看板）—— 两页在同一个菜单目录下并排

- **菜单段位**：本卡占 **14020 / 14021**，`14022-14029` 仍空但归订单管理按钮；**你的 14030 段完全没被碰过**，`order_num` 我用了 3（场=1 / 商品=2 / 订单=3），看板建议用 4 或插在 3 前面。父目录 `14000` 由 101 建好，**两卡都别重建**。
- **可直接照抄的 UI 骨架**：`plus-ui/src/views/gz-jp/order/index.vue` 的查询条（订单号 / 客人 keyword / 状态多选 `collapse-tags` / `daterange` 拆 `beginDate`+`endDate`）与 `el-drawer` 详情，和你要的看板筛选几乎同构。差别是你的表格行 = 商品行且要 `type="selection"` + 批量操作条。
- **★ 数组型 GET 参数已实测**：plus-ui 的 `tansParams` 把 `string[]` 序列化成 `businessStatus[0]=a&businessStatus[1]=b`（**索引式，不是重复参数名**）。三种格式（索引式 / 重复名 / 逗号分隔）**都能绑到 Spring 的 `List<String>`**，本卡真库逐一验过。所以 106 文档里写的 `fulfillStatus=a&fulfillStatus=b` 和前端实际发的索引式**都对**，不用改任何一边。
- **两页的口径差异要在 UI 上说清**：你的看板只出付过款的行，客人问「我的单呢」时店员在看板上查不到——**看板的空结果提示建议引导到订单管理页**（「没找到？该单可能未支付，去订单管理查」）。反过来本页详情的商品行是只读的，页面里已经写了「推进状态 / 发货请去履约看板」。
- **列表页跳转**：本页列表行的 `orderNo` 是纯文本没做跳转。若你想从看板点订单号跳到订单详情，本页详情端点是 `GET /system/gz/jp/order/{id}`（`id` 用看板行的 `orderId`），权限同为 `gz:jp:order:list`——**看板角色若没授该权限，跳过去会 403**，要么给 101 也授（本卡已给 100/101），要么在看板里内嵌简版订单信息。

### 给 GZ-JP-107（行级退款）

- 退款 rollup 把订单打成 `partial_refunded` / `refunded` 后，**本页无需任何改动**：`GzJpOrderStatus.labelOf` 已覆盖这两个态、字典 9282 已 seed、列表筛选下拉自动多出两项。
- 行级 `refundStatus` / `refundAmountCent` 本页详情**已经在展示**（`GzJpOrderAdminItemVO.refundStatus/refundStatusLabel/refundAmountCent`），你只要把值写进库即可，前端不用动。
- 若退款后要在**列表**上体现「这单退了多少」，那是新增列，**属你的 ticket 范围**（本页列表刻意只有 6 列，按 `UI:admin.order` 原文）。

### 给后续维护者：本卡端点契约

```jsonc
GET /system/gz/jp/order/list?pageNum=1&pageSize=20        // 权限 gz:jp:order:list
    &orderNo=000123                                        // ★ 模糊（LIKE %?%）
    &userId=14 | &keyword=小王                             // keyword 匹配昵称/openid；无匹配 total=0（不退化全量）
    &businessStatus=created&businessStatus=cancelled       // 多选；非法值 → 500 报错不静默丢弃
    &beginDate=2026-08-01&endDate=2026-08-07               // 按【下单时间】，含首尾整天
// ★ 读 res.rows（TableDataInfo）不是 res.data
// ★ 不过滤付款状态 —— created / cancelled 必出
{ "rows":[{ "id","orderNo","userId","userNickname","userMobile","userNo",
            "itemCount","totalQty","totalAmountCent",
            "businessStatus","businessStatusLabel",
            "createTime","paidTime","cancelledTime" }], "total":8 }

GET /system/gz/jp/order/{id}                              // R<GzJpOrderAdminDetailVO>，读 res.data
{ "id","orderNo","totalAmountCent","businessStatus","businessStatusLabel","itemCount","totalQty",
  "createTime","paidTime","cancelledTime","userNote","remark",              // remark = 内部备注，不下发 mp
  "userId","userNickname","userMobile","userNo",
  "payTransactionId","outTradeNo","wxTransactionId","payStatus","payFeeCent",  // ★ 内部运营信息
  "address":{recipient,mobile,province,city,district,detail},                  // 下单锁定的快照
  "items":[{ "id","productId","productNo","name","mainImageId",                // ★ mainImageId 是 file id 不是 URL
             "eventName","deliveryDateText","noticeText",
             "qty","unitPriceCent","amountCent","source",
             "fulfillStatus","fulfillStatusLabel",
             "carrierCode","carrierLabel","trackingNo","shippedAt",
             "refundStatus","refundStatusLabel","refundAmountCent" }] }
// 订单不存在 / 已软删 → 500「订单不存在」
// ★ 没有任何写端点。要改状态去 /system/gz/jp/fulfill/{advance,ship}
```

### 编号段位现状

| 资源 | 已占 | 下一个空号 |
|---|---|---|
| `sys_menu` GZ-JP | 14000-14005（101）、14010-14014（102）、**14020-14021（本卡）** | 14022-14029（订单按钮预留）/ **14030 段仍全空，归 108** |
| `dict_id` / `dict_code` | 9280-9285 / 92801-92821；**本卡未占** | 9286 / 92822 |
| jp 业务错误码 | 4101-4107（105）、4108-4110（106）；**本卡未占**（只读页不需要业务码，非法筛选值走通用 500） | **4111** |
| Flyway | …**V202608071027（本卡）** | `date +V%Y%m%d%H%M` |

### 全 jp 域通用（本卡新增 / 再次踩到）

- **`sys_menu` 没有 `tenant_id` 列**（菜单全局）。查它别带 `tenant_id`，否则 `ERROR 1054`；配上 `2>/dev/null` 会静默成空输出，看起来像「一条都没有」→ 会误判段位空闲/已占。**排查阶段先别 `2>/dev/null`**。
- **`PageQuery` 的构造器是 `(pageSize, pageNum)`**（不是 `(pageNum, pageSize)`，也没有无参构造器）。单测里写反了顺序不会编译失败，只会让分页断言诡异。
- **plus-ui `tansParams` 把数组序列化成索引式 `k[0]=&k[1]=`**（不是重复参数名）。Spring 的 `List<String>` 三种格式都能绑，实测过，不必为它改后端。
- 改 gz-jp 后必须 **`mvn -o clean install`** 再重启（`spring-boot:run` 加载的是 `~/.m2` 的 jar，不是 `target/classes`）。本卡开工时 8080 上跑的旧 jar 连 106 的端点都 404，就是这个原因。
- 单测类必须 `@Tag("dev")`；用 `Wrappers.lambdaQuery()` 且要断言 `getSqlSegment()` 时，`@BeforeAll` 要 `TableInfoHelper.initTableInfo(...)`。
- **临时验证数据一律 HARD DELETE 不软删**（软删行仍会被 accept 的全表扫描 / `SELECT COUNT(*)` 看到）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

建议覆盖：
- **admin Playwright E2E**（本卡有 admin 页面，是 Tier 1B 的主对象）：admin 登录 → 侧边栏「日本拼团 → 订单管理」路由可达（`/gz-jp/order`，component `gz-jp/order/index`）→ 列表渲染 8 行 → 逐项筛选（订单号模糊 / 客人关键词 / 状态多选 / 日期区间 / 重置）→ 点「详情」抽屉打开、三段（订单头 / 支付流水 / 收货地址）+ 商品表格渲染 → **★ 断言页面上不存在任何写按钮**（无新增/编辑/删除/推进/发货）→ 关闭抽屉。⚠️ 侧边栏动态路由需**重新登录**才刷新菜单（本卡刚 seed 菜单）。
- **API 契约回归**：字段名与本报告「本卡端点契约」段逐字一致；ID 全 string；列表返 `rows` 不是 `data`；金额整数分。
- **★ 口径回归（本卡最该守的）**：同一批数据下 `/system/gz/jp/order/list` 的 total > `/system/gz/jp/fulfill/list` 的 total，且前者含 `created`/`cancelled` 行、后者不含。
- **只读回归**：`POST/PUT/DELETE/PATCH /system/gz/jp/order` 全部 404/405 且 `gz_jp_order` / `gz_jp_order_item` 行数与 version 之和不变。
- **跨域回归**：本卡未动写路径，`POST /app/gz/jp/order` 下单 + 支付回调 + `/system/gz/jp/fulfill/advance|ship` 应完全不受影响（167 单测已覆盖，建议再跑一次真库冒烟）。
- **权限**：非 owner/staff 角色调本端点应 403（本卡只授 100/101）。

⚠️ 跑前确认 8080 上是本卡 `mvn -o clean install` 后的 jar（已装，实例在跑）。

---

**环境交还**：`:8080` 保持运行（重启前后都在跑，现载有 106+109 最新 jar，日志 `/tmp/gzjp109-app.log`）；未起 `:8081`；plus-ui dev server 未启动。临时验证数据已硬删（残留 0，DB 回到 8 单 / 10 行基线）。测试脚本未落项目目录。**未 commit**。

**accept 两条：PASS**（ACCEPT1_EXIT=0 / ACCEPT2_EXIT=0）。
