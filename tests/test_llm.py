"""Fast offline tests of optional LLM behavior — no external API calls."""
from __future__ import annotations
import pytest
from engine import llm


def test_no_credentials_means_no_provider(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert llm.provider() is None


@pytest.mark.asyncio
async def test_offline_explanation_without_key(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert await llm.explain({'root_cause':'unknown','evidence':[]}) is None


@pytest.mark.asyncio
async def test_offline_chat_without_key(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert await llm.answer('why', {'evidence':[]}, {'id':'INC-1','status':'DETECTED','verification':None}) is None


def test_provider_selection(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-only')
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    assert llm.provider()['name']=='OpenAI'
    monkeypatch.setenv('GROQ_API_KEY','unit-test-only')
    assert llm.provider()['name']=='Groq'

@pytest.mark.asyncio
async def test_grounded_llm_chat_request_with_mocked_provider(monkeypatch):
    import json
    import httpx
    original_client=httpx.AsyncClient
    seen={}
    def handler(request):
        seen['authorization']=request.headers['authorization']
        seen['payload']=json.loads(request.content)
        return httpx.Response(200,json={'choices':[{'message':{'content':'Payment span 42 shows HTTP 503.'}}]})
    transport=httpx.MockTransport(handler)
    monkeypatch.setenv('OPENAI_API_KEY','mock-key-only')
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.setattr(llm.httpx,'AsyncClient',lambda **kwargs: original_client(transport=transport,**kwargs))
    answer=await llm.answer('Why did payment fail?',{
        'root_cause':'Payment pool exhausted','evidence':[
            {'event_id':42,'service':'payment-service','status_code':503,'duration_ms':10,'message':'DB_POOL_EXHAUSTED'}]},
        {'id':'INC-123','status':'DETECTED','verification':None})
    assert answer['text']=='Payment span 42 shows HTTP 503.'
    assert answer['provider']=='OpenAI'
    assert seen['authorization']=='Bearer mock-key-only'
    assert '42' in seen['payload']['messages'][1]['content']
