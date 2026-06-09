# GZ-ADMIN-104 — 跨境物流 2 态推进（mp 店员端主形态 + plus-ui owner 兜底）

**优先级**: P1
**复杂度**: M（C1 简化后无批次 / 无归集；核心是 2 态状态机 + 必录单号校验 + 审计 + mp/admin 双端入口）
**关联 PRD**: doc/02-prd.md M5 §跨境物流（PRD 7 节点表 4.4 已被 doc/10 C1 裁定为 2 态覆盖）
**关联拆解**: doc/02-需求拆解.md §3.5
**关联 mockup**: mp 走 C 日漫海报浓墨（doc/tokens.md + doc/13 为准，不逐像素还原）；plus-ui owner 兜底走 ruoyi/Element Plus 默认审美（不引 mockup 像素）
**关联 ADR**: doc/_adr/0004-mp-admin-permission-foundation.md（mp 店员端权限底座，本卡复用）；doc/_adr/0005-cross-border-logistics-2-state.md（C1 物流 2 态对齐合同 §2.3，Kevin 决策 4）
**依赖**: GZ-ADMIN-103（订单聚合管理，物流推进读它的订单详情）+ GZ-USER-103（mp 物流 2 态只读展示，本卡是其写入侧；如 USER-103 订阅消息 hook 未就绪则留 hook 不阻塞）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md
  - **§9 跨境物流权威状态（C1 裁定 2 态 + 终态）** — 本 ticket 核心锚定（L1 `in_japan` / L2 `in_china_dispatching` / L3 `delivered`）
  - §9 状态机 + 关键节点 N1/N2/N8/N9（N2 进「已发往中国」必录单号；N8 owner 回退；N9 改单号）
  - §9 异常分支 E2（录错单号修正）/ E5（漏录单号 → 按钮 disabled）/ E6（订单态不允许推进逐单拦截）
  - §9 Q9.5（逐单手动切 + 录单号，**无批次自动归集**）
- **字段表**：doc/11-字段权威表.md
  - §6.3 `gz_ord_order` 物流字段 `logistics_status` / `cn_carrier_code` / `cn_tracking_no` / `cn_dispatched_at`（已由 D09 建，本卡只 UPDATE）
  - §7.4 `gz_gacha_order` 同名物流字段（已由 D09 建）
  - **§8.3 `gz_logistics_audit`** — 物流审计表（已由前序日建；`action_type` ∈ status_forward / status_rollback / carrier_set / carrier_update；`from_*` / `to_*` / `reason` / `operator_type` / `operator_id` / `operated_time`）
  - 附录 A.7 物流枚举（C1 2 态 + 终态）
  - §字典表 `gz_express_carrier`（**9 项**：yto/sf/zto/yunda/jd/ems/debang/jitu/other；本卡 DDL 只补菜单，字典若前序日已 seed 则不重复 INSERT）
- **下沉底座**：ADR-0004 §决策 1（mp openid 绑 sys_user + 登录加载 RBAC + `@SaCheckPermission` + 同租户 1001 + 停用/解绑即时踢）；落地见 GZ-SYS-007（StaffMeController / MpStaffPermissionServiceImpl）
- **UI 参考**：
  - mp 店员端：C 日漫海报浓墨（doc/tokens.md + doc/13 §3.2；**禁止**引 tokens §9，不存在；**不做物流时间线色 / 不引 tokens 1.5** — C1 删节点流转无时间线）
  - plus-ui owner 兜底：`N/A（admin 走 ruoyi 默认审美，不评判视觉）`

## What

让店员/owner 把预购或扭蛋订单的 `logistics_status` 在订单详情页逐单手动从 `in_japan` 推进到 `in_china_dispatching`（必录 `cn_carrier_code` 走 `gz_express_carrier` 9 项字典 + `cn_tracking_no`，写 `cn_dispatched_at`）→ 再推到 `delivered`；每次状态/单号变更写 `gz_logistics_audit` + `@Log`，并提供改单号二次入口与 owner 回退。**主形态下沉 mp 店员端**（复用 ADR-0004 权限底座），plus-ui owner 端兜底。

## AC（验收标准）

- [ ] **AC 1（后端 — 2 态推进接口）**：`POST /推进` 把单个订单 `logistics_status` 从 `in_japan` → `in_china_dispatching`，body 必带 `cn_carrier_code` + `cn_tracking_no`；
  - service 校验 `cn_carrier_code` ∈ `gz_express_carrier` 9 项（yto/sf/zto/yunda/jd/ems/debang/jitu/other），非法 → 400
  - `cn_carrier_code` 或 `cn_tracking_no` 任一为空 → 400（doc/10 §9.E5）
  - 写订单 `logistics_status=in_china_dispatching` + `cn_carrier_code` + `cn_tracking_no` + `cn_dispatched_at=NOW()`（同事务）
  - 同时写 `gz_logistics_audit` 一条：`action_type=status_forward` 主审计 + `carrier_set` 首录单号审计（或单条审计含 `to_status` + `to_carrier_code` + `to_tracking_no`，按实现选其一，reports 说明口径）
- [ ] **AC 2（后端 — 推到已签收）**：`in_china_dispatching` → `delivered` 推进接口，写 `logistics_status=delivered` + `delivered_time=NOW()` + `gz_logistics_audit`（`action_type=status_forward`，`from_status=in_china_dispatching` / `to_status=delivered`）
- [ ] **AC 3（后端 — 状态不可逆 + 订单态校验）**：
  - 目标态序号 ≤ 当前态（如 `delivered`→`in_china_dispatching`）→ 400「状态不可回退」（doc/10 §9 状态机；owner 回退走 AC 6 独立接口）
  - 跳态（`in_japan`→`delivered` 不经 `in_china_dispatching`）→ 400
  - 订单 `business_status` 不允许推进（如 `refunded` / 已 `delivered`）→ 400「该订单当前状态不可推进物流」（doc/10 §9.E6，逐单拦截）
- [ ] **AC 4（后端 — 改单号二次入口）**：`PUT 改单号` 接口可改 `in_china_dispatching` 订单的 `cn_carrier_code` / `cn_tracking_no`（不改 `logistics_status`、不重置 `cn_dispatched_at`）；写 `gz_logistics_audit`（`action_type=carrier_update`，记 `from_carrier_code` / `from_tracking_no` / `to_carrier_code` / `to_tracking_no`）；**不禁止修改**（doc/10 §9.N9 / E2）
- [ ] **AC 5（后端 — 跨业务复用）**：同一套接口按 `business_type`（`preorder` / `gacha`）+ `business_order_no` 定位订单，分别 UPDATE `gz_ord_order` / `gz_gacha_order`；`gz_logistics_audit` 写入 `business_type` + `business_order_no`（doc/11 §8.3）
- [ ] **AC 6（后端 — owner 回退）**：`POST 回退` 接口仅 owner 权限把 `logistics_status` 回退到上一态，`reason` **必填**（空 → 400）；写 `gz_logistics_audit`（`action_type=status_rollback`，记 `from_status` / `to_status` / `reason`）（doc/10 §9.N8）
- [ ] **AC 7（权限 — 复用 ADR-0004 底座）**：所有写接口走 `@SaCheckPermission("gz:ord:logistics:push")`（推进/录单号/改单号）；回退接口走 `@SaCheckPermission("gz:ord:logistics:rollback")`（仅 owner 授权）；纯顾客 / 无权限 mp token → 403；同租户 1001（不另造平行 RBAC）
- [ ] **AC 8（审计 + 操作日志）**：每个写接口加 ruoyi `@Log(title="跨境物流推进", businessType=UPDATE)`；`gz_logistics_audit.operator_type=admin`、`operator_id=` 当前登录用户名；reports 贴 DB 审计行 raw output
- [ ] **AC 9（mp 店员端 — 主形态）**：mp 店员端订单详情页（复用 GZ-ADMIN-201 订单查看详情）增加物流推进操作区：
  - 当前 `in_japan` → 显「发往中国」按钮 → 弹 `BizDatePicker` 风格表单（快递公司 9 选 1 下拉 + 单号输入）；二者任一空 → 提交按钮 disabled（doc/10 §9.E5）
  - 当前 `in_china_dispatching` → 显「已发往中国」+ 快递公司中文 + 单号 + 「改单号」入口 + 「推到已签收」按钮
  - 当前 `delivered` → 显「已签收」终态，无操作按钮
  - 仅用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token，不直接撒 `<wd-*>` 标签；快递公司中文经 `gz_express_carrier` 字典翻译
- [ ] **AC 10（plus-ui owner 兜底）**：plus-ui `views/gz-ord/` 订单详情（GZ-ADMIN-103 已建）补物流推进操作区（el-form + el-select 快递公司字典 + 单号 input + el-dialog 二次确认）：发往中国 / 推已签收 / 改单号 / **owner 回退**（仅 owner 可见，reason 必填）；走 ruoyi/Element Plus 默认审美
- [ ] **AC 11（单测覆盖）**：service 单测 ≥ 6 个 raw assertion：
  - happy path：`in_japan`→`in_china_dispatching` 录合法快递 + 单号 → 字段 + 审计正确（mock DB）
  - 漏录单号（`cn_tracking_no` 空）→ 400
  - 非法快递编码（不在 9 项）→ 400
  - 状态回退（`delivered`→`in_china_dispatching`）非 owner → 400
  - 订单 `business_status=refunded` 推进 → 400（E6）
  - owner 回退 `reason` 空 → 400
- [ ] **AC 12: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从「店员账号登 mp → 个人中心『门店管理』区块（GZ-SYS-007 已建）→ 订单查看（GZ-ADMIN-201）→ 订单详情」点 ≤ 4 次到达本卡物流推进操作区。
  - 若 GZ-ADMIN-201 订单查看入口已就绪 → 走真入口（首选）
  - 若订单查看详情入口尚未挂上 → 在 `pages/index/index.vue` 或个人中心「门店管理」区加临时入口直达店员订单详情 + 注释 `<!-- TODO(Tier2-entry-temp): GZ-ADMIN-104, remove when GZ-ADMIN-201 merged -->`

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`（物流推进主域；扭蛋单复用同 service，跨业务定位走 `business_type`）
  - `controller/GzLogisticsController.java`（mp 店员端 + admin 共用，路径如 `/app/gz/ord/logistics`（mp）+ owner 端复用同 service）+ 接口：
    - `POST /forward`（推进到下一态：`in_japan`→`in_china_dispatching` 必带快递/单号；`in_china_dispatching`→`delivered`）
    - `PUT /carrier`（改单号，body: business_type + business_order_no + cn_carrier_code + cn_tracking_no）
    - `POST /rollback`（owner 回退，body 含 reason，`@SaCheckPermission("gz:ord:logistics:rollback")`）
  - `service/IGzLogisticsService.java` + impl（状态机校验 / 9 项字典校验 / 必录校验 / 审计写入集中处）
  - `domain/dto/LogisticsForwardDto.java` / `LogisticsCarrierUpdateDto.java` / `LogisticsRollbackDto.java`
  - **DDL × 1**：`ruoyi-admin/src/main/resources/db/migration/V202606191300__GZ-ADMIN-104-logistics-menu.sql` — 插入「物流推进」菜单（**menu_id 11003**，挂订单管理下；perms `gz:ord:logistics:push` / `gz:ord:logistics:rollback`，授权 owner + 店员推进权 / 仅 owner 回退权）。**不新建表**（`gz_ord_order` / `gz_gacha_order` 物流字段 + `gz_logistics_audit` 前序日已建）；`gz_express_carrier` 字典若前序日未 seed 则在本 DDL 补 9 项，已 seed 则不重复
- **mp 店员端**：`code/main/miniapp/`
  - 订单详情页（复用 GZ-ADMIN-201）物流推进操作区组件（`Biz*` 原子组件）
  - `src/api/gz-ord/logistics.ts`（forward / carrier / rollback 封装）
- **Admin（owner 兜底）**：`code/main/plus-ui/`
  - `views/gz-ord/`（GZ-ADMIN-103 订单详情）补物流推进操作区 + 改单号 dialog + owner 回退 dialog
  - `api/gz-ord/logistics.ts`
- **测试**：mvn 单测（service ≥ 6 个）+ mp 店员端真机 happy path（人验）+ plus-ui owner 端 Playwright E2E（kevin-qa）

## 备注

### 强约束（C1 / 合同）

1. **2 态 + 终态，不是 7 节点**（doc/10 §9 C1）— **禁止** `logistics_node` / `gz_logistics_node` 表 / 7 节点 enum / 批次推进 / 自动归集 GROUP BY / 国内派送节点 / `gz_express_company` / `gz_logistics_log` / 物流时间线色 / tokens §1.5
2. **进 `in_china_dispatching` 必录** `cn_carrier_code`（9 项字典）+ `cn_tracking_no`（doc/10 §9.N2 / E5）— DB 不加 CHECK（doc/11 F-D31，业务层校验：mp/owner 表单 disabled + service assert）
4. **国内物流仅展示甲方录入单号**（合同 §2.3 #15）— 后端不调任何快递查询/轨迹抓取 API；用户复制单号自查
5. **跨境物流不自动抓取**（合同 §2.3 #14）— 不接日本段/国际段轨迹
6. **状态不可逆**（除 owner 回退专用接口，doc/10 §9 状态机）；回退 `reason` 必填，写审计
7. **退款解耦**：`logistics_status` 独立于 `business_status` 并行，不互相覆盖；订单 `business_status=refunded` 时 `logistics_status` 保留最后态，UI 显「已退款」覆盖（doc/10 §9.E3）
8. **复用 ADR-0004 底座**：mp 店员端走 `@SaCheckPermission` + 同租户 1001 + 停用/解绑即时踢；**不另造平行 RBAC**
9. **不动 ruoyi 自带模块**（CLAUDE.md §6 #1）；`@Log` 用 ruoyi 自带

### 下沉决策（Kevin 决策 2）

- **物流推进主形态下沉 mp 店员端**：店员手机现场发货录单（贴单后扫一眼即推），是日常高频场景，落 mp 体验优先
- **plus-ui owner 兜底**：owner 电脑后台也能切 2 态 + 改单号 + **回退**（回退仅 owner，店员无回退权）

### 物流合同对齐（Kevin 决策 4 → ADR-0005）

- 先实现 2 态，验收前与甲方口头确认，事后补签合同 §2.1；**不改 formal 合同**，决策记 ADR-0005（合同 v0.1 写「7 节点」由 doc/10 v0.2 C1 覆盖）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 逐单切 2 态，无批次/无自动归集 | C1 裁定（doc/10 §9 Q9.5）：快递单号一单一号，不存在批量录同一单号场景；mp 店员端逐单贴单即推更贴现场 |
| D2 | mp + admin 共用同一 service，跨业务按 `business_type` 分流 UPDATE | 状态机/校验/审计单点，避免 mp 端与 owner 端逻辑漂移 |
| D3 | 改单号入口独立于推进入口 | 「推进」是状态前移，「改单号」是单据修正，UX/接口分离更清晰；甲方运营反复改单号是常态 |
| D4 | owner 回退走独立接口 + 独立 perm | 回退是高危操作，与店员日常推进权限隔离，强制 reason 留痕 |
| D5 | `cn_dispatched_at` 仅首次进 `in_china_dispatching` 写，改单号/回退不重置 | 7 天自动签收时钟锚点（doc/11 §6.3），改单号不该重置签收倒计时 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | §0 自检假设上游表已建 → 实际未建翻车 | **§0 自检 grep migration 目录确认** `gz_ord_order` / `gz_gacha_order` 物流字段 + `gz_logistics_audit` + `gz_express_carrier` 字典实际存在（不假设上游已建）；缺则 STOP 报 Kevin |
| R2 | mp 店员端进「已发往中国」漏录快递公司/单号 | 表单 9 项字典必选 + 单号必填，二者任一空 → 提交 disabled（doc/10 §9.E5）+ service 层二次 assert |
| R3 | 国内单号录错无法修正 | AC 4「改单号」二次入口（mp + owner 端）+ 写 `gz_logistics_audit`（`carrier_update` 记 from/to）；**不禁止修改** |
| R4 | owner 误回退 | 回退仅 owner perm + `reason` 必填 + 写审计；店员端无回退入口 |
| R5 | mp 店员端订单详情入口未就绪（GZ-ADMIN-201 未 merge）→ Tier 2 测不了 | AC 12：GZ-ADMIN-201 入口未挂时本卡加临时入口 + `TODO(Tier2-entry-temp)` 注释，GZ-ADMIN-201 merge 后清理 |
| R6 | 订阅消息 hook（doc/10 §9.N7）依赖 USER-103 | 进「已发往中国」/「已签收」后 `ApplicationEventPublisher.publishEvent` 留 hook（`@TransactionalEventListener(phase=AFTER_COMMIT)`）；USER-103 未就绪则 listener 暂无人接，不报错、不阻塞推进事务 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!-- 问题清单写这里，然后 @coder 修 D15/GZ-ADMIN-104 revision 段 -->
