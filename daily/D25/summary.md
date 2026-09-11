# GZ-SYS-011 — 完工报告

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 关键 API 存在 | ✅ | `onShareAppMessage`/`onShareTimeline` 已在 auto-import.d.ts；news/detail 有可用先例 |
| 编译通过 | ✅ | `uni build -p mp-weixin` + vue-tsc 零错 |
| ADR 已读 | 无相关 | 沿用 GZ-NEWS-002 范式，无新决策 |
| 合同范围 | V1.2 | 甲方 8.31 主动提 |

## 改了哪些文件

**新增**
```
src/composables/useShare.ts          分享卡片构造 + 菜单开关（不注册钩子，原因见下）
src/composables/useShare.test.ts     9 例单测
test/e2e/flows/share.mjs             真模拟器逐页断言钩子挂载
```

**改动**
```
src/pages/bean/index.vue      + onShareAppMessage/onShareTimeline 注册
src/pages/recycle/form.vue    同上
src/pages/news/list.vue       同上
src/pages/me/index.vue        只注册 onShareAppMessage（私人页，故意不引朋友圈）
src/locale/{bean,recycle,news,user}.zh-CN.ts   各 1 条分享标题
test/e2e/run.mjs              注册 share flow
```

无后端改动、无迁移。

## ★ 关键过程：第一版是错的，靠真模拟器逮出来

第一版把 `onShareAppMessage` 调用写进了 `useShare()` 内部。**单测全绿、TS 全绿、lint 全绿**，
但真模拟器一跑：

```
── 应当可分享的页面 ──
  ✗ 拼豆 tab  好友=false  朋友圈=false（期望 true）
  ✗ 回收 tab  好友=false  朋友圈=false（期望 true）
  ✗ 资讯中心  好友=false  朋友圈=false（期望 true）
  ✗ 我的 tab  好友=false  朋友圈=false（期望 false）
```

**先校准了探测方法再下结论**：拿已知可用的 news/detail 当对照组，探针确认它有钩子 ——

```json
{ "route": "pages/news/detail",
  "ownShareKeys": ["onShareAppMessage:function", "onShareTimeline:function"] }
```

→ 探测方法没问题，是我的代码真的没注册上。查编译产物 + uni-app 源码定位根因：

```js
// node_modules/@dcloudio/uni-mp-vite/dist/plugins/runtimeHooks.js
const matches = source.match(new RegExp(`(${Object.keys(MINI_PROGRAM_PAGE_RUNTIME_HOOKS).join('|')})`, 'g'))
if (matches.includes('onShareTimeline')) matches.push('onShareAppMessage')
source = source + `;_sfc_main.__runtimeHooks = ${flag};`
```

```js
// node_modules/@dcloudio/uni-mp-weixin/dist/uni.mp.esm.js
const PAGE_INIT_HOOKS = [ ...
    // 'onShareTimeline',   // 右上角菜单，开发者手动注册
    // 'onShareAppMessage'  // 右上角菜单，开发者手动注册
];
```

**分享钩子的暴露与否取决于对页面源码的字面量正则扫描** → 藏进 composable 必然静默失效。
改成「composable 出内容、页面自己注册」后通过。

## AI 自测

### 1) 单测 538/538（新增 9 例）

```
$ pnpm test -- --run
 Test Files  48 passed (48)
      Tests  538 passed (538)
```

覆盖：menus 组合 / `from=` 拼接（含 path 自带 query 用 `&`）/ imageUrl 有无 / 朋友圈只给 query 不给 path /
取不到当前页时回落拼豆 tab。

⚠️ 单测**照不出**「钩子有没有真挂上」—— mock 掉 `@dcloudio/uni-app` 后编译期那一步根本不存在。
这一点已写进测试文件头，避免后人误以为单测绿就等于分享可用。

### 2) typecheck + lint

```
$ npx vue-tsc --noEmit   → ✅ 零错
$ npx eslint --fix ...   → EXIT=0
```

### 3) ★ 真模拟器逐页断言（唯一能证明分享可用的证据）

```
── 应当可分享的页面 ──
  ✓ 拼豆 tab（启动落地页）  land=pages/bean/index    好友=true  朋友圈=true（期望 true）
  ✓ 回收 tab                land=pages/recycle/form  好友=true  朋友圈=true（期望 true）
  ✓ 资讯中心                land=pages/news/list     好友=true  朋友圈=true（期望 true）
  ✓ 我的 tab（私人页）      land=pages/me/index      好友=true  朋友圈=false（期望 false）
── 绝不可分享的私人页 ──
  ✓ 我的预约        好友=false  朋友圈=false（期望都是 false）
  ✓ 我的回收记录    好友=false  朋友圈=false（期望都是 false）
  ✓ 我的订单        好友=false  朋友圈=false（期望都是 false）
  ✓ 4 个公开页分享已启用 + 3 个私人页确认未开放
[PASS] share
```

### 4) E2E 回归（无连带破坏）

```
$ node test/e2e/run.mjs smoke,focus,recycle
[PASS] smoke
[PASS] focus
[PASS] recycle
[run] 结束：3/3 flow 通过
```

## 已知 issue / 风险提示

1. **没有正式分享封面图**：当前不传 `imageUrl`，微信自动截当前页首屏。这是有意的 ——
   塞占位图比自动截屏更糟。甲方给图后 `useShare({ imageUrl })` 传入即可，结构不用改。
2. **朋友圈无法脚本触发**：微信限制 `onShareTimeline` 只能从右上「…」菜单点。
   news/detail 页有「分享到朋友圈」按钮弹引导提示的做法，本次未在其他页复制（会改动主页面视觉）。
3. **页面内没有可见的分享按钮**：本次只启用了「…」菜单里的转发（零视觉改动）。
   若要在拼豆页放一个显眼的 `<button open-type="share">` 引导分享，那会动主落地页视觉，
   建议先过设计/甲方确认再做 —— 属于可选增强，不在本次范围。

## 交付前须向甲方确认

1. **分享封面图**：给一张正式的（好友 5:4、朋友圈 1:1，PNG/JPG）。
2. **分享文案**：当前 4 条为拟稿，甲方可直接改
   - 拼豆：「成都谷子拼豆 · 在线选桌约座」
   - 回收：「谷子中古回收 · 到店核对现金结算」
   - 资讯：「谷子宇宙 · 资讯中心」
   - 我的：「成都谷子宇宙 · 拼豆约座 & 中古回收」
3. **要不要页面内可见分享按钮**（见已知 issue 3）。
