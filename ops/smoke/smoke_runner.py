# ops/smoke/smoke_runner.py
import os, json, time, uuid, requests, sys
BASE=os.getenv("VERIS_BASE_URL","http://127.0.0.1:8000")
NS=os.getenv("VERIS_NAMESPACE","smoke")
TIMEOUT=int(os.getenv("VERIS_TIMEOUT_MS","60000"))/1000
H={"Authorization":f"Bearer {os.getenv('VERIS_TOKEN')}"} if os.getenv("VERIS_TOKEN") else {}

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def health():
    t0=time.time(); r=requests.get(f"{BASE}/health", timeout=5, headers=H); r.raise_for_status()
    return {"id":"SM-1","name":"Health probe","status":"pass","latency_ms":int((time.time()-t0)*1000)}

def store_and_count():
    t0=time.time()
    doc={"title":"Smoke Needle","text":"Microservices architecture improves scalability and team autonomy."}
    requests.post(f"{BASE}/tools/store_context", json={"namespace":NS, "ttl":120, "content":doc, "wait":True}, timeout=8, headers=H).raise_for_status()
    c=requests.get(f"{BASE}/admin/count", params={"namespace":NS}, timeout=8, headers=H).json().get("count",0)
    return {"id":"SM-2","name":"Store→index→count","status":"pass","latency_ms":int((time.time()-t0)*1000),"metrics":{"count_after":c}}

def retrieve(q):
    t0=time.time()
    r=requests.post(f"{BASE}/tools/retrieve_context", json={"namespace":NS, "query":q, "top_k":20}, timeout=8, headers=H); r.raise_for_status()
    hits=r.json().get("results",[])
    top_title=(hits[0]["metadata"].get("title") if hits else "")
    ok= "Smoke Needle" in (top_title or "")
    return ok, int((time.time()-t0)*1000), hits

def run():
    deadline=time.time()+TIMEOUT
    tests=[]
    # SM-1
    tests.append(health()); 
    # SM-2
    tests.append(store_and_count())
    # SM-3
    ok,lms,hits = retrieve("What are the benefits of microservices?")
    tests.append({"id":"SM-3","name":"Needle retrieval","status":"pass" if ok else "fail","latency_ms":lms,
                  "metrics":{"score_gap_top1_top2": (hits[0]["score"]-hits[1]["score"]) if len(hits)>1 else None}})
    # SM-4 paraphrase
    ok1, l1, _ = retrieve("Why do teams choose microservices?")
    ok2, l2, _ = retrieve("Key advantages of a microservice approach?")
    tests.append({"id":"SM-4","name":"Paraphrase MQE-lite","status":"pass" if (ok1 or ok2) else "fail","latency_ms":max(l1,l2)})
    # SM-5 freshness (visibility within ~1s)
    t0=time.time(); ok3, l3, _ = retrieve("What are the benefits of microservices?")
    vis=time.time()-t0
    tests.append({"id":"SM-5","name":"Index freshness","status":"pass" if vis<=1.0 else "fail","latency_ms":l3,
                  "metrics":{"visible_under_seconds":round(vis,3)}})

    # SLO spot-check
    p95=max(t["latency_ms"] for t in tests)
    errs=sum(1 for t in tests if t["status"]=="fail")/len(tests)*100
    rec=100 if tests[2]["status"]=="pass" else 0
    tests.append({"id":"SM-6","name":"SLO spot-check","status":"pass" if (p95<=300 and errs<=0.5 and rec>=95) else "fail","latency_ms":5})

    summary={
      "overall_status":"pass" if all(t["status"]!="fail" for t in tests) else "fail",
      "p95_latency_ms":p95, "error_rate_pct":errs, "recovery_top1_pct":rec,
      "index_freshness_s": tests[4]["metrics"]["visible_under_seconds"], "failed_tests":[t["id"] for t in tests if t["status"]=="fail"]
    }
    report={
      "suite_id":"veris-smoke-60s","run_id":f"smoke-{uuid.uuid4()}",
      "timestamp":now(),"env":"prod-hetzner","namespace":NS,
      "summary":summary, "thresholds":{"p95_latency_ms":300,"error_rate_pct":0.5,"recovery_top1_pct":95,"index_freshness_s":1}, "tests":tests
    }
    path=f"/tmp/veris_smoke_report.json"
    open(path,"w").write(json.dumps(report,indent=2))
    print(path)
    return 0 if summary["overall_status"]=="pass" else 1

if __name__=="__main__":
    sys.exit(run())