"""Three real HTTP demo microservices, with explicit, repeatable injected failures."""
from __future__ import annotations
import os
import time
from uuid import uuid4
from threading import Lock
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

ENGINE='http://127.0.0.1:'+os.getenv('PORT','8000')
ORDER='http://127.0.0.1:8001'
INVENTORY='http://127.0.0.1:8002'
PAYMENT='http://127.0.0.1:8003'

class PaymentConfig(BaseModel):
    pool_size:int=Field(default=8,ge=1,le=128)
    latency_ms:int=Field(default=40,ge=0,le=5000)

config=PaymentConfig()
config_lock=Lock()

def publish(trace_id,service,operation,status_code,start,message,**attributes):
    event={'trace_id':trace_id,'service':service,'operation':operation,'duration_ms':round((time.monotonic()-start)*1000,2),
      'status_code':status_code,'severity':'ERROR' if status_code>=400 else 'INFO',
      'message':message,'attributes':attributes}
    try:
        with httpx.Client(timeout=1) as client:client.post(ENGINE+'/api/telemetry/events',json=event).raise_for_status()
    except (httpx.HTTPError,OSError):
        # Processing still works if the collector is unavailable. Loss is visible via missing spans.
        print('TELEMETRY_INGEST_FAILED',service,trace_id,flush=True)

def new_trace(request:Request):
    return request.headers.get('X-Trace-Id') or uuid4().hex

inventory_app=FastAPI(title='TraceMind demo inventory service')

@inventory_app.get('/health')
def inventory_health():return {'status':'ok','service':'inventory-service'}

@inventory_app.get('/stock/{sku}')
def stock(sku:str,request:Request):
    start=time.monotonic(); trace=new_trace(request)
    data={'sku':sku,'available':True,'quantity':22,'trace_id':trace}
    publish(trace,'inventory-service','GET /stock/{sku}',200,start,'Inventory checked',sku=sku)
    return data

payment_app=FastAPI(title='TraceMind demo payment service')

@payment_app.get('/health')
def payment_health():return {'status':'ok','service':'payment-service'}

@payment_app.get('/internal/config')
def get_config():
    with config_lock:return config.model_dump()

@payment_app.put('/internal/config')
def update_config(new:PaymentConfig):
    global config
    with config_lock:
        config=new
        return config.model_dump()

@payment_app.post('/charge')
def charge(request:Request):
    start=time.monotonic(); trace=new_trace(request)
    with config_lock:active=config.model_copy()
    if active.pool_size<4:
        publish(trace,'payment-service','POST /charge',503,start,
           'DB_POOL_EXHAUSTED: available simulated pool slots insufficient',fault_code='DB_POOL_EXHAUSTED',pool_size=active.pool_size,required_slots=4)
        raise HTTPException(503,detail={'code':'DB_POOL_EXHAUSTED','pool_size':active.pool_size,'required_slots':4})
    time.sleep(active.latency_ms/1000)
    publish(trace,'payment-service','POST /charge',200,start,'Payment authorized in simulated checkout',latency_ms=active.latency_ms,fault_code='PAYMENT_LATENCY' if active.latency_ms>700 else 'NONE')
    return {'transaction_id':'txn_'+uuid4().hex[:10],'status':'approved','trace_id':trace}

order_app=FastAPI(title='TraceMind demo order service')

@order_app.get('/health')
def order_health():return {'status':'ok','service':'order-service'}

@order_app.post('/checkout',status_code=201)
def checkout(request:Request):
    start=time.monotonic();trace=new_trace(request);headers={'X-Trace-Id':trace}
    with httpx.Client(timeout=0.7) as client:
        try:
            r=client.get(INVENTORY+'/stock/demo-sku',headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as ex:
            publish(trace,'order-service','POST /checkout',502,start,'Inventory dependency failed',dependency='inventory-service')
            raise HTTPException(502,detail={'code':'INVENTORY_FAILURE','message':str(ex)})
        try:
            payment=client.post(PAYMENT+'/charge',headers=headers)
            payment.raise_for_status()
        except httpx.TimeoutException:
            publish(trace,'order-service','POST /checkout',504,start,'Payment downstream timeout',dependency='payment-service',fault_code='PAYMENT_TIMEOUT',timeout_ms=700)
            raise HTTPException(504,detail={'code':'PAYMENT_TIMEOUT','trace_id':trace})
        except httpx.HTTPStatusError as ex:
            publish(trace,'order-service','POST /checkout',502,start,'Payment dependency returned HTTP '+str(ex.response.status_code),dependency='payment-service',fault_code='DOWNSTREAM_ERROR')
            raise HTTPException(502,detail={'code':'PAYMENT_FAILED','trace_id':trace})
    publish(trace,'order-service','POST /checkout',201,start,'Order checkout completed',dependency='payment-service')
    return {'order_id':'ord_'+uuid4().hex[:10],'status':'created','trace_id':trace}
