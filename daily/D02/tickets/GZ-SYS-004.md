# GZ-SYS-004 — 客服入口（全局浮层）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M8 §实现方式
**关联拆解**: doc/02-需求拆解.md §2.1 第 219 行
**关联 mockup**: —（浮层在各页 mockup 内体现，无独立 mockup）
**关联 ADR**: —（无）
**依赖**: GZ-SYS-001 ✅

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md M8 客服入口（如有；本 ticket 无核心业务流，参考 PRD M8 即可）
- **字段表**：doc/11-字段权威表.md — 本 ticket 不落 DDL，仅在 admin 端 sys_config 增 2 个配置项（不需要单独建表）
- **UI 参考**（设计冻结期）：
  - mp ticket：N/A（浮层视觉走 wot-design-uni 默认 FloatButton + brand-primary token）
  - admin ticket：N/A（设计冻结期 admin 走 ruoyi 默认 + plus-ui 配置项页）

## What

mp 全局右下角浮层按钮，点击触发微信原生 `<button open-type="contact">` 拉起企业微信客服会话；admin 端提供配置项管理「企业微信客服账号」+「降级文案（客服电话 + 微信号）」。

## AC（验收标准）

- [ ] **AC 1**：mp 端全局浮层组件 `<BizCustomerServiceFab>` 放在 `App.vue` 根层级，使用 wot-design-uni `wd-fab` 或 `<movable-area>` 实现；视觉位置右下角离底 tab 栏 32rpx；不遮挡底部 5 tab / fixed CTA 条
- [ ] **AC 2**：浮层点击逻辑：先读后台 sys_config `gz.customer_service.wx_kf_id`（企业微信客服账号），有值 → 渲染微信原生 `<button open-type="contact" data-corp-id="..." data-app-id="..." />`；空 → 弹出降级文案弹窗（展示 `gz.customer_service.phone` + `gz.customer_service.wx_id`）
- [ ] **AC 3**：admin 端配置页 `views/gz-common/config/customer-service.vue` 提供 3 字段编辑：企业微信客服账号 / 客服电话 / 客服微信号 — 用 plus-ui `<el-form>` 默认风格；保存写 `sys_config` 表（key 用 `gz.customer_service.*`）
- [ ] **AC 4**：sys_config 默认值在 DDL `V202605281200__GZ-SYS-004-customer-service-config.sql` 插入 3 个 key（值为空字符串占位）
- [ ] **AC 5**：admin 端添加菜单「系统管理 → 客服配置」（menu_id 5021）+ perm `gz:config:cs:edit`
- [ ] **AC 6**：mp 端浮层在所有 5 tab 页 + 任一详情页都可见（详情页 fixed CTA 条与浮层视觉不冲突 — 浮层位置避开 fixed CTA 区域）
- [ ] **AC 7**：单测可选（配置项 CRUD 简单，依赖 ruoyi 自带 sys_config 范式）

## Tech（端 + 范围）

- **后端**：复用 ruoyi 自带 `sys_config` 表 + `SysConfigController`，**不新增表**
  - 仅落 DDL 插入 3 个 sys_config 默认 key
  - sys_menu 插入 1 行（菜单 + perm）
- **Admin**：`code/main/plus-ui/src/views/gz-common/config/customer-service.vue`（el-form 默认风格）+ `api/gz-common/customer-service.ts` 调 ruoyi 自带 `/system/config/configKey/{key}` 与 `PUT /system/config`
- **小程序**：
  - `components/biz/BizCustomerServiceFab.vue`（业务组件，CLAUDE.md §7.5 组件库无关纪律）
  - `App.vue` 加入 `<BizCustomerServiceFab />`
  - `composables/useCustomerServiceConfig.ts`（拉 sys_config 三个 key，缓存到 pinia 5 分钟）
  - i18n key `customer_service.contact` / `.phone` / `.wx`
- **测试**：mp 端手动联调（微信原生 contact button 仅在真机 + 真实 AppID 下才能 trigger，dev profile 仅做"按钮存在 + 弹窗降级文案展示"测试）

## 备注

### 强约束

1. **不新增业务表**（sys_config 已够用）
2. **微信原生 contact button 限制**：必须在用户主动点击事件内触发，不能 setTimeout 包裹（小程序规范）
3. **dev profile 测试限制**：wxMOCK 短路下无法 trigger 真实企业微信客服，只能验证「按钮存在 + 降级弹窗文案正确」；真实联调留到 staging
4. **浮层不能遮挡 fixed CTA 条**：拼豆 booking-select.html / preorder-detail.html 等页面底部都有 fixed CTA，浮层位置必须避开

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 复用 ruoyi sys_config，不新建 `gz_customer_service_config` 表 | 单条配置无必要建独立表，sys_config 已是 K-V 范式 |
| D2 | mp 端用业务组件包一层 `<BizCustomerServiceFab>` | CLAUDE.md §7.5 组件库无关纪律 — 即使一行也包，后续切组件库不动业务页 |
| D3 | sys_config 缓存 pinia 5 分钟 | 高频读取（每页都有浮层），不要每次发请求 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 企业微信客服账号未到位（甲方流程未走完）| sys_config 空值 + 降级弹窗已覆盖；上线时甲方填进配置项即可生效，零代码变更 |
| R2 | 真机调试需要真实 AppID + 备案完成 | 接受：dev 仅验证降级；真机调试推迟到 staging 阶段 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
