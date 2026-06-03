# GZ-ADMIN-201 — mp 店员端订单查看（双下沉：店员手机只读查预购 + 扭蛋订单）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §订单聚合 / M7.10（主理人 + 店员两级权限）
**关联拆解**: doc/02-需求拆解.md V1.1 GZ-ADMIN 段（admin 下沉 mp 决策项）
**关联 mockup**: design/mockup/me-orders.html（视觉参考，店员视角复用 C 端订单卡布局）
**关联 ADR**: doc/_adr/0004-mp-admin-permission-foundation.md（**必读，本卡是其下沉落地**）
**依赖**: GZ-USER-101（订单聚合统一接口 + `IGzUnifiedOrderService`）+ GZ-ADMIN-103（`listForAdmin(queryBo)` 全租户查询方法 + 业务类型差异块 view-model）+ GZ-SYS-007（mp 管理端权限底座，D7x 已交付）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10 §9 跨业务订单聚合 + 跨境物流流（统一订单字段 / 物流 2 态展示口径）；doc/10 §8 扭蛋机抽奖全流程（扭蛋订单业务态 + 衍生订单 snapshot，**盲盒语义见备注**）；ADR-0004 §决策 1（mp 登录加载 RBAC + `@SaCheckPermission`）
- **字段表**：doc/11 §8.1 `gz_unified_order_view`（`GzUnifiedOrderVo` 字段对齐表，逐字一致）+ §8.2 business_status → UI 统一状态映射；doc/11 §gz_user（`staff_user_id` 绑定列，已落 GZ-SYS-007）；本卡仅 1 张 menu seed DDL（无新业务表）
- **UI 参考**（mp ticket）：design/mockup/me-orders.html（C 端订单列表布局，店员端只读复用，不强求逐像素）；门店管理入口区块复用 GZ-SYS-007 个人中心条件渲染

## What

把"订单查看（只读）"下沉到 mp 店员端：绑定到 `sys_user` 且被授权的店员，用手机登 mp 即可在「我的 → 门店管理 → 订单查看」只读浏览本租户（1001）的预购 + 扭蛋订单列表（按 `business_type` tab 切 + 时间倒序）+ 点进订单详情看业务态 / 物流 2 态 / 国内单号。复用 GZ-USER-101 的 `IGzUnifiedOrderService` + GZ-ADMIN-103 的 `listForAdmin` 全租户查询，**不另造平行查询逻辑**；权限走 ADR-0004 底座加一行 `@SaCheckPermission("gz:ord:view")`，**不另造平行 RBAC**。店员端**无任何写操作**（无退款 / 无物流推进 / 无改单号按钮）。

## AC（验收标准）

- [ ] **AC 1**：mp 店员端列表接口 `GET /app/gz/staff/orders?bizType=&status=&logisticsStatus=&userKeyword=&orderNo=&pageNum=&pageSize=`（sa-token-app 会话 + `@SaCheckPermission("gz:ord:view")`）；`bizType` 可选 `all` / `preorder` / `gacha`，默认 `all`；返回标准 ruoyi 分页 `{rows, total, code, msg}`，`rows` 为 `GzUnifiedOrderVo`。
- [ ] **AC 2**：接口**复用 `IGzUnifiedOrderService.listForAdmin(queryBo)`**（GZ-ADMIN-103 已建，不带 `user_id` 过滤、带 `tenant_id` 过滤）；**不新建第二份聚合 service / 不新写 UNION SQL**。返回 VO 字段名严格对齐 doc/11 §8.1「VO 字段对齐表」（snake_case 逐字一致），扭蛋分支 `product_snapshot_json` 含合并后恰好 5 字段（`name`/`cover`/`spec`/`machine`/`rarity`）。
- [ ] **AC 3**：店员端**只读**——本卡**不**新增任何写端点（无退款 / 无物流推进 / 无改单号 / 无确认收货）；mp 店员端订单详情页**无**「申请退款」「发往中国」「确认收货」等写按钮（写操作分别属 GZ-ADMIN-103 owner 端 / D11 GZ-ADMIN-104 / GZ-USER-104，不在本卡）。
- [ ] **AC 4**：权限隔离（curl 三态可测）：① 绑定且授权 `gz:ord:view` 的店员 token → 200 返回订单；② 纯顾客（`staff_user_id` 为 NULL）token → 403；③ 绑定但**未授权** `gz:ord:view` 的店员 token → 403。
- [ ] **AC 5**：**停用 / 解绑即时踢**（复用 GZ-SYS-007 `SysUserStaffKickoutAspect` + `MpStaffPermissionService`，本卡**不重写**）：owner 停用该店员 `sys_user`（或解绑 `staff_user_id` 置 NULL）后，同店员 token 再调 `/app/gz/staff/orders` 返 `{"code":401}`（会话即踢，无需等下次登录）。
- [ ] **AC 6**：同租户隔离——店员只能看到 `tenant_id='1001'` 的订单（靠 ruoyi `TenantLineInnerInterceptor` 自动注入 `WHERE tenant_id`，service 不手写）；VO **不暴露** `tenant_id` / `del_flag` / `staff_user_id` / `session_key` 等内部字段。
- [ ] **AC 7**：mp 订单详情按 `business_type` 渲染差异块（**复用 GZ-ADMIN-103 / USER-102 同一份多态 `product_snapshot_json` view-model 逻辑**）：扭蛋订单显示获得物 snapshot（`name` / `cover` 图 / `spec` 稀有度文案）+ 扭蛋机名 + 稀有度色边框；预购订单显示商品 + SKU 规格 snapshot。物流 2 态只读渲染（`in_japan`「在日本」/ `in_china_dispatching`「已发往中国」+ 快递公司中文（`cn_carrier_code` 走字典 `gz_express_carrier` 翻译）+ `cn_tracking_no` / `delivered`「已签收」），**店员端无「复制单号」以外的物流操作**。
- [ ] **AC 8**：菜单 / 权限 seed —— Flyway 迁移建 `gz:ord:view` 权限菜单节点，挂在 GZ-SYS-007 已建的「门店管理 / mp 管理端」菜单组下（menu_id 5064，紧邻 5060-5063 staff-binding），**仅 owner（100）+ 店员角色按需授权**；DDL 命名 `V202606071400__GZ-ADMIN-201-mp-staff-order-view-menu.sql`（时间戳 > 已有最大 `V202606051200`）。
- [ ] **AC 9**：mp 视觉走 C 日漫海报浓墨——店员端订单列表 / 详情页只用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token，**不直接撒 `<wd-*>` 标签**；扭蛋稀有度色用 tokens 1.4 稀有度 token；**禁止**引 tokens §9（不存在）。
- [ ] **AC 10**：单测 —— `GzStaffOrderControllerTest` / service 调用层至少 3 个：(a) 授权店员调 `bizType=all` 返回混合订单且 `created_at DESC` 正确；(b) 未授权店员调 → 403；(c) `bizType=gacha` 仅返回扭蛋订单且 `product_snapshot_json` 含 5 字段。
- [ ] **AC 11: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）—— Kevin 用绑定且授权的店员账号登 mp → 个人中心「门店管理」区块（GZ-SYS-007 已建条件入口）→ 点「订单查看」入口 → 到达本卡店员端订单列表页（**N=2**：门店管理区块 → 订单查看）。
  - 入口建在 GZ-SYS-007 已交付的个人中心「门店管理」区块内（**业务主线入口已存在**，不需临时入口）；本卡在该区块内新增「订单查看」菜单项（受 `isStaff` + `gz:ord:view` 条件渲染，纯顾客 / 无权限店员不显示）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-user/`（订单聚合域归属 GZ-USER，与 USER-101 同模块）
  - `controller/applet/GzStaffOrderMpController.java`（mp 路径 `/app/gz/staff/orders`，sa-token-app + `@SaCheckPermission("gz:ord:view")`，**新建**；薄壳调 `IGzUnifiedOrderService.listForAdmin` + 详情查单）
  - **复用**：`IGzUnifiedOrderService`（USER-101）+ `listForAdmin(queryBo)`（ADMIN-103）+ `GzUnifiedOrderVo`（USER-101）；**不新建** service / mapper / VO
  - **复用**：GZ-SYS-007 `MpStaffPermissionService` / `SysUserStaffKickoutAspect`（登录加载 RBAC + 停用/解绑即时踢）—— 本卡零改动
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V202606071400__GZ-ADMIN-201-mp-staff-order-view-menu.sql`（仅 menu/perm seed，menu_id 5064；**无新业务表**）
- **小程序**：`code/main/miniapp/src/pages/`
  - `me/staff-orders/index.vue`（店员端订单列表，bizType tab + 时间倒序 + 分页，复用 me-orders 卡布局，Biz* 组件）
  - `me/staff-orders/detail.vue`（店员端订单详情，多态 product_snapshot_json 渲染 + 物流 2 态只读，复用 USER-102 view-model）
  - `api/staffOrder.ts`（封装 `/app/gz/staff/orders` 列表 + 详情）
  - 个人中心「门店管理」区块（GZ-SYS-007 已建）内追加「订单查看」入口项（`v-if` isStaff + has `gz:ord:view`）
  - i18n：可见字符串走 `t('xxx.yyy')` + `zh_CN.ts` / `en_US.ts`；扭蛋文案用 扭蛋 / 获得 / 出现概率（**禁** 抽奖 / 中奖 / 开奖）
- **测试**：单测覆盖 controller 权限三态 + bizType 分支；vitest mp unit（列表渲染 + tab 切换）

## 备注

- **§0 自检改为 grep migration 目录确认上游表实际存在**（不假设上游已 merge）：
  ```bash
  ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'GZ-ORD-104|GZ-GACHA-104|GZ-SYS-007'
  grep -rl 'gz_ord_order|gz_gacha_order' code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
  grep -rl 'staff_user_id' code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
  ```
  另校验代码侧上游已落：`IGzUnifiedOrderService.listForAdmin`（ADMIN-103）+ `GzUnifiedOrderVo`（USER-101）+ `MpStaffPermissionService`（GZ-SYS-007）实际存在；缺 → STOP 报 Kevin，本卡不开工（依赖 USER-101 + ADMIN-103 + SYS-007 齐备才起）。
- **双下沉决策（Kevin 已拍板，D10 README §7）**：V1.1「订单查看（只读）」+「物流推进 + 录单号」双下沉 mp 店员端。本卡只做**订单查看只读**；物流推进写入侧是 D11 GZ-ADMIN-104（也下沉 mp）。对账 / 看板 / 商品 CRUD / 扭蛋池 / 回收站留 plus-ui。
- **零底座改动是设计目标**：GZ-SYS-007 已让"下沉新功能"边际成本 = 加一行 `@SaCheckPermission` + admin 授权 + 同租户 1001。本卡若发现需改底座（登录加载 / 踢人逻辑）→ 说明边界切错，STOP 报 Kevin。
- **盲盒语义（仅 gacha）**：店员端订单涉及扭蛋时，UI 可见文案 / i18n key 用 扭蛋 / 开盒 / 获得 / 出现概率（**禁** 抽奖 / 中奖 / 开奖）；后端 enum / 字段可保留 `draw`。引用 doc/10 **§8（扭蛋流）** + doc/12 MP-GACHA-DRAW + tokens 1.4 稀有度 token + doc/13 §3.2 动画（**禁止**引 tokens §9，不存在）。
- **字段 / 命名硬约束复核**：金额 `_cent`（前端转元）；snapshot 读 `*_snapshot_json`（JSON 列）；图片走 `image_id` / `cover`（FK gz_file_object，前端换签名 URL，不存裸 url）；`business_type` 取值 `preorder`/`gacha`；订单号格式 `域大写-yyyyMMdd-6位序号`；`del_flag` 仅 2 值；`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`，INSERT 不显式赋（自动填充），UNIQUE 必含 tenant_id。
- **物流 = 2 态 + 终态（C1，ADR-0005）**：`logistics_status` ∈ `in_japan` / `in_china_dispatching` / `delivered`，独立于 `business_status`。**禁止** 7 节点 / `logistics_node` / `gz_logistics_node` 表 / 批次推进 / 自动归集 / `gz_express_company` / 物流时间线色 / tokens 1.5。快递公司走字典 `gz_express_carrier`（9 项 yto/sf/zto/yunda/jd/ems/debang/jitu/other）。
- **退款 V1.1 仅全额且不在本卡**：店员端无退款入口；退款按钮是 GZ-ADMIN-103 owner 端（`@SaCheckPermission("gz:pay:refund:apply")`，非本卡）。
- **风险 R1**：上游 `listForAdmin` 若 ADMIN-103 未交付 → §0 自检 grep migration 目录 + grep 代码确认上游表 / service 实际存在；缺则 STOP，不私自补建聚合逻辑（避免与 ADMIN-103 双份实现漂移）。
- **menu_id 段**：本卡 perm 挂 GZ-SYS（5000-5999）mp 管理端组（5064，紧邻 staff-binding 5060-5063），**不占** GZ-ORD admin 9100 段（那是 plus-ui 预购商品 CRUD）。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D10/GZ-ADMIN-201 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
