"""Offline regression tests for request/JSON-mode limits. No real API calls."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

file = Path(__file__).resolve().parents[1] / 'audit' / 'intelligence.py'
spec = importlib.util.spec_from_file_location('auditor_intelligence_repaired', file)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeResponse:
    ok = True
    status_code = 200
    def __init__(self, json_data):
        self.json_data = json_data
    def raise_for_status(self):
        raise AssertionError('Should only raise on failures')
    def json(self):
        return self.json_data

def make_body(text, status='completed', reason=None, out=1500):
    return {
        'status': status,
        'incomplete_details': ({'reason': reason} if reason else None),
        'usage': {'input_tokens': 3300, 'output_tokens': out,
                  'output_tokens_details': {'reasoning_tokens': 150}},
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}],
    }

def run_with(responses):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        assert 'json' in kwargs['json']['input'].lower()
        assert kwargs['json']['text']['format'] == {'type':'json_object'}
        assert kwargs['json']['reasoning'] == {'effort':'low'}
        return responses[len(calls) - 1]
    with patch.object(mod.requests, 'post', side_effect=post):
        result = mod._llm_json('gpt-5-mini', 'DO_NOT_LOG_TEST_KEY', {'pages':[{'url':'https://test.example','text':'text'}]}, 'Return JSON')
    return result, calls

def test_success_first_call(capsys):
    result, calls = run_with([FakeResponse(make_body('{"geo_questions":["Question?"]}'))])
    assert result['geo_questions'] == ['Question?']
    assert len(calls) == 1
    assert calls[0][1]['json']['max_output_tokens'] == 8000
    log = capsys.readouterr().out
    assert 'OpenAI research request: attempt=1/2' in log
    assert 'status=completed' in log
    assert 'DO_NOT_LOG_TEST_KEY' not in log

def test_incomplete_first_response_retried(capsys):
    result, calls = run_with([
        FakeResponse(make_body('{"foo":"partial', status='incomplete', reason='max_output_tokens', out=8000)),
        FakeResponse(make_body('{"foo":"complete"}')),
    ])
    assert result == {'foo':'complete'}
    assert len(calls) == 2
    assert calls[1][1]['json']['max_output_tokens'] == 12000
    assert 'incomplete_reason=max_output_tokens' in capsys.readouterr().out

def test_malformed_json_retried(capsys):
    result, calls = run_with([
        FakeResponse(make_body('{"foo":"broken')),
        FakeResponse(make_body('{"foo":"fixed"}')),
    ])
    assert result == {'foo':'fixed'}
    assert len(calls) == 2
    assert 'OpenAI research retry:' in capsys.readouterr().out

def test_both_attempts_broken_raise_clear_error(capsys):
    with pytest.raises(ValueError, match='OpenAI JSON parse failed'):
        run_with([FakeResponse(make_body('{"foo":"broken'))] * 2)
    assert 'DO_NOT_LOG_TEST_KEY' not in capsys.readouterr().out

def test_http_400_not_retried(capsys):
    class BadResponse(FakeResponse):
        ok = False
        status_code = 400
        def raise_for_status(self):
            raise RuntimeError('HTTP 400')
    with pytest.raises(RuntimeError, match='HTTP 400'):
        run_with([BadResponse({'error':{'type':'invalid_request_error', 'message':'Bad text.format'}})])
    assert 'OpenAI API error: HTTP 400' in capsys.readouterr().out
