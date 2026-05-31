# GZ-USER-103 — 跨境物流 2 态简化展示（C1 裁定，原"7 节点"作废）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §跨境物流（**v0.3 文案是 7 节点，已被 C1 覆盖，待 PRD v1.0 签字时同步**）
**关联拆解**: doc/02-需求拆解.md §3.4 第 876-888 行 ⚠️ **AC 描述"7 节点时间线"已作废**；本 ticket 按 doc/10/11/12 的 C1 决策（2 态 + 终态）实施
**关联 mockup**: design/mockup/order-detail.html ⚠️ **当前文件是 7 节点版本，作废**；本 ticket 按 doc/12 §MP-ORD-DETAIL §页面结构 第 4 项的 2 态卡规范实施，待 6/16+ designer 重画
**关联 ADR**: —（C1 裁定见 doc/11 Changelog v0.2 / doc/10 §9 §跨境物流权威状态）
**依赖**: GZ-USER-102 ✅(D10) + GZ-ADMIN-104（admin 推进侧 D11 才做，本 ticket 只读 mp 接口先实装）

---

## 必读权威文档（缺一不可 — 本 ticket C1 颠覆原 AC，§0 自检必读以下三处）

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §跨境物流权威状态（C1 裁定，2026-05-26）**全表**（L1/L2/L3 三态定义 + 裁定要点）+ §关键节点 N3-N6 + §异常分支 E1-E6
- **字段表**：doc/11-字段权威表.md **§6.4 物流字段说明（C1 简化后）**（2 态 + 终态 + cn_carrier_code/cn_tracking_no 字段口径）+ §A.7 物流状态字典（3 项简化）+ §A.7.2 `gz_express_carrier` 快递公司字典（9 项枚举）
- **UI 参考**：doc/12 §MP-ORD-DETAIL §页面结构 第 4 项 **物流 2 态卡片**（C1 裁定，**取消 7 节点时间线**）。视觉走 C 日漫海报浓墨：Biz* 组件 + var(--c-*)，doc/tokens.md + doc/13；旧 mockup 仅布局参考：
  - 态 1 `in_japan`：文案"商品在日本备货中" + 副文"我们会在合批后统一发货"，**无可操作元素**
  - 态 2 `in_china_dispatching`：文案"已发往中国" + 快递单号 + 快递公司 + "📋 复制单号"按钮，提示"请到快递公司官方渠道查询轨迹"
  - 态 3 `delivered`：终态"已签收"
  - **物流时间线色 V1.1 不使用**（C 系统未单列该色段，无时间线 UI 故不需要）

## What

mp 端订单详情页内的物流模块（USER-102 已留 `<BizLogisticsCard>` 占位），按 C1 简化 2 态 + 终态实施：根据 `logisticsStatus` 字段渲染 3 种卡片（不是 7 节点时间线）。复制快递单号到剪贴板。**本 ticket 不实施 admin 端推进逻辑**（ADMIN-104 在 D11）。

## AC（验收标准）

- [ ] **AC 1**：`BizLogisticsCard.vue` 组件接收 props：`{ logisticsStatus: 'in_japan' | 'in_china_dispatching' | 'delivered', cnCarrierCode?: string, cnTrackingNo?: string, deliveredAt?: string }`
- [ ] **AC 2**：态 1（`in_japan`）渲染：
  - 卡片底色 `var(--c-tint-green)` + border `var(--c-line)`（在途感）
  - 大字"商品在日本备货中"
  - 副文"我们会在合批后统一发货"
  - 无任何操作按钮、无时间线 UI
- [ ] **AC 3**：态 2（`in_china_dispatching`）渲染：
  - 卡片白底 + border `var(--c-line)`
  - 大字"已发往中国"
  - 显示：快递公司名（按 `cnCarrierCode` 查 `gz_express_carrier` 字典映射到中文显示名，如 `sf` → "顺丰速运"）+ 快递单号
  - "📋 复制单号"按钮：`bg var(--c-red)` 白字按钮（C 套粗墨边 + 硬投影，BizButton）；点击调 `uni.setClipboardData({data: cnTrackingNo})` + toast"已复制"
  - 提示文案"请到快递公司官方渠道查询轨迹"
- [ ] **AC 4**：态 3（`delivered`）渲染：
  - 卡片浅灰底
  - "已签收" + deliveredAt 时间
  - 显示历史快递公司 + 单号（不可复制，已是历史信息但保留可见）
- [ ] **AC 5**：**不渲染 7 节点时间线 UI**；不引入物流时间线色 token（C 系统未单列该色段，V1.1 无时间线 UI）
- [ ] **AC 6**：USER-102 详情页中 `<BizLogisticsCard>` 占位接入实际 props（从订单详情接口返回的 logisticsStatus / cnCarrierCode / cnTrackingNo / deliveredAt 字段透传）
- [ ] **AC 7**：本 ticket **mp 端只消费已存在的 USER-101/102 接口**，**不新增后端接口**（logisticsStatus 等字段在 USER-101 VO 里已有）
- [ ] **AC 8**：快递公司中文名映射：mp 端在 `composables/useExpressCarrier.ts` 写一个 `code → name` 静态映射表（按 doc/11 §A.7.2 字典 9 项 + `other` 兜底），不实时调字典接口（性能 + 离线友好）
- [ ] **AC 9**：i18n 全覆盖（`order.logistics.xxx`）
- [ ] **AC 10**：联调验：admin 直接改 DB（D11 ADMIN-104 之前没 UI） — `UPDATE gz_ord_order SET logistics_status='in_china_dispatching', cn_carrier_code='sf', cn_tracking_no='SF1234567890' WHERE order_no='...'`；mp 端进详情验 3 态切换渲染正确 + 复制按钮工作

## Tech（端 + 范围）

- **后端**：本 ticket 不动后端（字段在 USER-101 VO 里已有）
- **小程序**：`code/main/miniapp/src/`
  - `components/biz/BizLogisticsCard.vue`（USER-102 占位，本 ticket 实装）
  - `composables/useExpressCarrier.ts`（新建，code → name 静态映射）
  - `lang/zh_CN/order.ts` + `en_US/order.ts` 加 `order.logistics.*` keys
- **测试**：admin 手动改 DB 三态验证 mp 渲染

## 备注

### 强约束

1. **不画 7 节点时间线**（C1 一票否决）：任何"待采购 / 日本备货 / 日本发出 / 国内清关 / 国内仓 / 国内派送"中间节点 UI 全部不实现；只 3 态卡
2. **不引入快递 100 / 快递鸟等第三方轨迹抓取**（合同 §2.3 强约束 #14）：用户点"复制单号"自行去快递公司官网查
3. **复制单号走 uni.setClipboardData**：不引外部库（合同附件二腾讯云全栈合规）
4. **快递公司字典硬编码 9 项 + other 兜底**：与 doc/11 §A.7.2 完全对齐 — `sf`/`yto`/`zto`/`yunda`/`jd`/`ems`/`debang`/`jitu`/`other` 共 9 项；遇未知 code 显示"其他快递"
5. **物流时间线色不使用**（C 系统未单列该色段，C1 后无时间线 UI）
6. **Biz* 组件（不直接撒 wd-*）+ var(--c-*)**：视觉走 C 设计系统 token（var(--c-*)，主 CTA = var(--c-red)），卡片底色用 c 变量，不硬编码 hex（doc/tokens.md）
7. **logisticsStatus 独立于 businessStatus**（doc/02 §4.2 + 合同 §2.3）：UI 上业务状态 chip 在状态卡显示，物流状态在本组件显示，二者并存不互相覆盖

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 3 态卡 vs 7 节点时间线 | C1 裁定（doc/11 v0.2 Changelog）；用户视角扁平化简洁 |
| D2 | 快递公司映射前端静态表 | 9 项枚举稳定（doc/11 §A.7.2），不需要实时查字典；省网络 + 离线友好 |
| D3 | "复制单号"按钮态 2 才显示 | 态 1 没单号；态 3 已签收无需复制（但单号保留可见作历史） |
| D4 | deliveredAt 时间格式化在 mp 端 | 标准 `YYYY-MM-DD HH:mm` 友好显示 |
| D5 | 不在本 ticket 写后端测试 | 没有新接口；联调即测试 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | doc/02-需求拆解.md §3.4 第 876-888 行仍写"7 节点 + tokens §1.5 时间线色"误导后续 | 本 ticket 标题已改"2 态简化展示"；ticket 卡片首段强调 C1 已覆盖原 AC；6/10 PRD v1.0 签字时同步更新 doc/02 |
| R2 | mockup `order-detail.html` 还是 7 节点版本，testing-human 时 Kevin 误对照 | 旧 mockup 仅布局参考；已切 C 系统，视觉以 doc/tokens.md + doc/13 为准；物流卡视觉按 C 设计系统遵循度判定（不逐像素） |
| R3 | admin-104 未实施 → mp 端只能看态 1 + 通过改 DB 验态 2 | 本 ticket 联调走"手动改 DB 模拟态 2"路径，AC 10 已锚定 |
| R4 | designer 重画 mockup 是 6/16+ 任务（doc/12 §5.2 V1.1 缺口）| 本 ticket 不阻塞 designer；功能优先视觉后调 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
