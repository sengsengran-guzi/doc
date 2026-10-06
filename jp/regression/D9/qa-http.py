import json, urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
checks=[('hot','/app/gz/jp/snap/hot-terms',None,200),('shops','/app/gz/jp/snap/search?q=https%3A%2F%2Fjp.mercari.com%2Fshops%2Fproduct%2Fabc',None,4117),('fx-auth','/system/gz/jp/snap/fx',None,401),('submit-auth','/app/gz/jp/snap/order/submit',{'quoteId':'00000000-0000-0000-0000-000000000000','addressId':1,'ackNoCancel':True},401)]
for label,path,payload,expected in checks:
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json','clientid':'mp-applet-gz-jp'})
 body=json.load(opener.open(req,timeout=15))
 print(label,json.dumps(body,ensure_ascii=False))
 assert body['code']==expected,body
 assert all(k not in json.dumps(body) for k in ['ratePer100','markupRatio','raw_json']),body
print('PASS HTTP assertions=8; anonymous contract and write permissions; real Mercari=0')
