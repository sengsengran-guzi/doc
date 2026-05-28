# GZ-BEAN-001 — 门店主数据（后台 + mp）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §关键字段 § Store + 关键页面（后台门店管理）
**关联拆解**: doc/02-需求拆解.md §2.3 第 283 行
**关联 mockup**: design/mockup/booking-select.html（顶部门店选择条 — 视觉参考）
**关联 ADR**: —
**依赖**: GZ-ADMIN-001 ✅(D03)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §前置依赖 §关键节点（门店切换 / 门店配置）
- **字段表**：doc/11-字段权威表.md **§3.1 `gz_bean_store` 门店表**（字段权威 — 完整 DDL 来源）+ §1 全局公共字段
- **UI 参考**（设计冻结期）：
  - mp ticket：`booking-select.html` 顶部门店选择条 — V1.0 单门店时隐藏选择条，直接显示门店名
  - admin ticket：N/A（plus-ui BizTable + el-form 默认）

## What

落地 `gz_bean_store` 表 + entity + mapper + Service；admin 端门店 CRUD（owner 权限）；mp 端门店列表 API（V1.0 仅返回 1 家成都拼豆店，UI 可隐藏选择条）。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606010900__GZ-BEAN-001-create-gz_bean_store.sql` 严格按 doc/11 §3.1（含 id / type enum(`pindou`/`guzi`) / name / address / phone / business_status enum(`active`/`closed`) / location_lng / location_lat + 全局公共字段）；UNIQUE `(tenant_id, name)`；索引 `idx_type_status`
- [ ] **AC 2**：admin 端 `views/gz-bean/store/index.vue` CRUD（plus-ui BizTable 默认）— owner 权限 `gz:bean:store:list/edit`
- [ ] **AC 3**：admin 端新建表单 type 字段默认 `pindou`（V1.0 仅 pindou 有预约能力，guzi 占位）；business_status 默认 `active`
- [ ] **AC 4**：mp 端 `GET /app/gz/bean/store/list` 返回 type=pindou + business_status=active 的门店列表（V1.0 单门店时返回 1 行）
- [ ] **AC 5**：写操作（新建/编辑/状态切换）加 `@Log(title="拼豆门店", businessType=...)`（SYS-006 规约）
- [ ] **AC 6**：sys_menu 插入「谷子业务 → 拼豆管理 → 门店管理」menu_id 6001（parent=100 谷子业务 / 6000 拼豆管理目录），perm `gz:bean:store:list`
- [ ] **AC 7**：种子数据 INSERT 1 条「成都拼豆店」（地址 / 电话占位，业务上线前甲方录入真实数据）
- [ ] **AC 8**：单测 happy path + 一个 UNIQUE 拦截（同名门店再加）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`（脚手架 D01 已建）
  - `controller/GzBeanStoreController.java`（admin 路径 `/system/gz/bean/store`）
  - `controller/applet/GzBeanStoreMpController.java`（mp 路径 `/app/gz/bean/store`，仅 list 接口）
  - `domain/GzBeanStore.java` + `domain/vo/GzBeanStoreVO.java` + `domain/bo/GzBeanStoreBo.java`
  - `mapper/GzBeanStoreMapper.java`
  - `service/IGzBeanStoreService.java` + `service/impl/GzBeanStoreServiceImpl.java`
  - DDL × 3：建表 / 菜单 / 种子数据（V202606010900 / 0901 / 0902）
- **Admin**：`views/gz-bean/store/index.vue` + `api/gz-bean/store.ts` + i18n
- **小程序**：`api/gz-bean.ts` 加 `getStoreList()`；UI 在 BEAN-010 拼豆首页消费（本 ticket 不直接写 mp 页）
- **测试**：mvn 单测 + admin 浏览器实操

## 备注

### 强约束

1. **type=guzi 占位**：V1.0 不实现 guzi 类型门店的预约 UI / API（doc/02 §2.3 第 287 行），但 schema 允许存（多门店扩展预留）
2. **V1.0 单门店但模型多门店**：所有业务表（gz_bean_seat / gz_bean_time_slot_template / gz_bean_booking）必含 store_id 外键，便于 v2 扩展
3. **UNIQUE 必含 tenant_id**（CLAUDE.md §6 #3）
4. **business_status 用 enum 不用 boolean**（后续可能扩 `under_maintenance` / `temporarily_closed` 等态）
5. **menu_id 段 6000-6099**（CLAUDE.md §6 #6 GZ-BEAN 6000-6999；6000 拼豆管理目录，6001 门店）

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | location_lng/lat 字段 V1.0 是否填 | 接受：V1.0 admin 后台暴露字段但不强制；后续接入地图导航时（v2）才用 |
| R2 | 门店删除时已有预约怎么办 | 软删（del_flag='1'）+ 业务上禁止删除 active 门店（先 closed 再删） |

---

## §revision（Kevin testing-human 后填，初始空）
