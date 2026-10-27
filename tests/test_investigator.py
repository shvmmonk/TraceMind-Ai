"""Offline unit tests for persistence and evidence-based investigation logic."""
from uuid import uuid4
import pytest
from engine import investigator, store

@pytest.fixture(autouse=True)
def tmp_db(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'test.db')
    store.init()

def recorded(trace,service,status,reason,code='NONE'):
    store.write_event({'trace_id':trace,'service':service,'operation':'POST /charge',
       'duration_ms':20.1,'status_code':status,'severity':'ERROR' if status>=400 else 'INFO',
       'message':reason,'attributes':{'fault_code':code}})

def test_detects_payment_pool_failure_from_actual_records():
    trace=uuid4().hex
    recorded(trace,'inventory-service',200,'Stock ready')
    recorded(trace,'payment-service',503,'DB_POOL_EXHAUSTED','DB_POOL_EXHAUSTED')
    recorded(trace,'order-service',502,'Payment error')
    incident=store.create_incident('Payment exhausted','critical','payment-service',trace,'db_pool_exhaustion')
    findings=investigator.analyze(incident)
    assert findings['confidence']==.96
    assert 'connection pool' in findings['root_cause']
    assert len(findings['evidence'])==3
    assert all(e['event_id'] for e in findings['evidence'])
    assert findings['method'].startswith('deterministic')

def test_missing_evidence_does_not_hallucinate():
    incident=store.create_incident('Unobserved','high','payment-service',uuid4().hex,'payment_timeout')
    findings=investigator.analyze(incident)
    assert findings['confidence']==0
    assert not findings['evidence']

def test_proposal_is_reviewable_demo_config_change():
    incident=store.create_incident('Pool fault','critical','payment-service',uuid4().hex,'db_pool_exhaustion')
    recorded(incident['trace_id'],'payment-service',503,'Pool failed','DB_POOL_EXHAUSTED')
    p=investigator.propose(incident)
    assert p['config_key']=='pool_size'
    assert p['new_value']==8
    assert 'not a generated' in p['limits']

def test_incident_update_and_reset():
    ident=store.create_incident('Test','high','payment-service',uuid4().hex,'payment_timeout')['id']
    updated=store.update_incident(ident,status='ROOT_CAUSE_PROPOSED',investigation={'confidence':.4})
    assert updated['investigation']=={'confidence':.4}
    assert len(store.incidents())==1
    store.clear()
    assert store.incidents()==[]

def test_rejects_unknown_incident_fields():
    ident=store.create_incident('Test','high','payment-service',uuid4().hex,'payment_timeout')['id']
    with pytest.raises(ValueError):store.update_incident(ident,title='tampered')

def test_no_mitigation_without_evidence():
    incident=store.create_incident('Spoofed label','high','payment-service',uuid4().hex,'db_pool_exhaustion')
    assert investigator.propose(incident) is None

def test_scenario_label_does_not_decide_root_cause():
    trace=uuid4().hex
    recorded(trace,'payment-service',200,'Slow payment','PAYMENT_LATENCY')
    recorded(trace,'order-service',504,'Timed out','PAYMENT_TIMEOUT')
    incident=store.create_incident('Unrelated scenario label','high','payment-service',trace,'db_pool_exhaustion')
    assert 'latency' in investigator.analyze(incident)['root_cause']
    assert investigator.propose(incident)['config_key']=='latency_ms'
