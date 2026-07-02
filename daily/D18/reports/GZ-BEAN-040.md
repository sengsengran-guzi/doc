## §AI 测试段（kevin-qa 自动追加，20:30）

### 后端集成 curl

```
=== GZ-BEAN-040: 改派座位 ===

# Happy path: used 单 id=11 (seat=13 S1) 改派到 seat=17 (S2，同 seatTypeConfigId=1)
POST /system/gz/bean/booking/11/reassign-seat?seatId=17
→ code=200 seatId=17 seatNo=S2 ✅
DB确认: gz_bean_booking id=11 seat_id=17

# 改派到时段重叠座 → 4002
先建 seat=21(S3) 17:00-19:00 的 used 单(id=14)
id=11 是 16:00-18:15，改派到 seat=21 → 区间重叠
POST /system/gz/bean/booking/11/reassign-seat?seatId=21
→ code=4002 msg=该座位该时段已被预约，请重选座位或时段 ✅

# 已放座单改派 → 4017
先 POST .../11/release-seat → code=200（设 actual_end_time）
再 POST .../11/reassign-seat?seatId=24
→ code=4017 msg=该预约非在店使用中，不可执行此看板操作（该单已放座，不可改派）✅

# 已取消/非 used 状态改派（隐式验证：放座后 status 仍 used，由 actual_end_time 区分）
已放座的单 status=used、actual_end_time!=null → 4017 ✅
```

### admin Playwright E2E

```
✅ 16-bean-board 渲染 OK（看板页可见）
UI 抽屉改派按钮需 used 单存在时手动点开抽屉验证；admin 截图已存档。
```

### 跳过

- 真机微信原生能力 → Tier 2
- 抽屉「改派座位」弹窗 UI 交互 → 需人工点选（seat 选择器级联）

### 结论

✅ Tier 1B 通过（GZ-BEAN-040 改派座位）：
- happy path 改派 ✅
- 时段重叠 4002 ✅
- 已放座单 4017 ✅
