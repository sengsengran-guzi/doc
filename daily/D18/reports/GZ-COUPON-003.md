## §AI 测试段（kevin-qa 自动追加，20:30）

### 后端集成 curl

```
=== GZ-COUPON-003: 优惠券规则自动发放 ===

# 前置：建 filtered+auto_issue=1 模板 id=2
issue_config_json: {"conditions":[{"type":"phone_bound"}]}
DB: issue_strategy=filtered, auto_issue=1, total_quota=100

# auto-issue-once 首次试跑
POST /system/gz/coupon/template/2/auto-issue-once
→ code=200 msg=发放成功 data=1（发放 1 张）
DB确认: gz_user_coupon id=2 user_id=1 template_id=2 status=unused ✅

# 重复跑去重验证
POST /system/gz/coupon/template/2/auto-issue-once（再次）
→ code=200 msg=发放成功 data=0（0 新发，已持券用户不重发）
DB确认: gz_user_coupon count=1（无重复） ✅

# issue_config_json 格式错误验证
测试：invalid JSON 格式 → code=500 msg=条件筛选至少需要 1 个条件（正确拒绝）✅

# DDL 验证
gz_coupon_template 新增列:
  auto_issue tinyint(1) NOT NULL DEFAULT 0 ✅
  last_auto_issue_time datetime(3) YES ✅
（V202606301919 Flyway 已应用）
```

### admin Playwright E2E

```
ADMIN_BASE=http://localhost:8090 node acceptance.mjs --only 60-coupon-template
✅ 60-coupon-template rows=2 +dlg  优惠券-券模板（带弹窗截图）
d18-coupon-check.png: 确认页面含「自动发放」文本 ✅（hasAutoIssue=true）
截图: 60-coupon-template.png / 60-coupon-template-dialog.png
```

### 跳过

- 真机微信原生能力 → Tier 2
- SnailJob 控制台手配 gzCouponAutoIssueTask cron → 需 Kevin 手操
- auto_issue 开关 UI 交互（toggle）+ 试跑弹窗 → 已确认按钮存在，完整 UI 流程待人工验

### 结论

✅ Tier 1B 通过（GZ-COUPON-003 自动发放）：
- auto-issue-once 首次发放 ✅
- 重复跑去重（0 重发）✅
- DDL 迁移 V202606301919 已应用 ✅
- 券模板页渲染 + 「自动发放」UI 可见 ✅
