---
ticket: GZ-JP-301
track: SYS
phase: D6
size: M
req_refs: [REQ-SYS-001, REQ-SYS-002, REQ-SYS-003]
depends_on: [GZ-JP-108, GZ-JP-109, GZ-JP-205]
touches:
  - code/main/miniapp-jp/**
  - code/main/RuoYi-Vue-Plus/**
  - doc/**
blueprint_refs:
  - FLOW:F-JP-00.step4
  - FLOW:F-JP-02.step6
accept:
  - name: 现有小程序全量回归零变化（多 appid 改造未伤及线上）
    form: API
    run: cd code/main/miniapp && node test/e2e/run.mjs all
  - name: 新小程序全流程 E2E
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs all
  - name: 迁移全部应用且无 pending（两个小程序共用 ry-vue 一个库）
    form: DATA
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM flyway_schema_history WHERE success=0" | grep -qx 0
---

# GZ-JP-301 联调回归与上线

## §0 状态自检

1. 甲方侧四件行政事项状态：新小程序注册 / ICP 备案 / 海淘类目资质 / 商户号绑定新 appid。
   **备案与类目未过，只能到 staging 不能上 prod**。
2. `git status` 确认无未提交改动（部署流水线会自动 commit+push，先对齐）。

## What

- 新旧两个小程序全量 E2E 回归（★ **必须串行**，devtools 端口共享单例）
- 真机 1 分钱支付：**新旧各跑一遍**（GZ-SYS-022 动了收款链路）
- 微信发货信息上报验证（`upload_shipping_info`，拼团属实物商品）
- staging 双小程序并跑观察，再灰度 prod
- ~~补 `.claude/CLAUDE.md`~~ —— **已由 D0 的 GZ-DOC-003 完成**（menu 段 14000-14999 / 代码位置 / git 仓布局），本卡不再重复

## AC

- 现有小程序（拼豆 / 回收 / 店员核销）行为与改造前**完全一致**
- 新小程序端到端：首页 → 场 → 商品 → 购物车 → 下单 → 支付 → 订单跟踪 全通
- Flyway 无失败迁移

## 收尾纪律

关闭本会话期间自己起的所有后台任务（`mvn spring-boot:run` / `pnpm dev`），不留占端口的残留。
