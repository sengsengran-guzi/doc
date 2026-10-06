# GZ-SNAP-401 实现报告

状态：实现与三条 accept 已通过；独立 QA 由主线程安排。

## 实现与提交

- 后端 `task/D11@6b3d7d51a`：新增 automatic-list / summary / purchase/{id}/detail 只读接口，租户隔离由既有 MyBatis 租户插件执行；summary 读取现存自动开关及账号健康，不调用 gateway、不虚构健康数据。detail 从真实 shipping_diff 退款单读取金额与状态。
- 后台 `task/D11@866349f`：三 tab（待人工 / 交易跟踪 / 自动任务），行内权限指令、填成功价格上限、填失败 / 取消交易 / 退货完成二次确认、到付实际运费必填、退款结果、证据图片 GzImageThumb、完整两语言、菜单角标。
- 菜单迁移 `V202610061555__GZ-SNAP-401-purchase-menu.sql`：14040 目录 / 14050 页面 / 14051-54 四权限；visible/status 均 0，owner tenant1001 授权；真实迁移 187→188。
- 交易列表排序修正：临期 arrived 优先、非空期限升序、NULL 最后、id 升序。真实 E2E 混合 1h / 24h / NULL 三行验证。
- 未改资金写出口，调用306/307已有人工结果与交易 API；复用 D10资金/并发证据，不全量重复。

## 文件（按仓）

后端：
- `ruoyi-admin/src/main/resources/db/migration/V202610061555__GZ-SNAP-401-purchase-menu.sql`
- `ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/controller/GzJpSnapPurchaseController.java`
- `ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/mapper/GzJpSnapPurchaseMapper.java`
- `ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/service/internal/GzJpSnapPurchaseReadService.java`
- `ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/service/internal/GzJpSnapTradeService.java`
- `ruoyi-modules/ruoyi-gz-jp/src/test/java/org/dromara/gz/jp/service/internal/GzJpSnapPurchaseReadTest.java`

后台：
- `src/api/gz-jp/snap-purchase.ts`
- `src/views/gz-jp/snap/purchase/index.vue`
- `src/views/gz-jp/snap/purchase/MenuBadge.vue`
- `src/lang/{zh_CN,en_US}.ts`
- `src/layout/components/Sidebar/SidebarItem.vue`
- `e2e/gz-jp/snap-purchase{,-fixtures}.ts`（spec实际名 snap-purchase.spec.ts）

越界：`src/layout/components/Sidebar/SidebarItem.vue` 添加隔离 MenuBadge 组件及条件渲染两行，为本卡明确要求的真实菜单角标；未改框架路由/菜单逻辑。

## 验证与 raw

1. MENU #0：迁移前活库14040..14099为空、全部迁移扫描最大14039；迁移后 invalid path/component/parent=0，14050正确parent=1，按钮权限=4。raw `evidence/menu.log`。
2. MENU #1：真实 owner 登录 getRouters 包含 `gz-jp/snap/purchase/index`，Playwright进入真实动态菜单页成功。raw `evidence/e2e-final.log`。
3. API/UI #2：`pnpm exec playwright test e2e/gz-jp/snap-purchase.spec.ts --reporter=line`，raw **3 passed (23.2s)**，worker1/channel chrome/data-test/8090；API quote→submit→simulate-callback产生夹具，不直接INSERT业务表。
   - manual 成功 / 价格高于锁价禁提交 / 失败二次确认 / 真退款行。
   - 交易取消二次确认真落库 / 发货 / 到付未填运费禁提交 / 到仓退款结果 / 临期红色置顶 / 1h→24h→NULL / 退货完成二次确认取消时零写 / 已评价真落库。
   - 自动任务真实queued行只读 / 无写操作 / 证据空态 / owner权限正路 / staff read/manual/trade 403 / anonymous401。
4. 新只读投影单测：`mvn -o test -DskipTests=false -Dtest=GzJpSnapPurchaseReadTest -Dsurefire.failIfNoSpecifiedTests=false -pl ruoyi-modules/ruoyi-gz-jp -am`，既有Mockito javaagent；raw **Tests run: 5, Failures: 0, Errors: 0, Skipped: 0**，BUILD SUCCESS。raw `evidence/targeted-unit.log`。
5. 定向 eslint：0；最终 vue-tsc **72→72**，新文件0。raw `evidence/targeted-eslint.log`、`evidence/vue-tsc-final.log`。D11全部页面完成后主线程统一prod build，不重复构建。
6. 唯一restart脚本两次clean install成功，新迁移apply1，第二次排序修正后validated188；raw `evidence/restart*.log`。

## 环境调整与清理

- 首次sandbox编译被 `.msp/incrementMark` 写限制拒绝，改用唯一restart脚本 host clean install；首次sandbox Vite绑定EPERM，Playwright受控host启动webServer成功。没有新增依赖。
- E2E初轮失败是fixture误断暂停原因：setup将开关开启后暂停原因清空，修正为真实账号数量。第二轮 manual已绿，trade失败仅中文ElementPlus aria Close按钮不能按英文名匹配，改 `.el-dialog__headerbtn`。两次装置失败均执行exact cleanup，产品退款/到仓已成功。最终三用例全绿。
- 最终5个自造订单及关联item/task/payment/refund、地址、FX精确删除；pricing/auto/trade三个共享配置byte-for-byte复原；采购账号未写。raw `evidence/e2e-final.log`。
- 初轮fixture曾通过wx-login把既有 `gz_user id14/mock-jp-tester` 昵称改为 `SNAP401 fixture`；最终fixture已去掉nickName输入。已向主线程报告；主线程确认MySQL FULL binlog有准确before-image，负责精确恢复；不猜值覆盖。正常登录审计时间按主线程口径保留。
- gateway使用本地fake +既有replay，真实煤炉请求0；主miniapp整个目录未写；不push、不合staging、不切gateway/miniapp-jp分支。
- 后端只剩非本卡已有未跟踪日志 tmp；后台干净。Playwright托管8090已自动停止，共享后端保留主线程使用。

## 下游提示

402请用14060 / path account（框架route name Account14060），顶部存在该动态route时跳转；未开放时当前提示即将开放。403/404无需改变本页接口。本卡 summary 只反映现存账号行和开关，未加健康探测或自动开关写入。
