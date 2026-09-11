# GZ-RECYCLE-016 — 回收提交页客服微信二维码

**优先级**: P2
**复杂度**: S
**关联 PRD**: doc/02-prd.md M10（回收预约）
**关联拆解**: N/A（甲方 8.27 微信新提，不在原 57 ticket 索引内）
**关联 mockup**: N/A
**关联 ADR**: N/A（复用既有 sys_config 运营素材模式，无需新 ADR）
**依赖**: 无

---

## 需求原文（甲方微信，2026-08-27）

甲方发来一张客服微信二维码截图，配文：

> 「中古回收 最后确认那 放一张客服的微信图片」

Kevin 转述给 AI 时进一步定位为「回收提交页」。

## 必读权威文档

- 复用现成模式：`gz.bean.home.banner` / `gz.home.banners`（sys_config + `MpPublicConfigKeyResolver` 白名单 + `@SaIgnore` 公开端点），非新造机制
- 字段表：本 ticket 不改业务表，无需 doc/11 新增段（仅新增一条 sys_config 行，非 gz 业务表）

## What

回收提交页（`pages/recycle/form.vue`）选完到店时间、提交按钮上方，加一块客服微信二维码：图 + 「长按识别，添加客服微信」提示。图片来源走 admin 可配置（sys_config），甲方素材未上传时整块不渲染。

## AC（验收标准）

- [ ] AC 1：新增 `sys_config` key `gz.recycle.serviceQrcode`（纯 OSS 图片 URL 字符串），已在 `MpPublicConfigKeyResolver` 白名单登记
- [ ] AC 2：mp 端 `GET /app/gz/common/config/get?key=gz.recycle.serviceQrcode` 匿名可读，值为空时返回空字符串（不报错）
- [ ] AC 3：`pages/recycle/form.vue` 在 `serviceQrUrl` 非空时渲染 `<image show-menu-by-longpress>` + 提示文案；为空时整块不渲染
- [ ] AC 4：admin「系统管理 → 参数设置」页能搜到、编辑这条 key（不新建 admin 页面）
- [ ] AC 5：非白名单 key（如 `sys.user.initPassword`）仍被拒绝，本次改动不放宽安全边界

## 技术要点（AI 落地时的关键决策）

1. **图片走 `show-menu-by-longpress`**（WeChat Mini Program 2.7.0+ 原生属性），用户长按图片走系统「识别图中二维码」——不是企业微信客服组件（`BizCustomerServiceFab`，目前 `CS_ENABLED=false` 全局下线），是完全独立、更轻量的静态图机制，两者不冲突不复用。
2. **config_value 是纯字符串**（不是 JSON），比 `gz.bean.home.banner` 更简单——这里只需要一张图，不需要标题/跳转链接。
3. **⚠️ 新增 sys_config 行必须显式写 `tenant_id='1001'`**——实施过程中踩了这个坑（见完工报告），已修正并记入本条备忘：`sys_config.tenant_id` 列 DEFAULT 是 ruoyi 原生 `'000000'`，裸 `INSERT` 不显式赋值会导致 admin（单租户 1001 会话）搜不到这一行。后续任何新增 sys_config seed 迁移都要显式带 `tenant_id`，不能照抄旧迁移的写法（旧迁移当前是 1001 是事后被 V202607272010 单租户合并迁移改过的，不是它们原始 INSERT 就对）。
