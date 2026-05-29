# ADR-0001 V1.0 业务运营账号与业务表 tenant_id 对齐到 '1001'

- 日期：2026-05-29
- 状态：Accepted
- 决策人：Kevin（kevin-product 评估，kevin-coder 落地）
- 关联 ticket：GZ-ADMIN-001（裂痕引入）、GZ-BEAN-001（裂痕暴露 + 修复）

---

## 背景

CLAUDE.md §6 #2 强约束「所有业务表 `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`」，但 GZ-ADMIN-001 落地时：

- `sys_user` 表里 `gz_owner`（user_id=100）、`gz_staff_chengdu`（user_id=101）的 tenant_id 落为 `'000000'`（ruoyi 默认主租户）
- `gz_bean_store` seed CD001 走 InjectionMetaObjectHandler 默认 tenant=`'1001'`

结果：业务运营账号登录后，列表走 tenant 过滤 → admin 端看不到 CD001；admin 端新建的门店落到 `'000000'` → seed 数据和新建数据"看不见对方"。kevin-qa Tier 1B 跑 admin Playwright 时暴露了"列表渲染空白"现象（虽然根本原因 50% 是 plus-ui `resp.data` 解包 bug，另一半是这里 — 即使解包修了，gz_owner 仍看不到 CD001）。

## 选项

### A 方案（采用 ✅）：业务运营账号迁到 '1001'

```sql
UPDATE sys_user SET tenant_id='1001' WHERE user_name IN ('gz_owner','gz_staff_chengdu');
DELETE FROM gz_bean_store WHERE tenant_id='000000';  -- 清理 kevin-qa 测试期间产生的脏数据
```

- ✅ 业务表保持 `'1001'`（与 CLAUDE.md §6 #2 一致）
- ✅ 业务运营账号迁过去后，新建数据自动落 `'1001'`，可见 CD001
- ✅ 改动小、回滚清晰、不需要修 ruoyi 默认租户配置
- ⚠️ `admin` 超管 tenant 仍 `'000000'`（保留 ruoyi 默认主租户能力 — admin 可跨租户切换）
- ⚠️ V1 当前仅 1 个业务租户 `'1001'`，未来如开新租户（如 `'1002'`），新业务账号 INSERT 时要显式指定 tenant_id

### B 方案（拒绝 ❌）：业务表改用 '000000'

- 改 InjectionMetaObjectHandler 默认值 / 改 seed
- ❌ 违反 CLAUDE.md §6 #2 强约束
- ❌ 与 dongjiaoshan 项目惯例不一致
- ❌ 与未来开多租户的设计冲突（`'000000'` 是超管租户，不应承载业务数据）

### C 方案（拒绝 ❌）：在 sys_tenant 新增 `'1001'` 行 + 修 ADMIN-001 source migration

- ❌ V1 只有 1 个业务租户，sys_tenant 行可以晚加（不影响 InjectionMetaObjectHandler 工作）
- ❌ 改 ADMIN-001 历史 migration 违反「不记录中间态 / migration 不可逆」（CLAUDE.md §12）
- ⚠️ 留作 V1.1 多租户上线时再做（届时 sys_tenant 必须有 `'1001'` 行才能在 ruoyi 租户切换 UI 显示，但 V1 不需要 UI 切换）

## 决策

采用 **A 方案**。新 migration `V202606010950__GZ-BEAN-001-fix-r1-tenant-realignment.sql` 落地。

## 影响

- `sys_user` 中 `gz_owner`、`gz_staff_chengdu` 的 tenant_id 从 `'000000'` 改为 `'1001'`
- `gz_bean_store` 清理 tenant=`'000000'` 脏数据（kevin-qa 测试期间产生的 TEST-001 / QA-E2E-001，均为软删态 del_flag=1）
- 业务运营账号下次登录时 token 中的 tenant_id 自动变为 `'1001'`，列表可见 CD001
- 下游 BEAN-002 / BEAN-003 / BEAN-004 等业务 ticket 不再有"假可用"风险
- ADMIN-001 历史 migration **不改动**（CLAUDE.md §12 不记录中间态原则；事实状态由新 migration 表达）

## 后续 / 待办

- V1.1 多租户上线时若需 ruoyi 后台租户切换 UI → 加 `sys_tenant` `'1001'` 行（独立 ticket，本 ADR 不涵盖）
- 未来如出现「ADMIN-XXX seed 业务账号」类型 ticket，**默认 tenant_id 必须 `'1001'`**，不要再写 `'000000'`
- 未来如出现「新增业务租户 `'1002'`」需求 → 拆 ADR-N 独立决策
