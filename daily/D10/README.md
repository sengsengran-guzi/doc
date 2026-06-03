# D10 — V1.1 订单聚合 + admin 三件套 + mp 订单查看下沉

> 阶段：V1.1 实施期（软期限 7/31，不绑日历日）
> 主题：**订单聚合统一接口 + mp 订单详情/物流/收货 + admin 预购商品/扭蛋池/订单管理三件套 + mp 店员端订单查看下沉**
> 上一日：D09（GZ-ORD-104 预购订单管理 + GZ-GACHA-104 扭蛋衍生订单管理）｜ 下一日：D11（物流推进下沉 mp + 对账中心 ⭐ + 看板 + 回收站）

---

## 今日目标

- **主线 1（mp 订单串行链）**：USER-101 订单聚合统一接口（service 层 UNION）→ USER-102 mp 订单详情统一页 → USER-103 mp 物流 C1 2 态展示（只读侧）→ USER-104 确认收货 + 自动签收
- **主线 2（admin 并行三件套，plus-ui）**：ADMIN-101 预购商品 CRUD + ADMIN-102 扭蛋池管理 + ADMIN-103 订单管理（三类聚合）
- **主线 3（mp 下沉，依赖 1+2）**：ADMIN-201 mp 店员端订单查看（复用 ADR-0004 权限底座，店员手机看预购 + 扭蛋订单列表/详情只读）

完工后：
- C 端用户在 mp「我的订单」一屏看到预购 + 扭蛋两类订单（按业务类型 tab 切，时间倒序），点进详情看物流 2 态 + 国内单号 + 复制按钮，到货可主动「确认收货」（或 7 天自动签收）
- admin owner 在 plus-ui 管理预购商品（CRUD + Excel 导入导出）、配置扭蛋池（权重前端实时归一化）、聚合查看三类支付订单（走 `gz_pay_transaction` 按 `business_type` 回查业务订单表）
- 店员用手机登 mp 即可只读查看预购 + 扭蛋订单（不必开 plus-ui 电脑后台）

## Ticket 清单（8 个，按依赖顺序）

| Ticket | 标题 | 端 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| GZ-USER-101 | 订单聚合统一接口（service 层 UNION） | 后端 | M | GZ-ORD-104 + GZ-GACHA-104 | pending |
| GZ-USER-102 | mp 订单详情统一页 | mp | M | GZ-USER-101 | pending |
| GZ-USER-103 | mp 物流 C1 2 态展示（只读侧，admin 写入由 D11 ADMIN-104） | mp | M | GZ-USER-102 | pending |
| GZ-USER-104 | 确认收货 + 自动签收（SnailJob） | mp + 后端 | S | GZ-USER-103 | pending |
| GZ-ADMIN-101 | 预购商品 CRUD（plus-ui，menu 9100 段） | admin | M | GZ-ORD-101 | pending |
| GZ-ADMIN-102 | 扭蛋池管理（plus-ui，menu 10100 段，权重前端归一化） | admin | M | GZ-GACHA-101 | pending |
| GZ-ADMIN-103 | 订单管理三类聚合（plus-ui，走 gz_pay_transaction 回查） | admin | M | GZ-ORD-104 + GZ-GACHA-104 | pending |
| GZ-ADMIN-201 | mp 店员端订单查看（下沉，复用 ADR-0004 底座） | mp | M | GZ-USER-101 + GZ-ADMIN-103 + GZ-SYS-007 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图**：

```
USER-101 ─→ USER-102 ─→ USER-103 ─→ USER-104          （mp 串行链）
   │                                                   （物流写入侧在 D11 ADMIN-104；本日 USER-103 只做 mp 读取 + 渲染）
   │
   ├──────────────┐
   ▼              ▼
ADMIN-101 ┐   ADMIN-201（依赖 USER-101 统一接口 + ADMIN-103 聚合口径 + SYS-007 权限底座）
ADMIN-102 ├ 并行（admin 三件套互不依赖，独立 spawn）
ADMIN-103 ┘
```

## 派单方式

```
开始 d10                          # 主线程读本 README，按依赖图自动跑
开始 d10/GZ-USER-101              # 单 ticket 启动
```

主线程动作：
1. 读 D10/README.md + 依赖图
2. **§0 自检先 grep migration 目录** 确认 `gz_ord_order` / `gz_gacha_order` / `gz_pay_transaction` 表的迁移文件实际存在（见下「与昨日 reports 对账」），缺则 STOP 报 Kevin
3. **第一波并行 spawn**：USER-101（串行链头）+ ADMIN-101 + ADMIN-102 + ADMIN-103 四条线同时起
4. USER-101 ✅ → spawn USER-102 → ✅ → USER-103 → ✅ → USER-104（串行）
5. USER-101 + ADMIN-103 + SYS-007（D7x 已交付）齐备 → spawn ADMIN-201
6. 8 ticket 全部 Tier 1A + 1B ✅ → mp ticket（USER-102/103/104 / ADMIN-201）进 progress.md「人验」列；纯 admin（ADMIN-101/102/103）AI ✅ 即终态

或显式分派：

```
@coder 做 D10/GZ-USER-101
@coder 做 D10/GZ-USER-102        # 上一个完工后
@coder 做 D10/GZ-ADMIN-101       # admin 三件套可并行 spawn
@coder 做 D10/GZ-ADMIN-201       # USER-101 + ADMIN-103 完工后
```

---

## 今日特殊约束

### 0. 删假 OK + 不绑日历日 — V1.1 从零起

⚠️ **不要把 ruoyi-gz-ord / ruoyi-gz-gacha 当已交付**。截至本日，这两个模块是**空脚手架**（各 1 个 HelloController），`gz_ord_*` / `gz_gacha_*` / `gz_recon_*` 表**全部不存在**，plus-ui 这两个域只有 Hello.vue。V1.1 所有业务表 + 接口从零建（由 D08/D09 的 ORD-101~104 / GACHA-101~104 建）。

- **§0 自检改为 grep migration 目录实际存在的表**，不假设上游 ticket 已 merge：
  ```bash
  ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'GZ-ORD|GZ-GACHA'
  grep -rl 'gz_ord_order|gz_gacha_order' code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
  ```
  对应迁移文件 + 表 DDL 在 → 才能开工；缺 → STOP 回 D08/D09 收尾，本日不开工。
- **V1.0 现状 = 「已通过 AI 测试，但未客户验收、未上线」**（不是「已上线运行 1-2 周」）。任何回切 V1.0 行为的改动需评估对未验收基线的影响。
- **本日不绑日历日**（不写 6/16-6/19）。V1.1 软期限 7/31，按依赖顺序推进。

### 1. 订单聚合实现口径 = service 层 UNION（doc/11 §8.1 已同步）

USER-101 的聚合**在 service 层做**：并发查 `gz_ord_order`（预购）+ `gz_gacha_order`（扭蛋）两表，各自映射为统一 VO，合并后按 `business_type` + 时间倒序排序 + 分页。

- **不创建 `gz_unified_order_view` 物理视图 / 物化视图**：V1.1 数据量小（千级），service 层合并即可（doc/11 §8.1 字段定义是逻辑视图，不强制物理化）
- 统一 VO 字段名严格对齐 doc/11 §8.1：`orderNo` / `businessType`(`preorder`/`gacha`) / `productSnapshot` / `totalAmount`（_cent 口径，前端转元）/ `businessStatus` / `logisticsStatus` / `cnCarrierCode` / `cnTrackingNo` / `addressSnapshot` / `createdAt` / `paidTime` / `deliveredTime`
- **扭蛋分支 productSnapshot 合并**：把 `gz_gacha_order` 的奖品 snapshot 拍平成统一形状 `{name, cover(image_id 解析), spec, machine(扭蛋机名), rarity(稀有度)}`；预购分支 `{name, cover, spec}`。前端按 `businessType` 分支渲染。
- snapshot 一律读 `*_snapshot_json`（JSON 列），图片走 `image_id` / `*_image_ids` 解析（不存裸 url）

### 2. C1 跨境物流 = 2 态 + 终态（不是 7 节点）⚠️ 一票否决

doc/10 §8 物流权威状态（C1 裁定）+ doc/11 §8.1 物流字段 + doc/12 §MP-ORD-DETAIL 三处一致：跨境物流 V1.1 = **2 态 + 终态**，`logistics_status` 取值 `in_japan` / `in_china_dispatching` / `delivered`。

- `logistics_status` **独立于 `business_status`** 并行存在，不互相覆盖（扭蛋订单可 `business_status=drawn` + `logistics_status=in_japan` 同时存在）
- **USER-103 mp 三态读取渲染**：
  - 态 1 `in_japan`：仅文案「商品在日本备货中」，无操作元素
  - 态 2 `in_china_dispatching`：显示快递公司中文（`cn_carrier_code` 走字典 `gz_express_carrier` 9 项 yto/sf/zto/yunda/jd/ems/debang/jitu/other 翻译）+ `cn_tracking_no` + 「复制单号」按钮（`uni.setClipboardData`）
  - 态 3 `delivered`：终态「已签收」
- **禁止**：7 节点 / `logistics_node` / `gz_logistics_node` 表 / 批次推进 / 自动归集 GROUP BY / `gz_express_company` / 物流时间线色 / tokens 1.5。物流审计统一复用 `gz_logistics_audit`（doc/11 §8.3）
- **不自动抓取轨迹**（合同 §2.3）：不引快递 100 / 快递鸟，用户复制单号自查
- admin 写入侧（手动切状态 + 录单号，**不是批次推进**）由 D11 ADMIN-104 实施并**下沉 mp 店员端**；本日 USER-103 只做 mp 端读取 + 渲染，不阻塞

### 3. USER-104 确认收货 + 自动签收（SnailJob）

- 主动确认：mp 详情页「确认收货」按钮，**仅 `in_china_dispatching` 态显示** → 立即 `delivered`，写 `delivered_time`（doc/10 §8.N6）
- 自动签收：**SnailJob 每小时扫** `logistics_status = in_china_dispatching` 且 **锚点 `cn_dispatched_at`（doc/11 已定）> 7 天** 的订单 → `delivered`（doc/10 §8.N5）
- 时间字段：`paid_time` / `cn_dispatched_at`（进 in_china_dispatching 时点）/ `delivered_time`，统一 DATETIME(3)
- **调度框架是 SnailJob**（`com.aizuda @JobExecutor`），仓库**无 sys_job 表**：用 `@Component + @JobExecutor` 薄壳 + 可单测 service；**禁止** Quartz / Flyway INSERT sys_job（启动 hard-fail）；ruoyi-gz-user 模块 pom 显式加 `ruoyi-common-job` 依赖；任务名 / CRON 写进 reports + testing-human，由人在 SnailJob 控制台注册

### 4. admin 三件套（plus-ui，ruoyi/Element Plus 默认审美）

| Ticket | menu 段 | 要点 |
|---|---|---|
| ADMIN-101 预购商品 CRUD | **9100 段** | 从零建，**不复用 ADMIN-005**；BizTable + EasyExcel 导入导出；库存字段 `stock_total` / `stock_remain`（不用 init/left）+ 乐观锁 `version`；状态枚举含 `auto_off`（自动下架，不用 off_shelf/archived） |
| ADMIN-102 扭蛋池管理 | **10100 段** | 权重**前端 reactive 自动归一化**（每行实时显示「归一化后概率（%）= weight / Σweight × 100」，仅在池有库存奖品里算），便于运营 sense check；GACHA 业务表段 10000-10099 |
| ADMIN-103 订单管理三类聚合 | （走 ADMIN-103 自身 menu，复用 plus-ui 范式） | 聚合走 `gz_pay_transaction` 按 `business_type`（`preorder`/`gacha`/`test`）回查对应业务订单表；**删 gz_order 单表 / biz_line / A·B 列**；退款按钮见 §5 |

- admin 全部走 ruoyi/Element Plus 默认审美 + plus-ui BizTable + EasyExcel，**不引用 mockup 像素**，不调样式（admin 不评判视觉）
- 包名 `org.dromara.gz.<域>.{controller,service,mapper,domain,dto}`

### 5. ADMIN-103 退款按钮（V1.1 仅全额 + 单向依赖 PAY-103）

- **退款 V1.1 仅全额**：一笔对一单，无金额 input；C 端无退款入口（仅文案「如需退款请联系客服」）
- admin 订单详情「申请退款」按钮：**owner 权限可见**，走 `@SaCheckPermission("gz:pay:refund:apply")`（**不用 `@SaCheckRole`**）
- **单向依赖 PAY-103**：本日 PAY-103 若未完工 → 按钮 **disabled + tooltip「PAY-103 完工后可用」**（不阻塞本日交付）
- PAY-001 已交付且是**微信支付 V3**：复用 `IWechatPayClient`(`WechatPayV3ClientImpl`/`MockWechatPayClient`) + apiV3Key + V3 NotificationParser(AES-GCM) + 回调 `/api/pay/v3/notify`；支付流水表 = `gz_pay_transaction` / `gz_pay_callback_log`。**禁止** V2 / XML / api-key / 新建 gz_pay_order / amount_fen / /api/wxpay/pay-notify

### 6. ADMIN-103 业务类型差异块（复用 USER-102 view-model）

ADMIN-103 订单详情按业务类型展示差异块：
- 扭蛋订单：获得物 snapshot（name / cover / spec）+ 扭蛋机名 + 稀有度（盲盒语义见 §8）
- 预购订单：商品 + SKU 规格 snapshot + 截止日 / 到货日 snapshot

差异块**复用 USER-102 的统一 view-model 逻辑**（同一份多态 productSnapshot 渲染），admin 端只是从 sa-token-staff 视角访问 + 多一个「申请退款」按钮。

### 7. 双下沉决策说明（Kevin 已拍板）

V1.1 admin 功能哪些下沉 mp 店员端、哪些留 plus-ui：

| 功能 | 落地 | 本日 ticket |
|---|---|---|
| **物流推进 + 录单号** | **下沉 mp 店员端**（plus-ui owner 兜底） | D11 ADMIN-104（本日 USER-103 只做 mp 读取侧） |
| **订单查看（只读）** | **下沉 mp 店员端** | **ADMIN-201（本日新增）** |
| 对账中心 / 数据看板 / 商品 CRUD / 扭蛋池 / 回收站 | **留 plus-ui** | ADMIN-101/102/103（本日）/ D11 其余 |

ADMIN-201 复用 ADR-0004 权限底座（`gz_user.staff_user_id` 绑 sys_user + 登录加载 RBAC + `@SaCheckPermission` + 停用/解绑即时踢）：店员端订单查看只需加一行 `@SaCheckPermission("gz:ord:view")` + admin 授权 + 同租户 1001，**不另造平行 RBAC**。

### 8. 盲盒语义（仅 gacha）

ADMIN-102 / ADMIN-201 / USER-101~104 涉及扭蛋时：
- **UI 可见文案 / i18n key 用**：扭蛋 / 开盒 / 获得 / 出现概率（**禁** 抽奖 / 中奖 / 开奖）
- 后端 enum / 字段可保留 `draw`（不强制改库）
- 引用 doc/10 **§8（扭蛋流，不是 §7=预购）** + doc/12 MP-GACHA-DRAW + tokens 1.4 稀有度 token + doc/13 §3.2 动画（**禁止**引 tokens §9，不存在）

### 9. 字段 / 命名硬约束（每张卡复核）

- 金额一律 `_cent`（分），不用 `_fen`
- snapshot 用 `*_snapshot_json`（JSON 列），不散列成多列；图片用 `image_id` / `*_image_ids`（FK 到 `gz_file_object`），不存裸 url
- 业务线分流统一 `business_type`（`preorder`/`gacha`/`test`），落 `gz_pay_transaction`；**禁止**在业务订单表加 `business_line`/`biz_line`/A·B 列
- 统一订单号格式：`域大写-yyyyMMdd-6位序号`，前缀 `PREORD`/`GACHA`/`TEST`，全局唯一 DB 约束（与 D07 已发的 `TEST-20260604-` 单一致）
- 库存 `stock_total` / `stock_remain`（不用 init/left）；乐观锁 `version`；状态枚举含 `auto_off`（不用 off_shelf/archived）
- `del_flag` 仅 2 值（0 正常 / 2 删除），对齐 ruoyi `@TableLogic`，不用 3 值
- `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`；INSERT 不显式赋 tenant_id（走自动填充）；UNIQUE 约束必含 tenant_id

### 10. 设计约定

- **admin（ADMIN-101/102/103）**：ruoyi/Element Plus 默认审美（不套用 C 系统）+ plus-ui BizTable，**不引用 mockup 像素**。mockup 仅作页面结构参考
- **mp（USER-102/103/104 / ADMIN-201）**：视觉走 C 日漫海报浓墨——只用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token，**不直接撒 `<wd-*>` 标签**；doc/tokens.md + doc/13 为准，旧 mockup 仅布局参考，不逐像素

---

## 与昨日 reports 对账（D09）

D09 完工后应交付（**主线程 §0 自检 grep migration 目录实际验证，不假设**）：
- GZ-ORD-104 预购订单管理（订单建单 + 状态机），含 `gz_ord_order` 表 + 字段 `logistics_status` / `cn_carrier_code` / `cn_tracking_no` / `cn_dispatched_at` / `paid_time` / `delivered_time` / `product_snapshot_json` / `total_amount_cent`（doc/11 §6 + §8.1 落地）
- GZ-GACHA-104 扭蛋衍生订单管理，含 `gz_gacha_order` 表 + 同名物流字段 + 奖品 snapshot 字段（doc/11 §7 + §8.1）
- `gz_pay_transaction`（PAY-001 已落地，含 `business_type` / `amount_cent` / `business_order_no`）

进 D10 前主线程 §0 自检校验：
```bash
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'GZ-ORD-104|GZ-GACHA-104'
grep -rl 'gz_ord_order|gz_gacha_order|gz_pay_transaction' code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
```
对应迁移文件 + 表字段齐 → 开工；缺则 STOP 报 Kevin（D10 不开工，先回 D09 收尾）。

D09 summary.md 中如有「对下游 ticket 的提示」段（统一 VO 字段名 / business_type 枚举值 / cn_dispatched_at 命名），在 USER-101 实施前主线程逐条对齐。

---

## 完成判定（DoD）

- [ ] 8 个 ticket 任务卡 §revision 段空（USER-101~104 / ADMIN-101/102/103/201）
- [ ] 8 个 reports/<T>.md 写完（含 §0 自检 grep migration raw output + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] mvn install（ruoyi-gz-user / ord / gacha / common -am）+ plus-ui build:prod + miniapp build:mp-weixin 三端全绿
- [ ] USER-104 SnailJob 任务名 + CRON 写进 reports + testing-human（待人在 SnailJob 控制台注册）
- [ ] Tier 1A + 1B（kevin-coder 自测 + kevin-qa：admin Playwright E2E + 后端集成 + mp vitest unit）全 ✅
  - 纯 admin（ADMIN-101/102/103）AI ✅ 即终态，无人验
  - mp（USER-102/103/104 / ADMIN-201）进 progress.md「人验」列待 Kevin 批量验
- [ ] testing-human.md 预填（mp happy path + 可达路径）：
  - mp 端用户进「我的订单」→ 切预购/扭蛋 tab → 列表时间倒序 → 点进详情看物流 2 态 + 复制单号 → `in_china_dispatching` 态点「确认收货」→ 变「已签收」
  - mp 端店员账号登录 → 个人中心「门店管理」→「订单查看」→ 预购 + 扭蛋订单列表 + 详情只读（停用 sys_user 后即踢，再调 401/403）

---

## 日终 closing 命令

```bash
cd doc/daily/D10
cat reports/*.md > summary.md
git add -A && git commit -m "D10: V1.1 订单聚合 USER-101~104 + admin 三件套 ADMIN-101/102/103 + mp 订单查看下沉 ADMIN-201"
# 然后写 D11/README.md（物流推进下沉 mp ADMIN-104 / 对账中心 ⭐ ADMIN-105 / 看板 ADMIN-106 / 回收站 ADMIN-108）
```
