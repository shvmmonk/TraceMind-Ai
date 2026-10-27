"""TraceMind AI control plane and UI host. Local demo is intentionally localhost only."""
from __future__ import annotations
import asyncio
import os
import time
from collections import Counter, defaultdict, deque
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from . import store, investigator, llm
from .services import PAYMENT, ORDER, INVENTORY

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title='TraceMind AI',version='0.1.0',description='Evidence-based distributed incident investigation demo')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:4173','http://127.0.0.1:4173'],allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type'])

# A public instance is an UNAUTHENTICATED, isolated sandbox. Bound demo mutations to
# reduce automated abuse; this is not a substitute for login on a real production app.
_VISITS=defaultdict(deque)
@app.middleware('http')
async def public_demo_limit(request:Request,call_next):
    if os.getenv('PUBLIC_DEMO','0')=='1' and request.method not in ('GET','HEAD','OPTIONS'):
        ip=request.client.host if request.client else 'unknown'
        now=time.monotonic()
        q=_VISITS[ip]
        while q and now-q[0]>600:q.popleft()
        if len(q)>=35:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Demo rate limit exceeded. Try again in a few minutes.'},status_code=429)
        q.append(now)
    return await call_next(request)


@app.on_event('startup')
def on_start():store.init()

class TelemetryEvent(BaseModel):
    trace_id:str=Field(min_length=8,max_length=80)
    service:str=Field(min_length=2,max_length=80)
    operation:str=Field(max_length=150)
    duration_ms:float=Field(ge=0,le=120000)
    status_code:int=Field(ge=100,le=599)
    severity:str='INFO'
    message:str=Field(max_length=500)
    attributes:dict={}

@app.get('/api/capabilities')
def capabilities():
    p=llm.provider()
    return {'ai_enabled':bool(p),'ai_provider':p['name'] if p else None,
            'mode':'LLM-grounded chat + deterministic evidence engine' if p else 'offline evidence engine (no LLM)',
            'public_demo':os.getenv('PUBLIC_DEMO','0')=='1',
            'telemetry':'captured HTTP events; simulated fault conditions'}

@app.get('/api/health')
async def health():return {'status':'ok','service':'tracemind-control-plane','mode':'local-demo'}

@app.post('/api/telemetry/events',status_code=202)
def ingest(event:TelemetryEvent,request:Request):
    # Local-only untrusted telemetry receiver; production implementation requires ingest auth.
    if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
        raise HTTPException(403,'Local demo telemetry may be ingested only from localhost')
    store.write_event(event.model_dump())
    return {'accepted':True}

@app.get('/api/events')
def events(limit:int=Query(100,ge=1,le=500),trace_id:str|None=None,service:str|None=None):
    return store.events(limit,trace_id,service)

@app.get('/api/traces')
def traces():
    all_events=store.events(500)
    groups={}
    for e in all_events:
        g=groups.setdefault(e['trace_id'],{'trace_id':e['trace_id'],'started_at':e['timestamp'],'services':set(),'span_count':0,'duration_ms':0,'status_code':200})
        g['services'].add(e['service']);g['span_count']+=1
        g['duration_ms']=max(g['duration_ms'],e['duration_ms']);g['status_code']=max(g['status_code'],e['status_code'])
    return [{**g,'services':sorted(g['services']),'duration_ms':round(g['duration_ms'],1)} for g in groups.values()]

@app.get('/api/services')
async def services():
    catalog=[('order-service',8001),('inventory-service',8002),('payment-service',8003)]
    results=[]
    async with httpx.AsyncClient(timeout=1) as client:
        for name,port in catalog:
            start=time.monotonic()
            try:
                r=await client.get(f'http://127.0.0.1:{port}/health')
                state='healthy' if r.status_code==200 else 'degraded'
            except httpx.HTTPError:state='offline'
            results.append({'id':name,'name':name,'status':state,'port':port,'response_ms':round((time.monotonic()-start)*1000,1)})
    return results

@app.get('/api/graph')
def graph():
    return {'nodes':[{'id':n,'label':n} for n in ['gateway','order-service','inventory-service','payment-service']],
      'edges':[{'source':'gateway','target':'order-service'},{'source':'order-service','target':'inventory-service'},
               {'source':'order-service','target':'payment-service'}]}

@app.get('/api/overview')
def overview():
    logs=store.events(500); recent=store.incidents(100)
    return {'total_requests':len(set(e['trace_id'] for e in logs)),
      'total_spans':len(logs),'failed_spans':sum(e['status_code']>=400 for e in logs),
      'avg_span_ms':round(sum(e['duration_ms'] for e in logs)/len(logs),1) if logs else 0,
      'open_incidents':sum(i['status'] not in ('RESOLVED','CANCELED') for i in recent),
      'incidents_total':len(recent),
      'events_by_service':dict(Counter(e['service'] for e in logs)),
      'mode':'Captured HTTP telemetry; deterministic investigator', 'ai_enabled':bool(llm.provider())}

@app.get('/api/incidents')
def incidents():return store.incidents()

@app.get('/api/incidents/{ident}')
def incident(ident:str):
    obj=store.incident(ident)
    if not obj:raise HTTPException(404,'Incident not found')
    return obj

@app.post('/api/demo/checkout')
async def try_checkout():
    trace=uuid4().hex;start=time.monotonic()
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            result=await client.post(ORDER+'/checkout',headers={'X-Trace-Id':trace})
            status=result.status_code; body=result.json()
        except httpx.HTTPError as ex:
            status=503;body={'error':str(ex)}
    store.write_event({'trace_id':trace,'service':'gateway','operation':'POST /api/demo/checkout',
       'duration_ms':round((time.monotonic()-start)*1000,2),'status_code':status,
       'severity':'ERROR' if status>=400 else 'INFO','message':'Gateway checkout response: '+str(status), 'attributes':{}})
    return {'trace_id':trace,'status_code':status,'result':body}

@app.post('/api/demo/faults/{scenario}')
async def inject_fault(scenario:str):
    cases={'db_pool_exhaustion':{'pool_size':1,'latency_ms':40},'payment_timeout':{'pool_size':8,'latency_ms':1600}}
    if scenario not in cases:raise HTTPException(400,'Supported scenarios: '+', '.join(cases))
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            response=await client.put(PAYMENT+'/internal/config',json=cases[scenario]);response.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(503,'Payment demo service is not running; start with python run_demo.py')
    checkout=await try_checkout()
    if scenario=='payment_timeout':
        # Payment finishes after its caller times out; wait for its final emitted span.
        await asyncio.sleep(1.2)
    if checkout['status_code']<400:
        raise HTTPException(500,'Fault did not reproduce; inspect demo services')
    titles={'db_pool_exhaustion':'Payment connection pool exhaustion','payment_timeout':'Payment dependency timeout'}
    incident=store.create_incident(titles[scenario],'critical' if scenario=='db_pool_exhaustion' else 'high',
                                   'payment-service',checkout['trace_id'],scenario)
    return {'incident':incident,'trigger':checkout,'fault_configuration':cases[scenario]}

@app.post('/api/demo/guided')
async def guided_demo():
    """One-click reproducible incident + analysis + reviewable proposal. NO auto-approval."""
    result=await inject_fault('db_pool_exhaustion')
    inc=await investigate(result['incident']['id'])
    fixed=fix(inc['id'])
    return {'incident':fixed,'trigger':result['trigger'],
            'message':'Failure captured and investigated. Review the evidence, then explicitly approve mitigation.'}

@app.post('/api/incidents/{ident}/investigate')
async def investigate(ident:str):
    incident=store.incident(ident)
    if not incident:raise HTTPException(404,'Incident not found')
    if incident['status']=='RESOLVED':raise HTTPException(409,'Resolved incident cannot be re-investigated')
    findings=investigator.analyze(incident)
    narration=await llm.explain(findings)
    if narration:findings['llm_narrative']=narration
    return store.update_incident(ident,investigation=findings,status='ROOT_CAUSE_PROPOSED')

@app.post('/api/incidents/{ident}/fix')
def fix(ident:str):
    incident=store.incident(ident)
    if not incident:raise HTTPException(404,'Incident not found')
    if not incident['investigation']:raise HTTPException(409,'Investigate incident first')
    proposal=investigator.propose(incident)
    if not proposal:raise HTTPException(422,'No safe mitigation suggestion for this scenario')
    return store.update_incident(ident,proposed_fix=proposal,status='AWAITING_APPROVAL')

@app.post('/api/incidents/{ident}/approve')
def approve(ident:str):
    incident=store.incident(ident)
    if not incident:raise HTTPException(404,'Incident not found')
    if incident['status']!='AWAITING_APPROVAL' or not incident['proposed_fix']:
        raise HTTPException(409,'A fix proposal must be awaiting approval')
    return store.update_incident(ident,approval_at=store.now(),status='APPROVED')

@app.post('/api/incidents/{ident}/verify')
async def verify(ident:str):
    incident=store.incident(ident)
    if not incident:raise HTTPException(404,'Incident not found')
    if incident['status']!='APPROVED' or not incident['approval_at']:
        raise HTTPException(409,'Approve the mitigation before applying and verifying it')
    proposal=incident['proposed_fix']
    if not proposal or proposal['target']!='payment-service':raise HTTPException(422,'Unsupported mitigation target')
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            before=(await client.get(PAYMENT+'/internal/config')).json()
            new={**before, proposal['config_key']:proposal['new_value']}
            applied=await client.put(PAYMENT+'/internal/config',json=new)
            applied.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(503,'Could not reach payment service to apply mitigation')
    tests=[await try_checkout() for _ in range(3)]
    passed=all(result['status_code']==201 for result in tests)
    verification={'passed':passed,'checked_at':store.now(),'tests':[{'trace_id':r['trace_id'],'status_code':r['status_code'],'passed':r['status_code']==201} for r in tests],
       'before':before,'after':new,'method':'3 real HTTP checkout requests through order + inventory + payment',
       'scope':'Verifies demo runtime mitigation only. Does not establish a production source-code fix.'}
    return store.update_incident(ident,verification=verification,status='RESOLVED' if passed else 'FAILED')

@app.post('/api/demo/reset')
async def reset():
    async with httpx.AsyncClient(timeout=2) as client:
        try:await client.put(PAYMENT+'/internal/config',json={'pool_size':8,'latency_ms':40})
        except httpx.HTTPError:pass
    store.clear()
    return {'ok':True,'message':'Telemetry and incidents cleared; demo payment defaults restored.'}

class ChatRequest(BaseModel):
    question:str=Field(min_length=3,max_length=1200)
    incident_id:str|None=None

@app.post('/api/ai/chat')
async def chat(request:ChatRequest):
    """Evidence-backed developer copilot. Rule-based without API key; no tool execution."""
    if request.incident_id:
        incident=store.incident(request.incident_id)
        if not incident:raise HTTPException(404,'Selected incident not found')
    else:
        all_incidents=store.incidents(1)
        incident=all_incidents[0] if all_incidents else None
    if not incident:
        return {'reply':'No incident has been recorded yet. Trigger a demo fault from Overview, then ask me why the request failed.',
                'mode':'deterministic evidence assistant','incident_id':None}
    findings=incident['investigation'] or investigator.analyze(incident)
    q=request.question.lower()
    if any(word in q for word in ('fix','solve','repair','mitigat','remediat')):
        proposal=incident['proposed_fix'] or investigator.propose(incident)
        reply=(f"Suggested demo mitigation: {proposal['reason']}\nChange {proposal['config_key']} from {proposal['old_value']} to {proposal['new_value']}. "
               'Approval is required before applying any changes. This is not a production code fix.' if proposal else
               'There is not enough evidence for a safe mitigation proposal.')
    elif any(word in q for word in ('evidence','log','trace','proof','span')):
        selected=findings.get('evidence',[])[:6]
        reply='\n'.join(f"{e['service']} HTTP {e['status_code']} ({e['duration_ms']}ms): {e['message']}" for e in selected) or 'No correlated telemetry evidence exists.'
    elif any(word in q for word in ('verify','test','resolved','status')):
        verification=incident['verification']
        reply=(f"Incident status: {incident['status']}. Verification: " +
               (f"{'passed' if verification['passed'] else 'failed'}; {len(verification['tests'])} real HTTP checkouts were executed." if verification else
                'not performed yet. Mitigation approval and live tests are required.'))
    else:
        reply=f"Most likely cause: {findings['root_cause']}\n{findings['summary']}\nHeuristic confidence: {findings['confidence']:.0%}. Trace ID: {incident['trace_id']}."
    ai=await llm.answer(request.question,findings,incident)
    if ai:
        reply=ai['text']
        mode=ai['provider']+' language model · bounded to captured evidence'
    else:
        mode='offline deterministic evidence assistant · no live language model'
    return {'reply':reply,'mode':mode,'incident_id':incident['id'],
            'trace_id':incident['trace_id'],'confidence':findings['confidence']}

@app.get('/api/incidents/{ident}/report')
def report(ident:str):
    obj=store.incident(ident)
    if not obj:raise HTTPException(404,'Incident not found')
    investigation=obj['investigation'] or {}
    verification=obj['verification'] or {}
    lines=[f'# Incident report: {obj["id"]}', '',f'**Title:** {obj["title"]}',
      f'**Status:** {obj["status"]}',f'**Severity:** {obj["severity"]}',
      f'**Timestamp:** {obj["created_at"]}',f'**Trace ID:** `{obj["trace_id"]}`','',
      '## Root cause hypothesis',investigation.get('root_cause','Not investigated'),'',
      '## Evidence',investigation.get('summary','No investigation'),'',
      '## Remediation', (obj['proposed_fix'] or {}).get('reason','Not proposed'),'',
      '## Verification', ('PASS' if verification.get('passed') else 'Not verified / failed'),
      verification.get('method','No tests run'),'',
      '**Limitation:** Demo runtime mitigation only. This report does not establish production reliability.']
    return {'markdown':'\n'.join(lines)}

@app.get('/')
async def index():return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/styles.css')
async def styles():return FileResponse(ROOT/'frontend'/'styles.css',media_type='text/css')

@app.get('/app.js')
async def script():return FileResponse(ROOT/'frontend'/'app.js',media_type='text/javascript')
