# GZ-BEAN-008 — admin 预约列表 + 扫码 / 手动核销

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M4 §关键页面（后台） + M7.5 预约管理
**关联拆解**: doc/02-需求拆解.md §2.3 第 385 行
**关联 mockup**: design/mockup/admin-bookings.html（V1.0 设计冻结期：admin 完全走 ruoyi/Element Plus 默认审美，**不引用 mockup 视觉**，仅参考列功能项）
**关联 ADR**: —
**依赖**: GZ-BEAN-004 ✅(D04) + GZ-SYS-006 ✅(D02 操作日志规约)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §关键节点 N10 / N11（店员核销） + §异常分支 E6/E7/E8（重复扫码 / 已取消 / 已过期的拒绝逻辑）
- **字段表**：doc/11-字段权威表.md **§3.4 `gz_bean_booking`**（admin 端读取 + UPDATE 字段：status / verify_time / verify_operator_id） + §3.5 `gz_bean_booking_log`（核销动作写一条 log） + §A.3 状态字典
- **UI 参考**（设计冻结期）：admin 端**不依赖 mockup**，走 ruoyi/Element Plus 默认 BizTable + el-dialog + el-button 范式（CLAUDE.md §7.5）；复用 D03 ADMIN-002 列表模板结构

## What

admin 后台「预约管理」页：店员 / owner 角色登录后看到的预约列表，支持按门店 / 日期 / 状态筛选；提供两种核销方式 — ①扫码核销（点"扫码"按钮 → 调起摄像头 / 上传 QR 截图 → 解析 payload → 校验签名 + 状态 → 标 used）；②手动核销（在列表选中一行 pending 预约 → 点"核销"按钮 → 二次确认 → 标 used）。所有核销动作写操作日志（@Log）。

## AC（验收标准）

- [ ] **AC 1**：admin 端 `src/views/gz-bean/bookings.vue` 列表页，挂菜单 ID 段 6000-6099（CLAUDE.md §6 #6）；菜单挂在「谷子业务 / 拼豆预约 / 预约管理」目录下
- [ ] **AC 2**：列表展示字段：预约号 / 门店 / 用户昵称 + 手机号 / 日期 + 时段 / 座位编号 / 状态 tag / 创建时间 / 操作（核销 + 详情）；顶部筛选：门店下拉（仅 type=pindou）+ 日期 picker（默认今天）+ 状态多选 + 用户手机号模糊搜
- [ ] **AC 3**：调 `GET /gz/bean/admin/booking/page?storeId=&date=&statusList=&phone=&pageNum=&pageSize=` — 后端按筛选条件 + sa-token 当前用户 store_id（owner 看全部，staff 仅看自己绑定的 store_id，复用 D03 ADMIN-002 `gz_store_id` 绑定）
- [ ] **AC 4**：扫码核销 — 点"扫码"按钮 → 弹 el-dialog 含 `<input type="file" accept="image/*">` 上传 QR 截图（V1.0 admin 是 PC 端，**不调摄像头**，仅支持上传截图）→ 前端用 `qrcode-decoder` 类库解析 payload → 调 `POST /gz/bean/admin/booking/verify` 含 `{qrPayload: string}` → 后端校验签名 + status = pending → UPDATE status=used, verify_time=NOW, verify_operator_id=currentUserId + 写 booking_log
- [ ] **AC 5**：手动核销 — 列表行选中一条 pending 预约 → 点"核销"按钮 → el-message-box 二次确认 → 调 `POST /gz/bean/admin/booking/{id}/verify-manual` → 后端同样 status 校验 + UPDATE + booking_log（与扫码核销共用 service 方法，区别仅入口）
- [ ] **AC 6**：异常分支文案映射（doc/10 §3 E6/E7/E8）：已核销 → 「该预约已核销」/ 已取消 → 「该预约已取消」/ 已过期 → 「该预约已过期，请重新预约」/ 签名不通过 → 「核销码无效或已被篡改」
- [ ] **AC 7**：核销 Controller 方法加 `@Log(title="拼豆预约核销", businessType=UPDATE)` 注解（CLAUDE.md 强约束 + D02 GZ-SYS-006 操作日志规约）
- [ ] **AC 8**：i18n 全覆盖（`bean.admin.bookings.xxx`）；单测：service 层 verify(payload) happy path + 签名不通过 + status 非 pending 三个 case

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/admin/GzBeanBookingAdminController.java`（admin 路径前缀 `/gz/bean/admin`）
  - `service/IGzBeanBookingService.java` + impl 加 `verifyByQrPayload(payload, operatorId)` 和 `verifyByBookingId(bookingId, operatorId)`（共用底层 doVerify(booking, operatorId) 方法 — 事务 + SELECT FOR UPDATE + 状态校验 + UPDATE + log）
  - 复用 D04 `BeanQrService.verify(payload)` 校验 HMAC 签名
  - 不落新 DDL（verify_time / verify_operator_id 字段在 BEAN-004 DDL 已含）
- **Admin 前端**：`code/main/plus-ui/src/`
  - `views/gz-bean/bookings.vue`（列表 + 筛选 + 扫码 dialog + 手动核销 dialog，复用 BizTable + Element Plus 默认）
  - `api/gz-bean/booking.ts`（封装 page / verifyByPayload / verifyManual）
  - 引入 `qrcode-decoder` 或同类纯 JS QR 解码库（需 Kevin 批准 — CLAUDE.md §6 #8；优先确认 plus-ui 是否已自带）
- **测试**：admin 端走通"扫码核销"+"手动核销"+"扫已核销的码报错"三个 case；mvn 单测 `GzBeanBookingServiceImplTest`

## 备注

### 强约束

1. **不调摄像头**（V1.0 admin 是 PC 端，店员从手机相册截 QR → 上传文件）— 简化方案，避免摄像头权限 + UA 检测复杂度
2. **核销动作必须事务 + SELECT FOR UPDATE + 状态校验**（防 BEAN-007 取消的竞态，doc/10 §3 §并发控制）
3. **签名密钥统一**：与 D04 / BEAN-005 同源（`gz.bean.qr.signing-secret`），不要在本 ticket 重新生成
4. **@Log 注解必加**（操作日志可追溯，doc/11 §10.3 menu_id + sys_oper_log）
5. **菜单 ID 段 6000-6099 GZ-BEAN**（CLAUDE.md §6 #6）
6. **store_id 权限隔离**：staff 角色 query 必须强制 `WHERE store_id = current_user.gz_store_id`；owner 不限制

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | qrcode-decoder 类库引入 → CLAUDE.md §6 #8 不引未澄清依赖 | 优先确认 plus-ui 已有的 QR 类库（如 vue-qrcode-reader 或类似）；如真需新引 → 任务卡 §0 自检阶段 raise Kevin 批 |
| R2 | admin-bookings.html mockup 缺口 → 视觉无标准 | 设计冻结期约定 admin 走 ruoyi 默认，testing-human 不评判视觉；6/10 后甲方风格 review 时统一调 |
| R3 | 上传 QR 截图解析失败率（截图模糊 / 含其他内容） | 前端解析失败 → 友好提示「无法识别核销码，请重新截图」+ 给 Tier 2「手动核销」 fallback 路径 |

---

## §revision（Kevin testing-human 后填，初始空）
