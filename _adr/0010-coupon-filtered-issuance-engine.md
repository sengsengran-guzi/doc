# ADR-0010 优惠券「条件筛选发放」引擎（可配置定向 audience）

- 日期：2026-06-22
- 状态：Accepted
- 决策人：Kevin（甲方 V1.2 调整需求：「管理员可以自行配置发放策略，策略按甲方实际需求定制」）
- 关联：GZ-COUPON-001（券模板 / 用户券 / ICouponIssuanceStrategy SPI / manual 已实现）；doc/11 §优惠券域；冒烟测试 FINDING 7-3
- 落地批次：冒烟修复后续（条件筛选发放）

---

## Context

GZ-COUPON-001 已落地发放策略 SPI 骨架：`issue_strategy` ∈ `manual`（已实现，admin 选名单批量发）/ `register_window` / `event`（均为预留 stub，`issue()` 直接 throw）。券模板已带 `issue_config_json` JSON 列与 `CouponIssuanceEvent` 监听器骨架。

甲方反馈：发放策略不应是写死的三种，**管理员应能自行配置定向条件**（如「最近 30 天注册且做过拼豆的人」），策略随甲方实际营销需求变化。原「新人 / 注册时段 / 做过拼豆」只是举例，不是固定枚举。

核心问题：怎样让 admin **不改代码**就能配置定向发券的目标人群，且框架可随新需求扩展条件维度。

## Decision

引入 **「条件筛选发放」(`filtered`)** —— 通用 audience 条件框架：admin 组合条件 → 预览命中人数 → 立即批量发放。

### 1. 策略字典收敛

`gz_coupon_issue_strategy` 最终值：
- `manual` 手动指定名单（admin 勾选用户 / 关键词，已实现，不变）
- `filtered` 条件筛选（本 ADR 新增，可配置 audience）
- `event` 事件触发（仍预留：需甲方定义事件类型 + 在回收/拼豆模块挂 publisher，本轮不做）

**去掉 `register_window`**：其「注册时段」语义并入 `filtered` 的 `register_time` 条件，避免并列两个时间策略。

### 2. 条件框架（后端 ruoyi-gz-coupon）

- `ICouponAudienceCondition` SPI：`String type()` + `Set<Long> resolve(JsonNode config)`（返回命中 userId 集）。
- 本轮 3 个实现：
  - `register_time`：注册时间区间（`{start,end}`，含「新人=近 N 天」用相对今天的区间）
  - `did_pindou`：存在拼豆预约（`{completedOnly?}` 可选仅已完成/已核销）
  - `phone_bound`：`gz_user.status='phone_bound'`
- `CouponAudienceResolver`：解析 `issue_config_json.conditions[]` → 逐条件 `resolve` → **AND 交集**。预览与发放共用此解析器。
- `FilteredIssuanceStrategy implements ICouponIssuanceStrategy`（`supports()="filtered"`）：解析→交集得 userId 集→复用既有配额乐观锁（`increaseIssuedCount`）+ 批量插入（与 manual 共用插入 helper）。
- **组合逻辑仅 AND**；`filtered` 必须 ≥1 条件（防止零条件全量误发）。

### 3. 跨域依赖

gz-coupon **仅依赖 gz-common**（不新增对 gz-bean 的依赖）。条件数据查询走 `IGzUserService`：
- 注册时间区间 / status → 直接查 `gz_user`
- 做过拼豆 → 查 `gz_bean_booking` 的 distinct user_id（gz-common 的 dashboard mapper 已读该表，路径一致）

### 4. 预览 + 发放

- 预览端点 `POST /system/gz/coupon/template/preview-audience`（传 `conditions[]`）→ 返回命中人数；admin 配置时与发放前都可预览校验。
- 发放：`filtered` 模板的发放弹窗不选人，调既有 `/issue`（服务端按模板 `issue_config_json` 解析 audience）；`manual` 模板维持选人流程。

### 5. Admin（plus-ui）

- 发放策略下拉：手动指定 / 条件筛选（event 仍 disabled 预留）。
- 选「条件筛选」时出条件构建器（增删条件；register_time→日期区间、did_pindou→是否仅已完成、phone_bound→无参），序列化进 `issue_config_json`。
- 发放弹窗按策略分支：filtered→条件摘要 + 「预览命中 N 人」+ 确认发放；manual→维持选人表格。

## Consequences

- admin 自助配置定向发券，**新增条件维度 = 加一个 `ICouponAudienceCondition` 实现**（对扩展开放，对修改关闭）。
- AND-only 覆盖绝大多数营销场景；OR / 嵌套留后续按需。
- `event` 自动发放仍预留，待甲方定义事件类型后另起（§8.5 协商）。

### issue_config_json 结构

```json
{"conditions":[
  {"type":"register_time","start":"2026-05-01","end":"2026-06-30"},
  {"type":"did_pindou","completedOnly":true},
  {"type":"phone_bound"}
]}
```
