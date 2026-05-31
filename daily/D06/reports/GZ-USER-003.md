# GZ-USER-003 完工报告 — mp 地址簿 CRUD

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅ 改动隔离于 gz-user 后端 + me/address + AddressCard + user.zh-CN |
| 上游依赖 merge | ✅ GZ-SYS-002(D02 登录) 已就位 |
| 关键类/表存在 | ✅ gz_user_address 本 ticket 落 DDL；gz_user 表已存在（FK 引用） |
| 编译通过 | ✅ mvn install BUILD SUCCESS；type-check 零新增；build 绿 |
| ADR 已读 | 无相关 ADR |

**权威蓝图引用摘录**：
- doc/10 §4.N3-N7：地址簿 list/新增/编辑/软删/设默认；默认地址状态机（旧默认自动取消）
- doc/11 §2.2 gz_user_address：完整字段 + 索引 idx_tenant_user / idx_tenant_user_default + 业务规则（单用户≤20，默认≤1 业务层兜底）

**关键决策（R2 — 省市区联动零新依赖）**：
- mp 端用 **uni-app 原生 `<picker mode="region">`**（自带全国省市区数据）→ **不引** wot-design-uni 城市集 / area-data（CLAUDE.md §6 #8 不引未澄清依赖；R2 直接缓解，无需报 Kevin 决策）。
- 默认地址唯一性：业务层事务兜底（resetOthersDefault 先把该用户其他 is_default=0 再 set 目标=1），**不依赖 DB 偏函数索引**（doc/11 §2.2 + 任务卡 D1）。
- 越权防护：所有写操作先校验 address.userId == 当前 userId（防改他人地址）。
- 软删（del_flag='2'，@TableLogic）+ list 自动过滤。

## 实现摘要

后端新增（org.dromara.gz.user）：
- `domain/entity/GzUserAddress.java` + `domain/vo/GzUserAddressVO.java`（id 加 ToStringSerializer）+ `domain/bo/GzUserAddressBo.java`（收件人/手机号 regex/省市区/详情校验）
- `mapper/GzUserAddressMapper.java`
- `service/IGzUserAddressService.java` + `service/impl/GzUserAddressServiceImpl.java`
- `controller/applet/GzUserAddressMpController.java`（GET /list, GET /{id}, POST, PUT, DELETE /{id}, POST /{id}/default）
- DDL `V202606031100__GZ-USER-003-create-gz_user_address.sql`

mp 新增：
- `pages/me/address/list.vue`（列表默认置顶 + 空态 + 删除二次确认 + 设默认）
- `pages/me/address/edit.vue`（收件人/手机号/region picker/详情/标签/默认 switch/智能粘贴）
- `components/biz/AddressCard.vue`
- `api/gz-user.ts` 加 getAddressList/getAddress/saveAddress/deleteAddress/setDefaultAddress + UserAddressVO/UserAddressSaveRequest

## AI 自测

### 编译 + install
```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-user -am -q
BUILD SUCCESS
```

### 单测（GzUserAddressServiceImplTest，含 TableInfoHelper 初始化）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
[INFO] Running org.dromara.gz.user.service.impl.GzUserAddressServiceImplTest
[INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0
   - 新建默认地址 → reset 其他(update null+wrapper) + insert
   - 新建非默认 → 不 reset
   - 编辑/设默认/软删他人地址 → ServiceException（越权防护）
   - 切换默认 → reset 其他 + set 当前
   - 软删本人 → deleteById
   - getByIdForUser 他人 → null（不暴露存在性）
[INFO] BUILD SUCCESS
```
> 注：纯 mock 单测下 LambdaUpdateWrapper.eq(GzUserAddress::getXxx) 需 mybatis-plus TableInfo 缓存，
> @BeforeAll 用最小 Configuration 注册一次（不连库）。

### DB 验证（dev MySQL 在线，手工导入）
```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606031100__...address.sql
$ SHOW INDEX FROM gz_user_address;
PRIMARY(id) / idx_tenant_user(tenant_id,user_id) / idx_tenant_user_default(tenant_id,user_id,is_default) ✅
$ SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_NAME='gz_user_address';
tenant_id DEFAULT '1001' / del_flag DEFAULT '0' / is_default DEFAULT 0 ✅
```

### API 烟雾（后端未在线，curl 备用，待全栈起来验）
```bash
# 新建默认地址 → 200，再建另一条默认 → 上一条 is_default 自动置 0
curl -X POST http://localhost:8080/app/gz/user/address \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"recipientName":"张三","mobile":"13800138000","province":"四川省","city":"成都市","district":"锦江区","detail":"春熙路1号","isDefault":1}'
```

## 风险提示 / 已知 issue

- 智能粘贴（AC 6）：uni.chooseAddress 在部分基础库/未配置时不可用 → 降级 toast「请手动填写」（doc/12 §7 D9 妥协方案，已处理）。
- R1（region picker 编码）：uni 原生 region picker 只返中文文本（province/city/district），不返国标编码。V1.0 仅收集展示足够；V1.1 真实下单调微信寄送如需编码 → 评估补编码字段（不 break 现有 schema，加可选列）。
- R2（设默认并发）：业务层事务 reset+set；V1.0 并发量小可接受（未加 SELECT FOR UPDATE 行锁，doc/11 §2.2 业务量评估后可接受）。
- 待 Kevin 批量人验关注（mp）：① 新建/编辑/删除地址 ② 省市区 picker 联动 ③ 设默认后旧默认自动取消（默认唯一）④ 删除二次确认 ⑤ 空态占位。

## 对下游 ticket 的提示

- DDL 需 Kevin 手工跑：`V202606031100__GZ-USER-003-create-gz_user_address.sql`（dev 已导入验证）。
- V1.1 预定下单（GZ-ORD）引用地址：用 GzUserAddressVO，地址软删保证历史引用不断（del_flag）。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ kevin-qa 无法 spawn（subagent 内 Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。主线程可决定是否补派复核。

### 后端单测
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
GzUserAddressServiceImplTest: Tests run: 9, Failures: 0, Errors: 0 ✅
（覆盖新建默认/切换默认/软删/越权防护，默认地址唯一性事务兜底）
BUILD SUCCESS
```

### API 契约回归（mp ↔ 后端 6 端点全核对）
```
GET /address/list ↔ @GetMapping("/list") ✅
GET /address/{id} ↔ @GetMapping("/{id}") ✅
POST/PUT /address ↔ @PostMapping + @PutMapping ✅
DELETE /address/{id} ↔ @DeleteMapping("/{id}") ✅
POST /address/{id}/default ↔ @PostMapping("/{id}/default") ✅
```

### mp vitest + type-check
```
vitest 全量 103 passed；type-check 零新增 TS 错
省市区联动用 uni 原生 region picker（零新依赖，R2 已解）
```

### Tier 2 可达性
```
会员中心九宫格「地址簿」→ /pages/me/address/list（USER-001 ROUTE_MAP 已配）→ 从已上线 tab 可达
```

**Tier 1B 结论：USER-003 ✅**（后端单测 9/9 + 契约 6 端点对齐 + DDL 已导入验证 + 可达性全绿）
