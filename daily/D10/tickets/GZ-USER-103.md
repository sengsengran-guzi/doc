# GZ-USER-103 — mp 跨境物流 C1 2 态 + 终态展示（只读侧；admin 写入由 D11 ADMIN-104）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §跨境物流（**PRD v0.x 文案是 7 节点，已被 C1 覆盖为 2 态 + 终态，PRD v1.0 签字时同步**）
**关联拆解**: doc/02-需求拆解.md §3.4 ⚠️ **原 AC「7 节点时间线」已作废**；本 ticket 按 doc/10 §9 / doc/11 §6.4 / doc/12 §MP-ORD-DETAIL 的 C1 决策（2 态 + 终态）实施
**关联 mockup**: design/mockup/order-detail.html ⚠️ **当前文件是 7 节点时间线版本，作废待重画**；本 ticket 按 doc/12 §MP-ORD-DETAIL §页面结构第 4 项「物流 2 态卡片」规范实施（不逐像素）
**关联 ADR**: doc/_adr/0005-cross-border-logistics-2state.md（C1 落地 + 「先做 2 态、验收前与甲方口头确认、事后补签合同 §2.1」记录；如不存在按 doc/10 §9 §跨境物流权威状态 C1 裁定实施）
**依赖**: GZ-USER-102（mp 订单详情统一页，已留 `<BizLogisticsCard>` 占位）

---

## 必读权威文档（缺一不可 — 本 ticket C1 颠覆原「7 节点」AC，§0 自检必读以下三处）

> 业务流 + 字段表是实施蓝图，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §跨境物流权威状态（C1 裁定，2026-05-26）全表（L1/L2/L3 三态定义 + 裁定要点）+ §状态机（logistics_status 跨业务通用）N1/N2/N5/N6（只读侧关注态来源，不实现 admin 推进 N2/N8/N9）
- **字段表**：doc/11-字段权威表.md **§6.4 物流字段说明（C1 简化后）** + **§6.3 `gz_ord_order`** 物流字段（`logistics_status` / `cn_carrier_code` / `cn_tracking_no` / `delivered_time`）+ **§7.4 `gz_gacha_order`** 同名物流字段 + **附录 A.7 物流状态字典（3 项）** + **§10.2 `gz_express_carrier` 快递公司字典（9 项枚举）**
- **UI 参考**（V1.1 设计走 C 日漫海报浓墨）：doc/12 §MP-ORD-DETAIL §页面结构第 4 项「物流 2 态卡片」（C1 裁定，**取消 7 节点时间线**）。视觉走 C 系统：`src/components/biz/Biz*` 原子组件 + `var(--c-*)` token（doc/tokens.md + doc/13），旧 mockup 仅布局参考、不逐像素：
  - 态 1 `in_japan`：文案「商品在日本备货中」+ 副文「我们会在合批后统一发货」，**无可操作元素**
  - 态 2 `in_china_dispatching`：文案「已发往中国」+ 快递公司中文名 + 快递单号 + 「复制单号」按钮 + 提示「请到快递公司官方渠道查询轨迹」
  - 态 3 `delivered`：终态「已签收」+ 签收时间，历史快递公司 + 单号保留可见

## What

实装 mp 端订单详情页内的物流卡片组件 `BizLogisticsCard.vue`（USER-102 已留占位）：按统一订单 VO 的 `logisticsStatus` 字段渲染 C1 的 3 种卡片（**不是 7 节点时间线**），态 2 提供「复制单号」（`uni.setClipboardData`）。**只做 mp 读取 + 渲染**，不实施 admin 写入（推进 + 录单号在 D11 ADMIN-104，且下沉 mp 店员端）。

## AC（验收标准）

- [ ] **AC 1**：`BizLogisticsCard.vue` 接收 props：`{ logisticsStatus: 'in_japan' | 'in_china_dispatching' | 'delivered', cnCarrierCode?: string, cnTrackingNo?: string, deliveredTime?: string }`（字段名对齐 doc/11 §6.4 时间命名钉死：签收时间是 `delivered_time` → VO `deliveredTime`，**禁用 `deliveredAt`**）
- [ ] **AC 2**：态 1（`in_japan`）渲染 —— 大字「商品在日本备货中」+ 副文「我们会在合批后统一发货」；**无任何操作按钮、无时间线 / 节点 UI**；卡片走 C 系统粗墨边 + 硬投影（BizPanel），底色用 `var(--c-*)` token，不硬编码 hex
- [ ] **AC 3**：态 2（`in_china_dispatching`）渲染 ——
  - 大字「已发往中国」
  - 显示快递公司中文名（按 `cnCarrierCode` 经 `gz_express_carrier` 映射，如 `sf` → 「顺丰速运」）+ 快递单号 `cnTrackingNo`
  - 「复制单号」按钮（BizButton，主色 `var(--c-red)` C 套粗墨边 + 硬投影）：点击调 `uni.setClipboardData({ data: cnTrackingNo })` 成功后 toast「已复制」
  - 提示文案「请到快递公司官方渠道查询轨迹」
- [ ] **AC 4**：态 3（`delivered`）渲染 ——「已签收」+ `deliveredTime` 格式化为 `YYYY-MM-DD HH:mm`；历史快递公司中文名 + 单号保留可见（**不显示复制按钮**，已是历史信息）
- [ ] **AC 5**：快递公司中文映射 —— mp 端 `composables/useExpressCarrier.ts` 内置 `code → name` 静态映射表，9 项严格对齐 doc/11 §10.2 `gz_express_carrier`：`yto`=圆通速递 / `sf`=顺丰速运 / `zto`=中通快递 / `yunda`=韵达速递 / `jd`=京东快递 / `ems`=EMS / `debang`=德邦 / `jitu`=极兔速递 / `other`=其他；遇未知 / 空 code 兜底显示「其他」。**不实时调字典接口**（9 项稳定 + 离线友好）
- [ ] **AC 6**：USER-102 详情页中 `<BizLogisticsCard>` 占位接入真实 props —— 从 USER-101 统一订单 VO 透传 `logisticsStatus` / `cnCarrierCode` / `cnTrackingNo` / `deliveredTime`，不另起接口
- [ ] **AC 7**：**本 ticket 不新增后端接口、无 DDL** —— 物流字段已由 USER-101 统一 VO（doc/11 §8.1 同名字段）暴露；后端侧仅核对 USER-101 VO 已含上述 4 字段（缺则回 USER-101 补，不在本卡新建表 / 接口 / 迁移）
- [ ] **AC 8**：`logisticsStatus` 独立于 `businessStatus` 并行渲染 —— 业务状态 chip 由状态卡负责，物流卡只渲染物流态，二者并存不互相覆盖（doc/10 §9 裁定要点：扭蛋订单可 `business_status=drawn` + `logistics_status=in_japan` 同时存在）
- [ ] **AC 9**：**不渲染 7 节点时间线 UI、不引物流时间线色 token、不引第三方轨迹库**（C1 一票否决；C 系统无单列时间线色段，无时间线 UI 故不需要；不引快递 100 / 快递鸟，用户复制单号自查）
- [ ] **AC 10**：i18n 全覆盖 —— 可见文案走 `t('order.logistics.xxx')` + `zh_CN` / `en_US`，盲盒语义不涉及（物流域）；不混 emoji（「复制单号」按钮文字不带 emoji）
- [ ] **AC 11: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）—— Kevin 从已上线首页 → 底部「我的」tab → 「我的订单」→ 列表点任一订单进 USER-102 详情页，下滑即见物流卡（USER-102 已建详情入口，本卡只是实装其占位组件，无需新增临时入口）。**联调态切换走「手动改 DB」**（D11 ADMIN-104 未交付前无写入 UI）：
  ```sql
  UPDATE gz_ord_order SET logistics_status='in_china_dispatching', cn_carrier_code='sf', cn_tracking_no='SF1234567890', cn_dispatched_at=NOW() WHERE order_no='PREORD-...';
  UPDATE gz_ord_order SET logistics_status='delivered', delivered_time=NOW() WHERE order_no='PREORD-...';
  ```
  进详情验 3 态渲染正确 + 态 2 复制按钮工作。

## Tech（端 + 范围）

- **小程序**（主体）：`code/main/miniapp/src/`
  - `components/biz/BizLogisticsCard.vue`（USER-102 占位，本 ticket 实装）
  - `composables/useExpressCarrier.ts`（新建，`code → name` 静态映射 9 项 + `other` 兜底）
  - `lang/zh_CN/order.ts` + `lang/en_US/order.ts` 加 `order.logistics.*` keys
  - USER-102 详情页透传 props（接 `<BizLogisticsCard>` 占位）
- **后端**：本 ticket **不动后端、无 DDL、无迁移文件**；仅核对 USER-101 统一 VO 已暴露 `logisticsStatus` / `cnCarrierCode` / `cnTrackingNo` / `deliveredTime`（doc/11 §8.1）。如需新建迁移（不应出现）按 `V<时间戳>__GZ-USER-103-<desc>.sql`（时间戳 > V202606051200）—— 本卡范围内不触发
- **测试**：mp vitest unit（`useExpressCarrier` 映射 9 项 + 兜底 / `deliveredTime` 格式化）；联调走 AC 11 手动改 DB 三态验渲染

## 备注

### 强约束（每条 C1 / 命名硬约束复核）

1. **不画 7 节点时间线**（C1 一票否决）：任何「待采购 / 日本备货 / 日本发出 / 国内清关 / 国内仓 / 国内派送」中间节点 UI 全部不实现，只 3 态卡
2. **不引快递 100 / 快递鸟等第三方轨迹抓取**（合同 §2.3 强约束 #14）：用户点「复制单号」自行去快递公司官网查
3. **复制单号走 `uni.setClipboardData`**：不引外部库（合同附件二腾讯云全栈合规）
4. **快递公司字典硬编码 9 项 + other 兜底**：与 doc/11 §10.2 `gz_express_carrier` 完全对齐（`yto`/`sf`/`zto`/`yunda`/`jd`/`ems`/`debang`/`jitu`/`other`）；未知 code 显示「其他」
5. **物流时间线色不使用**：C 系统未单列该色段（tokens 无 §1.5；§1.4 是稀有度色，与物流无关），C1 后无时间线 UI 故不需要
6. **Biz* 组件（不直接撒 `<wd-*>`）+ `var(--c-*)`**：视觉走 C 设计系统 token，主 CTA = `var(--c-red)`，卡片底色用 c 变量不硬编码 hex（doc/tokens.md + doc/13）
7. **`logisticsStatus` 独立于 `businessStatus`**（doc/10 §9 + 合同 §2.3）：业务态 chip 在状态卡、物流态在本卡，二者并存不互相覆盖
8. **时间字段命名钉死**：签收时间 prop 为 `deliveredTime`（对齐 doc/11 §6.4，业务态时间点用 `_time`，**禁用 `deliveredAt`**）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 3 态卡 vs 7 节点时间线 | C1 裁定（doc/10 §9 / doc/11 §6.4）；用户视角扁平简洁 |
| D2 | 快递公司映射前端静态表 | 9 项枚举稳定（doc/11 §10.2），不需实时查字典；省网络 + 离线友好 |
| D3 | 「复制单号」按钮仅态 2 显示 | 态 1 没单号；态 3 已签收单号保留可见但无需复制 |
| D4 | `deliveredTime` 格式化在 mp 端 | 标准 `YYYY-MM-DD HH:mm` 友好显示 |
| D5 | 本 ticket 不写后端测试 / 不建表 | 无新接口 / 无 DDL；字段在 USER-101 VO 已有，联调即验证 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | §0 自检误判上游已建 —— USER-101/102 实际未交付则物流字段无来源 | **§0 自检 grep migration 目录确认上游表实际存在**（`gz_ord_order` / `gz_gacha_order` 迁移文件 + 物流字段），并确认 USER-101 统一 VO 已暴露 4 个物流字段、USER-102 已留 `<BizLogisticsCard>` 占位；缺则 STOP 报 Kevin，不自行新建表 / 接口 |
| R2 | doc/02-需求拆解.md §3.4 仍写「7 节点 + 时间线色」误导后续 | 本卡标题 + 首段强调 C1 已覆盖原 AC；PRD v1.0 签字时同步 doc/02 |
| R3 | mockup `order-detail.html` 还是 7 节点版本，人验时误对照 | 旧 mockup 仅布局参考；视觉以 doc/tokens.md + doc/13 C 系统遵循度判定（不逐像素）；designer 6/16+ 重画（doc/12 §5.2 缺口） |
| R4 | ADMIN-104（admin 写入侧）D11 才做 → 本卡只能默认态 1 + 改 DB 验态 2/3 | AC 11 已锚定「手动改 DB 模拟态」联调路径；不阻塞本卡交付 |
| R5 | 误把 `delivered_time` 写成 `delivered_at` / `deliveredAt` | 强约束 #8 + AC 1 钉死；vitest 校验格式化函数入参名 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
- 问题 2：...
-->
