# GZ-SNAP-404 实现报告

STATUS: DONE
COMMITS: backend@08741d274；plus-ui@5031fd4
MIGRATION: V202610061635__GZ-SNAP-404-term-menu.sql
OUT_OF_TOUCHES: none

后台词表已接入分页、类型/启用/关键词筛选、新增、编辑、删除、启停和「试一试」。重复中文词返回友好提示。既有唯一键 `(tenant_id,zh_term)` 保持；软删词重新新增恢复原行，避免墓碑冲突。归一化直接用当前租户启用词表，mp 消费者每次直接查 DB，没有新增缓存。

文件：后端改 GzJpSnapTermController/Term/TermMapper，新增 TermBo/TermService 和菜单迁移；后台新增 api/gz-jp/snap-term.ts、views/gz-jp/snap/term/index.vue、e2e/gz-jp/snap-term.spec.ts，两语言各25个对应键。

## 实际验证

`bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp`：

```text
BACKEND UP (commit 940ae781b+DIRTY-WORKTREE, branch task/D11)
Successfully validated 191 migrations
Migrating schema ry-vue to version 202610061635 - GZ-SNAP-404-term-menu
Successfully applied 1 migration
```

分配前查14070–79活库与全部迁移为空；菜单验收：

```text
14070 C / parent14040 / component有效：1
14071–14079词表按钮数：4
```

`mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapNormalizeTest -Dsurefire.failIfNoSpecifiedTests=false`：

```text
Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

限定 eslint exit0，vue-tsc既有72条错误、本次0新增；命名空间中英25=25。

`pnpm exec playwright test e2e/gz-jp/snap-term.spec.ts --reporter=line`：

```text
404 cleanup: own term removed through API then exact own tombstone cleanup;
original dictionary/audit snapshot unchanged; wx-login/live Mercari=0
1 passed (12.4s)
```

owner 真实增改删、试一试、启停、筛选 API、唯一友好提示、非法类型拒绝、同词删除后重建，以及匿名/staff全部六种端点拒绝通过。mp search 响应 data.query 随新增、修改、启停、删除立即变化。未造首批经营词。

## 装置与清理

首轮启停命中 Element Plus 隐藏 role=switch input 超时，改点可见 `.el-switch`，保留实际HTTP/业务断言后通过。原子agent持有的8090服务已结束，由 Playwright 自起并退出时停止，最终无监听；root随后自起共享8090供405/QA复用。

测试词经API创建和删除，最后按精确 id/tenant/zh_term/del_flag 清理自造墓碑。原词表及审计快照逐行相同。微信登录0、真实煤炉0、主miniapp无写。raw位于 `raw/{restart,e2e,vue-tsc,normalize-test}.log`。

两个仓已只提交本人路径，后台干净，后端仅旧无关日志tmp；未push、未合staging。normalize新权限为 `gz:jp:snap:term:query`，弹窗提示新增词保存后才能在「试一试」命中。独立QA另行执行。
