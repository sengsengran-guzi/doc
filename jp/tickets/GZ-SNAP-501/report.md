# GZ-SNAP-501 实现报告

STATUS: DONE（功能 AI 验收通过；首次视觉保留 Kevin Tier 2 人验）

COMMITS: RuoYi-Vue-Plus@5f074b0be；miniapp-jp@1fbbe1de1f37ca750fb5a56a60e507b5b4b7397f。两仓 task/D12，不 push、不合 staging；无迁移。

## 实现与范围

- 导航源 `pages.config.ts`、`src/tabbar/config.ts` 配置首页/煤炉/我的。生成的 `src/pages.json` 三格已验证（本仓该生成文件被 Git 忽略，不强制入仓）。移除被触及配置中既有 `as any`。
- `src/static/tabbar/mercari.png` / `mercariHL.png`：80×80、透明底、购物袋+放大镜线性图形，不使用平台商标。代码原生 SVG 经现有 Chrome/Playwright 渲染，未引依赖；常态像素色精确取现有 home.png = RGB(26,26,26)，选中品牌绿 #33B36B。
- `src/pages/snap/index.vue`：方案 B 独立 tab；热门词、关键词/链接、Shops 拒绝、两列方图/双行标题、人民币参考价/日元价、排序、分页、stale、上游不可用态。复用 BizScreen/Panel/Button/SectionTitle/State，新 BizSnapCard；皮肤只读既有 token，无新主题，无 Vue hex/emoji。
- `src/api/gz-jp/snap-search.ts`、`src/locale/snap.zh-CN.ts`：显式 Card 类型、业务错误保留、域自包含 t()，无需额外 locale 注册文件。
- `index.logic.ts/.test.ts`：分页稳定去重（含同一新增页重复）、未知快照不编造 gate、4117/4119/网络异常映射。
- 后端 `GzJpSnapSearchVO.Card` 补可空 gateResult/gateReason；`GzJpSnapReadService.cards` 对本页通过过滤的 externalId 批量查已有快照，保持 MP 租户和逻辑删除过滤。一个批量 SELECT，无 N+1，无额外 gateway/detail 请求，无快照写入。详情仍实时准入权威。
- `src/pages/snap/detail.vue` 仅本 ticket 链接验证目标壳，只有 externalId 与加载态，不造商品数据；502 必须替换完整详情。
- `test/e2e/run.mjs` 注册 snap-search；替换全局 pkill cli -o 为只匹配本项目 dist 的 helper 检查/清理，不杀 IDE 本体，不触其它项目。

OUT_OF_TOUCHES: none（root 已预先补足 touches）。后端增量属于允许的 gz-jp 路径；没有 schema/经营口径变更。

## Accept 与 raw

### #0 三 tab / 两态 PNG：PASS

执行 prompt 原命令（读取生成 pages.json，剥 // 注释，断言 text），随后 `test -s` 两 PNG。输出：

```text
首页,煤炉,我的
```

`file` 确认 PNG 80×80 RGBA；source/dist 图标 SHA256 完全相等，见 `raw/development-artifacts.json`。

### #1 真模拟器 snap-search：PASS

```bash
node test/e2e/run.mjs snap-search
```

完整 raw `raw/501-e2e-pass.log`：

```text
✓真实后端回放卡片 2、价格、可空gate同源；热门词来自DB
✓分页与价格高→低真实回放排序
✓真实gateway失败→Redis stale结果与提示
✓真实gateway错误4119→煤炉暂时访问不了空态，输入框仍可用
✓Shops拒绝、商品链接自动直跳详情
✓临时词表、synthetic replay、专属Redis键已精确清理；经营配置/已有快照未修改，自造manual快照已清理
[PASS] snap-search
[run] 结束：1/1 flow 通过
```

数据链是模拟器→Spring 8080→容器 8700 replay；断言标题/日元金额/角标与独立后端响应一致。manual 用唯一 m501<timestamp> 的合成 item 回放调用真实 detail 准入，得到 manual/comment_required，再由搜索批量查其快照；未知卡片 gate=null。没有前端 mock 响应或假称真平台商品。

分页/排序由既有合成样本派生专属临时 replay（明确 synthetic），故障由专属 response=null 回放触发真实 gateway 错误。stale 只改本轮专属 Redis 搜索键的 at，再使专属回放失败；既有缓存/资料不改。热门词只插一条 id=-501 的专属词，finally 精确删除。

### 直接受导航影响的 home 回归：PASS（复用，不重复跑）

此前 `node test/e2e/run.mjs snap-search,home` 的 home 段绿，raw `raw/501-e2e-final.log`。该轮 snap-search 失败是故障样本 sort 与当前 price_desc 不一致，已纠正并在上述单独 flow 重验。

```text
后端 event/list → 3 条：QA-独立场B / QA-独立场A / 8月上旬快闪场
✓ 区块② 场卡片文案来自后端真数据
✓ 首页三区块齐 + banner 不塌陷 + 场卡片来自后端真数据
[PASS] home
```

遵循 Kevin 2026-10-06 减少无关重复测试授权，本卡不全量重跑未修改的 checkout/orders/D10 资金 flow。D12 最终 production build 留 root/独立 QA 统一执行，本次仅 development build。

## L0 与反 stale

```bash
JAVA_TOOL_OPTIONS=-javaagent:/Users/wkui/.m2/repository/org/mockito/mockito-core/5.17.0/mockito-core-5.17.0.jar \
mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am \
-Dtest=GzJpSnapSearchSnapshotTest,GzJpSnapSearchDegradeTest,GzJpSnapDetailContractTest \
-Dsurefire.failIfNoSpecifiedTests=false
```

raw `501-backend-tests.log` 与 3 份 Surefire XML：Snapshot 1 + Degrade 4 + Contract 5 = **10 tests，0 failure/error/skipped**，BUILD SUCCESS。新增 @Tag("dev")；测试确保已知 gate 带 reason、未知仍 null、批量一次、没有 upsert/gateway.item。

唯一后端 restart：`bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp`，clean install 完整模块、最新源码已 UP，**191 migrations validated**，raw `501-restart.log`。重启时 HEAD 为 D11+DIRTY；提交仅记版不改变内容，真实搜索 manual/null 字段已验证新运行契约。

前端定向 eslint（本卡 pages/snap、BizSnapCard、locale/API/navigation）exit 0；`pnpm type-check` exit 0，raw `501-eslint-final.log` / `501-typecheck-final.log`。

`pnpm exec vitest run src/pages/snap/index.logic.test.ts`：**5 tests passed**；`pnpm exec vitest run src/pages.routes.test.ts`：**3 tests passed**，raw 两份日志。既有 route 闸仅验直接相关导航，不全项目重跑。

`pnpm exec uni build -p mp-weixin --mode development`：DONE Build complete，raw `501-build-final.log`。devtools preflight 确认 localhost:8080 / wxMOCK / mp-applet-gz-jp；最终源/产物哈希和时间存 `development-artifacts.json`，模拟器用对应 dist/build/mp-weixin。

## 装置调整与清理

- 沙箱 Chrome 启动被拒、uni watch EMFILE：经审批用现有宿主 Chrome/工具运行；Mockito 自附加受限改加载现有 mockito-core agent，未引依赖。
- gateway 是 Docker COPY 样本进镜像，repo fixture 不挂载；本轮样本按唯一文件名 docker cp，未覆盖原样本/重建镜像。copied 文件为 root 所有，精确删除使用 docker exec -u 0；每个文件 `test ! -e` 读回。
- 自动识别链接再触发 confirm、返回详情后立刻 reLaunch 导致 automator 瞬态；flow 对链接只 input，链接验证放末尾，保持同样产品判据。
- 故障样本必须与页面当前 sort 一致：首轮故障只 created_desc、页面为 price_desc，修正为 price_desc；不把空成功返回降低成故障通过。
- MP commit-msg subject-case 拒绝以 GZ 开头，改为 `implement GZ-SNAP-501 ...` 后正常提交；未绕过 hook。
- 所有失败和成功轮次的自造文件/词表/快照/专属缓存已清理。收工额外 SQL 确认 id=-501 词数=0、m501179127* 自造快照数=0；容器/repo find 本轮 zz-501/m501 文件为空。只读既有商品锁/经营配置，无 pricing/FX 修改，无 wx-login nickName/avatar。
- miniapp-jp git clean；后端仅剩任务开始前已有 untracked ruoyi-admin/logs/sys-error.2026-10-01.log180801896327291.tmp，不纳入 commit。主 miniapp 完全只读，未 build/test 输出。真实煤炉请求 **0**。

## 下游与人验

- 502 用 `/pages/snap/detail?externalId=...` 接搜索链接/卡片，不依赖 Card gate 放行购买；详情必须实时判定。本卡壳不算完整详情。
- 当前经营配置 pricing 三项 null，因此真实界面明确显示「参考价暂不可用」，不造人民币数；数值参考价在配置可用时来自后端 referencePriceCent。截图不代表经营报价。
- Tier 2 待 Kevin 首版视觉拍板：`raw/snap-search-empty.png`、`snap-search-results.png`（含真实回放 manual/stale）、`snap-search-down.png`。AI 功能绿不代替该人验。
- root 若同步权威契约：搜索 Card 两新增可空字段来源就是既有 `gz_jp_snap_item.gate_result/gate_reason`；未知不推断，详情实时权威。无新增经营/资金口径。
