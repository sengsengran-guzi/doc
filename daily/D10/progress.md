# D10 — Progress

> V1.1 订单聚合 + admin 三件套 + mp 订单查看下沉。今日 ticket 状态表，Kevin 批量人验后更新「人验」列。

---

| Ticket | 标题 | 端 | AI 自测(1A+1B) | 人验(Tier2) | revision 轮次 | 状态 |
|---|---|---|---|---|---|---|
| GZ-USER-101 | 订单聚合统一接口（service 层 UNION） | 后端 | ✅ | — 无 | 0 | ✅ done |
| GZ-USER-102 | mp 订单详情统一页 | mp+后端 | ✅ | ⬜ 待批 | 0 | human-testing |
| GZ-USER-103 | mp 物流 C1 2 态展示（只读侧） | mp | ✅ | ⬜ 待批 | 0 | human-testing |
| GZ-USER-104 | 确认收货 + 自动签收（SnailJob） | mp+后端 | ✅ | ⬜ 待批 | 0 | human-testing |
| GZ-ADMIN-101 | 预购商品 CRUD（plus-ui，menu 9100 段） | admin | ✅ | — 无 | 0 | ✅ done |
| GZ-ADMIN-102 | 扭蛋池管理（plus-ui，权重归一化） | admin | ✅ | — 无 | 0 | ✅ done |
| GZ-ADMIN-103 | 订单管理三类聚合（plus-ui） | admin | ✅ | — 无 | 0 | ✅ done |
| GZ-ADMIN-201 | mp 店员端订单查看（下沉 ADR-0004） | mp+后端 | ✅ | ⬜ 待批 | 0 | human-testing |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

**close 口径**（CLAUDE.md §8.2）：
- 纯后端 / 纯 admin（USER-101 / ADMIN-101/102/103）→ Tier 1A+1B 全 ✅ 即终态 **done**，无人验
- mp（USER-102/103/104 / ADMIN-201）→ Tier 1A+1B ✅ 已 close 解锁下游，同时进**人验列待 Kevin 批量人验**（⬜）

---

## Tier 1B 集成期发现并闭环的 bug（3 个，均 Tier 1A 编译+单测抓不到的 Spring 上下文问题）

1. **双份 GzUnifiedOrderVo / ServiceImpl 启动冲突**（gz-user + gz-ord 各一份同名）→ ConflictingBeanDefinition + mybatis TypeAlias 冲突 → 补 `@Service("gzUserUnifiedOrderServiceImpl")`/`@Service("gzOrdUnifiedOrderServiceImpl")` + `@Alias("GzUserUnifiedOrderVo")`/`@Alias("GzOrdUnifiedOrderVo")` 限定。**这是补丁，D11 应下沉 gz-common 合并一份**（见下「对 D11 的债」）
2. （同上，TypeAlias 部分）
3. **GzLogisticsSignServiceImpl LambdaQueryWrapper abstract class cache miss** → 改 `new LambdaQueryWrapper<>(clazz)` + QueryWrapper 修复

## 待人工动作（非阻塞 close）

- **SnailJob 控制台注册**（USER-104）：任务名 `GZ-LOGISTICS-AUTO-SIGN`，执行器路由 `gzLogisticsAutoSignExecutor`，CRON `0 0 * * * ?`（每小时整点 Asia/Shanghai），阻塞策略 DISCARD，组 ruoyi_group。代码不自动注册，需人在控制台建一次。
- **重建库后** flush redis（新 seed gz_express_carrier 字典 + gz_ord_product_status 字典 + auto-sign-days config）：`docker exec sensenran-dev-redis redis-cli -a ruoyi123 --no-auth-warning FLUSHDB`

## 对 D11 的债 / 源头 doc 回填（§9.5 改源头）

1. **双份统一订单 VO/Service 下沉 gz-common**（D11 优先）：USER-101（C 端按 user UNION）+ ADMIN-103（admin 走 pay_transaction 回查）两份同形 VO，当前靠限定名共存。下沉 gz-common 单份 `GzUnifiedOrderVo` + 共用映射逻辑，删限定名补丁。
2. **doc/11 §8.1 + USER-101 ticket AC1 鉴权口径回填**：C 端「我的订单」用 `@SaCheckLogin + user_id 归属`，**不是** `@SaCheckPermission("gz:user:orders:list")`（那是店员门 ADR-0004，挂上去 C 端 403）。删/改源头 doc 的该 perm key。
3. **跨模块循环依赖纪律补注**：gz-ord 已单向依赖 gz-user，C 端聚合不可反向注入 gz-ord/gacha service（会成 Maven 环）→ 用只读 entity/mapper 镜像。USER-101 + ADMIN-201 同根因，建议写进 ticket 模板 / doc 架构段。
4. **ADMIN-102 菜单口径回填**：任务卡写 `gz:gacha:pool:*` + menu 10100 段，但 GACHA-101 已 Flyway 应用 10000 段 + `machine:*`/`prize:*`（不可改）→ ADMIN-102 复用既有授权未新建。doc 应对齐 reality。

## 阻塞 / 风险

无未解阻塞。8 ticket 全 Tier 1A+1B ✅。

## 已挪到明日的 ticket

无。D10 清单 8 个全部完成。D11：物流推进下沉 mp ADMIN-104 / 对账中心 ADMIN-105 / 看板 ADMIN-106 / 回收站 ADMIN-108 + 上述 VO 下沉债。
