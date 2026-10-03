import asyncio, time
from mercapi import Mercapi

async def main():
    m = Mercapi()
    t = time.perf_counter()
    res = await m.search('ブルーロック 缶バッジ')
    dt = time.perf_counter() - t
    print(f"[search] {dt:.2f}s  total_hits={res.meta.num_found}  page_items={len(res.items)}")
    for it in res.items[:5]:
        print(f"  {it.id_} | {it.price}円 | status={it.status} | {it.name[:40]}")
    first = res.items[0]
    t = time.perf_counter()
    d = await first.full_item()
    dt = time.perf_counter() - t
    print(f"[item] {dt:.2f}s  id={d.id_} price={d.price} status={d.status}")
    print(f"  shipping_payer={getattr(d.shipping_payer,'name',d.shipping_payer)}  condition={getattr(d.item_condition,'name',None)}")
    print(f"  seller={getattr(d.seller,'name',None)}  photos={len(d.photos or [])}  first_photo={(d.photos or [''])[0]}")
    print(f"  desc_head={ (d.description or '')[:60]!r}")

asyncio.run(main())
