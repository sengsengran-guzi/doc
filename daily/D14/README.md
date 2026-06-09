# D14 — 回收完成（预约填单 + 店员核对触发打款）+ tabbar 重构 + 扭蛋收尾

> 阶段：**V1.2 调整批次 收官日**（D11-D14 封顶）
> 主题：**回收预约端到端打通**（GZ-RECYCLE-002 mp 填单 + 自动估价 → GZ-RECYCLE-003 店员核对 + 拍照 + 触发反向打款 + admin 管理）**+ tabbar 重构**（GZ-SYS-010：3 tab = 拼豆/回收/我的，去首页，资讯/扭蛋入口迁「我的」）**+ 扭蛋收尾**（GZ-GACHA-111：入口迁「我的」+ 端到端做活回归，**最低优先级，本日最后一项**）
> 上一日：[D13](../D13/README.md)（拼豆 mp BEAN-015 + 优惠券抵扣 COUPON-002/003 + 反向打款 mock PAY-105 + 回收价目表 RECYCLE-001）｜ 下一日：**D15 原 V1.1 收官 ADMIN-104（物流 2 态推进）/ ADMIN-105 ⭐（对账中心）/ ADMIN-106（看板扩展）/ ADMIN-108（软删回收站）**——见 [d10-1 roadmap Daily 重排](../../../../../.claude/plans/d10-1-admin-miniapp-2-mutable-fairy.md)（V1.2 调整批次封顶后接回 V1.1 收官）
>
> **本批次起点真相**（主线程 §0 自检 **grep migration 目录实际验证，不假设上游已建**）：RECYCLE-002 依赖 D13 已建的 `gz_recycle_price_rule`（价目表，RECYCLE-001）；RECYCLE-003 依赖 RECYCLE-002 的 `gz_recycle_appointment`（本日 002 建）+ D13 的 `gz_pay_payout_transaction` + `IWechatPayClient.transferToUserWallet`（PAY-105，触发打款）+ ADR-0004 mp 管理端权限底座（已交付）；SYS-010 依赖**回收 tab 页存在**（RECYCLE-002 mp 填单页）+ BEAN-015 拼豆页（D13）+ designer C 风回收 tab 图标。`gz_recycle_appointment` 应**不存在 = 本日从零建**。

---

## 今日目标

V1.2 回收业务线**端到端闭环** + 小程序**导航形态定稿** + **扭蛋收尾**（四条链，3 个 mp 人验链 + tabbar mp 人验 + 扭蛋做活回归，本日为批次收官）：

- **主线 1（回收预约 mp 填单 — GZ-RECYCLE-002，mp 人验）**：
  - **`gz_recycle_appointment`**（doc/11 §12.2）：主状态机 `submitted → confirmed_onsite → paying → paid`，旁路 `cancelled / no_show / payout_failed`；含 product_snapshot_json / total_qty / matched_duration_minutes（提交冻结）/ estimated_amount_cent（自动估）/ appt_date·slot / receiver_openid·mobile·wechat_id 快照。
  - **自动估价 + 时长匹配**（doc/10 §13.N2/N3）：填品类（字典 `gz_recycle_category`）+ 数量命中 `gz_recycle_price_rule` 区间 → `unit_price_cent × total_qty` 估价 + `duration_minutes` 匹配（提交冻结）。
  - **mp 填单页（C 系统）**：填产品（品类 + 数量 + 描述，可多条）→ 实时估价 + 时长展示 → 选受时长约束的到店时段 → 采手机/微信号（沿用 §11.N6）→ 提交 `submitted`。价目表未覆盖 → 提示「该品类暂不支持线上估价，到店面议」（doc/10 §13.E1）。
- **主线 2（店员核对 + 触发打款 + admin 管理 — GZ-RECYCLE-003，mp 店员端人验 + admin AI 终态）**：
  - **mp 店员端核对页（复用 ADR-0004 权限）**：核对实物 → 拍照（`verify_image_ids`，image_id FK gz_file_object）→ 微调 `final_amount_cent`（留痕 verified_by / verify_time）→ 确认 → `submitted → confirmed_onsite`。
  - **触发反向打款**（doc/10 §13.N9 + §14）：`confirmed_onsite → paying` → 调 GZ-PAY-105（receiver_openid + final_amount_cent，建 `gz_pay_payout_transaction` business_type=recycle, business_order_no=appointment_no）→ success `paid` / failed `payout_failed`（可重试不重复转账）。
  - **admin（plus-ui owner 兜底）**：回收预约单管理（列表 + 详情，按门店/日期/状态筛）+ 反向打款单管理（状态/查单/失败重试）。
- **主线 3（tabbar 重构 — GZ-SYS-010，mp 人验）**：
  - 底部 tabbar 从含首页改为 **3 tab：拼豆 / 回收 / 我的**（选中朱红，C 风粗墨描边图标）。
  - **去独立首页**：原首页内容下沉，启动**默认指向 bean（拼豆）tab**。
  - 资讯入口 + 扭蛋入口**迁入「我的」tab 入口卡**（扭蛋做活非 ComingSoon，资讯保留 pages/news）。
  - 新增「回收」tab 的 C 风图标（active/inactive，**对接 designer**）。
  - 清理历史临时入口（grep `Tier2-entry-temp` → 用真 tab 入口替换，含 D13 BEAN-015 / COUPON-003 留的临时入口）。
- **主线 4（扭蛋收尾 — GZ-GACHA-111，mp 人验；最低优先级，本日最后一项）**：
  - 扭蛋（V1.1 已建 GACHA-101~104）入口从「我的」tab 入口卡进入（配合 SYS-010 迁移），**保留 `pages/gacha`，做活非 ComingSoon**。
  - **端到端做活回归**：从「我的」→ 扭蛋入口 → 列表 → 单机详情（概率公示）→ 投币 → JSAPI 支付（mock）→ 开盒事务出 1 件 → 出奖动画 → 进待发货订单，全链路无回归。
  - **降开发优先级 = 不改概率 / 不改 weight 数据 / 不动抽奖逻辑**：仅入口迁移 + 做活回归（区别于早先误解的「调低概率」，本批无任何 weight 数据调整任务）。
  - **本日最后一项**：等 SYS-010 把「我的」入口卡建好后再做（依赖 SYS-010 入口卡 + tabbar）。

完工后（V1.2 调整批次封顶）：
- 甲方/Kevin 真机：打开小程序即见 3 tab（拼豆默认落地）；「回收」tab 填单 → 自动估价 + 预计时长 → 选时段 → 提交；店员手机登 mp 核对实物 + 拍照 + 微调金额 + 确认 → 触发 mock 反向打款到账；owner 在 admin 看回收预约单 + 反向打款单（失败可重试）；资讯/扭蛋从「我的」1 次可达。

## Ticket 清单（4 个 / 全含 mp 人验 + RECYCLE-003 admin AI 终态部分）

| Ticket | 标题 | 端 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| GZ-RECYCLE-002 | 回收预约单 + 自动估价 + mp 填单页（含用户提交拍照 submit_image_ids 必填）| mp + be | **L** | GZ-RECYCLE-001（D13）| pending |
| GZ-RECYCLE-003 | 店员核对 + 拍照 + 触发打款 + admin 管理 | mp + admin + be | **L** | GZ-RECYCLE-002 + GZ-PAY-105（D13）+ ADR-0004（已交付）| pending |
| GZ-SYS-010 | tabbar 重构（去首页 → 拼豆/回收/我的 + 资讯/扭蛋迁我的）| mp | M | GZ-RECYCLE-002（回收页存在）+ GZ-BEAN-015（D13）+ designer 回收 tab 图标 | pending |
| GZ-GACHA-111 | 扭蛋入口迁「我的」+ 端到端做活回归（**最低优先级，本日最后**）| mp | S | GZ-SYS-010（「我的」入口卡 + tabbar）+ GACHA-101~104（已交付）| pending |

ticket 任务卡随本日 closing 细化。**全部 mp 人验**（RECYCLE-002 用户填单 / RECYCLE-003 店员端核对 / SYS-010 导航 / GACHA-111 扭蛋做活）；RECYCLE-003 admin 部分（预约/打款单管理）AI 终态。

**依赖图**：

```
D13 ✅ RECYCLE-001（gz_recycle_price_rule 价目表 + 时长规则）
D13 ✅ PAY-105（gz_pay_payout_transaction + transferToUserWallet mock）
已交付 ✅ ADR-0004（mp 管理端权限底座：openid 绑 sys_user + @SaCheckPermission）
        │
        ▼
GZ-RECYCLE-002 (mp 填单 + 自动估价 + gz_recycle_appointment + submit_image_ids 必填)  ─── mp 人验
        │
        ├──────────────────────────────┐
        ▼                               ▼
GZ-RECYCLE-003 (店员核对+拍照+触发打款    GZ-SYS-010 (tabbar 3tab：拼豆/回收/我的
   +admin 管理，←002 + PAY-105 + ADR-0004)   去首页指向 bean + 资讯/扭蛋迁我的，←回收页存在)
   mp 店员端人验 + admin AI 终态           mp 人验
                                            │
                                            ▼
                              GZ-GACHA-111 (扭蛋入口迁「我的」+ 做活回归
                                 ←SYS-010「我的」入口卡，**本日最后**) mp 人验
```

- **RECYCLE-002 是本日链路起点**：建 `gz_recycle_appointment` + mp 填单 + 自动估价 + **用户提交拍照 submit_image_ids 必填**（消费 D13 RECYCLE-001 价目表）。
- **RECYCLE-003 依赖 RECYCLE-002（预约单）+ D13 PAY-105（反向打款能力）+ ADR-0004（店员端权限）**：核对触发打款。
- **SYS-010 依赖 RECYCLE-002 回收页存在**（tabbar「回收」要指向真实填单页）+ D13 BEAN-015 拼豆页（「拼豆」tab 落地页）+ **designer 提供 C 风回收 tab 图标**；建议 RECYCLE-002 完工后起，可与 RECYCLE-003 并行。
- **GZ-GACHA-111 依赖 SYS-010**（「我的」入口卡 + tabbar 已迁扭蛋入口）：**本日最后一项**，SYS-010 把「我的」扭蛋入口卡建好后做扭蛋入口接通 + 端到端做活回归（不改概率/weight）。

## 派单方式

```
开始 d14
```

主线程动作：
1. 读 D14/README.md + 依赖图，做 §0 自检（grep migration 确认 `gz_recycle_price_rule`（RECYCLE-001）+ `gz_pay_payout_transaction`（PAY-105）已建；ADR-0004 mp 权限底座在位；`gz_recycle_appointment` 应不存在 = 从零建）。**确认 designer 已交付回收 tab C 风图标**（active/inactive 80×80 PNG），未交付则 SYS-010 先用占位图标 + 标 designer 待补。
2. **第一波 spawn**：RECYCLE-002（链路起点）。RECYCLE-002 ✅ → **第二波并行 spawn**：RECYCLE-003 + SYS-010（互不阻塞，均依赖回收页 / 预约单存在）。SYS-010 ✅（「我的」扭蛋入口卡建好）→ **第三波（本日最后）spawn**：GZ-GACHA-111（扭蛋入口接通 + 做活回归）。
3. kevin-coder 每卡完工后 → 全完工时**一个 kevin-qa 串行整批 Tier 1B**：
   - RECYCLE-003 admin 部分（预约/打款单管理）→ admin Playwright E2E AI ✅ 即终态
   - mp 部分（RECYCLE-002 用户填单 / RECYCLE-003 店员核对 / SYS-010 导航 / GACHA-111 扭蛋做活）→ kevin-qa 显式检查可达性 + vitest unit；进 progress.md「人验」列待 Kevin 批量验
4. 任一 AI 测试 ❌ → 闭环回 kevin-coder 修。
5. 4 卡 AI 全 ✅ → 日终 closing + **整理 V1.2 集成回归 checklist**（见末节）→ 通知 Kevin 集中批量人验 V1.2 全部 mp ticket（BEAN-015 / COUPON-003 / RECYCLE-002 / RECYCLE-003 店员端 / SYS-010 / GACHA-111）。

> 编排沿用 D10/D11 模式：主线程 §0 grep migration 自检 → 按依赖 spawn kevin-coder（各自 Tier 1A）→ 全完工后一个 kevin-qa 串行整批 Tier 1B（见 memory [[tier1b-qa-dispatch-by-mainthread]] + [[dev-infra-run-recipe]] + [[mp-build-devtools-hang]] + [[admin-test-tenant-account]]）。

## 今日特殊约束 ⭐

### GZ-RECYCLE-002 回收预约 mp 填单 + 自动估价（doc/10 §13 + doc/11 §12.2 + C 系统 + Tier 2 可达）

> **doc/10 §13（回收预约全流程 N1-N5 + 估价口径 + E1-E6）+ doc/11 §12.2（`gz_recycle_appointment` 字段 + 回收状态机）是唯一权威。设计走 doc/tokens.md + doc/13（C 日漫海报浓墨），仅 mp。**

- **回收状态机（doc/11 §12.2 / doc/10 §13，钉死）**：`submitted`（用户填单提交，自动估价冻结）→ `confirmed_onsite`（D14 RECYCLE-003 店员核对）→ `paying` → `paid`；旁路 `cancelled`（用户/店员取消）/ `no_show`（凌晨任务）/ `payout_failed`（打款失败可重试）。**本日 RECYCLE-002 只产 `submitted`**（confirmed_onsite 起在 RECYCLE-003）。
- **自动估价 + 时长冻结（doc/10 §13.N3 估价口径，钉死）**：按 `gz_recycle_price_rule` 命中 `(category, qty 落 qty_min~qty_max)` → `estimated_amount_cent = Σ 各品类(unit_price_cent × 该品类数量)`（多品类各自命中累加，doc/11 §12.3 F12.1）；`matched_duration_minutes` 按数量匹配时长，**提交冻结**进预约单。`estimated_amount_cent`（预估）≠ `final_amount_cent`（店员核对后实付，RECYCLE-003 定）。
- **快照字段（doc/11 §12.2）**：提交时 snapshot `receiver_openid`（从 gz_user.openid，反向打款必需）+ `mobile_snapshot` + `wechat_id_snapshot`（采集沿用 doc/10 §11.N6）；`product_snapshot_json`（用户填的物品清单，**JSON 列不散列**，强约束 #12）。
- **用户提交拍照 `submit_image_ids` 必填（钉死）**：mp 填单页含「上传实物照片」项，**必填**（前端 + 后端 Bo `@NotEmpty` 双重校验，无照阻断提交）；图片走 COS 上传存 `submit_image_ids`（逗号分隔 image_id FK gz_file_object，`usage_type=recycle_submit_image`，**不存裸 url**）。与 RECYCLE-003 店员核对拍照 `verify_image_ids` 是**两套独立字段**（用户报备 vs 店员核验）。
- **C 设计系统纪律（CLAUDE.md §7.5）**：mp 填单页只用 `src/components/biz/Biz*` + `var(--c-*)` token，不直接撒 `<wd-*>`；不逐像素还原 mockup；不混 emoji。
- **Tier 2 可达（CLAUDE.md §8.3，mp 硬约束）**：本日 SYS-010 同批做 tabbar 重构，「回收」tab 即为真入口；但 RECYCLE-002 若先于 SYS-010 完工 → **加临时入口**到现有页 `<!-- TODO(Tier2-entry-temp): GZ-RECYCLE-002, remove when GZ-SYS-010 merged -->`（SYS-010 用真「回收」tab 替换）。AC 必含：`Tier 2 可达 — Kevin 从 tabbar「回收」（或临时入口）点 N 次到达填单页`。
- **异常（doc/10 §13.E1）**：数量超所有价目区间 → 提示「该数量暂不支持线上估价，请到店咨询」（或按 admin 配置封顶，默认到店咨询，Q13.2）。

### GZ-RECYCLE-003 店员核对 + 触发打款 + admin 管理（ADR-0004 权限 + ADR-0006 打款 + Tier 2 可达）

> **doc/10 §13（N6-N12 店员核对 + 触发打款）+ §14（反向打款时序）+ doc/11 §12.2（核对字段 final_amount/verify_image_ids/verified_by）/§4.8（payout 单）是唯一权威。ADR-0004（mp 管理端权限复用）+ ADR-0006（反向打款幂等/查单优先）是决策权威。**

- **mp 店员端权限（复用 ADR-0004，doc/10 §13 触发条件）**：店员核对页走 mp 管理端权限底座（`gz_user.staff_user_id` 绑 sys_user + `@SaCheckPermission` + 同租户 1001 + 停用/解绑即时踢）；**不用 `@SaCheckRole`**。
- **店员核对流（doc/10 §13.N7/N8）**：按 appointment_no 调出预约 → 核对实物 → 拍照（`verify_image_ids` 逗号分隔 image_id，FK gz_file_object，`usage_type=recycle_verify_image`，**不存裸 url**，强约束 #12）→ 微调 `final_amount_cent`（默认 = estimated，可改，**微调必留痕** verified_by + verify_time + 拍照存证，doc/11 §12.3 F12.2）→ 确认 → `submitted → confirmed_onsite`。
- **触发反向打款（doc/10 §13.N9 + §14，幂等关键）**：`confirmed_onsite → paying` 时建 `gz_pay_payout_transaction`（`business_type=recycle`, `business_order_no=appointment_no`, `receiver_openid`=快照, `amount_cent=final_amount_cent`）→ 调 D13 PAY-105 `transferToUserWallet`（mock）→ success `paid` / failed `payout_failed`；`out_payout_no` + `batch_id` 双重幂等 + `version` 乐观锁防同一回收单重复打款（doc/11 §12.2 末段 + §4.8）。打款失败 `payout_failed` **留人工处理**（不无限自动重试，doc/10 §13.E4），owner 可重试 → `paying`。
- **admin（plus-ui owner 兜底，AI 终态）**：回收预约单管理（列表 + 详情，按门店/日期/状态筛）+ 反向打款单管理（状态查看 / 主动查单 / failed 重试）；走 ruoyi/Element Plus 默认审美，**不引 mockup**。
- **Tier 2 可达（店员端）**：店员从 mp「我的（店员端）」点 N 次到达回收核对页；业务主线入口未建则加临时入口 `TODO(Tier2-entry-temp)`。AC 必含可达条目。
- **回收反向出账独立核算（doc/11 §4.6 补注）**：店付用户的钱，**不计 GMV、不参与 4% 分成**，不进对账中心 §9 口径。

### GZ-SYS-010 tabbar 重构（去首页 → 3 tab + 入口迁移 + C 风图标 + Tier 2 可达）

> **doc/02-需求拆解 §3.6.4 GZ-SYS-010 AC + CLAUDE.md §7.5（tabbar 形态）+ doc/12（tabbar 3tab + 资讯·扭蛋迁移）是权威。**

- **3 tab（CLAUDE.md §7.5 + 需求拆解 §3.6.4）**：拼豆 / 回收 / 我的（选中朱红，C 风粗墨描边图标）。**改 `miniapp/src/tabbar/config.ts`**（关键文件锚点）。
- **去独立首页（关键）**：原首页内容下沉，启动**默认指向 bean（拼豆）tab**（不是首页）。改 `miniapp/src/pages/index/index.vue` 去首页 + 指定新 home = bean（pages.json `tabBar.list` 首项 / 启动页路由）。
- **资讯 + 扭蛋入口迁「我的」（roadmap 风险 3 落地）**：迁入「我的」tab 入口卡——**资讯保留 pages/news**（首页卡改我的入口卡）；**扭蛋做活非 ComingSoon**（GACHA-101~104 已交付，从我的入口进）。本卡建好「我的」扭蛋入口卡后，**GZ-GACHA-111（本日最后）接通扭蛋入口 + 端到端做活回归**（扭蛋 V1.2 仅降开发优先级 + 入口迁移 + 做活回归，**不改概率/weight**）。
- **回收 tab C 风图标（对接 designer）**：新增「回收」tab 的 C 风粗墨描边图标（active/inactive，80×80 PNG，对齐 designer 现有 tab 图标范式）；**转 designer 出图**（kevin-designer 首批任务范畴）；未交付前用占位图标 + 标 designer 待补，不阻塞 SYS-010 逻辑。
- **清理历史临时入口（CLAUDE.md §8.3 时序约束）**：§0 自检 grep `Tier2-entry-temp` → 把 D13 BEAN-015 / COUPON-003 + 本批 RECYCLE-002 留的临时入口**用真 tab 入口替换**（不是裸删，保证可达路径不断）。
- **Tier 2 可达（需求拆解 §3.6.4 AC6）**：Kevin 打开小程序即见 3 tab（拼豆默认落地）；资讯/扭蛋从「我的」1 次可达；回收/拼豆从 tab 直达。AC 必含。

### GZ-GACHA-111 扭蛋入口迁「我的」+ 端到端做活回归（**最低优先级，本日最后一项**）

> **doc/02-需求拆解 §3.6.6 GZ-GACHA-111 AC + doc/02-prd M2 §V1.2 定位调整（降开发优先级，入口迁「我的」，排最后）是权威。复用 V1.1 已建 gacha-list/detail/draw 页。**

- **降开发优先级硬约束**：扭蛋本批**只做入口迁移 + 端到端做活回归**，**不改概率 / 不改 `gz_gacha_prize.weight` 数据 / 不动抽奖逻辑**（区别于早先误解的「调低概率」——无任何 weight 数据调整任务）。`git diff` 应仅含 mp 入口接通 + 必要回归修复，不含 weight 数据/概率逻辑改动。
- **入口接通**：依赖 SYS-010 已建「我的」tab 扭蛋入口卡 → 本卡接通入口卡跳 `pages/gacha`（做活非 ComingSoon），清理扭蛋相关历史临时入口（grep `Tier2-entry-temp`）用「我的」入口卡真入口替换。
- **端到端做活回归**：从「我的」→ 扭蛋入口 → 扭蛋机列表 → 单机详情（概率公示）→ 投币 → JSAPI 支付（mock）→ 开盒事务出 1 件 → 出奖动画 → 进待发货订单，全链路跑通无回归（GACHA-101~104 既有逻辑不破坏）。
- **本日最后一项**：SYS-010 完工（「我的」入口卡 + tabbar）后再 spawn；纯 mp，无新增后端/表/menu。
- **Tier 2 可达**：Kevin 从「我的」点扭蛋入口卡 1 次到达扭蛋机列表，可走完一次做活（mock 支付）。AC 必含。

### 全局

- **admin 走 ruoyi/Element Plus 默认审美**：RECYCLE-003 admin 预约/打款单管理全部 plus-ui BizTable + Element Plus 默认，**不调样式、不引 mockup**（admin 不评判视觉）。**测 admin 登 gz_owner**（[[admin-test-tenant-account]]：谷子业务在租户 1001，用 gz_owner/gz_owner123! 别用 ruoyi 超管 admin 否则看不到数据）。
- **mp 走 C 日漫海报浓墨**：RECYCLE-002 填单页 / RECYCLE-003 店员核对页 / SYS-010 tabbar 仅 Biz* 组件 + `var(--c-*)` token，不直接撒 `<wd-*>`；doc/tokens.md + doc/13 为准。
- **menu_id 段（doc/11 §10.3）**：回收 **13000 段**（13000 目录 / 13001 价目表 D13 已占 / 13002 回收预约单 / 13003 反向打款单或挂 5100）；反向打款 admin 挂 **5100 段**（GZ-PAY）。SYS-010 无新增后端 menu（纯 mp 导航）。
- **包名（CLAUDE.md §6 #4）**：回收 `org.dromara.gz.recycle.*`；反向打款触发复用 `org.dromara.gz.common.pay.*`（PAY-105 能力）；店员端权限复用 ADR-0004 底座（`org.dromara.gz.user.*` / common）。
- **字段/命名硬约束（每卡复核）**：金额 `_cent`（final_amount_cent / estimated_amount_cent / unit_price_cent）/ snapshot `*_snapshot`（mobile/wechat_id/receiver_openid）/ JSON 列不散列（`product_snapshot_json`）/ 图片**两套** `submit_image_ids`（用户提交时拍照，**必填**，RECYCLE-002 写）+ `verify_image_ids`（店员核对拍照，RECYCLE-003 写）均 FK gz_file_object，逗号分隔 id，**不存裸 url** / 业务码 `RCY-yyyyMMdd-6位序号` / `PAYOUT-`（payout 单）/ 业务线 `business_type='recycle'` / 乐观锁 `version`（状态推进 + 防重复触发打款）/ `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` / `del_flag` 2 值。
- **SnailJob（非 sys_job）**：回收 no_show 凌晨任务（doc/10 §13.N12，优先店员标记 + cron 兜底，doc/11 §12.3 F12.3）+ 反向打款查单轮询（D13 PAY-105 已建，RECYCLE-003 触发后由它接管）= `@Component + @JobExecutor` 薄壳 + 可单测 service；任务名/CRON 写 reports + testing-human；**禁止** Flyway INSERT sys_job；模块 pom 加 `ruoyi-common-job`。
- **DDL 命名 `V<yyyyMMddHHmm>__<TICKET-ID>-<desc>.sql`**（时间戳 > 已有最大版本；已应用迁移不可改）；**不动 ruoyi 自带模块**。
- **不要 commit**：4 卡全完工 + AI 测试全 ✅ 后统一 commit；mp 部分进人验列待 Kevin 批量验（AI ✅ 即解锁，不阻塞 commit）。

## 推进姿态 = Mock 全链路自测

- 回收触发的反向打款在 `gz.pay.client.mode=mock` 下闭环（RECYCLE-003 调 D13 PAY-105 mock）：confirmed_onsite → paying → 查单 success → paid。
- 真实商户号 / 商家转账真实权限 + transferbatch SDK 列为【外部前置风险】（ADR-0006 / doc/11 §4.10 F4.6），权限+SDK 到位后小额真实回归；不当默认就绪。

## 与昨日 reports 对账（D13）

D13 完工后应交付（**主线程 §0 自检 grep migration 目录实际验证，不假设**）：
- GZ-RECYCLE-001 → `gz_recycle_price_rule`（品类×数量区间→单价+时长，区间不重叠校验）+ 字典 `gz_recycle_category`。RECYCLE-002 的自动估价 + 时长匹配全靠它。
- GZ-PAY-105 → `gz_pay_payout_transaction`（独立 PayoutStatus）+ `gz_pay_payout_callback_log` + `IWechatPayClient.transferToUserWallet`/`queryTransferByOutNo`（mock）+ 查单 SnailJob + 幂等。RECYCLE-003 的触发打款调它。
- GZ-BEAN-015 → mp 拼豆付费页（「拼豆」tab 落地页，SYS-010 指向它）。
- D13 summary.md「对下游 ticket 的提示」段（estimated 估价多品类累加口径 / payout 触发幂等 batch_id 生成 / receiver_openid 快照来源 / 拼豆页路由）在 RECYCLE-002/003 + SYS-010 实施前主线程逐条对齐。

进 D14 前主线程 §0 自检校验（**grep 实际存在的表/类，不假设**）：
```bash
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'GZ-RECYCLE-001|gz_recycle_price|GZ-PAY-105|payout'
grep -rl 'transferToUserWallet\|gz_pay_payout_transaction\|gz_recycle_price_rule' code/main/RuoYi-Vue-Plus/ruoyi-modules 2>/dev/null
# gz_recycle_appointment 应当查不到（= 本日从零建，正常）
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'recycle_appointment|GZ-RECYCLE-002' || echo "本日产物不存在 = 正常，从零建"
# 确认 designer 回收 tab 图标
ls code/main/miniapp/src/static/tabbar/ 2>/dev/null | grep -i recycle || echo "回收 tab 图标待 designer 交付（SYS-010 先用占位）"
# GZ-GACHA-111（本日最后）：纯 mp，无新增表/menu；确认扭蛋页/逻辑在位（GACHA-101~104 已交付）
grep -rl 'pages/gacha' code/main/miniapp/src 2>/dev/null | head || echo "扭蛋页缺失 → 回 V1.1 排查"
```
上游表/能力齐 → 开工；缺则 STOP 报 Kevin（先回 D13 收尾）。

## 完成判定（DoD）

- [ ] 4 个 ticket 任务卡 §revision 段空（RECYCLE-002 / RECYCLE-003 / SYS-010 / GACHA-111）
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 grep migration raw output + §N 完工 + ≥ 3 个代码 block raw output + 关联 ADR 已读摘录：RECYCLE-002 引 doc/10 §13 / RECYCLE-003 引 ADR-0004 + ADR-0006 / GACHA-111 引 PRD M2 §V1.2 降优先级）
- [ ] **RECYCLE-002 reports 必含**：自动估价命中区间 raw output（单/多品类 unit_price × qty 累加 = estimated_amount_cent）+ 时长匹配冻结 + 超区间 E1 提示分支 + **用户提交拍照 submit_image_ids 必填校验**（无照阻断提交 + image_id 入库 raw output）
- [ ] **GACHA-111 reports 必含**：扭蛋入口接通「我的」入口卡 + 端到端做活回归 raw output（列表→详情→投币→mock 支付→出 1 件→进订单）+ **`git diff` 确认无 weight 数据/概率逻辑改动**（降开发优先级，仅入口迁移+回归）
- [ ] **RECYCLE-003 reports 必含**：店员核对 → confirmed_onsite → 触发 mock 反向打款 → paid 全链路 raw output + 微调 final_amount 留痕（verified_by/verify_time/拍照 image_id 入库）+ **重复触发幂等**（同一 appointment 不重复 payout）+ failed → payout_failed 可重试分支
- [ ] mvn install（ruoyi-gz-recycle / common -am）+ plus-ui build:prod 全绿（RECYCLE-003 含 admin）；mp 部分（RECYCLE-002 / 003 店员端 / SYS-010）miniapp build:mp-weixin 绿（注意 [[mp-build-devtools-hang]]：尾部唤 devtools cli 假挂起，dist 已生成则 pkill cli -o）
- [ ] 回收 no_show 凌晨任务 SnailJob 任务名 + CRON 写进 reports + testing-human（如本日落地）；**确认无 Flyway INSERT sys_job**
- [ ] Tier 1A + 1B 全 ✅：
  - RECYCLE-003 admin 部分（预约/打款单管理）→ admin Playwright E2E AI ✅ 即终态
  - mp（RECYCLE-002 用户填单 / RECYCLE-003 店员核对 / SYS-010 导航 / GACHA-111 扭蛋做活）→ kevin-qa Tier 1B 显式检查可达性（grep `Tier2-entry-temp` 已被真 tab 入口替换）+ vitest unit；进 progress.md「人验」列待 Kevin 批量验
- [ ] 单测覆盖：RECYCLE-003 触发打款幂等 + 状态机流转 ≥ 80%（资金相关，对齐扭蛋/拼豆事务级目标 CLAUDE.md §8.1）
- [ ] **SYS-010 临时入口全清理**：grep `Tier2-entry-temp` 无残留（D13 BEAN-015 / COUPON-003 + 本批 RECYCLE-002 临时入口已用真 tab 入口替换）；启动默认指向 bean（拼豆）tab；资讯/扭蛋从「我的」1 次可达
- [ ] designer 回收 tab C 风图标交付（active/inactive 80×80 PNG）或标 designer 待补占位（不阻塞逻辑）
- [ ] testing-human.md 预填（mp happy path + 可达路径，4 卡）：
  - 回收用户：tabbar「回收」→ 填品类 + 数量 + 描述（多条）→ **上传实物照片（必填）** → 看实时估价 + 预计时长 → 选时段 → 采手机/微信号 → 提交 submitted
  - 回收店员：店员账号登 mp → 「我的（店员端）」→ 回收核对 → 调出预约（可见用户提交照片）→ 店员再拍照 + 微调金额 + 确认 → mock 打款到账 paid；停用 sys_user 后即踢
  - tabbar：打开小程序即见 3 tab（拼豆默认落地）→ 切回收/我的 → 「我的」点资讯/扭蛋各 1 次可达
  - 扭蛋做活（GACHA-111）：「我的」→ 扭蛋入口卡 → 列表 → 详情（概率公示）→ 投币 → mock 支付 → 出 1 件 → 进订单
- [ ] **V1.2 集成回归 checklist 全绿**（见下节）
- [ ] V1.2 调整批次 ticket 全部 close（D11-D14：ORD-110 / USER-005 / USER-006 / BEAN-013/014/015 / COUPON-001/002/003 / PAY-105 / RECYCLE-001/002/003 / SYS-010 / GACHA-111 共 15 个）

## V1.2 收官 — 集成回归 checklist（本日末整理，写 `D14/v1.2-integration-checklist.md`）

收官完成后整理一份独立 checklist（closing 时写，不在本 README 内），按 **拼豆付费配额 + 优惠券抵扣 + 回收反向打款** 全链路验：

- [ ] 拼豆付费全链路（mock client，单笔单时段）：mp 选 1 个「四人桌+下午」（显余量「还剩 N」）→ 金额 = 该类型单价（无累加）→ 选券 → 实付 = 单笔金额 − 券面额（下限 0）→ 采手机/微信号 → 提交下单事务（配额校验通过）→ mock 支付成功 → pay_status=paid 占名额 → 预约详情 + 核销码二维码；再约一笔（多次预约 = 多行 booking）独立计费/配额/核销
- [ ] 拼豆余量显示：mp 选座每档显「还剩 N 个」/「已满」灰显（余量 = quantity − 该 (类型,日期,时段) 活跃 booking 数），约到最后一个后该档转「已满」
- [ ] 拼豆防超卖：构造并发约同一 `(类型,日期,时段)` 最后名额 → 仅一单成功，其余拒单（单笔单时段无部分成交问题）；unpaid 超时（15min）SnailJob 释放配额 + 回滚锁券
- [ ] 拼豆旧数据迁移回归：旧免费 booking 原地补 seat_type（兜底 single）+ 付费列（标历史「已付 0 元」，无子表迁移）→ 历史单只读展示不丢信息；迁移前后 count 一致
- [ ] 优惠券闭环：发券（admin **manual 策略** 批量，issued_count 乐观锁不超发；register_window/event 接口存在可编译预留）→ mp 我的券 unused → 拼豆下单 locked → 支付成功 used（related_pay_out_trade_no 写入）→ 券面额不计 GMV（gz_pay_transaction.amount_cent = 实付）；取消订单 locked→unused 回滚；过期 SnailJob unused→expired（locked 不误伤）
- [ ] 回收估价：填多品类多数量 → 各品类命中价目表区间 → estimated = Σ(unit_price × qty)；total_qty → matched_duration_minutes 冻结；超区间 → 「到店面议」提示
- [ ] 回收两套拍照：用户提交时 submit_image_ids **必填**（无照阻断提交，image_id 入库）+ 店员核对时 verify_image_ids（存证）；两套独立字段，均 FK gz_file_object 不存裸 url
- [ ] 回收核对 + 反向打款（mock）：店员核对（可见用户 submit 照片）→ 店员拍照 verify_image_ids 入库 → 微调 final_amount 留痕（verified_by/verify_time）→ confirmed_onsite → 触发 payout（business_type=recycle, amount=final_amount_cent）→ created→processing→success → status=paid；paid 发 CouponIssuanceEvent 钩子（event 模板未配则不发券）；failed → payout_failed → owner 重试不重复转账（out_payout_no + batch_id 幂等）
- [ ] 反向打款独立核算：回收 payout 不计 GMV、不进对账 §9、不参与 4% 分成（合同 §4.1 / doc/11 §4.6 补注）
- [ ] tabbar 重构：打开小程序默认 bean（拼豆）落地；3 tab（拼豆/回收/我的）切换；资讯（pages/news 保留）+ 扭蛋（做活非 ComingSoon）从「我的」1 次可达；无 `Tier2-entry-temp` 残留
- [ ] 扭蛋做活回归（GACHA-111）：「我的」扭蛋入口卡 → 列表 → 详情（概率公示）→ 投币 → mock 支付 → 开盒出 1 件 → 进订单全链路无回归；**无 weight 数据/概率逻辑改动**（降开发优先级）
- [ ] 跨端权限（ADR-0004）：店员可 mp 做回收核对 + 触发打款，owner 可 plus-ui 兜底（回收预约单 + 反向打款单管理）；停用/解绑 sys_user 即时踢 mp token
- [ ] 三端编译：mvn install（ruoyi-gz-* -am）+ plus-ui build:prod + miniapp build:mp-weixin 全绿
- [ ] 预购下线（D11 ORD-110）无回归副作用：预购 admin/mp 入口屏蔽（代码保留）；扭蛋（V1.2 仅降开发优先级，GACHA-111 入口迁「我的」+ 做活回归，未改概率）可达

集成回归全绿 → V1.2 调整批次封顶（15 个 ticket）。**通知 Kevin 集中批量人验 V1.2 全部 mp ticket（BEAN-015 / COUPON-003 / RECYCLE-002 / RECYCLE-003 店员端 / SYS-010 / GACHA-111）→ 进入 D15（原 V1.1 收官：ADMIN-104 物流 2 态推进 / ADMIN-105 ⭐ 对账中心 / ADMIN-106 看板扩展 / ADMIN-108 软删回收站）。**

## 已知风险 ⭐

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | RECYCLE-003 重复触发反向打款 → 多打钱给用户 | `out_payout_no` + `batch_id` 双重 UNIQUE 幂等 + `gz_recycle_appointment.version` 乐观锁防并发触发；reports 必含同一 appointment 不重复 payout raw output（doc/11 §12.2 末段）|
| R2 ⭐ | 店员微调 final_amount 舞弊 / 无留痕 | 微调必留痕 verified_by + verify_time + 拍照 image_id 入库（doc/11 §12.3 F12.2）；owner admin 可审计异常微调；V1.2 不强制审批（高额阈值审批后续，Q13.1）|
| R3 | RECYCLE-002 估价命中 0/多区间 | 价目表区间不重叠校验已在 D13 RECYCLE-001；命中 0 → 「到店面议」；命中多 → 校验报错（配置有误，doc/11 §12.1 末段）|
| R4 | SYS-010 去首页后启动指向错（指首页死页 / 资讯扭蛋入口丢失）| 启动默认指向 bean（拼豆）tab；资讯迁「我的」入口卡保留 pages/news，扭蛋做活非 ComingSoon（roadmap 风险 3）；Tier 2 验可达 |
| R5 | SYS-010 临时入口未清理（D13/本批遗留 Tier2-entry-temp 残留）| §0 自检 grep `Tier2-entry-temp` → 用真 tab 入口替换（不裸删，CLAUDE.md §8.3 时序约束）；DoD 校验无残留 |
| R6 | 回收 tab C 风图标未交付阻塞 SYS-010 | designer 出图（kevin-designer 首批任务）；未交付先用占位图标 + 标待补，不阻塞 SYS-010 逻辑 |
| R7 | RECYCLE-003 店员端不可达（Kevin 测不了店员核对）| Tier 2 临时入口 + ADR-0004 店员账号；kevin-qa Tier 1B 显式验可达性 + 停用即踢 401/403 |
| R8 | RECYCLE-003 调 PAY-105 时 transferbatch SDK 仍未批准 | D13 PAY-105 已落 mock；RECYCLE-003 走 mock 触发闭环（success/failed/重试均 mock）；真实权限+SDK 到位后小额回归（ADR-0006 外部 gate）|
| R9 | SnailJob 误用 Quartz / Flyway INSERT sys_job → 启动 hard-fail | 回收 no_show 凌晨任务 = `@Component + @JobExecutor` 薄壳 + 可单测 service；模块 pom 加 `ruoyi-common-job`；任务名/CRON 写 reports 由人在控制台注册；**禁止** sys_job INSERT |
| R10 | GACHA-111 被误解为「调概率」/ 误改 weight 数据 | 降开发优先级 = **仅入口迁移 + 做活回归**，不改概率/weight（reports `git diff` 自证）；R10 是早先「权重放低」误解的纠正点（已删原 GACHA-110 权重卡）|
| R11 | GACHA-111 依赖 SYS-010「我的」入口卡未就绪 | 本日最后一项，SYS-010 完工（入口卡 + tabbar）后再 spawn；纯 mp 无新增表/menu |

---

## 日终 closing 命令

```bash
cd doc/daily/D14
cat reports/*.md > summary.md
git add -A && git commit -m "D14: V1.2 收官 — 回收预约 RECYCLE-002 + 店员核对触发打款 RECYCLE-003 + tabbar 重构 SYS-010（去首页→拼豆/回收/我的）+ 扭蛋收尾 GACHA-111（入口迁我的+做活回归）"
# 写 D14/v1.2-integration-checklist.md（集成回归）
# 通知 Kevin 集中批量人验 V1.2 全部 mp ticket（BEAN-015 / COUPON-003 / RECYCLE-002 / RECYCLE-003 店员端 / SYS-010 / GACHA-111）
# 下一日 = D15：原 V1.1 收官 ADMIN-104 物流 2 态推进 / ADMIN-105 ⭐ 对账中心 / ADMIN-106 看板扩展 / ADMIN-108 软删回收站
```
