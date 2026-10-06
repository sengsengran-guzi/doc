"""D8 independent QA. Local 8700 only; never calls a live read transport."""
import concurrent.futures
import hashlib
import hmac
import json
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote
import httpx

ROOT = Path(__file__).resolve().parents[4] / 'code/main/mercari-gateway'
config = {}
for line in (ROOT / '.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        config[key.strip()] = value.strip().strip('"').strip("'")
secret = config['GATEWAY_HMAC_SECRET']
base = 'http://127.0.0.1:8700'
checks = 0

def check(name, ok):
    global checks
    assert ok, name
    checks += 1
    print('PASS', name, flush=True)

def request(path, method='GET', payload=None, auth='valid'):
    body = b'' if payload is None else json.dumps(payload).encode()
    ts = str(int(time.time()) - (120 if auth == 'expired' else 0))
    message = '\n'.join([ts, method, path, hashlib.sha256(body).hexdigest()]).encode()
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    headers = {'X-GW-Ts': ts, 'X-GW-Sign': signature, 'Content-Type': 'application/json'}
    if auth == 'wrong':
        headers['X-GW-Sign'] = '0' * 64
    if auth == 'missing':
        headers = {}
    with httpx.Client(base_url=base, trust_env=False, timeout=65) as client:
        return client.request(method, path, content=body, headers=headers)

health = request('/v1/health')
check('signed health 200 fake', health.status_code == 200 and health.json()['driver'] == 'fake')
check('health accounts/session shape', len(health.json()['accounts']) > 0 and all(a['session'] == 'ok' for a in health.json()['accounts']))
check('health no credentials', all(w not in health.text.lower() for w in ('password', 'cookie', 'token', 'secret', 'proxy')) and secret not in health.text)
for auth in ('wrong', 'expired', 'missing'):
    r = request('/v1/health', auth=auth)
    check(auth + ' auth 401 body', r.status_code == 401 and r.json()['code'] == 'unauthorized')
r = request('/v1/img/https://evil.test/a.png', auth='missing')
check('unsigned outside image 403', r.status_code == 403 and r.json()['code'] == 'forbidden_url')
r = request('/v1/img/item/synthetic.png', auth='missing')
check('unsigned image bytes/cache', r.status_code == 200 and r.content.startswith(b'\x89PNG') and r.headers['cache-control'] == 'public, max-age=31536000, immutable')
r = request('/v1/search?q=' + quote('缶バッジ'))
check('search nonempty sale only', r.status_code == 200 and bool(r.json()['items']) and all(i['status'] == 'on_sale' for i in r.json()['items']))
check('search retains Shops for downstream filtering', any(i['item_type'] == 'shops' for i in r.json()['items']))
for ident, payer in [('m99000000001', 'seller'), ('m99000000002', 'buyer')]:
    r = request('/v1/items/' + ident)
    check(ident + ' details/shipping', r.status_code == 200 and r.json()['shipping_payer'] == payer and all(k in r.json() for k in ('description_ja','condition_text','category_id','seller_id','image_urls')))
r = request('/v1/sellers/99000004')
check('seller intro present', r.status_code == 200 and bool(r.json()['intro']))
time.sleep(1.1)
r = request('/v1/resolve?url=' + quote('https://merc.li/SYNTHETIC01', safe=''))
# Read the actual recorded mapping; do not invent a real platform link.
mapping = json.loads((ROOT / 'fixtures/replay/resolve.json').read_text())
link, ident = next(iter(mapping.items()))
r = request('/v1/resolve?url=' + quote(link, safe=''))
check('synthetic recorded resolve', r.status_code == 200 and r.json()['external_id'] == ident)
r = request('/v1/resolve?url=' + quote('https://evil.test/x', safe=''))
check('outside resolve 403', r.status_code == 403)
r = request('/v1/items/m99999999999')
check('missing item 404 deleted', r.status_code == 404 and r.json()['status'] == 'deleted')
r = request('/v1/search?q=QA_UNRECORDED_EMPTY')
check('empty search deterministic', r.status_code == 200 and r.json()['items'] == [])

# Use independent actual HTTP connections, three rounds, then query the persistent ledger.
account = health.json()['accounts'][0]['account_code']
for round_no in range(1, 4):
    order = f'QA-D8-r1-{round_no}'
    payload = {'order_no':order, 'external_id':f'mQAD8r1{round_no}', 'max_price_jpy':777,
               'expect_shipping_payer':'seller', 'account_code':account}
    barrier = threading.Barrier(2)
    def purchase():
        barrier.wait()
        return request('/v1/purchases', 'POST', payload)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(purchase) for _ in range(2)]
        responses = [f.result() for f in futures]
    check(f'concurrency round {round_no} safe results', all(r.status_code == 200 and r.json()['result'] in ('success','unknown') for r in responses) and any(r.json()['result'] == 'success' for r in responses))
    first = next(r.json() for r in responses if r.json()['result'] == 'success')
    repeat = request('/v1/purchases', 'POST', payload)
    check(f'round {round_no} repeat identical first result', repeat.status_code == 200 and repeat.json() == first)
    rows = request('/v1/_fake/ledger?order_no=' + order).json()['orders']
    check(f'round {round_no} one persistent click', len(rows) == 1 and rows[0]['click_count'] == 1 and rows[0]['call_count'] == 1)

# Reuse a single connection so the burst exceeds the actual global bucket capacity.
time.sleep(1.1)
statuses = []
with httpx.Client(base_url=base, trust_env=False) as client:
    for _ in range(40):
        statuses.append(client.get('/v1/img/item/synthetic.png').status_code)
check('actual burst 429', 200 in statuses and 429 in statuses and set(statuses) <= {200,429})
time.sleep(1.1)
check('actual bucket cooldown recovers', request('/v1/img/item/synthetic.png', auth='missing').status_code == 200)
print('HTTP status burst', {s:statuses.count(s) for s in set(statuses)})
print('COUNTS local HTTP checks', checks)
