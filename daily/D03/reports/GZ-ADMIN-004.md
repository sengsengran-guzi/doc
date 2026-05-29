# GZ-ADMIN-004 — 完工报告

> 后台路由 / 布局 / 侧边栏 — 收编 D02 业务菜单到「谷子业务」5000 根 + StoreSelector + 按角色默认跳转。
> 主线串行实施（无 spawn 并行 subagent — S 复杂度小 ticket）。

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | ✅ N/A | 仓库未 init git；wave 内不 commit，等当日 5 ticket ✅ 后统一 |
| 上游依赖 merge | ✅ GZ-ADMIN-001（D03 wave-1）已 ✅ — menu_id=5000 根 + sys_role 100/101 + sys_user gz_store_id 字段全部就位 | reports/GZ-ADMIN-001.md |
| 关键类 / 表 / API 硬探 | ✅ | 见下「§0 硬探记录」 |
| 编译通过 | ✅ plus-ui `pnpm build:dev` ✓（12.9s，0 ts 错） | 仅 chunk-size 警告，ruoyi 默认行为 |
| 权威蓝图引用完整 | ✅ doc/02-prd.md M7（admin 基础布局承载所有子模块） | 任务卡明示「关联 mockup: N/A 设计冻结期」走 ruoyi 默认 |
| ADR 已读 | 无相关（doc/_adr/ 空） | 本 ticket 不到 ADR 阈值（仅 reparent + 单组件 + i18n + permission guard 改写，影响 ≤ 5 文件） |
| 合同范围 | V1.0（合同 §2.1 第 5 项「后台基础」） | D03 = 2026-05-29 ≤ 6/15 硬期限 |

### §0 硬探记录

```bash
# 1. 确认 D02 顶级菜单错挂状态（任务要求修复点）
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e \
  "SELECT menu_id, menu_name, parent_id, menu_type FROM sys_menu \
   WHERE menu_id IN (5000, 5001, 5021, 5031, 5500) ORDER BY menu_id"
menu_id  menu_name        parent_id  menu_type
5000     谷子业务         0          M           ← ADMIN-001 已落 ✅
5001     C 端用户管理     0          M           ← SYS-003 顶级，需 reparent 到 5000
5021     客服配置         1          C           ← SYS-004 错挂 ruoyi 系统管理！需 reparent
5031     业务文件管理     1          C           ← SYS-005 错挂 ruoyi 系统管理！需 reparent
(5500 不存在 — 本 ticket 新建)

# 2. 5500 段 ID 空闲检查
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e \
  "SELECT MAX(menu_id) FROM sys_menu WHERE menu_id BETWEEN 5500 AND 5599"
MAX(menu_id) = NULL   ← ✅ 5500 段段首未占

# 3. 已有 D03 migration 时间戳无冲突
$ ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/V20260529*
V202605291000__GZ-ADMIN-001-extend-sys-user.sql
V202605291001__GZ-ADMIN-001-seed-roles.sql
V202605291002__GZ-ADMIN-001-seed-admin-users.sql
# 本 ticket 用 V202605291200/1201 时间戳 > 1002 ✅

# 4. plus-ui Navbar / permission / lang 结构
$ ls code/main/plus-ui/src/layout/components/Navbar.vue   ✅ 存在
$ ls code/main/plus-ui/src/permission.ts                   ✅ 存在
$ cat code/main/plus-ui/src/lang/zh_CN.ts | grep "^export\|route:"  ✅ 单文件结构

# 5. ADMIN-001 owner role_menu 是否已含 5000-5999 段批量授权
$ grep "BETWEEN 5000 AND 5999" V202605291001__GZ-ADMIN-001-seed-roles.sql
WHERE m.menu_id BETWEEN 5000 AND 5999;   ← ✅ owner 自动覆盖本 ticket 新增的 5500
```

### 关键发现 / 任务卡偏差适配

任务卡 AC 1 列了 4 个一级目录（100/200/300/400），但 ruoyi 自带 menu_id 段已占用这些 ID：

| 任务卡描述 | 实际落地 | 处理 |
|---|---|---|
| 100 谷子业务 | **5000**（ADMIN-001 已落） | 不动 — 本 ticket 仅 reparent 子菜单挂进来 |
| 200 系统管理 | **ruoyi 自带 menu_id=1**（路径 `/system`） | 不动 — 复用 |
| 300 数据看板 | **5500**（本 ticket 新建） | INSERT IGNORE 5500，预留 ADMIN-003 / D07 |
| 400 操作日志 | **ruoyi 自带 menu_id=500** 挂在 monitor/operlog | 不动 — 复用 |

依据：CLAUDE.md §6 #6 GZ-SYS 段 5000-5999 + D03 README §今日特殊约束「menu_id 段 5000-5099」+ ADMIN-001 reports §0 已记录同款偏差。

---

## 实现摘要

### 改动文件清单

```
NEW（共 3 个 — 2 DDL + 1 组件）：
  ruoyi-admin/src/main/resources/db/migration/
    V202605291200__GZ-ADMIN-004-menu-structure.sql        (49 行 — UPDATE 5001/5021/5031 parent_id + INSERT 5500)
    V202605291201__GZ-ADMIN-004-role-menu-mapping.sql     (60 行 — owner 补 5500 + staff 业务菜单子集 + ruoyi 操作日志路径)
  plus-ui/src/components/StoreSelector/
    index.vue                                              (37 行 — V1.0 单门店硬编码 + i18n placeholder)

MODIFIED（共 4 个）：
  plus-ui/src/layout/components/Navbar.vue                +6 行：import StoreSelector + isSuperadmin computed + <store-selector v-if> 模板挂载
  plus-ui/src/permission.ts                               +30 行：DEFAULT_PATHS map + resolveDefaultPath helper + router-guard 重写 to.path
  plus-ui/src/lang/zh_CN.ts                               +21 行：route.gz.* 11 个 key + storeSelector.* 3 个 key
  plus-ui/src/lang/en_US.ts                               +21 行：同上 en 版本
```

**Java 代码改动**：0（任务卡 §Tech "**后端仅 DDL**"）
**miniapp 改动**：0（admin 端 ticket 与 mp 无关）

### 新增产物

**数据层**：
- UPDATE 3 条 sys_menu reparent（5001 / 5021 / 5031 → parent_id=5000）
- INSERT 1 条 sys_menu（5500 数据看板顶级）
- INSERT 1 条 owner→5500 关联（兜底，BETWEEN 已含）
- INSERT 10 条 staff role_menu 关联（5500 + 5001-5003 + 5021 + 5031-5032 + ruoyi 2/108/500）

**前端**：
- 1 个新组件：`StoreSelector/index.vue`（topbar 门店切换器，V1.0 单门店硬编码占位）
- 1 处 Navbar.vue 挂载：avatar 左侧 + `v-if="!isSuperadmin"` 避免 ruoyi 兜底账号干扰
- 1 处 permission.ts router-guard：默认跳转按角色重写（owner→/system/user / staff→/gz-c-user/list / superadmin→/index 不变）
- 25 个 i18n key（zh + en × route.gz.* 11 + storeSelector.* 3 + 注释 = 单语 22 净 key）

### 关键决策（决策日记）

| # | 决策 | 理由 |
|---|---|---|
| D1 | 「数据看板」menu_id=5500 而非 5300（与 ruoyi 不冲突的更"低"段） | 5300 位于 GZ-USER 段（CLAUDE.md §6 #6 表 7000-7999 之前的 5000-5999 / 7000+ 都属 GZ 业务），5500 在 GZ-SYS 中段位置，明显与 5000「谷子业务」"目录簇"分开，便于将来 admin UI 把"看板"放进独立顶级目录 |
| D2 | UPDATE 而非 DELETE + 重建 5001/5021/5031 | UPDATE parent_id 风险低 + 保留所有子菜单关联 + 软改动可幂等重跑；DELETE + 重建会丢 sys_role_menu 关联引发 owner / staff 失权 |
| D3 | staff 不授 5004 用户详情按钮 / 5033 文件上传按钮 | 任务卡 AC 2「staff 角色仅业务菜单子集，不含管理员账号管理」— 类比敏感操作（看用户隐私详情 / 改业务文件）也排除。owner 可通过 ADMIN-002 UI 后续给 staff 个别勾选 |
| D4 | StoreSelector 用 `v-if="!isSuperadmin"` 隐藏 | ruoyi 自带 admin/admin123 是兜底账号，不属谷子业务用户；显示门店选择器会让人误解为该账号属"成都店"。owner/staff 都显示组件（disabled when 单门店）|
| D5 | StoreSelector 数据用 computed + i18n 而非 store / API | V1.0 单门店纯展示，不引入 pinia / API 调用（任务卡 R1 接受占位）；BEAN-001 完工后改为 `const { data } = await listStoreOptions()` 一行替换即可 |
| D6 | permission.ts 默认跳转用 router-guard 重写而非 sys_menu `is_default_path` 字段 | 任务卡 §强约束 #4 明确「default_path 实现走前端 router-guard，不动 sys_menu schema」— schema 改动需走 Flyway 并影响 ruoyi 自带后台界面（用户管理列表会多一列）|
| D7 | staff 给 ruoyi 操作日志菜单（2 + 108 + 500）三层路径 | ruoyi 菜单树 500 操作日志的 parent 链是 500 → 108 日志管理目录 → 2 系统监控 → 0；只给 500 不给祖父 108/2，sidebar 渲染时会丢入口（ruoyi MenuTreeUtils 折叠规则）|
| D8 | StoreSelector 组件放 `src/components/StoreSelector/index.vue`（不是任务卡描述的 `views/components/`） | plus-ui 现有结构 `src/components/` 是全局组件目录（LangSelect / SizeSelect 等同款），`src/views/` 不存在 components 子目录；与任务卡 §Tech 字面冲突但匹配 ruoyi 范式 |

### 已知问题 / 风险

| # | 风险 | 缓解 / 处理 |
|---|---|---|
| R1（owner 默认跳 /system/user 权限） | owner 默认跳转目标 `/system/user`（管理员账号管理）是 ruoyi 自带菜单，ADMIN-001 是否已经给 owner 授权 ruoyi 系统菜单？查 ADMIN-001 reports：owner 仅授权 5000-5999 段 — 不含 ruoyi 自带菜单 | **需 ADMIN-002 实施时同步授权 owner ruoyi 自带 `system:user:*` 系列 menu**；本 ticket 暂保留默认跳转配置，ADMIN-002 联调时 owner 登录后点 /system/user 会 404 / 401 — 此为 ADMIN-002 任务卡 §AC 应处理 |
| R2（owner 默认跳转可能落到 / 404） | 上面 R1 的具体表现：跳转目标无权限时 vue-router 进 404 页 | 临时缓解：可改 owner 默认目标为 `/gz-c-user/list`（owner 业务菜单子集，必有权限），但与"管理员账号管理优先"任务卡 AC 6 字面冲突 |
| R3（chunk size 警告 > 500 kB） | 1706 kB chunk 是 ruoyi 默认 monolithic 打包行为 | 不在本 ticket 范围（ruoyi-vue-plus 通用问题），不动 |
| R4（Navbar.vue 5 个 lint 错） | 5 个 lint 错全在 ruoyi 原代码（双引号 / 缺分号 / SCSS）— 不是本 ticket 引入 | 我加的 3 行（import + computed + 模板）已 lint 0 错；CLAUDE.md §10 「不重构 Kevin 没要求的代码」— 不动 ruoyi 原 lint 错 |

### 对下游 ticket 的提示

- **GZ-ADMIN-002（管理员账号 CRUD，本 wave 第三波）**：
  1. 同步授权 owner ruoyi 自带菜单（解决 R1 / R2）— 推荐做法：在 ADMIN-002 DDL 里加：
     ```sql
     INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
     SELECT 100, menu_id FROM sys_menu WHERE menu_id IN (1, 100, 101, 102, 103, 104, 105, 106, 107);
     -- 或参考 ruoyi 自带 superadmin (role_id=1) 关联的 menu_id 列表
     ```
  2. 在「角色管理」UI 提供 staff 角色编辑入口，让 owner 在 UI 上手动给 staff 勾选具体子菜单（解锁本 reports R3：staff 子菜单 UI 上配，不在 SQL 硬编码）
  3. 新建 staff 用户表单的"门店"下拉默认值 = 顶部 StoreSelector 当前 `currentStoreId`（D5 决策预期）
- **GZ-ADMIN-003（数据看板，D07）**：
  - 新建看板页时菜单 `parent_id=5500`，子菜单 menu_id 段 5501-5599
  - 看板首页可作为 owner 登录后默认跳转目标（视设计冻结期之后甲方需求决定，若决定改默认跳转，本 ticket 的 `DEFAULT_PATHS` 只需改一行）
- **GZ-BEAN-001（D04 拼豆门店配置）**：
  - 落 `gz_bean_store` 表后，**改 StoreSelector.vue 第 31-33 行**：
    ```ts
    // 旧（V1.0 占位）
    const storeOptions = computed<StoreOption[]>(() => [{ id: 1, name: t('storeSelector.defaultStore') }]);

    // 新（BEAN-001 完工后）
    import { listStoreOptions } from '@/api/gz-bean/store';
    const storeOptions = ref<StoreOption[]>([]);
    onMounted(async () => { storeOptions.value = (await listStoreOptions()).data; });
    ```
  - 此时还要在 pinia 建 `gzStoreStore` 维护当前选中门店，跨页面共享（如拼豆列表页要按 store 过滤）
- **6/15 V1.0 上线前清单**：
  - [ ] 验证 owner 登录后默认跳 `/system/user` 不报 401（需 ADMIN-002 先授权）
  - [ ] 验证 staff 登录后默认跳 `/gz-c-user/list` 能正常进列表
  - [ ] StoreSelector 在 V1.0 单门店时确实 disabled（避免用户认为可切换）

---

## §AI 测试段（机械验证）

### 1. DDL 时间戳顺序 + 文件结构

```
$ ls -la code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/V202605291200* V202605291201*
-rw-r--r--  1 wkui  staff  2729 May 28 17:47 V202605291200__GZ-ADMIN-004-menu-structure.sql
-rw-r--r--  1 wkui  staff  3987 May 28 17:48 V202605291201__GZ-ADMIN-004-role-menu-mapping.sql
```

2 个文件按时间戳 1200 → 1201 顺序，对应「先 reparent 菜单 / 再补角色映射」依赖顺序。

### 2. 两个 DDL 跑通 + 完整菜单树验证

```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue \
    < V202605291200__GZ-ADMIN-004-menu-structure.sql
(no output = success)

$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue \
    < V202605291201__GZ-ADMIN-004-role-menu-mapping.sql
(no output = success)

$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "
  SELECT menu_id, menu_name, parent_id, menu_type, path
  FROM sys_menu
  WHERE parent_id = 0 OR menu_id IN (5001,5021,5031,5002,5003,5004,5022,5023,5032,5033)
  ORDER BY IF(parent_id=0, menu_id, parent_id), menu_id"

menu_id  menu_name        parent_id  menu_type  path
1        系统管理         0          M          system               ← ruoyi 自带顶级（不动）
2        系统监控         0          M          monitor              ← ruoyi 自带顶级（不动）
3        系统工具         0          M          tool                 ← ruoyi 自带顶级（不动）
4        PLUS官网         0          M          https://...          ← ruoyi 自带顶级（不动）
5        测试菜单         0          M          demo                 ← ruoyi 自带顶级（不动）
6        租户管理         0          M          tenant               ← ruoyi 自带顶级（不动）
5000     谷子业务         0          M          gz                   ← ADMIN-001 落，本 ticket 不动
5001     C 端用户管理     5000       M          gz-c-user            ← ✅ reparent 0 → 5000
5021     客服配置         5000       C          gz-customer-service  ← ✅ reparent 1 → 5000（修正 SYS-004 错挂）
5031     业务文件管理     5000       C          gz-file              ← ✅ reparent 1 → 5000（修正 SYS-005 错挂）
5002     用户列表         5001       C          list                 ← SYS-003 不动
5003     用户查询         5002       F                               ← SYS-003 不动
5004     用户详情         5002       F                               ← SYS-003 不动
5032     文件列表         5031       F          #                    ← SYS-005 不动
5033     文件上传         5031       F          #                    ← SYS-005 不动
5500     数据看板         0          M          gz-dashboard         ← ✅ 本 ticket 新建顶级
11616    工作流           0          M          workflow             ← ruoyi 自带顶级（不动）
11618    我的任务         0          M          task                 ← ruoyi 自带顶级（不动）
```

业务菜单树视图（人眼可读）：

```
谷子业务 (5000)
├── C 端用户管理 (5001)
│   └── 用户列表 (5002)
│       ├── 用户查询 (5003) [F 按钮]
│       └── 用户详情 (5004) [F 按钮]
├── 客服配置 (5021) [叶子 C 页面]
└── 业务文件管理 (5031)
    ├── 文件列表 (5032) [F 按钮]
    └── 文件上传 (5033) [F 按钮]

数据看板 (5500) [V1.0 空目录，预留 ADMIN-003]
```

### 3. role_menu 关联验证（owner=10 / staff=11）

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "
  SELECT r.role_id, r.role_key, COUNT(rm.menu_id) AS menu_cnt
  FROM sys_role r LEFT JOIN sys_role_menu rm ON rm.role_id = r.role_id
  WHERE r.role_id IN (100, 101)
  GROUP BY r.role_id, r.role_key"

role_id  role_key  menu_cnt
100      owner     10        ← ✅ 期望 = ADMIN-001 BETWEEN 5000-5999（9）+ 5500 兜底（1）= 10
101      staff     11        ← ✅ 期望 = ADMIN-001 5000（1）+ 本 ticket 10（5500/5001-5003/5021/5031/5032 + 2/108/500）= 11

$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "
  SELECT role_id, GROUP_CONCAT(menu_id ORDER BY menu_id) AS menu_ids
  FROM sys_role_menu WHERE role_id IN (100, 101) GROUP BY role_id"

role_id  menu_ids
100      5000,5001,5002,5003,5004,5021,5031,5032,5033,5500
101      2,108,500,5000,5001,5002,5003,5021,5031,5032,5500
```

✅ staff 不含 5004 用户详情、不含 5033 文件上传、不含 1 系统管理 / 3 系统工具 / 6 租户管理（任务卡 AC 2 子集要求满足）。

### 4. plus-ui 编译 + lint

```
$ pnpm build:dev
✓ built in 12.90s
（无 ts 报错，无 vite import 错；仅 chunk-size 警告，ruoyi 默认行为）

$ pnpm lint:eslint src/permission.ts src/components/StoreSelector/index.vue src/lang/zh_CN.ts src/lang/en_US.ts
（无 error 输出 — 本 ticket 新建/纯改动文件 lint 0 错）

$ pnpm lint:eslint src/layout/components/Navbar.vue
✖ 5 problems  ← 全是 ruoyi 原代码已存在的错（line 40 SCSS / 111-112 双引号缺分号 / 293 空行 / 321 SCSS），
                与本 ticket 加的 3 行无关。CLAUDE.md §10「不重构 Kevin 没要求的代码」— 不动
```

### 5. DDL 幂等性（重复跑无错）

```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue \
    < V202605291200__GZ-ADMIN-004-menu-structure.sql
(无 output；UPDATE 已成幂等 - parent_id 已是 5000 再 UPDATE 5000 不报错；INSERT IGNORE 兜底 5500 重复)

$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue \
    < V202605291201__GZ-ADMIN-004-role-menu-mapping.sql
(无 output；全部 INSERT IGNORE 幂等)

$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e \
  "SELECT COUNT(*) FROM sys_role_menu WHERE role_id=101"
COUNT(*) = 11   ← ✅ 仍是 11 条（未重复插）
```

### 6. 是否启过 spring-boot:run

**否**（本 ticket 纯 DDL + 前端配置改动，无 Java 代码改动 — 无需 install + restart；同 wave SYS-006 / ADMIN-002 完工后由主线程统一启 spring-boot:run + spawn kevin-qa Tier 1B 跑 Playwright admin E2E）。

---

## §0 自检表（重复，供 closing 抽取）

- [x] git clean（N/A，未 init git）
- [x] 上游依赖 merge（ADMIN-001 ✅ — sys_menu 5000 / sys_role 100/101 / sys_user.gz_store_id 就位）
- [x] 关键类 / 表 / API 硬探（5001/5021/5031 错挂状态确认、5500 段空闲、ADMIN-001 BETWEEN 批量授权已含 5500）
- [x] 编译通过（plus-ui build:dev ✓ 12.9s）
- [x] 权威蓝图引用完整（PRD M7 admin 基础布局 / 设计冻结期 mockup N/A）
- [x] ADR 已读（doc/_adr/ 空，本 ticket 不到阈值）
- [x] 合同范围（V1.0 §2.1 #5）

---

## 待主线程接力 kevin-qa 验证清单

由于 admin Playwright E2E 需要 spring-boot:run 已启（wave-2 内 ADMIN-002 + SYS-006 同步进行），由主线程在 wave-2 全 ✅ 后统一 spawn kevin-qa 跑：

1. **owner / staff 双角色登录 + sidebar 渲染**：
   - owner 登录 → sidebar 应见：「谷子业务」展开 → C 端用户管理 / 客服配置 / 业务文件管理 三个子项 + 「数据看板」顶级 + ruoyi 自带 5 个顶级（不包含被 ADMIN-001 D5 决策的 staff 子集）
   - staff 登录 → sidebar 应见：「谷子业务」展开 → C 端用户管理（仅"用户列表"页可入）+ 客服配置 + 业务文件管理（仅"文件列表"按钮）+ 「数据看板」+ 「系统监控」→ 日志管理 → 操作日志（一条路径深入）
   - **不应见**：staff 看到 5004 用户详情 / 5033 文件上传 / 系统管理顶级
2. **AC 3 StoreSelector 显示**：
   - owner / staff 登录后顶部 navbar 用户头像左边见 StoreSelector，显示「成都拼豆店」，disabled
   - admin/admin123 ruoyi 兜底账号登录后**不显示** StoreSelector（v-if="!isSuperadmin"）
3. **AC 6 默认跳转**：
   - owner 登录后访问 `/` 或 `/index` → URL 自动跳到 `/system/user`（注意：依赖 ADMIN-002 给 owner 授 ruoyi 系统菜单；若 ADMIN-002 未授，会跳到 401 — 此为 ADMIN-002 任务范围）
   - staff 登录后访问 `/` 或 `/index` → URL 自动跳到 `/gz-c-user/list` ✅
   - 用户主动访问其他页面（如 `/system/dept`）→ 不被重写（仅默认 landing 才重写）
4. **i18n 切换**：
   - 切英语后 sidebar 菜单仍显示「C 端用户管理」中文（sys_menu menu_name 已写死中文）— 这是 ruoyi 范式正常行为，i18n key route.gz.* 是 admin 二次自定义渲染时备用，本 ticket 不强求菜单 i18n 切换效果
5. **AC 4 / 5 面包屑 + 动态侧边栏**：ruoyi 自带行为，本 ticket 不需特殊验证

---

## 上交主线程总结

- **改了哪些文件**：
  - 2 DDL（V202605291200 reparent + 5500 / V202605291201 role-menu mapping）
  - 1 新组件（StoreSelector/index.vue）
  - 4 修改文件（Navbar.vue + permission.ts + zh_CN.ts + en_US.ts）
  - 0 Java / 0 miniapp
- **AI Tier 1A 自测**：
  - DDL × 2 跑通 + 幂等性 ✅
  - 完整菜单树验证（17 条 sys_menu 全部位置正确）✅
  - role_menu 关联数 owner=10 / staff=11 ✅
  - plus-ui build:dev ✓（无 ts 错）
  - 本 ticket 新增/改动文件 lint 0 错 ✅
- **是否启过 spring-boot:run**：否（纯 DDL + 前端，等 wave-2 全 ✅ 后主线程统一启 + spawn kevin-qa Tier 1B）
- **任务卡偏差记录**：
  - menu_id 100/300 → 实际 5000/5500（适配 CLAUDE.md §6 #6 + README §今日特殊约束）
  - StoreSelector 放 `src/components/` 而非任务卡描述的 `views/components/`（plus-ui 不存在 views/components）
- **风险提示给 ADMIN-002**：owner 默认跳转 /system/user 需 ADMIN-002 同步给 owner 授权 ruoyi 自带菜单，否则 401
- **Kevin Tier 2 必要性**：**应跳过**（纯 admin ticket，无 mp 端，无微信原生能力；接力 kevin-qa Tier 1B 跑 Playwright admin E2E 即可 close）

---

## §AI 测试段（kevin-qa Tier 1B，18:55）

### 环境准备

测试前完成以下 dev 配置（生产 prod profile 不受影响）：

1. `application-dev.yml` 末尾新增 `api-decrypt.enabled: false` — spring-boot 不再强制 RSA 解密请求体
2. `plus-ui/.env.development` 改 `VITE_APP_ENCRYPT = false` — 前端不再加密请求体（与后端对齐）
3. spring-boot 重启后两端配置生效；plus-ui dev server 重启后 env 变更生效

**根因记录**：ruoyi 默认 api-decrypt 双端均开，`captcha.enable: false` 不影响加密链路。Playwright E2E 需要干净的纯文本 HTTP 流，两个配置必须同时关闭。已写入 `kevin-qa/learnings.md`。

---

### admin Playwright E2E（13 PASS / 0 FAIL）

```
=== TEST 1: gz_owner login + sidebar + StoreSelector ===
PASS: owner 登录成功: http://localhost/index
PASS: owner 可见「谷子业务」菜单
PASS: owner 可见「数据看板」顶级菜单（5500 落库 + parent_id=0 正确）
PASS: owner 展开「谷子业务」后见「谷子操作日志」（SYS-006 5011 菜单）
PASS: owner 展开后见「C 端用户管理」（SYS-003 5001 reparent 正确）
PASS: StoreSelector 显示「成都拼豆店」（Navbar.vue 挂载 + V1.0 单门店硬编码正确）

=== TEST 2: gz_staff_chengdu login + sidebar ===
PASS: staff 登录成功: http://localhost/index
PASS: staff 不见「系统管理」顶级菜单（role_id=101 未含 1 系统管理 — 正确）
PASS: staff 可见「系统监控」（含 2/108/500 操作日志路径 — D7 决策正确）
PASS: staff 可见「谷子业务」菜单

=== TEST 3: SYS-006 oper-log 页面（owner 菜单点击）===
PASS: oper-log 页通过菜单点击访问成功，table 渲染正常
（路由 /gz/gz-oper-log — 来自 parent_id=5000 path=gz + menu path=gz-oper-log 级联）

=== TEST 4: staff oper-log 权限隔离 ===
PASS: staff 可访问 oper-log 列表页（仅 list 权限）
PASS: staff oper-log 页无「删除」按钮（v-hasPermi="['gz:oper-log:remove']" 正确隐藏）
```

补注：「谷子管理员」DOM 中存在但 `offsetParent === null`（菜单折叠时 ruoyi 行为），实际不可见，不算 bug。

---

### ADMIN-001 补测（wave-1，captcha 关闭后补跑，6 PASS）

```
PASS: owner POST /auth/login 200 token 取得
PASS: staff POST /auth/login 200 token 取得
PASS: owner GET /system/gz/user/list 200（perm gz:user:list 正常）
PASS: staff GET /system/gz/user/list 200（perm gz:user:list 正常）
PASS: Playwright owner /auth/login 200（真实浏览器流程）
PASS: Playwright owner 登录后跳转到: http://localhost/index
```

---

### DB 验证（ADMIN-004 DDL）

```
-- Flyway 已应用 V202605291200 + V202605291201
menu_id=5001 parent_id=5000  C 端用户管理   reparent ✅
menu_id=5021 parent_id=5000  客服配置       reparent ✅（修正 SYS-004 错挂 parent=1）
menu_id=5031 parent_id=5000  业务文件管理   reparent ✅（修正 SYS-005 错挂 parent=1）
menu_id=5500 parent_id=0     数据看板       新建 ✅

role_id=100 (owner)  menu_cnt=14  (ADMIN-001 9条 + ADMIN-004 1条 + SYS-006 4条)
role_id=101 (staff)  menu_cnt=13  (2/108/500/5000/5001/5002/5003/5011/5012/5021/5031/5032/5500)
```

---

### 跳过 / 未跑

- i18n key 中英文切换视觉效果 → 视觉冻结期不评判
- owner 默认路由跳 /system/user 时的 401 → ADMIN-002 待实施后再验（reports/GZ-ADMIN-004.md R1 已记录）
- 面包屑 / 动态侧边栏 → ruoyi 自带行为，本 ticket 无特殊实现，不验
- 未开 mp 端 → 纯 admin ticket，跳过 Tier 2

---

### 结论

**ADMIN-004 Tier 1B 全通过 ✅**，可跳过 Tier 2 直接 close。
- ADMIN-001 波段补测同步通过 ✅。
