# D7x — D1-D7 测试集中修复批次

> **性质**：非顺序 daily，是 Kevin 跑 D1-D7 批量人验时发现问题的**集中修复批次**。
> **原则（硬约束）**：
> 1. **零 V1.1 推诿** —— 测试期发现的问题 + 让功能真正可用/可运营/安全的完整闭环，**都在 D7x 内彻底解决**，不留尾到 V1.1。
> 2. **整批派发** —— 任务描述先写完整；待 Kevin 基本测完（可能还会追加问题），再**一起派发**实现，避免边测边改的碎片化。
> 3. 真·未来新功能（如「更多 mp 管理端功能下沉」）≠ 本批次欠债，单列说明、不混入。

---

## 一、测试会话已内联修复（记录在案，无需再做）

| # | 问题 | 修复 | 产物 |
|---|---|---|---|
| 1 | 后端启动 Flyway `${...}` 占位符 hard-fail | 关 `placeholder-replacement` | application.yml |
| 2 | 后端启动 gz-news mapper `<script>` 内裸 `<=` XML 解析失败 | `<=` → `&lt;=` | GzNewsArticleMapper.java |
| 3 | admin 一堆 ruoyi 自带无关菜单 + 重复"数据看板"空壳 | 迁移隐藏（visible=1） | V202606041300 |
| 4 | 拼豆所有日期"暂无开放时段"（表无 seed） | seed 时段模板 + 座位 | V202606041400 |
| 5 | admin 文章提交 `Unknown column 'create_dept'` | 补列 | V202606041500 |
| 6 | mp 资讯 `NumberFormatException: "system"`（create_by varchar+脏值） | 清脏值 + 列改 BIGINT | V202606041600 |
| 7 | 登录默认企业是系统租户 000000（gz_owner 登不进） | 默认选业务公司 1001 | login.vue |
| 8 | mp 拼豆确认页门店/时段显示 %xx + 手机号授权 dev 拿不到 | onLoad decode + getPhoneNumber 补 wxMOCK 短路 | confirm.vue |
| — | 拼豆"提交前必须先支付"质疑 | 澄清：V1.0 拼豆=合同非交易免费模块，按设计不收费（无改动） | — |

**测 admin 须知**：登 `gz_owner / gz_owner123!`（租户 1001），不是 ruoyi 超管 admin（000000）。

---

## 二、本批次实现任务（ADR-0004 落地 + 完整闭环）

**主题**：核销搬到 mp + 建好 mp 管理端权限底座（决策见 [doc/_adr/0004](../../_adr/0004-mp-admin-permission-foundation.md)）。
**完整闭环 = 底座（含停用即时踢 + owner 自助绑定）+ 核销店员端 + 核销被扫端二维码 + type-check 收尾。**

| Ticket | 标题 | 端 | 复杂度 | 状态 |
|---|---|---|---|---|
| [GZ-SYS-007](tickets/GZ-SYS-007.md) | mp 管理端权限底座 | 后端+mp+admin | L | AC1-8 已实现；**AC9 停用自动踢 / AC10 owner 绑定管理 待做** |
| [GZ-BEAN-011](tickets/GZ-BEAN-011.md) | mp 扫码核销（店员端） | 后端+mp | M | 已实现；真机闭环待 012 |
| [GZ-BEAN-012](tickets/GZ-BEAN-012.md) | 顾客核销码二维码渲染（被扫端，接 @uqrcode/js） | mp | S | **待做**（含 success.vue 假 QR 网格替真码） |
| [GZ-SYS-008](tickets/GZ-SYS-008.md) | mp type-check 噪音清零 | mp | S | **待做** |
| [GZ-UI-001](tickets/GZ-UI-001.md) | mp 视觉 token 收口 + 客服浮层换皮 | mp | S | **待做**（上线前视觉审计：FAB 粉色 P0 + verify-scan/me 伪 token P1） |
| [GZ-UI-002](tickets/GZ-UI-002.md) | tabbar 3 套 C 风描边图标 | 设计+mp | S | **待做**（三 tab 共用同图 P0；依赖 designer 出图） |

> **已实现部分**（GZ-SYS-007 AC1-8 + GZ-BEAN-011）= 我（主线程）此前提前派 kevin-coder 跑的，代码已在工作树 + 自测通过（reports/ 下）。**流程已纠正**：剩余任务（SYS-007 AC9/AC10、BEAN-012、SYS-008 + 你后续测试再发现的）**不再零散派**，等你测试基本收尾后整批派发。

### 待派发清单（测试收尾后一起做）
1. GZ-SYS-007 AC9：停用 sys_user → 自动踢 mp token（现仅手动端点）
2. GZ-SYS-007 AC10：owner admin 自助绑定/解绑店员（现靠 seed/SQL）
3. GZ-BEAN-012：顾客二维码真渲染（现降级文本，核销真机不可扫）+ success.vue 假 QR 网格换真码
4. GZ-SYS-008：mp type-check 清零
5. **GZ-UI-001**：mp 视觉 token 收口 + 客服浮层换皮（P0 FAB 粉色 `#ff6b81` 全站 / P1 verify-scan + me staff-badge 伪 token；纯改皮 + grep gate 防回潮）
6. **GZ-UI-002**：tabbar 3 套 C 风图标（P0 三 tab 共用同图；依赖 designer 出图，可与 UI-001 并行起，替换等图）
7. 〔占位〕Kevin 后续测试新发现的问题 → 追加 ticket 进本表

> **视觉审计来源**：2026-06-01 kevin-designer 对 21 个 V1.0 mp 页做上线前 C 设计系统合规体检。结论 = **20/21 页 C-DNA 落地扎实（detail/select/news-list 可当标杆给甲方），唯客服浮层粉色圆钮 + tabbar 三同图 是用户一眼能看出"没做完"的两处**。emoji 多为 §7.5 占位示意（吉祥物/九宫格图标待替 SVG），不判违规；`<wd-*>` 裸标签 = 0，组件库无关纪律守住。详见各 ticket。

### 不在 D7x（真·未来，非欠债）
- 更多 mp 管理端功能下沉（订单/物流/资讯管理等）—— 新功能，底座已就绪，边际成本 = 加 `@SaCheckPermission` + 授权。

reports 落 `D7x/reports/<TICKET>.md`。
