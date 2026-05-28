# D03（Kevin 口径 d2）— Admin 框架 + mp 5 tab + 管理员账号 + 操作日志

> 日期：2026-05-29（周五）
> 阶段：V1.0 实施期 day 2
> 上一日：[D02](../D02/README.md) ｜ 下一日：[D04](../D04/README.md)

---

## 今日目标

- **主线 1**（admin 后台立起）：管理员登录 + owner/staff 角色 + 账号 CRUD + 后台框架（侧边栏/topbar/面包屑）+ 操作日志（GZ-ADMIN-001 + GZ-ADMIN-002 + GZ-ADMIN-004 + GZ-SYS-006）
- **主线 2**（mp 全局壳）：底部 5 tab 路由 + 占位页 + 全局 toast / loading / 客服浮层挂载（GZ-ADMIN-005）

完工后甲方可登入后台看 D02 已建的 C 端用户列表 + 操作日志已能记录管理员行为；mp 端 5 tab 可切换（V1.0 不上线的扭蛋 / 预购 tab 跳「敬请期待 V1.1」占位页）。

**今日同步推进**（**Kevin 自推进，AI 不参与**）：微信支付 V3 商户号资料提交（合同 §2.1（一）+ 强约束 #12，5-10 工作日审批），D07 (d6) PAY-001 实施前必须到位。

## Ticket 清单（5 个，按依赖顺序）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-ADMIN-001 | 管理员登录 + 账号 / 角色 | S | GZ-SYS-001 ✅ | pending |
| GZ-ADMIN-004 | 后台路由 / 布局 / 侧边栏 | S | GZ-ADMIN-001 | pending |
| GZ-ADMIN-002 | 管理员账号 CRUD | S | GZ-ADMIN-001 + GZ-SYS-006 | pending |
| GZ-SYS-006 | 操作日志（管理后台审计） | S | GZ-ADMIN-001 | pending |
| GZ-ADMIN-005 | mp 底部 5 tab + 全局布局 | S | GZ-SYS-001 ✅ | pending |

详见 `tickets/<TICKET-ID>.md`。

**依赖说明**：
- **串行链 1**：ADMIN-001 → ADMIN-004 → ADMIN-002（账号 CRUD UI 依赖布局壳） ⇄ SYS-006（操作日志写入逻辑，被 ADMIN-002 调用）
- **并行链 2**：ADMIN-005（mp 5 tab）与 admin 完全无依赖，可并行
- **实际派单建议**：先派 ADMIN-001 + ADMIN-005 并行 → ADMIN-001 完工后并行派 ADMIN-004 + SYS-006 → 最后派 ADMIN-002

## 派单方式

```
开始 d2
```

主线程动作：
1. 读 D03/README.md + 依赖图
2. **第一波 spawn**：ADMIN-001 + ADMIN-005（互无依赖）
3. **ADMIN-001 ✅ 后第二波 spawn**：ADMIN-004 + SYS-006
4. **ADMIN-004 + SYS-006 ✅ 后第三波 spawn**：ADMIN-002
5. 5 个 ticket 全部 ✅ → Kevin testing-human + 日终 closing

## 今日特殊约束

- **复用 ruoyi 自带 sys_user / sys_role / sys_menu**：本日 ticket 不新建管理员表，全部基于 ruoyi 自带 sys_user 范式（参考 dongjiaoshan ruoyi-djs-common 范式）
- **owner vs staff 两级**：sys_role 插入 2 条（roleKey=`owner` / `staff`），ruoyi 自带"超级管理员"保留作为开发兜底（admin 账号 admin/admin123 上线前删除）
- **关联门店字段**：sys_user 加 `gz_store_id BIGINT` 字段（V1.0 单门店但模型预留多门店，staff 用户绑定门店；owner 跨门店）— DDL 在 ADMIN-001 落地
- **操作日志范式**：复用 ruoyi 自带 `sys_oper_log` 表 + `@Log` 注解（org.dromara.common.log.annotation.Log），SYS-006 仅需在自定义业务 Controller 加 `@Log(title="...", businessType=BusinessType.UPDATE)`，不重写日志框架
- **mp 5 tab 中 2 个 V1.0 占位**：扭蛋 / 预购 tab 跳「敬请期待 V1.1」占位页（GZ-ADMIN-005），点击不报错 / 不跳 404
- **menu_id 段**：本日插入的菜单走 5000-5099 段（CLAUDE.md §6 #6 GZ-SYS 通用 5000-5999；本日属系统底座菜单）
- **不要 commit**：5 个 ticket 全部 ✅ + Kevin testing-human 通过后再统一 commit

## 与昨日 reports 对账（D02）

D02 完工后预期产物：
- ✅ gz_user 表已建（SYS-003），admin 端 C 端用户列表可查 — 本日 ADMIN-004 侧边栏要把这个菜单挂上
- ✅ gz_file_object 表已建（SYS-005），admin 端文件管理菜单也在侧边栏
- ✅ 客服浮层组件 `BizCustomerServiceFab` 已写（SYS-004），本日 ADMIN-005 在 App.vue 根挂载它
- ✅ wxMOCK 短路通道已建（SYS-002），mp 5 tab 切换时不触发登录拦截（资讯 tab 允许游客）

如 D02 任一 ticket 未 ✅ → 本日 ADMIN-004 / 005 仍可推进（互无强依赖），仅菜单挂载延迟到 D02 收尾再补。

## 完成判定（DoD）

- [ ] 5 个 ticket 任务卡 §revision 段空
- [ ] 5 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block raw output）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] testing-human.md 全勾：
  - admin 端 owner / staff 双角色都能登录
  - 切换 staff 时仅看到子集菜单
  - 添加 staff 账号后操作日志能看到记录
  - mp 端 5 tab 全部可切，扭蛋 / 预购 tab 跳占位页
- [ ] 商户号资料已提交（Kevin 推进，不阻塞 ticket）

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | ruoyi 自带 sys_role 角色权限模型与"owner/staff"语义对不齐 | 严格按 ruoyi 范式建：owner 给所有 perm，staff 给子集 perm（`gz:user:list`/`gz:file:upload`/`gz:bean:*` 等），角色定义不要硬编码 |
| R2 | sys_user `gz_store_id` 字段引入 | DDL 走 ALTER（V202605291000__GZ-ADMIN-001-extend-sys-user.sql），不要新建 admin_user 表 |
| R3 | mp 5 tab 占位页样式与 D02 客服浮层位置冲突 | ADMIN-005 实施时验证客服浮层在 5 tab 全部页面位置 OK，必要时按页定制浮层 z-index |
| R4 | 操作日志吞 perf | ruoyi 自带异步刷盘 + 仅写关键操作（CRUD + 状态变更），不写读操作 |
| R5 | 菜单 menu_id 段冲突 | 落 SQL 前 `SELECT MAX(menu_id) FROM sys_menu`；如 ruoyi 自带菜单已占 5000-5099 → 重 ID 到 5100-5199 |

---

## 日终 closing 命令

```bash
cd doc/daily/D03
cat reports/*.md > summary.md
git add -A && git commit -m "D03 (d2): Admin 框架 + mp 5 tab + 账号 / 角色 / 操作日志"
# 然后写 D04/README.md（D04 候选：BEAN-001/002/003/004★ — 拼豆最复杂日）
```
