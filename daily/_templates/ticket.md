# <TICKET-ID> — <一句话标题>

**优先级**: P0 | P1 | P2
**复杂度**: S | M | L | XL
**关联 PRD**: doc/02-prd.md M<N> §<段>
**关联拆解**: doc/02-需求拆解.md §<N>.<M>
**关联 mockup**: design/mockup/<page>.html（如有）
**关联 ADR**: doc/_adr/NNNN-<title>.md（如有）
**依赖**: <上游 ticket>（如有）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆（dongjiaoshan D6 教训）。
> UI 索引在 V1.0 设计冻结期降级为"视觉参考"（不卡硬约束，详 .claude/agents/kevin-coder.md "设计冻结期"段）。

- **业务流**：doc/10-业务流权威图.md §<M-N>-<阶段>（**必填**）
- **字段表**：doc/11-字段权威表.md §<表名>（涉及 DB 表的 ticket **必填**）
- **UI 参考**（V1.0 设计冻结期）：
  - admin ticket：`N/A（设计冻结期 admin 走 ruoyi 默认）`
  - mp ticket：`design/mockup/<page>.html（视觉参考，不强求逐像素还原）` 或 `N/A（无对应 mockup）`

## What

（1-2 句描述做什么，不写"为什么" — 那在 PRD / 需求拆解里）

## AC（验收标准）

- [ ] AC 1：（可测试的具体描述，禁止"做得好""体验流畅"这种主观）
- [ ] AC 2：...
- [ ] AC 3：...
- [ ] **AC N: Tier 2 入口可达**（**mp ticket 强制**，CLAUDE.md §8.3）— Kevin 从 `<已有入口页>` 点 N 次能到达本 ticket 新页 / 触发本流程。
  - 如业务主线入口已建（如 5 tab / 会员中心首页 / 拼豆首页）→ 列出现成路径
  - 如业务主线入口还没建（下游 ticket 才建）→ **本 ticket 加临时入口**到 `pages/index/index.vue` 或最近相关已上线页 + 注释 `<!-- TODO(Tier2-entry-temp): <本 ticket id>, remove when <清理者 ticket id> merged -->`
  - 纯 admin / 纯后端 ticket 无需此 AC（跳过 Tier 2，CLAUDE.md §8.2）

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-<域>/`
  - 新增 Controller / Service / Mapper / DTO
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V<时间戳>__<TICKET-ID>-<desc>.sql`
- **Admin**：`code/main/plus-ui/src/views/gz-<域>/<page>.vue`
- **小程序**：`code/main/miniapp/src/pages/<page>.vue`
- **测试**：单测覆盖核心 service

## 备注

（如有特殊约束 / 合同条款关联 / 微信侧依赖 / 第三方接入要点）

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D<N>/<TICKET-ID> revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
