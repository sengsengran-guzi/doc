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
