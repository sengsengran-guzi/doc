# GZ-UI-001 完工报告 — mp 视觉 token 收口 + 客服浮层换皮

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（按指令不做 git 操作） |
| c-tokens 真 token 存在 | ✅ `--c-red/--c-ink/--c-ink-2/--c-bw-2/--c-yellow/--c-shadow-btn/--c-line/--c-tint-green/--c-tint-yellow/--c-green/--c-fs-sm/--c-fs-lg/--c-fs-xs` 全部已定义 |
| 缺陷 file:line 核实 | ✅ 与 ticket 缺陷明细一致 |
| type-check | ✅ exit=0 |
| vitest | ✅ 114/114 全绿 |
| AC5 正则缺陷 | ✅ 已识别并修正 ticket（见下） |

## 实现摘要（纯改皮，零运行时逻辑）

| # | 文件 | 改动 |
|---|---|---|
| D-1 P0 | `BizCustomerServiceFab.vue` | 圆钮 `#ff6b81`→`var(--c-red)`；柔光 `box-shadow:0 4rpx 16rpx rgba(255,107,129,.35)`→硬投影 `4rpx 4rpx 0 var(--c-ink)` + `border:var(--c-bw-2) solid var(--c-ink)`；`:active` 柔光→`2rpx 2rpx 0 var(--c-ink)`；红点 `#faad14`→`var(--c-yellow)` + `2rpx solid var(--c-ink)`（原 `border:2rpx solid #fff`）。删冗余 `border:none`。 |
| D-3 P1 | `bean/verify-scan.vue` | 7 处伪 token：`--c-font-sm`→`--c-fs-sm`、`--c-ink-60`→`--c-ink-2`、`--c-accent-tint`→`--c-tint-green`、`--c-font-lg`→`--c-fs-lg`；成功框 `border-radius:8rpx`→`0`、`box-shadow:6rpx 6rpx 0`→`var(--c-shadow-btn)`。**理想已落地**：模板加竹绿状态条（`.verify__status` 用 `--c-green` 底 + `--c-bw-2 solid --c-ink` 描边 + ✓ 前缀），rows 包入 `.verify__body`，与 success.vue 核销凭证视觉对齐。 |
| D-4 P1 | `me/index.vue` | staff-badge `--c-font-xs`→`--c-fs-xs`、`--c-accent-tint`(粉)→`--c-tint-yellow`(鸟金系)、`border-radius:6rpx`→`0`。 |
| D-6 P2 | `BizSeatList.vue` | 满席态 `#e5e0d5`→`var(--c-line)`。 |
| D-cleanup P2 | `BizFixedCta.vue:21` / `login/index.vue:9` | JSDoc 旧 hex 注释（`#5BC85F`/`#FF6B81`）→ 改为 `var(--c-red)` 描述（不渲染，避免误导后人）。BizButton 经查无残留 hex 注释。 |

> 注：D-1 同文件的 `:show-message-card` 布尔修正归 GZ-SYS-008（type 修），此处 D-1 仅动 `<style>`。

## AC5 正则修正（复盘优先级 §1 — 改权威 spec）

**问题**：ticket 原 AC5 回归正则 `var\(--c-(...|ink-[0-9]|accent)` 用 `ink-[0-9]`（1 位数）→ **误伤真 token** `--c-ink-2`/`--c-ink-3`（全站 91 处合法用法全命中）。伪 token 实为 `--c-ink-60` 这类 **2 位数** 写法。

**修正**：收紧为 `ink-[0-9]{2}` → 只抓伪 token、不误伤真 token。已直接改 ticket AC5 + 注明原因。

证据：
```bash
# 旧缺陷正则 ink-[0-9] 误命中数：
grep -rnE "var\(--c-(font-(sm|lg|xs|body|h1|h2|hero)|ink-[0-9]|accent)" src | wc -l
# 91   ← 全是合法 --c-ink-2/3，全部误报

# 合法 --c-ink-2/3 用法计数（确认未被本票误删）：
grep -rcE "var\(--c-ink-[23]\)" src | grep -v ':0' | awk -F: '{s+=$2} END {print s}'
# 91   ← 与误报数完全吻合，证明误伤的全是真 token
```

## AI 自测（Tier 1A）

### AC5 修正后正则（src 全量，应零输出）
```bash
grep -rnE "var\(--c-(font-(sm|lg|xs|body|h1|h2|hero)|ink-[0-9]{2}|accent)" src
# 输出：(空)
# exit=1（1=无匹配=PASS，伪 token 清零）
```

### 逐个伪 token 残留扫描（应零输出）
```bash
grep -rnE "\-\-c-(font-sm|font-lg|font-xs|font-body|ink-60|accent-tint)" src
# 输出：(空)  exit=1（PASS）
```

### 残留旧 brand hex 扫描（#ff6b81/#faad14/#e5e0d5，应零输出）
```bash
grep -rniE "#(ff6b81|faad14|e5e0d5)" src
# 输出：(空)  exit=1（PASS）
```

### type-check + vitest（不回归）
```
> vue-tsc --noEmit
=== type-check exit=0 ===

 Test Files  17 passed (17)
      Tests  114 passed (114)
```

## 风险提示 / 已知 issue

- 纯 `<style>` + 模板属性改动 + verify-scan 模板加竹绿状态条容器（无 .ts 逻辑改动）。真机视觉契合度（朱红硬投影 / 竹绿状态条 / 鸟金徽章）留 Kevin Tier 2 主观评判。
- canvas 码点颜色（BizQrCode 内 `#1a1a1a`/`#9a948a` 字面量）**不在本票范围**（功能性高对比色，已在 BizQrCode JSDoc 标注随 c-tokens 同步，AC5 正则不含 canvas 字面量）。

## 待 Kevin Tier 2 批量人验（mp 端视觉）

- ⬜ 任意页右下角客服钮：朱红底 + 墨黑粗描边 + 硬投影（无虚化），按下投影缩位移
- ⬜ 绑定店员账号登 mp → 我的 tab 见鸟金店员徽章（直角、墨黑描边）
- ⬜ 店员中心「核销」→ verify-scan 扫码成功 → 成功结果框为竹绿状态条 C 风（对齐 success.vue）
- ⬜ 拼豆选座满席态座位为 `--c-line` 米灰（非旧 `#e5e0d5`）

## 对下游 ticket 的提示

- 旧 `--brand-primary` 时代 token（`--c-font-*` / `--c-ink-60` / `--c-accent-tint`）已全站清零，AC5 修正正则（`ink-[0-9]{2}`）可作后续回归 gate 模板，**勿退回 1 位数版**（会误伤 `--c-ink-2/3`）。
- 本票无新增临时入口（FAB/verify-scan/me 均现成入口，Tier 2 可达）。

## §AI 测试段（kevin-qa 完工后追加）

（本环境不 spawn subagent；Tier 1B 由主线程集成 gate 处理。占位）
