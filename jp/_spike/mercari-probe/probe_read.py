"""只读探测煤炉数据：原始 JSON 落盘 + 摘要。请求预算硬上限 10 次，每次间隔 3 秒。"""
import asyncio, json, os, time
from collections import Counter
from urllib.parse import urlparse
from mercapi import Mercapi
from mercapi.requests import SearchRequestData

OUT = os.path.join(os.path.dirname(__file__), "probe-out")
os.makedirs(OUT, exist_ok=True)
BUDGET = 10
used = 0


async def send(m, req, name):
    global used
    if used >= BUDGET:
        raise RuntimeError("request budget exhausted")
    used += 1
    t = time.perf_counter()
    res = await m._client.send(req)
    dt = time.perf_counter() - t
    body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {"_raw": res.text[:500]}
    with open(os.path.join(OUT, f"{used:02d}-{name}.json"), "w") as f:
        json.dump(body, f, ensure_ascii=False, indent=1)
    print(f"[{used}] {name}: HTTP {res.status_code} {dt:.2f}s")
    await asyncio.sleep(3)
    return res.status_code, body


def search_req(m, q, shipping_payer=None):
    data = SearchRequestData(SearchRequestData.SearchConditions(
        q, [], [], [], 0, 0, [], shipping_payer or [], [], [],
        [SearchRequestData.Status.STATUS_ON_SALE],
        SearchRequestData.SortBy.SORT_CREATED_TIME, SearchRequestData.SortOrder.ORDER_DESC, None), None)
    return m._search(data)


def summarize_search(body, label):
    items = body.get("items", [])
    print(f"  {label}: items={len(items)} total={body.get('meta', {}).get('numFound')}")
    if items:
        print("  item keys:", sorted(items[0].keys()))
    print("  itemType:", Counter(i.get("itemType") for i in items))
    print("  status:", Counter(i.get("status") for i in items))
    print("  shippingPayerId:", Counter(i.get("shippingPayerId") for i in items))
    print("  categoryId sample:", Counter(i.get("categoryId") for i in items).most_common(5))
    hosts = Counter(urlparse(t).netloc for i in items for t in (i.get("thumbnails") or [])[:1])
    print("  thumb hosts:", hosts)
    return items


def summarize_item(body, label):
    d = body.get("data", {})
    print(f"  {label}: id={d.get('id')} status={d.get('status')} price={d.get('price')}")
    print("   shipping_payer:", d.get("shipping_payer"))
    print("   item_category:", {k: d.get("item_category", {}).get(k) for k in ("id", "name", "parent_category_id", "parent_category_name", "root_category_id", "root_category_name")})
    print("   item_condition:", d.get("item_condition"))
    print("   seller:", {k: (d.get("seller") or {}).get(k) for k in ("id", "name")})
    photos = d.get("photos") or []
    print("   photo hosts:", Counter(urlparse(p).netloc for p in photos), "count", len(photos))
    desc = d.get("description") or ""
    print("   desc head:", repr(desc[:80]))
    print("   top-level keys:", sorted(d.keys()))


async def main():
    m = Mercapi()
    # 1 普通搜索（按新上架）：看字段、itemType、运费、分类、图片域名
    _, b = await send(m, search_req(m, "ブルーロック 缶バッジ"), "search-bluelock")
    items = summarize_search(b, "search")
    c2c = [i for i in items if i.get("itemType") == "ITEM_TYPE_MERCARI"]
    shops = [i for i in items if i.get("itemType") != "ITEM_TYPE_MERCARI"]
    # 2 个人卖家详情
    if c2c:
        _, d = await send(m, m._item(c2c[0]["id"]), "item-c2c")
        summarize_item(d, "c2c detail")
    # 3 Shops：若首屏没有就换一个更可能出 Shops 的词
    if not shops:
        _, b2 = await send(m, search_req(m, "ブルーロック 缶バッジ 新品 公式"), "search-shops-try")
        it2 = summarize_search(b2, "search2")
        shops = [i for i in it2 if i.get("itemType") != "ITEM_TYPE_MERCARI"]
    if shops:
        s = shops[0]
        print("  shops sample:", {k: s.get(k) for k in ("id", "itemType", "name", "price", "shopName")})
        code, d = await send(m, m._item(s["id"]), "item-shops-via-items-get")
        print("   items/get on shops id ->", code, str(d)[:200])
    # 4 到付：按运费负担=購入者 过滤（facet id 先试 1 / 2 看哪个是到付）
    for payer in (2,):
        _, b3 = await send(m, search_req(m, "缶バッジ", [payer]), f"search-payer-{payer}")
        it3 = summarize_search(b3, f"payer={payer}")
        if it3:
            _, d = await send(m, m._item(it3[0]["id"]), f"item-payer-{payer}")
            summarize_item(d, f"payer={payer} detail")
    # 5 要求留言：描述里带「コメント必須」
    _, b4 = await send(m, search_req(m, "コメント必須 缶バッジ"), "search-comment")
    it4 = summarize_search(b4, "comment")
    if it4:
        _, d = await send(m, m._item(it4[0]["id"]), "item-comment")
        summarize_item(d, "comment detail")
    print(f"total requests used: {used}")


if __name__ == "__main__":
    asyncio.run(main())
