# D<N> — Testing-human（Kevin 一人跑）

> 只做 AI 干不了的活：浏览器 UI / 微信开发者工具 / DB 客户端 / 代码 review / 产品 sense 主观判断。
> 命令式 / 可断言为真假的事（mvn / curl / mysql count）→ AI 在 reports/<T>.md 里贴 raw output，不在这跑。

---

## 0. 环境

- 后端跑起来：`mvn spring-boot:run -pl ruoyi-admin`
- Admin 跑起来：`cd code/main/plus-ui && pnpm dev` → 浏览器 http://localhost:80
- 小程序跑起来：`cd code/main/miniapp && pnpm dev:mp-weixin` → 微信开发者工具打开 `dist/dev/mp-weixin`

---

## 1. 今日 ticket 验收清单

### GZ-XXX-001 — <标题>

**关联 mockup**：design/mockup/<page>.html

**关联 AC**（从 tickets/GZ-XXX-001.md 复制）：
- [ ] AC 1：...
- [ ] AC 2：...
- [ ] AC 3：...

**测试动作**：
1. 浏览器打开 `<URL>` / 微信开发者工具 → 小程序首页
2. 操作：点击 X → 检查 Y
3. DB 验证：mysql 客户端 `SELECT * FROM gz_xxx WHERE ...`
4. admin 不评判视觉，只评判功能（admin mockup 仅概念参考）；如为 mp 页则视觉遵循 C 设计系统（以 doc/tokens.md + doc/13 为准）

**判定**：
- ✅ OK → 在 progress.md 标 ✅
- ❌ NOT OK → 在 `tickets/GZ-XXX-001.md` 的 `§revision` 段写"问题 N: 现象 / 期望"

---

### GZ-XXX-002 — <标题>

（同上格式）

---

## 2. 跨 ticket 联调（如有）

如果今日 ticket 之间有协作（如 GZ-SYS-001 微信登录 → GZ-USER-001 个人资料读取），单独跑一次：

1. 微信登录走通
2. 进入个人资料页 → 数据显示
3. 退出登录 → 再进入 → 应跳登录页

---

## 3. 视觉 / 文案 review

> **admin**：不评判视觉（颜色 / 位置 / 间距），只评判功能（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统）。
> **mp**：视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红主色 / 网点 / 报头风），以 doc/tokens.md + doc/13 为准；不纠结逐像素。

- mp 视觉走 C 设计系统 token（`var(--c-*)`），不硬编码 hex（doc/tokens.md）✅ / 偏色
- emoji 没乱用 ✅ / 滥用
- 中文文案没机翻味 ✅ / 像 GPT 风
- mp 粗墨边 / 硬投影 / 报头风遵循 C 系统 ✅ / 偏差

---

## 4. 性能 sense（主观感受）

- 小程序首页打开秒开？✅ / 卡
- API 响应 < 1s？✅ / 慢（哪个接口）
- DB 数据量级符合预期？✅ / 异常（如本该 10 条结果出来 1000 条）

---

## 5. GZ-ADMIN-105 对账中心 — SnailJob 任务注册（Kevin 控制台手动一次性操作）

> 纯 admin/后端 ticket，AI Tier 1A+1B 全 ✅ 即终态、**无人验**；本节仅为「跑批任务需人在 SnailJob 控制台注册」的运维提醒（禁 Flyway INSERT sys_job）。

在 SnailJob 控制台「任务管理」新建 3 个 Java 注解式任务（执行器名 = `@JobExecutor(name)`，组 `ruoyi_group`，阻塞 DISCARD）：

| 任务名 | 执行器路由 name | CRON | 含义 |
|---|---|---|---|
| 对账每日跑批 | `gzReconDailyJob` | `0 0 2 * * ?` | 每日 02:00 跑前一日 |
| 对账月度跑批 | `gzReconMonthlyJob` | `0 0 3 1 * ?` | 每月 1 日 03:00 跑前月 |
| 对账季度结算 | `gzReconSettleJob` | `0 0 4 15 3,6,9,12 ?` | 季度末月 15 日 04:00 |

注册后可在控制台「手动执行一次」验证：跑完查 `gz_recon_daily/monthly/settle` 落表。对账金额三层比对（误差=0）已由 AI 在 reports/GZ-ADMIN-105.md §AI 自测 3 完成。

---

## 6. GZ-ADMIN-104 物流 2 态推进 — mp 店员端真机人验（批量验，Tier 2）

> 唯一进人验的 D15 ticket（其余纯 admin/后端 AI ✅ 即终态）。可达路径全程走现成真入口（GZ-ADMIN-201 已建），无临时入口。

**可达路径**（≤4 次点击）：店员账号登 mp → 个人中心「门店管理」区块 →「订单查看」→ 选一个 preorder/gacha 订单进详情 → 页面下方「物流推进」操作区。

**测试动作**：
1. 选一个 `logistics_status=in_japan` 的订单 → 点「发往中国」→ 表单出现快递 9 选 1（圆通/顺丰/中通/韵达/京东/EMS/德邦/极兔/其他）+ 单号输入
   - ⬜ **不选快递 或 不填单号 → 「确认」按钮 disabled**（doc/10 §9.E5）
   - ⬜ 选顺丰 + 填单号 SF123 → 确认 → toast「操作成功」→ 物流卡变「已发往中国 + 顺丰 + SF123」
2. ⬜ 点「改单号」→ 改成中通 + ZT999 → 确认 → 物流卡更新（不重置签收倒计时）
3. ⬜ 点「推到已签收」→ 物流卡变「已签收」终态，推进操作区消失
4. ⬜ owner 在 **plus-ui** 订单详情（订单管理 → 详情）点「回退」→ reason 必填（空则 disabled）→ 填原因确认 → 物流态回退一级；店员端 mp **无回退入口**
5. ⬜ 停用该店员 sys_user → mp 再点推进 → 401/403 即踢（ADR-0004）
6. ⬜ 退款订单（business_status=refunded）→ 推进物流报错「该订单已退款，当前状态不可推进物流」

**验完**：OK → progress.md「人验」列标 ✅；NOT OK → 写回 ticket §revision 段 → `@coder 修 D15/GZ-ADMIN-104 revision 段`。
