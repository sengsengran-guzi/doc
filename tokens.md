# 谷子宇宙 · 视觉 Token — C 日漫海报浓墨

> ⛔ **本文描述的视觉系统已整套退场，不得据此实现。**
>
> 现行小程序皮肤是 **「功能优先清爽」**（甲方 2026-06 改版拍板）：暖中性底 `#f4f2ed` + 白卡 + 柔和扩散阴影 + 圆角 + **单一品牌绿 `#33b36b`**；
> 粗黑描边 / 硬投影 / 直角 / 网点**已全站归零**（`--c-bw: 0`，令牌名 `--c-red` 仍在但值已是绿）。
>
> **唯一色值/尺寸真源**：`code/main/miniapp/src/style/c-tokens.scss` + `code/main/miniapp/uno.config.ts`（两处必须一致；组件禁止硬编码 hex）。
> token 速查见 [doc/12-UI-权威索引.md](12-UI-权威索引.md) §0.6；设计语义见 `design/design_handoff_clean/README.md`。
>
> 本文与 [doc/13-设计语言-C日漫浓墨.md](13-设计语言-C日漫浓墨.md) 仅作**历史设计记录**保留。

---

> 小程序唯一皮肤：米白纸 + 墨黑粗描边 + 朱红 + 硬投影（无虚化），漫画分镜 / 号外报纸气质。
>
> **适用范围：仅 miniapp（C 端微信小程序）**。后台 admin 走 ruoyi / Element Plus 默认审美，**不适用本设计系统**。
>
> **唯一色值/尺寸真源**：`code/main/miniapp/src/style/c-tokens.scss`（CSS 变量 + 全局组件类）与 `code/main/miniapp/uno.config.ts`（`theme.colors.c` 镜像 + 字号别名 + shortcuts）。两处必须一致。本文是「设计语义说明」，数值与真源逐一对齐；改色改尺寸先改真源、再回写本文，组件里禁止硬编码 hex。
>
> 设计原则与「怎么用」见 [doc/13-设计语言-C日漫浓墨.md](13-设计语言-C日漫浓墨.md)。
>
> **单位**：设计稿 375pt 基准，`px → rpx 取 ×2`。本文色卡给 hex（设计语义），尺寸给 rpx（小程序实际值），同时标注 CSS 变量名与 UnoCSS 类。

---

## 1. 色彩 Token

### 1.1 品牌色

| 语义 | Hex | CSS 变量 | Uno 类 | 用途 |
|---|---|---|---|---|
| 朱红 | `#E73E2A` | `--c-red` | `text-c-red` / `bg-c-red` | **主 CTA / 价格 / 高亮 / 选中态**（最高权重，全局唯一主行动色） |
| 朱红按下 | `#C8301E` | `--c-red-deep` | `text-c-red-deep` | 朱红按下态 |
| 竹绿 | `#2E8B3F` | `--c-green` | `text-c-green` / `bg-c-green` | 次级行动 / 成功 / 营业中 / 库存余量 |
| 鸟金 | `#F4C200` | `--c-yellow` | `text-c-yellow` / `bg-c-yellow` | 标签 / 利益贴纸 / 强调高亮（多用黑底金字或金底黑字） |
| 藏青 | `#1E4D8C` | `--c-blue` | `text-c-blue` / `bg-c-blue` | 资讯 / 链接 / 物流相关 |

**铁律：价格永远朱红（`--c-red`），绝不用竹绿。** 竹绿只承担次级行动 / 成功态 / 营业中 / 库存量。

### 1.2 中性色（纸与墨）

| 语义 | Hex | CSS 变量 | Uno 类 | 用途 |
|---|---|---|---|---|
| 页面底（米白纸） | `#F5F1E8` | `--c-bg` | `bg-c-bg` | 整页背景（带横线稿纸纹） |
| 卡片底（纸白） | `#FFFCF4` | `--c-paper` | `bg-c-paper` | 分镜框 / 顶栏 / CTA 条底 |
| 墨黑 | `#1A1A1A` | `--c-ink` | `text-c-ink` / `border-c-ink` | 粗描边 / 主文字 / 标题 / 黑底块 |
| 次墨 | `#5C5249` | `--c-ink-2` | `text-c-ink-2` | 辅助文字 / 说明 |
| 弱墨 | `#9A948A` | `--c-ink-3` | `text-c-ink-3` | 占位 / 禁用 |
| 浅描边 | `#E0D9C8` | `--c-line` | `border-c-line` | 纸面上的浅分割线 |

### 1.3 分镜彩纸底 tint（商品 / 角色占位的底色，写死 5 档）

| 语义 | Hex | CSS 变量 | 用途 |
|---|---|---|---|
| 粉 | `#FFE5F0` | `--c-tint-pink` | IP 占位 / 商品分镜底（随机分配，营造杂志彩页感） |
| 红 | `#FFE0DC` | `--c-tint-red` | 同上 |
| 蓝 | `#E8F4FF` | `--c-tint-blue` | 同上 |
| 黄 | `#FFF4D1` | `--c-tint-yellow` | 同上（也用于「到店须知」浅黄提示框） |
| 绿 | `#E5FFE9` | `--c-tint-green` | 同上 |

### 1.4 稀有度色（扭蛋 V1.1 用，先收口）

| 档位 | Hex | CSS 变量 |
|---|---|---|
| SSR | `#FFD700` | `--c-r-ssr` |
| SR | `#A663F4` | `--c-r-sr` |
| R | `#4A90E2` | `--c-r-r` |
| N | `#B8B2A6` | `--c-r-n` |

---

## 2. 描边 & 阴影（C 套灵魂）

C 套的辨识度全在「粗墨边 + 硬投影」。投影是**纯黑、无虚化、有偏移量**的硬阴影，不是 Material 那种柔光。

### 2.1 描边

| 语义 | rpx | px | CSS 变量 | 用途 |
|---|---|---|---|---|
| 粗描边 | `5rpx` | 2.5px | `--c-bw` | 分镜框 / 顶栏 / 主按钮 / CTA 条 |
| 中描边 | `4rpx` | 2px | `--c-bw-2` | 小卡 / 标签框 / 气泡 |
| 细描边 | `3rpx` | 1.5px | `--c-bw-3` | 座位格 / 图例 / outline 标签 |

描边颜色一律 `--c-ink`（墨黑）。

### 2.2 硬投影

| 语义 | 值 | CSS 变量 | 用途 |
|---|---|---|---|
| 分镜投影 | `8rpx 8rpx 0 #1A1A1A` | `--c-shadow` | 分镜框默认投影（4px 偏移） |
| 按钮投影 | `6rpx 6rpx 0 #1A1A1A` | `--c-shadow-btn` | 主按钮（3px 偏移） |
| 小元素投影 | `4rpx 4rpx 0 #1A1A1A` | `--c-shadow-sm` | 小卡 / 入口格 / chip（2px 偏移） |
| 选中态红投影 | `6rpx 6rpx 0 #E73E2A` | `--c-shadow-sel` | 日期 / 时段 / 座位「被选中」时投影换成朱红 |
| CTA 条上沿 | `0 -4rpx 0 rgba(0,0,0,.06)` | `--c-shadow-cta` | 底部固定 CTA 条上边缘 |

**按下态**：主按钮 `:active` 时 `transform: translate(3rpx, 3rpx)` 同时投影缩到 `3rpx 3rpx`，制造「被按进纸里」的物理感。
**选中态**：可选元素选中时，把硬投影颜色从墨黑换成朱红（`--c-shadow-sel`），并轻微位移 `translate(-1rpx,-1rpx)` 上浮。

---

## 3. 字号 Token

> 单位 rpx（小程序），px 为设计稿对照（rpx ÷ 2）。

| 语义 | rpx | px | CSS 变量 | Uno 类 | 用途 |
|---|---|---|---|---|---|
| 报头巨字 | `84rpx` | 42 | `--c-fs-hero` | `text-c-hero` | 首页报头巨字（「痛 · 入荷」） |
| 结果大字 | `56rpx` | 28 | `--c-fs-display` | `text-c-display` | 扭蛋出奖 / 大结果数字（V1.1） |
| 页面主标题 | `40rpx` | 20 | `--c-fs-h1` | `text-c-h1` | 漫画标题 MangaTitle / 步骤序号 |
| 区块标题 | `32rpx` | 16 | `--c-fs-h2` | `text-c-h2` | 平行四边形区块签 / 大按钮 |
| 强调正文 | `30rpx` | 15 | `--c-fs-lg` | `text-c-lg` | 强调正文 / 门店名 |
| 正文 / 按钮 | `26rpx` | 13 | `--c-fs-body` | `text-c-body` | 正文 / 按钮文字 |
| 副文字 / chip | `22rpx` | 11 | `--c-fs-sm` | `text-c-sm` | 副文字 / 气泡 / chip |
| 标签 / 说明 | `20rpx` | 10 | `--c-fs-xs` | `text-c-xs` | 标签文字 / 辅助说明 |
| 角标 / 编号 | `18rpx` | 9 | `--c-fs-2xs` | `text-c-2xs` | 角标 / monospace 编号 |
| 极小编码 | `16rpx` | 8 | `--c-fs-3xs` | `text-c-3xs` | `SCENE.01` / `STORE_01` 等编码小字 |

数字（价格 / 倒计时 / 余量）加 `.c-num`（`font-variant-numeric: tabular-nums`）对齐。

---

## 4. 间距 / 圆角

| 语义 | rpx | px | CSS 变量 | 用途 |
|---|---|---|---|---|
| 页面左右内边距 | `28rpx` | 14 | `--c-gap-page` | 页面横向 padding |
| 卡内边距 | `24rpx` | 12 | `--c-gap-card` | 分镜框内部 padding |
| 常规间隔 | `16rpx` | 8 | `--c-gap` | 元素间常规 gap |

**圆角：C 套基本直角（`--c-radius: 0`），追求海报 / 分镜的硬朗感。**

| 语义 | 值 | CSS 变量 | 用途 |
|---|---|---|---|
| 基础圆角 | `0` | `--c-radius` | 所有卡 / 按钮 / 标签默认直角 |
| 气泡圆角 | `36rpx 36rpx 36rpx 8rpx` | `--c-radius-bubble` | 对话气泡（唯一圆角特例，左下角收尖模拟气泡尾巴） |

例外：顶栏返回按钮、头像、稀有度圆点等「天生圆形」元素仍可用 `border-radius: 50%`。

---

## 5. 字体

| 语义 | 值 | CSS 变量 |
|---|---|---|
| 正文字族 | `'PingFang SC','Hiragino Sans GB','Heiti SC',system-ui,sans-serif` | `--c-font` |
| 编码 / 数字小字 | `'SF Mono','Roboto Mono',Menlo,monospace` | `--c-font-mono` |

漫画标题靠 `font-weight: 900` + 紧字距（`letter-spacing: -1rpx`）出粗黑效果；编码小字（`SCENE.01` / 日期 / 单号 / 国际单号）一律走 monospace，强化「号外报纸 / 机读」气质。

---

## 6. 组件类清单 ↔ Biz 组件

页面**不直接撒全局类**，统一走 `src/components/biz/` 下的业务组件（组件库无关纪律，见 [.claude/CLAUDE.md §7.5](../.claude/CLAUDE.md)）。下表是「全局类 → Biz 组件 → 用途」的对照。

| 全局类 | Biz 组件 | 用途 |
|---|---|---|
| `.c-screen` | `BizScreen` | 屏幕根容器：米白底 + 横线稿纸纹 |
| `.c-panel`（`--dashed` / `--sm` / `--ink` / `--flat` / `--accent`） | `BizPanel` | 分镜框：纸底 + 粗墨边 + 硬投影。一切内容容器的基座 |
| `.c-btn`（`--block` / `--lg` / `--sm` / `--green` / `--ink` / `--ghost` / `--disabled`） | `BizButton` | 主行动按钮：粗墨边 + 硬投影 + 900 字重 + 按下位移 |
| `.c-tag`（`--red` / `--green` / `--ink` / `--outline`） | `BizTag` | 标签：鸟金底黑字 / 反白墨底 / 描边款 |
| `.c-manga-title`（`--stroke`） | `BizMangaTitle` | 漫画粗黑标题，`--stroke` 加白描边 |
| `.c-section-title`（`__tag` / `__sub` / `__more`） | `BizSectionTitle` | 区块标题：黑色平行四边形签 + monospace 副标 + 「全部 →」 |
| `.c-step-title`（`__n` / `__date`） | `BizStepTitle` | 拼豆步骤标题（①②③ 朱红序号 + 标题 + 右侧日期） |
| `.c-speech` | `BizSpeechBubble` | 对话气泡（白底墨边 + 收尖圆角） |
| `.c-screentone`（`--fine` / `--wide` / `--light`） | `BizScreentone` | 网点底纹（绝对定位覆盖层，放分镜内） |
| `.c-burst` | （`BizScreentone` 的 burst 模式 / 局部用 class） | 集中线（径向，强调用） |
| `.c-topbar` | （未抽组件） | 自定义导航条样式类；V1.0 用**原生导航栏 C 配色**（pages.config.ts globalStyle）+ 页面内 `.masthead` 报头条（见 `pages/index/index.vue`），暂不单独抽组件 |
| `.c-cta-bar` | `BizFixedCta` | 底部固定 CTA 条 |
| `.c-mono` | （工具类，按需挂） | monospace 编码小字 |
| `.c-num` | （工具类，按需挂） | 数字 tabular 对齐 |
| `.c-price` | （工具类，按需挂） | 价格朱红大字 |

V1.1 待建 Biz 组件（出奖动画 / 物流时间线 / 核销码 / 概率条）详见 doc/13 的原子清单表。

---

## 7. 底部 tabbar 规范

### 7.1 V1.0：精简 3 tab

```
[ 首页 ]   [ 拼豆 ]   [ 我的 ]
   ⌂          🎨         👤
```

- V1.0 主打**拼豆预约**，故底部只放 3 tab。
- **扭蛋 / 预购属 V1.1，不占 tab**：V1.0 阶段从首页 teaser 卡片进入「ComingSoon 占位页」。
- **资讯不占 tab**：从首页资讯卡片进入资讯列表 / 详情。
- 选中态：图标 + 文字朱红（`--c-red` `#E73E2A`），文字 900 字重；顶部一道 30rpx 朱红短横标记选中项。
- 未选中：次墨（`--c-ink-2` `#5C5249`），600 字重 —— 比纯墨黑柔和，与原生 tabbar 文字色统一（口径对齐 `src/tabbar/config.ts` 的 `color` 与 `pages.json`）。
  图标 PNG 资源 inactive 态用纯墨黑 `--c-ink` `#1A1A1A`（粗墨描边视觉权重足，与柔和文字色搭配不冲突）。
- 底部留安全区（`env(safe-area-inset-bottom)`）。

### 7.2 V1.1：扩展 5 tab

```
[ 首页 ]   [ 扭蛋 ]   [ 预购 ]   [ 资讯 ]   [ 我的 ]
   ⌂          ○          □          ☰          ☻
```

V1.1 扭蛋 / 预购上线后，tabbar 扩到 5 个；资讯从首页卡片升格为独立 tab。结构与选中态规范不变。

---

## 8. 视觉避坑

1. **IP 占位规则**：所有二次元角色 / 商品图均为**占位**，用「彩纸 tint 底 + 角色剪影（`CharSilhouette`）+ `MOCK` 水印」表示，上线由甲方替换正版授权图。**文档与代码示例里不要把真实 IP 名当正式内容**，统一写「IP 占位」。
2. **价格永远朱红**：价格 / 倒计时 / 稀缺数字一律 `--c-red`，不用竹绿。
3. **网点 / 集中线克制**：网点（`.c-screentone`）`opacity` 控制在 0.12–0.25，只做底纹不抢内容；集中线（`.c-burst`）只在报头 / 出奖等强调位用，整页不超过 1–2 处。
4. **文案语气 = 适度二次元梗 + 去重日文**：保留中文二次元梗（谷子号外 / EXTRA、痛入荷、抽爆、欧皇 / 非酋、SCENE.01、围观），但重日文改中文（無料予約→免费预约、満→约满、朝/昼/夜→上午/下午/晚上、予約→预约）。完整对照表见 [doc/13](13-设计语言-C日漫浓墨.md)。
5. **不逐像素还原 mockup**：JSX 设计稿 / mockup 是「视觉语言 + 布局参考」，落地以 c-tokens.scss 的 rpx 数值为准，不追求逐像素复刻圆角 / 间距 / 阴影。
6. **不混 emoji 到正式 UI 文案**：emoji 仅限占位示意（如设计稿入口图标），正式上线图标走 iconify / 本地 SVG。
