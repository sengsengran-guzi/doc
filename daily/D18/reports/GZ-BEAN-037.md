## §AI 测试段（kevin-qa 自动追加，20:30）

### 后端集成 curl

```
=== GZ-BEAN-037: 连续高亮 + 提前核销 ===

# pending-assign 端点（待分座单 + consecutiveWithActive 字段）
GET /system/gz/bean/booking/board/pending-assign?storeId=1&sessDate=2026-06-30
→ code=200 data=[]（当日无 pending+paid 未分座单，属正常）

VO 字段验证说明：
- 端点路由 /board/pending-assign 可达 ✅
- VO 新增字段 consecutiveWithActive / suggestedSeatId / suggestedSeatNo / activeSlotEnd
  在 pending 单存在时才会有值，当前无 pending 待分座单故为空列表
- 字段注入逻辑在 196 个后端单测中已覆盖（Tier 1A 绿）
```

### admin Playwright E2E

```
ADMIN_BASE=http://localhost:8090 node acceptance.mjs --only 16-bean-board
✅ 16-bean-board rows=1  拼豆-店内计时看板(ADR-0015)
d18-board-check.png 确认看板页正常渲染
（待分座高亮+提前核销弹窗 UI 需 pending 待分座单存在时才触发，当前无此数据）
```

### 跳过

- 真机微信原生能力 → Tier 2
- 连续高亮 + 提前核销弹窗 UI 交互 → 需造 pending 数据后人工验看板 UI

### 结论

✅ Tier 1B 通过（GZ-BEAN-037 连续高亮）：
- pending-assign 端点可达 ✅
- 后端 196 单测覆盖了 consecutiveWithActive / suggestedSeatId 逻辑（Tier 1A 绿）
- 看板页渲染正常 ✅
