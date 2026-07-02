# GZ-BEAN-036 完工报告 — 拼豆按星期+时段关闭座位 Req3 + Req1 价格区间填充

## §AI 测试段（kevin-qa Tier 1B，06-30）

### admin Playwright E2E

工具：puppeteer-core + system Chrome（`/Applications/Google Chrome.app`），pushState+popstate 客户端跳转。

---

**TEST 1 — 座位关闭规则 CRUD（新页 /gz-bean/seat-closure）**

```
PASS: 导航 /gz-bean/seat-closure → 页面渲染：el-table + 筛选区 4 个 el-select（门店/座位/星期/启用）+ 新建关闭按钮
PASS: 点「新建关闭」→ 对话框打开（标题：批量新建座位关闭）
PASS: 通过 Vue 响应式状态直接设置：seatIds=[A1(id=1)], weekdays=[2], startHour=10, endHour=12
      UI 回显验证：seatTags=["A1"], weekdayChecked=["周二"], selectSelected 包含"A1","10:00","12:00"
FAIL: 提交 → API 400，msg: "请求参数格式错误：Text '10:00:00' could not be parsed, unparsed text found at index 5"
      API body: {"storeId":1,"seatIds":["1"],"weekdays":[2],"timeStart":"10:00:00","timeEnd":"12:00:00","remark":null}
      后端 @JsonFormat(pattern = "HH:mm") 只接受 "HH:mm"，前端 hourToTime() 错误输出 "HH:00:00" (HH:mm:ss)
```

**根因定位（精确）**：
```typescript
// src/views/gz-bean/seat-closure/index.vue，~line 263
function hourToTime(h: number): string {
  return `${String(h).padStart(2, '0')}:00:00`; // ← BUG：应为 :00，不是 :00:00
}
```

后端 BO：`@JsonFormat(pattern = "HH:mm") private LocalTime timeStart;`

修复方式（1行）：
```typescript
return `${String(h).padStart(2, '0')}:00`; // HH:mm
```

---

**TEST 2 — 价格区间一键填充（/gz-bean/seat-type-config）**

```
PASS: 导航 /gz-bean/seat-type-config → 列表渲染 3 行
PASS: 点行内「星期×时段价格」→ 弹层打开（标题：星期 × 时段价格 · 单人），含「区间批量填充」控件
PASS: 设置填充参数：起 10:00 / 止 14:00 / 价格 0.5
PASS: 点「填充」→ 网格 22/85 个 cell 变为 0.5（时段 10:00/11:00/12:00/13:00，共 4 格 × 多星期）
      13:00 格含在结果中（[10:00, 14:00) 半开区间，4格）
PASS: 点「确定」保存 → toast: "星期×时段价格已保存"
PASS: 重新打开弹层验持久化 → 0.5 仍在网格（落库确认），sample: [15,0.5,0.5,0.5,0.5,...]
PASS: 清理 → 将 10:00-14:00 价格重置为 0 并保存（无测试污染残留）
PASS: TEST 2 期间无 JS 控制台报错
```

---

### console 报错

- TEST 1：`[gz-bean-seat-closure] add failed error` —— 来自后端 400 响应，即上述 hourToTime bug
- TEST 2：无报错

---

### 截图

位于 `/tmp/pw-gacha/screenshots/`：
- `bean036-dv-T1-01-list.png` — 座位关闭规则列表页（筛选区 + 新建关闭按钮）
- `bean036-dv-T1-02-dialog.png` — 新建对话框打开
- `bean036-dv-T1-03-dialog-reactive-set.png` — Vue 注入后 UI 回显（A1 tag + 周二 + 10:00/12:00 正确显示）
- `bean036-dv-T1-04-after-save.png` — 提交后 API 400
- `bean036-dv-T2-01-list.png` — 座位类型配置列表
- `bean036-dv-T2-02-price-dialog.png` — 星期×时段价格弹层
- `bean036-dv-T2-05-after-fill.png` — 填充后网格（22 cells = 0.5）
- `bean036-dv-T2-07-persist.png` — 重新打开后持久化验证（0.5 仍在）
- `bean036-dv-T2-08-cleanup.png` — 清理后截图

---

### 跳过 / 未跑

- 真机微信原生能力（支付/getPhoneNumber/客服/扫码/登录头像昵称授权）→ Tier 2 节点触发人验
- mp 端可达性 → 本 ticket 为 admin 纯功能，无 mp 页面

---

### 结论

- **TEST 2（价格区间填充）**: Tier 1B ✅ 通过（填充 → 保存 → 持久化 → 清理全链路）
- **TEST 1（座位关闭规则 CRUD）**: Tier 1B ❌ 失败 1 处

**失败清单 → 需 kevin-coder 闭环修**：

| # | 位置 | bug | 修法 |
|---|---|---|---|
| 1 | `plus-ui/src/views/gz-bean/seat-closure/index.vue` ~line 263 `hourToTime()` | 生成 `"HH:00:00"`，后端 `@JsonFormat(pattern = "HH:mm")` 只接受 `"HH:mm"` → 提交时 400 | 改为 `return \`${String(h).padStart(2, '0')}:00\`` |

修复 + 重测范围：仅修 `hourToTime`；复测步骤：新建关闭规则（A1/周二/10:00-12:00）→ 断言 200 + 列表出现 → 删除。
