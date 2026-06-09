# D11（d11）— Testing-human（Kevin mp 真机批量人验清单）

> admin + 后端 + 单测全部 AI 接管（Tier 1A coder + Tier 1B kevin-qa）。本文件只列 **Kevin 要点的具体动作** — mp 端真机 + 微信原生能力 + 产品 sense。
>
> **本日 mp 人验项**：GZ-ORD-110（预购入口**消失**验证）/ GZ-USER-005（个人资料页录入微信号）/ GZ-USER-006（chooseAvatar 头像 + nickname 昵称持久化 + 登录态续期）。GZ-BEAN-013（纯 admin）**跳过本文件**。coder 每天预填，**Kevin 不必当天测** —— 累计 3-4 天 mp ticket 后集中跑一轮。
>
> **节奏**：不强求每天；本日 3 个 mp 人验项基本无微信原生支付能力（GZ-USER-006 涉 chooseAvatar / 微信登录态续期，属微信能力，建议真机扫一眼），可并入下次批量人验扫掉。

---

## 0. 启动前 check

| # | 检查项 | 命令 / 操作 | 状态 |
|---|---|---|---|
| 0.1 | docker 三容器 | `docker ps \| grep sensenran-dev` 看到 mysql/redis/minio 全 Up（MySQL:3307 / Redis:6380 偏移端口） | ⬜ |
| 0.2 | 后端 8080 | `lsof -i:8080 -sTCP:LISTEN` 看到 java 进程 | ⬜ |
| 0.3 | mp dev 编译 | `cd code/main/miniapp && pnpm dev:mp-weixin` 后等 "DONE Build complete" | ⬜ |
| 0.4 | 微信开发者工具 | 已导入 `code/main/miniapp/dist/dev/mp-weixin` | ⬜ |
| 0.5 | 测试账号 | mp 用普通微信登录用户；如需 admin 核对用 `gz_owner/gz_owner123!`（租户 1001，别用 ruoyi 超管 admin） | ⬜ |

---

## 1. 测试清单（表格驱动，逐行勾选）

### 1.1 GZ-ORD-110 — 预购下线（入口**消失**验证）⭐

> **反向验证**：预购入口应**消失**（非应出现）。这是「确认看不到」的测试，无需临时入口。

**入口路径**（CLAUDE.md §8.3 可达性约束）：从 mp 首页 + 底部 tab「我的」→「我的订单」检查无预购入口
- 当前首页（GZ-SYS-010 tabbar 重构在 D14，本日首页仍在）应无可点击预购卡
- 订单聚合「我的订单」页应无「预购」tab（仅扭蛋 tab）

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| A1 | mp 启动 → 看首页卡片区 | **无**预购入口卡（无跳 pages/ord 的 card/banner） | ⬜ |
| A2 | 底部 tab「我的」→「我的订单」 | 订单 tab 列表**无「预购」tab/筛选项**，仅扭蛋（gacha）tab 在 | ⬜ |
| A3 | 尝试任何残留路径进预购 | 点不到预购商品页 / 预购下单页（入口已隐藏） | ⬜ |
| A4 | （对照）扭蛋入口仍在 | 扭蛋功能 + 订单仍可访问（**保留做活，未被误藏**） | ⬜ |
| A5 | DB 验证（可选） | `docker exec sensenran-dev-mysql mysql -uroot -p... ry-vue -e "SELECT menu_id,menu_name,visible FROM sys_menu WHERE menu_id IN (9110,9111,9112,11007,11008,11009)"` → preorder 项 visible=0，gacha 项 visible=1 | ⬜ |

### 1.2 GZ-USER-005 — 个人资料页录入微信号

**入口路径**（CLAUDE.md §8.3）：从底部 tab「我的」→「个人资料」（GZ-USER-002 已上线页，N=2）→ 微信号录入框
- 业务主线入口已建（资料页 GZ-USER-002），**无临时入口**

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| B1 | 底部 tab「我的」→「个人资料」 | 资料页有**微信号录入框**（placeholder「请输入微信号，便于门店联系」） | ⬜ |
| B2 | 输入微信号 → 点「保存资料」 | toast 保存成功，无报错 | ⬜ |
| B3 | 退出资料页 → 重进 | 微信号**回显**刚填的值 | ⬜ |
| B4 | 清空微信号 → 保存 | 允许保存（可空，不报必填错） | ⬜ |
| B5 | DB 验证（可选） | `... -e "SELECT id,nickname,phone,wechat_id FROM gz_user WHERE id=<当前用户>"` → wechat_id 落库 | ⬜ |
| B6 | 边界：超长输入（>64 字符） | 前端/后端校验拦截（≤64），不报 500 | ⬜ |

### 1.3 GZ-USER-006 — 微信资料完善（chooseAvatar 头像 + nickname 昵称持久化）+ 登录态续期 ⭐

**入口路径**（CLAUDE.md §8.3）：从底部 tab「我的」→「个人资料」（GZ-USER-002 已上线页，N=2）→ 头像区 chooseAvatar 按钮 + 昵称 input
- 业务主线入口已建（资料页 + 登录链路），**无临时入口**
- ⚠️ 涉微信原生能力（chooseAvatar / 登录态续期），建议真机扫一眼

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| C1 | 底部 tab「我的」→「个人资料」→ 点头像区 chooseAvatar 按钮 | 弹微信头像选择（默认头像 / 相册 / 拍照），**不是** getUserProfile 一键授权弹窗 | ⬜ |
| C2 | 选头像 + 在昵称框（`<input type="nickname">`）填昵称 → 保存资料 | toast 保存成功；头像上传成功无报错 | ⬜ |
| C3 | 退出资料页 → 重进 | 头像 + 昵称**回显**刚设的值（不重复弹采集） | ⬜ |
| C4 | DB 验证（可选） | `... -e "SELECT id,nickname,avatar_image_id FROM gz_user WHERE id=<当前用户>"` → nickname + avatar_image_id（**FK gz_file_object，非裸 url**）落库 | ⬜ |
| C5 | 登录态续期：杀小程序进程 → 隔一段时间重开（或本地 token 过期场景） | **不弹重新登录授权**，直接进登录态（静默 wx.login 续期透明） | ⬜ |
| C6 | 头像 url 检查（可选） | 资料页头像走 COS 签名 URL（gz_file_object），非微信临时 wxfile:// 裸路径 | ⬜ |

---

## 2. 跨 ticket 联调（如有）

| # | 链路 | 期望 | 判定 |
|---|---|---|---|
| — | GZ-USER-005（微信号）+ GZ-USER-006（头像昵称）同在「个人资料」页，可一并填一并保存一并回显（同「保存资料」按钮）；ORD-110 入口消失独立，无需联调 | 资料页一次保存微信号+头像+昵称全落库 | ⬜ |

---

## 3. 不在此处测的（已被 AI 覆盖）

| 范围 | 谁覆盖 | 在哪看结果 |
|---|---|---|
| GZ-USER-006 后端 profile 落库 / token 静默续期单测 | kevin-coder Tier 1A + kevin-qa Tier 1B | `reports/GZ-USER-006.md` §AI 自测段（头像昵称落库 + 续期不返 401） |
| GZ-BEAN-013 座位类型配额 config CRUD / admin 配置页 | kevin-qa Playwright E2E | `reports/GZ-BEAN-013.md` §AI 测试段 |
| 后端单测 / 集成 / curl API | kevin-coder Tier 1A + kevin-qa Tier 1B | `reports/<T>.md` §AI 自测段 + §AI 测试段 |
| admin Playwright E2E（菜单可见性 / 配额 CRUD） | kevin-qa Tier 1B | `reports/<T>.md` §AI 测试段 |
| Flyway DDL（gz_user ALTER / seat_type_config 建表 / menu visible） | kevin-coder Tier 1A | reports §AI 自测段 |
| mp vitest unit | kevin-coder Tier 1A + kevin-qa 复测 | reports §AI 测试段 |
| admin / mp 视觉评判（颜色 / 间距 / 圆角） | **不测**（设计冻结期） | — |

---

## 4. 判定

- ✅ **该 ticket 过** → progress.md「人验」列标 ✅（**不 gate 日终 closing**）
- ❌ **有问题** → 在对应 ticket 任务卡 `D11/tickets/<T>.md §revision` 段写"问题 N: 现象 / 期望"（ticket 已 close 也照填）→ 喊 `@coder 修 D11/<T> revision 段`

---

## 跳过判定

| 条件 | 动作 |
|---|---|
| GZ-BEAN-013（纯 admin）Tech 段无 `miniapp/` 路径 | **跳过本文件**对应项，AI Tier 1A + 1B ✅ 即 close |
| 本日 mp 人验项 ORD-110 / USER-005 **无微信原生能力**（不涉支付/登录/客服/扫码/手机号） | 不强求当天真机，可并入下次批量人验扫掉 |
| GZ-USER-006 涉微信原生（chooseAvatar / 登录态续期） | 建议真机扫一眼（C1/C5），其余可并入下次批量人验 |

---

## 判定结果（Kevin 填）

| Ticket | 进度 |
|---|---|
| GZ-ORD-110（A1-A5，入口消失）| ⬜ 待测 |
| GZ-USER-005（B1-B6，资料录入微信号）| ⬜ 待测 |
| GZ-USER-006（C1-C6，头像昵称持久化 + 登录态续期）| ⬜ 待测 |

**本轮批量人验结论**：⬜ 全 ✅ ｜ ⬜ 有 ❌，已回填对应 ticket §revision

**Kevin 时间花费**：____ min（一轮批量人验，扫掉累计的 mp ticket）
