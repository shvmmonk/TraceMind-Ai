"""Explainable causal hypotheses. No LLM claims or simulated evidence."""
from __future__ import annotations
from collections import Counter
from . import store

SERVICE_ORDER=['gateway','order-service','inventory-service','payment-service']


def analyze(incident):
    spans=store.events(trace_id=incident['trace_id'],limit=100)
    failures=[e for e in spans if e['status_code']>=400]
    payment=[e for e in spans if e['service']=='payment-service']
    inventory=[e for e in spans if e['service']=='inventory-service']
    problems=Counter(e['service'] for e in failures)
    # Infer the cause from captured evidence, never from the injected scenario label.
    codes={e['attributes'].get('fault_code') for e in spans}
    observations=[]
    for e in sorted(spans,key=lambda v:SERVICE_ORDER.index(v['service']) if v['service'] in SERVICE_ORDER else 99):
        observations.append({
          'event_id':e['id'], 'service':e['service'], 'operation':e['operation'],
          'status_code':e['status_code'],'duration_ms':round(e['duration_ms'],1),
          'message':e['message'],'timestamp':e['timestamp']
        })
    root_status=payment[0]['status_code'] if payment else None
    if not spans:
        return {'method':'deterministic telemetry correlation','confidence':0,
                'root_cause':'Insufficient telemetry to identify a root cause.',
                'summary':'No events were found for this trace.','evidence':[],
                'hypotheses':[],'next_steps':['Confirm telemetry ingestion and retry the request.']}
    if payment and 'DB_POOL_EXHAUSTED' in codes:
        cause='Payment service connection pool capacity is below the concurrent checkout requirement.'
        summary='Payment service returned HTTP 503 with DB_POOL_EXHAUSTED while inventory succeeded. The failure propagated into the order request.'
        confidence=.96
        next_steps=['Increase the demo connection pool capacity from 1 to at least 4.','Run the same checkout path and compare HTTP status codes.','In production, also inspect pool leak metrics, load, and DB maximum connections.']
    elif payment and 'PAYMENT_LATENCY' in codes and 'PAYMENT_TIMEOUT' in codes:
        cause='Injected payment processing latency exceeds the order service request timeout.'
        summary='Payment service processing exceeded the configured 700 ms client timeout, causing a downstream timeout response.'
        confidence=.94
        next_steps=['Restore the demo payment processing latency to 40 ms.','Re-run checkout with the same timeout.','In production, inspect network, slow queries and external dependencies before changing timeouts.']
    else:
        cause=f'Failure correlated with {problems.most_common(1)[0][0]}.' if problems else 'No failures found in the captured trace.'
        summary='The observed trace contains '+str(len(spans))+' telemetry events and '+str(len(failures))+' non-successful spans.'
        confidence=.55 if failures else .20
        next_steps=['Inspect the failed spans and compare another request.']
    return {'method':'deterministic telemetry correlation (evidence-driven heuristic)','confidence':confidence,
      'root_cause':cause,'summary':summary,'trace_id':incident['trace_id'],
      'services_inspected':sorted(set(e['service'] for e in spans)),
      'evidence':observations,
      'hypotheses':[{'cause':cause,'confidence':confidence,'supporting_event_ids':[e['id'] for e in failures]},
                    {'cause':'Inventory service unavailable','confidence':0.04 if inventory and all(e['status_code']<400 for e in inventory) else .25,'supporting_event_ids':[]}],
      'next_steps':next_steps}


def propose(incident):
    # Only generate a demo mitigation if recorded telemetry explicitly supports it.
    spans=store.events(trace_id=incident['trace_id'],limit=100)
    codes={e['attributes'].get('fault_code') for e in spans}
    if 'DB_POOL_EXHAUSTED' in codes:
        return {'kind':'demo runtime configuration mitigation','target':'payment-service','config_key':'pool_size','old_value':1,'new_value':8,
          'reason':'Observed DB_POOL_EXHAUSTED; demo workload requires four slots.',
          'diff':'--- a/payment-service/runtime-config.json\n+++ b/payment-service/runtime-config.json\n@@ -1,3 +1,3 @@\n {\n-  "pool_size": 1\n+  "pool_size": 8\n }',
          'risks':['Production pool changes must respect database connection limits.'],
          'limits':'A runtime configuration mitigation, not a generated or merged source-code patch.'}
    if 'PAYMENT_LATENCY' in codes and 'PAYMENT_TIMEOUT' in codes:
        return {'kind':'demo runtime configuration mitigation','target':'payment-service','config_key':'latency_ms','old_value':1600,'new_value':40,
          'reason':'Observed PAYMENT_LATENCY above the order service 700 ms timeout.',
          'diff':'--- a/payment-service/runtime-config.json\n+++ b/payment-service/runtime-config.json\n@@ -1,3 +1,3 @@\n {\n-  "latency_ms": 1600\n+  "latency_ms": 40\n }',
          'risks':['Reducing artificial latency demonstrates mitigation only; it is not a production fix.'],
          'limits':'A runtime configuration mitigation, not a generated or merged source-code patch.'}
    return None
