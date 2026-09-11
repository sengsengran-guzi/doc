# GZ-RECYCLE-017 — 完工报告

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | ✅ 起点 clean | 三个代码仓起点均 clean（部署流水线已把 D22/D23 推 staging） |
| 上游依赖 merge | ✅ | GZ-RECYCLE-012 小时格 / 014 取消顾客单 均已在 staging |
| 关键类/表/API 存在 | ✅ | `markNoShow` / `selectExpiredSubmittedIds` mapper 方法早已存在，本次纯复用 |
| 编译通过 | ✅ | `mvn clean install` 见下 |
| 权威蓝图引用 | doc/11 §12 回收段（状态机） | 无字段变更，无需更新字段表 |
| ADR 已读 | ADR-0022（小时格占用）+ 对齐 GZ-BEAN-041 | 无新决策，不新增 ADR |
| 合同范围 | V1.2（回收域运维能力） | |

## 改了哪些文件

**后端**（255 行，0 迁移）：
```
 controller/GzRecycleAppointmentController.java     |  44 ++  (2 新端点)
 service/IGzRecycleAppointmentService.java          |  46 ++  (2 方法 + BatchReleaseResult record)
 service/impl/GzRecycleAppointmentServiceImpl.java  |  51 ++  (实现)
 domain/bo/GzRecycleBatchReleaseBo.java             | 新增    (ids + @Size(500))
 test/.../GzRecycleAppointmentServiceImplTest.java  | 114 ++  (7 个新用例)
```

**Admin**（215 行）：
```
 api/gz-recycle/appointment.ts              |  34 ++
 lang/zh_CN.ts / en_US.ts                   |  16 ++ each
 views/gz-recycle/appointment/index.vue     | 149 ++  (过期待处理 panel)
```

**零迁移 / 零新表 / 零新权限 / 零新状态** —— 纯复用既有 `markNoShow` + `no_show`。

## AI 自测

### 1) 后端单测（新增 7 例，全模块 118 全绿）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle -am
[INFO] Tests run: 30, Failures: 0, Errors: 0 -- GzRecycleAppointmentServiceImplTest   （原 23 + 新 7）
[INFO] Tests run: 118, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

新增用例：全部成功 / 幂等 skipped / 单条异常不中断整批 / 空入参不打 DB /
上界夹到昨天 / 区间倒置返空不打 DB / 只查 submitted 不含 confirmed_onsite。

⚠️ 踩坑记录：断言 wrapper 参数时 `getParamNameValuePairs()` 恒空 —— `.eq()/.le()` 是**延迟**解析，
必须先调 `getSqlSegment()`，而那需要 MP lambda 缓存（纯 Mockito 无 Spring 容器）。解法同
`GzRecycleStaffListTest`：`@BeforeAll` 加 `TableInfoHelper.initTableInfo(...)`。

### 2) 前端 typecheck + lint

```
$ npx vue-tsc --noEmit -p tsconfig.json | grep gz-recycle
✅ gz-recycle 零 TS 错误

$ npx eslint --fix src/views/gz-recycle/appointment/index.vue src/api/gz-recycle/appointment.ts src/lang/*.ts
eslint EXIT=0

$ i18n key 对齐检查
zh keys=415  en keys=415 ；zh 独有: 无 ；en 独有: 无
```

### 3) 真接口端到端（含最关键的「顾客被卡死→解封」闭环）

```
① 列表：条数=5，全部 submitted，全在过去 ✅
  RCY-20260709-000003  2026-07-09  user=11
  RCY-20260709-000001  2026-07-10  user=11
  ... （5 条）

② 日期筛选 dateFrom=2026-07-15 → 条数=2 ✅（精确收敛）

③ 【顾客被卡死取证】mp 真下单，同用户第二次提交：
   {"code":4127,"msg":"您已有进行中的回收预约，完成或取消后再约"}   ← 守卫如实触发

④ 把该单挪到过去 → 出现在过期列表（条数 5→6）✅

⑤ 释放：{"succeeded":1,"skipped":0,"failed":0}

⑥ 【解封验证】同一顾客重新预约：
   code=200 操作成功  新单=RCY-20260828-000002 2026-09-01 15:00:00   ← ★ 闭环成立

⑦ 幂等：重复释放同一单 → {"succeeded":0,"skipped":1,"failed":0} ✅

⑧ 把一张 confirmed_onsite 单挪到过去 → 列表 5 条，非 submitted 的 0 条 ✅（完成态未被卷入）
```

### 4) admin 真浏览器（Playwright，0 console error）

```
标题栏: 过期待处理 5 GZ-RECYCLE-017
列头:   [预约号, 门店, 数量区间, 到店日期, 到店时段, 已过期, 操作]
首行:   RCY-20260709-000003 成都春熙路店 200 点以上 2026-07-09 19:00-21:00 【50 天】 详情
按钮:   [查询, 重置, 批量释放]

勾选 2 行 → 按钮变「批量释放 （2）」且启用 ✅
点击 → 二次确认「确认释放选中的 2 笔过期预约？释放后状态变为「未到店」，对应顾客可重新预约。」✅
确认 → 列表 5→3，标题徽章同步 5→3 ✅
DB 核对：id=1、3 → no_show；id=2、4、5 原样 submitted ✅（精确释放勾选项，未误伤）
console：0 errors（2 warning 是 ruoyi 框架自带 router deprecation）
```

清理：测试数据已全部复原（id 1/3 回 submitted、id 31 回 2026-08-15、2 张测试单已删）。

## 已知 issue / 风险提示

**🔴 顺带发现一个更严重的线上 bug（本 ticket 未修，需 Kevin 拍板）**

`USER_ACTIVE_STATUSES` / `countActiveByUserForUpdate` 都含 `confirmed_onsite`。但客户 7.15 把回收改成
**店内现金结算后，`confirmed_onsite` 就是终态**（`verify` 里 auto-payout 关闭时直接 return，不再进 paying/paid）。

后果：**任何成功卖过一次东西的老顾客，永远约不了第二单。**

dev 库实证：user 14 只有一张 `confirmed_onsite` 单，已被永久锁死。

这不是有意设计 —— 常量注释自己写着「排除 paid/cancelled/no_show 三终态（**拿到钱或结束即可再约**）」，
意图明确是「交易结束就能再约」。只是 7.15 切现金模式时漏改了这个列表（打款模式下 `paid` 才是终态，
现金模式下 `confirmed_onsite` 就是）。

修法是把 `confirmed_onsite` 从两处（Java 常量 + mapper `@Select` 内联字面量，
`GzRecycleActiveStatusConsistencyTest` 会守一致性）移除。**但这是业务口径变更**（谁能再约），
故本 ticket 不擅自改，列给 Kevin 决策。

**其他**
- 本 ticket 无 mp 端改动，未跑 mp 模拟器 E2E。
- 释放是**单向**的：`no_show` 没有回滚入口。若店员误释放，顾客重新下单即可（这也正是释放的目的），
  原单不恢复。考虑到 no_show 本就是该单的正确终态，未做撤销功能。

## 交付前须向甲方确认

1. 「释放」的语义是标记为**「未到店」**（no_show），不是删除 —— 记录仍在，可查、可对账。
2. 已核对完成的单（「店员已确认」）**不在候选内**，不会被误释放。
3. 上面那个 🔴 老顾客约不了第二单的问题，要不要一起修（改动 2 行，但改变谁能再约的口径）。
# GZ-RECYCLE-018 — 完工报告

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 上游依赖 | ✅ | 由 GZ-RECYCLE-017 实施中查证发现，同批交付 |
| 关键类/常量存在 | ✅ | `USER_ACTIVE_STATUSES` + `countActiveByUserForUpdate` 两份拷贝 |
| 编译通过 | ✅ | `mvn clean install` |
| ADR 已读 | ADR-0021 坑位 3（一人一单集不含 manual_hold 的既有口径）| 本次不改该条 |
| 合同范围 | V1.2 回收域缺陷修复 | |

## 改了哪些文件（3 个，2 行实质改动）

```
service/impl/GzRecycleAppointmentServiceImpl.java   USER_ACTIVE_STATUSES 去掉 confirmed_onsite + javadoc 说明
mapper/GzRecycleAppointmentMapper.java              @Select 内联字面量同步 + javadoc 说明
test/.../GzRecycleActiveStatusConsistencyTest.java  新增回归测试钉死决策
```

**无迁移 / 无表变更 / 无数据订正**。

## AI 自测

### 1) 单测（119/119，一致性测试 3→4）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle -am
[INFO] Tests run: 4, Failures: 0 -- GzRecycleActiveStatusConsistencyTest    （原 3 + 新 1）
[INFO] Tests run: 119, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### 2) ★ 验证一致性守卫真的会红（不是摆设）

改两处拷贝的风险在于「只改一处」。故意把 mapper SQL 改回 4 态、Java 常量留 3 态：

```
[ERROR] GzRecycleActiveStatusConsistencyTest.userActiveStatuses_bothCopiesMatch
org.opentest4j.AssertionFailedError: countActiveByUserForUpdate 的状态个数与 Java 常量不符
  （改口径必须同步所有拷贝）。Java=[submitted, paying, payout_failed]
                            SQL=[submitted, confirmed_onsite, paying, payout_failed]
  ==> expected: <3> but was: <4>
```

守卫如实拦下。恢复正确版本后重跑 → 119/119 绿。

### 3) ★ 真库端到端 A/B 对照（mp 真接口，非 mock）

把那张 `confirmed_onsite` 单（id=31）临时挂到 mock 登录用户名下逐组对照：

**A 组 —— 修复目标：**
```
用户持有 confirmed_onsite（已现金结算完成）→ 提交新预约
✅ 放行  code=200 msg=操作成功   新单=RCY-20260831-000001
```
（修复前此处必为 `code=4127`）

**B 组 —— 资金守卫不得被削弱：**
```
✅ 仍拦截 [paying / 钱在途]                code=4127
✅ 仍拦截 [payout_failed / 打款失败待处理]  code=4127
✅ 仍拦截 [submitted / 真·进行中]          code=4127
```

**C 组 —— 读写路径口径必须一致**（分叉 = 前端显示可约但提交被拒，最难排查的一类投诉）：
```
  confirmed_onsite 读路径横幅=无  写路径=放  ✅一致
  paid             读路径横幅=无  写路径=放  ✅一致
  cancelled        读路径横幅=无  写路径=放  ✅一致
  no_show          读路径横幅=无  写路径=放  ✅一致
  submitted        读路径横幅=有  写路径=拦  ✅一致
  paying           读路径横幅=有  写路径=拦  ✅一致
  payout_failed    读路径横幅=有  写路径=拦  ✅一致
```
全 7 状态零分叉。

### 4) 全量回归（gz-recycle + gz-bean + 依赖模块）

```
[INFO] Tests run: 254, Failures: 0, Errors: 0, Skipped: 0
[INFO] Tests run:  56, Failures: 0, Errors: 0, Skipped: 0
[INFO] Tests run: 264, Failures: 0, Errors: 0, Skipped: 0
[INFO] Tests run: 119, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS                                        （合计 693 全绿）
```

### 5) 数据复原

```
id=31 → user_id=14 / status=confirmed_onsite（回到原始）
20260831 残留单数=0
过期未核销积压=5 条（应为 5）✅
```

## 已知 issue / 风险提示

1. **auto-payout 开启后的极端边界**：若 `markPaying` 返 0（前一句 UPDATE 已持行锁，实际不可能），
   单子会停在 `confirmed_onsite` 且钱未发出，此时顾客可再约。判定为可接受：一人一单是**运营占位规则**
   不是资金安全规则；资金安全由 `out_payout_no` 1:1 幂等保证，再约一张新单不影响旧单打款。
2. **本次不追溯存量**：历史 `confirmed_onsite` 单保持原样，只是不再计入「进行中」——修复即时生效，
   无需数据订正。

## 交付前须向甲方确认

「一人一单」的口径现在是：**顾客手上没有「待到店核对 / 打款中 / 打款失败」的单，就能再约**。
店员核对完成（现金已结清）后顾客**当场即可再下一单**——这是修复后的正确行为，之前是不能的。
