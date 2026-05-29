# D04（d3）— Testing-human（Kevin 真机 spot check）

> **B 方案**：admin + 后端 + 单测全部 AI 接管。本文件只列 Kevin 要点的具体动作 — mp 端真机 + 微信原生能力 + 并发场景手感。
>
> **本日 Tier 2 范围**：**BEAN-003**（mp 选座三步流）+ **BEAN-004 ★**（confirm 手机号 / success 核销码 / 并发场景）。
> 其他纯 admin / be 段（BEAN-001 / BEAN-002）AI Tier 1A + 1B 已全 ✅，跳过 Tier 2。
>
> **预计时间**：8-12 min（V1.0 最复杂日，**并发场景 + wx.getPhoneNumber 必须真机过一遍**）

---

## 0. 启动前 check

| # | 检查项 | 命令 / 操作 | 状态 |
|---|---|---|---|
| 0.1 | docker 三容器 | `docker ps \| grep sensenran-dev` 看到 mysql/redis/minio 全 Up | ⬜ |
| 0.2 | 后端 8080 | `lsof -i:8080 -sTCP:LISTEN` 看到 java（PID 48183 当前态）| ⬜ |
| 0.3 | mp dev 编译 | `cd code/main/miniapp && pnpm dev:mp-weixin` 等 "DONE Build complete"（dev:mp watch 应一直在跑）| ⬜ |
| 0.4 | 微信开发者工具 | 已导入 `code/main/miniapp/dist/dev/mp-weixin` | ⬜ |
| 0.5 | 准备 2 个微信开发者工具实例 | 并发场景 §1.2 B8 需要（同一座位 2 端口同时点）| ⬜ |

---

## 1. 测试清单

### 1.1 GZ-BEAN-003 — mp 选座三步流

**入口路径**：mp 首页 → 底部「拼豆」tab → 拼豆 tab 页面看到绿色边框「体验选座流程」临时入口卡片 → 点 → `pages/bean/select`
（临时入口含 `<!-- TODO(Tier2-entry-temp): GZ-BEAN-003, remove when GZ-BEAN-010 merged -->`，GZ-BEAN-010 实施时由 coder 清）

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| A1 | 拼豆 tab → 体验选座入口 → 进 select 页 | 顶部门店显示「成都春熙路店」 / 横向日期条今天高亮 | ⬜ |
| A2 | 切日期（点明天 / 后天）| 时段网格刷新（如配了多个 weekday）| ⬜ |
| A3 | 选时段（如「上午」）| 座位列表渲染 A1/A2/A3/B1（B2 enabled=0 不出现）| ⬜ |
| A4 | 选座位 | 座位卡片高亮 brand-primary / 摘要"日期/时段/座位"实时变化 | ⬜ |
| A5 | 底部 CTA 文案变化 | 「请先选时段」→「请先选座位」→「下一步：填写信息」逐步可点 | ⬜ |
| A6 | 点 CTA「下一步：填写信息」| 跳转 `pages/bean/confirm`（不是 toast）— BEAN-004 已接力 | ⬜ |
| A7 | 视觉评判 | **不评判**（设计冻结期 — 6/10-6/14 风格统一时统一过）| ⬜ N/A |

### 1.2 GZ-BEAN-004 ★ — confirm 手机号 + success 核销码 + 并发场景

**入口路径**：从 §1.1 A6 跳进 confirm 页

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| B1 | 进 confirm 页 | 显示 store/date/slot/seat 摘要正确 | ⬜ |
| B2 | **未绑手机号用户**（首次进）— 弹 `<button open-type="getPhoneNumber">` ⭐ | 微信弹**原生授权弹窗**（拒/同意按钮）| ⬜ |
| B3 | B2 拒授权 | 弹「拼豆预约需手机号」提示 + 退回选座页 / confirm 页 disable 提交 | ⬜ |
| B4 | B2 同意授权 → 后端 `/applet/gz/user/bind-phone` 绑定成功 | gz_user.mobile 落库 / confirm 页提交按钮亮起 | ⬜ |
| B5 | 点提交 | 跳 `pages/bean/success` / 显示 booking_no + verify_code（QR 当前是降级文本 — BEAN-005 上 qrcode-uni）| ⬜ |
| B6 | 已绑手机号用户（B4 后重进）→ 直接进 confirm | 不再弹授权 / 直接可提交 | ⬜ |
| B7 | 同一用户同时段重复提交 ⭐（manual 复跑）| 第 2 次返友好错「您已有该时段预约」（4003）| ⬜ |
| B8 | **并发场景 ⭐⭐**：开 2 个微信开发者工具实例 → 两端同一座位同时段同时点提交 | 仅 1 个成功跳 success / 另一个友好错「座位已被占」（4002 SEAT_TAKEN，非 500）| ⬜ |
| B9 | DB 验证（可选 — AI 已 50 并发压测过）| `docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT booking_no,status,seat_id,date,slot_start FROM gz_bean_booking WHERE status='pending' ORDER BY id DESC LIMIT 5;"` 终态符合 | ⬜ |

---

## 2. 跨 ticket 联调

| # | 链路 | 期望 |
|---|---|---|
| C1 | 完整 happy path：mp 首页 → 拼豆 tab → 体验选座 → select 三步选完 → confirm 手机号（已绑）→ submit → success 核销码 | 全段 ✅，无 500，无 console 红错 | ⬜ |

---

## 3. 不在此处测的（B 方案 — 已被 AI 覆盖）

| 范围 | 谁覆盖 | 在哪看 |
|---|---|---|
| **BEAN-001** 门店主数据 / R1 多租户 hotfix | kevin-qa Playwright + 后端 curl + DB | `reports/GZ-BEAN-001.md` §AI 测试段（含 hotfix 复测） |
| **BEAN-002** 座位 + 时段模板 / 批量配置 / @Log | kevin-qa Playwright + 36 单测 + curl 26 端点 | `reports/GZ-BEAN-002.md` §AI 测试段 |
| **BEAN-003** mp 后端 API（store/seat/slot/availability）/ vitest unit | kevin-qa 后端 curl + mp vitest + 静态结构验证 | `reports/GZ-BEAN-003.md` §AI 测试段 |
| **BEAN-004 ★** 三层防并发兜底 / 50 并发压测 / @Log / admin 核销 API / 75 单测 + 37 vitest | kevin-coder Tier 1A（50 并发压测 raw output） + kevin-qa Tier 1B + revision 复测 | `reports/GZ-BEAN-004.md` §AI 自测 + §AI 测试段 + §revision 段 |
| admin / mp 视觉评判（颜色 / 间距 / 圆角）| **不测**（设计冻结期 6/10-6/14 统一 review）| — |

---

## 4. 判定

- ✅ 全过 → 在底部「判定结果」段标 ✅ → 跑日终 closing（cat reports/*.md → summary + commit + 写 D05/README.md）
- ❌ 有问题 → 在对应 ticket 任务卡 `D04/tickets/<T>.md §revision` 段写「问题 N: 现象 / 期望」 → 喊 `@coder 修 D04/<T> revision 段`

---

## 判定结果（Kevin 填）

| Ticket | 进度 |
|---|---|
| BEAN-003 mp 选座（A1-A6）| ⬜ 待测 |
| BEAN-004 ★ confirm/success/并发（B1-B9）| ⬜ 待测 |
| 跨 ticket 联调（C1 全栈 happy path）| ⬜ 待测 |
| BEAN-001 / BEAN-002 | ✅ 跳过 Tier 2，AI 全 ✅ 已 close |

**最终判定**：⬜ 全 ✅，可日终 closing ｜ ⬜ 有 ❌，待 revision

**Kevin 时间花费**：____ min（B 方案目标 8-12 min，含并发双开）
