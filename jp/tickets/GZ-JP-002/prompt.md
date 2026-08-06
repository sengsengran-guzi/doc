---
ticket: GZ-JP-002
track: SYS
phase: D2
size: M
req_refs: [REQ-SYS-004, REQ-SYS-005]
depends_on: [GZ-JP-001, GZ-SYS-020, GZ-SYS-023]
touches:
  - code/main/miniapp-jp/src/**
  - code/main/miniapp-jp/test/e2e/**
blueprint_refs:
  - FLOW:F-JP-00.step1
  - FLOW:F-JP-00.step3
accept:
  - name: 新小程序 wx-login 打通并落到独立 gz_user 行
    form: API
    run: |
      RESP=$(curl -s -X POST http://localhost:8080/app/gz/common/auth/wx-login \
        -H 'Content-Type: application/json' -H 'clientid: mp-applet-gz-jp' \
        -d '{"code":"e2e-jp-login"}'); \
      echo "$RESP" | jq -e '.data.token != null and .data.userId != null' >/dev/null
  - name: 模拟器 E2E 可达首页并渲染
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs smoke
---

# GZ-JP-002 新小程序登录打通 + E2E harness

## §0 状态自检

1. 后端已起且 GZ-SYS-020/023 已 merge（`curl localhost:8080/actuator/health` 或等价）。
2. 微信开发者工具已开「服务端口」，且 dist/dev 是**当前代码**构建产物 —— 
   ★ `dev:mp` 出 `dist/dev`、`build:mp` 出 `dist/build`，devtools import 的是 `dist/dev`，别搞混。

## What

- 打通新小程序的微信登录：请求带 `clientid: mp-applet-gz-jp`，后端按该 clientid 解析到新 appid
- 复制 `code/main/miniapp/test/e2e/` 到新工程并改 flows（页面路径、选择器）
- preflight 沿用原逻辑（devtools cli 存在 / dist 有 app.json / 后端健康），后端地址不变

## AC

- 新小程序登录后在 `gz_user` 落**独立一行**（app_id = 新 appid），与旧小程序同一人互不干扰
- `node test/e2e/run.mjs smoke` 绿

## ⚠️ 并发约束

devtools 自动化端口是**共享单例、禁并发**。两个小程序的 E2E **必须串行**，
CI 里排队跑，不能并行。这条写进新工程的 `test/e2e/README.md`。
