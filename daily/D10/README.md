# D10 (Kevin 口径 d9) — V1.1 订单聚合 USER-101~104 + admin 前半 ADMIN-101/102/103

> 日期：2026-06-18（周四）
> 阶段：V1.1
> 上一日：D09 ｜ 下一日：D11

---

## 今日目标

- 主线 1（mp 串行链）：USER-101 订单聚合统一接口 → USER-102 订单详情统一布局 → USER-103 跨境物流 2 态简化展示 → USER-104 用户确认收货 + 自动签收
- 主线 2（admin 并行三件套）：ADMIN-101 预购商品 CRUD + ADMIN-102 扭蛋池管理 + ADMIN-103 订单管理（三类聚合）

## Ticket 清单（7 个，按依赖顺序）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-USER-101 | 订单聚合统一接口 | M | GZ-ORD-104 + GZ-GACHA-104 | pending |
| GZ-USER-102 | 订单详情统一布局 | M | GZ-USER-101 | pending |
| GZ-USER-103 | 跨境物流 2 态简化展示（C1 重定义，原"7 节点"已作废） | M | GZ-USER-102 + GZ-ADMIN-104(mp 端读) | pending |
| GZ-USER-104 | 用户确认收货 + 自动签收 | S | GZ-USER-103 | pending |
| GZ-ADMIN-101 | 预购商品管理 CRUD | M | GZ-ORD-101 | pending |
| GZ-ADMIN-102 | 扭蛋池管理 | M | GZ-GACHA-101 | pending |
| GZ-ADMIN-103 | 订单管理（三类聚合） | M | GZ-ORD-104 + GZ-GACHA-104 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖图**：

```
USER-101 ─→ USER-102 ─→ USER-103 ─→ USER-104       （串行链，mp 端）
                                                    （ADMIN-104 admin 推进侧 D11 才做，本日 USER-103 只做 mp 读取接口）

ADMIN-101 ┐
ADMIN-102 ├ 并行（互不依赖，独立 spawn）
ADMIN-103 ┘
```

## 派单示例

```
开始 d9                       # 主线程读本 README，按依赖顺序自动跑（先串行链，后并行 admin 三件套）
开始 d9/GZ-USER-101           # 单 ticket 启动
```

或显式分派：

```
@coder 做 D10/GZ-USER-101
@coder 做 D10/GZ-USER-102     # 上一个完工后
@coder 做 D10/GZ-ADMIN-101    # admin 三件套可并行 spawn
```

## 今日特殊约束

### 0. C1 决策一票否决 — USER-103 不是 7 节点

⚠️ **本 ticket 列表中 USER-103 原标题"跨境物流 7 节点展示"已作废**。doc/10 §9（跨境物流权威状态）+ doc/11 §6.4（物流字段 C1 简化后）+ doc/12 §MP-ORD-DETAIL 三处一致裁定：跨境物流 V1.1 实际是 **2 态 + 终态**（`in_japan` / `in_china_dispatching` / `delivered`），**不是 7 节点完整时间线**。

USER-103 任务卡按 C1 实施（即 2 态卡 + 国内单号 + 复制按钮 + 不画 7 节点时间线）。原 doc/02-需求拆解.md §3.4 第 876-888 行的 7 节点 AC 已被 C1 覆盖，本日按 doc/10/11/12 实施，待 PRD v1.0 签字时把 doc/02 同步对齐。

**实施口径速查**：

- mp 详情态 1（`in_japan`）：仅显示文案"商品在日本备货中"，无操作元素
- mp 详情态 2（`in_china_dispatching`）：显示快递公司 + 单号 + "📋 复制单号"按钮
- mp 详情态 3（`delivered`）：终态"已签收"
- **不使用物流时间线色**（C 系统未单列该色段，无时间线 UI，V1.1 不用）
- admin 端的录入/推进逻辑由 ADMIN-104 在 **D11** 实施；本日 USER-103 只完成 mp 端读取接口 + 渲染

### 1. 物流字段独立于业务状态

doc/02 §4.2 + 合同 §2.3 明确：`logistics_status` 字段独立于 `business_status`（业务状态），二者**并行存在**，不互相覆盖。例如扭蛋订单 `business_status = drawn`（已抽奖）和 `logistics_status = in_japan`（物流在日本）同时存在；UI 列表卡按 doc/11 §8.2 的"business_status → UI 统一状态映射"渲染，详情页则分别展示两者。

### 2. 跨境物流不自动抓取（合同 §2.3）

USER-103 实施不引入快递 100 / 快递鸟等第三方轨迹抓取库。**仅展示甲方手动推进的 2 态 + 国内单号**，用户点"复制单号"自行到对应快递公司官网/小程序查询轨迹。

### 3. 国内物流仅展示甲方录入单号（合同 §2.3）

USER-103 的国内单号字段（`cn_carrier_code` + `cn_tracking_no`）由 admin 在 D11 ADMIN-104 录入；本日 USER-103 实施前先确认 doc/11 §6.3 / §7.4 这两个字段已在表结构里（D08/D09 已建）。"复制单号"按钮调 `uni.setClipboardData`，不依赖外部库。

### 4. ADMIN-103 退款入口

ADMIN-103 订单详情有"申请退款"按钮，**仅 owner 权限可见**（staff 隐藏），点击触发 `GZ-PAY-103` 退款流。本日 PAY-103 已在 D08/D09 完工（如未完工，按钮先 disabled 显示 + tooltip"PAY-103 完工后可用"），不阻塞本日交付。

### 5. ADMIN-102 概率权重归一化

ADMIN-102 奖品池配置：**概率权重不强制总和 100，系统自动归一化**。表格每行右侧实时显示"归一化后概率（%）"列（前端 reactive 计算：`weight / sum(weights) * 100`，仅在池有库存奖品里计算），便于运营 sense check。

### 6. ADMIN-103 业务类型差异块

ADMIN-103 订单详情按业务类型展示差异块：
- 扭蛋订单：中奖物 snapshot + 机器名 + 稀有度
- 预购订单：商品 + SKU 规格 snapshot + 截止日 / 到货日 snapshot

差异块**复用 USER-102 的统一布局逻辑**（同一个统一 view-model），admin 端只是从 sa-token-staff 视角访问 + 多一个"申请退款"按钮。

### 7. 设计约定

- **admin（ADMIN-101/102/103）**：走 ruoyi/Element Plus 默认审美（不套用 C 系统）+ plus-ui BizTable，**不引用 mockup 像素**。mockup 仅作页面结构参考。
- **mp（USER-102/103/104）**：视觉走 C 日漫海报浓墨：Biz* 组件 + var(--c-*)，doc/tokens.md + doc/13；旧 mockup 仅布局参考。不逐像素。

## 与昨日 reports 对账

D09 完工后应交付：
- GZ-ORD-104 预购订单管理（订单建单 + 状态机），含 `gz_ord_order` 表 + 字段 `logistics_status` / `cn_carrier_code` / `cn_tracking_no`（doc/11 §6.3 落地）
- GZ-GACHA-104 扭蛋衍生订单管理，含 `gz_gacha_order` 表 + 同名物流字段（doc/11 §7.4）

进 D10 前主线程 §0 自检会校验这两张表 + 字段存在；缺则 STOP 报 Kevin（D10 不开工，先回 D09 收尾）。

D09 summary.md 中如有"对下游 ticket 的提示"段（统一订单 view-model 字段名 / 业务类型枚举值约定 / paid_at 字段命名），在 USER-101 实施前主线程逐条对齐。

---

## 日终 closing 命令

```bash
cd doc/daily/D10
cat reports/*.md > summary.md
git add -A && git commit -m "D10 (d9): V1.1 订单聚合 USER-101~104 + admin 前半 ADMIN-101/102/103"
# 然后写 D11/README.md（含 ADMIN-104 物流批次推进 / FIN 对账中心起步等）
```
