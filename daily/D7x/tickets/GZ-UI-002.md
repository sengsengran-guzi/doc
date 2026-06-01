# GZ-UI-002 — tabbar 3 套 C 风描边图标（替换脚手架占位）

**优先级**: P0（上线硬阻塞）
**复杂度**: S（设计出图 + 替换配置）
**关联**: doc/tokens.md §7.1（V1.0 3 tab 规范）+ doc/13 §3.1（BottomTabC 原生 tabbar）+ .claude/CLAUDE.md §7.5（designer 首批任务①）
**依赖**: **kevin-designer 出图**（C 风描边 tab 图标，designer 首批任务①），出图后才能替换
**由来**: 上线前视觉审计（2026-06-01）发现 tabbar 三个 tab 共用同一张 `home.png`，用户只能靠文字区分位置；底部导航是 C 端每屏常驻元件，属上线硬阻塞。

---

## What

把底部 tabbar 三个 tab 换成 3 套**各不相同**的 C 风粗墨描边图标（首页 / 拼豆 / 我的），替换现在三个 tab 共用的 `home.png` 占位 + 清掉 `static/tabbar/` 下脚手架残留（`example.png`/`exampleHL.png`/`scan.png`）。

## 缺陷明细（审计已核实）

| file:line | 现状 | 期望 |
|---|---|---|
| `src/tabbar/config.ts:42-57`（`nativeTabbarList`） | 首页/拼豆/我的 三项 `iconPath`+`selectedIconPath` 全 `static/tabbar/home.png`+`homeHL.png` | 各指向自己的图标：home / bean / me 三套 |
| `src/pages.json` tabBar.list | 由 config.ts 重生成，同样三 tab 同图 | 随 config.ts 改后重生成 |
| `src/static/tabbar/` | 躺着脚手架默认 `example.png`/`exampleHL.png`/`scan.png` | 删除（scan 若核销扫码页用到需确认，当前 verify-scan 走 wx.scanCode 不依赖此图） |

## AC（验收标准）

- [x] AC 1（出图）：3 套 C 风粗墨描边 tab 图标，每套 inactive（墨黑 `--c-ink` #1A1A1A）+ active（朱红 `--c-red` #E73E2A）各一张，共 6 张；80×80 PNG 透明底（读回断言全 PASS）；语义：首页 house ⌂ / 拼豆 调色盘 🎨 / 我的 人像 👤，粗墨硬朗无柔光渐变。**done-with-caveat：AI 手画几何图标（pngjs 自写光栅器），美术精度待 Tier-3 视觉签字（Kevin / 真设计师走查精修），可同名 drop-in 替换。**
- [x] AC 2（替换）：6 张图入 `src/static/tabbar/`（`home/homeHL`、`bean/beanHL`、`me/meHL`）；`src/tabbar/config.ts` 三项各自指向（验证三 icon 各不相同 PASS）；删脚手架 `example.png`/`exampleHL.png`/`scan.png`（+ 顺手删无引用的 `personal.png`/`personalHL.png`，grep 确认全无代码引用）。
- [~] AC 3（重生成 + 验证）：config.ts 已改三项各异；**未跑 build（避免与 mp agent 撞 dist，pages.json 重生成留主线程最终构建）**。ASCII 预览确认三图形状各异可辨、选中态朱红 / 未选中墨色。**真机三 tab 截图待 Tier 2 批量人验补。**
- [x] AC 4（doc 同步）：tokens.md §7.1 未选中色统一为 `--c-ink-2` `#5C5249`（对齐 config.ts `color` + pages.json 现值，不改 pages.json 数值），并注明图标 PNG inactive 态用纯墨黑 `--c-ink`。口径收口无分歧（复盘 §1 改权威蓝图对齐代码）。
- [~] AC 5（Tier 2 可达）：tabbar 全站常驻无需新入口；待 Kevin 批量人验进小程序底部确认 3 tab 图标不再雷同、切换选中态朱红高亮。

## Tech（端 + 范围）

- **设计**（kevin-designer）：出 6 张 C 风 tab 图标 PNG（AC1）。
- **小程序**：`src/static/tabbar/`（图标资源）+ `src/tabbar/config.ts`（`nativeTabbarList` 三项 iconPath/selectedIconPath）。改 config.ts 触发 pages.json 重生成。
- **测试**：人眼 / 截图验证三图各异 + 选中态朱红。**无后端 / 无 DB。**

## 备注

- **强依赖出图**：本票实施排在 designer 出图之后；出图是 designer 首批任务①（CLAUDE.md §7.5 已规约），可与 GZ-UI-001 改皮并行起，但替换步骤等图到位。
- 改 `tabbar/config.ts` 后必须重启 dev server 让 pages.json 重生成，否则旧配置缓存。
- `scan.png` 删除前 grep 确认无引用（核销扫码 verify-scan.vue 走 `wx.scanCode` 原生，不依赖此静态图）。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-UI-002 revision 段 -->
