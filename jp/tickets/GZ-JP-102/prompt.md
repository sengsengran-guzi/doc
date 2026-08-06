---
ticket: GZ-JP-102
track: PROD
phase: D3
size: M
req_refs: [REQ-PROD-001, REQ-PROD-002, REQ-PROD-003, REQ-PROD-004, REQ-PROD-005, REQ-PROD-006, REQ-PROD-007]
depends_on: [GZ-JP-101]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
  - code/main/plus-ui/src/views/gz-jp/product/**
  - code/main/plus-ui/src/api/gz-jp/**
blueprint_refs:
  - FLOW:F-JP-01.step2
  - FIELD:gz_jp_product.notice_text
  - FIELD:gz_jp_product.price_cent
  - UI:admin.product
accept:
  - name: 建表且公共字段全集齐
    form: DDL
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='ry-vue' AND table_name='gz_jp_product'
        AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
        | grep -qx 7
  - name: 注意事项与包邮价字段就位，且无库存列（一期不做）
    form: DDL
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='ry-vue' AND table_name='gz_jp_product'
        AND column_name IN ('notice_text','price_cent','delivery_date_text','event_id')" | grep -qx 4 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='ry-vue' AND table_name='gz_jp_product'
        AND column_name LIKE 'stock%'" | grep -qx 0
  - name: 菜单 path/component 非空且父级有效（防 404 与错父级）
    form: MENU
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14010 AND 14019 AND m.del_flag='0'
        AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
           OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
           OR (m.parent_id<>0 AND NOT EXISTS
               (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id AND p.del_flag='0')) )" | grep -qx 0 &&
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14010 AND 14019 AND del_flag='0'" | grep -qE '^[1-9]'
---

# GZ-JP-102 商品（gz_jp_product）建表 + admin 商品管理

## §0 状态自检

1. GZ-JP-101 已 merge（场表存在，商品要挂 event_id）。
2. 确认 `gz_file_object` + OSS 上传链路可用（主图/图集走 file id，**禁裸 url**）。

## What

商品建表 + admin CRUD，挂在场下。字段真源见 `field-ssot.yaml` 的 `gz_jp_product`。

**一期明确不做**（都是甲方没提或已砍的）：
- ❌ 库存（集单预订本质不限量，甲方从未提过库存）
- ❌ SKU 多规格（REQ-PROD-007 待澄清；我方判断不同规格各上架一个商品）
- ❌ Excel 导入导出
- ❌ 富文本详情编辑器（详情用图集承载）

**必须做**：`notice_text` 独立字段 —— 甲方原话「有一些额外的注意事项等」，
这是下单前的风险告知位，不能塞进图集或备注。

## AC

- admin 商品管理：按场筛选 / 列表 / 新建 / 编辑 / 批量上下架 / 删除
- 表单含：所属场 / 名称 / 主图 / 图集 / 价格 / 预计到货文本 / **注意事项** / 排序号
- 菜单挂 14010 段
