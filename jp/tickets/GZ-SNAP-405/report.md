# GZ-SNAP-405 实现报告

状态：DONE，2026-10-06。后端 `task/D11@56d60a6ef`；plus-ui `task/D11@997d36c`。无新迁移、不 push、不合 staging；主 miniapp 零修改、真煤炉请求 0。8090 复用主线程服务；后端只通过共享 restart 脚本重启。

## 实现

后端只新增履约列表投影 `source` / `snapTradeStatus`：原分页查询 LEFT JOIN 未删采购任务，DTO→VO 显式映射两字段，旧字段/排序/场筛选/付款闸均保持原样。

前端代切商品标「代切」，未 rated（包括没有采购状态）勾选格 disabled + tooltip「验货评价后才能推进」。表头选择仍用 Element Plus selectable，组内选择事件仍用既有 selection-change。rated 接回原批量推进/发货，终态守卫仍生效。新增固定文字中英两语言各 2 key；新增代码无 TS any、无依赖。

新增 `e2e/gz-jp/fulfill-board-snap.spec.ts` 两条；复用 401 API+fake/replay 夹具，用真实报价→提交→模拟支付回调生成 4 自造业务订单，API 标记购买成功→卖家已发货→到仓→评价。wx-login 只传 code。未直接 INSERT 代切业务表，未改用户资料/账号。

一期 fixture 安全修复：`fulfill-fixtures.ts` 原先删除 99101..99199 整段，现改为运行前检测准确 ID 与相关退款均未占用，不覆写既存数据；清理仅准确自造 ID+tenant/自然业务号，退款一起清理，清理后读回 0。Docker 用当前已核实绝对路径。

## 验证与 raw

1. `bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp`：默认沙箱写 ~/.m2 被拒（首轮尚未触重启）；授权 escalated 重跑 clean install exit 0，运行时列表两新字段在 UI 网络响应中断言。

```text
BACKEND UP (commit 08741d274+DIRTY-WORKTREE, branch task/D11)
Successfully validated 191 migrations (execution time 00:00.116s)
```

原始输出 `raw/restart.log`。无新增单测，不把 `-DskipTests` 的编译当单测通过；307 既有后端守卫真库证据由主线程复用。

2. 限定 eslint：`pnpm exec eslint src/views/gz-jp/fulfill/index.vue src/api/gz-jp/fulfill.ts src/lang/zh_CN.ts src/lang/en_US.ts e2e/gz-jp/fulfill-board-snap.spec.ts e2e/gz-jp/fulfill-fixtures.ts --fix` exit 0，raw 空输出。最终 spec 再定向 lint exit 0（`raw/lint-last.log`）。只格式化 ticket 文件。

3. `pnpm exec vue-tsc --noEmit` exit 2；实际 error TS 条数 72=基线72，涉及405的页面/API零错误。`raw/tsc.log`。prod build 主线程在 D11 末统一执行。

4. Accept #0 pass，实际覆盖8条：一期6条 + snap2条。按最新减少重复测试授权复用同产物已经通过的一期6条与未评价1条，仅重跑失败装置涉及的评价后1条。

首先执行 ticket 两 spec 命令：
`npx playwright test e2e/gz-jp/fulfill-board-snap.spec.ts e2e/gz-jp/fulfill-board.spec.ts --reporter=line`。
新 spec 首轮暴露隐藏 native input 的 check() 不能点击；改点击可见 `.el-checkbox`。第二轮 tooltip 遮挡表头，先移开鼠标并等 tooltip 消失再点击；这轮一期6条再次绿并完成清理读回（`raw/e2e-final.log`）。加强混合全选后暴露当前dev41行/默认20页，自造行不在首页；改 UI 页容量50。再用旧 UI 提示的用户编号筛选得到空，静态核实既有 `GzUserServiceImpl.selectIdsByKeyword` 实际只搜 nickname/mobile/openid、不搜userNo；本票不改旧行为，最终不传 keyword 并断列表包含所有自造 ID。

`npx playwright test e2e/gz-jp/fulfill-board-snap.spec.ts --reporter=line`：未评价1条 pass（`raw/e2e-snap.log`，第二条当时装置失败）。最终只运行：
`npx playwright test e2e/gz-jp/fulfill-board-snap.spec.ts --grep 'after rating' --reporter=line`：评价后1条 pass，14.5s（`raw/e2e-rated.log`）。

```text
6 passed (1.4m)                         # 一期6条，raw/e2e-final.log
1 passed (37.2s)                       # 未评价条，raw/e2e-snap.log 同时保留当轮失败详情
1 passed (14.5s)                       # 最终评价后条，raw/e2e-rated.log
fixtures: 4 API quote→submit→mock callback orders; gateway fake/replay; live Mercari=0
cleanup: 4 owned orders/items/tasks/payments/refunds removed; address and FX removed; 3 config values restored byte-for-byte; no account mutations
fulfill cleanup: exact owned IDs removed; orders/items/product/event/refund readback=0
```

产品断言：实时后台 list 响应 code200/source=snap、行ID及trade状态匹配；未评价/arrived源标签、disabled、tooltip、全选不能纳入未评价行；rated与未rated混合表头全选后未rated均未选，立即清空全部选择，只重新选准确自造rated ID。推进/发货 POST request.itemIds **严格等于 `[fixture.itemId]`**，DB fulfill_status 变 customs→delivered、tracking_no 精确一致，最终checkbox终态disabled。一期客人聚合/终态/跨客人/推进/跨订单同包发货/退款二次确认6条均通过。未修改其它既存订单行；混合全选阶段只有浏览器选择状态，未提交写请求。

## 文件与范围

后端4文件（全部 `ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/`）：
- `domain/dto/GzJpFulfillBoardRow.java`
- `domain/vo/GzJpFulfillBoardItemVO.java`
- `mapper/GzJpOrderItemMapper.java`
- `service/impl/GzJpFulfillServiceImpl.java`

plus-ui6文件：
- `src/views/gz-jp/fulfill/index.vue`
- `src/api/gz-jp/fulfill.ts`
- `src/lang/zh_CN.ts`
- `src/lang/en_US.ts`
- `e2e/gz-jp/fulfill-board-snap.spec.ts`
- `e2e/gz-jp/fulfill-fixtures.ts`

全部在 touches 范围内，OUT_OF_TOUCHES=none。doc report/raw 未 commit。后端剩余非本票 untracked `ruoyi-admin/logs/sys-error.2026-10-01.log180801896327291.tmp` 保留；未动它。plus-ui提交后干净（主线程后续build生成噪音由主线程管）。

## 下游与限制

独立 QA 请只看 ticket/蓝图/代码，不读本文实现解释。最终8条证据按上述分段复用，没有伪报一轮8条全绿。真实煤炉与支付只用了授权替身。旧编号搜索缺口单独留档，不扩405。后端守卫沿用307，未增资金出口；本票只读投影与选择预反馈。
