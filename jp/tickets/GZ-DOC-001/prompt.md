---
ticket: GZ-DOC-001
track: SYS
phase: D0
size: S
req_refs: [REQ-SYS-004]
depends_on: []
touches:
  - doc/_adr/**
blueprint_refs:
  - FLOW:F-JP-00
  - FLOW:F-JP-00.step3
  - FIELD:gz_user.app_id
accept:
  - name: ADR 文件存在且写明「加 app_id 列 vs unionid 合并」的取舍与否决理由
    form: API
    run: |
      F=doc/_adr/0019-multi-miniapp-appid-support.md; \
      test -f "$F" && grep -q 'app_id' "$F" && grep -q 'unionid' "$F" && \
      grep -qE '(否决|不采用|列为后续|Rejected)' "$F" && \
      grep -qE '(Accepted|已接受)' "$F"
  - name: 四个改造点在 ADR 里都有落点（防只写结论不写影响面）
    form: API
    run: |
      F=doc/_adr/0019-multi-miniapp-appid-support.md; \
      grep -q 'WechatPayV3ClientImpl' "$F" && grep -q 'access_token' "$F" && \
      grep -q 'ConditionalOn' "$F" && grep -q 'clientid' "$F"
---

# GZ-DOC-001 ADR-0019 多小程序（多 appid）支持

## §0 状态自检

1. `ls doc/_adr/ | tail -3` —— 确认最新编号是 0018，0019 未被占用。
2. 复习 CLAUDE.md §12：**ADR 是唯一允许写「为什么这么选」的文档**，事实写 doc/10/11/12，
   决策原因写 ADR + git commit message。

## What

把「后端支持第二个小程序」这个架构级决策落成 ADR。现在这个决策散落在 ticket 正文和
`flows.yaml` 的 body 里，**没有单一出处**——半年后没人知道为什么不走 unionid。

必写的几段：

**背景**：现有后端把微信 appid 建模成单值标量（`WxMiniappProperties.appid`、`WechatPayProperties.appid`），
real/mock 用 8 处 `@ConditionalOnExpression` 全局互斥。新小程序有独立 appid，不改造则登录与支付都不通。

**决策**：
1. 配置由标量改 `Map<clientid, app>`，real/mock 从启动期条件 Bean 改运行时按 app 分派
2. `access_token` Redis key 加 appid 维度
3. 支付的统一下单与**调起签名**（`WechatPayV3ClientImpl:93/125`）appid 一律从下单上下文取，
   落点激活 `gz_pay_channel.appid` 列做真源
4. `gz_user` 加 `app_id` 列，唯一键 `(tenant_id, openid)` → `(tenant_id, app_id, openid)`

**被否决的方案：unionid 合并**。需甲方把两个小程序绑到同一微信开放平台账号，
当前 prod 该字段极可能为 NULL，依赖它会引入不确定性。**列为后续增强，不是永久否决。**

**影响面**：改的是线上正在跑的登录与收款核心，每个改造点都必须全量回归现有小程序。

## AC

- 落 `doc/_adr/0019-multi-miniapp-appid-support.md`，状态 Accepted
- 四个改造点各有一段，写清「改什么 + 为什么必须改 + 不改的表现」
- unionid 方案的否决理由与复活条件写明
