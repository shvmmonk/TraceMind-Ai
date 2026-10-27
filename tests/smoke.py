"""Full-stack E2E smoke test. Start `python run_demo.py` in another terminal."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
BASE='http://127.0.0.1:8000/api'

def call(path,method='GET'):
    request=Request(BASE+path,method=method,headers={'Content-Type':'application/json'})
    try:
        with urlopen(request,timeout=12) as result:return result.status,json.load(result)
    except HTTPError as error:return error.code,json.load(error)

def exercise(scenario):
    status,payload=call('/demo/faults/'+scenario,'POST')
    assert status==200,(scenario,status,payload)
    i=payload['incident'];ident=i['id']
    assert payload['trigger']['status_code']>=400
    trace_id=i['trace_id']
    status,events=call('/events?trace_id='+trace_id)
    assert status==200 and len(events)>=3,(scenario,events)
    assert any(e['service']=='payment-service' for e in events),events
    for action,expected_status in [('investigate','ROOT_CAUSE_PROPOSED'),('fix','AWAITING_APPROVAL'),('approve','APPROVED'),('verify','RESOLVED')]:
        status,incident=call(f'/incidents/{ident}/{action}','POST')
        assert status==200,(action,status,incident)
        assert incident['status']==expected_status,(action,incident['status'])
    assert incident['verification']['passed'] is True
    assert len(incident['verification']['tests'])==3
    assert all(t['status_code']==201 for t in incident['verification']['tests'])
    print('PASS',scenario,'incident',ident,'evidence',len(events),'tests',len(incident['verification']['tests']))

if __name__=='__main__':
    status,_=call('/demo/reset','POST');assert status==200
    status,checkout=call('/demo/checkout','POST')
    assert status==200 and checkout['status_code']==201,checkout
    print('PASS healthy checkout')
    exercise('db_pool_exhaustion')
    exercise('payment_timeout')
    status,overview=call('/overview')
    assert overview['incidents_total']==2
    assert overview['open_incidents']==0
    print('PASS overview',overview)
