# D04（Kevin 口径 d3）— 拼豆预约 ⭐ V1.0 核心：主数据 + 选座 + 提交★

> 日期：2026-06-01（周一）
> 阶段：V1.0 实施期 day 3 — **V1.0 最复杂日 ★**
> 上一日：[D03](../D03/README.md) ｜ 下一日：[D05](../D05/README.md)

---

## 今日目标

- **主线**：拼豆预约 V1.0 的**核心数据 + 核心路径 + 核心防并发**一次性立起：
  1. 门店主数据（GZ-BEAN-001）— V1.0 仅成都拼豆店但模型多门店
  2. 座位 + 时段模板配置（GZ-BEAN-002）— admin 端按周配置开放时段
  3. mp 端选日期 → 选时段 → 选座位（GZ-BEAN-003）— 实时占用反馈
  4. **提交预约 + Redis 锁 + UNIQUE 索引防并发（GZ-BEAN-004 ★）** — V1.0 最复杂业务点 ⭐

完工后用户可走通"打开 mp → 拼豆首页 → 选时段 → 选座位 → 提交 → 拿核销码"的核心 happy path（详情展示在 D05 GZ-BEAN-005 实现）；后端有完整防抢座 + 防黄牛刷座 + 防同一用户重复预约的三层防线。

## Ticket 清单（4 个，严格串行依赖）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-BEAN-001 | 门店主数据（后台 + mp） | S | GZ-ADMIN-001 ✅(D03) | pending |
| GZ-BEAN-002 | 座位主数据 + 时段模板配置 | M | GZ-BEAN-001 | pending |
| GZ-BEAN-003 | mp 时段 + 座位选择 | M | GZ-BEAN-002 | pending |
| **GZ-BEAN-004 ★** | **提交预约 + UNIQUE 索引 + Redis 锁** | **M** | GZ-BEAN-003 + GZ-SYS-002 ✅(D02) | pending |

详见 `tickets/<TICKET-ID>.md`。

**依赖说明**：本日 4 ticket **严格串行**（不能并行）：BEAN-001 → BEAN-002 → BEAN-003 → BEAN-004。任一上游失败 → 当日 STOP，下游不开。

## 派单方式

```
开始 d3
```

主线程动作：
1. 读 D04/README.md + 依赖图
2. **严格串行 spawn**：BEAN-001 ✅ → BEAN-002 ✅ → BEAN-003 ✅ → BEAN-004 ★
3. 不允许并行（不像 D02/D03 那样多 ticket 并行 — 拼豆主数据是层层依赖的"骨干"，并行风险大）
4. 4 个 ticket 全部 ✅ → Kevin testing-human 重点验 BEAN-004 并发场景（手动开 2 个微信开发者工具同时点同一座位）+ 日终 closing

## 今日特殊约束 ⭐

- **本日是 V1.0 最复杂日**：BEAN-004 ★ 是 V1.0 唯一 "M" 复杂度 + "L 级思考密度" 的 ticket，AI 实施时**禁止快速过 §0 自检**，强制读 doc/10 §3 拼豆并发段全文 + doc/11 §3 字段权威表全文 + dongjiaoshan 是否有类似抢座并发参考代码（如果有）
- **三层防并发兜底**（doc/10 §3 §并发控制 权威定义）：
  1. **UNIQUE 索引** `(tenant_id, store_id, seat_id, date, slot_start)`（DB 层兜底，不可绕过）
  2. **Redis 短锁** `bean:lock:{user_id}:{date}:{slot_start}` 5s TTL（防同一用户连点）
  3. **业务校验**：同一用户同时段同门店最多 1 个 active 预约（应用层 SELECT-then-INSERT 在事务内）
- **手机号强收集场景**：BEAN-004 用户未绑手机号 → 先弹手机号绑定（`wx.getPhoneNumber` 解码 → 更新 gz_user.phone_num）→ 通过后才执行真预约。**这是 V1.0 唯一强收集手机号的场景**，其他业务（资讯 / 会员中心）不强收
- **核销码生成**：BEAN-004 提交成功后生成 `(预约 ID + HMAC 签名)` 形式的核销码 payload，前端用 wxapi 渲染 QR；签名密钥读 `application-{env}.yml` 的 `gz.bean.qr.signing-secret`（dev/staging/prod 不同）
- **门店 type=pindou 才有预约能力**：BEAN-001 模型 type 字段（enum `pindou` / `guzi`），V1.0 type=guzi 占位不实现预约 UI / API
- **menu_id 段**：本日插入的菜单走 6000-6099 段（CLAUDE.md §6 #6 GZ-BEAN 6000-6999）
- **不要 commit**：4 个 ticket 全部 ✅ + Kevin testing-human 并发验过后再统一 commit

## 与昨日 reports 对账（D03）

D03 完工后预期产物：
- ✅ admin 端布局 + 菜单已就位（ADMIN-004），本日 BEAN-001/002 加菜单挂在「谷子业务」目录下
- ✅ admin 端账号 CRUD 已就位（ADMIN-002），staff 账号绑定 `gz_store_id` 字段可填了（BEAN-001 完工后下拉数据可用）
- ✅ operations 日志 @Log 注解已规约（SYS-006），本日 BEAN-001/002 admin 端 CRUD Controller 必须加 @Log
- ✅ mp 5 tab 已就位（ADMIN-005），本日 BEAN-003 在「拼豆 tab」入口 page 下挂选座页

## 完成判定（DoD）

- [ ] 4 个 ticket 任务卡 §revision 段空
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] **BEAN-004 ★ reports 必须包含「并发压测 raw output」**：用 `ab -n 100 -c 50` 或 `wrk` 压同一时段同一座位的提交接口 100 次并发 → DB 中该座位最终只有 1 条 active 记录
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] testing-human.md 全勾：
  - admin 端 owner 配 1 个门店 + 5 个座位 + 工作日 3 个时段
  - mp 端用户走通选座 → 提交 → 拿到核销码 QR
  - **并发场景**：用 2 个微信开发者工具同时点同一座位提交 → 仅 1 个成功，另一个友好提示「座位已被占」
  - 同一用户同时段提交 2 次 → 第二次被拒
  - 未绑手机号用户提交 → 弹手机号绑定 → 绑定后继续

## 已知风险 ⭐

| # | 风险 | 缓解 |
|---|---|---|
| R1 ★ | BEAN-004 并发场景压不住 → V1.0 上线后真实业务抢座撞车 | UNIQUE 索引是兜底（DB 层不可绕过）；如出现冲突 → 用户友好提示而不是 500 错误；Kevin testing-human 必须手动验并发 |
| R2 | Redis 锁 TTL 设置不当（太长卡死合法重试 / 太短防不住快速连点）| 用 5s TTL + Redisson 自动续期（如启用 Redisson）；测试覆盖"5s 后自动释放" |
| R3 | 时段模板配置复杂（按星期 + 按时段 + 按座位）→ admin UI 编辑成本高 | BEAN-002 提供批量编辑接口（一周配置 + 单座位开关），不强求逐时段配 |
| R4 | 核销码 QR 在低端机微信渲染慢 / 失真 | 用微信原生 `wx.createOffscreenCanvas` + qrcode-uni 库；签名 payload < 200 字符避免 QR 复杂度爆炸 |
| R5 | 手机号强收集影响转化（用户拒授权 → 流失） | doc/10 §3 §异常分支 明确：拒授权 → 弹「拼豆预约需手机号」提示 + 退回选座页；不强制（可走"放弃预约"路径） |
| R6 | 单座位停用（gz_bean_seat.is_active=false）影响已有预约 | doc/10 §3 §业务规则：停用座位不影响已有 pending/used 预约，仅阻断新提交 |

---

## 日终 closing 命令

```bash
cd doc/daily/D04
cat reports/*.md > summary.md
git add -A && git commit -m "D04 (d3): 拼豆主数据 + 选座 + 提交（防并发 ★）"
# 然后写 D05/README.md（D05 候选：BEAN-005/006/007/008/009/010 — 拼豆收尾 6 ticket）
```
