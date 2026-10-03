import asyncio, time
from mercapi import Mercapi
async def main():
    m = Mercapi()
    for kw in ['呪術廻戦 アクリルスタンド', 'ブルーロック 缶バッジ']:
        t = time.perf_counter(); r = await m.search(kw); print(f"[search] {kw}: {time.perf_counter()-t:.2f}s hits={r.meta.num_found} items={len(r.items)}")
        await asyncio.sleep(2)
asyncio.run(main())
