---
ticket: GZ-SNAP-001
track: SNAP-GW
phase: D13
size: M
req_refs: [REQ-SNAP-064, REQ-SNAP-006, REQ-SNAP-010, REQ-SNAP-065]
depends_on: [GZ-SNAP-202]
touches:
  - doc/jp/_spike/s0/**
  - doc/_adr/0025-jp-snap-mercari-gateway.md
blueprint_refs:
  - FLOW:F-JP-07.step2
  - FLOW:F-JP-12.step5
  - FLOW:F-JP-12.step6
  - FLOW:F-JP-12.step7
  - OWN:mercari_purchase_fact
  - OWN:mercari_account_session
accept:
  - name: ADR-0025 §3 回填了 go / no-go 结论
    form: API
    run: grep -qE '^- \*\*S0 结论：(go|no-go)\*\*' doc/_adr/0025-jp-snap-mercari-gateway.md
    counterfeit: 只写了报告没回填 ADR，或结论写成「基本可行」这类不可判定措辞 → 红
  - name: 验证报告 6 项实测都有数（不是「待测」）
    form: API
    run: |
      F=doc/jp/_spike/s0/REPORT.md; test -f "$F" && \
      for k in 读接口限速 下单全流程 下单耗时 验证出现频率 登录态保持时长 购买记录可查; do \
        grep -qE "^\| *$k *\|[^|]*[0-9]" "$F" || { echo "missing: $k"; exit 1; }; done
    counterfeit: 某项写「未测 / 待补」或没有数字 → 红
---

# GZ-SNAP-001 技术验证（go / no-go）：自动下单能否在甲方账号上跑通

## 前置（外部阻塞，★ 账号到位即可插队，不必等前面的任务）

- 甲方采购的阿里云东京服务器 + 固定日本 ISP 代理（REQ-SNAP-065）
- 甲方煤炉账号 + 付款方式 + 余额，转运仓地址设为默认收货地址（REQ-SNAP-010 / 060）
- **不许**用 Kevin 本机代理出口做下单或批量请求。

## §0 状态自检

1. 三项前置齐了才开工；任一缺 → STOP 报 Kevin，不要拿别的环境凑。
2. 读 ADR-0025 §3 / §4（风险边界：不打码、不伪装指纹、不批量注册；遇验证即停）。
3. GZ-SNAP-202 的只读能力可在东京服务器上跑。

## What

在东京服务器上，用 Playwright（持久化登录目录，日本员工经 GZ-SNAP-201 的远程登录工具手工登录一次，含短信验证）+ ISP 代理出口，实测 6 项，写 `doc/jp/_spike/s0/REPORT.md`（每项一行表格：项 | 方法 | 结果数字 | 结论）：

**执行顺序（前两段不花钱，任何一段出问题即停下报 Kevin）**：
- 段 1 登录保持：员工远程登录一次 → 程序在 1 小时 / 6 小时 / 24 小时后各打开一次「マイページ」，记录是否仍登录、是否被要求再验证；
- 段 2 走到确认页：程序打开个人卖家商品页 → 「購入手続きへ」→ 看到购买确认页（付款方式、收货地址）**即停，不点「購入する」**，重复 3 件商品；
- 段 3 真买一件：¥300 级个人卖家商品，程序点击「購入する」，Kevin 在场；随后按商品 ID 查购买记录。

1. **读接口限速**：匿名搜索 / 详情在什么频率开始被拦（阶梯加压，上限每分钟 60 次，见拦即停）。
2. **下单全流程**：网页版买一件 ¥300 级**个人卖家**商品（这一期不卖煤炉 Shops，REQ-SNAP-047），从商品页到交易页每步截图（存 `_spike/s0/evidence/`，脱敏）。
3. **下单耗时**：点「購入する」到交易页出现的秒数（至少 3 次）。
4. **验证出现频率**：整个验证期间出现验证码 / 短信验证的次数与时机。
5. **登录态保持时长**：持久化目录下多久需要重新登录。
6. **购买记录可查**：按商品 ID 能否在购买记录里查到、下单后多久可见（对账的前提，决定 REQ-SNAP-029 口径是否成立）。
   顺带记录：煤炉自动完成交易的时限（回填 REQ-SNAP-034 的评价期限默认值）。

另录页面样本给 GZ-SNAP-203 / 204 做判定测试（存 `_spike/s0/pages/`，脱敏）：商品页、购买确认页、交易页、购买记录页；
能安全复现的话再录「余额不足 / 付款方式不可用」时的购买确认页（纸面推演 P6），不能复现就在报告里标明。
同时用 App 分享一次商品，记录分享链接的格式（纸面推演 P7）。

然后在 ADR-0025 §3 末尾回填一行：`- **S0 结论：go**` 或 `- **S0 结论：no-go**`，下一行写依据与对后续任务的影响：
- go → GZ-SNAP-203 / 204 按原样做；
- no-go → 日本服务部署 `GATEWAY_DRIVER=disabled`，GZ-SNAP-203 关闭不做（ticket 写明原因）、GZ-SNAP-204 只做「无」，
  巡检改由日本员工在 admin 手工标记（FLOW:F-JP-09.step1b，已实现），自动下单总开关永久关闭。

## AC

- 两条 accept 绿。
- 报告里不含账号密码、Cookie、完整地址等凭据与个人信息。
- 验证中一旦触发验证码：立即停，记录，**不尝试绕过**。
