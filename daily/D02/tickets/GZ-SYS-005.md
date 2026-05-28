# GZ-SYS-005 — 文件上传与对象存储对接

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M6 §文章编辑器 / M7.6 资讯管理
**关联拆解**: doc/02-需求拆解.md §2.1 第 232 行
**关联 mockup**: design/mockup/admin-news.html（视觉参考，但本 ticket 仅做底层上传服务，富文本组件在 GZ-NEWS-003）
**关联 ADR**: —（无）
**依赖**: GZ-SYS-001 ✅

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §5 资讯发布流（涉及富文本图片上传）；其他业务（GZ-USER-002 头像 / GZ-BEAN-XX 占位 / V1.1 商品图）均消费本 ticket 提供的统一上传 API
- **字段表**：doc/11-字段权威表.md **§5.3 `gz_file_object` 对象存储文件元数据**（全局共用 — 本 ticket 落 DDL 的权威依据）+ §1 全局公共字段
- **UI 参考**（设计冻结期）：
  - admin ticket：N/A（设计冻结期 admin 走 ruoyi 默认 + el-upload 默认）
  - mp ticket：N/A（本 ticket 仅提供 API，mp UI 在 GZ-USER-002 / GZ-NEWS 等消费方做）

## What

落地 `gz_file_object` 表 + 统一文件上传 API（admin 走 ruoyi 自带 `OssClient` 抽象，dev 用 MinIO，prod 切阿里云 OSS）；admin 端 / mp 端业务字段只存 file_id，返回 URL 时后端统一拼。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202605281100__GZ-SYS-005-create-gz_file_object.sql` 落地 `gz_file_object` 表，字段严格按 doc/11 §5.3（file_id BIGINT pk / oss_key / bucket / file_name / file_size / mime_type / md5 / scene_tag / uploader_user_id / uploader_user_type enum(`admin`/`mp_user`) + 公共字段）
- [ ] **AC 2**：admin 端 `POST /system/gz/file/upload`（multipart/form-data，参数 `file` + `sceneTag`）→ 调 ruoyi `OssClient.upload(...)` 上传 → 落 `gz_file_object` → 返回 `{fileId, ossKey, url}`；单文件 ≤ 10MB；图片白名单 jpg/png/webp/gif；非图片 → 400
- [ ] **AC 3**：mp 端 `POST /app/gz/common/file/upload`（同上参数 + sa-token mp-client 权限）→ 同后端服务，uploader_user_type = `mp_user`
- [ ] **AC 4**：admin 端 + mp 端 `GET /system/gz/file/url?fileId=` / `/app/gz/common/file/url?fileId=` 返回签名 URL（带 1h 过期签名，避免 oss_key 直接暴露）；业务表只存 `file_id BIGINT`，渲染时调 url 接口
- [ ] **AC 5**：sys_oss_config 默认填 1 行 dev profile MinIO 配置（endpoint `http://sensenran-dev-minio:9000` / bucket `sensenran-dev` / access-key `ruoyi` / secret-key `ruoyi123`），prod profile 走 env var 占位符（dongjiaoshan 同款模式）
- [ ] **AC 6**：admin 端测试页 `views/gz-common/file/upload-test.vue`（plus-ui el-upload 默认风格 + 上传成功展示返回 file_id / url）— 用于本 ticket testing-human 验证
- [ ] **AC 7**：单测 `GzFileServiceImplTest` 至少 1 个 happy（mock OssClient 上传）+ 1 个白名单拦截（上传 .exe → 400）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`
  - `controller/GzFileController.java`（admin 路径 `/system/gz/file`）
  - `controller/applet/GzFileMpController.java`（mp 路径 `/app/gz/common/file`）
  - `domain/GzFileObject.java` + `domain/vo/GzFileObjectVO.java`
  - `mapper/GzFileObjectMapper.java`
  - `service/IGzFileService.java` + `service/impl/GzFileServiceImpl.java`
  - 复用 ruoyi `org.dromara.common.oss.core.OssClient` + `OssFactory`（无需新引依赖）
  - DDL：`V202605281100__GZ-SYS-005-create-gz_file_object.sql`
  - sys_menu 插入：admin 端「系统管理 → 文件管理」menu_id 5031 + perm `gz:file:list` / `gz:file:upload`
  - **不**新建 sys_oss_config（ruoyi 已有），仅 INSERT 1 行 dev profile 默认配置
- **Admin**：`views/gz-common/file/upload-test.vue`（测试页，el-upload 默认）+ `api/gz-common/file.ts`
- **小程序**：本 ticket 不实装 mp 上传 UI（GZ-USER-002 改头像时第一次用），仅 `api/gz-common.ts` 加 `uploadFile()` + `getFileUrl()` 函数
- **测试**：mvn + admin upload-test.vue 联调

## 备注

### 强约束

1. **业务表只存 file_id（BIGINT）不存 URL**（避免 oss bucket 切换 / 域名变更时业务表大量 ALTER）
2. **URL 必带签名 + 1h 过期**（防止 file_id 枚举攻击）
3. **白名单严格 jpg/png/webp/gif**（V1.0 不允许任何其他类型；视频上传在 V1.1 资讯里再扩）
4. **单文件 ≤ 10MB**（PRD M6 §文章编辑器约定）
5. **不直接调阿里云 OSS SDK** — 用 ruoyi `OssClient` 抽象（CLAUDE.md §6 #8 不引未澄清新依赖；ruoyi 已抽象 minio/aliyun/qiniu/cos）
6. **prod profile sys_oss_config 走 env var 占位符**（dongjiaoshan 同款 `${ALIYUN_OSS_ACCESS_KEY:default}`）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 ruoyi 自带 sys_oss_config + OssClient，不重写 | 范式齐备，避免重复造轮子 |
| D2 | 新建 gz_file_object 而非用 ruoyi 自带 sys_oss | sys_oss 是 ruoyi 自带通用 OSS 文件表，我们不污染它；gz_file_object 是 sensenran 业务文件元数据，加 scene_tag（cs_avatar / news_cover / news_body / preorder_main / ...）方便后续业务查询 |
| D3 | URL 签名 1h 过期 | 平衡安全性与缓存友好（CDN 上 1h 内 URL 不变可缓存）|
| D4 | mp 端 uploader_user_type = 'mp_user' 用 enum 不用 boolean | 后续可能扩出更多类型（如 admin_subaccount）|
| D5 | dev profile MinIO 与 dongjiaoshan 共用容器命名规则但隔离 bucket | sensenran-dev bucket，避免与 dongjiaoshan-dev bucket 数据互串 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 阿里云 OSS bucket 尚未创建（D01 §AC 2.2 Kevin 自推进中）| 本 ticket 仅落 dev profile 配置，bucket 真实化由 Kevin 启动费推进；上线前最后一步切 prod profile 即可 |
| R2 | 微信小程序 wx.uploadFile 与本 ticket POST `/app/gz/common/file/upload` 契约差异 | 接受：本 ticket 仅设计 RESTful API（multipart/form-data），mp 端用 `wx.uploadFile` 时按同款 multipart 契约调用，GZ-USER-002 实施时确认 |
| R3 | file_id BIGINT 在跨表 join 时性能 | 接受：file_id 索引主键 BTree O(log n)，业务表通过 file_id 关联读单条 OK |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
