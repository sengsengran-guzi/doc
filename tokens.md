# 谷子宇宙 · 视觉 Token v1（基于 V4 拍板版）

> 所有 mockup 必须在 `<style><:root>` 中引用本文件定义的变量，**不要硬编码颜色**。
> 来源：从甲方现有"谷子宇宙"小程序首页抠取主色，V4 已客户口头认可。

---

## 1. 色彩 Token

### 1.1 品牌色

| Token | Hex | 用途 |
|---|---|---|
| `--brand-primary` | `#5BC85F` | 主 CTA / Logo / 高亮 / 库存条 / 主要图标 / 选中态 |
| `--brand-primary-deep` | `#3DAE43` | 主色按下态 / 强调文字 / 边框深 |
| `--brand-primary-soft` | `#E8F8E9` | 主色 8% 浅染（卡片底 / chip 底 / 跑马灯底） |
| `--brand-accent` | `#FFC72C` | 辅助黄：标签 / 二级 CTA / 利益贴纸 / Banner 强调 |
| `--brand-accent-deep` | `#F2A900` | 辅助黄按下态 |

### 1.2 功能色

| Token | Hex | 用途 |
|---|---|---|
| `--price` | `#FF4B4B` | 价格 / 倒计时数字 / 稀缺数字 / 删除/危险动作 |
| `--price-deep` | `#E03333` | 价格强调态 / 按下 |
| `--success` | `#5BC85F` | 同 brand-primary（不再单独定义） |
| `--warning` | `#FFC72C` | 同 brand-accent |

### 1.3 中性色

| Token | Hex | 用途 |
|---|---|---|
| `--bg` | `#F7F8FA` | 页面底色（整页背景） |
| `--card` | `#FFFFFF` | 卡片白底 |
| `--ink` | `#1F1F1F` | 正文 / 标题 |
| `--ink-2` | `#5C5C66` | 次级文字 / 辅助说明 |
| `--ink-3` | `#9A9AA3` | 弱文字 / 占位 / 已禁用 |
| `--line` | `#ECECEF` | 分割线 / 卡片边框 |

### 1.4 稀有度色（卡牌四档，写死）

| Token | Hex | 用途 |
|---|---|---|
| `--r-ssr` | `#FFD700` | SSR 金（边框 + 角标） |
| `--r-sr` | `#A663F4` | SR 紫 |
| `--r-r` | `#4A90E2` | R 蓝 |
| `--r-n` | `#C0C0C0` | N 灰 |
| `--r-ssr-soft` | `#FFF7D6` | SSR 卡背景渐变上端 |
| `--r-sr-soft` | `#F1E6FE` | SR 软底 |
| `--r-r-soft` | `#E5F0FB` | R 软底 |

### 1.4b 稀有度光晕（盲盒重画版新增，用于 draw / 拟物机器胶囊发光）

| Token | 值 | 用途 |
|---|---|---|
| `--rarity-glow-ssr` | `rgba(255,215,0,.55)` | SSR 揭晓光晕 / 金胶囊发光 |
| `--rarity-glow-sr`  | `rgba(166,99,244,.45)` | SR 揭晓光晕 |
| `--rarity-glow-r`   | `rgba(74,144,226,.35)` | R 揭晓光晕 |
| `--rarity-glow-n`   | `rgba(192,192,192,.25)` | N 揭晓光晕 |

### 1.5 物流时间线色（订单详情用）

| 状态 | 颜色 |
|---|---|
| 已完成节点圆点 + 连线 | `--brand-primary` |
| 当前节点圆点 | `--brand-primary` + 外圈光晕 `rgba(91,200,95,.25)` |
| 未完成节点圆点 + 连线 | `--ink-3` (`#9A9AA3`) |
| 异常 / 卡单节点 | `--price` (`#FF4B4B`) |

---

## 2. 字号 Token

> 小程序内字号偏紧凑，对齐拼多多/淘宝信息密度。

| Token | px | 用途 |
|---|---|---|
| `--fs-display` | 30 | 价格大数字 / 抽奖结果数字 |
| `--fs-h1` | 16 | 页面主标题（商品名 / 机器名） |
| `--fs-h2` | 14 | 区块标题（"奖品池" "热销"） |
| `--fs-body` | 13 | 正文 / 按钮文字 |
| `--fs-sm` | 11 | 副文字 / chip / 倒计时 |
| `--fs-xs` | 10 | 标签文字 / 辅助说明 |
| `--fs-xxs` | 9 | 标签内 / 极小辅助 |

字体：`'Noto Sans SC', system-ui, sans-serif`；数字加 `font-variant-numeric: tabular-nums`（用 `.num` class）。

---

## 3. 间距 Token (spacing)

> 用 Tailwind 默认间隔（4px 基准），不另起一套。

| 场景 | 值 |
|---|---|
| 页面左右内边距 | `px-3` (12px) |
| 卡片内边距 | `p-3` (12px) |
| 卡片之间垂直间隔 | `mt-3` (12px) |
| 区块标题与内容间隔 | `mb-2.5` (10px) |
| 标签之间 | `gap-1` (4px) |
| 按钮内文字行距 | `mt-0.5` (2px) |
| 底部 fixed CTA 条上方留白 | `mb-32` (128px，给 CTA 让位) |

---

## 4. 圆角 Token (radius)

| 场景 | Tailwind | px |
|---|---|---|
| 大卡片 / Banner | `rounded-lg` | 8 |
| 小 chip / 标签 | `rounded` | 4 |
| 极小标签（rarity-chip） | `rounded-[2px]` | 2 |
| 按钮 | `rounded-md` | 6 |
| 头像 / 圆点 | `rounded-full` | 999 |
| 进度条 | `rounded-full` | 999 |

---

## 5. 阴影 Token

| 场景 | 值 |
|---|---|
| 卡片 hover/常态 | `0 1px 3px rgba(0,0,0,.04)` |
| 底部 fixed CTA 条 | `0 -2px 12px rgba(0,0,0,.05)` |
| 主 CTA（绿）发光 | `0 2px 8px rgba(91,200,95,.45)` |
| SSR 金边光晕 | `0 1px 6px rgba(255,215,0,.25)` |
| 角标（红） | `0 2px 6px rgba(255,75,75,.3)` |
| 利益贴纸（黄） | `0 1px 2px rgba(255,199,44,.4)` |

---

## 6. 组件级共享 class（约定）

所有 mockup 都用以下命名（V4 已落定）：

| class | 用途 |
|---|---|
| `.frame` | 375px 视口容器 |
| `.status-bar` | 顶部 9:41 状态栏 |
| `.nav-bar` | 顶部导航 |
| `.num` | 数字 tabular |
| `.tag-green` / `.tag-yellow` / `.tag-red` / `.tag-outline` | 四种标签 |
| `.rarity-chip` + `.ssr/.sr/.r/.n` | 稀有度角标 |
| `.prize-card` + `.ssr/.sr/.r` | 奖品卡边框 |
| `.cta-single` / `.cta-ten` | 双 CTA 按钮 |
| `.countdown-num` | 倒计时黑底数字格 |
| `.scroll-marquee` + `.scroll-marquee-inner` | 跑马灯 |
| `.stock-bar-track` + `.stock-bar-fill` | 库存进度条 |
| `.section-bar` | 区块标题左侧绿条 |
| `.benefit-sticker` | 黄底利益贴纸 |
| `.badge-corner` | 卡片左上红色角标 |
| `.tabbar` + `.tabbar-item` + `.tabbar-item.active` | 底部 5 tab |
| `.fixed-cta-bar` | 详情/选择页底部固定 CTA 条 |
| `.timeline-node` + `.timeline-node.done/.active/.todo` | 物流时间线节点 |

---

## 7. 底部 5 tab 结构（统一规范）

```
[ 首页 ] [ 扭蛋 ] [ 预购 ] [ 拼豆 ] [ 我的 ]
  ⌂        🎰      📦      🎨      👤
```

- 高度 `h-14` (56px)
- 选中态：图标 + 文字 `--brand-primary-deep`
- 未选中：图标 + 文字 `--ink-2`
- 字号 10px，图标 20px
- 在所有"主路由级"页面出现：home / gacha-list / preorder-list / booking-select / me-home / news-list
- 详情页（gacha-detail / gacha-draw / preorder-detail / order-detail）**不**显示 tab，用 fixed CTA 条代替

---

## 8. 视口与 frame

```css
.frame {
  max-width: 375px;
  margin: 20px auto;
  background: var(--bg);
  min-height: 812px;
  box-shadow: 0 8px 32px rgba(0,0,0,.12);
  position: relative;
}
body { background: #DDD; }  /* 灰底衬托 375 视口 */
```

---

## 9. 文案/视觉避坑（V4 已确认 + 2026-05-18 盲盒大修订）

- 不写"必中 1 SR"等保底承诺 → 用"立省 21"等价值表达
- 价格永远 `--price` 红，绝不用品牌绿（绿色用于 CTA / 库存 / 高亮，不混淆为价格）
- SSR 不做呼吸动画（亮底克制版）
- IP 占位用 emoji，不用真实 IP 图（CHIIKAWA / 立牌 / 大毛绒 / 徽章）
- 概率公示默认折叠，"合规 / 实时归一化"双标签外露
- **盲盒语义（2026-05-18 大修订）**：
  - ❌ 抽奖 / 中奖 / 开奖 / 抽奖概率 / 中奖率
  - ✅ 扭蛋 / 开盒 / 获得 / 出现概率 / 出现率
  - 核心金句：「100% 获得，概率为获得对应商品的可能性」（区别抽奖"可能落空"）
  - 保留：奖品池（玩家圈通用）/ 概率公示（合规术语）
- **趣味性**（甲方明确要求）：
  - gacha-detail 必须有拟物扭蛋机（玻璃罩 + 胶囊 + 把手 + 出蛋口）
  - gacha-draw 必须三段分镜动画演示（转动 → 裂开光爆 → 揭晓稀有度光晕）
  - gacha-list 每个机器卡用立体迷你机器视觉，不是平面商品图
- **收集驱动**：
  - 每次开盒后强提示图鉴进度（伏笔 me-collection）
  - 集齐特典明示徽章奖励（玩家圈共识：集齐欲望 > 单抽欲望）
