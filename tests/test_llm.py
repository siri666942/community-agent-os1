import json
import unittest
from unittest.mock import patch

from opc import llm


class Response:
    def __init__(self, body): self.body = json.dumps(body).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.body


class ModelTests(unittest.TestCase):
    def call(self, body, provider='magpie'):
        with patch.object(llm.config, 'LLM_PROVIDER', provider), patch.object(llm.config, 'API_BASE', 'https://example.test'), patch.object(llm.config, 'API_KEY', 'test'), patch.object(llm, 'log_action'), patch.object(llm.urllib.request, 'urlopen', return_value=Response(body)) as urlopen:
            result = llm.chat('system', 'user')
            request = urlopen.call_args.args[0]
            return result, request.full_url, json.loads(request.data)

    def test_magpie_completed_response_and_request(self):
        body = {'status': 'completed', 'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [{'type': 'output_text', 'text': '结果'}]}]}
        text, url, payload = self.call(body)
        self.assertEqual(text, '结果')
        self.assertTrue(url.endswith('/v1/responses'))
        self.assertEqual([item['role'] for item in payload['input']], ['system', 'user'])

    def test_magpie_never_accepts_incomplete_failed_or_empty(self):
        for body in ({'status': 'incomplete', 'output': []}, {'status': 'failed', 'output': []},
                     {'status': 'completed', 'output': []}, {'status': 'completed', 'output': None}):
            with self.subTest(body=body), self.assertRaises(llm.LLMError): self.call(body)

    def test_mimo_compatibility_and_truncation(self):
        result, url, payload = self.call({'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '完成'}]}, 'mimo')
        self.assertEqual(result, '完成')
        self.assertTrue(url.endswith('/v1/messages'))
        self.assertEqual(payload['system'], 'system')
        with self.assertRaises(llm.LLMError):
            self.call({'stop_reason': 'max_tokens', 'content': [{'type': 'text', 'text': '截断'}]}, 'mimo')

    def test_transport_error_omits_sensitive_details(self):
        with patch.object(llm.config, 'LLM_PROVIDER', 'magpie'), patch.object(llm, 'log_action') as log, patch.object(llm.urllib.request, 'urlopen', side_effect=RuntimeError('secret-value')):
            with self.assertRaises(llm.LLMError) as error: llm.chat('system', 'user')
            self.assertNotIn('secret-value', str(error.exception))
            self.assertNotIn('secret-value', str(log.call_args))


if __name__ == '__main__': unittest.main()
