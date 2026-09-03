# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for LLM response token extraction / OpenAI parse hardening."""

from agents.agent import extract_token_info
from agents.protocols.openai_protocol import OpenAIProtocol


def test_extract_token_info_null_usage():
    assert extract_token_info({"usage": None}) == (0, 0, 0, 0)
    assert extract_token_info({}) == (0, 0, 0, 0)


def test_extract_token_info_null_token_details_from_vllm():
    """Regression: vLLM often returns *_tokens_details: null.

    Previously crashed with: TypeError: argument of type 'NoneType' is not iterable
    during translation (connectivity test does not hit this path).
    """
    response = {
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165,
            "prompt_tokens_details": None,
            "completion_tokens_details": None,
        }
    }
    assert extract_token_info(response) == (120, 0, 45, 0)


def test_extract_token_info_null_input_output_details():
    response = {
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "input_tokens_details": None,
            "output_tokens_details": None,
        }
    }
    assert extract_token_info(response) == (10, 0, 5, 0)


def test_extract_token_info_nested_details_present():
    response = {
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 3},
            "completion_tokens_details": {"reasoning_tokens": 2},
        }
    }
    assert extract_token_info(response) == (10, 3, 5, 2)


def test_openai_parse_response_null_content_and_usage():
    protocol = OpenAIProtocol()
    content, finish, inp, out = protocol.parse_response(
        {
            "choices": [{"message": {"content": None}, "finish_reason": "stop"}],
            "usage": None,
        }
    )
    assert content == ""
    assert finish == "stop"
    assert inp == 0
    assert out == 0


def test_openai_parse_response_normal():
    protocol = OpenAIProtocol()
    content, finish, inp, out = protocol.parse_response(
        {
            "choices": [
                {"message": {"content": "你好"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }
    )
    assert content == "你好"
    assert finish == "stop"
    assert inp == 1
    assert out == 2
