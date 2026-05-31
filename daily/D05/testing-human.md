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

### GZ-BEAN-010 — mp 拼豆首页（C 端入口落地页）

**关联 mockup**：design/mockup/home.html / booking-select.html（视觉参考，C 设计系统为准，不逐像素）

**前置**：跑 DDL — `mysql ... ry-vue < .../V202606020020__GZ-BEAN-010-default-banner-config.sql`，重启后端（gz-common 已 install）。

**关联 AC**：
- [ ] AC 1：拼豆 tab → `/pages/bean/index` 落地页（tabBar 已配，无需改 pages.json）
- [ ] AC 2：顶部 banner — 调 `/app/gz/common/config/get?key=gz.bean.home.banner`；无素材 → 占位图 + 默认文案「成都拼豆店开张啦」
- [ ] AC 3：主 CTA「立即预约」朱红大按钮（var(--c-red)，约屏宽 80% block，首屏可见）→ 跳 `/pages/bean/select`
- [ ] AC 4：次级「我的预约」弱按钮 + 右箭头 → 跳 `/pages/bean/my-list`（BEAN-006 上线后可达）
- [ ] AC 5：底部规则卡 3 条文案（取消 / 到店 / 客服）
- [ ] AC 6：未登录守卫（useNavGuard onShow 弹「登录后才能预约拼豆」）；点 CTA 也走 ensureLoggedIn
- [ ] AC 7：i18n 全覆盖 + C 设计系统 token（无硬编码 hex）
- [ ] **AC 8（Tier 2 可达）**：拼豆 tab 即落地页本身（N=0 直达）；「立即预约」N=1 到选座页；「我的预约」N=1 到列表页（BEAN-006 后）

**测试动作**：
1. 微信开发者工具 → 底部 tab 切「拼豆」→ 应看到 banner 占位卡（🧩 + MOCK 水印 + 「成都拼豆店开张啦」）+ 朱红「立即预约」大按钮 + 「我的预约」卡 + 「预约须知」3 条
2. 已登录点「立即预约」→ 跳选座页；点「我的预约」→ 跳列表页（BEAN-006 上线后）
3. 未登录态切「拼豆」tab → 弹登录引导窗（取消跳首页）
4. 视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红 CTA / 网点 / 报头风），不逐像素

**判定**：
- ✅ OK → progress.md 标 ✅
- ❌ NOT OK → `tickets/GZ-BEAN-010.md` 的 `§revision` 段写"问题 N: 现象 / 期望"

---

### GZ-BEAN-005 — mp 预约详情 + 核销码 QR 大图

**入口**：拼豆 tab → 我的预约 → 卡片点入；或提交成功页「查看预约详情」CTA。

- [ ] 详情布局：门店名+地址 → 日期时段 → 座位号 → QR 大图（约屏宽 70%）→ 状态 tag → 底部 CTA
- [ ] **QR 真机可扫**：用微信「扫一扫」扫详情页 QR，payload 形如 `BK|<bookingNo>|<verifyCode>`（关键 — 这是 BEAN-008 店员核销的输入）
- [ ] 4 状态视觉：pending QR 彩色 + 朱红 tag + 显示「取消预约」按钮；used QR 灰显 + 绿「已核销」；cancelled / no_show QR 灰显 + 灰状态字，无取消按钮
- [ ] 低端机若 QR 渲染失败 → 兜底显示核销码文本（不白屏）
- [ ] 视觉遵循 C 设计系统

### GZ-BEAN-006 — mp 我的预约列表（4 状态 tab）

**入口**：拼豆 tab → 「我的预约」。

- [ ] 顶部 4 tab（待核销 / 已核销 / 已取消 / 已过期），默认「待核销」，选中态朱红
- [ ] 卡片：门店名 + 日期时段 + 座位 + 状态 tag + 静态缩略 icon（非真 QR）；按时间倒序
- [ ] pending tab 卡片右下角有「取消」按钮；其他 3 tab 无
- [ ] 卡片点击 → 跳详情页（BEAN-005）
- [ ] 空状态：当前 tab 无数据 → 插画 + 「立即预约」CTA → 拼豆首页
- [ ] nav-bar「+ 新建」→ 跳拼豆首页 / 选座

### GZ-BEAN-007 — mp 取消预约（二次确认）

**入口**：详情页「取消预约」或列表 pending 卡片「取消」。

- [ ] 点取消 → 弹二次确认（uni.showModal「确定取消？座位将释放给他人」）
- [ ] 确认 → toast「取消成功」→ 详情页状态变 cancelled + QR 灰显 + 取消按钮消失；列表卡片移到「已取消」tab
- [ ] 点「再想想」→ 不取消，状态不变
- [ ] 对已 used / no_show 的预约取消 → toast「已核销/已过期，不可取消」（终态拒绝）
- [ ] 连点取消按钮 → 防重复（不重复弹窗 / 不重复请求）

---

## 1.5 ⭐ 端到端闭环（D05 核心 — 必跑一次，跨 mp + admin + DB）

> README §今日特殊约束：本日必须把"用户提交 → 用户看码 → 店员扫码核销 → 标 used"端到端跑通。D04 只验到"提交成功"，本日验全闭环。

**前置**：两条 DDL 已手工导入（banner + 状态字典），后端 + plus-ui + 微信开发者工具全起，至少一个绑定门店的 staff/owner admin 账号。

1. **mp 用户提交**：拼豆 tab → 立即预约 → 选日期/时段/座位 → 提交 → 成功
2. **mp 用户看码**：进我的预约（待核销 tab）→ 点入详情 → 看到彩色 QR 大图
3. **admin 店员核销（扫码）**：plus-ui → 谷子业务/拼豆预约/预约管理 → 列表能看到这条 pending（按门店/日期/状态筛）→ 点「扫码核销」→ 上传刚才详情页 QR 截图 → 解析 + 校签通过 → 状态变 **used**，操作日志记一条
4. **mp 回看**：用户刷新详情 → 状态变「已核销」+ QR 灰显；列表卡片移到「已核销」tab
5. **竞态/终态校验**：再扫同一张已 used 的码 → admin 报「该预约已核销」；对已取消的预约扫码 → 报「该预约已取消」
6. **手动核销旁路**：另起一条 pending → admin 列表选中 → 点「核销」→ 二次确认 → 变 used（与扫码同底层）
7. **no_show cron**（可选，需 SnailJob 控制台已注册 gzBeanNoShowMarkTask）：构造一条昨日 pending → 控制台「执行一次」→ 该条变 no_show + booking_log 记 system 操作

**判定**：闭环任一环断 → 在对应 ticket `§revision` 写「问题 N: 现象 / 期望」。

---

## 2. 跨 ticket 联调（如有）

如果今日 ticket 之间有协作（如 GZ-SYS-001 微信登录 → GZ-USER-001 个人资料读取），单独跑一次：

1. 微信登录走通
2. 进入个人资料页 → 数据显示
3. 退出登录 → 再进入 → 应跳登录页

---

## 3. 视觉 / 文案 review（C 设计系统遵循度）

- mp 视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红主色 var(--c-red) / 网点 / 报头风），以 doc/tokens.md + doc/13 为准，不纠结逐像素；admin 不评判视觉
- emoji 没乱用 ✅ / 滥用
- 中文文案没机翻味 ✅ / 像 GPT 风

---

## 4. 性能 sense（主观感受）

- 小程序首页打开秒开？✅ / 卡
- API 响应 < 1s？✅ / 慢（哪个接口）
- DB 数据量级符合预期？✅ / 异常（如本该 10 条结果出来 1000 条）
