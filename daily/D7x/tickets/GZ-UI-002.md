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

- [ ] AC 1（出图，designer）：3 套 C 风粗墨描边 tab 图标，每套 inactive（墨黑 `--c-ink`）+ active（朱红 `--c-red`）各一张，共 6 张；80×80 PNG（透明底）；语义：首页 ⌂ / 拼豆 🎨（拼豆/调色盘意象）/ 我的 👤。视觉契合 C 系统（粗描边、硬朗），不用柔光渐变。
- [ ] AC 2（替换）：6 张图入 `src/static/tabbar/`（命名如 `home/homeHL`、`bean/beanHL`、`me/meHL`）；改 `src/tabbar/config.ts` 三项各自指向；删脚手架 `example.png`/`exampleHL.png`/`scan.png`（确认无引用后删）。
- [ ] AC 3（重生成 + 验证）：改 config.ts 后重启 dev（重生成 pages.json）；微信开发者工具 / 真机看三 tab 图标**各异可辨**，选中态朱红、未选中墨系，选中项文字 900 字重。贴三 tab 截图。
- [ ] AC 4（doc 同步，D-7）：tokens.md §7.1 写未选中色 `--c-ink`，但 config.ts 实现用 `--c-ink-2`（注释明示让未选中态柔和）。**designer 拍板口径**后改 doc 对齐代码（复盘优先级 §1 改权威蓝图），或调代码对齐 doc。本票顺手收口，不留口径分歧。
- [ ] AC 5（Tier 2 可达）：tabbar 全站常驻，无需新入口。Kevin 批量人验：进小程序底部看 3 tab 图标不再雷同，切换页面选中态朱红高亮正确。

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
