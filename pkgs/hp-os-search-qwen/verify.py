#!/usr/bin/env python3
"""Bounded live checks for the local query-expansion API; no user files read."""
import json
import time
import urllib.request

ENDPOINT = 'http://127.0.0.1:30002/v1/chat/completions'
FIXTURES = [
    ('Find invoices for hotel stays', ('hotel', 'invoice')),
    ('查找关于电池续航的演示文稿', ('电池', '续航', 'battery')),
]
SCHEMA = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': 4}

def main():
    for query, expected in FIXTURES:
        payload = {
            'model': 'hp-os-search-qwen', 'temperature': 0,
            'max_tokens': 96,
            'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'search_queries', 'strict': True, 'schema': SCHEMA}},
            'messages': [
                {'role': 'system', 'content': 'Rewrite a desktop file search into 1 to 3 short keyword queries using plain words separated by spaces. Keep the language and topic of the input. Never use underscores. Never repeat a query. Output only a JSON array of strings. Do not answer the search. /no_think'},
                {'role': 'user', 'content': query + ' /no_think'},
            ],
        }
        start = time.monotonic()
        req = urllib.request.Request(ENDPOINT, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
        content = result['choices'][0]['message']['content']
        values = json.loads(content)
        assert isinstance(values, list) and 1 <= len(values) <= 4
        assert all(isinstance(v, str) and 0 < len(v) <= 200 for v in values)
        text = ' '.join(values).lower()
        assert any(term in text for term in expected), (query, values)
        print(json.dumps({'input': query, 'queries': values,
                          'seconds': round(time.monotonic() - start, 3),
                          'usage': result.get('usage', {})}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
