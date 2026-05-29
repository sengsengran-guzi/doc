# D02（d1）— Testing-human（Kevin 真机 spot check）

> **B 方案 2026-05-28**：admin + 后端 + 单测全部 AI 接管（Tier 1A coder + Tier 1B kevin-qa）。本文件只列 **Kevin 要点的具体动作** — mp 端真机 + 微信原生能力 + 产品 sense。
>
> **本日 Tier 2 范围**：SYS-002 + SYS-004（mp ticket）。SYS-003 / SYS-005 是纯 admin/be，跳过 Tier 2 — AI 全 ✅ 即 close。
>
> **预计时间**：5-10 min

---

## 0. 启动前 check

| # | 检查项 | 命令 / 操作 | 状态 |
|---|---|---|---|
| 0.1 | docker 三容器 | `docker ps \| grep sensenran-dev` 看到 mysql/redis/minio 全 Up | ✅ Up 34h |
| 0.2 | 后端 8080 | `lsof -i:8080 -sTCP:LISTEN` 看到 java | ✅ pid 53525（revision 后重启） |
| 0.3 | mp dev | `cd code/main/miniapp && pnpm dev:mp-weixin` 后等 "DONE Build complete" | ⬜ 自查 |
| 0.4 | 微信开发者工具 | 已导入 `code/main/miniapp/dist/dev/mp-weixin` | ⬜ 自查 |

---

## 1. 测试清单（表格驱动，逐行勾选）

### 1.1 GZ-SYS-002 — 微信登录链路 ⭐ 主流程

**入口路径**：首页底部橙色虚线框 → 点 "→ 微信登录页（SYS-002）" 按钮（临时入口，5 tab 建好后会被 GZ-ADMIN-005 清掉）

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| A1 | 微信开发者工具 → 首页 → 看橙色虚线框 "🧪 d1 Tier 2 测试入口" | 看到框 + "→ 微信登录页（SYS-002）" 按钮 | ⬜ |
| A2 | 点按钮 → 跳 `pages/login/index` | 进入登录页 + 顶 navbar 显示"登录" + 看到 "微信一键登录" 按钮 + 主色 #FF6B81 | ⬜ |
| A3 | 点 "微信一键登录" → 触发 `wx.getUserProfile` | 弹出微信原生授权弹窗（头像 / 昵称 / "允许" / "拒绝"） | ⬜ |
| A4 | 授权框点 "允许" | toast "登录成功" + 自动跳首页 + storage 有 TOKEN | ⬜ |
| A5 | DEVTOOLS Console 输 `uni.getStorageSync('TOKEN')` | 返非空字符串（token） | ⬜ |
| A6 | DEVTOOLS Console 输 `uni.getStorageSync('USER_INFO')` 或 store debug | 看到 nickName / avatarUrl（来自微信授权） | ⬜ |
| A7 | 在首页/我的页验证头像回填 | 显示真实微信头像（非默认占位图） | ⬜ |
| A8 | **拒授权 fallback**：清缓存 → 重进 login → 点登录 → **拒绝**授权 | toast "已切换为仅浏览模式" + 跳首页 + token 仍写入（fallback nickName="微信用户"） | ⬜ |
| A9 | **二次登录幂等**：保留 token → 重新点登录按钮 | 不报错 + DB 中同 openid 用户 `last_login_time` 刷新（命令行验：`docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT id, openid, nickname, last_login_time FROM gz_user ORDER BY id DESC LIMIT 3;"`） | ⬜ |
| A10 | **已登录态自动跳转**：保留登录态 → 重进 `pages/login/index` | onLoad 检测到 isLoggedIn=true → 立即 reLaunch 到首页（不停留登录页） | ⬜ |

---

### 1.2 GZ-SYS-004 — 客服浮层

**入口路径**：任意页面（7 个 page 都挂了浮层）

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| B1 | 首页 / login / 任意 page | 右下角💬浮层可见 + 不遮挡内容 + 圆形红/品牌色 | ⬜ |
| B2 | 浮层位置（首页）| 离屏底 ~132rpx，避开未来的 tab 栏区域 | ⬜ |
| B3 | 点浮层（`wx_kf_id` 当前空 — 走降级路径）| 弹 `uni.showModal` "暂未配置客服" / 显示"客服电话 - / 客服微信号 -"（dev 默认空字段，文案应优雅，不显示 undefined） | ⬜ |
| B4 | admin 端 superadmin 进「系统管理 → 客服配置」改 `wx_kf_id=ww_test123` + `phone=028-12345` + `wx_id=cs_kefu` → 保存 | DB 落库（命令行验：`mysql -e "SELECT * FROM sys_config WHERE config_key LIKE 'gz.customer_service%';"`） | ⬜ |
| B5 | mp 端等 ≤5min（pinia store TTL）或强制刷新（清 storage）→ 再点浮层 | 弹窗显示新值（phone + wx_id 已回填）+ 长按支持复制 | ⬜ |
| B6 | mp 端**匿名用户**（清 token）→ 进任意 page → 浮层可见 | 浮层正常显示（不触发 401 跳登录页 — SYS-004 修过这个 bug） | ⬜ |

---

## 2. 跨 ticket 联调（如有）

| # | 链路 | 期望 |
|---|---|---|
| C1 | SYS-002 登录 → SYS-004 浮层在登录页可见 → 退出登录 → 浮层仍可见 | 全段 ✅ | ⬜ |

---

## 3. 不在此处测的（B 方案 — 已被 AI 覆盖）

| 范围 | 谁覆盖 | 在哪看结果 |
|---|---|---|
| 后端单测 / 集成 / curl API | kevin-coder Tier 1A + kevin-qa Tier 1B | `reports/GZ-SYS-002.md` §AI 自测段 + §AI 测试段 |
| admin Playwright E2E（SYS-003 用户列表 / SYS-004 配置页 / SYS-005 文件上传页） | kevin-qa Tier 1B | `reports/GZ-SYS-003.md` / 004 / 005 §AI 测试段 |
| Flyway DDL / Redis 缓存 / MinIO bucket | kevin-coder Tier 1A | 各 reports §AI 自测段 |
| mp vitest unit | kevin-coder Tier 1A 自跑 + kevin-qa 验 | reports §AI 测试段 |
| admin / mp 视觉评判（颜色 / 间距 / 圆角） | **不测**（设计冻结期，6/10-6/14 风格统一时再 review） | — |

---

## 4. 判定

- ✅ **全过** → 在底部「判定结果」段标 ✅ → 告诉主线程跑日终 closing
- ❌ **有问题** → 在对应 ticket 任务卡 `D02/tickets/GZ-XXX.md §revision` 段写"问题 N: 现象 / 期望" → 喊 `@coder 修 D02/GZ-XXX revision 段`

---

## 判定结果（Kevin 填）

| Ticket | 进度 |
|---|---|
| SYS-002 mp 登录（A1-A10） | ⬜ 待测 |
| SYS-004 客服浮层（B1-B6） | ⬜ 待测 |
| C1 跨 ticket 联调 | ⬜ 待测 |

**最终判定**：⬜ 全 ✅，可日终 closing ｜ ⬜ 有 ❌，待 revision

**Kevin 时间花费**：____ min（B 方案目标 5-10 min）
