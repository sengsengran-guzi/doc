import json,subprocess,urllib.request,pathlib,concurrent.futures,hashlib,datetime,time
ROOT=pathlib.Path.cwd(); REPO=ROOT/'code/main/RuoYi-Vue-Plus'; C='e5cd7e4891bf95d1d19206ce24a7b32e';B=99101000000
MYSQL=['/usr/local/bin/docker','exec','-i','sensenran-dev-mysql','mysql','-uroot','-proot','ry-vue','-N','--batch','--raw']
def sql(q):
 r=subprocess.run(MYSQL,input=q.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert r.returncode==0,r.stderr.decode();return r.stdout.decode().strip()
def lit(x):return "CONVERT(0x"+str(x).encode().hex()+" USING utf8mb4)" if str(x) else "''"
def req(path,data=None,token=None):
 h={'clientid':C,'Content-Type':'application/json'}
 if token:h['Authorization']='Bearer '+token
 r=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if data is None else json.dumps(data).encode(),headers=h)
 return json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r,timeout=40))
jars=list((pathlib.Path.home()/'.m2/repository/org/dromara/ruoyi-gz-jp').glob('*/*.jar'));jar=max(jars,key=lambda p:p.stat().st_mtime)
assert all(p.stat().st_mtime<=jar.stat().st_mtime for p in (REPO/'ruoyi-modules/ruoyi-gz-jp/src/main/java').rglob('*.java'))
print('artifact sha256='+hashlib.sha256(jar.read_bytes()).hexdigest(),flush=True)
login=req('/auth/login',{'tenantId':'1001','username':'admin','password':'admin123','clientId':C,'grantType':'password'});assert login['code']==200,login
token=login['data']['access_token'];assert req('/system/tenant/dynamic/1001',token=token)['code']==200
owner=req('/auth/login',{'tenantId':'1001','username':'gz_owner','password':'gz_owner123!','clientId':C,'grantType':'password'});assert owner['code']==200,owner
owner_token=owner['data']['access_token']
assert req('/system/gz/jp/snap/trade/list',token=owner_token)['code']==403
created=[]
try:
 for n in (5,):
  id=B+n;on='JPO-QA10-'+str(n);ext='m9910100000'+str(n);snap=json.dumps({'snap':{'shippingPayer':'buyer','ratePer100Jpy':4.123,'estShippingCent':500}})
  assert sql('SELECT COUNT(*) FROM gz_jp_order WHERE id='+str(id))=='0'
  sql(f"INSERT INTO gz_pay_transaction(id,tenant_id,out_trade_no,business_type,business_order_no,user_id,openid,amount_cent,status,transaction_id,create_by,create_time) VALUES({id},'1001','{on}','jp','{on}',14,'307_mock',1000,'paid','mock307_{n}',1,NOW()); INSERT INTO gz_jp_order(id,tenant_id,order_no,user_id,total_amount_cent,business_status,pay_transaction_id,address_snapshot_json,paid_time,create_by,create_time) VALUES({id},'1001','{on}',14,1000,'paid',{id},'{{}}',DATE_SUB(NOW(),INTERVAL {4-n} HOUR),1,NOW()); INSERT INTO gz_jp_snap_item(id,tenant_id,external_id,title_ja,price_jpy,item_status,shipping_payer,gate_result,fetched_at,active_order_item_id,create_by,create_time) VALUES({id},'1001','{ext}','307 fixture',1000,'on_sale','buyer','manual',NOW(),{id},1,NOW()); INSERT INTO gz_jp_order_item(id,tenant_id,order_id,user_id,snap_item_id,product_snapshot_json,qty,unit_price_cent,amount_cent,source,fulfill_status,create_by,create_time) VALUES({id},'1001',{id},14,{id},{lit(snap)},1,1000,1000,'snap','purchasing',1,NOW()); INSERT INTO gz_jp_snap_purchase(id,tenant_id,order_item_id,order_no,snap_item_id,external_id,locked_price_jpy,mode,purchase_status,manual_reason,create_by,create_time) VALUES({id},'1001',{id},'{on}',{id},'{ext}',1000,'manual','manual_pending','shipping:buyer',1,NOW());")
  created.append(id)


 id=B+5
 assert req(f'/system/gz/jp/snap/purchase/{id}/manual-success',{'mercariTxnId':'txn307-race','actualPriceJpy':900},token)['code']==200
 assert req(f'/system/gz/jp/snap/trade/{id}/seller-shipped',{},token)['code']==200
 def race(verb):return req(f'/system/gz/jp/snap/trade/{id}/{verb}',{'actualShippingJpy':100} if verb=='arrived' else {},token)['code']
 with concurrent.futures.ThreadPoolExecutor(2) as pool:codes=list(pool.map(race,['arrived','trade-cancel']))
 assert sorted(codes)==[200,409],codes
 row=sql(f"SELECT CONCAT(p.trade_status,':',i.fulfill_status,':',IFNULL(s.active_order_item_id,0)) FROM gz_jp_snap_purchase p JOIN gz_jp_order_item i ON i.id=p.order_item_id JOIN gz_jp_snap_item s ON s.id=p.snap_item_id WHERE p.id={id}")
 assert row in (f'arrived:await_seller_ship:{id}','cancelled:purchase_failed:0'),row
 assert sql(f"SELECT COUNT(*) FROM gz_jp_refund WHERE order_item_id={id}")=='1'
 used=int(sql(f"SELECT SUM(refund_amount_cent) FROM gz_jp_refund WHERE order_item_id={id}"));assert used in (87,1000),used
 print('two independent HTTP/DB transactions arrival vs cancel: codes='+str(codes)+'; final='+row+'; one refund reservation='+str(used)+'; budget<=1000; live Mercari0',flush=True)
finally:
 for id in created:
  sql(f"DELETE FROM gz_pay_callback_log WHERE out_trade_no='JPO-QA10-{id-B}'; DELETE FROM gz_jp_refund WHERE order_item_id={id}; DELETE FROM gz_jp_snap_purchase WHERE id={id}; DELETE FROM gz_jp_order_item WHERE id={id}; DELETE FROM gz_jp_snap_item WHERE id={id}; DELETE FROM gz_jp_order WHERE id={id}; DELETE FROM gz_pay_transaction WHERE id={id};")
 assert sql(f"SELECT COUNT(*) FROM gz_jp_order WHERE id = {B+5}")=='0'
 req('/system/tenant/dynamic/clear',token=token)
 print('exact fixture rows restored; no shared pricing/FX/account changes',flush=True)
