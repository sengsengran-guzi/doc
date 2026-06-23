# ADR-0012 回收预约「单份多选 + 去估价 + 数量桶映射时长 + 到店核销二维码」

- 日期：2026-06-23
- 状态：Accepted
- 决策人：Kevin（甲方 2026-06-23 沟通反馈 6 点 + Kevin 拍板，kevin-product 评估，kevin-coder 落地）
- 关联设计稿：[doc/15-V1.2-拼豆回收优化-设计.md](../15-V1.2-拼豆回收优化-设计.md) §0 / §4 / §5 / §6 / §7（本 ADR 钉死其中回收侧落库/契约决策）
- 关联 ticket：T4（回收单份多选 + IP 主数据 + 数量桶）/ T5（拍照声明 + 到店档 + 预计时间）/ T6（总量信息聚合详情 + 到店核销二维码）/ T7（IP/数量桶 seed + doc 回写）
- 落地批次：D18+（阶段 1 并行 T4/T5/T6，阶段 3 T7 收口）
- 配套阅读：拼豆侧 ADR-0011（1h 区间连续预约）同批出，结构对称；反向打款 ADR-0006（本 ADR 不动 payout 出账，仅复用）

---

## Context

V1.0/V1.1 回收预约（GZ-RECYCLE-001/002/003）按「估价驱动」建模：

- **价目表估价**：`gz_recycle_price_rule` 按 `(category, qty_min, qty_max)` 配单价 + 时长；提交时后端按各品类命中区间累加冻结 `estimated_amount_cent`（金额）/ `total_qty`（件数）/ `matched_duration_minutes`（时长）进预约单，前端实时展示估价。
- **多条明细**：`SubmitBo.products` 是 `List<ProductLine>`（每条 `{category, qty, ip?, remark?}`），`product_snapshot_json` 落库为 **JSON 数组**；IP 为前端硬编码 5 个、纯透传不入库不参估价。
- **数量自由整数**：用户填精确件数，估价按件数 × 单价。

甲方在 2026-06-23 沟通明确推翻这套估价模型，要求（设计稿 §0 点 2 / §4 / §5 / §6）：

1. **回收不做估价** —— 表单不再显示/计算金额；实际金额仅由店员到店核对时定 + 反向打款，线上不预估也不冻结金额。
2. **填一份**（单份多选）—— 一次预约 = 单个物品对象（品类多选 + IP 多选 + 用户自定义 IP + 数量桶单选 + 备注 + 图），取代「加多条明细」。
3. **数量桶**（1-25 / 25-50 / 50-75）取代精确件数；数量桶**只驱动「预计回收时间」**，不参与任何金额计算。
4. **IP 主数据可配** —— IP 后台 CRUD + mp 用户自加自定义文本；IP 纯标注，不进估价。
5. **回收预约生成到店核销二维码**（复用拼豆 `QrCodeSigner` 签名机制），店员扫码核对；**核销不限本店**（无门店权限隔离，设计稿 §0 点 3）。
6. **总量信息双端可见**（顾客窄 / 店员-admin 全量，设计稿 §6）。

核心设计问题：估价逻辑下线后 `price_rule` 表怎么处置？`product_snapshot_json` 从数组改对象如何不让线上历史回收单详情解析崩？数量桶→时长配置放哪？回收核销码签名因子怎么定？

**未冲击 4% 分成**：回收 payout 走 ADR-0006 独立 `business_type=recycle` 核算、不计 GMV，本 ADR 不动出账逻辑。

## Decision

### 1. 去估价 —— 表单/线上不算金额，价目表停用不删

- **mp 回收表单不再展示/计算任何金额**；提交不传金额、后端不重算、不冻结 `estimated_amount_cent`。
- **`estimateAll` / `IGzRecyclePriceRuleService.estimate` 估价逻辑下线**：service 层移除提交链路对估价的调用（`submit` 不再调 `estimateAll`、不再因 `hasUnpriced` 拦截整单）；`estimateAll` VO/端点若 mp 不再调用则停用（保留方法签名兼容已有单测，**不删类**）。
- **实际金额仅店员核对 `final_amount_cent` + 反向打款决定**（GZ-RECYCLE-003 `verifyAndPayout` 链路不变；`validateFinalAmount` 软上限校验保留，但**去掉「≤ 估价 × 倍数」那一档**——估价已无、`estimatedAmountCent` 恒空/0，仅保留「≤ 绝对硬上限 `gz.recycle.final_amount.max_cent`」一档兜底防手输多打一位）。
- **`gz_recycle_price_rule` 表 + 估价单测处置 = 停用而非删表**（守强约束 destructive 红线 + 兼容旧数据）：
  - 表**物理保留、不 DROP**；admin 价目表入口（菜单 13001 + 13010-13014）**隐藏**（`sys_menu.visible='1'`），不再用于线上估价。
  - 估价相关单测（`estimate` / `estimateAll` happy/error path）**保留可跑、不删**（验证停用方法仍自洽，避免删测掩盖回归）；新提交链路单测断言「提交不依赖估价、金额字段为空」。
  - 既有提交单上的 `estimated_amount_cent` / `matched_duration_minutes` 历史值**保留可读**（详情页对历史单照显，新单这两列含义变更见 §3）。

> **取舍**：选「停用保留」而非「DROP price_rule + 删估价代码」。DROP 会丢 V1.1 历史估价审计 + 触 destructive 红线；删码会让旧数据详情无法解释 `estimated_amount_cent` 来源。停用代价仅一张闲表 + 一段隐藏菜单 + 一组守自洽的旧单测，可接受。

### 2. 单份多选 —— `List<ProductLine>` 改单对象，`product_snapshot_json` 数组改对象

一次预约 = **单个物品对象**（取代多条明细 `List<ProductLine>`）：

```
{
  "categories": ["card", "goods"],        // 品类多选（字典 gz_recycle_category，已可配）
  "ips": ["火影", "海贼王", "我自己写的冷门IP"], // IP 多选（gz_recycle_ip）+ 用户自定义文本，并存提交
  "qtyBucket": "1-25",                    // 数量桶单选（存 gz_recycle_qty_range.code）
  "remark": "..."                          // 可选备注
}
```

- **契约改动**（`GzRecycleAppointmentSubmitBo`）：
  - 删 `List<ProductLine> products`（连同内部类 `ProductLine`）。
  - 新增单对象字段：`List<String> categories`（`@NotEmpty`，每项校验 ≤ 32 / 命中字典）、`List<String> ips`（可空，每项 ≤ 64，列表项与用户自定义文本并存、不校验命中 IP 主数据——自定义 IP 本就不在表里）、`String qtyBucket`（`@NotBlank`，命中 `gz_recycle_qty_range.code`）、`String remark`（≤ 200）。
  - `submitImageIds` 必填校验**不变**（拍照前置声明 §5 是纯前端 gate）。
- **落库**：`product_snapshot_json` 从 **JSON 数组**改为 **JSON 对象**（`{categories,ips,qtyBucket,remark}`），仍走 JSON 列不散列（强约束 #12）。`writeProductJson` 序列化单对象。
- **`parseProducts` 兼容旧数组数据（兼容策略，钉死防线上详情崩）**：
  - 读 `product_snapshot_json` 时先**探测根节点类型**（用 Jackson `readTree` 判 `isArray()` vs `isObject()`）：
    - 根是**数组** → 旧数据（V1.1 多明细）：反序列化为 `List<ProductLineVO>`，**收敛投影**到新对象 VO —— `categories` = 去重各行 `category`，`ips` = 去重各行非空 `ip`，`qtyBucket` 置 `null`（旧数据无桶，详情显「历史单·精确件数 N」用旧 `total_qty` 兜底），`remark` 取首行或拼接。
    - 根是**对象** → 新数据：直接反序列化为新对象 VO。
  - 解析异常**不抛**（沿用现有 `catch → 返回空 + log.warn` 防御，保证历史单详情不崩）；新增对「数组根」分支的单测 + 「对象根」分支的单测，断言旧数组数据可读、字段正确投影。
  - VO 侧 `GzRecycleAppointmentVO` / `GzRecycleAppointmentAdminVO` 的 `products` 字段语义从「明细列表」改为「单物品对象」（mp 详情 + admin drawer 同步改渲染）。

> **取舍**：选「同列原地改 JSON 形态 + parse 双分支兼容」而非「新增 `item_json` 列 + 双列并存」。JSON 列本就不散列、改形态零 DDL（不动表结构），双分支 parse 是纯读时兼容、无数据搬迁；新列会让两套字段长期并存、查询/审计分叉。旧数据量小（V1.1 回收单有限），读时投影成本可忽略。

### 3. 数量桶 → 预计回收时间（独立 CRUD 表 `gz_recycle_qty_range`，admin 可配，取代按件数累加时长）

- **数量桶 = 独立 CRUD 主数据表 `gz_recycle_qty_range`**（已落地 `V202606270003`，**非 sys_dict、非 sys_config**——桶要同时承载「标签 + 预计时长」且 admin 频繁可改/可加档，主数据表一处承载比字典 + config 双处分散更内聚）：

  | 列 | 说明 |
  |---|---|
  | `id` | PK BIGINT UNSIGNED AUTO_INCREMENT |
  | `code` | 桶机读码（mp 提交落 `product_snapshot_json.qtyBucket`，后端按 `code` 查时长）；seed `1-25 / 25-50 / 50-75`；UNIQUE(tenant_id, code) |
  | `label` | 桶展示文案（`1-25 件` 等，可 i18n 透传） |
  | `duration_minutes` | 该桶**预计回收时长**（分钟）；admin 可改（seed 默认 30 / 60 / 90） |
  | `sort_no` | 展示排序 |
  | `enabled` | 0=停用 / 1=启用（mp 仅拉启用桶） |
  | + 公共字段 | `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` + `create_*/update_*/del_flag`（logicDeleteValue=1） |

- **桶 → 固定时长**：每个桶在表内自带 `duration_minutes`，**取代** `price_rule.duration_minutes` 按命中区间累加的 `matched_duration_minutes`；加「75+」桶 = admin 新增一行（`code='75plus'` 等），无需改表/迁移。
- **落库语义变更**（`gz_recycle_appointment` 同表列复用，不加列）：
  - `total_qty` 列**停用于精确件数**（用户不再填精确件数）；新单 `total_qty` 置 `null`（旧单历史值保留可读）。详情展示「数量：<桶 label>」而非数字。
  - `matched_duration_minutes` 新单 = 按 `product_snapshot_json.qtyBucket`（= `gz_recycle_qty_range.code`）查表的 `duration_minutes`（不再 `Σ` 各品类时长）；旧单历史值保留可读。
  - `estimated_amount_cent` 新单恒 `null`（§1 去估价）；旧单保留可读。
- **桶值回看**：`product_snapshot_json.qtyBucket` 存桶 `code`（不另加列，从 JSON 读 + 关 `gz_recycle_qty_range` 取 label/时长）；如 admin 列表要按桶筛选再评估加冗余列（默认不加）。

### 4. IP 主数据 `gz_recycle_ip`（后台 CRUD）+ mp 用户自加自定义 IP

- **新建主数据表 `gz_recycle_ip`**（已落地 `V202606270001`；admin CRUD，区别于字典 —— IP 条目多、甲方频繁增删、带排序/启停，主数据表比字典更合适）：

  | 列 | 说明 |
  |---|---|
  | `id` | PK BIGINT UNSIGNED AUTO_INCREMENT |
  | `ip_name` | IP 名称（如 火影 / 海贼王），VARCHAR(64)；UNIQUE(tenant_id, ip_name)（强约束 #3 唯一约束必含 tenant_id） |
  | `sort_no` | 排序 |
  | `enabled` | 0=停用 / 1=启用（mp 仅列启用项） |
  | `remark` | 备注 |
  | `tenant_id` | `VARCHAR(20) NOT NULL DEFAULT '1001'`（强约束 #2；INSERT 走自动填充不显式赋，seed 显式写 '1001'） |
  | + ruoyi 公共字段 | `create_dept/create_by/create_time/update_*/del_flag`（`@TableLogic` logicDeleteValue=1） |

- **包名**：`org.dromara.gz.recycle.{controller,service,mapper,domain.entity,domain.bo,domain.vo}`（`GzRecycleIp` 实体 / `GzRecycleIpController` 等，强约束 #4）。
- **mp 用户自加自定义 IP**：不在列表的 IP 走自由文本输入，与多选列表项**并存提交**进 `ips[]`（§2）。自定义 IP **不回写主数据表**（仅落该单 snapshot），避免脏数据污染主数据。
- **IP 纯标注、不进估价**（估价已下线 §1）；admin 复核仅参考、不影响金额。
- **menu**（已落地 `V202606270004`）：GZ-RECYCLE = 13000-13999；13001 价目表 / 13002 预约单 / 13003 反向打款 / 13010-13014 + 13020-13023 按钮已占 → **IP 管理 = 13004（C）+ 13030-13033 按钮，数量桶/时长管理 = 13005（C）+ 13040-13043 按钮**；owner role_id=100 显式 `sys_role_menu` 授权（13000 段不在 ruoyi 5000-5999 批量授权范围）。perm：`gz:recycle:ip:list/add/edit/remove` + `gz:recycle:qtyRange:list/add/edit/remove`。
- **seed**（已落地 `V202606270002`）：照搬 mp 原硬编码 5 个 IP 占位（火影/海贼王/航海王/鬼灭/初音，设计稿 §9 待补 #1），可在 admin 调整。

### 5. 到店核销二维码 —— 复用拼豆 `QrCodeSigner`，核销不限本店

- **复用 `org.dromara.gz.bean.service.internal.QrCodeSigner`**（HMAC-SHA256 截 32 位 hex，JDK 内置 `Mac`，无第三方依赖）为回收预约发核销码。
- **签名因子**：`appointmentNo + apptDate + storeId`（回收单核销维度），新增 `QrCodeSigner.signByRecycle(...)` + `verifyByRecycle(...)` 方法（与现有 `sign`/`signByType` 同范式，**不改既有方法**），或在 recycle 域内薄封一层调 `QrCodeSigner`。payload 短码形如 `RC|{appointmentNo}|{verifyCode}`（区别拼豆 `BK|...`）。
- **签名密钥复用** `gz.bean.qr.signing-secret`（`GzBeanQrProperties`，dev 默认值 / staging-prod env `GZ_BEAN_QR_SECRET`）—— 回收与拼豆同密钥即可（核销码是短期凭证、payload 含业务码自带区分前缀），**不新建 recycle 专属密钥配置**（避免多一处 env 管理；如后续要隔离再拆）。
- **核销流程**：mp 顾客 `recycle/detail.vue` 展示核销二维码（渲染 `RC|...` payload）→ 店员 `verify-scan` 扫码 → 后端解析 payload + `verifyByRecycle` 校签 → 拉出 `appointment` 进 `staff-verify` 核对（替代纯列表找单）。
- **核销不限本店（无门店权限隔离，设计稿 §0 点 3）**：店员扫任意门店回收单均可核对；`GzAdminUserStoreMapper` 门店绑定**保留不删但不用于数据过滤**。校签通过 + 状态 `submitted` 即可进核对，不校验「扫码店员所属门店 = 单门店」。

### 6. 总量信息聚合 + 双端可见边界

- **聚合（补展示，基本不加表）**：聚合 VO 补 payout 段（用 `out_payout_no` 拉真实到账态 / 到账时间 / 失败原因）；修 my-list「到账金额」语义（区分「核对金额 `final_amount_cent`」vs「真实到账状态」——`confirmed_onsite/paying` 时钱未必到账，不能直接显「已到账金额」）。
- **顾客端可见边界（窄）**：看自己提交段全部（品类/IP/桶/备注/提交图）+ 复核金额 + 真实到账态/时间；**不露**门店复核图 / 店员名 / 内部单号（`out_payout_no` 等）。
- **店员 / admin 端（全量）**：提交段 + 复核段 + payout 段全部可见。
- mp 新建 `recycle/detail.vue`（接已存在零调用的 `/{id}` 端点）+ 三段时间线（提交 / 复核 / 转账）+ 核销二维码（§5）。

## Rationale

- **去估价贴合甲方真实运营**：回收实物状态/品相线上拍照看不准，价格本就到店人工定 —— 线上估价是伪精度、徒增「估价 vs 实付」纠纷。砍掉估价让模型与「店员定价 + 反向打款」真实流程一致。
- **单份多选 = 用户真实心智**：用户一次回收一堆杂物，「多选品类 + 多选 IP + 选个数量档」比「逐条加明细填件数」交互轻得多；JSON 列原地改形态、零 DDL，parse 双分支纯读时兼容、不搬数据。
- **数量桶 → 时长**：去估价后件数精度无意义，桶档够用且驱动「预计回收时间」给店员排班参考；sys_config 配映射比建表轻。
- **IP 主数据而非字典**：IP 条目多、甲方频繁增删、可能带排序/logo，主数据表比字典灵活；自定义 IP 不回写主数据避免脏数据。
- **核销码复用拍豆 `QrCodeSigner`**：同 HMAC 范式、同密钥、payload 前缀区分，零新依赖、零新 env；核销不限本店契合「店员 / admin 看全部门店」的无隔离运营口径。
- **停用不删**：守 destructive 红线 + 留历史可追溯 + parse 兼容旧数据，代价仅闲表 + 隐藏菜单，长期可清。

## Consequences

- ✅ mp 回收表单大简化：单份多选无金额，交互轻、无「估价 vs 实付」预期落差。
- ✅ `product_snapshot_json` 旧数组数据可读（parse 双分支兼容），线上历史回收单详情不崩（设计稿 §10 风险点闭环）。
- ✅ IP 后台可配（`gz_recycle_ip` CRUD）+ 用户自定义并存；核销码复用拍豆机制、店员扫码进核对、不限本店。
- ✅ 总量信息双端可见、可见边界清晰（顾客窄 / 店员-admin 全量）；到账态真实（拉 payout 终态，不再用 `confirmed_onsite` 误显已到账）。
- ⚠️ **`gz_recycle_price_rule` 成停用表**：物理保留、admin 入口隐藏（`visible='1'`）；估价单测保留可跑、不删（守自洽防回归掩盖）；禁止新代码再依赖估价做提交校验（§0 自检 / QA 打回项）。
- ⚠️ **`SubmitBo.ProductLine` 内部类删除**：调用方（mp api 封装 + 单测）同步改单对象契约；`estimateAll(List<ProductLine>)` 签名失活（保留方法兼容旧测，新提交链路不调）。
- ⚠️ **落库列语义变更（同列复用不加列）**：新单 `estimated_amount_cent`=null（去估价）、`total_qty`=null（无精确件数）、`matched_duration_minutes`=按桶映射固定值（非 Σ）；旧单历史值保留可读，详情渲染需区分新旧单（旧单 `total_qty` 兜底显件数 / 新单显桶 label）。
- ✅ **已落地 Flyway 迁移（GZ-RECYCLE-004，本 ADR 钉死的数据模型源头，不可再改 —— Flyway checksum）**：
  - `V202606270001__GZ-RECYCLE-004-create-recycle-ip.sql` — 建 `gz_recycle_ip` 表（`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` + `UNIQUE(tenant_id, ip_name)`）。
  - `V202606270002__GZ-RECYCLE-004-seed-recycle-ip.sql` — seed 5 个占位 IP（seed 显式写 `tenant_id='1001'`，先 DELETE 占位再 INSERT 幂等）。
  - `V202606270003__GZ-RECYCLE-004-create-qty-range.sql` — 建 `gz_recycle_qty_range` 表（`UNIQUE(tenant_id, code)`）+ seed 3 档（`1-25/25-50/50-75`，`duration_minutes` 默认 30/60/90）。
  - `V202606270004__GZ-RECYCLE-004-menu-perm.sql` — IP=13004 + qty-range=13005 菜单（C）+ 13030-13033 / 13040-13043 按钮 + owner role_id=100 授权。
- ⚠️ **待补 Flyway 迁移**（时间戳 > 当前最大 `V202606270004`，从 `V202606270005` 起递增、已应用迁移不可改）：
  - `V202606270005__GZ-RECYCLE-hide-price-rule-menu.sql` — 价目表菜单 13001 + 13010-13014 `visible` 改 `'1'` 隐藏（停用 §1）。
  - final_amount 上限简化（§1）：去掉「≤ 估价 × `max_ratio`」档 = **改 service 代码**（`validateFinalAmount` 不再读 `max_ratio`），`gz.recycle.final_amount.max_cent` 既有 sys_config 保留即可，**无需新 DDL**（如要清 `max_ratio` 占位 config，并入 0005 一条 DELETE）。
- ⚠️ **数量桶载体澄清（不走 sys_dict）**：数量桶用独立 CRUD 表 `gz_recycle_qty_range`（§3），**非 sys_dict**——故不占 dict_id/dict_code 段，无 ruoyi 系统字典 tenant 000000 查不到的坑。表内 seed 显式 `tenant_id='1001'`（业务表惯例，非 000000 系统级）；mp/admin 直接查表取 label，不用 dict-tag。回收**状态**字典 `gz_recycle_status` 仍按既有 `tenant_id='000000'` 系统级 + 前端 dict-tag（不变，memory ruoyi-menu-dict-gotchas）。
- ⚠️ **`validateFinalAmount` 简化**：去掉「≤ 估价 × max_ratio」档（估价已无），仅留「≤ 绝对硬上限 `gz.recycle.final_amount.max_cent`」防店员手输多打一位；`gz.recycle.final_amount.max_ratio` config 失效（保留 key 不删，逻辑不再读）。
- ⚠️ **doc 回写（CLAUDE.md §9.5 改源头优先）**：doc/10 回收业务流（去估价 / 单份多选 / 桶→时长 / 核销码）；doc/11 §12.x（回收去估价、IP 主数据、数量桶字典、`product_snapshot_json` 对象形态、总量 VO、核销码签名因子）。本 ADR 是「为什么这么选」的决策记录，事实落地后以 doc/10/11 为唯一真源。

## Supersedes（取代/修订既有 ADR 的部分）

- **修订 ADR-0006（反向打款）**：不动 payout 出账机制，仅**移除其上游「估价驱动 final_amount 软上限的估价×倍数档」**——`validateFinalAmount` 去估价后仅留绝对硬上限档（ADR-0006 出账幂等 / PayoutStatus / 独立核算口径全部保留）。
- **不触 ADR-0008/0007/0011（拼豆侧）**：本 ADR 只管回收域；拼豆 1h 区间连续预约由配套的 ADR-0011 钉死。`QrCodeSigner` 为回收新增 `signByRecycle/verifyByRecycle`，**不改** ADR-0008 体系下的 `sign/signByType` 拍豆核销码语义。
- **未在既有 ADR 出现的回收提交/估价/明细模型**（GZ-RECYCLE-001/002/003 的代码事实，无独立 ADR）：由本 ADR 首次以决策形式钉死「去估价 + 单份多选 + 桶→时长 + IP 主数据 + 核销码」新模型，取代代码里的「估价 + List<ProductLine> 多明细 + 按件数累加时长 + 硬编码 IP」旧实现。
