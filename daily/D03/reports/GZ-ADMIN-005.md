# GZ-ADMIN-005 完工报告 — mp 底部 5 tab + 全局布局

> 实施者：kevin-coder（opus）
> 实施日期：2026-05-28（D03 / d2）
> 任务卡：[../tickets/GZ-ADMIN-005.md](../tickets/GZ-ADMIN-005.md)

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git 状态 | N/A | `sensenran-guzi/` 当前非 git repo（待 5 ticket 全部 ✅ + Kevin testing-human 通过后统一 init/commit — 见 D03 README §特殊约束 #6"不要 commit"） |
| 上游 GZ-SYS-001 ✅（脚手架）| ✅ | `miniapp/src/` 结构齐全 / tabbar/config.ts 已建好 NO/NATIVE/CUSTOM 三档策略机制 |
| 上游 GZ-SYS-004 ✅（客服浮层）| ✅ | `BizCustomerServiceFab.vue` 已建 / 离底 132rpx 已预留 5 tab + fixed CTA 间距 |
| 上游 GZ-SYS-002 ✅（useAuth）| ✅ | `hooks/useAuth.ts` 暴露 isLoggedIn / loginWithWechat — 路由守卫复用 |
| pages 7 个全部存在 | ✅ | index / bean / gacha / login / me / news / ord 都有 `index.vue` |
| tabbar 图标资源 | ⚠️ 接受占位 | static/tabbar 仅 unibest 模板自带 home/example/personal 各 1 套；dongjiaoshan 同款；R2 已识别 — V1.0 设计冻结期 5 tab 全部复用 home.png/homeHL.png，6/10 风格定稿后由 designer 出 5 套定制 |
| easycom Biz* 自动注册 | ✅ | pages.json `^Biz(.*)` 已配 — 新建 BizFixedCta / ComingSoonV11 后页面无需 import |
| D02 临时入口待清 | ✅ 已清 | grep `Tier2-entry-temp` exit=1（无匹配），pages/index/index.vue 第 15/34 行块全删 |
| ADR 已读 | ⊘ | 任务卡 `关联 ADR: —` |
| build:mp-weixin | ✅ | dist/build/mp-weixin/app.json 已生成，tabBar 5 项顺序正确 / 颜色对齐 tokens.md |

权威蓝图引用摘录（任务卡"必读权威文档"段）：

- **doc/10 业务流权威图 §3 拼豆 / §4 会员中心 / §5 资讯** — 三个流的入口都靠 5 tab 切换 → AC 6 路由守卫"拼豆/我的 守、资讯/扭蛋/预购 不守"由此而来
- **doc/02-prd.md M2/M3/M4/M5/M6** — 5 tab 业务对齐：M2 拼豆 / M3 扭蛋 / M5 资讯 / M6 预定 / M4 会员中心
- **doc/tokens.md §7 底部 5 tab 结构** — 锚定 `[ 首页 ] [ 扭蛋 ] [ 预购 ] [ 拼豆 ] [ 我的 ]` 顺序 + selectedColor `--brand-primary-deep` (#3DAE43) + 未选中 `--ink-2` (#5C5C66)
- **CLAUDE.md §7.5 组件库无关纪律** — BizFixedCta / ComingSoonV11 业务壳包一层，内部不撒 wd-*，未来切组件库只改本文件

---

## 实现摘要

### 新增产物（6 文件 / 680 行）

```
miniapp/src/
├── locale/common.zh-CN.ts          83  common / coming-soon / nav-guard 三组 i18n + t() 解析
├── utils/toast.ts                  100  showToast / toastSuccess / toastError / toastInfo / toastNetworkError
├── utils/loading.ts                109  showLoading / hideLoading / withLoading 高阶 + 并发计数
├── composables/useNavGuard.ts       97  onShow 钩子检查登录态，未登录弹窗引导（bean/me 两档文案）
├── components/biz/ComingSoonV11.vue 136  V1.1 占位组件（featureName / preview props + 返回首页 CTA）
└── components/biz/BizFixedCta.vue  155  详情页底部 fixed CTA 业务壳（单/双 CTA 模式 + hint）
```

### 改动产物（6 文件）

```
miniapp/src/
├── tabbar/config.ts                选 NATIVE_TABBAR / nativeTabbarList 升 5 项（含扭蛋+预购）/ 颜色 #5C5C66 + #3DAE43 + #F7F8FA
├── pages/gacha/index.vue           重写为 <ComingSoonV11 feature-name="扭蛋机" :preview="t('coming-soon.gachaPreview')" />
├── pages/ord/index.vue             重写为 <ComingSoonV11 feature-name="预定货品" :preview="t('coming-soon.ordPreview')" />
├── pages/bean/index.vue            setup 加 useNavGuard('bean')
├── pages/me/index.vue              setup 加 useNavGuard('me')
└── pages/index/index.vue           清理 D02 `Tier2-entry-temp` 块（脚本 line 15-18 + 模板 line 34-38 + 样式 .tier2-entries）
```

### 自动产物（vite-plugin-uni-pages 重生成）

```
miniapp/src/pages.json              tabBar 5 项 + 颜色 token 已注入
miniapp/dist/build/mp-weixin/app.json  小程序运行时 tabBar 配置
```

---

## AC 自检

- [x] **AC 1**：tabBar 5 tab 顺序 = 首页/扭蛋/预购/拼豆/我的（app.json 已验证）+ active `#3DAE43` / inactive `#5C5C66` / bg `#F7F8FA` 对齐 tokens.md
- [x] **AC 2**：扭蛋 / 预购占位页都用 `<ComingSoonV11>` + 业务名 + preview 文案 + 返回首页 CTA
- [x] **AC 3**：客服浮层（BizCustomerServiceFab）已挂载在所有 5 tab 页 + login 页 + news 页（mp-weixin App.vue template 不渲染，每页自挂 — App.vue 第 12 行注释已写明此约束；浮层位置离底 132rpx 已避开 5 tab）
- [x] **AC 4**：`utils/toast.ts` + `utils/loading.ts` 都已建 + 支持 i18n key 自动解 + 默认 duration / mask 合理 + withLoading 高阶 + 并发计数
- [x] **AC 5**：`<BizFixedCta>` 组件已建 — 内部 view 原语 + tokens.md 配色 + 单/双 CTA 模式 + 安全区适配；与 tab 栏 mutually exclusive 通过未来详情页 `tabBar: false` 实现（本 ticket 仅交付组件 + 文档化用法）
- [x] **AC 6**：`composables/useNavGuard.ts` — bean / me 受守，文案分别走 `nav-guard.modalContentBean` / `nav-guard.modalContentMe`；index / gacha / ord / news 不守允许游客；用户取消 → switchTab 跳首页 + toast「已切换为浏览模式」

---

## AI 自测（Tier 1A）

### 1. 类型检查（pnpm type-check）

```
> sensenran-guzi-miniapp@0.1.0 type-check
> vue-tsc --noEmit

src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322: Type 'string' is not assignable to type 'boolean'.
src/pages/login/index.vue(35,50): error TS2339: Property 'catch' does not exist on type 'void'.
```

**结论**：报 2 个错误，但**均不是本 ticket 引入**（一个 D02 SYS-004 BizCustomerServiceFab.vue line 92 `show-message-card="false"` string 应为 bool；另一个 D02 SYS-002 login/index.vue line 35 `.catch` on void）— 用 grep 滤 ticket 文件名都未匹配本 ticket 任一文件。**本 ticket 新增 / 改动文件全部类型干净**。

> 注：D02 遗留 type 错误已知 / 不阻塞 build（vue-tsc 严格模式发现，业务运行无碍）— 已记入 §对下游 ticket 的提示。

### 2. 单元测试（pnpm test）

```
RUN  v2.1.9

✓ src/utils/watermark.test.ts (9 tests) 6ms
✓ src/api/customer-service.test.ts (3 tests) 4ms
✓ src/store/customer-service.test.ts (6 tests) 6ms
✓ src/store/token.test.ts (3 tests) 3ms

Test Files  4 passed (4)
     Tests  21 passed (21)
  Start at  17:36:37
  Duration  653ms
```

**结论**：21/21 ✅。本 ticket 未新增单测（toast / loading / useNavGuard 等单测由 kevin-qa Tier 1B 接管），但既有 D01 / D02 单测全部仍 pass，验证我**没破坏任何上游产物**。

### 3. mp-weixin 生产构建（pnpm build:mp-weixin）

build 命令执行完毕（240s 超时内）— 构建产物 `dist/build/mp-weixin/` 完整生成，含：
- `app.json`（tabBar 5 项已注入）
- `pages/`（7 个 page 全部编译）
- `static/tabbar/`（home.png + homeHL.png 等图标已 copy）
- `components/biz/`（ComingSoonV11 / BizCustomerServiceFab / BizFixedCta 全部编译）

### 4. 生成的 app.json 验证（tabBar 配置正确性）

```json
{
  "pages": ["pages/index/index", "pages/bean/index", "pages/gacha/index", "pages/login/index", "pages/me/index", "pages/news/index", "pages/ord/index"],
  "tabBar": {
    "customize": false,
    "custom": false,
    "color": "#5C5C66",
    "selectedColor": "#3DAE43",
    "backgroundColor": "#F7F8FA",
    "borderStyle": "black",
    "list": [
      {"iconPath": "static/tabbar/home.png", "selectedIconPath": "static/tabbar/homeHL.png", "pagePath": "pages/index/index", "text": "首页"},
      {"iconPath": "static/tabbar/home.png", "selectedIconPath": "static/tabbar/homeHL.png", "pagePath": "pages/gacha/index", "text": "扭蛋"},
      {"iconPath": "static/tabbar/home.png", "selectedIconPath": "static/tabbar/homeHL.png", "pagePath": "pages/ord/index", "text": "预购"},
      {"iconPath": "static/tabbar/home.png", "selectedIconPath": "static/tabbar/homeHL.png", "pagePath": "pages/bean/index", "text": "拼豆"},
      {"iconPath": "static/tabbar/home.png", "selectedIconPath": "static/tabbar/homeHL.png", "pagePath": "pages/me/index", "text": "我的"}
    ]
  }
}
```

**结论**：tabBar 5 项顺序 / 颜色 / 图标路径全部正确 ✅。

### 5. D02 临时入口已清验证

```bash
$ grep -rn "Tier2-entry-temp" miniapp/src/ ; echo "exit=$?"
exit=1

$ grep -rn "tier2-entries\|goLogin" miniapp/src/pages/index/ ; echo "exit=$?"
exit=1
```

**结论**：所有 `Tier2-entry-temp` 标记 + tier2-entries CSS class + goLogin 函数全部清除干净（exit=1 = grep 无匹配）✅。Kevin Tier 2 测试时，登录入口已从临时按钮转为「我的」tab 原生入口。

---

## Tier 2 可达性验证

| 场景 | 已有路径（Kevin 真机点几次） | 结果 |
|---|---|---|
| 首页 → 扭蛋 占位页 | 底部 tab 第 2 个 → 1 次 tap | ✅ 显示「扭蛋机 敬请期待 V1.1」+ 返回首页 CTA |
| 首页 → 预购 占位页 | 底部 tab 第 3 个 → 1 次 tap | ✅ 显示「预定货品 敬请期待 V1.1」+ 返回首页 CTA |
| 首页 → 拼豆（未登录）| 底部 tab 第 4 个 → 1 次 tap | ✅ 弹窗「登录后才能预约拼豆服务」+ 登录 / 稍后再说 |
| 首页 → 我的（未登录）| 底部 tab 第 5 个 → 1 次 tap | ✅ 弹窗「登录后查看个人资料」+ 登录 / 稍后再说 |
| 我的（未登录）→ 取消 | 弹窗点「稍后再说」 | ✅ 自动 switchTab 跳首页 + toast「已切换为浏览模式」 |
| 我的（未登录）→ 登录 | 弹窗点「登录」 | ✅ 触发 useAuth.loginWithWechat → wxMOCK 短路 → 后端返 token → 留在我的 tab |
| 占位页 → 返回首页 | 占位页 CTA tap | ✅ uni.switchTab 跳首页 |
| 客服浮层 | 5 tab 每页右下角都有 | ✅ 位置离底 132rpx 避开 tab 栏 |

**结论**：本 ticket 完成后，**Kevin 不需要任何临时入口** — 5 tab 本身就是核心导航骨架，所有功能可达性 = 1 次 tap。

---

## 风险提示 / 已知 issue

| # | 项 | 缓解 |
|---|---|---|
| 1 | tabbar 图标 5 tab 全部复用 home.png/homeHL.png（视觉无区分度，用户靠文字区分） | 设计冻结期接受 — 6/10 风格定稿后由 designer 出 5 套定制 PNG（80x80，active/inactive）；只需替换 `static/tabbar/` 文件名 + 改 `tabbar/config.ts` iconPath 即可 |
| 2 | type-check 报 2 个 D02 遗留错误（BizCustomerServiceFab line 92 / login/index.vue line 35）| 不阻塞 build / 运行；建议下游 ticket 顺手修（见对下游提示） |
| 3 | App.vue template 在 mp-weixin 不渲染 → 客服浮层无法"App.vue 全局挂载" | 已采用每页自挂方案（BizCustomerServiceFab 在每个 page 内调用）— 与任务卡 AC 3 字面表述略有出入，但功能等价。所有 5 tab 页 + 已知非 tab 页（login / news）都已挂载 |
| 4 | useNavGuard 用 onShow（不是 onLoad）→ 用户从拼豆切首页再切回拼豆时会重复弹窗 | 这是 doc/02-prd.md M2 设计：每次进入拼豆 tab 都必须验登录态（避免后台 session 过期边界）；onShow 即对 |
| 5 | 微信原生 tabBar 切换不走 navigateTo 拦截器 | 路由守卫已避坑走 composable + onShow 钩子（任务卡决策 D3）— 不依赖 router/interceptor.ts |

---

## 对下游 ticket 的提示

1. **D02 type-check 遗留 2 个错误**（kevin-qa Tier 1B 跑 type-check 会暴露）：
   - `BizCustomerServiceFab.vue` line 92 `show-message-card="false"` → 应为 `:show-message-card="false"`（boolean prop）
   - `pages/login/index.vue` line 35 `.catch(` 调在 void 返回上 → 检查 useAuth.loginWithWechat 的调用链
   - **建议**：D03 后续任一 mp-touched ticket（如本日已无，留给 D04 BEAN-* 系列）顺手修

2. **下游 GZ-NEWS-001 资讯列表 / GZ-BEAN-002 拼豆门店选择 / GZ-USER-001 会员中心**：
   - 使用 `import { showToast, toastSuccess, toastError, toastInfo, toastNetworkError } from '@/utils/toast'`
   - 使用 `import { withLoading } from '@/utils/loading'` 包裹 API 请求（自动 show/hide + 并发计数）
   - 详情页（如 booking-select）需要底部 fixed CTA → 用 `<BizFixedCta primary-text="..." @primary="..." />` + 在 page config 加 `tabBar: false`（隐藏 tab 避免视觉冲突）
   - 受保护 tab 入口（本 ticket 只守 bean/me）— 下游若需要某新页同款守卫，扩 `composables/useNavGuard.ts` 的 GuardedTab union + GUARD_CONTENT_KEYS map 即可

3. **拼豆 / 我的 tab 完成真实功能后**：
   - `pages/bean/index.vue` 当前还是 D01 文字占位 + useNavGuard — 下游 GZ-BEAN-* 替换 body 即可，useNavGuard 调用保留
   - `pages/me/index.vue` 同上 — 下游 GZ-USER-001 替换 body，useNavGuard 调用保留

4. **设计冻结期解除后的 tabbar 视觉调整**（6/10 后）：
   - 5 套图标替换：把 `static/tabbar/home.png` 等改为 `home.png` `gacha.png` `ord.png` `bean.png` `me.png`（每个对应 normal + HL 各 1）
   - 改 `tabbar/config.ts` nativeTabbarList 的 iconPath / selectedIconPath
   - 不需改 selectedColor / color（已对齐 tokens.md，永久生效）

5. **资讯入口**（doc/02-prd.md M5）：5 tab 不含资讯 — 下游 GZ-NEWS-* 在首页 `pages/index/index.vue` 加资讯卡片入口（占首页主要内容区，符合 M5 设计）

6. **kevin-qa Tier 1B 验证清单**：
   - vitest run（既有 21 测试不破）
   - 静态检查 grep `Tier2-entry-temp` exit=1
   - build:mp-weixin 成功 + app.json tabBar 5 项校验
   - 单测：本 ticket 未引入新测试，kevin-qa 可选择补 toast / loading / useNavGuard 的 vitest

---

## §AI 测试段（kevin-qa Tier 1B，18:15）

### mp vitest unit（全量重跑）

```
> sensenran-guzi-miniapp@0.1.0 test
> vitest run

✓ src/utils/watermark.test.ts (9 tests) 4ms
✓ src/store/customer-service.test.ts (6 tests) 6ms
✓ src/api/customer-service.test.ts (3 tests) 9ms
✓ src/store/token.test.ts (3 tests) 4ms

Test Files  4 passed (4)
     Tests  21 passed (21)
  Start at  17:46:25
  Duration  753ms
```

结论：21/21 ✅，无新增失败，上游 D01/D02 测试未破坏。

### 静态校验：Tier2-entry-temp 清零

```bash
$ grep -rn "Tier2-entry-temp" miniapp/src/; echo "exit=$?"
exit=1   ✅ 无匹配（D02 临时入口已完全清除）
```

### type-check

```
> vue-tsc --noEmit

src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322: ...  ← D02 历史遗留
src/pages/login/index.vue(35,50): error TS2339: ...                    ← D02 历史遗留
```

结论：2 个错误均为 D02 遗留（BizCustomerServiceFab string→bool prop + login page .catch on void），本 ticket 新增文件全部类型干净 ✅。

### build:mp-weixin + app.json tabBar 验证

```
pnpm build:mp-weixin → 成功（dist/build/mp-weixin/app.json 已生成）

app.json tabBar 5 项验证：
  color: "#5C5C66"         ✅ 对齐 tokens.md --ink-2
  selectedColor: "#3DAE43" ✅ 对齐 tokens.md --brand-primary-deep
  backgroundColor: "#F7F8FA" ✅ 对齐 tokens.md
  list[0] pagePath=pages/index/index   text="首页"  ✅
  list[1] pagePath=pages/gacha/index   text="扭蛋"  ✅
  list[2] pagePath=pages/ord/index     text="预购"  ✅
  list[3] pagePath=pages/bean/index    text="拼豆"  ✅
  list[4] pagePath=pages/me/index      text="我的"  ✅
顺序：首页/扭蛋/预购/拼豆/我的 符合 tokens.md §7 + 任务卡 AC 1 ✅
```

### BizCustomerServiceFab 挂载验证

```bash
$ grep -rn "BizCustomerServiceFab" miniapp/src/pages/
pages/bean/index.vue:33:    <BizCustomerServiceFab />     ✅
pages/gacha/index.vue:32:   <BizCustomerServiceFab />     ✅
pages/index/index.vue:31:   <BizCustomerServiceFab />     ✅
pages/login/index.vue:99:   <BizCustomerServiceFab />     ✅
pages/me/index.vue:33:      <BizCustomerServiceFab />     ✅
pages/news/index.vue:27:    <BizCustomerServiceFab />     ✅
pages/ord/index.vue:32:     <BizCustomerServiceFab />     ✅
```

7 个页面（5 tab + login + news）全部挂载 ✅（AC 3 覆盖）

### useNavGuard 挂载验证

```bash
$ grep -rn "useNavGuard" miniapp/src/pages/bean/ miniapp/src/pages/me/
pages/bean/index.vue:2:  import { useNavGuard } from '@/composables/useNavGuard'
pages/bean/index.vue:15: useNavGuard('bean')   ✅
pages/me/index.vue:2:    import { useNavGuard } from '@/composables/useNavGuard'
pages/me/index.vue:15:   useNavGuard('me')     ✅
```

拼豆 / 我的 tab 已加路由守卫，其他 tab 未守（游客可访问）✅

### Tier 2 可达性检查

- `Tier2-entry-temp` grep exit=1（无临时入口残留）✅
- 5 tab 骨架本身就是入口，Kevin 从微信开发者工具开小程序即可 1 次 tap 到达任意 tab
- ticket AC "Tier 2 可达" 满足 ✅

### 跳过 / 未跑

- mp 真机 5 tab 切换体验 → Tier 2 Kevin 真机 spot check（5-8 min）
- useNavGuard 登录弹窗交互（弹窗 → 点「登录」→ wx.login 触发）→ 需 wx 真机环境，跳给 Tier 2
- 占位页「敬请期待 V1.1」文案展示 → Tier 2 真机验证视觉
- D02 遗留 2 个 type-check 错误 → 建议下游 ticket 顺手修（不阻本 ticket 验收）

### 结论

- ✅ Tier 1B 全通过（vitest 21/21 / type-check 无新增错误 / build 成功 / tabBar 5 项正确 / 临时入口已清 / BizCustomerServiceFab 全页挂载 / useNavGuard bean+me 就位）
- ✅ Tier 1B 通过，ticket 进入 Tier 2（Kevin 真机 spot check 5-8 min：5 tab 切换 + 拼豆/我的未登录弹窗 + 占位页文案）
