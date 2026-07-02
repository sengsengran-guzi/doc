# ADR-0013 扭蛋「奖品」升级为「可复用产品库 + 机器×产品投放线」

- 日期：2026-06-24
- 状态：Accepted
- 决策人：Kevin（甲方需求：产品可跨机器复用 + 独立产品编辑入口；主线程评估与落地）
- 关联 ticket：GZ-GACHA-112（产品库 + 投放线改造，全栈）
- 落地批次：待排（V1.2 扭蛋域新模块，合同 §8.5「另议」范畴）
- 关联文档：doc/11 §7.1/§7.2 字段表 · doc/10 §8 抽奖流 · PRD §M2 · [ADR-0008](0008-seat-type-quota-model.md)（同类「内联→主数据」重构思路）

---

## Context

现有扭蛋模型（GZ-GACHA-101）：`gz_gacha_machine`（机器）+ `gz_gacha_prize`（奖品池）。
**奖品是内联在某台机器下创建的** —— 名称 / 图片 / 稀有度 / 参考价全部长在 `gz_gacha_prize` 行上，`machine_id NOT NULL`。

- 一台机器挂多条 prize（加权随机池），抽奖按 `WHERE machine_id=? AND enabled=1 AND stock_remain>0` 取在池行、按 `weight` 归一化抽 1 件 —— 「一台机器 N 个奖品」本就成立（PRD §M2 钉死）。
- **痛点**：奖品不可跨机器复用。同一款谷子要投放进 3 台机器，得建 3 次、传 3 次图、改价要逐台改。甲方要「一个编辑产品的地方 + 多个产品组合成一台机器」。

被否的轻量做法（产品库只当「新建奖品时的模板」复制名/图、不建关联）：**改产品不会同步到已投放机器**，不满足「一处编辑全局生效」，淘汰。

## Decision

### 1. 新建产品库主表 `gz_gacha_product`（产品 = 跨机器共享主数据）

产品库承载「产品固有属性」（改一处、所有引用机器实时生效，因走 FK join 取值）：

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED PK | 主键（不暴露前端） |
| `tenant_id` | VARCHAR(20) NOT NULL DEFAULT '1001' | 租户（铁律 #2，INSERT 不显式赋） |
| `product_no` | VARCHAR(32) NOT NULL | 业务码 `GPRD-yyyyMMdd-6位序号` |
| `name` | VARCHAR(128) NOT NULL | 产品名 |
| `image_id` | BIGINT UNSIGNED NULL | 产品图 FK 语义→`gz_file_object.id`（禁存裸 url，铁律对齐） |
| `reference_value_cent` | BIGINT NULL | 公示参考价（分，可空→不显示） |
| `ip_tag` | VARCHAR(64) NULL | IP 标签（产品库筛选用） |
| `enabled` | TINYINT NOT NULL DEFAULT 1 | 1 可投放 / 0 停用（停用不能再加入新机器；已投放线不受影响） |
| `version` | INT NOT NULL DEFAULT 0 | 乐观锁 |
| + 标准审计列 | | `create_time/update_time/create_by/update_by/create_dept` |
| `del_flag` | CHAR(1) NOT NULL DEFAULT '0' | 软删 0/2（@TableLogic） |
| `remark` | VARCHAR(500) NULL | 备注 |

约束：`UNIQUE KEY uk_gacha_product_no (tenant_id, product_no)`；`KEY idx_gacha_product_ip (tenant_id, ip_tag)`。

### 2. `gz_gacha_prize` 改造为「机器×产品投放线」

投放线承载「该产品在该机器的投放参数」（**每台独立**）：

- **新增**：`product_id BIGINT UNSIGNED NOT NULL` —— FK 语义→`gz_gacha_product.id`（不加 DB 外键，应用层保证，与全项目一致）。
- **保留**（每台独立）：`machine_id` / `prize_no` / `rarity` / `weight` / `stock_initial` / `stock_remain` / `enabled` / `version` + 审计 + `del_flag`。
- **删除**（搬到产品库，改 join 取值）：`name` / `image_id` / `reference_value_cent`。
- **新增唯一约束**：`UNIQUE KEY uk_gacha_prize_machine_product (tenant_id, machine_id, product_id)` —— 同一产品在一台机器只投放一次（再投放=改已有线的权重/库存）。
- 原索引 `idx_gacha_prize_pool (tenant_id, machine_id, enabled, stock_remain)` 保留（抽奖在池候选仍走它）。

**属性归属（甲方拍板）**：产品库 = 名 / 图 / 参考价（固有）；投放线 = **稀有度** / 概率权重 / 库存 / 启用（均按机器可调，同一产品在 A 机可标 SSR、B 机可标 SR）。

### 3. 抽奖事务 & 快照：几乎不动

- 抽奖仍锁 `gz_gacha_prize` 在池行、按 `weight` 归一化抽（`ProbabilityNormalizer` / `SecureRandomDrawer` / `SELECT FOR UPDATE + version` 全不变）。
- `GachaSnapshot.Prize` 抽奖时已把 名/图/稀有度/参考价 落快照 → 落库后**历史抽奖记录 / 订单 / 已出货图鉴不受改表影响**。
- 仅运行时「读取展示字段」从 prize 行改为 join `gz_gacha_product`（机器详情 / 奖品池列表 / 抽奖前展示）。快照写入逻辑改为：从产品库取 名/图/参考价 + 从投放线取 稀有度，组装快照。

### 4. 图鉴 / 集齐：保持现状（每机器集齐）

`gz_user_gacha_collection` 仍按 `UNIQUE(tenant_id, user_id, machine_id, prize_id)`，集齐徽章 = 集齐该机器所有投放线（PRD §7.5 玩法不变）。**不**做跨机器全局产品图鉴。图鉴格子展示改 join 产品库取名/图。

### 5. 存量数据迁移（Flyway，1:1 自动建产品）

新环境无存量则空跑；dev/staging/prod 已有 prize（如截图「火影忍者测试」机器）按下列一条龙迁移（同一迁移文件内）：

1. 建 `gz_gacha_product` 表。
2. 对每条现有 `gz_gacha_prize`：用其 `name/image_id/reference_value_cent` **1:1 建一条 `gz_gacha_product`**（`product_no` 用 `GPRD-` + 旧 prize id 兜底唯一），`ip_tag` 取机器 `ip_tag`（可空）。
3. `gz_gacha_prize` 加 `product_id` 列 → 回填指向 step2 新建产品。
4. 加唯一约束 `uk_gacha_prize_machine_product`；删旧列 `name/image_id/reference_value_cent`。

**同名不自动合并**（避免误并不同产品）；甲方之后想去重在产品库手动整理（改投放线 product_id 指同一产品 + 删多余产品）。`gz_gacha_prize` 不 DROP、不丢历史。

### 6. Admin 两处（产品库独立 + 挂载并入机器编辑弹框）

- **「产品库」页**：菜单 `10005`（GACHA 段 10000-10099，对齐铁律 #6），perms `gz:gacha:product:list/query/add/edit/remove`，按钮 `10050-10054`，授 owner role 100。产品 CRUD + 传图（ruoyi OssClient）+ 参考价（元↔分）+ IP 标签 + 启用开关。
- **挂载产品并入「扭蛋机管理」编辑弹框**（甲方反馈：独立奖品池页多余，改为更直接的内嵌）：进某台机器「编辑」→ 弹框内「挂载产品」区，从产品库选产品加入本机 + 配 稀有度 / 权重 / 库存 / 启用（即时保存，复用 prize API）。已加入产品不可重复加（uk 拦）。**新增机器**先存基础信息（需 machineId 才能挂产品），保存后「编辑」挂载。
- **去掉独立「奖品池管理」菜单**（10002，C 路由 + plus-ui `gz-gacha/prize/index.vue` 已下线）；投放线按钮权限 `10020-10024` reparent 到机器菜单 `10001` 下保留（内嵌区复用，迁移 V202606300003）。

### 7. mp 端：单机详情只显示产品列表，**不显示概率**（甲方拍板）

- 单机详情「全部奖品」网格：每格显示 **产品图 + 产品名 + 稀有度标签 + 参考价**（可空不显示）。
- **删除概率公示模块 / 概率折叠区**：weight 仅后台驱动抽奖，不对 C 端展示任何概率百分比。
- mp 展示 VO（`GzGachaMachineDetailVo` / prize 列表项）改为 join 产品库取 名/图/参考价，稀有度取投放线；移除归一化概率字段的对 mp 输出。
- 合规备忘：国内盲盒/抽奖类目「概率公示」有时有监管要求；甲方明确选择不展示，记录在案。

## 实施清单（writing-plans 展开）

1. DDL：`gz_gacha_product` 建表 + `gz_gacha_prize` ALTER + 迁移 + 菜单/perm（Flyway 新文件，时间戳 > 当前最大）。
2. 后端：`GzGachaProduct` 域全套（entity/bo/vo/mapper/service/controller）+ `GzGachaPrize` 改造（去内联列、加 product_id、CRUD 改「选产品」）+ 抽奖快照组装改 join + mp/admin VO join。
3. Admin：新产品库页 + 奖品池页改造 + i18n（zh/en）。
4. mp：单机详情去概率、产品列表化。
5. 权威蓝图：更新 doc/11 §7（拆 `gz_gacha_product` + 改 §7.2 投放线字段）+ doc/10 §8（展示读 join、概率不对外）。
6. 测试：后端单测（产品 CRUD / prize 选产品 / 抽奖快照仍正确）+ admin Playwright + mp 模拟器 E2E（产品库 CRUD、奖品池选产品、机器详情产品列表无概率）。

## Consequences

- ✅ 满足「一处编辑产品、全局机器生效」；运营投放成本大降（选已有产品 vs 重建）。
- ✅ 抽奖事务 / 历史快照零风险（快照隔离）。
- ⚠️ 一次性 schema 改造 + 迁移（已应用迁移不可改，铁律 #5；迁移须在所有环境验真）。
- ⚠️ 属于 V1.2 已「只做活回归」的扭蛋域上的新模块，工时/排期合同 §8.5 另议。
- ⚠️ mp 去概率公示偏离 PRD §M2「看清概率」原意，为甲方明确决策，合规风险甲方自担。
