import asyncio, time
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page(locale='ja-JP')
        t = time.perf_counter()
        await pg.goto('https://jp.mercari.com/search?keyword=%E3%83%96%E3%83%AB%E3%83%BC%E3%83%AD%E3%83%83%E3%82%AF%20%E7%BC%B6%E3%83%90%E3%83%83%E3%82%B8&status=on_sale', wait_until='domcontentloaded')
        try:
            await pg.wait_for_selector('[data-testid="item-cell"]', timeout=20000)
            cells = await pg.locator('[data-testid="item-cell"]').count()
            print(f"[headless search page] {time.perf_counter()-t:.2f}s item_cells={cells}")
        except Exception as e:
            print(f"[headless search page] no item cells after {time.perf_counter()-t:.2f}s: {type(e).__name__}")
        print("title:", await pg.title())
        await pg.screenshot(path='search.png')
        t = time.perf_counter()
        await pg.goto('https://jp.mercari.com/item/m47053605018', wait_until='domcontentloaded')
        try:
            await pg.wait_for_selector('[data-testid="checkout-button"], [data-testid="price"]', timeout=20000)
            btn = await pg.locator('[data-testid="checkout-button"]').count()
            print(f"[headless item page] {time.perf_counter()-t:.2f}s checkout_button={btn}")
        except Exception as e:
            print(f"[headless item page] selector miss after {time.perf_counter()-t:.2f}s: {type(e).__name__}")
        await pg.screenshot(path='item.png')
        await b.close()
asyncio.run(main())
