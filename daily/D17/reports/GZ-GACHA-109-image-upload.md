# GZ-GACHA-109（part 1）完工报告 — 扭蛋后台图片直传（封面 / 奖品图）

> 后台扭蛋配置增强 part 1：把「手填文件 ID」换成「直接上传图片」。
> part 2（machine 出荷时间 + 尺寸字段，碰 DDL）另做。

## What

admin 扭蛋机/奖品配置原来要运营**手填 `gz_file_object.id`**（截图：封面 file_id 输入框），体验差。改为**直接上传图片**：选图 → 传 OSS → 自动存 fileId + 预览。

## 改了哪些文件（plus-ui）

| 文件 | 改动 |
|---|---|
| `src/components/GzImageUpload/index.vue` | **新建**可复用图片上传组件（gz_file_object 体系，v-model 绑 fileId 字符串，非裸 url） |
| `src/views/gz-gacha/machine/index.vue` | 封面：`el-input`(手填id) → `<GzImageUpload v-model="form.coverImageId">`；删 coverImageIdStr 计算属性 |
| `src/views/gz-gacha/prize/index.vue` | 奖品图：`el-input`(手填id) → `<GzImageUpload v-model="form.imageId">`；删 imageIdStr 计算属性 |
| `src/lang/zh_CN.ts` / `en_US.ts` | 增 `gzImageUpload.*`（上传/移除/校验提示） |

## 复用现成后端（无需新建）

- 上传：`POST /system/gz/file/upload`（multipart `file` + `usageType`，权限 `gz:file:upload`）→ 返回 `{fileId, url, ...}`（GZ-SYS-005 已建）
- 回显：`GET /system/gz/file/url?fileId=` → 1h 预签名 url
- usageType 用 `gacha_prize_image`（封面也复用此场景；枚举无独立 machine_cover）
- api 封装 `@/api/gz-common/file`（uploadGzFile / getGzFileUrl）已存在

## 组件能力

- 选图即传（auto-upload）；jpg/png/webp/gif，≤10MB 前端校验
- 上传成功 emit fileId（字符串，对齐表单字段）；编辑回显按 id 反查预签名 url 预览
- 120×120 预览卡 + 移除按钮；上传/加载 loading 态
- 模式同 `gz-common/file/upload-test.vue`（已联调过的范式），不另起炉灶

## 自测

```
$ grep -rn "coverImageIdStr|imageIdStr" src/   → 0（手填字段已清干净）
$ pnpm exec eslint <5 改动文件>                → 0 error（--fix 后）
$ pnpm exec vue-tsc --noEmit | grep 改动文件   → 0（类型干净）
```

## ⚠️ 依赖 Kevin：配置 OSS

上传落地依赖 RuoYi OSS 配置（`sys_oss_config`，腾讯云 COS / 合同附件二指定腾讯云）。**Kevin 配好 OSS 后**，admin 上传即通；未配则上传报错（后端 OSS 客户端未就绪）。

## 待办

- **part 2**：machine 加「出荷时间 ship_time + 尺寸 size_desc」字段（Flyway 加列 + entity + VO + 表单 + mp 展示）对齐竞品。
- 端到端真传一张图验证：需 Kevin 起 admin + 配好 OSS（我无法在此跑）。
