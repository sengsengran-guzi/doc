# GZ-USER-101 — 订单聚合统一接口（service 层 UNION，跨预购 + 扭蛋）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §用户操作流程 §进入会员中心 步骤 4-5（订单聚合 tab）
**关联拆解**: doc/02-需求拆解.md §3.4（GZ-USER 域 V1.1 订单聚合）
**关联 mockup**: design/mockup/order-list.html（仅作字段消费参考；本 ticket 纯后端，无 UI 实装，mp UI 由 USER-102 接入）
**关联 ADR**: —（C1 跨业务订单聚合 / 物流 2 态裁定见 doc/10 §9 + doc/11 §8 Changelog v0.2；C1 物流合同对齐记 ADR-0005，本卡只读不实施物流写入）
**依赖**: GZ-ORD-104（建 `gz_ord_order` 表 + 物流/snapshot/金额字段）+ GZ-GACHA-104（建 `gz_gacha_order` 表 + 同名物流字段 + 奖品 snapshot）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆（dongjiaoshan D6 教训）。

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §跨业务订单聚合（V1.1 GZ-USER-101/102）+ §统一订单字段（跨业务）+ §跨境物流权威状态（C1 裁定，L1/L2/L3）
- **字段表**：doc/11-字段权威表.md **§8.1 `gz_unified_order_view` 统一订单视图**（VO 字段对齐表 = 唯一字段口径权威 + gacha 分支 5 字段合并规则钉死）+ §8.2 business_status → UI 统一状态映射 + §6.3 `gz_ord_order`（预购订单 schema）+ §7.4 `gz_gacha_order`（扭蛋衍生订单 schema）+ 附录 A.7 物流枚举（C1 2 态 + 终态）
- **UI 参考**（纯后端 ticket，仅作字段消费对齐）：doc/12 §MP-ORD-LIST（消费方页面，本 ticket 不实装 UI，但接口字段需对齐其消费需求；不出「拼豆」tab，doc/11 §8.1 D3 裁定）

## What

后端落统一订单聚合接口：跨 `gz_ord_order`（预购）+ `gz_gacha_order`（扭蛋）两类业务订单，service 层 UNION（不建物理 MySQL VIEW、不建物化表），按 `business_type` tab 筛 + `created_at` 时间倒序返回统一 VO。mp 端 `GET /api/user/orders` 调本接口拿订单列表。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /api/user/orders?bizType=&pageNum=&pageSize=`（sa-token-app 权限 + `@SaCheckPermission("gz:user:orders:list")`）；`bizType` 可选值 `all` / `preorder` / `gacha`，默认 `all`；返回标准 ruoyi 分页结构 `{rows, total, code, msg}`
- [ ] **AC 2**：返回 VO `GzUnifiedOrderVo` 字段名**严格对齐 doc/11 §8.1「VO 字段对齐表」**（snake_case，钉死，逐字一致）：`order_no` / `business_type`（`preorder`/`gacha`）/ `user_id` / `product_snapshot_json`（JSON）/ `total_amount_cent`（BIGINT，分）/ `business_status` / `logistics_status` / `cn_carrier_code` / `cn_tracking_no` / `address_snapshot_json`（JSON，gacha 可能 NULL）/ `paid_time` / `delivered_time` / `created_at`。任何字段名不一致 → STOP 修 doc/11，不私自加减字段
- [ ] **AC 3**：聚合**在 service 层 UNION**：`GzUnifiedOrderService.listByUser(userId, businessType?)` 分别查 `gz_ord_order`（贴字面量 `business_type='preorder'`）+ `gz_gacha_order`（贴字面量 `business_type='gacha'`），各自映射成 `GzUnifiedOrderVo` 后合并、按 `created_at DESC` 排序、内存分页。**不建 MySQL `CREATE VIEW`、不建物化表**（doc/11 §8.1 F8.1）
- [ ] **AC 4**：`bizType=preorder` 只查 `gz_ord_order`；`bizType=gacha` 只查 `gz_gacha_order`；`bizType=all` 才并查两表后合并（避免不必要的单表查询）
- [ ] **AC 5**：gacha 分支 `product_snapshot_json` 按 doc/11 §8.1「gacha 分支合并规则」从 `prize_snapshot_json` + `machine_snapshot_json` 合并出**恰好 5 个字段**：`name`（prize_snapshot_json.name）/ `cover`（prize_snapshot_json.image_id，空回退 machine_snapshot_json.cover_image_id）/ `spec`（rarity 文案化）/ `machine`（machine_snapshot_json.name）/ `rarity`（enum `SSR`/`SR`/`R`/`N`）。preorder 分支直接透传 `gz_ord_order.product_snapshot_json` 原结构。**cover 透传 image_id（FK gz_file_object），不解析裸 url**（前端换签名 URL）
- [ ] **AC 6**：`tenant_id`（1001）+ `del_flag` 过滤由 ruoyi `TenantLineInnerInterceptor` + `@TableLogic` 在各自 mapper 自动加，service **不手写** `WHERE tenant_id=` / `WHERE del_flag=`
- [ ] **AC 7**：仅返回当前登录用户订单：service 内 `where user_id = <LoginHelper 取的当前 app_user id>`（前端 hide 不算防御）
- [ ] **AC 8**：`business_status` → UI 状态 chip 的映射**不在本接口做**，原样透传各业务侧枚举字符串（doc/11 §6.3 / §7.4）；mp 端按 doc/11 §8.2 映射表自行渲染
- [ ] **AC 9**：`logistics_status` 直接透传 C1 枚举值（`in_japan` / `in_china_dispatching` / `delivered`，附录 A.7）；`cn_carrier_code` / `cn_tracking_no` 仅 `in_china_dispatching`（L2）后非空，原样透传不翻译（mp 端按字典 `gz_express_carrier` 渲染中文）
- [ ] **AC 10**：分页 `pageSize` 上限 50（防恶意大分页拖库），超限按 50 截断；分页在合并 + 排序后做
- [ ] **AC 11**：单测 `GzUnifiedOrderServiceImplTest` 至少 3 个：(a) `bizType=gacha` 仅返回扭蛋订单且 product_snapshot_json 含 5 字段 / (b) `bizType=preorder` 仅返回预购订单且透传原 snapshot / (c) `bizType=all` 混合按 `created_at DESC` 合并排序正确

> 纯后端 ticket — 无 Tier 2 入口可达 AC（CLAUDE.md §8.2；mp 入口由 USER-102 建）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserOrderMpController.java`（mp 路径 `/api/user/orders`，sa-token-app + `@SaCheckPermission`，新建）
  - `service/IGzUnifiedOrderService.java` + `service/impl/GzUnifiedOrderServiceImpl.java`（service 层 UNION 合并 + 内存分页，新建）
  - `domain/vo/GzUnifiedOrderVo.java`（统一 VO，字段名严格对齐 doc/11 §8.1）
  - `domain/bo/GzUnifiedOrderQueryBo.java`（`bizType` / `pageNum` / `pageSize`）
  - service impl 注入 `IGzOrdOrderService`（GZ-ORD-104）+ `IGzGachaOrderService`（GZ-GACHA-104），调各自 listByUser 后映射合并；preorder/gacha 各自 join 自己的 snapshot（snapshot 已内联在订单表 JSON 列，无需额外 join）
  - **不落新 DDL**（查询服务，消费 GZ-ORD-104 + GZ-GACHA-104 已建的 `gz_ord_order` + `gz_gacha_order` 表；如确需新建迁移则命名 `V<时间戳>__GZ-USER-101-<desc>.sql`，时间戳 > V202606051200，但本 ticket 预期无 DDL）
  - 包名 `org.dromara.gz.user.{controller,service,mapper,domain,dto}`（CLAUDE.md §6 #4）
- **小程序**：本 ticket **不动 mp**，USER-102 才接入消费
- **测试**：admin/seed 预造 2 个扭蛋订单 + 3 个预购订单（不同 `created_at`）→ curl `GET /api/user/orders?bizType=all` 验返回 5 单 + 时间倒序；`bizType=gacha` 验返回 2 单且 snapshot 含 5 字段

## 备注

### 强约束

1. **VO 字段名严格对齐 doc/11 §8.1「VO 字段对齐表」**（snake_case，逐字钉死）：任何不一致 → STOP 修 doc/11（CLAUDE.md §9.5 #1 改源头 doc），不在 ticket patch
2. **service 层 UNION，不建物理 VIEW / 物化表**（doc/11 §8.1 F8.1 + §8.4）：物理 VIEW 绕过 ruoyi `TenantLineInnerInterceptor` 租户隔离 + `@TableLogic` 软删拦截器；V1.1 数据量小（千级）service 层合并 + 内存分页足够；性能瓶颈出现时再评估物化表（doc/11 §8.4 留底）
3. **gacha 分支 product_snapshot_json = 恰好 5 字段**（name/cover/spec/machine/rarity，doc/11 §8.1 钉死），不增不减；cover 透传 `image_id`（FK gz_file_object），**不存裸 url**（图片硬约束）
4. **金额字段 `total_amount_cent`（分）透传**，不用 `_fen`，不在接口层转元（mp 端转元）
5. **业务类型枚举只用 `preorder` / `gacha`**：**不出现 `bean`**（拼豆预约不进订单聚合，doc/11 §8.1 D3 + PRD M5 裁定，doc/12 §MP-ORD-LIST 3 tab 不含拼豆）；business_type 是字面量贴在 VO，**不在业务订单表加 `business_line`/`biz_line`/A·B 列**
6. **盲盒语义**（gacha 分支）：本 ticket 纯后端透传 enum/字段（`rarity` / `business_status` 可保留 `draw` 系命名），不涉 UI 可见文案；mp 可见文案语义（扭蛋/开盒/获得/出现概率，禁抽奖/中奖/开奖）由 USER-102 把控
7. **logistics_status 独立透传 C1 3 枚举**（`in_japan` / `in_china_dispatching` / `delivered`，附录 A.7），与 `business_status` 并行，**不互相覆盖、不翻译为中文**（mp 端按字典渲染）
8. **不暴露内部字段**：`tenant_id` / `del_flag` / `session_key` / `staff_user_id` 等一律不进 VO；VO 只含 §8.1 表列出的字段
9. **包名 `org.dromara.gz.user.*`**（CLAUDE.md §6 #4 业务包名规则）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | service 层 UNION（不写物理 VIEW / 物化表） | 物理 VIEW 绕过 ruoyi 租户 + 软删拦截器易漏隔离；两业务表字段语义差异大（预购 SKU vs 扭蛋奖品），service 各自映射 + 合并清晰可测（doc/11 §8.1） |
| D2 | `bizType` 单类筛走单表查询 | 性能优化：`preorder`/`gacha` 只查对应表，`all` 才并查 |
| D3 | product_snapshot_json 多态 | gacha 分支合并出固定 5 字段（name/cover/spec/machine/rarity）；preorder 分支透传原 snapshot；前端按 `business_type` 分支渲染 |
| D4 | 分页在合并 + 排序后做（内存分页） | V1.1 数据量小（千级）OK；如未来上量 → V2 评估物化表 + 分页下推（doc/11 §8.4） |
| D5 | business_status 不在接口翻译 | 两业务枚举语义不同（`paid` 预购=已付待发 / 扭蛋无此态），mp 端按 doc/11 §8.2 映射表区分渲染（AC 8） |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 上游表实际不存在（V1.1 从零起，ruoyi-gz-ord/gacha 是空脚手架） | **§0 自检 grep migration 目录确认上游表实际存在**：`ls migration/ \| grep -E 'GZ-ORD-104\|GZ-GACHA-104'` + `grep -rl 'gz_ord_order\|gz_gacha_order' migration/`；缺 → STOP 回 D09 收尾，本卡不开工（不假设上游已 merge） |
| R2 | 上游两表字段不齐（logistics_status / cn_carrier_code / cn_tracking_no / product_snapshot_json / prize_snapshot_json / machine_snapshot_json / total_amount_cent / paid_time / delivered_time / create_time） | §0 自检 grep 对应迁移文件 DDL 验字段存在；缺则 STOP 回 D09 |
| R3 | 合并后内存分页全量扫两表 | V1.1 数据量极小（千级）不优化；V2 数据量上来后改物化表 + 物理分页（doc/11 §8.4） |
| R4 | business_status 枚举值两表语义不同（`paid` 预购≠扭蛋无此态） | AC 8 明确不在接口层映射，mp 端按 doc/11 §8.2 映射表区分渲染 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
