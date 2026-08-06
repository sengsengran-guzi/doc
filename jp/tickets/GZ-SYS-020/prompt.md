---
ticket: GZ-SYS-020
track: SYS
phase: D1
size: L
req_refs: [REQ-SYS-004]
depends_on: []
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/wechat/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application*.yml
blueprint_refs:
  - FLOW:F-JP-00.step1
  - FLOW:F-JP-00.step2
accept:
  - name: 两个 clientid 各自解析到自己的 appid
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-common -am \
        -Dtest=WxMiniappPropertiesTest,WxLoginAdapterDispatchTest 2>&1 | tail -5
  - name: 旧单值配置不改仍能启动（向后兼容）
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-common -am \
        -Dtest=WxMiniappLegacyConfigTest 2>&1 | tail -5
---

# GZ-SYS-020 微信小程序配置多 appid 化 + real/mock 运行时分派

## §0 状态自检（实现前必做，不通过 STOP 报 Kevin）

1. `grep -rn "ConditionalOnExpression\|ConditionalOnProperty" ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/wechat/` —— 确认 real/mock 互斥点**恰好 8 处**（login/phone/accessToken/shipping 各 real+mock）。数量对不上说明代码已变，先报。
2. `grep -rn "properties.getAppid()" ruoyi-modules/ruoyi-gz-common/` —— 列全部读点，改造要覆盖。
3. 现有 miniapp 能正常登录（改造前基线）。

## What

把 `wx.miniapp` 从**单值标量**改成**按 clientid 索引的 Map**，并把 real/mock 的选择从**启动期条件 Bean**改成**运行时按 app 分派**。

- `WxMiniappProperties`：`appid`/`secret` 标量 → `Map<String, MiniappApp> apps`（key = clientid）。
  **保留原单值字段做向后兼容**：配了单值且 apps 为空时，自动包装成 `{默认clientid: 单值}`。
- 8 处 `@ConditionalOnExpression` / `@ConditionalOnProperty` 撤掉 → real 与 mock 两个实现**都注册**，
  由一个 `WxAdapterDispatcher` 按当前请求的 clientid 查出该 app 的 mode 再选实现。
- `WxLoginServiceImpl.DEFAULT_MP_CLIENT_ID` 常量 → 配置项 `wx.miniapp.default-client-id`。

## AC

- 配置两个 app（旧 = real、新 = mock）时两者互不干扰，各自走对的通道
- 只配旧的单值形态时，服务照常启动、行为与改造前一致
- 单测覆盖：clientid 未知 → 明确抛错不静默落到默认 app

## 不做

不动 `RedisSessionKeyStore`（key 按 openid，天然跨 appid 唯一，无需改）。
