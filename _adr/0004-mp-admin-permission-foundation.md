# ADR-0004 小程序管理端能力的权限底座（C 端 openid 绑定 sys_user，复用 ruoyi RBAC）

- 日期：2026-06-01
- 状态：**Accepted**
- 决策人：Kevin（三点决策已拍板，见文末。实现交 kevin-coder，落地批次 D7x）
- 关联：拼豆核销 GZ-BEAN-008（现仅 admin）/ GZ-SYS-002 微信登录 / 后续 mp 管理端功能 / 落地 D7x

---

## 背景

拼豆核销（GZ-BEAN-008）目前只挂在 admin 网页（`GzBeanBookingController` 的 `/{id}/verify` + `/verify-scan`，`@SaCheckPermission("gz:bean:booking:verify")`，授 owner+staff）。但门店实操里店员在店里、手上是手机/微信，几乎不会去开后台网页扫码核销——GZ-BEAN-008 自己也写了「店员用微信扫预约码」，扫码本该在小程序，却被塞进了 admin，是设计内部矛盾。

Kevin 判断：后续会有较多管理端功能要在小程序落地（核销只是第一个），值得**提前把权限底座做对**，而不是给核销打个一次性白名单补丁。

**关键现状（鉴权模型）**：
- mp 微信登录（`WxLoginServiceImpl`）建 `LoginUser` + `UserType.APP_USER`，deviceType=mp，userId=gz_user.id，**不带任何 ruoyi 角色/权限**。
- admin 是 `SYS_USER`，带完整 ruoyi RBAC（角色/菜单/权限，`@SaCheckPermission` 生效）。
- 两者共用同一 sa-token（`StpUtil`/`LoginHelper`），靠 `userType` 区分。
- `gz_user` 目前**无任何店员/角色字段**；`gz:bean:booking:verify` 已正确授给 role 100(owner)+101(staff)。
- 店员 sys_user 已 seed：`gz_owner`(100)、`gz_staff_chengdu`(101)，均租户 1001。

矛盾本质：mp 的 app_user token 身上没有 `gz:bean:booking:verify`，无法直接复用 admin 的核销端点。

## 决策

### 1. 底座方案：openid 绑定 sys_user + 登录时加载其 ruoyi 权限（推荐，替代「平行 RBAC」）

**不在 gz_user 上另造一套角色/权限系统**，而是：

1. **绑定关系**：把一个 C 端微信用户（gz_user.openid）绑定到一个 ruoyi 店员账号（sys_user，如 gz_staff_chengdu）。
   - V1.0：gz_user 加一列 `staff_user_id BIGINT NULL`（指向 sys_user.user_id；NULL=纯顾客）。1:1 够用。
2. **登录时加载权限**：mp wx-login 建 app_user LoginUser 后，若该 openid 已绑定 → 把绑定 sys_user 的角色 + 菜单权限集合载入这个 LoginUser（ruoyi LoginUser 本就有 rolePermission/menuPermission 字段）。
3. **端点零新增鉴权代码**：mp 管理端端点直接用标准 `@SaCheckPermission("gz:xxx:yyy")`——和 admin 端**同一个权限 key、同一套 RBAC**。

**为什么这是"做对的底座"**：
- **权限单一真源 = ruoyi RBAC**。在 admin「系统管理→角色/菜单」给店员分 `gz:bean:booking:verify`，mp 端自动生效，不维护第二套。
- **可线性扩展**：后续每个 mp 管理端功能（订单管理/物流推进/资讯发布…）只需加一行 `@SaCheckPermission` + 复用其已有权限 key，**零新增鉴权基建**。正是 Kevin 要的"提前把底座做好"。
- **店员单一身份**：店员用自己的微信，既是顾客又是店员；绑定即解锁店员能力，不需要第二个账号体系。

**被否方案（平行 RBAC）**：给 gz_user 加自己的角色/权限表。否决理由：与 admin RBAC 双源、双份维护、必然漂移；只有在"mp 管理功能永不与 admin 重叠"时才更简单——但核销已经重叠，未来更会。

### 2. 首个功能：mp 扫码核销（复用后端，仅加壳）

- 新 mp 端点 `POST /app/gz/bean/booking/verify-scan`，`@SaCheckPermission("gz:bean:booking:verify")`，**复用现有** `GzBeanBookingServiceImpl` 核销逻辑 + `QrCodeSigner` 验签。后端几乎零新逻辑。
- mp 个人中心：LoginUser 带店员权限时，显示「核销」入口 → 扫码页 `wx.scanCode`（原生、真机可用）→ 拿 `"BK\|{bookingNo}\|{verifyCode}"` → POST 核销。
- admin 网页保留**手动核销（按预约号）**作兜底（owner 远程查/扫码失败时）。

### 3. 范围切分（Kevin 定调：D7x 内完整闭环，零 V1.1 推诿）

**D7x 必须交付一个完整可用的闭环**（不许半成品推 V1.1）：

| # | 内容 | 落地 ticket |
|---|---|---|
| ① | gz_user.staff_user_id 列 + mp 登录加载绑定 sys_user 权限 | GZ-SYS-007 AC1-7 ✅ |
| ② | mp 核销端点（复用 verify）+ wx.scanCode 扫码页 + 个人中心条件入口 | GZ-BEAN-011 ✅ |
| ③ | 顾客核销码渲染成真二维码（被扫端，接 @uqrcode/js）—— 否则核销真机不可扫 | GZ-BEAN-012 |
| ④ | 停用 sys_user **自动**踢 mp token（不只手动端点）—— 安全红线完整 | GZ-SYS-007 AC9 |
| ⑤ | owner admin 自助绑定/解绑店员 —— 客户不靠 dev 跑 SQL 即可运营 | GZ-SYS-007 AC10 |
| ⑥ | mp type-check 噪音清零 | GZ-SYS-008 |

**唯一留作真·未来**（非欠债，是新功能）：更多 mp 管理端功能下沉（订单/物流/资讯管理等）。底座已让其边际成本 = 加一行 `@SaCheckPermission` + 在 admin 授权，无需再动底座。

**派发方式**：任务描述已写完整；待 Kevin 测试基本收尾（可能再追加问题），整批派 kevin-coder 实现，不零散派。

## 后果

- ✅ 一套 RBAC、两个端（web + mp），admin 管权限、mp 复用，后续 mp 管理功能边际成本极低（加 `@SaCheckPermission` 即可）。
- ✅ 核销回到最自然的端（mp 原生扫码），解决门店实操摩擦。
- ✅ 不触发合同重谈——核销仍属拼豆非交易免费模块，只是换操作端（区别于"预约收费"那种新业务线）。
- ⚠️ **sa-token 风险（实现重点）**：把 sys_user 权限载入 app_user LoginUser，需 kevin-coder 验证 ruoyi LoginUser/权限装载链路可干净支持；mp token 携带店员权限属安全敏感，**禁用/解绑必须即时失效**（踢 token，不靠下次登录）。
- ⚠️ **绑定鸡生蛋**：要绑 openid 须店员先 wx-login 拿到 gz_user。开发期用"先登一次→手工/seed 绑"；**自助绑定流在 D7x GZ-SYS-007 AC10 内做完**（不推 V1.1）。
- ⚠️ **租户一致**：店员 sys_user 与其 gz_user 须同租户(1001)，绑定/权限加载时校验。
- ⚠️ 净新增功能吃 6/15 buffer：Kevin 已定 **D7x 完整闭环、不挪 V1.1**（含被扫端二维码 + 停用自动踢 + 自助绑定）。若 6/15 期限实在紧张需取舍，再单独 raise，不在 ADR 默认退让。

## 拍板结论（Kevin 2026-06-01）

1. **架构 = 绑定 sys_user + 复用 ruoyi RBAC**（不做平行 RBAC）。
2. **绑定存储 = gz_user 加列 `staff_user_id BIGINT NULL`**（1:1，指向 sys_user.user_id；NULL=纯顾客）。
3. **范围 = 当前批次完整落地**：最小底座 + mp 扫码核销在 **D7x** 集中实现，不挪 V1.1。

落地批次 **D7x**（D1-D7 测试集中修复批次）。实现交 kevin-coder：gz_user 加列迁移 → mp 登录加载绑定 sys_user 权限 → mp 核销端点（复用 verify）→ wx.scanCode 扫码页 + 个人中心条件入口 → seed 绑定 gz_staff_chengdu。安全红线：解绑/禁用即时踢 token。
