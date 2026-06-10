# GZ-RECYCLE-003 — 店员核对 + 拍照 + 触发反向打款 + admin 管理

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md M10 §回收 + M10-B §反向打款
**关联拆解**: doc/02-需求拆解.md §3.6.5 GZ-RECYCLE-003
**关联 ADR**: ADR-0004（mp 管理端权限复用）+ ADR-0006（反向打款幂等/查单优先）
**依赖**: GZ-RECYCLE-002（`gz_recycle_appointment`）+ GZ-PAY-105（D13，`IGzPayPayoutService.initiatePayout` + mock）+ ADR-0004（已交付，店员端权限底座）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §13（N6-N12 店员核对 + 触发打款）+ §14（反向打款时序 N1-N6 + 幂等 + mock）
- **字段表**：doc/11-字段权威表.md §12.2（核对字段 final_amount_cent/verify_image_ids/verified_by/verify_time/out_payout_no/status 推进 + 触发打款幂等）+ §4.8（`gz_pay_payout_transaction`）+ §4.6 补注（回收反向出账独立核算不计 GMV）
- **ADR**：ADR-0004（openid 绑 sys_user + @SaCheckPermission + 停用即踢）/ ADR-0006（out_payout_no + batch_id 双重幂等 + 主动查单优先 + mock）
- **UI 参考**：mp 店员核对页走 C 系统（doc/tokens.md + doc/13）；admin 走 ruoyi/Element Plus 默认（不引 mockup）

## What

mp 店员端核对页（复用 ADR-0004 权限）：按 appointment_no 调出预约 → 核对实物 → 拍照（verify_image_ids）→ 微调 final_amount_cent（留痕）→ 确认 `submitted→confirmed_onsite` → 触发反向打款（调 D13 PAY-105，`confirmed_onsite→paying`，success `paid`/failed `payout_failed`）。+ admin（plus-ui owner 兜底）回收预约单管理 + 反向打款单管理。

## AC（验收标准）

- [ ] AC 1：**mp 店员核对**（doc/10 §13.N7/N8）：店员端按 appointment_no 调出预约（可见用户 submit_image_ids 实物照 + 物品清单 + 估价）→ 拍照存 `verify_image_ids`（COS `usage_type=recycle_verify_image`，逗号分隔 image_id FK gz_file_object，**不存裸 url**）→ 微调 `final_amount_cent`（默认 = estimated_amount_cent，可改）→ 确认 → `submitted→confirmed_onsite`，**留痕** `verified_by`（核对店员 admin 用户名）+ `verify_time` + ops log。version 乐观锁推进。
- [ ] AC 2：**触发反向打款**（doc/10 §13.N9 + §14，幂等关键）：confirmed_onsite 时调 `IGzPayPayoutService.initiatePayout(new InitiateBo("recycle", appointment_no, userId, receiver_openid 快照, final_amount_cent, transferRemark))` → 回写 `gz_recycle_appointment.out_payout_no` + `status=paying`；mock 链路 created→processing→（查单 SnailJob/手动）success → 回写 `status=paid`；failed → `status=payout_failed`。**幂等已内建于 PAY-105**（重复触发返回已有单不二次转账），RECYCLE-003 不自己防重，但 `version` 乐观锁防并发推进。
- [ ] AC 3：**失败重试**（doc/10 §13.E4）：payout_failed 单 owner 可重试 → 调 PAY-105 `retryFailedToCreated` 后重新 initiate → `paying`；不无限自动重试。
- [ ] AC 4：**mp 店员端权限**（复用 ADR-0004）：核对页走 `@SaCheckPermission`（新增权限点如 `gz:recycle:appointment:verify`）+ 同租户 1001 + 停用/解绑 sys_user 即时踢（401/403）；**不用 @SaCheckRole**。mp useStaff hook 加 PERM_RECYCLE_VERIFY，「我的（店员端）」门店管理区加「回收核对」入口。
- [ ] AC 5：**admin（plus-ui owner 兜底，AI 终态）**：①回收预约单管理（列表 + 详情，按门店/日期/状态筛，详情显两套照片 + 估价/实付/核对留痕）；②反向打款单管理（状态查看 / 主动查单 / failed 重试）。走 ruoyi/Element Plus 默认 + BizTable，**不引 mockup**。menu 13003（回收预约单 admin）+ 反向打款 admin 挂 5110 段（PAY-105 已占 menu，复用其列表或新增 owner 视图）。
- [ ] AC 6：**回收反向出账独立核算**（doc/11 §4.6 补注）：payout `business_type='recycle'`，不计 GMV、不参与 4% 分成、不进对账中心 §9。代码注释 + reports 写明。
- [ ] AC 7：no_show 兜底（doc/10 §13.N12 / F12.3）：优先店员标记；可选 SnailJob 凌晨扫超 appt_date 仍 submitted 单 → no_show（`@Component + @JobExecutor` 薄壳 + 可单测 service，模块 pom 加 ruoyi-common-job；任务名/CRON 写 reports + testing-human，**禁止 Flyway INSERT sys_job**）。如本卡落地写明任务名。
- [ ] **AC 8: Tier 2 入口可达（店员端）**（mp 强制）— 店员账号登 mp →「我的（店员端）」门店管理 →「回收核对」N 次到达核对页；业务主线入口未建则加临时入口 `TODO(Tier2-entry-temp): GZ-RECYCLE-003`。
- [ ] AC 9：单测覆盖 RECYCLE-003 触发打款幂等 + 状态机流转 ≥ 80%（资金相关）：confirmed_onsite→paying→paid 全链路 + 重复触发同一 appointment 不重复 payout + failed→payout_failed 可重试 + 微调留痕。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-recycle/`（核对 service + 触发打款，注入 `IGzPayPayoutService`，pom 已依赖 gz-common）
  - service：verify（核对+拍照+微调+确认+触发打款，@Transactional）+ retryPayout + admin 列表/详情
  - controller：mp `/app/gz/recycle/staff/...`（@SaCheckPermission）+ admin `/system/gz/recycle/appointment/...`
  - DDL：权限菜单 seed（13003 段 + 回收核对权限点）`V<yyyyMMddHHmm>__GZ-RECYCLE-003-menu.sql`；如建表外仅菜单/权限
  - SnailJob no_show（如落地）
- **Admin**：`plus-ui/src/views/gz-recycle/appointment/*` + 反向打款单管理（gz-pay 域或复用 PAY-105 视图）+ api/router/permission
- **小程序**：`miniapp/src/pages/recycle/staff-verify.vue`（+ logic.ts）+ `src/api/gz-recycle.ts` 扩 staff 接口 + useStaff PERM_RECYCLE_VERIFY + me/index.vue 门店管理入口
- **测试**：触发打款幂等 + 状态机 service 单测 ≥ 80%

## 备注

- mock 全链路：`gz.pay.client.mode=mock`，confirmed_onsite→paying→查单 success→paid；真实商家转账权限 + SDK 列【外部前置风险】（ADR-0006），不当默认就绪。
- 字段硬约束：final_amount_cent / verify_image_ids 不存裸 url / verified_by+verify_time 留痕 / business_type='recycle' / version 乐观锁防重复触发。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 待 Kevin 批量人验填 -->
