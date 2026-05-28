# GZ-BEAN-004 ★ — 提交预约 + UNIQUE 索引 + Redis 锁

**优先级**: P0
**复杂度**: M（V1.0 最复杂 ticket — L 级思考密度，禁止快速过 §0 自检）
**关联 PRD**: doc/02-prd.md M4 §用户操作流程 步骤 6-7 + §并发处理 + §业务规则
**关联拆解**: doc/02-需求拆解.md §2.3 第 326 行
**关联 mockup**: design/mockup/booking-select.html（提交按钮 + fixed CTA 条 — 视觉参考）
**关联 ADR**: —（如本日 BEAN-004 实施期间需要决策"是否引入分布式锁框架"等可新建 ADR 0001）
**依赖**: GZ-BEAN-003 + GZ-SYS-002 ✅(D02)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 重点反复读）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** **全文**，特别是：
  - §状态机（pending → used / cancelled / no_show 4 态完整定义）
  - §关键节点 步骤 6（提交）+ 步骤 7（核销码生成）
  - **§并发控制**（三层防线 UNIQUE / Redis / 业务校验 — 本 ticket 实现锚定）
  - §异常分支（手机号未绑 / 座位已占 / Redis 锁竞争 / 网络断 重试 全部场景）
  - §业务规则（同用户同时段最多 1 预约 / 取消不限时 / no_show 凌晨自动）
- **字段表**：doc/11-字段权威表.md
  - **§3.4 `gz_bean_booking`**（核心表 — 完整 DDL 来源 + UNIQUE 索引定义）
  - §3.5 `gz_bean_booking_log`（状态变更日志）
  - §3.6 拼豆状态字段详细口径
  - **§3.7 关键 Redis Key 规则**（`bean:lock:{user_id}:{date}:{slot_start}` TTL / key naming）
  - §2.1 gz_user 手机号字段（强收集场景）
- **UI 参考**（设计冻结期）：`booking-select.html` 底部 CTA 提交按钮 — 视觉参考；手机号绑定弹窗用 wd-popup 默认

## What

mp 端用户在 BEAN-003 选座完成后跳本页，点提交：
1. 校验登录 + 手机号绑定（未绑 → 弹绑定流程，绑完继续）
2. Redis 锁 `bean:lock:{user_id}:{date}:{slot_start}` 5s TTL（防同一用户连点）
3. DB 事务内：
   - 校验同一用户同时段无 active 预约（SELECT count FROM gz_bean_booking）
   - INSERT gz_bean_booking → UNIQUE 索引拦截抢座撞车（兜底，正常路径不应该撞）
   - INSERT gz_bean_booking_log（pending 状态首条记录）
   - 生成核销码 payload（booking_id + HMAC 签名）
4. 返回核销码 → mp 端渲染 QR + 跳转 BEAN-005 详情页

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606011200__GZ-BEAN-004-create-gz_bean_booking-and-log.sql` 落两张表：
  - `gz_bean_booking`（id / store_id / seat_id / date / slot_start / slot_end / user_id / phone_num_snapshot / status enum / qr_payload / qr_signature / created_at / updated_at + 公共字段）
  - **UNIQUE KEY** `uk_tenant_seat_slot (tenant_id, store_id, seat_id, date, slot_start) WHERE status IN ('pending','used')` ⭐ **关键防抢座**
  - 索引 `idx_user_status_date (user_id, status, date)` `idx_store_date (store_id, date)`
  - `gz_bean_booking_log`（id / booking_id / from_status / to_status / operator_type enum(`user`/`admin`/`cron`) / operator_id / reason / + 公共字段）
- [ ] **AC 2**：mp 端 `POST /app/gz/bean/booking/submit`（参数 store_id + date + slot_start + slot_end + seat_id）→ 提交链路：
  - sa-token mp-client 校验 → 拿 user_id
  - 校验 user.phone_num 已绑（未绑 → 返回 errCode=`PHONE_REQUIRED` + 提示前端弹手机号流程）
  - **Redis 锁**：`redis.set("bean:lock:{user_id}:{date}:{slot_start}", "1", "EX", 5, "NX")` → false 时返回「请勿重复提交」
  - **DB 事务**：
    - 应用层校验：`SELECT COUNT(*) FROM gz_bean_booking WHERE user_id=? AND date=? AND slot_start=? AND status IN ('pending','used')` > 0 → 返回「同时段已有预约」
    - `INSERT gz_bean_booking ... status='pending'`（UNIQUE 撞 → DB throw → catch 返回「座位已被占」）
    - 生成核销码 payload `{bookingId, ts, sign}`；sign = HMAC-SHA256(payload, `gz.bean.qr.signing-secret` from config)
    - UPDATE gz_bean_booking SET qr_payload + qr_signature WHERE id = newId（或合并到上一步 INSERT）
    - INSERT gz_bean_booking_log（from_status=null, to_status='pending', operator_type='user', operator_id=user_id）
- [ ] **AC 3**：mp 端手机号强收集流程：
  - 检测到 errCode=`PHONE_REQUIRED` → 弹 `<wd-popup>` 提示「拼豆预约需提供手机号 → 授权」
  - 用户点授权按钮 `<button open-type="getPhoneNumber" @getphonenumber="onPhone">` → 后端 `POST /app/gz/common/user/phone-bind`（参数 encryptedData + iv）→ 后端用 user.session_key 解码 → UPDATE gz_user.phone_num
  - 绑定成功 → 自动重新提交（同一调用上下文）
  - 用户拒授权 → 退回 BEAN-003 选座页，toast「需手机号才能预约」
- [ ] **AC 4**：核销码生成逻辑：
  - payload = `{bookingId: 12345, ts: 1717228800, expires: 1717315200}` JSON 字符串（24h 有效）
  - signature = HMAC-SHA256(payload, secret)，base64 encode
  - mp 端用 qrcode-uni 或 wxapi.createOffscreenCanvas 渲染 QR
- [ ] **AC 5**：单测必须覆盖：
  - happy path（mock Redis + DB 完整流程）
  - 同一用户同时段第二次提交 → 应用层拦截
  - 不同用户抢同座位 → UNIQUE 拦截（mock DB throw DuplicateKeyException）
  - Redis 锁竞争 → 第二个请求被锁
  - 手机号未绑 → 返回 PHONE_REQUIRED
  - 共 5 个测试方法，全部 raw assertion
- [ ] **AC 6**：写操作加 @Log
- [ ] **AC 7**：**reports 必须包含并发压测 raw output**（`ab -n 100 -c 50` 或 `wrk -t10 -c50 -d10s` 压同一时段同一座位的提交接口 → DB 最终该座位 status='pending' 仅 1 条；其他 99 个请求被 Redis 锁 / UNIQUE 拦截，返回友好错误）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/applet/GzBeanBookingMpController.java`（mp 路径 `/app/gz/bean/booking`）+ `submitBooking()` 方法
  - `controller/applet/GzUserPhoneMpController.java`（mp 路径 `/app/gz/common/user/phone-bind` — 跨域到 gz-common 也行，但本日为聚焦 BEAN 放这）
  - `service/IGzBeanBookingService.java` + `service/impl/GzBeanBookingServiceImpl.java`（核心业务逻辑）
  - `service/internal/QrCodeSigner.java`（HMAC 签名工具，独立 Bean 便于测试 mock）
  - `domain/GzBeanBooking.java` + `GzBeanBookingLog.java` + VO + BO
  - `mapper/GzBeanBookingMapper.java` + `GzBeanBookingLogMapper.java`
  - DDL × 1（两表一文件）
  - `application-dev.yml` + `application-staging.yml` + `application-prod.yml` 加 `gz.bean.qr.signing-secret`（dev 随机字符串 / staging/prod env var 占位符）
- **小程序**：
  - `pages/bean/confirm.vue`（提交确认页 — 显示选中信息 + 提交按钮）
  - `pages/bean/qr.vue`（提交成功后跳转，显示核销码 QR + 调 BEAN-005 详情接口）
  - `components/biz/BizPhoneBindPopup.vue`（手机号绑定弹窗）
  - `api/gz-bean.ts` 加 `submitBooking()` + `api/gz-common.ts` 加 `bindPhone()`
  - `composables/useBookingSubmit.ts`（提交编排：phone check + submit + redirect）
- **测试**：mvn 单测 + 浏览器并发压测 + 微信开发者工具实操（2 个工具同时点同座位）

## 备注

### 强约束 ★

1. **三层防并发是不可绕过的兜底**（doc/10 §3 §并发控制 权威）：UNIQUE / Redis / 业务校验缺一不可
2. **UNIQUE 索引必含 tenant_id**（CLAUDE.md §6 #3）+ 必含 status 部分索引（仅 pending/used；cancelled/no_show 不参与 unique）
   - MySQL 不支持部分索引，做法是 unique key 不带 status，业务上 cancelled / no_show 仍占索引位 — **但状态约束保证**：用户取消后该座位释放给其他用户，做法是 UNIQUE on `(tenant_id, store_id, seat_id, date, slot_start, status)` 让 cancelled / no_show 可以与 pending 共存（多 status 仍唯一）。**正确做法**：UNIQUE 索引含 status 但只对 status='pending' 与 status='used' 起作用 — 实现上：取消时 status='cancelled' 后该行仍占 UNIQUE，新预约抢同座会撞 → 不对！应该用业务删除（DELETE cancelled）或 UNIQUE 不含 status 但靠应用层判定。
   - **最终方案**（doc/11 §3.4 锚定）：UNIQUE `(tenant_id, store_id, seat_id, date, slot_start)` 不含 status；取消时 **物理删除** gz_bean_booking 行 + 在 gz_bean_booking_log 留审计；no_show 同理（cron 把 booking 删但 log 留）
   - **审计完整性**：gz_bean_booking_log 永不删，永远可查历史；gz_bean_booking 仅保留 active 行
3. **手机号是 V1.0 唯一强收集场景**（doc/10 §3）
4. **核销码签名密钥不进 git**（dev 可硬编码 / staging+prod env var）
5. **核销码有效期 24h**（业务上：预约日当日 + 1 天）— payload 含 `expires`，后台核销时校验

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | UNIQUE 不含 status + 取消时物理删 booking 行（log 留）| 避免部分索引复杂度；审计走 booking_log 表 |
| D2 | Redis 用普通 SET NX EX 5s，不引 Redisson | V1.0 流量小（拼豆并发预计 < 50 req/s），普通锁够用；Redisson 引入增加依赖 |
| D3 | 核销码用 HMAC-SHA256 而非 JWT | JWT 太重（payload 字段多），HMAC-SHA256 + 自定义 payload 更简洁 |
| D4 | 手机号绑定弹窗放业务组件 `<BizPhoneBindPopup>` | 后续 V1.1 业务支付下单也可能复用（虽然 V1.1 用法不同），抽组件 |
| D5 | qr_payload 落库（不仅在响应返回）| BEAN-005 详情页用 GET 拉 qr payload 渲染（不复算）— 服务器变更签名密钥时旧 QR 仍有效 |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ★ | 并发压测发现 UNIQUE 撞但应用层未友好处理 | catch DuplicateKeyException → 返回 errCode=`SEAT_TAKEN` + 前端 toast「座位已被占，请重选」+ 自动跳回 BEAN-003 |
| R2 | Redis 锁过期但 DB 事务未完成 → 第二个请求乘虚而入 | 锁 TTL 5s + DB 事务实测 < 200ms（V1.0 数据量小），不会超时；如出现压测时 DB 抖 → 锁加到 10s |
| R3 | wx.getPhoneNumber 解码失败（session_key 已过期）| 后端 catch + 提示用户重新登录（清 token）→ 重走 SYS-002 流程 |
| R4 | QR 渲染失败（低端机微信版本）| 兜底显示 booking_id 文本 + 提示用户截图给店员手动核销 |
| R5 | 签名密钥泄漏 → 伪造核销码 | dev 硬编码可接受 / staging+prod 走 env var；上线前生成长随机字符串（32+ 字符）|
| R6 | 应用层校验 "同用户同时段无 active 预约" 与 INSERT 之间的窗口 | 用 DB 事务 + SELECT FOR UPDATE 锁住 user_id 那几行（虽然不直接更新但 lock）；性能可接受 |

### ADR 候选（如本日实施时遇到分歧）

- **ADR-0001**：是否引入 Redisson（vs 普通 set NX）— 默认 D2 普通锁；如压测发现锁竞争频繁 → 新建 ADR-0001 评估
- **ADR-0002**：核销码格式（HMAC vs JWT vs 自签发 token） — 默认 D3 HMAC

---

## §revision（Kevin testing-human 后填，初始空）
