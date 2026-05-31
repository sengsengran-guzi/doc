# GZ-USER-004 完工报告 — mp 我的订单 tab 占位结构

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅ 改动隔离于 me/orders + OrderListEmpty + api/types/order + gz-user.ts |
| 上游依赖 merge | ✅ GZ-USER-001（会员中心首页，九宫格「我的订单」入口）已实现 |
| 关键类/表存在 | ✅ 本 ticket 不动后端、不调 API（V1.0 占位） |
| 编译通过 | ✅ type-check 零新增；build 绿；vitest 通过 |
| ADR 已读 | 无相关 ADR |

**权威蓝图引用摘录**：
- doc/10 §4.N8：进入「我的订单」tab，V1.0 全部 tab 显示「暂无订单，敬请期待 V1.1」占位；预约不混入
- 合同 §2.1 第一期：订单聚合 tab 仅占位结构，业务线 A/B 订单数据待 V1.1 接入
- doc/12 §7 偏差 D3：mockup 4 tab（含拼豆）→ 按 PRD 删拼豆 tab，仅 全部/扭蛋/预购 3 tab

## 实现摘要

mp 新增/改动：
- `pages/me/orders.vue`（3 tab：全部/扭蛋/预购，纯前端切换，**不调任何 API**，占位空态）
- `components/biz/OrderListEmpty.vue`（空状态业务组件）
- `components/biz/OrderListEmpty.test.ts`（vitest 占位文案验证）
- `api/types/order.ts`（新增：OrderListVO 契约 VO 真源 — AC 5）
- `api/gz-user.ts` 加 getOrderList() 声明（V1.0 仅声明不实现，re-export OrderListVO）
- `locale/user.zh-CN.ts` 加 orders 段

**契约 VO 定齐（AC 5，V1.1 接入合同）**：
```ts
interface OrderListVO {
  orderId: string          // 业务码不暴露 id（跨层契约 #2）
  type: 'gacha' | 'preorder'
  amount: number; status: string; createdAt: string
  coverUrl?: string; title?: string
}
```
V1.1 直接复用，不允许 break 现有字段（只可加可选字段）。

**强约束落实**：
- 预约不混入订单 tab（独立「我的预约」入口走 BEAN-006 /pages/bean/my-list，USER-001 九宫格已暴露）
- 3 tab 删拼豆（doc/12 §7 D3）
- getOrderList 仅声明 TS 签名，V1.0 不调（避免后端误以为已接入）

## AI 自测

### 编译（type-check + build）
```
$ pnpm type-check → 本 track 零新增 TS 错（仅 2 个 pre-existing 历史债）
$ pnpm build:mp-weixin → dist 含 pages/me/orders.{js,json,wxml,wxss}
$ grep "pages/me/orders" dist/build/mp-weixin/app.json → pages/me/orders ✅
```

### 单测（vitest）
```
$ pnpm vitest run src/components/biz/OrderListEmpty.test.ts
 ✓ src/components/biz/OrderListEmpty.test.ts (1 test) 7ms
   - 渲染「暂无订单，敬请期待 V1.1」占位文案
```
> tab 切换交互（AC 7）：orders.vue 不 import getOrderList → 静态保证「不调 API」；
> 3 tab 切换纯 ref 状态，无网络。真机交互留 Kevin 批量人验。

### 可达性（Tier 2）
```
USER-001 九宫格「我的订单」→ ROUTE_MAP.orders='/pages/me/orders' ✅
本页从已上线「我的」tab 点九宫格可达，无需临时入口
```

## 风险提示 / 已知 issue

- R5（V1.1 接入契约不一致）：OrderListVO 已留 type/status 两个泛字段；V1.1 如需物流号/退款状态 → 加可选字段（不 break 现有契约）。契约真源在 api/types/order.ts 单点维护。
- R2（用户疑惑「为什么没拼豆」）：占位文案 + 「我的预约」入口在 USER-001 九宫格独立暴露，UX 路径清晰。
- 待 Kevin 批量人验关注（mp）：① 订单 tab 3 子 tab 切换 ② 三个 tab 全显示「暂无订单，敬请期待 V1.1」占位。

## 对下游 ticket 的提示

- V1.1 GZ-ORD/GZ-GACHA 接入：实现后端 `/app/gz/user/orders/list?type=` → orders.vue 按 activeTab 调 getOrderList（当前注释已标接入点）→ OrderListVO 直接复用零改字段。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ kevin-qa 无法 spawn（subagent 内 Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。主线程可决定是否补派复核。

### mp vitest
```
$ pnpm vitest run src/components/biz/OrderListEmpty.test.ts
 ✓ OrderListEmpty.test.ts (1 test) — 「暂无订单，敬请期待 V1.1」占位
全量 103 passed（无回归）
```

### type-check
```
本 track 零新增 TS 错；OrderListVO 契约 VO 在 api/types/order.ts 类型校验通过
```

### 契约层（V1.1 接入合同）
```
getOrderList GET /app/gz/user/orders/list（V1.0 仅声明不实现）
OrderListVO { orderId, type, amount, status, createdAt, coverUrl?, title? } 已定齐
orders.vue 不 import getOrderList → 静态保证「不调 API」（AC 3/AC 4）
```

### Tier 2 可达性
```
会员中心九宫格「我的订单」→ /pages/me/orders（USER-001 ROUTE_MAP 已配）→ 从已上线 tab 可达
```

**Tier 1B 结论：USER-004 ✅**（vitest + type-check + 契约定齐 + 不调 API 静态保证 + 可达性全绿）
