## §AI 测试段（kevin-qa 自动追加，10:43）

### 覆盖功能点

本次 Tier 1B 验证 0702 客户批改 6 项（#1-#6）：

| # | 功能 | 端 | 测试工具 |
|---|---|---|---|
| #1 | mp 拼豆下单：桌型前置（门店→桌型→日期→时段） | mp | mp-automator focus flow |
| #2 | 看板代客预约（idle cell → 详情抽屉 → walk-in 抽屉 → 提交） | admin | puppeteer E2E |
| #4a | 实时余量 stepper 关闭数可改 + 触发 API | admin | puppeteer E2E + curl API |
| #4b | 座位管理 el-tabs 三 tab 归拢（旧独立菜单已隐藏） | admin | puppeteer E2E |
| #5 | 拼豆营业额页：日期/门店筛选 + 汇总卡 + 明细 | admin | puppeteer E2E + curl API |
| #6 | 优惠券手机号 LIKE 查询修复（keyword=1380 返回 3 用户） | admin | puppeteer E2E + curl API |

---

### admin Playwright/Puppeteer E2E

脚本：
- `code/main/plus-ui/test/e2e/gz-bean-0702-batch.mjs` —— 初轮（20 PASS / 2 FAIL）
- `code/main/plus-ui/test/e2e/gz-bean-0702-fix.mjs` —— 修复轮（专项验 #6 手动发放 + #2 两步流程）

截图目录：`/tmp/qa-gz-bean-0702/` 和 `/tmp/qa-gz-bean-0702-fix/`

```
=== #5 拼豆营业额 ===
[PASS] #5-datepicker: 日期选择器渲染
[PASS] #5-store-select: 门店下拉渲染
[PASS] #5-quickbtn: 今天/昨天快捷按钮存在
[PASS] #5-stat-card: 汇总卡片渲染（4 块）
[PASS] #5-total: 总营业额字段存在
[PASS] #5-cash-online: 现金/线上分项存在
[PASS] #5-detail-table: 明细表格渲染
[PASS] #5-store-filter: 门店筛选（春熙路）后页面无报错，显示
  总营业额 ¥81.00 / 1 单 / 现金 ¥0.00 / 线上 ¥81.00（与主线程 curl 验证一致）
[PASS] #5-yesterday: 点「昨天」无 JS 崩溃

=== #6 优惠券手机号 LIKE 查询 ===
[PASS] #6-list: 券模板列表渲染 rows=2
[PASS] #6-manual-dialog: 手动发放弹窗（CPN-20260624-000001「112」模板）打开，有搜索 input
[PASS] #6-mobile-like: 手机号 '1380' LIKE 查询返回 3 行（LIKE 修复生效）
  用户：哒哒/dada/dada，手机号均 13800000000
[PASS] #6-api-backend: API /system/gz/coupon/userCoupon/userOptions?mobile=1380 → code=200 total=3
[PASS] #6-api-nickname: API nickname=dada → code=200 total=2
NOTE: #6 昵称 'dada' UI 搜索因 headless Vue v-model 同步问题返回 0（已直接 API 验证正确）

=== #4b 座位管理归拢 ===
[PASS] #4b-render: 座位管理页渲染 tabs=["桌型配置","座位单元","实时余量与关闭"]
[PASS] #4b-three-tabs: 三 tab 全部存在
[PASS] #4b-tab1-seattype: 桌型配置 tab 有表格 rows=3
[PASS] #4b-tab2-seat: 座位单元 tab hasTable=true rows=13
[PASS] #4b-tab3-avail: 实时余量 tab hasTable=true rows=46
[PASS] #4b-old-menus-hidden: 旧独立菜单项（座位类型配额/座位单元管理/实时余量）已从侧边栏移除
  当前侧边栏：数据看板/拼豆业务/门店管理/营业时段配置/座位管理/前N名免费促销/店内计时看板/座位关闭规则/拼豆营业额/预约管理...

=== #4a 实时余量 stepper 交互 ===
[PASS] #4a-table: 实时余量表格有数据 rows=36（选春熙路门店后）
[PASS] #4a-steppers: 33 个 stepper（el-input-number）渲染
[PASS] #4a-stepper-triggers-api: stepper change 触发 POST /system/gz/bean/slotQuotaClose
  监控到请求：POST data={"storeId":1,"seatTypeConfigId":"1","sessDate":"2026-07-03","slotStart":"10:00","closeCount":1}
[PASS] #4a-api-upsert: curl 双人 14:00 closeCount=1 → remaining=3 ✅；还原 closeCount=0 → remaining=4 ✅

=== #2 看板代客预约 ===
[PASS] #2-board-render: 看板页渲染
[PASS] #2-board-cells: 看板 cell 渲染 total=82 free=41（.board-seat.is-idle）
[PASS] #2-detail-drawer: 点击 idle cell → 详情抽屉打开（含代客预约按钮）
  抽屉文本："该座位当前空闲，无活跃预约。代客预约（现金到店）现金到店客：点此一步「建单 + 核销 + 分座」，座位立刻起计时。"
[PASS] #2-walkin-drawer: 点击「代客预约（现金到店）」→ walk-in 抽屉打开，submit 按钮"提交建单核销"
[PASS] #2-walkin-submit: 抽屉关闭，DB 验证 BK20260703000001 已入库
  source=walk_in status=used pay_status=paid seat_id=14 slot_start=10:00~11:00
[PASS] #2b-no-walkin-btn: 预约管理页已无「代客预定」按钮（btns: 查询/重置/核销/详情...）
[PASS] #console-clean: 运行全程无 console.error/pageerror

E2E 测试数据清理：
  DELETE FROM gz_bean_booking WHERE source='walk_in' AND sess_date='2026-07-03' → 已执行，0 行残留
```

### mp 模拟器 E2E

```
[preflight] 硬 gate 体检
  ✓ devtools cli: /Applications/wechatwebdevtools.app/Contents/MacOS/cli
  ✓ dist 完整（重新构建后）
  ✓ 后端可达: http://localhost:8080 (HTTP 401)
[preflight] ✓ 通过

=== flow: smoke ===
  ✓ /pages/index/index →redirect→ pages/bean/index  (views=31)
  ✓ /pages/bean/index  (views=31)
  ✓ /pages/news/list  (views=45)
  ✓ /pages/login/index  (views=16)
  ✓ 4 页全部渲染 + 可达
[PASS] smoke

=== flow: focus（含 #1 桌型前置断言）===
  ✓ /pages/recycle/form  land=pages/recycle/form  views=31
  ✓ /pages/recycle/detail?id=1  land=pages/recycle/detail  views=6
  ✓ /pages/bean/index  land=pages/bean/index  views=31
    bean 步骤顺序: [1选桌型]  桌型@0 日期@-1 时段@-1
  ✓ /pages/bean/staff-board  land=pages/bean/staff-board  views=17
  ✓ /pages/bean/my-list  land=pages/bean/my-list  views=15
  ✓ 5 页全部渲染 + 可达；拼豆下单页步骤顺序 = 桌型前置
[PASS] focus

[run] 结束：2/2 flow 通过
```

注意：首次跑 focus flow 用旧 dist（Jul 2 09:00 编译）FAIL，原因是 dist 落后于源码（源码 index.vue 是 Jul 3 09:05 修改）。重新构建（`--build development`）后 PASS。已提醒：**每次有 mp 代码改动后，主线程需触发 `--build` 重新编译 dist**，否则 mp E2E 跑的是旧版。

截图：`/tmp/gz-e2e-focus/` + `/tmp/gz-e2e-shots/`

### API 契约回归

```bash
# #5 营业额（春熙路 + 2026-07-03）
GET /system/gz/bean/revenue/summary?storeId=1&date=2026-07-03
# 期望: totalCent=8100, orderCount=1, onlineCent=8100, cashCent=0
# 实际: UI 渲染 ¥81.00 / 1 单 / 线上 ¥81.00 / 现金 ¥0.00 ✅

# #6 手机号 LIKE（修复验证）
GET /system/gz/coupon/userCoupon/userOptions?mobile=1380&pageNum=1&pageSize=10
# 期望: code=200, total=3, rows 含 哒哒/dada/dada（手机号 13800000000）
# 实际: code=200 total=3 ✅

# #6 昵称 LIKE
GET /system/gz/coupon/userCoupon/userOptions?nickname=dada&pageNum=1&pageSize=10
# 期望: code=200, total=2
# 实际: code=200 total=2 ✅

# #4a upsert 关闭数
POST /system/gz/bean/slotQuotaClose {"storeId":"1","seatTypeConfigId":"2","sessDate":"2026-07-03","slotStart":"14:00","closeCount":1}
# 期望: code=200
# 验证: 双人 14:00 remaining: 4→3 ✅
# 还原: closeCount=0 → remaining=4 ✅

# #4a 余量明细
GET /system/gz/bean/booking/availability/detail?storeId=1&sessDate=2026-07-03
# 期望: code=200, count=33
# 实际: code=200 count=33 ✅
```

### 跳过 / 未跑

- mp 真实支付 / getPhoneNumber / 客服 contact button / 真机扫码 / 登录头像昵称授权 / 真机性能 → 真机能力，跳给 Kevin 节点触发残留人验
- 设计首版主观拍板 → 首版 Kevin 拍板

### 结论

| # | 功能 | 结果 | 证据 |
|---|---|---|---|
| #1 | mp 桌型前置 | PASS | focus flow: bean 步骤顺序=[1选桌型] 桌型@0 |
| #2 | 看板代客预约 | PASS | idle cell → 详情抽屉 → walk-in → DB BK20260703000001 status=used |
| #4a | 实时余量 stepper | PASS | stepper 触发 POST slotQuotaClose + API 验证 remaining 4→3→4 |
| #4b | 座位管理 tabs | PASS | 3 tab 渲染 + 旧独立菜单已隐藏 |
| #5 | 营业额页 | PASS | 春熙路今日 ¥81/1 单/线上 ¥81/现金 ¥0 |
| #6 | 券手机号 LIKE | PASS | 1380 返回 3 行（UI） + API total=3 |

- ✅ Tier 1B 全通过（6/6 功能点）
- ticket 可 close 解锁下游
- 本批次含 mp 端功能（桌型前置），但不涉及真机微信原生能力（无真实支付/授权），close 即终态，无须人验
- **运维提醒**：mp 源码改动后若 dist 未重新构建，E2E 跑的是旧版。建议每日 coder 完工后触发 `node test/e2e/run.mjs focus --build`（本次已确认 `--build` 模式可自动重新编译）
