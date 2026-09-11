# D23 — 回收提交页客服微信二维码

> 需求来源：2026-08-27 甲方（森森然）微信，配发一张客服微信二维码截图。

## 本批 ticket

| Ticket | 内容 | 复杂度 |
|---|---|---|
| `GZ-RECYCLE-016` | 回收提交页最后确认区加客服微信二维码（admin 可配置、素材未配时不渲染） | S |

## 需求原文（甲方微信）

> 「中古回收 最后确认那 放一张客服的微信图片」（附一张个人微信「扫一扫，添加我为朋友」二维码截图）

## 实现思路

复用项目已有的运营素材机制（`gz.bean.home.banner` / `gz.home.banners` 同款：`sys_config` + `MpPublicConfigKeyResolver` 白名单 + `@SaIgnore` 公开端点），不新建业务表、不新建 admin 页面。位置放在 `pages/recycle/form.vue` 选完到店时间、提交按钮上方。

## 踩的坑（记入 ticket 卡片 + curator 后续可抽 skill）

新增 `sys_config` 行裸 `INSERT` 不显式写 `tenant_id` 会落到列 DEFAULT `'000000'`，而本项目已单租户合并到 `1001`（V202607272010），导致 admin 搜不到这行。已用订正迁移修复，并记入 ticket 备忘：**以后新增 sys_config seed 一律显式写 `tenant_id='1001'`**，不能照抄旧迁移（旧迁移当前是 1001 是事后被单租户合并迁移改过的，不是原始 INSERT 就对）。

## 交付前须向甲方确认

无——本 ticket 是甲方原话的直接翻译。**图片本体**待 Kevin 提供（本会话工具链无法把聊天里的图片导出成文件），Kevin 通过 admin「文件管理」上传后，到「参数设置」把 `gz.recycle.serviceQrcode` 这行的参数键值改成 OSS URL 即可生效，不需要发版。

## AI 测试结论

| 项 | 状态 |
|---|---|
| 后端单测（gz-common resolver） | ✅ 11/11 |
| mp vitest | ✅ 529/529（新增 4 个） |
| vue-tsc + eslint | ✅ 零错（4 个 lint 报错核实为改动范围外的既有噪音） |
| Flyway 迁移 + tenant 订正 | ✅ 真库验证（含一次坑的发现与修复） |
| mp 端点 curl（含白名单边界回归） | ✅ |
| admin 真浏览器编辑闭环 | ✅（含发现的「不能清空」UX 边界，记入已知 issue） |
| mp 模拟器 E2E | 未做（纯展示静态图块，无交互分支；理由见 report §已知 issue 2） |

详见 `reports/GZ-RECYCLE-016.md`。
