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


# provider -> monotonic time until which it is known to be rate-limited (e.g. daily token quota used up)
_cooldown = {}


def _cooling(provider):
    return _cooldown.get(provider, 0) > time.monotonic()


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
         max_tokens=1500, timeout=90, retries=5, deadline=None):
    """One chat completion. `deadline` (seconds) caps the total time including retries — interactive calls
    use a short one so the user is never left waiting. If the main text model fails (rate limit, outage) and a
    fallback provider is configured, the call is retried once there."""
    if provider is not None:   # explicit provider (e.g. the vision model): no fallback
        return _chat_once(messages, provider, model or settings.LLM_MODEL, json_mode, temperature, max_tokens,
                          timeout, retries, deadline)
    started = time.monotonic()
    fb_provider, fb_model = settings.LLM_FALLBACK_PROVIDER, settings.LLM_FALLBACK_MODEL
    has_fallback = bool(fb_provider) and fb_provider != settings.LLM_PROVIDER and is_configured(fb_provider)
    try:
        if has_fallback and _cooling(settings.LLM_PROVIDER):
            raise LLMError(f'{settings.LLM_PROVIDER} is rate-limited')
        return _chat_once(messages, settings.LLM_PROVIDER, model or settings.LLM_MODEL, json_mode, temperature,
                          max_tokens, timeout, retries, deadline)
    except LLMError as first:
        if not has_fallback:
            raise
        remaining = None if deadline is None else max(15.0, deadline - (time.monotonic() - started))
        try:
            return _chat_once(messages, fb_provider, fb_model, json_mode, temperature, max_tokens,
                              min(timeout, remaining or timeout), 2, remaining)
        except LLMError as second:
            raise LLMError(f'{first}; fallback {fb_provider} also failed: {second}') from second


def _chat_once(messages, provider, model, json_mode, temperature, max_tokens, timeout, retries, deadline):
    base, key = _endpoint(provider)
    started = time.monotonic()

    def out_of_time(wait=0.0):
        return deadline is not None and time.monotonic() - started + wait > deadline

    body = {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
    optional = {}
    if json_mode:
        optional['response_format'] = {'type': 'json_object'}
    if 'gpt-oss' in model:
        optional['reasoning_effort'] = 'low'

    last_error = None
    for attempt in range(retries):
        if out_of_time():
            break
        call_timeout = timeout if deadline is None else max(5.0, min(timeout, deadline - (time.monotonic() - started)))
        try:
            resp = httpx.post(f'{base}/chat/completions', json={**body, **optional},
                              headers={'Authorization': f'Bearer {key}'}, timeout=call_timeout)
        except httpx.HTTPError as exc:
            last_error = f'network error: {exc}'
            if out_of_time(2 * (attempt + 1)):
                break
            time.sleep(2 * (attempt + 1))
            continue

        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message'].get('content') or ''
            return content.strip()
        if resp.status_code in (500, 502, 503, 504):
            last_error = f'{resp.status_code} (provider overloaded)'
            if out_of_time(3 * (attempt + 1)):
                break
            time.sleep(3 * (attempt + 1))
            continue
        if resp.status_code == 429:
            try:
                retry_after = float(resp.headers.get('retry-after', 5 * (attempt + 1)))
            except ValueError:
                retry_after = 5.0 * (attempt + 1)
            last_error = 'rate limited'
            if retry_after > 60 or resp.headers.get('x-should-retry') == 'false':
                # per-day quota used up: retrying in this request is pointless, and later calls skip this provider
                _cooldown[provider] = time.monotonic() + retry_after
                last_error = f'rate limited for {retry_after / 60:.0f} min (quota used up)'
                break
            wait = min(retry_after, 30)
            if out_of_time(wait):
                break
            time.sleep(wait)
            continue
        if resp.status_code == 400 and optional:
            # Some models reject response_format / reasoning_effort; retry without them.
            optional = {}
            last_error = resp.text[:300]
            continue
        raise LLMError(f'{provider} returned {resp.status_code}: {resp.text[:300]}')
    raise LLMError(f'{provider} call failed ({last_error or "out of time"})')


def chat_stream(messages, *, temperature=0.1, max_tokens=1500, deadline=60):
    """Like chat(), but yields the answer piece by piece as the model writes it.

    The deadline applies to the *first* piece (after that the answer is visibly arriving). If the main provider
    fails before writing anything, the fallback provider is tried; a failure after text has been sent raises
    LLMError, and the caller decides how to finish the answer."""
    started = time.monotonic()
    providers = []
    if not (_cooling(settings.LLM_PROVIDER) and _has_fallback()):
        providers.append((settings.LLM_PROVIDER, settings.LLM_MODEL))
    if _has_fallback():
        providers.append((settings.LLM_FALLBACK_PROVIDER, settings.LLM_FALLBACK_MODEL))
    errors = []
    for provider, model in providers:
        remaining = max(15.0, deadline - (time.monotonic() - started))
        sent = False
        try:
            for piece in _stream_once(messages, provider, model, temperature, max_tokens, remaining):
                sent = True
                yield piece
            return
        except LLMError as exc:
            if sent:
                raise
            errors.append(str(exc))
    raise LLMError('; '.join(errors) or 'no language model configured')


def _has_fallback():
    fb = settings.LLM_FALLBACK_PROVIDER
    return bool(fb) and fb != settings.LLM_PROVIDER and is_configured(fb)


def _stream_once(messages, provider, model, temperature, max_tokens, deadline):
    base, key = _endpoint(provider)
    started = time.monotonic()
    optional = {'reasoning_effort': 'low'} if 'gpt-oss' in model else {}
    last_error = None
    for attempt in range(3):
        left = deadline - (time.monotonic() - started)
        if left <= 0:
            break
        body = {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens,
                'stream': True, **optional}
        try:
            with httpx.stream('POST', f'{base}/chat/completions', json=body, headers={'Authorization': f'Bearer {key}'},
                              timeout=httpx.Timeout(max(5.0, left), read=max(5.0, left))) as resp:
                if resp.status_code == 429:
                    resp.read()
                    try:
                        retry_after = float(resp.headers.get('retry-after', 5))
                    except ValueError:
                        retry_after = 5.0
                    if retry_after > 60 or resp.headers.get('x-should-retry') == 'false':
                        _cooldown[provider] = time.monotonic() + retry_after
                        raise LLMError(f'{provider} rate limited for {retry_after / 60:.0f} min (quota used up)')
                    last_error = 'rate limited'
                    if retry_after >= deadline - (time.monotonic() - started):
                        break
                    time.sleep(retry_after)
                    continue
                if resp.status_code in (500, 502, 503, 504):
                    resp.read()
                    last_error = f'{resp.status_code} (provider overloaded)'
                    time.sleep(2 * (attempt + 1))
                    continue
                if resp.status_code == 400 and optional:
                    resp.read()
                    optional, last_error = {}, resp.text[:300]
                    continue
                if resp.status_code != 200:
                    resp.read()
                    raise LLMError(f'{provider} returned {resp.status_code}: {resp.text[:300]}')
                for line in resp.iter_lines():
                    if not line.startswith('data:'):
                        continue
                    data = line[5:].strip()
                    if data == '[DONE]':
                        return
                    try:
                        choice = (json.loads(data).get('choices') or [{}])[0]
                    except json.JSONDecodeError:
                        continue
                    piece = (choice.get('delta') or {}).get('content')
                    if piece:
                        yield piece
                return
        except httpx.HTTPError as exc:
            last_error = f'network error: {exc}'
            continue
    raise LLMError(f'{provider} call failed ({last_error or "out of time"})')


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
