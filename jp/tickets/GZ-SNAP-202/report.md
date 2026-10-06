# GZ-SNAP-202 预算与样本冲突报告

STATUS: SPEC_CONFLICT

日期：2026-10-06。分支 `mercari-gateway/task/D8`，接手 HEAD `f8b984693fee55e845b4f214600d08f1e28ffa52`，代码工作区干净。本轮没有实现、没有代码提交、没有迁移；仅写本报告，doc 不提交。主 miniapp 未改，8080 与 Docker 未重启。

## 冲突与已核实证据

已读 impl-brief、ticket 全文、ADR-0025、FLOW:F-JP-12.step2/3/3b/4、OWN:mercari_item_live、纸面推演相关链路、phase-plan 二期执行口径、READ-PROBE-2026-10-03、pitfalls、201 报告及现有读源。

ticket What 6 要求同商品/同关键词 JSON 与 HTML 各一份；What 6b 要求 2~3 个关键词搜索、8 类各至少一件详情及卖家简介，录制一次性真实请求 ≤15。主线程进一步明确底层网络请求、重定向与 fallback 都计入预算，不能按业务调用计数。

本地 `fixtures/replay/{search,items,sellers,img}` 仅有 `.gitkeep`；`tests/fixtures` 不存在。`doc/jp/_spike/mercari-probe` 只有脚本、报告与两张截图，无 `probe-out` 原始响应。READ-PROBE 明写原始 JSON 含昵称、未入库。全项目只读扫描（排除 node_modules、.venv、.git、target、dist）未发现 probe-out、mercari JSON 或 replay JSON。截图不能代替完整 JSON/HTML/简介。

按 8 类各一件分别录制的常规计划：8 个详情 JSON + 8 个详情 HTML + 8 个卖家 profile + 2 个关键词的 JSON/HTML（4）= 28 次，尚未计浏览器渲染子请求和跳转。这是常规独立样本计划的账本，并非声称数学上禁止一件商品覆盖多类或多个商品共用卖家。**当前没有可证实类别重叠、简介覆盖与商品 ID 的本地原始样本，无法事先构造保证完整覆盖的 ≤15 有限计划。**不得先打真搜索赌重叠，也不得把缺类合成数据冒充录制。

READ-PROBE 还证实 Shops 通过普通 items/get 返回 400，因此该请求本身不能满足 Shops 详情录制；不能把它算成已完成详情。

## 有限请求计划与实际账本

录制候选计划 28 次已在执行前发主线程，因超过硬上限被否决，未执行。

| 用途 | 上限 | 实际真实请求 | 运行次数 |
|---|---:|---:|---:|
| live 契约 | 单次 ≤5，最多2次 | 0 | 0 次有效测试；原样 pytest 因文件不存在而未收集 |
| 一次性录制 | ≤15，最多1次 | 0 | 0 |
| QA/返工/E2E | 0 | 0 | 0 |

无代理凭据/secret 被读取输出、提交或写入报告，无登录、购买、验证绕过。未写外部循环/批量请求。

## 原样 accept（bash -c，项目根）

#0：`cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_parse_parity.py tests/test_replay_coverage.py`，exit 4：

```text
no tests ran in 0.00s
ERROR: file or directory not found: tests/test_parse_parity.py
```

#1：`cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_img_proxy.py tests/test_resolve.py`，exit 4：

```text
ERROR: file or directory not found: tests/test_img_proxy.py

no tests ran in 0.00s
```

#2：`cd code/main/mercari-gateway && .venv/bin/pytest -q -m live tests/test_live_read.py`，exit 4，0 次真实请求：

```text
ERROR: file or directory not found: tests/test_live_read.py

no tests ran in 0.00s
```

现有上游基线 `cd code/main/mercari-gateway && .venv/bin/pytest -q`，exit 0；74 条属于 201 基线，不是 202 验收：

```text
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 3.19s
```

## 下游与状态

无样本用途清单可交付：当前没有任何真实录制样本，8 类均未完成。默认运行容器仍 replay+fake，live 源仍为201的501占位。没有越界代码文件；本报告是票据要求的文档交付。主线程应将首次冲突登记为 spec_conflict 并取得明确口径后再续作；不得把74条基线测试当本票绿，302/303/501/502 的完整回放依赖未满足。
