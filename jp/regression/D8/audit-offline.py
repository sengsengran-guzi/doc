"""Evidence audit and real monotonic cooldown, using injected offline transports."""
import asyncio
import json
import sys
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[4] / 'code/main/mercari-gateway'
sys.path.insert(0, str(ROOT))
from app.read_sources.live import LiveReadSource
from app.read_sources.parsing import parse_item, parse_search, parse_html
fixture = ROOT / 'fixtures/replay'
count = 0
def check(name, ok):
    global count
    assert ok, name
    count += 1
    print('PASS', name)
budget = json.loads((fixture / 'live-budget.json').read_text())
check('live one run request count matches transport entries <=5', len(budget['runs']) == 1 and all(r['result'] == 'pass' and r['request_count'] == len(r['requests']) <= 5 for r in budget['runs']))
check('live only anonymous search and detail transport', [(r['method'],r['host'],r['path']) for r in budget['runs'][0]['requests']] == [('POST','api.mercari.jp','/v2/entities:search'),('GET','api.mercari.jp','/items/get')])
search = parse_search(json.loads((fixture/'raw/real-search.json').read_text()))
item = parse_item(json.loads((fixture/'raw/real-item.json').read_text()))
check('real JSON subset sale and shipping/category', len(search['items']) == 3 and all(r['status']=='on_sale' for r in search['items']) and item['external_id']==budget['runs'][0]['item_id'] and item['shipping_payer']=='seller' and item['category_id']=='980')
manifest = json.loads((fixture/'provenance.json').read_text())
html_rows = [s for s in manifest['samples'] if 'html' in s]
check('11 HTML samples explicitly synthetic', len(html_rows)==11 and all(s['source']=='synthetic' for s in html_rows))
check('real source count exactly two', len([s for s in manifest['samples'] if s['source']=='real_anonymized_subset'])==2)
for s in manifest['samples']:
    for k in ('json','html','seller','path'):
        if k in s:
            assert (fixture/s[k]).is_file(), (s,k)
check('all provenance references exist', True)

class Api:
    calls = 0
    healthy = False
    async def item(self, ident):
        self.calls += 1
        if not self.healthy:
            raise httpx.ConnectError('offline QA error')
        return json.loads((fixture/'raw/auto.json').read_text())
class Browser:
    calls = 0
    async def read(self, kind, ident):
        self.calls += 1
        return parse_html((fixture/'raw/auto.html').read_text(), kind)
async def run():
    api, browser = Api(), Browser()
    source = LiveReadSource(api=api,browser=browser,recovery_seconds=.1)
    check('first API error falls back to browser', (await source.item('m99000000001'))['via']=='browser')
    check('second error opens circuit', (await source.item('m99000000001'))['via']=='browser' and source.failures==2)
    api.healthy=True
    check('cooldown skips recovered API until elapsed', (await source.item('m99000000001'))['via']=='browser' and api.calls==2)
    await asyncio.sleep(.15)
    check('real monotonic cooldown recovery', (await source.item('m99000000001'))['via']=='api' and api.calls==3 and source.failures==0 and source.egress_ok())
asyncio.run(run())
print('COUNTS independent offline checks', count)
