# GZ-ADMIN-005 — mp 底部 5 tab + 全局布局

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M2/M3/M4/M5/M6 共享 + tokens.md §7（底部 5 tab 结构）
**关联拆解**: doc/02-需求拆解.md §2.6 第 606 行
**关联 mockup**: design/mockup/home.html（5 tab 锚定） + gacha-list.html / preorder-list.html（V1.0 占位）
**关联 ADR**: —
**依赖**: GZ-SYS-001 ✅

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md §3 拼豆 / §4 会员中心 / §5 资讯 — 三个流的入口都靠 5 tab 切换
- **字段表**：doc/11-字段权威表.md — 不落 DDL
- **UI 参考**（设计冻结期）：
  - mp ticket：`design/mockup/home.html`（5 tab 视觉结构）— **mp 端视觉走 wot-design-uni 默认 + tokens.md brand-primary**，不强求逐像素还原 mockup

## What

mp 端 uni-app pages.json 配 5 tab 结构 + 全局 App.vue 挂载客服浮层（SYS-004 已建）+ 全局 toast / loading 工具 + V1.0 不上线 tab（扭蛋 / 预购）的占位页。

## AC（验收标准）

- [ ] **AC 1**：`miniapp/src/pages.json` tabBar 配 5 tab：
  - 首页（home） `pages/index/index`
  - 扭蛋（gacha） `pages/gacha/index`（占位）
  - 预购（preorder / ord） `pages/ord/index`（占位）
  - 拼豆（bean） `pages/bean/index`
  - 我的（me） `pages/me/index`
  - tab 图标 + 文字色对齐 tokens.md（active = brand-primary / inactive = gray-500）
- [ ] **AC 2**：扭蛋 / 预购占位页内容统一组件 `<ComingSoonV11>`（参数：业务名 / 简短预告文案），居中显示「业务名 敬请期待 V1.1」+ 一个返回首页 CTA
- [ ] **AC 3**：App.vue 全局挂载 `<BizCustomerServiceFab>`（D02 SYS-004 已建）；位置右下角避开 tab 栏 + fixed CTA 条 32rpx
- [ ] **AC 4**：全局 toast 工具 `utils/toast.ts`（封装 `uni.showToast` + i18n key 自动解 + duration 默认 2000）；全局 loading 工具 `utils/loading.ts`（封装 `uni.showLoading` / `uni.hideLoading`，自动 try-finally）
- [ ] **AC 5**：详情页（如 booking-select / news-detail 等）的 fixed CTA 条规范：用 `<BizFixedCta>` 业务组件包装；与 tab 栏 mutually exclusive（详情页隐藏 tab，通过 `tabBar: false` in page config）
- [ ] **AC 6**：路由守卫 `composables/useNavGuard.ts` — 切到拼豆 / 我的 tab 时检查登录态，未登录弹「登录后才能预约」（GZ-SYS-002 useAuth 同款）；切到资讯 / 首页 / 扭蛋占位 / 预购占位允许游客

## Tech（端 + 范围）

- **小程序**：
  - `src/pages.json`（tabBar 配置）
  - `src/pages/gacha/index.vue` + `src/pages/ord/index.vue`（占位页，调用 `<ComingSoonV11>`）
  - `src/components/biz/ComingSoonV11.vue`（业务组件 — 不直接撒 wd-* 标签）
  - `src/components/biz/BizFixedCta.vue`（fixed CTA 条业务组件）
  - `src/utils/toast.ts` + `src/utils/loading.ts`
  - `src/composables/useNavGuard.ts`（路由守卫）
  - `src/App.vue`（挂载 BizCustomerServiceFab）
- **测试**：mp dev:mp-weixin → 微信开发者工具 → 5 tab 点击切换 / 占位页提示文案 / 客服浮层位置 / 详情页 fixed CTA 不挡 tab

## 备注

### 强约束

1. **5 tab 顺序固定**：首页 / 扭蛋 / 预购 / 拼豆 / 我的 — mockup home.html 已锚定，不改
2. **组件库无关纪律**（CLAUDE.md §7.5）：所有页面组件包业务壳（`<BizFixedCta>` / `<ComingSoonV11>` 等放 `components/biz/`），不直接撒 `<wd-*>`
3. **客服浮层位置不冲突 tab 栏 + fixed CTA**：tab 栏高度约 100rpx，浮层离底 32rpx → 浮层底缘距屏底 132rpx；详情页隐藏 tab 时浮层位置不变
4. **i18n**：占位页 / toast / loading 文案全部走 `t('common.xxx')` + `t('coming-soon.xxx')`
5. **不要做 tab 红点 / 角标**（V1.0 不需要，V1.1 扭蛋 / 预购上线时再加）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 uni-app 原生 tabBar（pages.json 配），不用自定义 tabBar | 单门店 / 单业务线，原生 tabBar 性能 + 兼容性最好 |
| D2 | 占位页统一组件 `<ComingSoonV11>` | 扭蛋 / 预购 V1.0 都占位，未来还会有其他占位场景（如新业务线），抽组件复用 |
| D3 | 路由守卫用 composable 而不是全局拦截器 | uni-app 全局拦截器对 tabBar 切换不友好，composable 在 onShow 钩子触发更可靠 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | uni-app + Vue3 + wot-design-uni 兼容性问题 | D01 GZ-SYS-001 已验证 hello world 跑通，本 ticket 仅扩 tab 配置 |
| R2 | 微信小程序原生 tabBar 自定义图标限制（必须本地 png，不支持 svg / 远程）| 接受：从 dongjiaoshan miniapp 静态资源 + tokens.md 截图工具自制 5 套图标（active / inactive） |
| R3 | 占位页跳转拦截不到位（用户在扭蛋 tab 长时间停留期望真功能）| 占位文案明确「敬请期待 V1.1」+ 返回首页 CTA，引导回主流程 |

---

## §revision（Kevin testing-human 后填，初始空）
