---
ticket: GZ-SYS-021
track: SYS
phase: D1
size: S
req_refs: [REQ-SYS-004]
depends_on: [GZ-SYS-020]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/wechat/impl/WxRealAccessTokenManager.java
blueprint_refs:
  - FLOW:F-JP-00.step2
accept:
  - name: access_token 缓存 key 含 appid，两 app 互不覆盖
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-common -am \
        -Dtest=WxAccessTokenIsolationTest 2>&1 | tail -5
  - name: 旧 key 不再被写入（防两 app 串号回归）
    form: API
    run: |
      grep -q 'ACCESS_TOKEN_CACHE_KEY_PREFIX' \
        code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/wechat/impl/WxRealAccessTokenManager.java \
        && ! grep -qE '"wx:miniapp:access_token"' \
        code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/wechat/impl/WxRealAccessTokenManager.java
---

# GZ-SYS-021 access_token 按 appid 隔离

## §0 状态自检

1. `grep -n "wx:miniapp:access_token" -r ruoyi-modules/` —— 确认当前 key 无 appid 维度。
2. 确认 GZ-SYS-020 已 merge（dispatcher 可用）。

## What

`WxRealAccessTokenManager.ACCESS_TOKEN_CACHE_KEY` 从固定串改为 `wx:miniapp:access_token:{appid}`。

**为什么必须改**：两个小程序共用一个 Redis key 会互相覆盖 token —— 表现是手机号解密、
微信发货信息上报**随机串到另一个小程序**，且报错信息完全看不出根因。

## AC

- 两个 appid 各自缓存、各自过期，互不影响
- 刷新逻辑（提前量、并发保护）保持原语义
