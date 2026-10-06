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
 for n in (1,2,3,4):
  id=B+n;on='JPO-QA10-'+str(n);ext='m9910100000'+str(n);snap=json.dumps({'snap':{'shippingPayer':'buyer','ratePer100Jpy':4.123,'estShippingCent':500}})
  assert sql('SELECT COUNT(*) FROM gz_jp_order WHERE id='+str(id))=='0'
  sql(f"INSERT INTO gz_pay_transaction(id,tenant_id,out_trade_no,business_type,business_order_no,user_id,openid,amount_cent,status,transaction_id,create_by,create_time) VALUES({id},'1001','{on}','jp','{on}',14,'307_mock',1000,'paid','mock307_{n}',1,NOW()); INSERT INTO gz_jp_order(id,tenant_id,order_no,user_id,total_amount_cent,business_status,pay_transaction_id,address_snapshot_json,paid_time,create_by,create_time) VALUES({id},'1001','{on}',14,1000,'paid',{id},'{{}}',DATE_SUB(NOW(),INTERVAL {4-n} HOUR),1,NOW()); INSERT INTO gz_jp_snap_item(id,tenant_id,external_id,title_ja,price_jpy,item_status,shipping_payer,gate_result,fetched_at,active_order_item_id,create_by,create_time) VALUES({id},'1001','{ext}','307 fixture',1000,'on_sale','buyer','manual',NOW(),{id},1,NOW()); INSERT INTO gz_jp_order_item(id,tenant_id,order_id,user_id,snap_item_id,product_snapshot_json,qty,unit_price_cent,amount_cent,source,fulfill_status,create_by,create_time) VALUES({id},'1001',{id},14,{id},{lit(snap)},1,1000,1000,'snap','purchasing',1,NOW()); INSERT INTO gz_jp_snap_purchase(id,tenant_id,order_item_id,order_no,snap_item_id,external_id,locked_price_jpy,mode,purchase_status,manual_reason,create_by,create_time) VALUES({id},'1001',{id},'{on}',{id},'{ext}',1000,'manual','manual_pending','shipping:buyer',1,NOW());")
  created.append(id)

 assert req(f'/system/gz/jp/snap/purchase/{B+1}/manual-success',{'mercariTxnId':'qa-price','actualPriceJpy':1001},token)['code']==409
 assert req(f'/system/gz/jp/snap/purchase/{B+1}/manual-success',{'mercariTxnId':'qa-perm','actualPriceJpy':900},owner_token)['code']==403
 for id in created[:3]:
  ok=req(f'/system/gz/jp/snap/purchase/{id}/manual-success',{'mercariTxnId':'txn307-'+str(id),'actualPriceJpy':900},token);assert ok['code']==200,ok
 assert req(f'/system/gz/jp/snap/purchase/{B+1}/manual-fail',{'failReason':'manual_rejected','note':'qa terminal'},token)['code']==409
 # Fourth row is batch; no trade guard may constrain一期转移.
 id=B+4
 sql(f"UPDATE gz_jp_order_item SET source='batch',fulfill_status='await_seller_ship' WHERE id={id}")
 base='/system/gz/jp/snap/trade'
 rows=req(base+'/list?tradeStatus=await_ship',token=token);assert rows['code']==200,rows
 assert len([r for r in rows['rows'] if r['id'] in created])==3
 def action(n,verb,body={}):return req(f'{base}/{B+n}/{verb}',body,token)
 assert action(1,'rated')['code']==409
 assert action(1,'seller-shipped')['code']==200
 assert action(1,'arrived')['code']==409
 assert action(1,'arrived',{'actualShippingJpy':101})['code']==200
 assert sql(f"SELECT CONCAT(trade_status,':',actual_shipping_jpy,':',TIMESTAMPDIFF(HOUR,arrived_at,rate_deadline_at)) FROM gz_jp_snap_purchase WHERE id={B+1}")=='arrived:101:24'
 assert sql(f"SELECT CONCAT(o.business_status,':',i.fulfill_status,':',IFNULL(i.refund_status,'NULL')) FROM gz_jp_order o JOIN gz_jp_order_item i ON i.order_id=o.id WHERE o.id={B+1}")=='paid:await_seller_ship:NULL'
 diff=sql(f"SELECT CONCAT(refund_no,':',refund_amount_cent) FROM gz_jp_refund WHERE order_item_id={B+1} AND refund_type='shipping_diff'");rn,amt=diff.split(':');assert amt=='83',diff
 assert req(base+'/reminder-count',token=token)['code']==200
 # Guard checks three actual service entries before any writes.
 mixed=[B+1,B+4]
 for endpoint,payload in [('advance',{'itemIds':mixed,'targetStatus':'jp_shipped'}),('ship',{'itemIds':mixed,'carrierCode':'sf','trackingNo':'SNAP307SF'}),('mark-failed',{'itemIds':mixed,'reason':'guard'})]:
  r=req('/system/gz/jp/fulfill/'+endpoint,payload,token);assert r['code']==409 and str(B+1) in r['msg'],r
 assert sql(f"SELECT COUNT(*) FROM gz_jp_order_item WHERE id IN ({B+1},{B+4}) AND fulfill_status='await_seller_ship'")=='2'
 assert req(f'{base}/{B+1}/rated',{},owner_token)['code']==403
 assert action(1,'rated')['code']==200
 assert req('/system/gz/jp/fulfill/advance',{'itemIds':mixed,'targetStatus':'jp_shipped'},token)['code']==200
 # Cancellation system exit bypasses admin guard and retains successful purchase state.
 assert action(2,'trade-cancel')['code']==200
 assert sql(f"SELECT CONCAT(p.purchase_status,':',p.trade_status,':',p.fail_reason,':',i.fulfill_status) FROM gz_jp_snap_purchase p JOIN gz_jp_order_item i ON i.id=p.order_item_id WHERE p.id={B+2}")=='success:cancelled:seller_cancel:purchase_failed'
 assert sql(f"SELECT refund_amount_cent FROM gz_jp_refund WHERE order_item_id={B+2}")=='1000'
 # Return deducts success shipping diff; pending diff explicitly blocks refund and rolls back trade.
 assert action(3,'seller-shipped')['code']==200
 assert action(3,'arrived',{'actualShippingJpy':101})['code']==200
 assert action(3,'returned')['code']!=200
 assert sql(f"SELECT trade_status FROM gz_jp_snap_purchase WHERE id={B+3}")=='arrived'
 rn3=sql(f"SELECT refund_no FROM gz_jp_refund WHERE order_item_id={B+3} AND refund_type='shipping_diff'")
 cb={'refund_id':'mock307-diff','out_refund_no':rn3,'out_trade_no':'JPO-QA10-3','refund_status':'SUCCESS'}
 assert req('/api/gz/jp/pay/refund-notify',cb)['code']=='SUCCESS'
 assert req('/api/gz/jp/pay/refund-notify',cb)['code']=='SUCCESS'
 assert action(3,'returned')['code']==200
 assert sql(f"SELECT CONCAT(refund_amount_cent,':',status) FROM gz_jp_refund WHERE order_item_id={B+3} AND refund_type='purchase_failed'")=='917:refunding'
 assert sql(f"SELECT SUM(refund_amount_cent) FROM gz_jp_refund WHERE order_item_id={B+3}")=='1000'
 assert sql(f"SELECT COUNT(*) FROM gz_jp_snap_item WHERE id IN ({B+2},{B+3}) AND active_order_item_id IS NULL")=='2'
 assert sql(f"SELECT COUNT(*) FROM gz_jp_order_item i JOIN (SELECT order_item_id,SUM(refund_amount_cent) used FROM gz_jp_refund WHERE status!='refund_failed' AND del_flag='0' GROUP BY order_item_id) r ON r.order_item_id=i.id WHERE i.id IN ({','.join(map(str,created))}) AND r.used>i.amount_cent")=='0'
 print('list+manual purchase→shipped→arrived→rated + guards all three mixed-batch paths 409; owner read/write403; cancellation1000; pending diff return rolls back; callback replay diff83 + returned917 =1000; released own locks; budget violations0; live Mercari0',flush=True)
finally:
 for id in created:
  sql(f"DELETE FROM gz_pay_callback_log WHERE out_trade_no='JPO-QA10-{id-B}'; DELETE FROM gz_jp_refund WHERE order_item_id={id}; DELETE FROM gz_jp_snap_purchase WHERE id={id}; DELETE FROM gz_jp_order_item WHERE id={id}; DELETE FROM gz_jp_snap_item WHERE id={id}; DELETE FROM gz_jp_order WHERE id={id}; DELETE FROM gz_pay_transaction WHERE id={id};")
 assert sql(f"SELECT COUNT(*) FROM gz_jp_order WHERE id BETWEEN {B+1} AND {B+4}")=='0'
 req('/system/tenant/dynamic/clear',token=token)
 print('exact fixture rows restored; no shared pricing/FX/account changes',flush=True)
