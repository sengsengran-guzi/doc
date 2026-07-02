## §AI 测试段（kevin-qa 自动追加，20:30）

### 后端集成 curl

```
=== GZ-BEAN-039: 代客预定 ===

# Happy path: 传已有 mobile=13800000000，storeId=1, seatTypeConfigId=1, seatId=13, 16:00-18:00
POST /system/gz/bean/booking/admin-create
Body: {storeId:1, seatTypeConfigId:1, seatId:13, sessDate:"2026-06-30", slotStart:"16:00:00",
       slotEnd:"18:00:00", mobile:"13800000000", customerName:"测试客户A", amountCent:8000}
→ code=200 bookingId=11 status=used payStatus=paid source=None(VO序列化)
DB确认: status=used, pay_status=paid, source=admin, amount_cent=8000, remark="代客预定：测试客户A" ✅

# 防超卖：同座同时段重复 admin-create → 期望 4002
第二次 admin-create 同参数
→ code=200（BUG: 期望 4002 SEAT_TAKEN，实际放行，DB 产生重叠记录 id=11/12）❌

# 配额满 → 4011（验证：seat_closure 关闭全部单人座 → 有效容量 0）
POST admin-create slotStart:"14:00:00" slotEnd:"16:00:00"
→ code=4011 msg=该时段座位已约满（seat_closure 覆盖 10:00-16:00，有效容量=8-8=0）✅ 逻辑正确

# 无 mobile → 创建散客占位用户（BUG）
POST admin-create 不传 mobile
→ code=500 cause: "Field 'user_no' doesn't have a default value"
  resolveProxyBookingUserId 插 gz_user 时未 set user_no（NOT NULL 无 default）❌
```

### 发现 BUG

**BUG-1（严重）**：同座同时段两次 admin-create 均成功，DB 有两条重叠记录。
- 现象：`countActiveCoveringSlotForUpdate` + `selectActiveSeatOverlapForUpdate` 应拦截，实际放行。
- 期望：第二次返回 code=4002。
- 已清理重复数据（DELETE id=12）。

**BUG-2（一般）**：不传 mobile 时，`resolveProxyBookingUserId` 创建散客用户缺少 `user_no` 字段。
- 现象：INSERT gz_user 报 "Field 'user_no' doesn't have a default value"。
- 修复建议：`resolveProxyBookingUserId` 里 `new GzUser()` 后加 `created.setUserNo(generateUserNo(tenantId))`（参考正常登录注册路径）。

### admin Playwright E2E

```
ADMIN_BASE=http://localhost:8090 node acceptance.mjs --only 13-bean-booking
✅ 13-bean-booking rows=8  拼豆-预约管理  截图存在
d18-booking-check.png 确认「代客预定」按钮存在于预约管理页 ✅
```

### 跳过

- 真机微信原生能力 → Tier 2
- 代客预定弹窗完整级联（门店/日期/时段/桌型/座位）UI 流程 → 需人工点选 admin 弹窗

### 结论（初测）

❌ Tier 1B 部分失败（GZ-BEAN-039 代客预定）：
1. BUG-1：同座同时段重复代客预定未被 4002 拦截（防超卖漏洞）
2. BUG-2：无 mobile 时散客用户创建失败（user_no 缺失）

---

## §AI 测试段 复测（kevin-qa，20:45，coder 修后重跑）

后端已重启（新 jar 含 BUG-1/BUG-2 修复）。

### 复测 BUG-1 防超卖

```bash
# 第一单：storeId=1, seatTypeConfigId=1, seatId=13, 2026-06-30 16:00-18:00, mobile=13800000000
POST /system/gz/bean/booking/admin-create
→ code=200 bookingId=20 status=used payStatus=paid

# DB 确认：seat_id 真落库
id  status  pay_status  seat_id  slot_start  slot_end   source
20  used    paid        13       16:00:00    18:00:00   admin
✅ seat_id=13 在 INSERT 时已绑定（修复：先 assignSeatAtVerify 绑座再 insert）

# 第二单：同 seatId=13 同时段 → 期望 4002
POST /system/gz/bean/booking/admin-create（相同参数）
→ code=4002 msg=该座位该时段已被预约，请重选座位或时段 ✅

# DB 无重叠记录
SELECT COUNT(*) FROM gz_bean_booking WHERE sess_date='2026-06-30' AND slot_start='16:00:00' AND seat_id=13
→ cnt=1 ✅（未产生第二条重叠记录）
```

**BUG-1 修复验证：PASS ✅**

### 复测 BUG-2 散客用户

```bash
# 第一次不传 mobile：storeId=1, seatTypeConfigId=1, seatId=17, 19:00-20:00
POST /system/gz/bean/booking/admin-create（无 mobile 字段）
→ code=200 bookingId=21 status=used payStatus=paid ✅

# DB 确认：gz_user 创建 WALKIN 占位用户
id  user_no      openid                 nickname  register_source
8   WALKIN-1001  offline-walkin-1001    线下散客   admin
✅ user_no=WALKIN-1001，openid=offline-walkin-1001

# booking 关联散客用户
id  user_id  mobile_snapshot  source
21  8        00000000000      admin ✅

# 第二次不传 mobile → 复用同一散客用户（find-or-create 幂等）
POST /system/gz/bean/booking/admin-create（seatId=21, 同时段，无 mobile）
→ code=200 bookingId=22

# DB 确认：gz_user 只有 1 条 WALKIN（不重复建）
SELECT COUNT(*) FROM gz_user WHERE openid='offline-walkin-1001' → walkin_user_count=1 ✅
booking id=22 user_id=8（复用同一散客）✅
```

**BUG-2 修复验证：PASS ✅**

### 结论（复测）

✅ Tier 1B 全通过（GZ-BEAN-039 代客预定）：
- happy path（传已有 mobile）→ 200 status=used payStatus=paid source=admin ✅
- 防超卖：同座同时段第二单 → 4002 ✅；DB 无重叠记录 ✅
- 散客用户：无 mobile → 创建 WALKIN-1001 占位用户 ✅；二次复用不重建 ✅
- 配额满 → 4011 ✅（seat_closure 覆盖，有效容量=0）

ticket GZ-BEAN-039 可 close。
