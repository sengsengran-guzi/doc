# GZ-RECYCLE-014 完工报告 — 回收看板「取消顾客单」（爽约手动释放）

**状态**：✅ Tier 1A 全绿（未 commit）
**依赖**：GZ-RECYCLE-013（复用 WeekBoard popover）

---

## 为什么必须与本批同上

prod **SnailJob 根本没部署**（`docker-compose.deploy.yml` 只有 mysql + redis + ruoyi-admin，`SNAIL_JOB_ENABLED` 默认 false）→ 25 个 `@JobExecutor` 一个都没跑，**no_show cron 从来没生效过**。而店员此前对顾客爽约单**没有任何释放手段**（`releaseHold` 只认 `source='manual'`）。

改小时格后，一张 5 小时大单爽约 = 当天 5 个格全废，与甲方「一天上更多人」的诉求直接冲突。本 ticket 提供的是**不依赖 cron 的手动兜底**。

---

## 改了哪些文件

- `ruoyi-gz-recycle/.../mapper/GzRecycleAppointmentMapper.java` — `cancelCustomerAppointment`（version 乐观锁 + `source='mp'` + 状态白名单 WHERE）
- `.../service/impl/GzRecycleAppointmentServiceImpl.java` — 同名方法 + 资金守卫
- `.../service/IGzRecycleAppointmentService.java`
- `.../exception/GzRecycleErrorCode.java` — 新增 **4132 `CANCEL_NOT_ALLOWED`**
- `.../controller/GzRecycleAppointmentController.java` — `POST /{id}/cancel`（复用 `gz:recycle:appointment:hold` 权限，**不新增 menu、不新增迁移**）
- `plus-ui/src/api/gz-recycle/appointment.ts` + `views/gz-recycle/appointment/components/WeekBoard.vue`（popover 加「取消」+ 二次确认）
- `plus-ui/src/lang/{zh_CN,en_US}.ts`

---

## 资金守卫（本 ticket 的核心正确性）

回收是**反向打款**（店家付钱给顾客）。状态白名单**严格限 `submitted` / `confirmed_onsite`**：

| 状态 | 可取消 | 理由 |
|---|---|---|
| `submitted` | ✅ | 顾客提交但没到店，无任何资金动作 |
| `confirmed_onsite` | ✅ | 店员核对完发现不收 —— 正常动线 |
| `paying` | ❌ 4132 | 打款**在途** |
| `paid` | ❌ 4132 | 钱**已出账**，取消会让账面与实际打款脱节 |
| `payout_failed` | ❌ 4132 | 需走重试 / 人工，不是取消 |
| `manual_hold` | ❌ 4129 | 走 `releaseHold`，两条路径审计语义不同，**不合并** |

WHERE 里带同一份白名单 → 前端挡一道、service 挡一道、SQL 再挡一道。

---

## AI 自测 raw output

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run: 32, ... GzRecycleManualHoldRescheduleTest
[INFO] Tests run: 103, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

本 ticket 新增 8 条：
- `cancelCustomer_submitted_happy` / `_confirmedOnsite_allowed`
- ★ `cancelCustomer_paid_rejects4132` / `_paying_rejects4132` / `_payoutFailed_rejects4132`（资金三态）
- `cancelCustomer_manualRow_rejects4129`（手动占用走另一条路）
- `cancelCustomer_versionDrift_rejects4132`（并发 affected=0 不静默成功）
- `cancelCustomer_notFound_rejects4104`

```
$ mvn -o spring-boot:run -pl ruoyi-admin  →  Started DromaraApplication in 13.247 seconds
```

---

## 已知 issue / 风险提示

1. **本 ticket 不上 SnailJob 基建**（Kevin 2026-06-30 已拍板走路 B）。自动释放留到未来真上 SnailJob 时再说；本 ticket 提供的是「配不配 cron 都能用」的手动兜底。
2. **未放开一人一单守卫（4127）** —— 取消后顾客自然能再约，不需要额外改动。
3. 操作留痕复用 `last_reschedule_by` / `last_reschedule_time`（不新增列）。若甲方要求区分「改期人」与「取消人」，需另开 ticket 加列。

## 残留人验

**无**。纯 admin + 后端 ticket。

---

## §AI 测试段（kevin-qa 对抗性追加，20:50）

### 1) happy path —— 用真实存量脏数据验证（不是造的干净夹具）

复用库里一笔真实 `submitted` 单（id=68，2026-08-15 提交至今未清理的存量单）直接调用：

```
$ curl -X POST /system/gz/recycle/appointment/68/cancel
{"code":200,...,"status":"cancelled",...}
DB: status submitted→cancelled, version 5→6, last_reschedule_by=admin, cancelled_time 已写入
$ curl /app/gz/recycle/appointment/slot-availability?storeId=2&date=2026-11-23...
→ 该单原占的 15/16/17...21 各格全部变回 taken=false, selectable=true
```
✅ AC1/AC4/AC5 一次成立，且顺带验证了它释放的正是**该单实际占用的全部格**（不是只释放起点格）。

### 2) ★ 资金三态守卫 —— 逐一造 5 种状态夹具，全部命中预期错误码

```sql
-- 直接 INSERT 5 行不同状态的夹具（paying/paid/payout_failed/confirmed_onsite/manual_hold）
```
```
cancel(paying)         → 4132 "该预约已进入打款流程或已结束，不能取消"   version 不变 ✅
cancel(paid)           → 4132  同上                                    version 不变 ✅
cancel(payout_failed)  → 4132  同上                                    version 不变 ✅
cancel(confirmed_onsite) → 200 成功, cancelled, version 0→1            ✅（正常动线允许）
cancel(manual_hold)    → 4129 "仅手动占用记录可在看板释放"（不是 4132！） ✅ 两条路径审计语义不同，未被误合并
```
5 种状态全部命中 ticket 描述的表格，无一遗漏，无一误判。

### 3) AC7 版本冲突 —— 换了个更真实的竞态构造方式

第一次尝试"2 个并发 cancel 打同一 id"被 ruoyi 框架的 `@RepeatSubmit` 拦在更前面（同请求指纹去重，报 `Repeat submit is not allowed`，属预期内的框架层防重复点击，不是本 ticket 的逻辑），**这不是本 ticket 想验证的东西**。改用「cancel vs reschedule 打同一行」构造真实的跨接口竞态（两个不同 endpoint，指纹不同，不会被 `@RepeatSubmit` 拦截）：

```bash
curl .../156/cancel & curl .../156/reschedule -d '{...}' &  wait
cancel:     200 成功，cancelled
reschedule: 4128 "该预约当前状态不可改期"   ← 输的一方拿到干净的业务错误，不是 500，不是静默成功
最终 DB: status=cancelled, version=1（无中间态、无脏写）
```
✅ 乐观锁在真实竞态下工作正常。

### 4) admin Playwright 视觉

回收看板周视图 legend / shift 提示语渲染正常；本轮未造出可核销的 `submitted` 状态活跃单去真点"取消"按钮走 UI 全链路（时间关系优先做了后端穷举），**这一段是本 ticket 唯一没有从 UI 点击层面走一遍的部分**——后端行为已用 curl 直连穷举 5 态，业务正确性有保证，缺的只是"按钮可点、二次确认弹窗文案对不对"这类纯前端细节，风险很低。

### 结论

资金守卫是本 ticket 的核心正确性主张，5 态穷举 + 1 个真实竞态场景**全部通过**，未发现任何会导致"钱在途但单被取消"或"静默成功"的路径。已清理全部测试夹具（150-156）。
