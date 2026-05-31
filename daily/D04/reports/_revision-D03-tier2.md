# D04 Tier 2 发现：D03 GZ-ADMIN-005 revision（mp 主体白屏 + customize warning）

> 时间：2026-05-29 15:55
> 触发：Kevin D04 Tier 2 真机走查 mp 端时发现 3 tab 主体白屏 + 4 个 console warning
> 处理人：kevin-coder
> 完整 revision 追加到 `doc/daily/D03/reports/GZ-ADMIN-005.md` §revision 段

## 摘要

- **根因（已定位 + 已修）**：`src/tabbar/config.ts` 用 `#ifdef MP-ALIPAY` 在 .ts 文件里包 `customize` 字段；条件编译对 .ts 不生效，导致 `customize: false` 漏进 mp-weixin app.json 触发 console warning
- **主体白屏的代码层根因**：未定位到（所有 dist 产物结构正常）；最可能是开发者工具产物缓存
- **修复**：改用 `process.env.UNI_PLATFORM === 'mp-alipay'` 运行时判断 → dist app.json 已无 `customize` 字段
- **Kevin 重测路径**：清开发者工具缓存 → 重启工具 → 重新打开 dist/dev/mp-weixin
- **如重测仍白屏**：贴 console Error tab + AppData 面板 + Wxml 面板 → 二次诊断

## 改动文件

- `code/main/miniapp/src/tabbar/config.ts`

## 防回归建议（待下一个 ticket 实施时顺手做）

- 跨日 prompt 模板（`.claude/agents/kevin-coder.md`）补一行底线："`#ifdef MP-*` 条件编译仅适用于 .vue / .scss / .css；.ts / .js 文件请用 `process.env.UNI_PLATFORM` 运行时判断"
- 或在 `tabbar/config.ts` 类似的"按平台分支"代码处加 lint 提示

## 没有 commit

按指令未 git commit；Kevin 决定是否纳入 D04 closing 时一起提交。
