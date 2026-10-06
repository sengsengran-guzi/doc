# GZ-JP 二期代切 D8–D12 执行结果

> 本轮结束：D0–D12 全部 qa_passed，47/51 ticket 完成。D13–D15 共四张保持 pending，未派 D13。只做本地 feat/jp-snap 合流，没有 push 或合 staging。

## 1. task_state report 进度

命令：`python3.11 ~/claude-config/skills/zhixing/scripts/task_state.py --state doc/jp/waves/state.json report`。
完整原始输出：[task-state-report.txt](regression/D12/task-state-report.txt)。

```text
任务档进度：ticket 47/51 完成

任务      状态            ticket 进度     QA 轮次
D0      ✅qa_passed    3/3           3
D1      ✅qa_passed    4/4           1
D2      ✅qa_passed    2/2           1
D3      ✅qa_passed    5/5           1
D4      ✅qa_passed    4/4           1
D5      ✅qa_passed    5/5           1
D6      ✅qa_passed    1/1           0
D7      ✅qa_passed    5/5           1
D8      ✅qa_passed    2/2           0
D9      ✅qa_passed    4/4           1
D10     ✅qa_passed    3/3           0
D11     ✅qa_passed    5/5           0
D12     ✅qa_passed    4/4           0
D13     ⬜pending      0/1           0
D14     ⬜pending      0/2           0
D15     ⬜pending      0/1           0
```

## 2. 每阶段 QA

| 阶段 | 结论 | 报告 |
|---|---|---|
| D7 | r1 FAIL，返工后 r2 PASS | [qa/D7-r1.md](qa/D7-r1.md)、[qa/D7-rework-r1.md](qa/D7-rework-r1.md)、[qa/D7-r2.md](qa/D7-r2.md) |
| D8 | r1 PASS | [qa/D8-r1.md](qa/D8-r1.md) |
| D9 | r1 FAIL（测试夹具），r2 PASS | [qa/D9-r1.md](qa/D9-r1.md)、[qa/D9-r2.md](qa/D9-r2.md) |
| D10 | r1 PASS | [qa/D10-r1.md](qa/D10-r1.md) |
| D11 | r1 PASS | [qa/D11-r1.md](qa/D11-r1.md) |
| D12 | r1 PASS | [qa/D12-r1.md](qa/D12-r1.md) |

D10 独立 QA 实跑 101 条单测、62 次真 HTTP/DB 断言；差价 83 分加剩余退款 917 分等于 1000 分，独立连接到仓/取消竞争只产生一笔退款。各阶段原始证据在 `regression/D<N>/` 与相应 ticket 的 `evidence/`、`raw/`。

D12 独立QA：后端22+小程序97=119条单测，26+8=34项独立HTTP/DB断言，7个真实模拟器flow全部通过。并发详情只建1快照、同报价两连接提交只建1单/1支付；6370分报价与真实264分已退运费差价对账。最终默认双场景success13.505秒、failed16.933秒，fake分别calls1/clicks1与calls1/clicks0；原始输出已持久。

## 3. Tier 2 人验

- GZ-SNAP-501：煤炉搜索页首版视觉、三格 tabbar 及图标。[结果截图](tickets/GZ-SNAP-501/raw/snap-search-results.png)、[不可用态](tickets/GZ-SNAP-501/raw/snap-search-down.png)。
- GZ-SNAP-502：详情页首版视觉、价格说明和准入提示。[详情截图](tickets/GZ-SNAP-502/raw/snap-detail-auto.png)、[到付价格说明](tickets/GZ-SNAP-502/raw/snap-detail-manual-price.png)。
- GZ-SNAP-503：真机微信原生支付，随后续 D15 演练；本轮仅 mock 支付。
- 协议代切条款待甲方过目。D13 所需东京服务器、ISP 代理、真实采购账号未到位；本轮不派 D13，也不声称已上线。

## 4. 全程冲突、回流与阻塞处理

1. **D7 业务入口冲突已按 Kevin 方案 A 解决**：snap 与 batch 按来源判定入口，batch 保持一期语义。改 FLOW:F-JP-09.step1、102 ticket 与阶段计划；authority impact 为 102/204/307。102 已返工，后续实现沿用新口径。支付回调/超时的 RR 快照读，以及退款受理失败/回调从表盲写竞态已修。
2. **D8 样本要求与真实请求预算冲突**：原完整多类别录制超出一次性 15 次预算，按最新自主调整授权改为少量真实 JSON 加明确标记的合成夹具。202 实际仅发送 2 次真实请求（搜索、详情）；其后 QA、返工、E2E 全部零真实煤炉请求。真实 HTML、简介、图片、短链适配没有得到真实平台验证。回流 FLOW:F-JP-12/202/阶段计划，影响 001/201/202/203/204/301/303/304/305/307；201 既有实现不受影响。
3. **D9 快照及准入澄清**：补主图原 URL 兜底字段；付款准入取报价与下单前新读结果的保守交集，任何 blocked 拒绝。影响 102/304；一期兼容已核对。搜索卡参考价不虚构未知运费承担，详情报价为权威。回放分类变体与 JPEG 占位图为合成数据，报告标注来源。D9 r1 的 gate 单测夹具误把过滤配置提供给所有键，产品 fail-closed 正确；修夹具后 r2 通过。
4. **D10 相关实现缺口**：shipping_diff 独立退款分支与剩余预算守卫已实现；到仓与取消使用同一锁顺序，混拼团/未评价代切的人工推进整批拒绝。REQ-SNAP-031 note 澄清实际到付运费在到仓时录入，人工采购成功不录运费；req_refs 306/401/504 已核对，authority diff 无变化。不改变经营价格、分成或计费口径。
5. **环境反复卡住的根因已处理**：后端用专用 launchd 保活，私有选项文件权限 600；修重启锁、相对脚本路径、异步 remove/submit 等待与 dev gateway URL 覆盖。故障代理避开 Python 反向 DNS 阻塞。审批 timeout 不算命令执行，避免重复启动。Docker 路径、Mockito 既有 javaagent、Maven 完整模块路径及中文组件关闭选择器已写现场约定。故障注入用临时 SQLite/隔离 fake 服务，已恢复共享数据及配置、停止测试代理。
6. **D11 新发现**：401 修评价期限 NULL 排前的问题；Sidebar 角标所需精确文件已补 touches。fixture 初轮登录覆盖测试用户昵称，已由 FULL binlog 精确 before-image 恢复，只写 nickname，一行并读回；后续 fixture 不传资料。402 真栈发现 afterCommit 内 cache.evict 再延后导致不驱逐，修两处为即时 evictIfPresent；19 条定向单测及暖缓存 false→true→false 通过。两项已记知识库，不涉及蓝图业务语义变更。独立QA组合发现共享fixture数组污染，修测试资产复位/快照后六spec同worker14/14通过；五类配置由FULL binlog恢复QA开始前原值与审计、清缓存读回，并由QA独立确认。

7. **D12 只读详情契约**：补真实fetchedAt epoch毫秒（Asia/Shanghai）、旧构造/null兼容。impact仅302/502：302既有写入不变免重做，502落实。模拟器confirm后reLaunch超时改navigateTo串行五态、确认导航放末尾，保留所有产品断言；pricing字节/审计及缓存精确恢复。

8. **D12 确认页原报价公共投影**：补认证只读预览，不重新签发quote或延长TTL，不暴露内部汇率/加价；回流FLOW:F-JP-06.step2及UI:mp.order_confirm.snap，impact仅304/503，304提交契约无变化免重做。测试快照统一HEX(CAST(column AS CHAR))并mode600持久化，避免HEX数字语义导致恢复失败；配置、资料、地址、购物车、异步图片均按确切所有权恢复/清理，已记知识库。

9. **D12 订单状态公共投影**：UI:mp.order_detail.snap补六个展示态、交易白名单及仅成功shipping_diff累计；退款待受理/失败时显示处理中，不提前声称已退款。impact仅504，本次落实，无历史任务失效。测试启用采购调度前确认无其它采购任务/账号，并延后其它调度，避免旁路BOC/旧单处理。

10. **D12独立QA装置补齐**：自动审批拒绝外层只对比未恢复的六flow包装命令，尚未执行；补finally按PK/tenant恢复完整baseline后获准。搜索粘贴链接现在触发完整详情，新增未锁快照漏清，测试资产e1bee8f补全行恢复/本轮新增quote与cache清理并单跑通过，七表前后完全相同。独立probe跳过卖家发货被正确409，补合法发货API后34项重验通过。504初次success raw未持久，报告如实标注；最终独立QA默认两场景均保留原始输出。生产构建成功，但production dist SHA捕获遇cwd错误后被dev覆盖；不为元数据重构建，实际被测dev指纹完整，细节见QA报告。没有剩余环境阻塞或待执行审批。

## 验证边界与收尾

- 不 push、不合 staging；主 `code/main/miniapp` 全目录只读。
- 当前经营pricing三个参数仍NULL；测试只临时填值并精确恢复，不代甲方定价，未配置时购买报价不可用。
- 真实煤炉点击及购买记录延迟、真钱支付/部分退款、真实 Tokyo 午夜与长期调度不是本轮替身验证的覆盖范围。
- D7 留档：orders flow 曾首跳装置抖动，复现需排查；后台退款重试回调抢先时的展示误报仍需在相关改动中核对；主 miniapp 真支付 E2E 缺口不在本轮只读范围内补做。
- 已移除自己的8080 launchd、停止gateway replay/fake容器，8080/8090/8700/8711/8712均无listener；私有backend-options.json已删，基础设施和用户开发者工具保留。见[实际运行清理](regression/D12/final-runtime-cleanup.json)。
- 测试配置字节/audit、用户资料/地址/购物车完整恢复，自造订单/支付/退款/账号/FX/快照/回放/图片及MinIO对象精确清理；七表baseline一致，见QA原始证据。
- 合流后tree与被验task/D12完全相同。后端20、MP32文件touches均闭合。

| 仓 | 最终分支 | HEAD | 工作区 |
|---|---|---|---|
| RuoYi-Vue-Plus | feat/jp-snap | `0b57012c1` | 原有sys-error日志tmp保留，非本轮改动 |
| plus-ui | feat/jp-snap | `723e42136` | 干净 |
| miniapp-jp | feat/jp-snap | `b71415c7f` | 干净 |
| mercari-gateway | feat/jp-snap | `ec0ca2762` | 干净 |
| miniapp | staging | `898ff4370` | 干净 |

所有完整SHA及工作区证据见[final-code-repositories.json](regression/D12/final-code-repositories.json)。主miniapp仍为原staging@898ff43，全目录只读。
