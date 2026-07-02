## §AI 测试段（kevin-qa 自动追加，20:30）

### 后端集成 curl

```
=== GZ-BEAN-038: 延时改分钟 ===

# booking id=11 (used, 16:00-18:00) extend +15min
POST /system/gz/bean/booking/11/extend?addMinutes=15
→ code=200  slot_end: 18:00 → 18:15:00 (DB 确认精确到分)

# addMinutes=0 → 4019 (非法)
POST /system/gz/bean/booking/11/extend?addMinutes=0
→ code=4019 msg=延时分钟数非法，请输入 1-720 之间的正整数 ✅

# addMinutes=721 → 4019 (超上限)
POST /system/gz/bean/booking/11/extend?addMinutes=721
→ code=4019 msg=延时分钟数非法，请输入 1-720 之间的正整数 ✅

# 3b 链路验证：延时 15min → slot_end=18:15 → 18:00 格被占用
SQL: countActiveCoveringSlot(store=1, config=1, date=2026-06-30, slot=18:00)
→ active_cnt=1 ✅（延时溢入整点格，mp 余量 -1，available=7，single cap=8-1=7，不置灰但余量正确减少）
```

### admin Playwright E2E

```
ADMIN_BASE=http://localhost:8090 node acceptance.mjs --only 16-bean-board
✅ 16-bean-board rows=1  拼豆-店内计时看板(ADR-0015)  截图存在
d18-board-check.png 确认看板页正常加载
```

### mp 模拟器 E2E

```
node test/e2e/run.mjs smoke
preflight: CLI ✓ / dist ✓ / backend ✓
[PASS] smoke（4 页全部渲染 + 可达）

3b 视觉验证：API 层已验 countActiveCoveringSlot 正确反映延时占格；
mp 下单页格子 full 判断取决于余量 ≤0，当前 single cap=8 仅占 1，不置灰属正常。
单桌型单座延时验证通过（余量逻辑正确）。
```

### 跳过

- mp 真实支付 / getPhoneNumber / 客服 / 真机扫码 / 登录头像昵称授权 / 真机性能 → Tier 2
- 设计首版视觉 → Kevin 节点触发

### 结论

✅ Tier 1B 通过（GZ-BEAN-038 延时改分钟）：延时分钟参数名修正 ✅、精确到分 ✅、4019 边界 ✅、3b 余量联动 ✅。
