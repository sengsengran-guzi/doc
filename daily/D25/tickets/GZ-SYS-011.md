# GZ-SYS-011 — 小程序分享给朋友 / 朋友圈

**优先级**: P1（拉新入口，甲方主动提）
**复杂度**: M
**关联拆解**: N/A（甲方 8.31 微信新提）
**关联 ADR**: 无（沿用 GZ-NEWS-002 已验证的分享范式）
**依赖**: 无

---

## 需求原文（甲方，2026-08-31）

> 「小程序里应该添加分享给朋友功能」

## 现状（实施前查证）

全项目只有**资讯详情页**（GZ-NEWS-002）实现过分享。其余页面**右上「…」菜单里的「转发」是灰的、点不动** ——
用户想发给朋友根本发不出去。

在线的 C 端页面只有 **3 个 tab + 资讯中心**（V1.2 后首页已下线成重定向壳、预购下线、扭蛋只剩「我开过的」私人页）。

## What

给在线公开页开启微信分享（好友 + 朋友圈），私人页明确不开放。

| 页面 | 好友分享 | 朋友圈 | 说明 |
|---|---|---|---|
| `pages/bean/index`（拼豆 tab） | ✅ | ✅ | 启动落地页，分享落地即本页 |
| `pages/recycle/form`（回收 tab） | ✅ | ✅ | 拉新主力场景 |
| `pages/news/list`（资讯中心） | ✅ | ✅ | 单篇分享在 news/detail（已有） |
| `pages/me/index`（我的 tab） | ✅ | ❌ | **私人页**：好友分享重定向到拼豆 tab；朋友圈无法重定向落地页故不开 |
| 我的预约 / 我的回收记录 / 我的订单 | ❌ | ❌ | 私人页，分享会把私有 id 带进别人聊天记录 |

## AC

- [x] AC 1：4 个公开页「转发」可用（此前全灰）
- [x] AC 2：「我的」只开好友分享、**不开朋友圈**，且好友分享落地到拼豆 tab 而非个人页
- [x] AC 3：3 个私人页确认**完全没有**分享钩子
- [x] AC 4：分享链接带 `from=share` / `from=timeline` 埋点参数；path 自带 query 时用 `&` 拼接
- [x] AC 5：不塞占位分享图 —— 甲方正式素材到位前用微信自动截屏（最诚实的默认）
- [x] AC 6：真模拟器逐页断言钩子是否真的挂上（`test/e2e/flows/share.mjs`）

## ⚠️ 实施中撞到的 uni-app 硬约束（务必留档）

**分享钩子不能抽进 composable。** uni-app 的 `uni:mp-runtime-hooks` 插件靠
**对页面文件自身源码做字面量正则匹配**决定是否给小程序暴露分享能力：

```js
const matches = source.match(new RegExp(`(${Object.keys(MINI_PROGRAM_PAGE_RUNTIME_HOOKS).join('|')})`, 'g'))
if (matches.includes('onShareTimeline')) matches.push('onShareAppMessage')
source = source + `;_sfc_main.__runtimeHooks = ${flag};`
```

调用藏在别的模块里 → 页面源码无该字样 → `__runtimeHooks = 0` → **微信压根不知道这页能转发，
且不报任何错**。第一版正是这么写的，单测全绿、TS 全绿，真模拟器一跑全 false。

**衍生结论**：「我的」页想要「有好友分享但没朋友圈」，表现为**连 `onShareTimeline` 的 import 都不能有** ——
插件见到该字样就会连朋友圈一起暴露。

**没有采用的做法**：在页面里写句含 `onShareAppMessage` 字样的注释骗过正则。那是雷 —— 谁顺手清理注释
谁就静默搞死分享，且编译期之前没有任何测试能拦住。

## 最终结构

- `composables/useShare.ts`：出「菜单开关 + 两个卡片构造器」，**不注册钩子**
- 页面：`const share = useShare({...})` + 自己写 `onShareAppMessage(share.onFriend)`

## 待甲方提供

**正式分享封面图**（PNG/JPG；好友分享 5:4、朋友圈 1:1）。当前不传 `imageUrl`，微信自动截当前页首屏。
素材到位后 `useShare({ imageUrl })` 传入即可，无需改结构。
