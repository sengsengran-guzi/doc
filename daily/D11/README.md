# D11 — V1.2 快赢 + 拼豆地基 + 资料/登录态地基

> 阶段：V1.2 调整批次实施期（D11-D14 封顶；不绑日历日，按依赖顺序推进）
> 主题：**快赢（预购下线，屏蔽入口保留代码）+ 拼豆座位类型配额地基（推倒 A1-A10）+ 资料/登录态地基（gz_user 微信号 + chooseAvatar/nickname 持久化 + sa-token 长效续期）**
> 上一日：D10（V1.1 订单聚合 USER-101~104 + admin 三件套 ADMIN-101/102/103 + mp 订单查看下沉 ADMIN-201）｜ 下一日：D12（拼豆付费核心 GZ-BEAN-014 + 优惠券地基 GZ-COUPON-001）

---

## 今日目标

V1.2 调整批次第一日。**4 个 ticket 全并行，互不依赖**——都是「快赢 + 地基」，不碰下游付费/优惠券/回收链路（扭蛋本批仅降开发优先级，入口迁移 + 做活回归排 D14 最后 GZ-GACHA-111，**本日无扭蛋任务**）：

- **快赢（预购下线）**：GZ-ORD-110 屏蔽预购 admin + mp 双端入口，`ruoyi-gz-ord` 代码 + `gz_ord_*` 表 + plus-ui 预购视图**全部保留**（仅 `sys_menu.visible` 置 0 + mp 首页/聚合卡隐藏入口），随时可恢复。**勿误藏扭蛋订单**（扭蛋 V1.2 保留做活）。
- **用户字段（微信号）**：GZ-USER-005 `gz_user` ALTER 加 `wechat_id VARCHAR(64) NULL`（**手动填，非 API**）+ mp 资料页（GZ-USER-002）加录入框 + i18n。为下游 GZ-BEAN-015 付款前采集预填。
- **资料完善 + 登录态地基**：GZ-USER-006 mp 资料页头像区改 `chooseAvatar` 按钮 + 昵称 `<input type="nickname">` 一次性采集**持久化**（头像上传 COS 存 `avatar_image_id` + 昵称存 `gz_user.nickname`，getUserProfile 已废弃）+ 登录态 = sa-token 长效 + mp 启动**静默 wx.login 续期**（不踢用户）。必读 **ADR-0009**。
- **拼豆地基（推倒 A1-A10）**：GZ-BEAN-013 新建 `gz_bean_seat_type_config`（门店 × 座位类型 → 数量 + 单价，**quantity 即余量基础**）+ 字典 `gz_bean_seat_type`（single/double/quad）+ admin 座位配置页改为「配类型数量 + 单价」（替换原 A1-A10 座位图）+ 标注废弃 `gz_bean_seat` 预约用途（表保留不 DROP）。**单笔单时段模型，无子表**。

完工后：
- 用户在 mp 已看不到预购入口（首页卡 + 聚合 tab 残留入口清零），但代码/表/数据原封不动可恢复
- 用户在 mp「我的-个人资料」可主动录入/编辑微信号（手动填，可空）
- 用户在 mp「我的-个人资料」用 chooseAvatar 选头像 + 填昵称并持久化（再进回显，不重复采集）；长时间不开也不被踢登录（token 静默续期）
- 甲方在 admin 拼豆配置页按门店配「单人/双人/四人桌」各几个 + 单价（不再画 A1-A10 座位图）

## Ticket 清单（4 个，全并行 — 无依赖）

| Ticket | 标题 | 端 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| GZ-ORD-110 | 预购下线（屏蔽 admin + mp 入口，保留代码/表/视图） | admin + be + mp | S | 无（GZ-ORD-104 / ADMIN-103 已交付） | pending |
| GZ-USER-005 | gz_user.wechat_id 字段 + mp 资料页录入 | be + admin + mp | S | 无（GZ-USER-002 已交付） | pending |
| GZ-USER-006 | 微信资料完善（chooseAvatar+nickname 持久化）+ 登录态保持 | be + mp | M | 无（GZ-USER-002 + GZ-SYS-005 + 登录链路已交付） | pending |
| GZ-BEAN-013 | 座位类型配额配置（admin 配数量/单价 + 废弃 A1-A10） | be + admin | M | 无（GZ-BEAN-001/002 已交付） | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图**：

```
GZ-ORD-110     ┐
GZ-USER-005    │
GZ-USER-006    ├─ 全并行，互不依赖（4 条线同时 spawn 各自 Tier 1A）
GZ-BEAN-013    ┘
```

下游衔接（仅说明，不在本日）：
- GZ-USER-005（wechat_id）→ D12 GZ-BEAN-014 付费列 / D13 GZ-BEAN-015 付款前采集预填
- GZ-USER-006（资料持久化 + 登录态）→ 全局受益（拼豆/回收付款前采集复用已持久化头像昵称；sa-token 长效登录态贯穿 V1.2 各 mp 流，ADR-0009）
- GZ-BEAN-013（类型配额 config + 字典）→ D12 GZ-BEAN-014 按 booking 计数防超卖（vs `quantity`）+ 余量查询接口 → D13 GZ-BEAN-015 mp 选类型显余量下单（单笔单时段）

## 派单方式

```
开始 d11                          # 主线程读本 README，按依赖图自动跑（4 条全并行）
开始 d11/GZ-USER-005              # 单 ticket 启动
@coder 做 D11/GZ-ORD-110          # 显式分派（4 个可同时 spawn，互不依赖）
@coder 做 D11/GZ-USER-005
@coder 做 D11/GZ-USER-006
@coder 做 D11/GZ-BEAN-013
```

主线程动作：
1. 读 D11/README.md + 依赖图
2. **§0 自检先 grep migration 目录**（见下「与昨日 reports 对账」），确认 `gz_user` / `gz_bean_seat` / `gz_bean_booking` / `gz_ord_*` 表的迁移文件实际存在 + `gz_file_object`（GZ-USER-006 头像存 COS 依赖）+ 微信登录链路类在位，缺则 STOP 报 Kevin
3. **一次性并行 spawn 4 条 kevin-coder 线**（GZ-ORD-110 / GZ-USER-005 / GZ-USER-006 / GZ-BEAN-013 互不依赖，各自跑 Tier 1A 自测）
4. 4 条全完工 → **一个 kevin-qa 串行整批 Tier 1B**（admin Playwright E2E + 后端集成 + mp vitest unit + mp 可达性检查）
5. 4 ticket 全 Tier 1A + 1B ✅ → mp ticket（GZ-ORD-110「入口消失」验证 / GZ-USER-005 资料页录入 / GZ-USER-006 头像昵称持久化 + 登录态续期）进 progress.md「人验」列；纯 admin（GZ-BEAN-013）AI ✅ 即终态

---

## 今日特殊约束

### 0. V1.2 批次背景 — 不绑日历日 + V1.0/V1.1 现状

- **本日不绑日历日**。V1.2 调整批次（D11-D14）软期限，按依赖顺序推进。
- **V1.0/V1.1 现状 = 「已通过 AI 测试，但未客户验收、未上线」**（不是「已上线运行」）。GZ-ORD-110 屏蔽预购入口、GZ-BEAN-013 废弃 A1-A10 座位都是在**未上线基线**上做调整，无线上数据迁移风险（旧 booking 数据迁移在 D12 GZ-BEAN-014 内做）。
- **§0 自检改为 grep migration 目录实际存在的表**，不假设上游 ticket 已 merge。

### 1. GZ-ORD-110 屏蔽口径 = 仅入口不可见，代码/表/视图全保留 ⚠️ 勿误藏扭蛋

- **admin 侧**：`UPDATE sys_menu SET visible='0'`，**仅**预购相关菜单（9110-9112 预购业务 + 11007-11009 订单聚合 admin 中的 **preorder 项**）。
- ⚠️ **一票否决**：订单聚合 admin（11007-11009）下有预购 + 扭蛋两类，**只藏 preorder 项，绝不藏扭蛋（gacha）项**。扭蛋 V1.2 保留做活（GZ-GACHA-111 入口迁「我的」+ 做活回归，D14 最后），其 admin 入口必须仍 `visible='1'`。改 menu 前先 `SELECT menu_id, menu_name, visible FROM sys_menu WHERE menu_id IN (9110,9111,9112,11007,11008,11009)` 逐行确认哪个是 preorder。
- **mp 侧**：首页预购卡隐藏（GZ-SYS-010 tabbar 重构后首页会下线，本卡此处确保**无残留预购入口**）；聚合「我的订单」若有预购 tab/入口同步隐藏（不删 pages/ord 代码）。
- **代码/表/数据全留**：`ruoyi-gz-ord` 模块代码、`gz_ord_*` 表、plus-ui `views/gz-ord/*` 视图、mp `pages/ord/*` **一律保留不删**，仅入口不暴露，随时可恢复。
- 迁移文件**只 UPDATE menu visible**（不 DROP 表、不删 menu 行）：`V<时间戳>__GZ-ORD-110-hide-preorder-entry.sql`。

### 2. GZ-USER-006 微信资料持久化 + 登录态续期（ADR-0009 必读）⚠️

- **必读 ADR-0009**（微信资料采集 + 登录态保持）：① 头像昵称用 `chooseAvatar` 按钮 + `<input type="nickname">` 一次性采集**持久化**（`getUserProfile` 已被微信废弃，**禁止使用**）；② 头像临时路径**上传 COS 存 `avatar_image_id`**（FK gz_file_object，**不存裸 url**），昵称存 `gz_user.nickname`；③ 登录态 = sa-token 长效 token + mp 启动 / 401 时**静默 `wx.login → code2session` 续期**（openid 静默可得，不弹授权、不踢用户）。
- **getUserProfile 禁用硬约束**：代码中不得出现 `wx.getUserProfile` / `getUserInfo` 一键授权（§0 自检 / QA 打回项）；头像只能 chooseAvatar、昵称只能 nickname input。
- **同页复用**：与 GZ-USER-005（微信号录入）同在 GZ-USER-002 资料页（`pages/me/profile`）加，复用同一「保存资料」+ 同一 profile 接口，**不新建资料页 / 不新建 profile 接口**，仅扩字段 + 改头像采集方式。
- **登录态不踢用户**：token 失效走静默续期，只有 openid 都拿不到 / 用户主动退出才回登录页；reports 验 token 过期 → 静默续签新 token 不返 401。

### 3. GZ-USER-005 wechat_id 手动填，非微信 API ⚠️

- **微信不开放 API 查微信号**（doc/11 §2.1 已注）——`wechat_id` 只能**用户手动填**，绝不调任何微信接口去「自动获取微信号」。
- 字段：`gz_user.wechat_id VARCHAR(64) NULL`，可空，无 UNIQUE（一个微信号可被多人填，不做去重）。
- mp 资料页（GZ-USER-002 已建，`pages/me/profile`）加一个普通文本输入框（`<input>` / Biz 表单项），placeholder「请输入微信号，便于门店联系」；走 `PUT /api/user/profile` 已有更新接口扩字段，不新建接口。
- 拼豆付款前采集（D13 GZ-BEAN-015）会读 `gz_user.wechat_id` 预填；本卡只做「存 + 编辑」，不碰拼豆流。

### 4. GZ-BEAN-013 推倒 A1-A10 = 类型配额模型（ADR-0008 必读）⚠️

- **必读 ADR-0008**（座位类型配额模型）：① 废弃 `gz_bean_seat`（A1-A10）用于预约——**表物理保留不 DROP，逻辑停用**；② 新建 `gz_bean_seat_type_config`（门店 × 类型 → 数量 + 单价）；③ admin 座位配置页从「画 A1-A10 座位图」**简化为「配每类型数量 + 单价」**。
- **`gz_bean_seat_type_config` 字段**（严格对齐 doc/11 §3.4）：`store_id` / `seat_type`（VARCHAR(16)，字典 `gz_bean_seat_type`：`single`/`double`/`quad`）/ `quantity`（INT，配额上限）/ `price_cent`（BIGINT，单价分）/ `enabled` / `UNIQUE(tenant_id, store_id, seat_type)`。
- **字典 seed**：`gz_bean_seat_type`（single 单人 / double 双人 / quad 四人桌；可扩展），随本卡 Flyway seed（doc/11 附录 A.14 + §10.2）。
- **废弃标注**：admin 原 A1-A10 座位图配置入口（AD-BEAN-CONFIG 的座位段）下线/隐藏；`gz_bean_seat` 表保留不 DROP；**禁止**本卡或后续新代码再 INSERT/依赖 `gz_bean_seat` 做预约分配（§0 自检 / QA 打回项）。
- **本卡只做地基（config + 字典 + admin 配置页）**：`gz_bean_booking` 付费列 + seat_type ALTER、按 booking 计数防超卖、余量查询接口、旧数据迁移都在 **D12 GZ-BEAN-014**（依赖本卡）。**单笔单时段，无 `gz_bean_booking_unit` 子表**（ADR-0007/0008，一笔预约 = 一行 booking；多类型/多时段 = 多次预约）。本卡 menu **复用 6000 GZ-BEAN 段**（不新开段；seed 前 `SELECT MAX(menu_id) FROM sys_menu WHERE menu_id BETWEEN 6000 AND 6999` 确认不冲突）。

### 5. 迁移文件命名 + 字段硬约束（每张卡复核）

- **迁移文件命名** `V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`，放 `ruoyi-admin/src/main/resources/db/migration/`。**当前最大时间戳 = `V202606190200`**（D10 GZ-USER-104）；本日新迁移**用 `V2026061906xx+` 段**（> 当前最大；已应用迁移文件不可改，改 schema 一律新建更大时间戳，CLAUDE.md §5/§6 #5）。
- **金额一律 `_cent`（分）**，不用 `_fen`（`gz_bean_seat_type_config.price_cent`）。
- **`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`**；INSERT 不显式赋 tenant_id（走 `InjectionMetaObjectHandler` 自动填充，CLAUDE.md §6 #2/#3）；**UNIQUE 约束必含 tenant_id**（`gz_bean_seat_type_config` 的 `(tenant_id, store_id, seat_type)`）。
- **字典走 sys_dict**（`gz_bean_seat_type` 用 `sys_dict_type` + `sys_dict_data` seed，不写死枚举常量）。
- **`del_flag` 仅 2 值**（0 正常 / 2 删除）对齐 ruoyi `@TableLogic`，不用 3 值。
- **包名 `org.dromara.gz.<域>.{controller,service,mapper,domain,dto}`**（bean → `org.dromara.gz.bean.*`；user → `org.dromara.gz.user.*`）。
- **不动 ruoyi 自带模块源码**（CLAUDE.md §6 #1）。

### 6. 设计约定

- **admin（GZ-ORD-110 部分 / GZ-BEAN-013）**：ruoyi/Element Plus 默认审美 + plus-ui BizTable，**不引用 mockup 像素**，不调样式（admin 不评判视觉，设计冻结期）。
- **mp（GZ-ORD-110 入口隐藏 / GZ-USER-005 资料页录入框 / GZ-USER-006 chooseAvatar 头像区 + 昵称 input）**：视觉走 C 日漫海报浓墨——只用 `src/components/biz/Biz*` 原子组件 + `var(--c-*)` token，**不直接撒 `<wd-*>` 标签**（CLAUDE.md §7.5）；doc/tokens.md + doc/13 为准，旧 mockup 仅布局参考，不逐像素。

---

## 与昨日 reports 对账（D10）

D10 已交付（**主线程 §0 自检 grep migration 目录实际验证，不假设**）：
- GZ-USER-101~104（订单聚合 + mp 订单详情/物流/收货）+ ADMIN-101/102/103（预购商品 CRUD / 扭蛋池管理 / 订单管理三类聚合）+ ADMIN-201（mp 店员端订单查看下沉）
- 表：`gz_ord_order` / `gz_gacha_order`（含物流字段）/ `gz_pay_transaction` / `gz_logistics_audit`；菜单 9100 段（ORD admin）/ 10100 段（GACHA pool）/ 11007-11009（订单聚合 admin）

进 D11 前主线程 §0 自检校验：
```bash
cd code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration
# 本日 4 ticket 改动锚点表是否齐：
grep -rl 'gz_user'              . | head   # GZ-USER-005/006 ALTER 锚点（gz_user 已由 GZ-SYS/USER 早期建）
grep -rl 'gz_file_object'       . | head   # GZ-USER-006 头像存 COS 锚点（avatar_image_id FK gz_file_object，由 GZ-SYS-005 建）
grep -rl 'gz_bean_seat\b'       . | head   # GZ-BEAN-013 废弃锚点（gz_bean_seat 由 GZ-BEAN-002 建）
grep -rl 'gz_bean_booking'      . | head   # GZ-BEAN-013 关联（付费列在 D12，本卡不动）
# GZ-USER-006 登录态续期锚点（微信登录链路类，非迁移）：
grep -rl 'wx.login\|code2session\|jscode2session' ../../../../../ruoyi-modules 2>/dev/null | head
# preorder 菜单实际 menu_id 确认（GZ-ORD-110 改 visible 前对照）：
ls | grep -E 'GZ-ORD-101-menu|GZ-ADMIN-103-menu'
```
对应表 + 菜单存在 → 开工；缺则 STOP 报 Kevin（回 D10 收尾，本日不开工）。

D10 summary.md「对 D11 的债 / 源头 doc 回填」段（统一订单 VO 下沉 gz-common / C 端鉴权口径回填 / 跨模块循环依赖纪律）属 D15 收官债，**不影响 D11 本日 4 ticket**（无一碰订单聚合 service），仅记录在册。

---

## 完成判定（DoD）

- [ ] 4 个 ticket 任务卡 §revision 段空（GZ-ORD-110 / GZ-USER-005 / GZ-USER-006 / GZ-BEAN-013）
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 grep migration raw output + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] GZ-USER-006 reports 附：chooseAvatar 头像上传 COS → avatar_image_id 落库 + 昵称落库 raw output + token 过期 → 静默续期签发新 token（不返 401）raw output；**确认无 getUserProfile 调用**
- [ ] mvn install（ruoyi-gz-user / bean / ord / common -am）+ plus-ui build:prod + miniapp build:mp-weixin 三端全绿
- [ ] GZ-ORD-110 改 menu visible 前已 `SELECT` 逐行确认 preorder vs gacha（**未误藏扭蛋项**，raw output 入 reports）
- [ ] GZ-BEAN-013 `gz_bean_seat_type_config` 表 + `gz_bean_seat_type` 字典 seed 落地（`DESC` + `SELECT dict_label,dict_value` raw output 入 reports）；`gz_bean_seat` 标废弃注释入 reports；**确认无 `gz_bean_booking_unit` 子表**（单笔单时段）
- [ ] GZ-USER-005 `gz_user.wechat_id` ALTER 落地（`DESC gz_user | grep wechat_id` raw output）；mp 资料页录入框可见可存
- [ ] Tier 1A + 1B（kevin-coder 自测 + kevin-qa：admin Playwright E2E + 后端集成 + mp vitest unit + mp 可达性检查）全 ✅
  - 纯 admin（GZ-BEAN-013）AI ✅ 即终态，无人验
  - mp（GZ-ORD-110 入口消失 / GZ-USER-005 资料页录入 / GZ-USER-006 头像昵称持久化 + 登录态续期）进 progress.md「人验」列待 Kevin 批量验
- [ ] testing-human.md 预填（mp 可达路径）：
  - GZ-ORD-110：mp 首页 / 我的订单 → **确认看不到任何预购入口**（入口消失验证）
  - GZ-USER-005：mp「我的」→「个人资料」→ 录入微信号 → 保存 → 重进资料页回显
  - GZ-USER-006：mp「我的」→「个人资料」→ chooseAvatar 选头像 + 填昵称 → 保存 → 重进回显；长时间后重进**不弹重新登录**

---

## 日终 closing 命令

```bash
cd doc/daily/D11
cat reports/*.md > summary.md
git add -A && git commit -m "D11: V1.2 快赢+地基 — 预购下线 GZ-ORD-110 + gz_user.wechat_id GZ-USER-005 + 微信资料完善/登录态 GZ-USER-006 + 拼豆座位类型配额 GZ-BEAN-013"
# 然后写 D12/README.md（拼豆付费核心 GZ-BEAN-014 ←013 + 优惠券地基 GZ-COUPON-001，参 ADR-0007/0008 + doc/11 §3/§11）
```
