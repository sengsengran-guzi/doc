# D18 — kevin-test.xlsx 6 项客户反馈实现

> 来源：`doc/test/kevin-test.xlsx`（5 条）+ Kevin 现场追加第 6 条（看板过期单结单/补核销）。
> 计划：`~/.claude/plans/doc-test-kevin-test-xlsx-5-mossy-quasar.md`（已批准）。
> 全部围绕 **拼豆 GZ-BEAN** + **优惠券 GZ-COUPON**，上线后 revision。

## Ticket 索引（6）— 全部 Tier 1A + 1B ✅ close

| Ticket | 域 | 内容 | 状态 |
|---|---|---|---|
| GZ-COUPON-003 | COUPON | 优惠券规则自动发放（定时扫描 + 去重补发） | ✅ Tier 1A+1B |
| GZ-BEAN-037 | BEAN | 看板同用户连续时段高亮 + 提前核销（默认沿用座，可改选） | ✅ Tier 1A+1B |
| GZ-BEAN-038 | BEAN | 延时改输入分钟（精确到分，占用按整点格回收）；mp 溢出占格(3b) | ✅ Tier 1A+1B |
| GZ-BEAN-039 | BEAN | admin 代客预定（立即锁座 + 线下已付） | ✅ Tier 1A+1B（2 bug 闭环：防超卖+散客userNo） |
| GZ-BEAN-040 | BEAN | 已核销单改派座位 | ✅ Tier 1A+1B |
| GZ-BEAN-041 | BEAN | 看板过期单批量结单 / 补核销（pending\|no_show→used 翻案 / 标爽约 / 标已结束） | ✅ Tier 1A+1B |

**测试总账**：后端 gz-bean 196 + gz-coupon 56 单测全绿；admin Playwright（看板/预约/券模板 3 页）✅；mp 模拟器 E2E smoke ✅；后端集成 curl 6 ticket 全 ✅（GZ-BEAN-039 修后复测 4002 防超卖 + 散客用户复用均过）。6 个 ticket 均纯 admin/后端，无真机微信原生，AI gate 全 ✅ 即终态，无人验残留。

## 关键决策（与 Kevin 确认）

1. 需求1 = **定时扫描**（复用已有 filtered 策略 + auto_issue 开关 + 去重，不走注册即时事件）。
2. 需求3a = **记录精确分钟，占用按整点格回收**（slot_end 到分钟，配额/防超卖整点格，无需改表）。
3. 需求3b = 3a 延伸：延时溢入下一整点格 → mp 该桌型该格配额 −1（现有 `countActiveCoveringSlot` 已交付，**零 mp 改动**）。
4. 需求4 = **立即锁座 + 线下已付**（store source=admin，out_trade_no=NULL，不进微信对账 GMV；用户身份 find-or-create by mobile，无则门店租户级「线下散客」占位）。
5. 需求6 = 看板「过期待处理」区 + 批量结单；**补核销支持 pending|no_show 翻案**（与 no_show cron 解耦）。
   **根因实锤**：`gzBeanNoShowMarkTask` cron 未在 SnailJob 控制台配 → 过期单滞留可点核销。Kevin 需补配控制台调度（见下）。

## 权限决策（偏离原计划，降风险）

原计划 T2/T4/T5/T6 各新建 menu 权限点（6062-6064）。**实际复用 `gz:bean:booking:verify`**（看板放座/延时已是此模式）—— 全是店员现场操作、同信任级，避免新 menu seed + 角色授权撞号风险（项目踩坑史）。**唯一 DDL = T4 的 `source` 列**（`V202606301934__GZ-BEAN-039-booking-source.sql`）。

## SnailJob / cron 决策（2026-06-30 Kevin 拍板：走路 B）

**根因**：prod `docker-compose.deploy.yml` 没部署 SnailJob server，且 `SNAIL_JOB_ENABLED` 默认 false → **线上 25 个定时任务一个都没跑**（no_show / 券过期 / 对账 / 打款查单 / 资讯定时发布全停）。"过期单还能点核销"即 `gzBeanNoShowMarkTask` 没跑。

**决策 = 路 B：不上 SnailJob 基建**，靠本批新增的手动工具兜底：
- 过期单 → 看板「过期待处理」面板，店员每天收摊手动批量结单（补核销 / 标爽约 / 标已结束）。
- 优惠券规则发放 → 券模板页「立即试跑」手动点一轮（含去重）。

本批功能**设计成 cron 配不配都能用**，故路 B 零基建即可上线。日后要自动化（路 A）再起 `ruoyi-snailjob-server:5.6.1` 容器 + 开 `SNAIL_JOB_ENABLED=true` + 控制台 8800 注册任务（`gzBeanNoShowMarkTask` `0 0/5 * * * ?` / `gzCouponAutoIssueTask` `0 0/15 * * * ?`，组 ruoyi_group）。详见 memory `snailjob-not-deployed-in-prod`。

## 测试

- **后端 Tier 1A 绿**：gz-bean `mvn clean install` → **196 tests 0 fail**（含新增 reassign/settle/markNoShow/batchSettle/extend-minutes/3b 链路）；gz-coupon **56 tests 0 fail**。
- **Tier 1B（主线程派 kevin-qa）**：admin Playwright（看板高亮/延时分钟/代客预定/改派/过期批量结单 + coupon 开关/试跑）+ mp 模拟器 E2E（延时溢出→下单页该格置灰）+ 后端集成（真 DB 防超卖/补核销翻案）+ 契约回归。
- 详见 `reports/`。

## 商业口径备注（已实现默认值，Kevin 可调）

- 代客线下单 **不计微信对账 GMV**（无通道流水）。
- 3b「不可预定」精确语义 = 该桌型该格配额 −1（单桌即置灰，多桌为余量递减）；可据此向客户说明。
