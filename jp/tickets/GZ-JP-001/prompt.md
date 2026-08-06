---
ticket: GZ-JP-001
track: SYS
phase: D2
size: M
req_refs: [REQ-SYS-001, REQ-SYS-005]
depends_on: []
touches:
  - code/main/miniapp-jp/**
blueprint_refs:
  - FLOW:F-JP-00.step1
  - UI:global.theme
accept:
  - name: 工程可构建出 dist 且 app.json 含预期页面
    form: API
    run: |
      cd code/main/miniapp-jp && pnpm install --frozen-lockfile >/dev/null 2>&1; \
      pnpm build:mp >/dev/null 2>&1; pkill -f 'cli -o' 2>/dev/null; \
      test -f dist/build/mp-weixin/app.json && \
      grep -q 'pages/index/index' dist/build/mp-weixin/app.json
  - name: clientid 与 appid 已切到新小程序（防复制残留旧值）
    form: API
    run: |
      grep -q "mp-applet-gz-jp" code/main/miniapp-jp/.env && \
      ! grep -rq "wx2f8b93e09703f07d" code/main/miniapp-jp/.env*
---

# GZ-JP-001 miniapp-jp 工程初始化

## §0 状态自检

1. **appid 策略：一期先用 `wxMOCK` 占位**（Kevin 2026-08-06 定）。真 appid 到位后按
   `doc/jp/phase-plan.md` 的「appid 回补清单」补做，**本 ticket 可正常 close**。
2. `ls code/main/miniapp/` —— 确认源工程结构完好，作为复制基线。

## What

从 `code/main/miniapp/` 复制裁剪出 `code/main/miniapp-jp/`（**同 repo**，Kevin 已定）。

**视觉基调 = 方案 A（延续现有）**，已由 Kevin 2026-08-06 拍板 —— `src/style/` **原样复制不改值**，
工期不增。组件禁止硬编码 hex，一律走 token 变量。

**保留**：`src/http/`（含 401 静默续期）· `src/store/token.ts` · `src/hooks/useAuth.ts` ·
`src/components/biz/` 的基础件（按钮/面板/弹层/图片/空态）· 登录与隐私协议合规件 · UnoCSS + 样式 token · vitest 配置

**删除**：拼豆 / 回收 / 扭蛋 / 资讯 / 店员端 全部页面与 api · 对应 Biz 业务组件 · 对应 locale

**改配置**：
- `.env`：`VITE_APP_CLIENT_ID=mp-applet-gz-jp`，`VITE_UNI_APPID=__UNI__GZJP01`
- `.env.development/.staging/.production`：`VITE_WX_APPID=<新appid>`，baseurl 沿用 `guzi.tianda.studio`
- 新 `private.<新appid>.key`（上传私钥，**不进 git**，加 .gitignore）—— mock 阶段跳过，回补时加
- tabbar：首页 / 我的（两格）

## AC

- `pnpm build:mp` 出 dist（注意：尾部唤 devtools cli 会假挂起，`pkill -f 'cli -o'` 即 exit 0）
- 全仓 grep 不到旧小程序的 appid 与 clientid 残留
- `pnpm type-check` 与 `pnpm lint` 绿
