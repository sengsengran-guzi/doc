# GZ-UI-002 完工报告 — tabbar 3 套 C 风描边图标

**状态**: done-with-caveat（图标精度待 Tier-3 视觉签字）
**优先级**: P0（上线硬阻塞）
**端**: 小程序（miniapp）· 无后端 / 无 DB

---

## §0 状态自检

| 检查项 | 结果 |
|---|---|
| git | N/A（项目非 git 仓库，直接改文件） |
| 上游依赖（designer 出图） | 本票即出图 + 替换一体完成（自带光栅器生成） |
| 现状核实 | config.ts:42-57 三 tab 全指 `home.png/homeHL.png`（PASS，与 ticket 缺陷明细一致） |
| pngjs 可用 | `node_modules/pngjs` 存在（PASS） |
| 待删文件引用 | grep 确认 `example/exampleHL/scan/personal/personalHL.png` 全无代码引用（PASS） |
| verify-scan 不依赖 scan.png | `src/pages/bean/verify-scan.vue` 无 scan.png / tabbar 引用，走 wx.scanCode（PASS，可删） |
| 色值真源 | tokens.md §1.2：`--c-ink`=#1A1A1A、`--c-red`=#E73E2A、`--c-ink-2`=#5C5249（以真源为准，非 ticket prompt 的 #1A1714） |

---

## ⚠️ 诚实声明（Tier-3 视觉签字项）

**这 6 张是 AI 手画的几何 C 风图标**，由 `scripts/gen-tabbar-icons.mjs` 用 **pngjs + 自写极小光栅器**生成（本机无 SVG 光栅化器：sharp/canvas/magick/inkscape 全无）。
- 它们满足功能要求（三 tab 各异可辨 + C 风粗墨硬朗 + inactive 墨黑 / active 朱红 + 80×80 透明底），**解除 P0 上线阻塞**（不再三 tab 雷同靠文字区分）。
- 但**美术精度不是终版**：最终应由 Kevin / 真设计师走查精修（Tier-3 视觉签字）。
- **易替换路径**：真设计师产出同名 PNG 后 **drop-in 覆盖** `home.png/homeHL.png/bean.png/beanHL.png/me.png/meHL.png` 即可，**无需改 config.ts**。生成脚本 committed，可重跑微调几何参数。

---

## 改动文件清单

| 文件 | 改动 |
|---|---|
| `miniapp/scripts/gen-tabbar-icons.mjs` | 新建。pngjs + 自写光栅器（点-线段距离画粗线 + 扫描线填充多边形 + 描边/挖洞圆），生成 6 张 80×80 C 风图标，可重跑 |
| `miniapp/src/static/tabbar/home.png` `homeHL.png` | 重新生成：house ⌂（屋顶+墙体+门） |
| `miniapp/src/static/tabbar/bean.png` `beanHL.png` | 新增：调色盘 🎨（圆环+拇指孔+三颗拼豆点） |
| `miniapp/src/static/tabbar/me.png` `meHL.png` | 新增：人像 👤（头圆+肩身轮廓） |
| `miniapp/src/static/tabbar/example.png` `exampleHL.png` `scan.png` `personal.png` `personalHL.png` | **删除**（脚手架残留，无引用） |
| `miniapp/src/tabbar/config.ts` | nativeTabbarList 三项各指 home/bean/me 自己的 icon+HL；更新「图标策略」JSDoc（去占位措辞 + 注明 AI 几何 C 风待精修 + drop-in 路径） |
| `doc/tokens.md` §7.1 | 未选中色 `--c-ink` → `--c-ink-2`（#5C5249，对齐 config.ts/pages.json），注明图标 PNG inactive 用纯墨黑 |
| `doc/daily/D7x/tickets/GZ-UI-002.md` | 勾 AC |

**未动**（守边界）：pages.json（颜色数值 + tabBar.list 重生成留主线程构建）、其它 miniapp pages/components、后端、admin。

---

## 自测 raw output

### 1. 生成 6 张图标

```
生成 C 风 tabbar 图标 → .../src/static/tabbar
inactive(墨黑 #1A1A1A) + active(朱红 #E73E2A)，80×80 透明底：
  home.png     80x80  非透明像素=1714
  homeHL.png   80x80  非透明像素=1714
  bean.png     80x80  非透明像素=1653
  beanHL.png   80x80  非透明像素=1653
  me.png       80x80  非透明像素=1448
  meHL.png     80x80  非透明像素=1448
完成。⚠️ AI 手画几何图标，待 Tier-3 视觉签字（Kevin / 真设计师）；可同名 drop-in 替换。
```

### 2. 读回断言（width==80 && height==80 && 非透明像素>0 && 色调正确）

```
PASS home.png     80x80 非透明=1714 墨黑像素=1714
PASS homeHL.png   80x80 非透明=1714 朱红像素=1714
PASS bean.png     80x80 非透明=1653 墨黑像素=1653
PASS beanHL.png   80x80 非透明=1653 朱红像素=1653
PASS me.png       80x80 非透明=1448 墨黑像素=1448
PASS meHL.png     80x80 非透明=1448 朱红像素=1448

=== ALL 6 PASS (80x80 + 非透明像素 + 色调正确) ===
--- exit=0 ---
```

### 3. config.ts 三 tab 图标各不相同

```
iconPath: [ 'static/tabbar/home.png', 'static/tabbar/bean.png', 'static/tabbar/me.png' ]
selectedIconPath: [ 'static/tabbar/homeHL.png', 'static/tabbar/beanHL.png', 'static/tabbar/meHL.png' ]
PASS: 三 tab 图标各不相同
--- exit=0 ---
```

### 4. 删后无残留引用 + 目录干净

```
=== 删后剩余 ===
bean.png  beanHL.png  home.png  homeHL.png  me.png  meHL.png   （仅 6 张新图标）

PASS: example/scan/personal 全无引用
```

### 5. ASCII 形状预览（三套各异可辨）

- `home.png` = 房子：屋顶三角 + 墙体方框 + 实心门
- `bean.png` = 调色盘：圆环 + 右下拇指孔 + 三颗拼豆点
- `me.png` = 人像：头圆 + 肩身轮廓

---

## AC 勾稽

| AC | 状态 | 说明 |
|---|---|---|
| AC1 出图 | ✅ done-with-caveat | 6 张 80×80 透明底，inactive 墨黑 / active 朱红，三套各异；AI 几何图标待 Tier-3 精修 |
| AC2 替换 | ✅ | config.ts 三项各指 + 删脚手架（含额外删 personal.png/personalHL.png） |
| AC3 重生成验证 | ~ 部分 | config 已改；**不跑 build**（避免撞 mp agent dist，pages.json 重生成留主线程）；真机截图待 Tier 2 |
| AC4 doc 同步 | ✅ | tokens.md §7.1 未选中色对齐 `--c-ink-2`，不改 pages.json 数值 |
| AC5 Tier 2 可达 | ~ 待人验 | tabbar 常驻无新入口；待 Kevin 批量人验看图 |

---

## 对下游 / 主线程的提示

1. **pages.json 重生成**：本票只改 config.ts，未触发 `pnpm dev:mp-weixin`（避免与 mp agent 撞 dist）。主线程最终构建时 pages.json 会自动按新 config 重生成三 tab 各异的 iconPath/selectedIconPath。当前 pages.json 仍是旧的三 tab 同图状态，**属预期**，构建后即修正。
2. **真机截图（AC3 / AC5）** 进 Tier 2 批量人验：进小程序底部看 3 tab 图标各异、切换选中态朱红高亮。
3. **真设计师精修路径**：同名 drop-in 覆盖 6 张 PNG，无需碰 config.ts；或调 `scripts/gen-tabbar-icons.mjs` 几何参数重跑。
