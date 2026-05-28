# GZ-BEAN-010 — mp 拼豆首页（C 端入口落地页）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §用户操作流程 步骤 1（首页入口） + tokens.md §底部 5 tab
**关联拆解**: doc/02-需求拆解.md §2.3 第 414 行
**关联 mockup**: design/mockup/home.html（拼豆 tab 模块） + design/mockup/booking-select.html（V1.0 设计冻结期：视觉参考，wot-design-uni 默认 + tokens.md brand-primary 主 CTA）
**关联 ADR**: —
**依赖**: GZ-BEAN-003 ✅(D04)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §关键节点 N1（进入拼豆首页 → home / 拼豆 tab → booking landing） — 本 ticket 就是 N1 的着陆页
- **字段表**：doc/11-字段权威表.md **§10.4 sys_config**（banner / 跑马灯文案走配置表，运营素材切换不动代码）
- **UI 参考**（设计冻结期）：doc/12 §MP-BEAN-SELECT 来源映射（"拼豆"底部 tab → MP-BEAN-SELECT，doc/12 §1.1 第 129 行 + §1.1 D5 待澄清问题第 1472 行已裁定 V1.0 按 PRD 实施 — 拼豆 tab = 落地页 = 本 ticket，**不直接是选座页**）；mockup `home.html` 中"拼豆"卡片视觉参考

## What

mp 底部 5 tab 之一「拼豆」点击后的落地页 `/pages/bean/index`：顶部 banner / 跑马灯（甲方运营素材，走 sys_config）→ 中部主 CTA「立即预约」（brand-primary 大按钮，点击跳 MP-BEAN-SELECT = BEAN-003 选座页）→ 「我的预约」次级入口（点击跳 BEAN-006 列表页）→ 底部可选规则说明（甲方需求待定，V1.0 占位）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `pages/bean/index.vue` 路由 `/pages/bean/index`，配置为底部 tab "拼豆"的默认页（修改 `pages.json` tab bar）
- [ ] **AC 2**：顶部 banner：调 `GET /app/gz/common/config/get?key=gz.bean.home.banner` 拉运营素材（图 URL + 文案 + 跳转 link，JSON 格式存 sys_config），无素材时显示占位图 + 默认文案「成都拼豆店开张啦」
- [ ] **AC 3**：中部主 CTA「立即预约」brand-primary 大按钮（约屏宽 80%，位于首屏可见区）→ 点击跳 `/pages/bean/select`（BEAN-003 选座页）
- [ ] **AC 4**：次级入口「我的预约」（弱按钮 + 右箭头）→ 点击跳 `/pages/bean/my-list`（BEAN-006 列表页）
- [ ] **AC 5**：底部规则说明卡片：固定 3-5 条文字（取消规则 / 到店时间 / 联系方式占位），文案走 i18n `bean.home.rules.*`
- [ ] **AC 6**：未登录用户进入此页不拦截（仅浏览）；点「立即预约」时若未登录 → 弹「登录后才能预约」（复用 D02 useAuth）
- [ ] **AC 7**：i18n 全覆盖；视觉 token 走 tokens.md `brand-primary`，不硬编码颜色

## Tech（端 + 范围）

- **后端**：复用 D02 GZ-SYS-006 / 类似的 `sys_config` 查询接口（如未单独开 `/app/gz/common/config/get` → 本 ticket 加薄包装），不落新 DDL；INSERT 一条 sys_config 默认值 `key=gz.bean.home.banner, value={...}`（走 db migration `V202606020020__GZ-BEAN-010-default-banner-config.sql`）
- **小程序**：
  - `pages/bean/index.vue`（新建）
  - 修改 `pages.json` tabBar — "拼豆"tab pagePath 改为 `pages/bean/index`
  - `api/gz-common.ts` 加 `getSysConfig(key)`（如复用 D02 已封装则不重复）
- **测试**：mp 端从底部 tab "拼豆"切入 → 看到 banner + CTA → 点 CTA 跳选座页（未登录弹登录）→ 点"我的预约"跳列表页

## 备注

### 强约束

1. **运营素材走 sys_config**（doc/11 §10.4） — banner 切换 / 文案修改不发版
2. **未登录不拦截浏览**（doc/10 §3 N1 用户可未登录看落地页，仅点 CTA 触发登录）
3. **brand-primary 走 tokens.md**，不硬编码颜色（CLAUDE.md §7.5 设计冻结期 mp 端 token 必走）
4. **tabBar 修改注意**：`pages.json` 改动需要在微信开发者工具重新编译才生效；本 ticket §0 自检要确认 tabBar 改后小程序能正常加载

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 甲方运营素材未到位 → banner 空白 | sys_config 默认值 + 占位图占住，运营素材到位后改 sys_config 一行；任务卡里写明 |
| R2 | mockup home.html 是首页非拼豆首页，结构差异 | 本 ticket 是「拼豆 tab 落地页」≠ 首页（home.html）；按 PRD 实施，不要逐像素还原 home.html（doc/12 §1.1 第 1472 行 D5 待澄清已裁定）|

---

## §revision（Kevin testing-human 后填，初始空）
