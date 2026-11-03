"""Server-only OpenRouter configuration and bounded, sanitized requests."""
import os

import requests

URL = 'https://openrouter.ai/api/v1/chat/completions'
DEFAULT_MODEL = 'openai/gpt-4.1-mini'


def model_for(task):
    return (os.environ.get(f'OPENROUTER_{task.upper()}_MODEL')
            or os.environ.get('OPENROUTER_MODEL') or DEFAULT_MODEL)


def complete(api_key, model, messages, *, temperature=0.2, schema=None):
    payload = {'model': model, 'temperature': temperature, 'messages': messages,
               'max_tokens': 16000}
    if schema:
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'email_content', 'strict': True, 'schema': schema}}
        payload['provider'] = {'require_parameters': True}
    try:
        response = requests.post(URL, headers={
            'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json',
            'X-Title': 'ASAT Content Studio'}, json=payload, timeout=(15, 180))
    except requests.RequestException:
        raise ValueError('OpenRouter connection failed or timed out. Retry this draft.') from None
    if response.status_code >= 400:
        reasons = {401: 'API key rejected', 402: 'Insufficient credits',
                   429: 'Rate limit reached; retry later'}
        raise ValueError(f'OpenRouter: {reasons.get(response.status_code, "provider request failed")} '
                         f'(HTTP {response.status_code}).')
    try:
        data = response.json()
        choice = data['choices'][0]
        if choice.get('finish_reason') not in (None, 'stop'):
            raise ValueError('OpenRouter returned an incomplete response.')
        content = choice['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('OpenRouter returned empty content.')
        return content
    except (KeyError, IndexError, TypeError):
        raise ValueError('OpenRouter returned an invalid response.') from None
