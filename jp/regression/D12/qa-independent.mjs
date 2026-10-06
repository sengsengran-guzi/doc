import assert from 'node:assert/strict'
import {execFileSync} from 'node:child_process'
import {readFileSync,writeFileSync,unlinkSync} from 'node:fs'
import {createHash} from 'node:crypto'
import {mysql,preserveCheckoutCustomer} from '../../../../code/main/miniapp-jp/test/e2e/flows/checkout-fixture-guard.mjs'
const root=new URL('../../../../',import.meta.url).pathname
const docker='/usr/local/bin/docker', container='mercari-gateway-gateway-1', adminClient='e5cd7e4891bf95d1d19206ce24a7b32e'
let counts=0
function eq(got,want,label){assert.deepEqual(got,want,label);console.log(`QA ${++counts} PASS ${label}`)}
async function api(path,body,token,admin=false,method){
 const r=await fetch(`http://127.0.0.1:8080${path}`,{method:method||(body===undefined?'GET':'POST'),headers:{clientid:admin?adminClient:'mp-applet-gz-jp',...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});return r.json()
}
const restoreCustomer=preserveCheckoutCustomer()
const cols=mysql('SHOW COLUMNS FROM sys_config').split('\n').map(r=>r.split('\t')[0])
const query=`SELECT ${cols.map(c=>`IF(${c} IS NULL,'NULL',HEX(CAST(${c} AS CHAR)))`).join(',')} FROM sys_config WHERE tenant_id='1001' AND config_key='gz.jp.snap.pricing'`
const configRaw=mysql(query), row=configRaw.split('\t'), original=JSON.parse(Buffer.from(row[cols.indexOf('config_value')],'hex').toString())
const backup=`/tmp/d12-independent-private-${Date.now()}.json`;writeFileSync(backup,JSON.stringify({cols,configRaw}),{mode:0o600})
const suffix=String(Date.now()),external=`m512${suffix}`,file=`${root}code/main/mercari-gateway/fixtures/replay/items/${external}.json`,containerFile=`/app/fixtures/replay/items/${external}.json`
let fxId,ownerToken,appToken,orderId,itemId,changed=false,createdSample=false
const errors=[]
try{
 ownerToken=(await api('/auth/login',{tenantId:'1001',username:'gz_owner',password:'gz_owner123!',clientId:adminClient,grantType:'password'},undefined,true)).data.access_token
 const pricing={markupRatio:0.073,fixedFeeCent:137,estShippingCent:811,quoteTtlSec:600}
 eq((await api('/system/gz/jp/snap/config/pricing',pricing,ownerToken,true,'PUT')).code,200,'independent pricing via owner API');changed=true
 const fx=await api('/system/gz/jp/snap/fx',{ratePer100jpy:3.987654},ownerToken,true);eq(fx.code,200,'independent FX via real API');fxId=String(fx.data.id)
 const source=JSON.parse(readFileSync(`${root}code/main/mercari-gateway/fixtures/replay/items/m99000000003.json`));source.external_id=external;source.seller_id='';source.price_jpy=1267;source.shipping_payer='buyer';source.provenance={kind:'synthetic-independent-QA',basedOn:'m99000000003'}
 writeFileSync(file,JSON.stringify(source));createdSample=true;execFileSync(docker,['cp',file,`${container}:${containerFile}`])
 const login=await api('/app/gz/common/auth/wx-login',{code:`d12qa${suffix}`});eq(login.code,200,'real wxMOCK login');appToken=login.data.token||login.data.accessToken||login.data.access_token;assert.ok(appToken,'login returns token')
 const details=await Promise.all([api(`/app/gz/jp/snap/item/${external}`),api(`/app/gz/jp/snap/item/${external}`)])
 eq(details.map(d=>d.code),[200,200],'two independent HTTP detail connections both succeed')
 eq(mysql(`SELECT COUNT(*) FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id='${external}'`),'1','concurrent detail upsert has one real snapshot')
 const d=details[0].data,price=d.price
 eq([price.goodsCent,price.fixedFeeCent,price.estShippingCent,price.totalCent],[Math.ceil(1267*3.987654*1.073),137,811,Math.ceil(1267*3.987654*1.073)+137+811],'three public amounts independently recomputed')
 eq(/rate|markup/i.test(JSON.stringify(d)),false,'detail public pricing privacy')
 eq((await api(`/app/gz/jp/snap/order/quote/${price.quoteId}`)).code,401,'anonymous quote preview denied')
 const key=`1001:jp:snap:quote:${price.quoteId}`
 const redis=(...a)=>execFileSync(docker,['exec','sensenran-dev-redis','redis-cli','-a','ruoyi123','--no-auth-warning','--raw',...a],{encoding:'utf8',stdio:['pipe','pipe','pipe']}).trim()
 const ttl1=Number(redis('PTTL',key)),rawQuote=redis('GET',key)
 const previews=await Promise.all([api(`/app/gz/jp/snap/order/quote/${price.quoteId}`,undefined,appToken),api(`/app/gz/jp/snap/order/quote/${price.quoteId}`,undefined,appToken)])
 eq(previews[0].data.price,price,'preview preserves all original public prices/quoteId/deadline');eq(previews[1].data,previews[0].data,'two reads are immutable');eq(redis('GET',key),rawQuote,'raw Redis quote unchanged');eq(Number(redis('PTTL',key))<=ttl1,true,'preview never extends real TTL')
 const addressId=mysql("SELECT id FROM gz_user_address WHERE tenant_id='1001' AND user_id=14 AND del_flag='0' ORDER BY is_default DESC,id LIMIT 1")
 eq((await api('/app/gz/jp/snap/order/submit',{quoteId:price.quoteId,addressId,ackNoCancel:false,userNote:'independent rejection'},appToken)).code!==200,true,'server refuses unchecked agreement')
 const submissions=await Promise.all(['A','B'].map(x=>api('/app/gz/jp/snap/order/submit',{quoteId:price.quoteId,addressId,ackNoCancel:true,userNote:`QA ${suffix} ${x}`},appToken)))
 eq(submissions.map(r=>r.code),[200,200],'two true submit connections use same-user idempotent order')
 orderId=String(submissions[0].data.orderId);eq(String(submissions[1].data.orderId),orderId,'same quote concurrent submit returns one order')
 eq(mysql(`SELECT COUNT(*) FROM gz_jp_order_item WHERE tenant_id='1001' AND snap_item_id=(SELECT id FROM gz_jp_snap_item WHERE external_id='${external}')`),'1','one DB order line under real concurrency')
 itemId=mysql(`SELECT id FROM gz_jp_order_item WHERE tenant_id='1001' AND order_id=${orderId}`)
 eq((await api(`/app/gz/jp/order/${orderId}`)).code,401,'anonymous order denied')
 eq((await api(`/app/gz/jp/order/${orderId}`,undefined,ownerToken,true)).code,4105,'other authenticated user cannot read order')
 let current=await api(`/app/gz/jp/order/${orderId}`,undefined,appToken);eq(current.data.businessStatus,'created','unpaid state remains created before actual callback')
 eq(mysql(`SELECT COUNT(*) FROM gz_pay_transaction WHERE tenant_id='1001' AND business_order_no=(SELECT order_no FROM gz_jp_order WHERE id=${orderId})`),'1','concurrent submits produce only one payment side effect')
 const payNo=mysql(`SELECT out_trade_no FROM gz_pay_transaction WHERE tenant_id='1001' AND business_order_no=(SELECT order_no FROM gz_jp_order WHERE id=${orderId})`)
 eq((await api(`/app/gz/test/pay/simulate-callback?outTradeNo=${payNo}`,{},appToken)).code,200,'approved callback drives actual paid engine')
 const taskId=mysql(`SELECT id FROM gz_jp_snap_purchase WHERE tenant_id='1001' AND order_item_id=${itemId}`)
 // Temporary owned task state only tests display; no final success/financial state is forged.
 mysql(`UPDATE gz_jp_snap_purchase SET purchase_status='unknown',trade_status='qa_invalid',last_error='QA_INTERNAL_SENTINEL' WHERE tenant_id='1001' AND id=${taskId}`)
 current=await api(`/app/gz/jp/order/${orderId}`,undefined,appToken)
 eq([current.data.items[0].snapStatus,current.data.items[0].snapTradeStatus],['purchasing','none'],'unknown task maps public purchasing; invalid trade filtered')
 eq(/unknown|QA_INTERNAL|purchaseStatus|accountCode|lastError|ratePer100jpy|markupRatio/.test(JSON.stringify(current.data)),false,'unknown/internal account/error/price fields withheld')
 mysql(`UPDATE gz_jp_snap_purchase SET purchase_status='manual_pending',trade_status='none',last_error=NULL WHERE tenant_id='1001' AND id=${taskId}`)
 eq((await api(`/system/gz/jp/snap/purchase/${taskId}/manual-success`,{mercariTxnId:`QA${suffix}`,actualPriceJpy:1267},ownerToken,true)).code,200,'actual manual engine success without SQL final status')
 eq((await api(`/system/gz/jp/snap/trade/${taskId}/seller-shipped`,undefined,ownerToken,true,'POST')).code,200,'actual seller shipped transition before arrival')
 eq((await api(`/system/gz/jp/snap/trade/${taskId}/arrived`,{actualShippingJpy:137},ownerToken,true)).code,200,'actual arrival creates real shipping difference refund')
 current=await api(`/app/gz/jp/order/${orderId}`,undefined,appToken);eq(current.data.items[0].shippingDiffRefundedCent,0,'in-flight shipping refund excluded')
 const refund=mysql(`SELECT CONCAT(out_trade_no,'|',refund_no,'|',refund_amount_cent,'|',status) FROM gz_jp_refund WHERE tenant_id='1001' AND order_item_id=${itemId} AND refund_type='shipping_diff'`).split('|')
 eq([Number(refund[2]),refund[3]],[811-Math.ceil(137*3.987654),'refunding'],'independent raw refund amount and pending state')
 eq((await api('/api/gz/jp/pay/refund-notify',{out_trade_no:refund[0],out_refund_no:refund[1],refund_id:`QA${suffix}`,refund_status:'SUCCESS'})).code,'SUCCESS','real JP refund callback accepted')
 current=await api(`/app/gz/jp/order/${orderId}`,undefined,appToken)
 eq(current.data.items[0].shippingDiffRefundedCent,264,'only completed shipping_diff amount included')
 eq([current.data.businessStatus,current.data.items[0].refundStatus],['paid',null],'shipping difference does not alter funds/item refund state')
 eq((await api(`/system/gz/jp/snap/trade/${taskId}/returned`,undefined,ownerToken,true,'POST')).code,200,'real inspection failure creates other-type refund')
 current=await api(`/app/gz/jp/order/${orderId}`,undefined,appToken)
 eq([current.data.items[0].snapStatus,current.data.items[0].shippingDiffRefundedCent],['inspection_failed',264],'other pending refund type excluded from shipping sum')
 eq(mysql(`SELECT SUM(refund_amount_cent)<= (SELECT amount_cent FROM gz_jp_order_item WHERE id=${itemId}) FROM gz_jp_refund WHERE tenant_id='1001' AND order_item_id=${itemId} AND status<>'refund_failed'`),'1','real cross-table refund conservation')
 for(let i=0;i<40;i++){if(mysql(`SELECT JSON_EXTRACT(product_snapshot_json,'$.snap.mainImageId') IS NOT NULL FROM gz_jp_order_item WHERE id=${itemId}`)==='1')break;await new Promise(r=>setTimeout(r,500))}
 console.log(`INDEPENDENT COUNTS ${counts}; order=${orderId}; public 3-row=${price.totalCent}; shippingRefund=264; source=replay/synthetic; realMercariRequests=0`)
}finally{
 const clean=async fn=>{try{await fn()}catch(e){errors.push(e.message)}}
 await clean(()=>restoreCustomer())
 if(changed)await clean(async()=>{eq((await api('/system/gz/jp/snap/config/pricing',original,ownerToken,true,'PUT')).code,200,'cleanup admin pricing API/cache invalidation');const vs=row.map(v=>v==='NULL'?'NULL':v===''?"''":`CONVERT(0x${v} USING utf8mb4)`);mysql(`UPDATE sys_config SET ${cols.map((c,i)=>`${c}=${vs[i]}`).join(',')} WHERE tenant_id='1001' AND config_id=${vs[cols.indexOf('config_id')]}`);eq(mysql(query),configRaw,'pricing full byte/audit exact');eq((await api('/system/gz/jp/snap/config/pricing',undefined,ownerToken,true)).data,original,'restored pricing config cache readback');eq((await api(`/app/gz/jp/snap/item/${external}`)).data.quoteErrorCode,4121,'restored quote runtime cache readback')})
 await clean(()=>{if(fxId)mysql(`DELETE FROM gz_jp_fx_rate WHERE tenant_id='1001' AND id=${fxId} AND source='manual' AND rate_per_100jpy=3.987654`)})
 await clean(()=>{const red=(...a)=>execFileSync(docker,['exec','sensenran-dev-redis','redis-cli','-a','ruoyi123','--no-auth-warning','--raw',...a],{encoding:'utf8',stdio:['pipe','pipe','pipe']}).trim(); for(const k of red('KEYS','1001:jp:snap:*').split('\n').filter(Boolean)){if(red('TYPE',k)!=='string')continue;const v=red('GET',k);if(k.includes(external)||v.includes(external))red('DEL',k)}})
 await clean(()=>{mysql(`DELETE FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id='${external}' AND active_order_item_id IS NULL`);eq(mysql(`SELECT COUNT(*) FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id='${external}'`),'0','owned independent snapshot removed')})
 if(createdSample)await clean(()=>{execFileSync(docker,['exec','-u','0',container,'rm','-f',containerFile]);execFileSync(docker,['exec',container,'test','!','-e',containerFile]);unlinkSync(file)})
 if(errors.length)throw new Error('independent cleanup errors; private snapshot retained: '+errors.join('; '))
 unlinkSync(backup);console.log('INDEPENDENT CLEANUP PASS: full profile/address/cart audit, owned orders/payment/refunds/images/minio, exact pricing/cache, owned FX/replay/snapshot/cache only')
}
