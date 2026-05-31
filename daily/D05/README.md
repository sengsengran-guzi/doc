# D05（Kevin 口径 d4）— 拼豆收尾：详情/列表/取消 + admin 核销 + no_show cron + 拼豆首页

> 日期：2026-06-02（周二）
> 阶段：V1.0 实施期 day 4 — 拼豆 V1.0 闭环最后一日
> 上一日：[D04](../D04/README.md) ｜ 下一日：[D06](../D06/README.md)

---

## 今日目标

- **主线 1**（用户侧闭环）：基于 D04 已落地的提交链路，把"看 / 列表 / 取消"三件事补齐 — mp 端预约详情 + 核销码大图（BEAN-005）、我的预约列表 4 状态 tab（BEAN-006）、取消预约二次确认（BEAN-007）
- **主线 2**（商家侧闭环）：admin 后台预约列表 + 扫码 / 手动核销（BEAN-008）— 让甲方店员能真正在线下走核销动作
- **主线 3**（异常收尾）：凌晨 2 点 no_show 定时任务（BEAN-009）+ mp 拼豆首页落地页（BEAN-010）

完工后拼豆预约 V1.0 整条业务流闭环：用户「打开 mp → 拼豆 tab 落地页 → 选座 → 提交 → 看码 → 到店核销 / 自主取消 / 隔夜过期」，店员「admin 端管理预约 + 扫码核销」。**D06 起进入 GZ-USER 会员中心 + GZ-NEWS 资讯阶段。**

## Ticket 清单（6 个，1 个串行链 + 4 个并行）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-BEAN-005 | mp 预约详情 + 核销码 QR 大图 | S | GZ-BEAN-004 ✅(D04) | pending |
| GZ-BEAN-006 | mp 我的预约列表（4 状态 tab） | S | GZ-BEAN-005 | pending |
| GZ-BEAN-007 | mp 取消预约（二次确认 + cancelled） | S | GZ-BEAN-006 | pending |
| GZ-BEAN-008 | admin 预约列表 + 扫码 / 手动核销 | M | GZ-BEAN-004 ✅ + GZ-SYS-006 ✅(D02) | pending |
| GZ-BEAN-009 | no_show 自动标记 cron（凌晨 2 点） | S | GZ-BEAN-004 ✅ | pending |
| GZ-BEAN-010 | mp 拼豆首页（C 端入口落地页） | S | GZ-BEAN-003 ✅(D04) | pending |

详见 `tickets/<TICKET-ID>.md`。

**依赖说明**：
- **串行链**：BEAN-005 → BEAN-006 → BEAN-007（详情接口 / 列表接口 / 取消接口逐层递进，BEAN-007 取消按钮挂在 BEAN-006 列表项 + BEAN-005 详情页）
- **并行**：BEAN-008 / BEAN-009 / BEAN-010 三者互无依赖，可与 BEAN-005 同时 spawn

## 派单方式

**整日触发**（推荐 — 主线程读本 README → 按依赖图 spawn 多个 kevin-coder）：

```
开始 d4
```

**单 ticket 触发**（如某 ticket revision 闭环 / 局部重做）：

```
@coder 做 D05/GZ-BEAN-008
```

主线程动作：
1. 读 D05/README.md（本文件）+ 依赖图
2. **首发并行**：同时 spawn BEAN-005（串行链头）+ BEAN-008 + BEAN-009 + BEAN-010（4 个 subagent 并发跑）
3. BEAN-005 ✅ → spawn BEAN-006
4. BEAN-006 ✅ → spawn BEAN-007
5. 6 个 ticket 全部 ✅ → 主线程提示 Kevin testing-human + 日终 closing

## 今日特殊约束

- **拼豆收尾日 = 闭环验证日**：本日 testing-human 必须把"用户提交 → 用户看码 → 店员扫码核销 → 标 used"的端到端跑通一次（D04 只验到"提交成功"，本日验"全闭环"）
- **核销码签名密钥统一**：BEAN-005 渲染 QR / BEAN-008 扫码校验 — 两端必须用同一个 `gz.bean.qr.signing-secret`（D04 BEAN-004 已落 yml 配置），不要在本日各自新生 secret
- **状态枚举 4 个**（doc/10 §3 状态机 + doc/11 §A.3 速查表）：`pending` / `used` / `cancelled` / `no_show`；本日 BEAN-006 tab / BEAN-008 筛选 / BEAN-009 cron 三处必须用同一份字典编码（sys_dict_data `gz_bean_booking_status`，doc/11 §10.2 已定义）
- **取消时机**（合同 §2.3）：V1.0 不限制取消时间（即便已到时段开始仍可取消）；BEAN-007 任务卡里写「v2 候选：取消截止 / 黑名单」TODO，不实现
- **admin-bookings.html mockup 缺口**（doc/12 §1.2 列为缺口）：BEAN-008 admin 端直接走 ruoyi/Element Plus 默认审美（不套用 C 系统）BizTable + 复用 D03 ADMIN-002 的列表模板，**不依赖 mockup**（CLAUDE.md §7.5：admin 完全不评判视觉）
- **no_show cron 配置**（CLAUDE.md §6 + 复用 ruoyi 自带 SnailJob / Quartz）：BEAN-009 任务挂在 ruoyi `sys_job` 表，cron 表达式 `0 0 2 * * ?`，job 名 `GZ-BEAN-NO-SHOW-MARK`；任务幂等可重跑（doc/10 §3 §异常分支 E10 已约定）
- **DDL 文件命名**：本日 BEAN-009 / BEAN-010 会写 DDL（注册 job / 默认 banner 配置），命名严格按 `V<yyyyMMddHHmm>__GZ-BEAN-00X-<desc>.sql`
- **不要 commit**：6 个 ticket 全部 ✅ + Kevin testing-human 通过端到端闭环验证后再统一 commit

## 与昨日 reports 对账（D04）

D04 完工后预期产物（本日依赖）：
- ✅ `gz_bean_booking` 表 schema + UNIQUE 索引（BEAN-004 落 DDL）— 本日 BEAN-005 读取、BEAN-008 列表查、BEAN-009 cron 扫描全靠这张表
- ✅ 核销码 payload 生成 + HMAC 签名（BEAN-004 service 层）— 本日 BEAN-005 mp 端 wxapi 渲染 QR、BEAN-008 admin 扫码校验签名复用 `BeanQrService.sign() / verify()`
- ✅ `application-{env}.yml` 的 `gz.bean.qr.signing-secret` 已配（dev / staging / prod 不同）
- ✅ mp 端 `useBookingSelection` pinia store 已就位（BEAN-003）— 本日 BEAN-010 拼豆首页 CTA 跳转 BEAN-003 选座页时复用该 store
- ⏳ BEAN-004 reports 如有遗留 §revision 未闭环 → 本日 STOP 等 D04 闭完再开

## 完成判定（DoD）

- [ ] 6 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 6 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿（任一红 → STOP）
- [ ] testing-human.md 全勾：
  - mp 端用户：从拼豆首页 → 选座 → 提交 → 看码（QR 清晰可扫）→ 进我的预约列表（4 tab 切换）→ 进详情 → 取消 → 状态变 cancelled → 再次提交新预约
  - admin 端店员：进预约管理 → 看列表（按门店 / 日期 / 状态筛）→ 扫 mp 端码 → 状态变 used + 操作日志记录
  - cron：手动触发 BEAN-009 job（admin 端 sys_job 列表点"执行一次"）→ 检查昨日 pending 是否被批量标 no_show

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 核销码 QR 在低端机扫描慢 / 失真 | BEAN-005 用微信原生 `wx.createOffscreenCanvas` + 控制 payload < 200 字符；testing-human 用真机扫一次 |
| R2 | BEAN-008 扫码核销与 BEAN-007 用户取消的竞态（用户在店员扫码瞬间点取消） | doc/10 §3 §异常分支 E6/E7 已约定：核销时校验 `status = pending` 才允许标 used，否则返回「已取消 / 已核销」错误 |
| R3 | BEAN-009 cron 任务失败被吞掉 → no_show 标漏 | doc/10 §3 §异常分支 E10：cron 必须幂等（重跑不重复标），失败 → ruoyi SnailJob 自带告警通道；不允许 catch 后静默 |
| R4 | admin-bookings.html mockup 缺口 → BEAN-008 视觉与最终方向不一致 | admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统）；本日 BEAN-008 testing-human 不评判视觉 |
| R5 | BEAN-006 列表无 no_show 状态视觉（mockup booking-list.html 仅 3 状态）| doc/10 §3 §状态机已裁定"V1.0 实现 4 状态，mockup 缺口待 designer 补"；本日 BEAN-006 用 BizTag 灰款（var(--c-ink-3)）渲染 no_show；已切 C 系统，视觉以 doc/tokens.md + doc/13 为准 |
| R6 | BEAN-010 banner / 跑马灯素材未到位（甲方运营素材未发） | 默认占位图 + 文案，BEAN-010 任务卡里写「素材到位后切换无需改代码 — 走 sys_config」 |

---

## 日终 closing 命令

```bash
cd doc/daily/D05
cat reports/*.md > summary.md
# Kevin testing-human OK 后再 commit
git add -A && git commit -m "D05 (d4): 拼豆收尾 BEAN-005/006/007/008/009/010"
# 然后写 D06/README.md（D06 候选：GZ-USER-001/002/003 + GZ-NEWS-001/002）
```
