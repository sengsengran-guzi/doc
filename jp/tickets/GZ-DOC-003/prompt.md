---
ticket: GZ-DOC-003
track: SYS
phase: D0
size: S
req_refs: [REQ-SYS-001, REQ-SYS-005]
depends_on: []
touches:
  - .claude/CLAUDE.md
blueprint_refs:
  - FLOW:F-JP-00.step1
accept:
  - name: menu 段位表已含 GZ-JP 14000 段
    form: API
    run: |
      grep -qE '14000\s*-\s*14999' .claude/CLAUDE.md && grep -q 'GZ-JP' .claude/CLAUDE.md
  - name: 代码位置表已含新模块与新小程序工程
    form: API
    run: |
      grep -q 'ruoyi-gz-jp' .claude/CLAUDE.md && grep -q 'miniapp-jp' .claude/CLAUDE.md
  - name: 已加「不主动计算商业口径」纪律
    form: API
    run: |
      grep -qE '不主动(计算|推算).*商业|商业.*不主动' .claude/CLAUDE.md
---

# GZ-DOC-003 CLAUDE.md 更新（★ 必须在 D1 之前做完）

## §0 状态自检

1. `grep -n "menu_id 分段" .claude/CLAUDE.md` —— 找到 §6 铁律 6 的段位表位置。
2. `grep -rhoE "\b14[0-9]{3}\b" code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/*.sql | sort -un` ——
   再确认一次 14000 段仍空（13000 段被 GZ-RECYCLE 占到 13053+13999）。

## What

**为什么这个 ticket 必须排在 D1 之前**：CLAUDE.md 是每个 subagent 开工必读的约定文件。
开发期间它要是过时的，派出去的 subagent 会读到错的 menu 段位约定——
**本项目 menu_id 已经撞过 3 次号**（GZ-BEAN-036 误用 6051-6055 删掉核销权限，
FLUSHDB 后才暴露，看板/核销/放座/延时全线 403）。这不是理论风险。

三处改动：

1. **§6 铁律 6 的 menu_id 分段表**新增一行：`14000-14999 | GZ-JP（日本拼团）`
   —— 并注明子段：14000 目录 / 14001 场 / 14010 商品 / 14020 订单 / 14030 履约看板

2. **§4 代码位置**新增：
   - 后端 `ruoyi-modules/ruoyi-gz-jp`（日本拼团 GZ-JP，包名 `org.dromara.gz.jp`）
   - 小程序 `code/main/miniapp-jp/`（谷子宇宙拼团，独立 appid，clientid = `mp-applet-gz-jp`）
   - Admin `plus-ui/src/views/gz-jp/`

3. **§12 输出风格新增一条纪律**：
   > **不主动计算商业口径 / 分成** —— 合同、报价、分成核算由 Kevin 自己谈，
   > 需要 AI 辅助时会明确提出。不要在每个需求分析里自动附带商业条款判断。

## AC

- 三处都改到，且 grep 断言全过
- 不破坏现有段位表的其他行
