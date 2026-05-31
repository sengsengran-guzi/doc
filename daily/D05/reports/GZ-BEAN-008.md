# GZ-BEAN-008 完工报告 — admin 预约列表 + 扫码 / 手动核销

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 主线程指示「项目非 git repo，§0 git 跳过，不 commit」（RuoYi-Vue-Plus 子目录有上游 clone 的 git，仅用于看 diff，不提交） |
| 上游依赖 merge | ✅ BEAN-004（controller `/system/gz/bean/booking` + service verify/cancel/selectPageList + QrCodeSigner + 菜单 6050-6056 含 `gz:bean:booking:verify`）；BEAN-005（selectVoById enrich + qrPayload 即时重算口径） |
| 关键类/表存在 | ✅ GzBeanBookingController / ServiceImpl / QrCodeSigner / GzBeanBooking entity / mapper；gz_bean_booking 表存在；sys_user.gz_store_id 字段存在（ADMIN-001 ALTER） |
| 编译通过 | ✅ mvn compile + install（gz-bean）/ plus-ui build:prod 均过 |
| ADR 已读 | 无相关 ADR（doc/_adr 空）；权威蓝图 doc/10 §3（N10/N11 核销 + E6/E7/E8 异常分支）+ doc/11 §3.4/§3.5/§A.3 已对齐 |

**真实状态修正（主线程已提示，已核对）**：
- admin 列表 + 手动核销在 BEAN-004 已存在，**未新建** `/gz/bean/admin` 控制器；增量挂在现有 `GzBeanBookingController`（前缀 `/system/gz/bean/booking`）。
- 菜单 6050「预约管理」component=`gz-bean/booking/index`、perm=`gz:bean:booking:list`（owner+staff）BEAN-004 已建 → **未重复建菜单 DDL**；扫码核销复用 `gz:bean:booking:verify`（无新权限点）。
- 状态字典 `gz_bean_booking_status` 全工程无 → 本 ticket 新建（唯一处）。

## 实现摘要

### 改动文件（git diff --stat + 新增）

**后端 ruoyi-gz-bean（增量）**
- `controller/GzBeanBookingController.java`：list 加 store_id 隔离（resolveStaffStoreId）；新增 `POST /verify-scan`（`@SaCheckPermission("gz:bean:booking:verify")` + `@Log(title="拼豆预约扫码核销", businessType=UPDATE)`）
- `service/IGzBeanBookingService.java`：加 `verifyByQrPayload` + `selectPageList(query, pageQuery, staffStoreId)` 重载
- `service/impl/GzBeanBookingServiceImpl.java`：抽出私有 `doVerify(booking, operatorId, logNote)`（手动 + 扫码共用）；`verify()` 与 `verifyByQrPayload()` 都调它；selectPageList 加 store 隔离 + statusList 多选 + 列表 enrich storeName
- `domain/bo/GzBeanBookingQueryBo.java`：加 `statusList`（多选筛选）
- `exception/GzBeanErrorCode.java`：加 4009 QR_PAYLOAD_MALFORMED / 4010 QR_SIGNATURE_INVALID
- `mapper/GzBeanBookingMapper.java`：加 `selectByBookingNo`
- **新增** `mapper/GzAdminUserStoreMapper.java`：只读直查 `sys_user.gz_store_id`（不改 ruoyi-system 源码）
- **新增** `domain/bo/GzBeanBookingVerifyScanBo.java`：扫码请求体 `{qrPayload}`（@NotBlank）
- `test/.../GzBeanBookingServiceImplTest.java`：加 4 个 QR 扫码 case

**状态字典 DDL**
- **新增** `ruoyi-admin/src/main/resources/db/migration/V202606020030__GZ-BEAN-008-dict-booking-status.sql`

**Admin 前端 plus-ui（纯新建 + i18n）**
- **新增** `src/views/gz-bean/booking/index.vue`（列表 + 筛选 + 扫码 dialog + 手动核销）
- **新增** `src/api/gz-bean/booking.ts`（page / detail / verifyManual / verifyByScan）
- `package.json`：加 `jsqr@1.4.0`（Kevin §6#8 已批准；MIT，纯 JS QR 解码，零传递依赖）
- `src/lang/zh_CN.ts` + `src/lang/en_US.ts`：`gzBeanBooking.*` 全覆盖

### 关键技术点

- **verify-scan 端点路径**：`POST /system/gz/bean/booking/verify-scan`，body `{qrPayload}`
- **doVerify 抽出共用**：✅ 是。`verify(id)`（手动）查 booking 后调 `doVerify`；`verifyByQrPayload(payload)`（扫码）解析→回表→校签后调同一 `doVerify`。底层逻辑唯一（status=pending 守卫 + UPDATE used + verifyTime + verifiedBy + dedupToken 切 booking_no + 写 admin booking_log），仅 logNote 区分入口（"店员手动核销" / "店员扫码核销"）
- **签名校验**：复用 `QrCodeSigner.verify(bookingNo, booking.sessDate, booking.seatId, verifyCode)`，密钥统一走 `GzBeanQrProperties.signingSecret`（与 BEAN-004 submit / BEAN-005 详情即时重算同源，不新生）
- **QR payload 解析**：`split("\\|", -1)` 严格 3 段 + 首段 "BK" + 后两段非空，否则 QR_PAYLOAD_MALFORMED
- **store_id 隔离结论**：owner / superadmin → resolveStaffStoreId 返 null（看全部，受 query.storeId 可选筛选）；staff → 读 `sys_user.gz_store_id` 强制隔离（忽略前端 query.storeId 防越权）。当前种子 staff(101) gz_store_id=NULL（待 ADMIN-002 UI 配），NULL 时不额外拦截（V1.0 单店安全默认，与 GZ-SYS-006 staff scope 同思路）。角色判定复用 GZ-SYS-006 的 `LoginUser.getRolePermission()` 模式
- **前端扫码**：file input（accept image/*，不调摄像头）→ FileReader → Image → canvas getImageData → `jsQR(data, w, h)` → payload → verify-scan。后端业务错误（签名无效 / 状态非法 / 不存在）的中文 msg 由 ruoyi request.ts 拦截器自动 ElNotification toast；dialog 不自动关闭，店员可改手动核销 fallback（强约束 R3）
- **状态字典**：dict_type=`gz_bean_booking_status`，tenant_id='000000'（系统级共享，与 sys_show_hide 同约定），dict_id/dict_code 取 9001-9004 避开 ruoyi 占用；pending=warning / used=success / cancelled=info / no_show=danger。前端 `useDict('gz_bean_booking_status')` + `dict-tag` 回显，筛选下拉同源

## AI 自测（Tier 1A）

### 后端编译 + install
```
$ mvn -o compile -pl ruoyi-modules/ruoyi-gz-bean -am   → 无错误
$ mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am   → BUILD SUCCESS
（install 必跑：spring-boot:run 加载 ~/.m2 jar，新 verify-scan 路由 / GzAdminUserStoreMapper 需 install 后 restart 才生效，CLAUDE.md §5）
```

### 单测（gz-bean 全量 61，含本 ticket 新增 4 QR case）
```
[INFO] Running GzBeanBookingServiceImplTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
  ├─ verifyByQrPayload happy（校签通过 → pending → used）           ✅
  ├─ verifyByQrPayload 签名不通过 → QR_SIGNATURE_INVALID（不核销）   ✅
  ├─ verifyByQrPayload 状态非 pending（已核销）→ INVALID_STATUS      ✅
  └─ verifyByQrPayload 格式非法 → QR_PAYLOAD_MALFORMED（不回表）     ✅
[INFO] Running QrCodeSignerTest      Tests run: 7
[INFO] 全模块汇总  Tests run: 61, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### 状态字典 DDL（dev MySQL 实跑 + 幂等验证）
```
$ docker exec -i sensenran-dev-mysql mysql ry-vue < V202606020030__GZ-BEAN-008-dict-booking-status.sql
$ SELECT dict_sort, dict_label, dict_value, list_class FROM sys_dict_data WHERE dict_type='gz_bean_booking_status';
dict_sort  dict_label  dict_value  list_class
1          待核销       pending     warning
2          已核销       used        success
3          已取消       cancelled   info
4          已过期       no_show     danger
# 再跑一次（幂等）→ rows_after_rerun = 4（先 DELETE by dict_type 后 INSERT，可重复 cleanup 复跑）
# Redis dict cache 已 flush（DEL 000000:sys_dict），后端下次 useDict 重载
```

### SQL 真 schema 校验（selectByBookingNo + gz_store_id 读）
```
$ SELECT id,booking_no,status FROM gz_bean_booking WHERE booking_no='NOPE' AND del_flag='0' LIMIT 1;  → selectByBookingNo sql-ok
$ SELECT user_id,user_name,gz_store_id FROM sys_user WHERE user_id IN (100,101);
100  gz_owner          NULL   （owner → 看全部）
101  gz_staff_chengdu  NULL   （staff 未绑店 → V1.0 单店安全默认看全部，待 ADMIN-002 UI 配）
```

### Admin 前端构建（TS + 模板 gate）
```
$ pnpm add jsqr@1.4.0   → + jsqr 1.4.0  Done
$ pnpm build:prod       → 完整 asset 列表产出，无 TS / 模板 error
  （vue-tsc + vite 全过；gz-bean/booking/index 懒加载 chunk 已 emit）
```

### admin 三路径自测说明（kevin-coder 无 Playwright，描述 + 留 Tier 1B 验）
1. **列表 + 筛选**：进「拼豆管理 / 预约管理」→ 门店下拉（getGzBeanStoreOptions，type=pindou 由 BEAN-001 options 端点保证）/ 日期范围 picker 默认今天 / 状态多选（useDict 4 项）/ 手机号模糊 → 查询调 `GET /list`（owner 全量 / staff 后端强制本店）
2. **手动核销**：列表 pending 行「核销」按钮（非 pending 行 disabled）→ ElMessageBox 二次确认 → `POST /{id}/verify` → 成功 toast + 刷新；非法状态后端 INVALID_STATUS 中文 msg 自动 toast
3. **扫码核销**：「扫码核销」按钮 → dialog → 上传 QR 截图 → jsQR canvas 解码 → 预览 payload → 「确认核销」→ `POST /verify-scan` → 后端校签 + 状态校验；签名无效 / 已核销 → 中文 msg toast + dialog 保留供手动 fallback

## 风险提示 / 已知 issue

- **R1（store 隔离 NULL 默认）**：当前 staff 种子账号 gz_store_id=NULL，按代码会「看全部」。V1.0 单门店场景下等价无害；待 ADMIN-002 UI 给 staff 绑店后才真正隔离。这是设计选择（与 GZ-SYS-006 staff scope 一致），非 bug。
- **R2（dev DB Flyway 历史）**：dev MySQL 当前无 `flyway_schema_history` 表（gz 数据似为手工/脚本预置）。我手工执行了本 DDL 用于验证 —— 因 DDL 幂等（先 DELETE by dict_type），未来 Flyway 在干净环境跑该 version 无冲突。后端首次启动若走 Flyway，本 migration 正常生效。
- **R3（jsqr 解码率）**：模糊 / 含杂物截图可能解不出 → 前端「未识别到二维码，请重新截图」+ 保留手动核销 fallback（已实现）。
- **待 Kevin 批量人验关注**：N/A — 纯 admin + 后端 ticket，Tech 段无 `miniapp/` 路径、AC 无微信原生能力 → 按 CLAUDE.md §8.2 例外，**无人验**，AI Tier 1A+1B 全 ✅ 即终态 close。

## 对下游 ticket 的提示

- **ADMIN-002（admin-user CRUD）**：给 staff 账号配 `gz_store_id` 后，本页 store 隔离才真正生效（owner 看全部 / staff 仅本店）。建议 ADMIN-002 完工后回归验一次「staff 登录预约列表只见本店」。
- **未引入临时入口**：本 ticket 纯 admin，无 mp 新页 → 无 Tier 2 可达性临时入口需求；也未发现需清理的 `Tier2-entry-temp`（grep 无命中本 ticket 范围）。
- **状态字典已建**：后续任何 admin/统计页要显示预约状态标签，直接 `useDict('gz_bean_booking_status')`，勿重复建 dict_type。

## §AI 测试段（kevin-qa 完工后追加）

（占位，kevin-qa spawn 完成后追写到此）
