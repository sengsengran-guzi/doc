# GZ-RECYCLE-002 — 回收预约单 + 自动估价 + mp 填单页（用户提交拍照 submit_image_ids 必填）

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md M10 §回收
**关联拆解**: doc/02-需求拆解.md §3.6.5 GZ-RECYCLE-002
**关联 ADR**: ADR-0004（mp 权限，店员端在 003）
**依赖**: GZ-RECYCLE-001（D13，`gz_recycle_price_rule` + estimate service + dict `gz_recycle_category`）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §13（回收预约全流程 N1-N5 + 估价口径 + E1/E7）
- **字段表**：doc/11-字段权威表.md §12.2（`gz_recycle_appointment` 全字段 + 回收状态机）+ §12.3 F12.1/F12.4（多品类累加 + 两套照片）+ 附录 A.20（回收态 dict）/ A.21（回收品类 dict）
- **UI 参考**（mp，C 日漫海报浓墨）：doc/12 §4.0 tab2 回收 = MP-RECYCLE-FORM（`/pages/recycle/form`）+ §MP-RECYCLE-LIST；doc/tokens.md + doc/13 为视觉真源（不逐像素还原）

## What

建 `gz_recycle_appointment`（回收预约单主状态机，本卡只产 `submitted`）+ 用户 mp 回收填单页：填品类×数量×描述（可多条）→ 实时自动估价 + 时长匹配 → **上传实物照片（submit_image_ids 必填）** → 选受时长约束的到店时段 → 采手机/微信号 → 提交。多品类各自命中价目表区间累加估价。

## AC（验收标准）

- [ ] AC 1：DDL `gz_recycle_appointment`（doc/11 §12.2 全字段，时间戳 > 已有最大版本 V202606210201）：appointment_no(`RCY-yyyyMMdd-6位`)/user_id/store_id/product_snapshot_json(JSON 不散列)/total_qty/matched_duration_minutes/estimated_amount_cent/appt_date/slot_start/slot_end/submit_image_ids(NOT NULL)/verify_image_ids(NULL)/final_amount_cent(NULL)/verified_by/verify_time/receiver_openid/mobile_snapshot/wechat_id_snapshot/out_payout_no/status(default 'submitted')/cancelled_time/version。`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` + del_flag 2 值 + 索引（UNIQUE(tenant_id,appointment_no) / IDX user_id / (store_id,appt_date,slot_start) / status / out_payout_no）。menu 13002 段（回收预约单管理目录占位，owner 授权）。
- [ ] AC 2：**自动估价 + 时长匹配**（doc/10 §13.N3 + doc/11 F12.1）：提交时按 `product_snapshot_json` 每条 (category, qty) 调 RECYCLE-001 `estimate(category, qty)` → `estimated_amount_cent = Σ 各品类(unit_price_cent × 该品类数量)`；`total_qty = Σ 各品类数量`；`matched_duration_minutes` 按总时长匹配口径冻结（实施时定：多品类取 Σ 各命中 duration 或按 total_qty 命中，reports 写明选型 + 理由）。提交时三值冻结进预约单。
- [ ] AC 3：**用户提交拍照 submit_image_ids 必填**（doc/10 §13.N2.5/E7，钉死）：mp 填单页含「上传实物照片」项，**前端 + 后端 Bo `@NotEmpty` 双重校验**，无照阻断提交（后端拒收报「请先拍照上传实物再提交」）。图片走 COS 上传（`uploadFile(tempPath, 'recycle_submit_image')`）存 image_id（逗号分隔，FK gz_file_object，`usage_type=recycle_submit_image`，**不存裸 url**）。后端 GzFileUsageType 新增 `RECYCLE_SUBMIT_IMAGE`。
- [ ] AC 4：**快照字段**（doc/11 §12.2）：提交时 snapshot `receiver_openid`（从 gz_user.openid，反向打款必需）+ `mobile_snapshot` + `wechat_id_snapshot`（采集沿用 doc/10 §11.N6 / bean 付费页 getPhoneNumber + 手填微信号范式）。无 openid → E5 拦截提示补授权。
- [ ] AC 5：**超区间 E1 提示**（doc/10 §13.E1）：某品类数量未命中任何价目区间（estimate 抛「无报价规则」）→ mp 提示「该品类暂不支持线上估价，请到店咨询」，不阻断其余品类，但含未估价品类时不可提交（或按 Q13.2 默认到店咨询）。reports 写明分支处理。
- [ ] AC 6：mp 填单页走 C 系统：只用 `src/components/biz/Biz*` + `var(--c-*)` token，不直接撒 `<wd-*>`；不混 emoji。复用 bean/index.vue 的 BizDatePicker / 时段 chip / getPhoneNumber 范式。页面路由 `/pages/recycle/form`（doc/12 §4.0）。
- [ ] AC 7：mp api 封装 `src/api/gz-recycle.ts`（estimate 试算 + submit 预约 + 我的回收记录列表）+ vitest 单测（透传 url/method/body，仿 gz-bean.test.ts）；id 跨层用 string。
- [ ] **AC 8: Tier 2 入口可达**（mp 强制，CLAUDE.md §8.3）— 本批 SYS-010 同日做 tabbar「回收」真入口，但 RECYCLE-002 若先完工 → **加临时入口** `<!-- TODO(Tier2-entry-temp): GZ-RECYCLE-002, remove when GZ-SYS-010 merged -->` 到 `pages/index/index.vue`（现首页入口网格）跳 `/pages/recycle/form`，N=1。SYS-010 用真「回收」tab 替换。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-recycle/`（包 `org.dromara.gz.recycle.*`）
  - entity `GzRecycleAppointment` + Bo（`GzRecycleAppointmentSubmitBo`，submit_image_ids `@NotEmpty`）+ VO + Mapper + IService/Impl + Controller（mp `/app/gz/recycle/...` + 估价复用）
  - 估价：注入 `IGzRecyclePriceRuleService.estimate`（已在 gz-recycle，无跨模块）
  - appointment_no 生成器（仿 PayoutNoGenerator / 拼豆 bookingNo 范式）
  - DDL `V<yyyyMMddHHmm>__GZ-RECYCLE-002-create-appointment.sql` + menu seed（13002 段）
  - GzFileUsageType 新增 `recycle_submit_image`（后端枚举，所在模块按现有 usage_type 定义处）
- **小程序**：`miniapp/src/pages/recycle/form.vue`（+ form.logic.ts 抽纯函数便于单测）+ `src/api/gz-recycle.ts` + `gz-recycle.test.ts`；mp GZ_FILE_USAGE_TYPE 加 `RECYCLE_SUBMIT_IMAGE`
- **测试**：估价累加 / 时长冻结 / submit_image_ids 必填校验 service 单测（≥ happy path + E1 + 空照拒收）

## 备注

- 本卡只产 `submitted`；confirmed_onsite 起在 RECYCLE-003。final_amount_cent/verify_image_ids/verified_by 本卡建列不写值。
- 「我的回收记录」列表页（MP-RECYCLE-LIST）可本卡建只读壳（list 接口 + 简单列表），详情/状态展示随 003 完善；或留 003。reports 写明边界。
- 字段硬约束：金额 `_cent` / JSON 列不散列（product_snapshot_json）/ 图片不存裸 url / 业务码 `RCY-` / version 乐观锁 / tenant_id String '1001'。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 待 Kevin 批量人验填 -->
