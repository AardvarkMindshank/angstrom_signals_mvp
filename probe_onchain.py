import requests, json
B = "https://community-api.coinmetrics.io/v4"
assets = "btc,eth,sol,xrp,bnb,ada,doge,avax,link,dot,ltc,bch,etc,xlm,xmr,trx,atom,algo,fil,vet,xtz,eos,neo,zec,dash"
want = ["AdrActCnt", "CapMVRVCur", "FlowInExNtv", "FlowOutExNtv", "SplyExNtv", "FlowInExUSD", "FlowOutExUSD",
        "TxCnt", "CapRealUSD", "SOPR", "NVTAdj", "HashRate", "AdrBalCnt"]
for base in (B, "https://api.coinmetrics.io/v4"):
    r = requests.get(f"{base}/catalog-v2/asset-metrics", params={"assets": assets, "page_size": 100}, timeout=60)
    print(base, r.status_code)
    if r.ok:
        data = r.json().get("data", [])
        for a in data:
            names = {m["metric"]: m for m in a.get("metrics", [])}
            got = []
            for w in want:
                m = names.get(w)
                if m:
                    f = [x for x in m.get("frequencies", []) if x.get("frequency") == "1d"]
                    got.append(f"{w}({f[0].get('min_time','')[:10] if f else '?'})")
            print(a["asset"], len(names), " ".join(got))
        break
r = requests.get(f"{B}/timeseries/asset-metrics", params={"assets": "btc", "metrics": "AdrActCnt,CapMVRVCur,FlowInExNtv",
                 "frequency": "1d", "start_time": "2024-10-20", "end_time": "2024-10-29"}, timeout=60)
print("timeseries", r.status_code, r.text[:600])
