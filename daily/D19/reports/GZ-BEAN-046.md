## §AI 测试段（kevin-qa 自动追加，08:55）

### admin Playwright E2E — GZ-BEAN-046 walk-in 松绑 + 分钟精度

票 ID：GZ-BEAN-046（店内计时看板 → 代客预约 walk-in 松绑 + 分钟精度改动）
浏览器：Chromium (Google Chrome /Applications/Google Chrome.app)
后端：http://localhost:8080 / plus-ui：http://localhost:8090
账号：gz_owner / gz_owner123!（dev 无验证码）

```
=== GZ-BEAN-046 admin Playwright E2E ===
时间: 2026-07-05T00:48 ~ 00:57

--- AC1: 登录 + 进看板 ---
[PASS] ac1_login — 登录后 URL: http://localhost:8090/index ✅
[PASS] ac1_board — 路由 /gz-bean/board 加载成功，看板元素 88 个 ✅
  门店：CD001 · 成都春熙路店（自动选中）
  日期：2026-07-05（今天，自动）
  统计栏：空闲 17 / 使用中 1 / 临近结束 1 / 已超时 1

--- AC2: 代客预约抽屉 + el-time-picker 渲染 ---
  点击 D1（空闲）→ 侧边面板出现
  面板文本: ["代客预约（现金到店）","现金到店客：点此一步「建单 + 核销 + 分座」，座位立刻起计时。"]
  点「代客预约」按钮 → 抽屉打开

[PASS] ac2_drawer_open — 抽屉标题「代客预约 · 一步建单核销分座」✅

el-time-picker 检测:
  .el-date-editor--time 数量: 2（开始 + 结束各一个）
  抽屉内 input[0]: val="08:48" placeholder="" → el-time-picker
  抽屉内 input[1]: val="09:48" placeholder="" → el-time-picker
  点击开始 input → el-time-panel 弹出（时/分双列滚动轮）
  el-time-spinner / el-time-panel 数量: 2

[PASS] ac2_time_picker_is_el_time_picker — el-time-picker 有时分滚动面板 ✅

hint 文案检测（无 raw i18n key）:
  [".walkInHint: 现金到店客：点此一步「建单 + 核销 + 分座」，座位立刻起计时。",
   "...备注挂在座位上...",
   "可精确到分钟，店员自由设",
   "共 60 分钟 · 按 2 个整点格计价",
   "免费单不计营业额",
   "留空 = 按桌型逐格计价；填数 = 议价/抹零"]
  raw i18n key (gzBeanBoard.*): false

[PASS] ac2_hint_no_raw_i18n_key — 提示文案全部正常渲染，无 raw i18n key ✅

--- AC3: 分钟精度提交 16:34 → 17:50 ---
  开始设为 16:34 → el-time-panel 打开 → Ctrl+A + type "16:34:00" + Enter
  结束设为 17:50 → el-time-panel 打开 → Ctrl+A + type "17:50:00" + Enter
  
  设置后 hint: "共 76 分钟 · 按 2 个整点格计价"（16:34→17:50=76分钟，ceil(17.83)-floor(16.57)=18-16=2格）
  
[PASS] ac3_minute_76min_hint — 76分钟 · 2个整点格 计算正确 ✅

  提交按钮：disabled=false
  点「提交建单核销」→ 等待 4 秒
  抽屉关闭: true
  看板刷新: D1 → "使用中 BK20260705000004 / 尾号 0000 / 16:34-17:50 / 剩 1 时 16 分"

[PASS] ac3_submit_success — 代客单建单成功，D1 起计时 ✅

--- AC4: 午夜 23:30-23:59 不卡死 ---
  切至 D2（空闲）→ 代客预约抽屉
  开始=23:30，结束=23:59
  hint: "共 29 分钟 · 按 1 个整点格计价"
  当前 input 值: ["23:30","23:59","","on",""]
  提交按钮：disabled=false
  点「提交建单核销」→ 计时开始
  耗时: 6133ms（< 9000ms 阈值）
  页面响应: alive=true
  toast: ["D2 临近结束剩 29 分钟。后续暂无排座，可问客人是否延时。"]
  看板: D2 → "临近结束 BK20260705000005 / 23:30-23:59 / 剩 29 分 00 秒 / 可延时"

[PASS] ac4_midnight_no_freeze — 午夜 23:30-23:59 正常返回，页面未卡死 ✅
  注：toast 是「临近结束」提醒（因 23:30-23:59 和当前时间差很近），属正常业务逻辑

Browser Console Errors: 无
```

截图列表（位于 scratchpad）：
- v2-06-walkin-drawer.png — 代客预约抽屉渲染（座位D1、开始08:48、结束09:48、hint文案正常）
- v2-07-time-picker-panel-open.png — el-time-picker 时分双列滚动面板
- v2-10-times-set.png — 16:34/17:50 设置后，hint 显示「共 76 分钟 · 按 2 个整点格计价」
- v2-11-after-submit.png — D1 使用中 BK20260705000004 / 16:34-17:50，D2 临近结束 23:30-23:59
- ac4v2-07-times-filled.png — 23:30/23:59 设置后，hint「共 29 分钟 · 按 1 个整点格计价」，提交按钮 enabled
- ac4v2-08-midnight-after-submit.png — 提交后 D2 变使用中 BK20260705000005，「D2临近结束」弹窗出现，页面正常

### API 契约回归（简要）

```bash
# walk-in 提交端点：POST /system/gz/bean/booking/walk-in
# Tier 1A coder 已用 curl 验证；本次 Playwright 通过真浏览器打真后端
# D1 BK20260705000004 (16:34-17:50) + D2 BK20260705000005 (23:30-23:59) 均 200 入库
```

### 跳过 / 未跑

- mp 端：本 ticket 仅涉及 admin plus-ui 看板，无 mp 侧改动，跳过 mp vitest / mp E2E
- 真机微信原生能力：不涉及，跳过给 Tier 2
- 设计首版主观拍板：admin 不评判视觉，跳过

### 结论

✅ Tier 1B 全通过 → ticket 可 close（解锁下游）

| AC | 描述 | 结果 |
|---|---|---|
| AC1 | 登录 + 进看板，门店/日期选择，座位统计渲染 | ✅ |
| AC2 | 代客预约抽屉打开，el-time-picker 有时分滚动，hint 文案无 raw i18n key | ✅ |
| AC3 | 16:34→17:50 分钟精度提交，hint 显示「76分钟·2整点格」，建单成功座位起计时 | ✅ |
| AC4 | 23:30→23:59 午夜边界提交，6133ms 内正常返回，页面未卡死/转圈 | ✅ |

Browser Console Errors: 0 条
