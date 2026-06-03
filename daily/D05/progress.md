# D05 — Progress

> 拼豆收尾日。6 ticket 全部 AI Tier 1A ✅。mp ticket 进人验列待 Kevin 批量人验；纯后端/admin ticket AI ✅ 即终态。

---

| Ticket | 标题 | AI Tier 1A | AI Tier 1B | testing-human | revision | 状态 |
|---|---|---|---|---|---|---|
| GZ-BEAN-005 | mp 预约详情 + QR 大图 | ✅ build+57 vitest | ✅ 单测/可达性 | ⬜ 待批量人验（真机扫码） | 0 | ✅ AI done，进人验列 |
| GZ-BEAN-006 | mp 我的预约列表 4 tab | ✅ build+vitest 16 | ✅ 全量 73 回归 | ⬜ 待批量人验（4 tab 真机） | 0 | ✅ AI done，进人验列 |
| GZ-BEAN-007 | mp 取消预约 wiring | ✅ build+vitest 11 | ✅ 全量 84 回归 | ⬜ 待批量人验（取消流程真机） | 0 | ✅ AI done，进人验列 |
| GZ-BEAN-008 | admin 列表 + 扫码核销 | ✅ 61 单测+build:prod | ⏳ Playwright E2E 待全栈 | — 纯 admin 无人验（§8.2） | 0 | ✅ AI done（待 E2E） |
| GZ-BEAN-009 | no_show cron | ✅ 11 单测+install | ✅ 单测（机械） | — 纯后端无人验（§8.2） | 0 | ✅ done（终态） |
| GZ-BEAN-010 | mp 拼豆首页 landing | ✅ build+22 vitest | ✅ 可达性 grep | ⬜ 待批量人验（落地页真机） | 0 | ✅ AI done，进人验列 |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

---

## 三端构建（DoD gate，主线程日终验）

- 后端 `mvn install gz-common,gz-bean -am`：**BUILD SUCCESS** ✅
- mp `pnpm type-check`：D05 贡献零 TS 错（仅剩 2 个 pre-existing 历史债，见下）；`build:mp-weixin` 产物全套 ✅；`pnpm vitest run` **11 文件 84/84** ✅
- plus-ui `pnpm build:prod`：**✓ built 12.2s** ✅

---

## 阻塞 / 风险

- **Flyway 未接入**（无依赖无配置，CLAUDE.md §5/§6 写的"自动跑"与现实不符）：DB schema 手工导入。D05 唯二新 DDL 需 Kevin 手工跑：
  - `V202606020020__GZ-BEAN-010-default-banner-config.sql`（banner 默认配置）
  - `V202606020030__GZ-BEAN-008-dict-booking-status.sql`（状态字典，BEAN-008 已在 dev MySQL 跑过 + flush dict cache）
  - BEAN-009 无 DDL（SnailJob job 走控制台注册，非 Flyway）
- **2 个 pre-existing 类型债**（非 D05 引入，build 不阻塞但 type-check exit 1）：
  - `BizCustomerServiceFab.vue:92`（GZ-SYS-004）
  - `pages/login/index.vue:35`（GZ-SYS-002）
  - 建议开独立小 ticket 清，不混进 D05。
- **BEAN-008 admin Playwright E2E（Tier 1B）** 需后端 + plus-ui + MySQL + Redis 全栈在线，当前环境未起全栈 → 折到 Kevin 批量验证或专门 qa 跑。
- **SnailJob no_show job** 需在 SnailJob 控制台注册（job 名 gzBeanNoShowMarkTask / cron `0 0 2 * * ?`），见 reports/GZ-BEAN-009.md §控制台注册。

## 已挪到明日的 ticket

无。D05 6 ticket 全部实现完成。**D06 起进入 GZ-USER 会员中心 + GZ-NEWS 资讯阶段。**
