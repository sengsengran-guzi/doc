---
ticket: GZ-SNAP-302
track: SNAP
phase: D9
size: L
req_refs: [REQ-SNAP-012, REQ-SNAP-013, REQ-SNAP-014, REQ-SNAP-015, REQ-SNAP-016, REQ-SNAP-019, REQ-SNAP-040, REQ-SNAP-047]
depends_on: [GZ-SNAP-301, GZ-SNAP-202]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application.yml
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application-dev.yml
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application-prod.yml
blueprint_refs:
  - FLOW:F-JP-05.step1
  - FLOW:F-JP-05.step2
  - FLOW:F-JP-05.step3
  - FLOW:F-JP-05.step4
  - FLOW:F-JP-05.step5
  - FIELD:gz_jp_snap_term.zh_term
  - FIELD:gz_jp_snap_term.sort_no
  - FIELD:gz_jp_snap_item.title_zh
  - FIELD:gz_jp_snap_item.fetched_at
  - OWN:mercari_item_live
  - OWN:snap_runtime_config
accept:
  - name: 归一化：链接 / 裸 ID 直达、词表最长匹配、机翻失败降级原词
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapNormalizeTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapNormalizeTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapNormalizeTest.xml
    counterfeit: 词表按首个命中而非最长匹配（「蓝色监狱」被「蓝色」截走）、merc.li 短链被当关键词去搜、或机翻抛错时整个搜索 500 → 红
  - name: 过滤在 ruoyi 侧：Shops 商品 / 白名单外 / 命中黑名单的商品搜索不出、详情直开也拒；白名单为空=全拒
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapFilterTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapFilterTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapFilterTest.xml
    counterfeit: 只在搜索列表过滤、详情接口不过滤（贴链接可绕过黑名单），Shops 商品混进结果，或白名单为空时放行全部 → 红
  - name: 日本服务不可用时搜索返回最近缓存或明确错误码，不 500
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapSearchDegradeTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapSearchDegradeTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapSearchDegradeTest.xml
    counterfeit: gateway 超时直接冒泡成 500、缓存命中时仍去打日本服务（同查询串并发 10 次触发 10 次调用）、或同一 IP 超限后仍打日本服务 → 红
---

# GZ-SNAP-302 ruoyi 代切找货：搜索 / 详情 API + 归一化 + 翻译 + 过滤 + 出图

## §0 状态自检

1. GZ-SNAP-301 / 202 完工；本地日本服务以 `replay + fake` 起（默认），能从回放样本搜到商品。**开发与测试不打真煤炉**。
2. **阿里云机器翻译**是 Kevin 已批准的新外部服务（REQ-SNAP-015）。SDK 用官方 `com.aliyun:alimt20181012`；
   引入前在 ruoyi 已有依赖里确认没有更合适的现成封装。AccessKey 走环境变量，不进 git。
   翻译做成可切换实现 `gz.jp.snap.translate.provider = aliyun | mock`：dev / test 用 mock（确定性输出，如原文前加「[译]」，
   对少量固定词给固定译文），staging / prod 用 aliyun。dev 没有 AccessKey 不能成为阻塞。
3. 读 `FLOW:F-JP-05` 全部五步与 OWN:snap_runtime_config（过滤只在 ruoyi 执行、不信任日本服务）。
4. 读 GZ-SNAP-202 产出的 `mercari-gateway/README.md` 里的动漫周边分类 ID 列表。

## What

mp 接口（`/app/gz/jp/snap`，匿名可访问，游客可搜）：

1. `GET /search?q=&sort=&page=` —— 归一化 → 调 gateway 搜索（带 `category_ids` = 分类白名单，让煤炉按层级收窄）→ 过滤 → 首屏标题批量机翻 → 图片改写 CDN → 返回卡片列表。
   - 归一化：识别 `jp.mercari.com/item/m\d+`、裸 `m\d+`、App 分享短链 `merc.li/…`（调日本服务 `GET /v1/resolve` 解析）→ 返回 `{redirectItemId}` 让前端直跳详情；
     粘贴 Shops 链接（`jp.mercari.com/shops/product/…`）→ 业务码 `SNAP_SHOPS_UNSUPPORTED`（前端提示「暂不支持煤炉 Shops 商品」，REQ-SNAP-047）；
     中文按词表最长匹配替换，未覆盖部分走机翻（Redis 缓存 7 天）；机翻失败降级原词。
   - Redis 缓存 3 分钟（key = 归一化后的查询串 + sort + page）+ 同 key 在途请求合并（单飞）。
   - **限流**：搜索与详情按用户限流（未登录按 IP），用 ruoyi 已有的 `@RateLimiter`；超限返回业务码 `SNAP_TOO_FAST`，不打日本服务（纸面推演 P11）。
   - 日本服务不可用 → 有缓存给缓存（标 `stale=true`）、无缓存返回业务错误码 `SNAP_UPSTREAM_DOWN`（前端显示「煤炉暂时访问不了」）。
   - 列表卡片价格字段：人民币价由 GZ-SNAP-303 的报价器给「参考价」（不锁价）；本卡先留字段，303 接上。
2. `GET /item/{externalId}` —— 实时查一次（不走缓存）→ upsert `gz_jp_snap_item`（含 `fetched_at` / `raw_json` / 机翻 `title_zh`）→ 过滤判定（分类按详情的末级 / 父级 / 根任一在白名单即通过）→ 返回详情（描述机翻、日文原文都给）。准入与报价由 303 叠加。
3. `GET /hot-terms` —— 词表 `term_type=ip`、`enabled=1`，按 `sort_no` 前 12 条（煤炉 tab 空态 chips）。

admin 接口：`POST /system/gz/jp/snap/term/normalize` —— 输入中文串返回替换后的日文查询串（词表页「试一试」用）。

其余：
- 标题机翻缓存键 = `external_id + 标题 hash`，标题变了才重翻。
- 图片 URL 改写：`https://<cdn 域名>/v1/img/<原路径>`，CDN 域名走配置（甲方行政项，未到位前 dev 指向日本服务地址）。
- 新迁移把动漫周边分类 ID 初值写入 `gz.jp.snap.filter.categoryWhitelist`（UPDATE 1001 租户那一行；时间戳取当下）。
  白名单可配任意层级，初值优先用父级（如 745 キャラクターグッズ），少配末级——实测见 `_spike/mercari-probe/READ-PROBE-2026-10-03.md`。

## AC

- 三条 accept 绿。
- 不在白名单 / 命中黑名单 / 非在售的商品：搜索结果里没有；详情接口返回明确的不可购买原因（不是 404 也不是 500）。
- 匿名可搜可看详情；接口响应不含卖家个人信息以外的多余原始字段（raw_json 只存库不下发）。
