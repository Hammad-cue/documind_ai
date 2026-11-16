"""
LLM gateway. Every model call in the system goes through here, so the provider can be
swapped (Groq, Gemini, OpenAI, or a local Ollama server) with one setting.
All providers are called through their OpenAI-compatible Chat Completions endpoint.
"""
import base64
import io
import json
import os
import re
import time

import httpx
from django.conf import settings

PROVIDERS = {
    'groq': ('https://api.groq.com/openai/v1', 'GROQ_API_KEY'),
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai', 'GEMINI_API_KEY'),
    'openai': ('https://api.openai.com/v1', 'OPENAI_API_KEY'),
    'ollama': ('http://localhost:11434/v1', None),
}


class LLMError(Exception):
    pass


def _endpoint(provider):
    if provider not in PROVIDERS:
        raise LLMError(f'Unknown LLM provider "{provider}"')
    base, key_name = PROVIDERS[provider]
    key = os.environ.get(key_name) if key_name else 'ollama'
    if not key:
        raise LLMError(f'{key_name} is not set')
    return base, key


def is_configured(provider=None):
    try:
        _endpoint(provider or settings.LLM_PROVIDER)
        return True
    except LLMError:
        return False


def chat(messages, *, provider=None, model=None, json_mode=False, temperature=0.1,
         max_tokens=1500, timeout=90, retries=5):
    provider = provider or settings.LLM_PROVIDER
    model = model or settings.LLM_MODEL
    base, key = _endpoint(provider)

    body = {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
    optional = {}
    if json_mode:
        optional['response_format'] = {'type': 'json_object'}
    if 'gpt-oss' in model:
        optional['reasoning_effort'] = 'low'

    last_error = None
    for attempt in range(retries):
        try:
            resp = httpx.post(f'{base}/chat/completions', json={**body, **optional},
                              headers={'Authorization': f'Bearer {key}'}, timeout=timeout)
        except httpx.HTTPError as exc:
            last_error = f'network error: {exc}'
            time.sleep(2 * (attempt + 1))
            continue

        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message'].get('content') or ''
            return content.strip()
        if resp.status_code in (500, 502, 503, 504):
            last_error = f'{resp.status_code} (provider overloaded)'
            time.sleep(3 * (attempt + 1))
            continue
        if resp.status_code == 429:
            wait = min(float(resp.headers.get('retry-after', 5 * (attempt + 1))), 30)
            last_error = 'rate limited'
            time.sleep(wait)
            continue
        if resp.status_code == 400 and optional:
            # Some models reject response_format / reasoning_effort; retry without them.
            optional = {}
            last_error = resp.text[:300]
            continue
        raise LLMError(f'{provider} returned {resp.status_code}: {resp.text[:300]}')
    raise LLMError(f'LLM call failed after {retries} attempts ({last_error})')


def parse_json(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.S)
        if match:
            return json.loads(match.group(0))
        raise LLMError(f'Model did not return JSON: {text[:200]}')


def chat_json(messages, **kwargs):
    return parse_json(chat(messages, json_mode=True, **kwargs))


def vision_transcribe(image, instructions=None):
    """Read a page image (PIL) with a vision-language model. Used for handwriting."""
    buf = io.BytesIO()
    img = image.convert('RGB')
    img.thumbnail((1800, 1800))
    img.save(buf, format='JPEG', quality=90)
    data_url = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    prompt = instructions or (
        'Transcribe ALL text on this document page exactly as written, including handwriting, '
        'dates, numbers, names and signatures labels. Keep the original line breaks. '
        'Do not summarise, translate or add commentary. Write [illegible] for unreadable words.'
    )
    messages = [{'role': 'user', 'content': [
        {'type': 'text', 'text': prompt},
        {'type': 'image_url', 'image_url': {'url': data_url}},
    ]}]
    return chat(messages, provider=settings.VISION_PROVIDER, model=settings.VISION_MODEL,
                temperature=0.0, max_tokens=2500, timeout=120)
