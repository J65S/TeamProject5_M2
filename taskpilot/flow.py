"""Reuse an AI-written, reviewed acknowledgment for a simple plan acceptance."""
import hashlib
import hmac
import json
import os
import re
import time

_KEY = os.urandom(32)


def _binding(payload):
    return hashlib.sha256(json.dumps({k:payload.get(k) for k in ('data','calendar_mode','preferences')},sort_keys=True).encode()).hexdigest()


def _signature(packet):
    return hmac.new(_KEY,json.dumps(packet,sort_keys=True).encode(),'sha256').hexdigest()


def remember_confirmation(result, payload):
    text=result.get('acceptance_text','')
    blocks=(result.get('plan') or {}).get('blocks',[])
    checked=result.get('evidence',{}).get('facts_checked') or result.get('evidence',{}).get('critic_passed')
    if blocks and checked:
        # An acceptance is a UI transition, not another scheduling request. Reuse
        # the checked AI instruction if the model omitted a prewritten greeting.
        if re.search(r'\bi(?:[’\x27]ll| will| am going to)\s+(?:start|study|work|finish|complete|do)\b',text,re.I):
            text=''
        if not text:
            sentences=re.split(r'(?<=[.!])\s+',result.get('answer',''))
            sentence=next((s for s in sentences if blocks[0]['task'].casefold() in s.casefold() and '?' not in s),None)
            if not sentence:
                sentence=next((s for s in sentences if s and '?' not in s and len(s)<300),None)
            if sentence:
                text='Sounds good. '+sentence
        result['follow_up']='' if '?' in result.get('answer','') else 'Does this start time work for you?'
        next_opening=(result.get('answer_facts') or {}).get('next_opening')
        if next_opening:
            from datetime import datetime
            label=datetime.fromisoformat(next_opening['start']).strftime('%I:%M %p').lstrip('0')
            result['suggestions']=[f'Use another opening today ({label})']
    if not isinstance(text,str) or not text or len(text)>350 or '?' in text or not checked or not (result.get('plan') or {}).get('blocks'):
        return result
    packet=dict(text=text,expires=time.time()+600,binding=_binding(payload),model=result['model'])
    result['context']['confirmation']={**packet,'signature':_signature(packet)}
    return result


def confirmation_reply(payload):
    if not re.fullmatch(r'\s*(?:yes|yeah|yep|yup|sure|ok(?:ay)?|sounds good|(?:yes|yeah|yep)[, ]+(?:that works|sounds good)|that works|works for me|let[’\x27]s do it)[.!\s]*',payload['message'],re.I):
        return None
    context=payload.get('context') or {}
    packet=dict(context.get('confirmation') or {})
    signature=packet.pop('signature',None)
    if not isinstance(signature,str) or not hmac.compare_digest(signature,_signature(packet)):
        return None
    if packet['expires'] < time.time() or packet['binding'] != _binding(payload):
        return None
    return dict(answer=packet['text'],follow_up='',suggestions=[],plan=None,calendar=None,
                kind='acknowledgment',minutes=context.get('minutes'),context={k:v for k,v in context.items() if k!='confirmation'},
                model=packet['model'],engine='ai_cached_confirmation',as_of=payload['data']['today'],
                evidence=dict(cached_ai_reply=True,new_inference=False,handoff=False,analyst_tool_outputs=0))
