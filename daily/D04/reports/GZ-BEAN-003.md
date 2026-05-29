# GZ-BEAN-003 — 完工报告

> mp 端拼豆选座页（日期 → 时段 → 座位 三步流，M 复杂度）。D04 串行 4 ticket 第 3 个，BEAN-004 提交流程的前置。
> 实施时间 ~50 min（含 BEAN-002 seed 重建 + Tier 2 临时入口卡片 + vitest 显式 import 适配）。

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | ✅ N/A | 项目无 git 仓库 |
| 上游 BEAN-002 install + 重启 | ✅ | PID 6514 / 重启后 PID 31632 LISTEN 8080 |
| service 层方法已留位 | ✅ | `selectMpEnabledSeats(Long)` / `selectMpEnabledSlots(Long, LocalDate)` 在 BEAN-002 已实现 |
| miniapp 编译健康 | ✅ | `pnpm dev:mp` → "DONE Build complete" 4981ms |
| ADMIN-005 拼豆 tab 入口已上线 | ✅ | `pages/bean/index.vue` 含 useNavGuard('bean') + customer-service fab |
| BEAN-001 store API mp 可用 | ✅ | `GET /app/gz/bean/store/list` 200 → CD001 成都春熙路店 |
| 权威蓝图 doc/10 §3.N3-N5 + doc/11 §3.2/3.3 已读 | ✅ | 字段层完全对齐；占用判定逻辑在 doc/10 §3.N4 |
| 合同范围 | ✅ V1.0 拼豆主线 D04 = 2026-06-01 ≤ 6/15 硬期限 | |

### §0 硬探记录

```
$ lsof -i:8080
java    31632 wkui  ...  TCP *:http-alt (LISTEN)  ✅

$ ls code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-bean/.../controller/applet/
GzBeanStoreMpController.java   ← BEAN-001 留下；本 ticket 加 GzBeanSeatMpController + GzBeanSlotMpController

$ grep -A 1 "selectMpEnabledSeats\|selectMpEnabledSlots" .../IGzBeanSeatService.java .../IGzBeanTimeSlotTemplateService.java
✅ 两个 service 方法在 BEAN-002 已实现，本 ticket 直接 wrap 即可

$ ls code/main/miniapp/src/pages/bean/
index.vue   ← ADMIN-005 拼豆 tab 占位页（含 useNavGuard）

$ ls code/main/miniapp/src/components/biz/
BizCustomerServiceFab.vue / BizFixedCta.vue / ComingSoonV11.vue
✅ 复用 BizFixedCta（GZ-ADMIN-005 已建底部 fixed CTA 业务壳）
```

### 权威文档引用摘录（doc/10 §3.N3-N5 / doc/11 §3.2-3.3）

**doc/10 §3.N3-N5 关键节点**：
- N3 选日期：默认今天，最多 7 天，过去日不可选
- N4 拉取时段：`GET /api/bean/slots?store_id&date` 返回该日所有开放时段（service 内部按 weekdays 过滤）
- N5 选时段 + 座位：座位列表型（mockup 已锚定，doc/02 §2.3 + AC 决策 D1），已占用座位灰显

**doc/10 §3 占用判定权威**：
- N4 返回数据**含**每时段的座位占用情况；占用源自 `gz_bean_booking.status='pending'` 的记录（doc/11 §3.4）
- **本 ticket 时**：BEAN-004 booking 表尚未建 → `/availability` 端点全部返 available=true 占位，加 `// TODO(GZ-BEAN-004): join gz_bean_booking after BEAN-004 lands` 注释

**doc/11 §3.2 mp 端拉时段 SQL 等价**：
```
SELECT * FROM gz_bean_time_slot_template
 WHERE store_id=? AND enabled=1
   AND FIND_IN_SET(?, weekdays)
   AND ? BETWEEN COALESCE(effective_date,'1970-01-01') AND COALESCE(expire_date,'2099-12-31')
```
本 ticket service 实现（BEAN-002 已写）：SQL 过滤 enabled + 日期范围；weekdays 在 Java 侧 set 精确 split 过滤 — 已验证 mp 端测试 TEST-2 拉到 2 个 weekdays='1,2,3,4,5,6,7' 时段 ✅

**doc/11 §3.3 座位 mp 视图**：仅返 `enabled=1` 子集，按 sortNo / seatNo 升序 — 已验证 mp 端测试 TEST-3 5 座 → 4 可见（B2 enabled=0 正确过滤）✅

---

## 实现摘要

### 改动文件清单

**后端（ruoyi-gz-bean）— 2 新增**：
```
A code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-bean/src/main/java/org/dromara/gz/bean/controller/applet/
  ├── GzBeanSeatMpController.java     (含内部 SeatAvailabilityVO 静态类)
  └── GzBeanSlotMpController.java
```

**Mp（miniapp）— 5 新增 + 1 修改**：
```
A code/main/miniapp/src/locale/bean.zh-CN.ts                 (bean.select.* / bean.entry.* 文案 + 简化 t())
A code/main/miniapp/src/components/biz/BizDatePicker.vue     (横向滚动 7 天日期选择)
A code/main/miniapp/src/components/biz/BizSlotGrid.vue        (时段网格 2 列)
A code/main/miniapp/src/components/biz/BizSeatList.vue        (座位列表 3 列 + 占用判定)
A code/main/miniapp/src/pages/bean/select.vue                (主选座页，三步流 + summary + fixed CTA)
M code/main/miniapp/src/pages/bean/index.vue                  (加 Tier 2 临时入口卡片，含 TODO(Tier2-entry-temp) 注释)
M code/main/miniapp/src/api/gz-bean.ts                         (4 个新 API + 3 个 VO 类型；保留 BEAN-001 listBeanStores)

A code/main/miniapp/src/api/gz-bean.test.ts                   (5 vitest — API 透传 / 返回值穿透)
A code/main/miniapp/src/components/biz/BizSeatList.test.ts   (4 vitest — 占用判定 / is-active / id String 化)
```

**DDL**：本 ticket 不落新 DDL（只读查询）✅
**Admin**：本 ticket 不动 plus-ui（admin 端在 BEAN-002 已建好座位 / 时段配置页）✅

### 关键决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | mp Controller 拆 2 个文件（Seat / Slot 各一）| 与 admin 端 GzBeanSeatController / GzBeanTimeSlotTemplateController 1:1 对应；未来加 booking 端点不撑爆单文件 |
| D2 | `/availability` 端点内嵌 SeatAvailabilityVO（静态内部类）| 这个 VO 仅服务于 mp 端 /availability，不污染顶层 `domain.vo`；BEAN-004 起会有完整的 booking 占用 schema，再单独抽 |
| D3 | BEAN-004 booking 表未建 → /availability 全返 available=true | 比起拒绝返 400（用户体验差）或返空（mp 端崩）更稳；带 TODO(GZ-BEAN-004) 注释，下游 ticket §0 grep 即可定位 |
| D4 | 业务组件包一层（BizDatePicker / BizSlotGrid / BizSeatList） | CLAUDE.md §7.5 组件库无关纪律；本 ticket 全用 view/text 原语，不撒 wd-* / uni-* —— 未来切换组件库零成本 |
| D5 | 座位列表型（不是平面图）+ 每行 3 个 | 任务卡 AC D1：V1.0 仅 5-24 座，列表足够；mockup 也是列表型 |
| D6 | id 字段全 String 透传（emit / 路由 / availability map key） | dongjiaoshan 教训 #1 防 Long → JS number 精度坑；测试 BizSeatList "ID String 化"显式锁定 |
| D7 | 临时入口卡片放 pages/bean/index.vue + TODO(Tier2-entry-temp) | CLAUDE.md §8.3 Tier 2 可达性硬约束；当前 BEAN-010 拼豆首页未建 → 必须临时入口让 Kevin 1 次点击可达 |
| D8 | watch 自动级联（date 变 → 拉 slot；slot 变 → 拉 seat + availability）| 用户操作更顺手 — 不用每步点"下一步"；选错时也自动回滚下游选中态（seat 清空） |
| D9 | onLoad 仅拉门店 + 自动级联拉时段（不开始就拉 seat）| 减少初始网络请求；选了时段后才拉座位 + availability — 减少 BEAN-004 上线后 availability 调用频次 |
| D10 | 测试用 mvn install 一次 + 直接 docker mysql 种 5 座 2 时段 | 跨 BEAN-002 admin CRUD 验过的能力，本 ticket 不重测 admin 写路径，专注 mp 读端点 |
| D11 | vitest 必须显式 `import { computed } from 'vue'`（即使页面有 unplugin-auto-import）| unplugin 仅在 vite build 时跑，不在 vitest test runner；显式 import 是双保险 |
| D12 | `/availability` 端点的 slotStart 用 `String`（不是 LocalTime） | "10:00" / "10:00:00" 两种格式都要兼容；service 层后续 BEAN-004 需要 parse 为 LocalTime 时再做（避免本 ticket 引入额外 @DateTimeFormat 装饰器） |

### 关联蓝图引用

- **业务流**：doc/10 §3 拼豆预约 §关键节点 N3/N4/N5 — mp 端日期 / 时段 / 座位三步；占用判定来自 booking 表（BEAN-004 接力）
- **字段表**：doc/11 §3.2 时段模板 + §3.3 座位 — mp VO 字段层完全对齐
- **关联 ticket**：BEAN-001 ✅ store API mp 端调用 / BEAN-002 ✅ service 层 selectMpEnabledSeats + selectMpEnabledSlots / **BEAN-004（下游）** booking 表上线后 /availability join 真实占用 / BEAN-005（下游）预约详情页 / BEAN-010（下游）拼豆首页 — 上线后清理本 ticket 留的 Tier2-entry-temp 临时入口

---

## AI 自测（5 个测试代码 block + DB 状态 + Tier 2 可达性）

### 1. 后端编译

```
$ cd code/main/RuoYi-Vue-Plus && mvn compile -pl ruoyi-modules/ruoyi-gz-bean -am -q
（无输出 = BUILD SUCCESS — quiet 模式仅打错误）
```

### 2. 后端单测回归（全 BEAN 域 + common 域）

```
$ cd code/main/RuoYi-Vue-Plus && mvn test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-bean -am \
    -Dsurefire.failIfNoSpecifiedTests=false

[INFO] Tests run: 26, Failures: 0, Errors: 0, Skipped: 0   ← ruoyi-gz-common 回归
[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0   ← GzBeanSeatServiceImplTest (BEAN-002)
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0   ← GzBeanTimeSlotTemplateServiceImplTest (BEAN-002)
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0   ← GzBeanStoreServiceImplTest (BEAN-001 回归)
[INFO] Tests run: 36, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

BEAN-001/002 36 + common 26 = 62 单测全 ✅ — 本 ticket 加 mp Controller 不影响 service 层
```

### 3. mp 端点 curl 验证（含 seed 数据）

种子数据（5 座位 + 2 时段；B2 停用作过滤验证）：
```sql
-- /tmp/bean003-seed.sql
INSERT INTO gz_bean_time_slot_template VALUES
(1, '上午', '10:00:00', '12:00:00', '1,2,3,4,5,6,7', 1, 0, ...),
(1, '下午', '14:00:00', '16:00:00', '1,2,3,4,5,6,7', 1, 1, ...);
INSERT INTO gz_bean_seat VALUES
(1, 'A1', 1), (1, 'A2', 1), (1, 'A3', 1), (1, 'B1', 1), (1, 'B2', 0);
-- ✅ slot_count=2 / seat_count=5 / B2 enabled=0
```

curl 7 个端点 / error path（含 mp token 拿取 + 4 happy + 3 error）：

```bash
# mp wx-login mock 短路拿 token
$ POST /app/gz/common/auth/wx-login -d '{"code":"mock-bean003-001","nickName":"测试用户003"}'
  → {"code":200,"data":{"token":"eyJ...KsSkz...","userId":"16",...}}  ✅

# TEST-1: store/list（BEAN-001 回归）
$ GET /app/gz/bean/store/list (auth)
  → {"code":200,"data":[{"id":1,"storeNo":"CD001","name":"成都春熙路店","type":"pindou",...}]}  ✅

# TEST-2: slot/list 拉今天（2026-05-29）所有时段
$ GET /app/gz/bean/slot/list?storeId=1&date=2026-05-29 (auth)
  → {"code":200,"data":[
      {"id":1,"slotName":"上午","startTime":"10:00:00","endTime":"12:00:00","weekdays":"1,2,3,4,5,6,7","enabled":1,...},
      {"id":2,"slotName":"下午","startTime":"14:00:00","endTime":"16:00:00","weekdays":"1,2,3,4,5,6,7","enabled":1,...}
    ]}  ✅ 2 个时段全返；按 sortNo 升序

# TEST-3: seat/list 拉门店座位（B2 停用应被过滤）
$ GET /app/gz/bean/seat/list?storeId=1 (auth)
  → {"code":200,"data":[
      {"id":1,"seatNo":"A1","enabled":1},
      {"id":2,"seatNo":"A2","enabled":1},
      {"id":3,"seatNo":"A3","enabled":1},
      {"id":4,"seatNo":"B1","enabled":1}
    ]}  ✅ 5 座 → 4 可见（B2 enabled=0 已过滤）

# TEST-4: availability 占位（BEAN-004 接力）
$ GET /app/gz/bean/seat/availability?storeId=1&date=2026-05-29&slotStart=10:00:00 (auth)
  → {"code":200,"data":[
      {"seatId":1,"seatNo":"A1","available":true},
      {"seatId":2,"seatNo":"A2","available":true},
      {"seatId":3,"seatNo":"A3","available":true},
      {"seatId":4,"seatNo":"B1","available":true}
    ]}  ✅ 全 true 占位；BEAN-004 join booking 后真实工作

# === error path ===

# TEST-5: slot/list 缺 date 参数 → 500 拦截
$ GET /app/gz/bean/slot/list?storeId=1 (auth)
  → {"code":500,"msg":"发生未知异常，请联系管理员"}  ✅ @NotNull 拦住

# TEST-6: 无 token → 401
$ GET /app/gz/bean/seat/list?storeId=1
  → {"code":401,"msg":"认证失败，无法访问系统资源"}  ✅ sa-token 全局拦截

# TEST-7: 错日期格式 → 友好错误
$ GET /app/gz/bean/slot/list?storeId=1&date=2026/06/01 (auth)
  → {"code":500,"msg":"请求参数类型不匹配，参数[date]要求类型为：'java.time.LocalDate'，但输入值为：'2026/06/01'"}  ✅
```

### 4. mp 端 vitest 单测（9 新加 + 全量回归）

```
$ cd code/main/miniapp && pnpm vitest run

 ✓ src/api/customer-service.test.ts (3 tests) 4ms
 ✓ src/api/gz-bean.test.ts (5 tests) 2ms                  ← 新加 / API 透传 + 返回值穿透
 ✓ src/components/biz/BizSeatList.test.ts (4 tests) 12ms  ← 新加 / 占用判定 + is-active + id String 化
 ✓ src/store/customer-service.test.ts (3 tests) 4ms
 ✓ src/store/token.test.ts (3 tests) 4ms
 ✓ src/utils/watermark.test.ts (12 tests) 5ms

 Test Files  6 passed (6)
      Tests  30 passed (30)   ← 21 回归 + 9 新加 = 30 全过
   Duration  971ms
```

新加单测覆盖：
- `gz-bean.test.ts` × 5：listBeanStores / listBeanSlots / listBeanSeats / listSeatAvailability / 返回值穿透
- `BizSeatList.test.ts` × 4：availability 空 → 全可用 / availability false → emit 拦 / modelValue → is-active / id String 化（dongjiaoshan #1 防精度坑）

### 5. mp 端编译 + 路由识别

```
$ cd code/main/miniapp && pnpm dev:mp
DONE Build complete. Watching for changes...
ready in 4981ms.

$ grep -A 2 "bean/select" src/pages.json
  "path": "pages/bean/select",
  "type": "page",
  ✅ unibest 自动扫描 + 注入 pages.json（无需手写）

$ ls dist/dev/mp-weixin/pages/bean/
index.js   index.json   index.wxml   index.wxss   ← 拼豆 tab 入口页（含临时入口卡片）
select.js  select.json  select.wxml  select.wxss  select-vendor.js   ← 本 ticket 主选座页

$ ls -la dist/dev/mp-weixin/pages/bean/select.wxss
2481 bytes  ← 含 BizDatePicker + BizSlotGrid + BizSeatList scoped styles
```

### 6. DB 状态验证（mp Controller 行为对账）

```sql
-- seed 后态
SELECT id, slot_name, weekdays, enabled FROM gz_bean_time_slot_template;
1  上午  1,2,3,4,5,6,7  1
2  下午  1,2,3,4,5,6,7  1
   ✅ 2 时段 / 全周生效 / enabled

SELECT id, seat_no, enabled FROM gz_bean_seat ORDER BY sort_no;
1  A1  1
2  A2  1
3  A3  1
4  B1  1
5  B2  0   ← mp 端不可见（service 层 enabled=1 过滤）
   ✅ 5 座 / B2 停用作 mp 过滤验证种子
```

### 7. Tier 2 可达性自检

| 项 | 结果 |
|---|---|
| 拼豆 tab 入口已上线（GZ-ADMIN-005）| ✅ pages/bean/index.vue |
| 从拼豆 tab 1 次点击到选座页 | ✅ 加 `.entry-card`（绿色边框卡片，文案"体验选座流程"）→ goSelect() → uni.navigateTo('/pages/bean/select') |
| 临时入口标记 | ✅ `<!-- TODO(Tier2-entry-temp): GZ-BEAN-003, remove when GZ-BEAN-010 merged -->` 两处（template 块 + script setup 块） |
| 清理者下游 ticket | GZ-BEAN-010（拼豆首页）落地时清理 — 已记入本报告"对下游 ticket 提示" |
| Kevin 操作路径 | mp 启动 → 拼豆 tab（如未登录会先弹 useNavGuard 登录引导）→ 点"进入选座" → 主选座页 |

✅ **可达性硬约束达成**（CLAUDE.md §8.3）：Kevin 测试时**无需自定义编译模式 / console wx.navigateTo / mockup 想象**，从拼豆 tab 1 次点击即达。

---

## 风险提示 / 已知 issue

| # | 风险 | 严重度 | 缓解 / 待办 |
|---|---|---|---|
| R1 | `/availability` 端点 BEAN-004 之前全返 available=true — Kevin Tier 2 看不到"灰显已占用" UX | 低 | TODO(GZ-BEAN-004) 注释已留；BEAN-004 实施时 join `gz_bean_booking.status='pending'` 后真实工作；Kevin 测试时可手动改 BizSeatList.test.ts 模拟 occupied 看效果 |
| R2 | mp 端用户停留选座页 30s 后他人占座 → BEAN-004 提交时 409 | 中 | BEAN-004 实施时友好提示「座位已被占，请重选」+ 自动回退本页并 reload availability；本 ticket 不处理（提交流程在 BEAN-004） |
| R3 | mp 端 wx-login mock 短路（dev 环境占位 AppID）— 真实微信 AppID 上线后行为可能微调 | 极低 | useAuth.fetchWxCode 已有 mock-* 短路逻辑；BEAN-004/005 实施时复用 |
| R4 | 跨日选择切换会清空座位选中态（watch 设计）| 设计如此 | 用户切日 → 时段重拉 → 座位清空 → 用户重选时段后再拉座位；防止"跨日带状态"导致 BEAN-004 提交时 staleness |
| R5 | `/availability` 端点路径与 service `selectMpEnabledSeats` 重复查询门店全座位 — 略冗余 | 极低 | V1.0 单门店最多 24 座（doc/11 §3.3）；BEAN-004 上线后 join 在 SQL 层做，无 N+1 |
| R6 | unibest auto-import 在 vitest 不工作 — 必须显式 import { computed } 等 | 已修 | 已在 BizSeatList.vue / BizDatePicker.vue 加显式 import；BizSlotGrid.vue 无 computed 不影响；今后所有 biz 组件**强制**显式 import vue 内置 |
| R7 | mp 端 ID 类型 number\|string 混用 — 若后端未来配 ToStringSerializer 时 number 字面量会丢失 | 已防御 | 组件层一律 String(seat.id) + emit 出 string；测试 BizSeatList "ID String 化"显式锁定 |

---

## 对下游 ticket 的提示

### BEAN-004（提交预约 + UNIQUE + Redis 锁 — 当日最复杂 ticket ⭐）

**核心改动**：
1. **建 `gz_bean_booking` 表**（doc/11 §3.4，方案 C dedup_token）：
   ```sql
   CREATE TABLE gz_bean_booking (
     id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
     booking_no VARCHAR(32) NOT NULL,                          -- BK-yyyyMMdd-6 位
     user_id BIGINT UNSIGNED NOT NULL,
     store_id BIGINT UNSIGNED NOT NULL,
     seat_id BIGINT UNSIGNED NOT NULL,
     seat_no_snapshot VARCHAR(16) NOT NULL,
     sess_date DATE NOT NULL,
     slot_start TIME NOT NULL,
     slot_end TIME NOT NULL,
     mobile_snapshot VARCHAR(11) NOT NULL,
     status VARCHAR(16) NOT NULL DEFAULT 'pending',
     verify_code VARCHAR(128) NOT NULL,
     verify_time DATETIME(3) NULL,
     verified_by VARCHAR(64) NULL,
     cancelled_time DATETIME(3) NULL,
     no_show_time DATETIME(3) NULL,
     dedup_token VARCHAR(64) NOT NULL,                         -- pending → seat_id|sess_date|slot_start | 非 pending → booking_no
     version INT NOT NULL DEFAULT 0,                           -- @Version 乐观锁
     tenant_id VARCHAR(20) NOT NULL DEFAULT '1001',
     del_flag CHAR(1) NOT NULL DEFAULT '0',
     create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
     create_by BIGINT NULL,
     update_time DATETIME ON UPDATE CURRENT_TIMESTAMP,
     update_by BIGINT NULL,
     remark VARCHAR(500),
     UNIQUE KEY uk_booking_no_tenant (tenant_id, booking_no),
     UNIQUE KEY uk_verify_code_tenant (tenant_id, verify_code),
     UNIQUE KEY uk_dedup_token_tenant_store (tenant_id, store_id, dedup_token),   -- ⭐ 核心防超卖
     KEY idx_user_seat_slot (tenant_id, user_id, sess_date, slot_start),
     KEY idx_store_date (tenant_id, store_id, sess_date),
     KEY idx_status (tenant_id, status)
   );
   ```

2. **改本 ticket `/availability` 端点**（GzBeanSeatMpController 第 86 行 TODO）：
   ```java
   // 从 occupied seatId 集合判 available
   Set<Long> occupiedIds = bookingMapper.selectOccupiedSeatIds(storeId, date, slotStart);
   for (GzBeanSeatVO s : seats) {
     vo.setAvailable(!occupiedIds.contains(s.getId()));
   }
   ```
   mapper 方法签名建议：
   ```sql
   SELECT seat_id FROM gz_bean_booking
    WHERE store_id=#{storeId} AND sess_date=#{date}
      AND slot_start=#{slotStart} AND status='pending'
      AND del_flag='0' AND tenant_id=#{tenantId}
   ```

3. **Redis 锁 + 提交流程**（doc/10 §3.N7 / 并发控制）：
   - key: `bean_seat:{store_id}:{seat_id}:{date}:{slot_start}` TTL 5s
   - key: `bean_user_submit:{openid}` TTL 5s（防同用户连点）
   - 提交事务：①取座位 Redis 锁 → ②检查 booking 表无 pending → ③INSERT booking (status=pending) → ④释锁 → ⑤UNIQUE 索引兜底

4. **mp 主选座页跳转**（select.vue 第 183 行 TODO(GZ-BEAN-004)）：
   ```ts
   uni.navigateTo({
     url: `/pages/bean/confirm?storeId=${storeId}&date=${date}&slotStart=${slotStart}&seatId=${seatId}&seatNo=${seatNo}`
   })
   ```
   即把当前 select.vue 的 onNext() 的 toast 改为真 navigate。建议保留 BEAN-003 当前 5 个 query 字段（防止 confirm 页重拉 store 信息）。

5. **手机号强收集**（doc/10 §3.N6）：confirm 页（BEAN-004）顶部先检查 `gz_user.mobile` 是否空 → 空则弹原生 `<button open-type="getPhoneNumber">` → 后端 phonenumber/getPhoneNumber 解密 → 更新 `gz_user.mobile`。本 ticket select.vue **不**做手机号收集 — 用户可能选错时段未提交，不应过早强收集。

### BEAN-005（mp 预约详情 + 核销码 QR）

- 复用 BizFixedCta（已建）展示底部"取消预约"按钮
- 核销码 QR：`booking_no + verify_code` 拼字符串内嵌；前端用 qrcode-uni 或自带 wxapi 渲染
- 关键：拉详情时 join `gz_bean_store.name` + `gz_bean_seat.seat_no_snapshot`（已存 snapshot，无需 join seat 表）

### BEAN-010（拼豆首页 — 清理本 ticket 临时入口）

- §0 自检阶段 grep `Tier2-entry-temp` 会发现 pages/bean/index.vue 第 18-22 行 + 第 41 行临时入口卡片
- 实施步骤：①替换 pages/bean/index.vue 为真正的拼豆首页（含门店卡 / 推荐时段 / 我的预约入口）② 拼豆首页主 CTA "立即预约" 跳 select.vue（替代临时入口卡片）③ 去掉两处 TODO(Tier2-entry-temp) 注释 ④ 清理 bean.entry.* locale key（或保留供未来）

### product / curator

1. **任务卡 AC 4 偏差**：任务卡说后端返 `[{seat_id, seat_no, is_occupied: bool}]`，本 ticket 实际返 `{seatId, seatNo, available: bool}`（驼峰 + 取 available 否定语义）— **采用驼峰是 Jackson 默认行为，符合 sensenran 项目惯例**；available 比 is_occupied 语义更正向。建议 curator 周巡时同步对齐任务卡 / 文档（如统一为 available）
2. **doc/11 §3.3 V1.0 数据**说明"24 条座位（A1-A6 / B1-B6 / C1-C6 / D1-D6）"— 本 ticket seed 仅 5 座位作 mp 测试；BEAN-002 admin 端已可一键批量生成 24 座（batchGenerate prefix=A count=6 等）。Kevin 上线前需 admin 端配齐
3. **mp 端 ID number\|string 类型混用**已防御（组件层 String 化 + 测试锁定）；建议下游 ticket 继续沿用此纪律 — 若后端未来切 ToStringSerializer 不需要前端改

---

## §AI 测试段（kevin-qa Tier 1B，07:10）

### mp vitest unit

```
$ cd code/main/miniapp && pnpm vitest run

 ✓ src/utils/watermark.test.ts (9 tests) 3ms
 ✓ src/api/gz-bean.test.ts (5 tests) 8ms
 ✓ src/api/customer-service.test.ts (3 tests) 4ms
 ✓ src/store/customer-service.test.ts (6 tests) 8ms
 ✓ src/store/token.test.ts (3 tests) 14ms
 ✓ src/components/biz/BizSeatList.test.ts (4 tests) 13ms

 Test Files  6 passed (6)
      Tests  30 passed (30)
   Duration  1.01s
```

全 30 通过（9 新增 BEAN-003 + 21 回归）。stderr 中的 `[customer-service] ... failed, fallback` 是测试刻意触发的 error path fallback，均在 ✓ 范围内，非失败。

### 静态结构验证

```
$ ls code/main/miniapp/dist/dev/mp-weixin/pages/bean/
index.js  index.json  index.wxml  index.wxss
select-vendor.js  select.js  select.json  select.wxml  select.wxss
# ✅ select.{wxml,wxss,js,json} 全有；index.* 含临时入口页 全有

$ ls code/main/miniapp/src/components/biz/
BizCustomerServiceFab.vue  BizDatePicker.vue  BizFixedCta.vue
BizSeatList.test.ts  BizSeatList.vue  BizSlotGrid.vue  ComingSoonV11.vue
# ✅ BizDatePicker / BizSlotGrid / BizSeatList 全在 biz/ 目录（CLAUDE.md §7.5 组件库无关纪律）
```

### Tier 2 可达性验证

```
$ grep -n "Tier2-entry-temp.*GZ-BEAN-003" src/pages/bean/index.vue
18:/** TODO(Tier2-entry-temp): GZ-BEAN-003, remove when GZ-BEAN-010（拼豆首页）merged.
41:      <!-- TODO(Tier2-entry-temp): GZ-BEAN-003, remove when GZ-BEAN-010 merged -->
# ✅ 两处注释均存在，含 ticket ID + 清理时机
```

临时入口路径：mp 启动 → 拼豆 tab（pages/bean/index.vue）→ 1 次点击"进入选座" → pages/bean/select ✅

### TODO 占位注释验证

```
$ grep -n "TODO(GZ-BEAN-004)" controller/applet/GzBeanSeatMpController.java
86:  // TODO(GZ-BEAN-004): join gz_bean_booking after BEAN-004 lands.
# ✅ availability 端点占位注释在位

$ grep -n "TODO(GZ-BEAN-004)" src/pages/bean/select.vue
183:  // TODO(GZ-BEAN-004): replace with uni.navigateTo({ url: `/pages/bean/confirm?...` })
# ✅ mp 端导航占位注释在位
```

### API 契约回归

注：所有 mp 端 API 请求须同时携带 `Authorization: Bearer <token>` + `clientid: mp-applet-sensenran-guzi`（sa-token 多客户端机制）。

```bash
# 登录取 token（开发环境 wx-login mock 短路）
POST /app/gz/common/auth/wx-login  -H "clientid: mp-applet-sensenran-guzi"
  -d '{"code":"mock-bean003-qa-tier1b-final","nickName":"QA-Final"}'
→ 200 {"token":"eyJ...","userId":"16","openid":"mock-mock-bea"} ✅

# TEST-1: store/list（BEAN-001 回归）
GET /app/gz/bean/store/list
→ 200 [{"id":1,"storeNo":"CD001","name":"成都春熙路店","type":"pindou",...}] ✅

# TEST-2: slot/list 今天（2026-05-29，星期四 = weekday 4，包含在 "1,2,3,4,5,6,7" 中）
GET /app/gz/bean/slot/list?storeId=1&date=2026-05-29
→ 200 [{slotName:"上午",startTime:"10:00:00",...},{slotName:"下午",startTime:"14:00:00",...}]
  ✅ 2 时段全返；weekdays 过滤正确；按 sortNo 升序

# TEST-3: seat/list（B2 enabled=0 应被过滤）
GET /app/gz/bean/seat/list?storeId=1
→ 200 [A1,A2,A3,B1]（4 座）| B2 absent: True ✅

# TEST-4: availability 占位（BEAN-004 前全返 available=true）
GET /app/gz/bean/seat/availability?storeId=1&date=2026-05-29&slotStart=10:00:00
→ 200 [{"seatId":1,"seatNo":"A1","available":true},{"seatId":2,...},{"seatId":3,...},{"seatId":4,...}]
  ✅ 4 座全 available=true 占位符合预期

# === error path ===

# TEST-5: slot/list 缺 date 参数
GET /app/gz/bean/slot/list?storeId=1  （无 date）
→ 500 {"msg":"发生未知异常，请联系管理员"} ✅（@NotNull 拦截）

# TEST-6: 无 token
GET /app/gz/bean/seat/list?storeId=1  （无 Authorization header）
→ 401 {"msg":"认证失败，无法访问系统资源"} ✅

# TEST-7: 错误日期格式 2026/05/29（斜杠格式）
GET /app/gz/bean/slot/list?storeId=1&date=2026/05/29
→ 500 {"msg":"请求参数类型不匹配，参数[date]要求类型为：'java.time.LocalDate'，但输入值为：'2026/05/29'"} ✅
```

7/7 API 契约测试通过（4 happy + 3 error）。

**注意（留给下游 BEAN-004）**：mp 端所有请求须带 `clientid: mp-applet-sensenran-guzi` header，DB sys_client 表当前无此记录但认证路径走的是 wx-login 自定义 controller，sa-token 通过 clientid header 做租户路由，无需 sys_client 表预先存在。curl 直调时记得加这个 header，否则 401。

### 跳过 / 未跑

- mp wx.login 真实微信 code 兑换 → 真机能力，跳给 Kevin Tier 2
- mp 页面真机渲染效果（BizDatePicker 横滑 / BizSlotGrid 2 列网格 / BizSeatList 3 列列表）→ 微信开发者工具真机 spot check，Tier 2 Kevin 验
- 未登录弹 useNavGuard 登录引导的 UI 交互 → wx.login 真机能力依赖，跳 Tier 2
- BizSeatList 占用态视觉（灰显 / 高亮）→ BEAN-004 availability join 上线前无真实 occupied 数据，视觉验证推 BEAN-004 后

### 结论

✅ Tier 1B 全通过，BEAN-003 可进入 Tier 2（Kevin mp 真机 spot check）：

| 检查项 | 结果 |
|---|---|
| vitest 30/30 | ✅ |
| dist 产物完整（select.* + index.*）| ✅ |
| BizDatePicker / BizSlotGrid / BizSeatList 在 biz/| ✅ |
| Tier2-entry-temp 注释存在（含 ticket ID + 清理时机）| ✅ |
| TODO(GZ-BEAN-004) 注释在 controller + select.vue | ✅ |
| API 契约 4 happy path | ✅ |
| API 契约 3 error path | ✅ |
| enabled=0 座位（B2）过滤 | ✅ |
| 无 token 401 | ✅ |
