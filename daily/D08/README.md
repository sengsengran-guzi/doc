# D08（Kevin 口径 d7）— V1.1 首日：业务支付通用化 + 预购全链路

> 日期：2026-06-16（周二）
> 阶段：**V1.1 实施期 day 1**（V1.0 已 6/15 上线运行中）
> 上一日：[D07](../D07/README.md) ｜ 下一日：[D09](../D09/README.md)

---

## 今日目标

- **主线 1**（业务支付通用化）：把 V1.0 仅"通道调通 HelloWorld"的微信支付升级为业务统一服务 — 统一订单号 / 创建预订单 / 回调幂等 + 主动查单补单 + 后台退款（owner 触发）（PAY-101 / 102 / 103）
- **主线 2**（预购全链路）：预购商品 + SKU 数据模型 → mp 商品列表 + 筛选 → 商品详情 + 下单确认 → 调起支付 + 订单生成 → 会员中心订单查询（ORD-101 / 102 / 103 / 104 / 105 — 共 5 个 ticket，预购业务线 A 在今日打通骨架）

完工后，V1.1 业务支付通用层就位 + 预购业务线 A 端到端可跑通（C 端浏览 → 下单 → 支付 → 出单 → 查单），为 D09 扭蛋（业务线 B）+ 物流模块铺路。

## Ticket 清单（8 个，按依赖图分波次）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-PAY-101 | 业务支付统一服务 | M | GZ-PAY-001 ✅ | pending |
| GZ-PAY-102 | 主动查单 + 补单 | S | GZ-PAY-101 | pending |
| GZ-PAY-103 | 退款服务（特例触发） | M | GZ-PAY-101 + GZ-ADMIN-103 ✅ | pending |
| GZ-ORD-101 | 预购商品 + SKU 数据模型 | M | GZ-SYS-001 ✅ | pending |
| GZ-ORD-102 | mp 商品列表 + 筛选 | M | GZ-ORD-101 + GZ-ADMIN-005 ✅ | pending |
| GZ-ORD-103 | mp 商品详情 + 下单确认 | M | GZ-ORD-101 + GZ-USER-003 ✅ | pending |
| GZ-ORD-104 | 预购下单 + 支付 + 订单生成 | M | GZ-ORD-103 + GZ-PAY-101 | pending |
| GZ-ORD-105 | 预购订单查询（C 端 + 后台基础） | S | GZ-ORD-104 + GZ-USER-101 ✅ | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图（严格按波次 spawn — 8 个 ticket 密度大，乱并行容易撞 schema / 撞回调链路）**：

```
波次 1（并行，互无依赖）：
   GZ-PAY-101 ━━━━━━━━━━━━━━━━━━━┓
   GZ-ORD-101 ━━━━━━━━━━━━━━━━━━━┫
                                  ┃
波次 2（PAY-101 完工后并行）：     ┃
   GZ-PAY-102 ──依赖 PAY-101 ─────┫
   GZ-PAY-103 ──依赖 PAY-101 ─────┃
                                  ┃
波次 3（ORD-101 完工后并行）：     ┃
   GZ-ORD-102 ──依赖 ORD-101 ─────┫
   GZ-ORD-103 ──依赖 ORD-101 ─────┫
                                  ┃
波次 4（PAY-101 + ORD-103 都完工后）：
   GZ-ORD-104 ──依赖 ORD-103 + PAY-101 ─┫
                                        ┃
波次 5（ORD-104 完工后）：              ┃
   GZ-ORD-105 ──依赖 ORD-104 ──────────┛
```

## 派单方式

**整日触发**（推荐 — 主线程读本 README → 严格按依赖图 spawn）：
```
开始 d7
```

**单 ticket 触发**（如某 ticket revision 闭环 / 局部重做）：
```
@coder 做 D08/GZ-PAY-101
```

主线程动作：
1. 读 D08/README.md（本文件）+ 依赖图
2. **波次 1**：并行 spawn GZ-PAY-101 + GZ-ORD-101（互无依赖）
3. **波次 2**（PAY-101 ✅ 后）：并行 spawn GZ-PAY-102 + GZ-PAY-103
4. **波次 3**（ORD-101 ✅ 后）：并行 spawn GZ-ORD-102 + GZ-ORD-103
5. **波次 4**（PAY-101 ✅ + ORD-103 ✅）：spawn GZ-ORD-104
6. **波次 5**（ORD-104 ✅）：spawn GZ-ORD-105
7. 8 个 ticket 全 ✅ → 主线程提示 Kevin testing-human + 日终 closing

⚠️ **不要乱并行**：波次 4 的 ORD-104 同时依赖 PAY-101 + ORD-103，**两者都未完工**前 spawn 必然踩坑（统一订单号格式没定 / 商品 snapshot 字段不齐）。AI 自己 §0 自检若发现上游未 merge → STOP 报 Kevin。

## 今日特殊约束

- **V1.1 首日，V1.0 已上线运行 1-2 周**（6/04 D06 完工 → 6/15 上线 → 6/16 V1.1 开工）。今日所有 ticket 在 V1.0 已稳定的基础上叠加，**不允许动 V1.0 已上线的代码路径**（拼豆预约 / 会员中心 / 资讯）除非 PAY-101 改 PAY-001 通用层需要回切（必须 Kevin 批准）
- **微信支付商户号必须已经审批通过**（V1.0 PAY-001 已通道调通 HelloWorld）。今日 PAY-101 起在 dev profile 仍用 sandbox / mock，staging 接真实商户号
- **业务支付统一订单号格式**（PAY-101 锚定，全 V1.1 后续 ORD/GACHA 均复用）：
  ```
  <业务前缀>-<yyyyMMddHHmmss>-<6 位序号>
  示例：preorder-20260616153012-000001
  业务前缀枚举：gacha / preorder / pindou-future（V1.1 拼豆暂不收费，但前缀预留）
  全局唯一（DB UNIQUE 约束）
  ```
- **4% 分成口径**（合同 §4.1 强约束）：两业务线 A（预定）/ B（扭蛋）分别核算，**不交叉冲抵**。ORD-104 落订单时必须把 `business_line` 字段写为 `preorder`（对账 SQL 按此分流），不允许混在通用订单表里靠业务前缀反推
- **退款 C 端无入口**（doc/02 §3.1 PAY-103 AC 4 + 合同 §4.5）：PAY-103 仅 owner 后台触发；mp 端订单详情页 **不允许** 出现"申请退款"按钮，仅显示"如需退款请联系客服"文案
- **订单状态机**（ORD-104 锚定）：`created → paid → in_logistics → delivered → closed`；`cancelled` 仅 `created`（未支付）态可达；其他态需走 PAY-103 退款流程
- **库存乐观锁**（ORD-101 锚定）：gz_ord_sku 表带 `version` 字段，扣减时 `UPDATE ... WHERE id=? AND version=?`；预购 SKU 库存可空（表示无限），可空时跳过乐观锁
- **商品 + SKU snapshot**（ORD-101 + ORD-103 + ORD-104 锚定）：下单时把当时的商品名 / SKU 规格名 / 单价分 / 主图 url 完整 snapshot 进 gz_ord_order 表，防止商品下架 / 改名 / 调价后历史订单显示异常
- **截止日逻辑**（ORD-103 锚定）：商品 `deadline_at` 已过 → 后台 cron 自动下架（status='off'）；用户已加购物车的需在提交时拦截 → 返回 errCode=`PRODUCT_OFF` + 前端提示「该商品已截止，请重选」
- **mp 端组件库** = wot-design-uni 默认（V1.0 设计冻结期已解除，但 V1.1 视觉规范以 6/14 风格统一调整后的为准）；今日如果还未拿到甲方最终视觉，**功能优先**继续走 wot 默认审美
- **admin 端**（PAY-103 退款按钮 / ORD-101 商品管理 CRUD / ORD-102 间接依赖 ADMIN-005 商品管理）走 ruoyi/Element Plus 默认审美 + 复用 V1.0 已有的 BizTable / Form 组件
- **DDL 文件命名**：本日 PAY-101 / ORD-101 落 DDL，严格按 `V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql` 放 `ruoyi-admin/src/main/resources/db/migration/`，时间戳必须 > V1.0 已上线的最大时间戳
- **i18n 强制**：mp 端 / admin 端可见字符串全走 `t('xxx.yyy')` + zh-CN 默认
- **不要 commit**：8 个 ticket 全部 ✅ + Kevin testing-human 通过后再统一 commit

## 与昨日 reports 对账（D07）

D07 `summary.md` 抓"对下游 ticket 的提示"段：
- ✅ V1.0 所有 ticket（PAY-001 / SYS-001/002/003/004/005 / BEAN-001~005 / USER-001~003 + USER-101 / NEWS-001~003 / ADMIN-005/103）已 6/15 上线，线上运行稳定
- ✅ gz_user / gz_user_address 表 schema 完整（ORD-103 选地址直接读 gz_user_address，无需新建表）
- ✅ ADMIN-103 后台订单详情骨架已就位（PAY-103 退款按钮叠加到该页面）
- ✅ ADMIN-005 商品管理 CRUD 骨架已就位（ORD-101 复用为预购商品管理 UI）
- ⏳ 微信支付商户号 staging 环境 cert 待 Kevin 在 6/16 上午导入（不阻塞 PAY-101 开发，dev profile 用 sandbox）
- ⏳ V1.1 物流模块 7 节点（合同 §2.3）拆到 D10 实现，ORD-105 今日仅占位"物流"模块入口（详情页空状态）

## 完成判定（DoD）

- [ ] 8 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 8 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] PAY-101 + PAY-102 在 dev profile 跑通：预购下单 → 调起 sandbox 支付 → 模拟回调 → 订单状态 paid（端到端 mock 流程）
- [ ] ORD-104 + ORD-105 在 mp 模拟器跑通：商品列表 → 详情 → 下单确认 → 跳支付 → 模拟支付成功 → 跳订单详情 → 状态显示 paid
- [ ] testing-human.md 全勾
- [ ] cat reports/*.md > summary.md 已生成

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | PAY-101 统一订单号格式与 V1.0 已上线的 PAY-001 HelloWorld 单不一致 | PAY-101 实施时检查 PAY-001 是否已有遗留订单号（理论上无 — HelloWorld 仅通道调通无真实业务订单），如有 → 留兼容字段 `legacy_order_no` |
| R2 | 8 个 ticket 同日完工密度过大，波次 4/5 时间被挤压 → ORD-104/105 草率收尾 | 严格按波次 spawn 不浪费时间；ORD-104 是 V1.1 第一个跨域事务（PAY + ORD），即使今日 §0 自检发现复杂 → 单独抽到 D09 头，不强压今日 |
| R3 | 微信支付回调幂等性写不对 → 同 transaction_id 重复处理导致订单二次状态变更 | PAY-101 AC 3 强约束：回调 handler 入口先 `SELECT FOR UPDATE` 订单行 + 检查当前 status，已 paid 则直接返回 success 不重复处理 |
| R4 | ORD-101 商品 + SKU snapshot 字段定义不齐，ORD-104 下单时漏字段 | ORD-101 实施时与 ORD-104 同步 review snapshot 字段清单（商品名 / 主图 / SKU 规格名 / 单价分 / 数量 — 至少这 5 个），写到 doc/11 §6.3 |
| R5 | mp 端商品列表筛选（IP / 作品标签）字段在 ORD-101 未定义 → ORD-102 实施时回退改 schema | ORD-101 schema 必含 `ip_tag VARCHAR(64)` + `series_tag VARCHAR(64)`（doc/11 §6.1 锚定），即使 V1.1 首日数据少也建索引 |
| R6 | 业务线 A 4% 分成核算 SQL 漏字段（如 business_line 没写） | ORD-104 落订单时强制 `business_line='preorder'`；对账 SQL 单独 D10/D11 写，今日只保证字段就位 |
| R7 | PAY-103 退款回调链路与 PAY-101 支付回调共用一个 endpoint → 容易混淆 | PAY-103 使用独立回调 endpoint `/api/wxpay/refund-notify`（PAY-101 是 `/api/wxpay/pay-notify`），路由 + 处理器分离 |

---

## 日终 closing 命令

```bash
cd doc/daily/D08
cat reports/*.md > summary.md
# Kevin testing-human OK 后再 commit
git add -A && git commit -m "D08 (d7): V1.1 业务支付 PAY-101/102/103 + 预购全链路 ORD-101/102/103/104/105"
# 然后写 D09/README.md（D09 候选：GZ-GACHA-101/102/103 + GZ-ORD-106 物流 + GZ-USER-103 物流模块）
```
