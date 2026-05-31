# GZ-USER-003 — mp 地址簿 CRUD

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M5 §关键字段 § Address + 关键页面 §地址簿
**关联拆解**: doc/02-需求拆解.md §2.4 第 461 行
**关联 mockup**: design/mockup/address-list.html + design/mockup/address-edit.html（仅布局参考；视觉以 C 设计系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-SYS-002 ✅(D02)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§4 会员中心占位流** §地址簿分支（默认唯一规则 / 软删 / V1.1 下单时引用）
- **字段表**：doc/11-字段权威表.md **§2.2 `gz_user_address`**（字段权威 — 完整 DDL 来源）+ §1 全局公共字段
- **UI 参考**（视觉走 C 日漫海报浓墨：页面用 Biz* 组件 + var(--c-*)，见 doc/tokens.md + doc/13；旧 mockup 仅作布局参考，以 c-tokens.scss 的 rpx 为准）：doc/12-UI-权威索引.md **§MP-ME-ADDR-LIST** + **§MP-ME-ADDR-EDIT** + mockup `address-list.html` / `address-edit.html`

## What

落地 `gz_user_address` 表 + CRUD service；mp 端列表 + 新建 + 编辑 + 删除 + 设为默认；默认地址 DB 约束 + 业务层双重保证唯一。V1.0 仅收集数据，V1.1 真实下单时使用。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606031100__GZ-USER-003-create-gz_user_address.sql` 严格按 doc/11 §2.2（含 user_id / receiver_name / receiver_phone / province / city / district / detail / is_default + 全局公共字段）；索引 `idx_user_default(user_id, is_default)`；UNIQUE `(tenant_id, user_id, id)`（如 doc/11 §2.2 有其他唯一约束以 doc 为准）
- [ ] **AC 2**：mp 端 `/pages/me/address/list` 列表展示（默认地址置顶 + 普通地址）；右上"新增"按钮跳编辑页
- [ ] **AC 3**：mp 端 `/pages/me/address/edit?id=<可选>` 表单：收件人 + 手机号 + 省市区联动 picker + 详细地址 + "设为默认" switch；保存调 `POST/PUT /app/gz/user/address`
- [ ] **AC 4**：设为默认时业务层兜底：`UPDATE gz_user_address SET is_default=false WHERE user_id=? AND id!=?` 走在同一事务内（不依赖 DB 唯一索引，因为 V1.0 schema 未必有偏函数索引能力）
- [ ] **AC 5**：删除走软删（del_flag='1'），列表查询过滤；列表为空时显示"暂无地址，点击新增"占位
- [ ] **AC 6**：mockup 含的"智能粘贴"按钮（doc/12 §7 偏差 D9）保留 UI，实施时降级为调 `wx.chooseAddress`（如 wx API 可用）→ 失败则 toast"请手动填写"
- [ ] **AC 7**：i18n 走 `t('user.address.xxx')`
- [ ] **AC 8**：单测覆盖：新建默认地址 / 切换默认地址（验上一条 is_default 被取消） / 软删

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserAddressMpController.java`（mp 路径 `/app/gz/user/address`）
  - `domain/GzUserAddress.java` + `domain/vo/GzUserAddressVO.java` + `domain/bo/GzUserAddressBo.java`
  - `mapper/GzUserAddressMapper.java`
  - `service/IGzUserAddressService.java` + `service/impl/GzUserAddressServiceImpl.java`
  - DDL × 1（建表）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/address/list.vue` + `pages/me/address/edit.vue`
  - `components/biz/AddressCard.vue`（业务组件）
  - `api/gz-user.ts` 加 `getAddressList()` / `getAddress(id)` / `saveAddress()` / `deleteAddress()` / `setDefaultAddress()`
  - `locales/zh_CN/user.ts` 加 address 段
- **测试**：mvn 单测 + mp 端浏览器 / 微信开发者工具实操

## 备注

### 强约束

1. **UNIQUE 必含 tenant_id**（CLAUDE.md §6 #3）
2. **INSERT 不显式赋 tenant_id**（CLAUDE.md §6 #3，走 InjectionMetaObjectHandler 自动填）
3. **默认地址唯一在业务层 + DB 双重保证**：业务层事务先 reset 其他为 false 再 set 当前为 true；DB 层如能加偏函数索引则加，不能则忽略（V1.0 mysql 8 可加 `WHERE is_default=true` 的虚拟列索引，本 ticket 评估后决定）
4. **省市区数据**：优先用 wot-design-uni 内置 `wd-picker`；如数据不全 → §0 自检确认后报 Kevin（CLAUDE.md §6 #8 不引未澄清依赖）
5. **i18n 强制**：所有 placeholder / label / toast 走 `t('user.address.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 默认地址唯一性走业务层而非纯 DB | V1.0 mysql 偏函数索引未必启用，业务层兜底更兼容 |
| D2 | 软删而非物理删 | V1.1 历史订单可能引用地址，物理删会断引用 |
| D3 | 智能粘贴按钮保留 UI 但实施降级 | mockup 偏差 D9 妥协方案，避免重做 mockup |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 省市区 picker 数据集与微信地区编码不一致 → V1.1 下单调微信寄送时不匹配 | 存"中文文本 + 编码"双字段；编码用国家标准（如 `area-data` 同款） |
| R2 | 设默认事务中并发请求可能导致两条都 is_default=true | 业务层加 user_id 行锁 `SELECT ... FOR UPDATE`；V1.0 并发量小可接受 |
| R3 | 手机号字段是否加密 | 与 gz_user.phone_num 一致策略；如 SYS-003 加密则本字段也加密 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
