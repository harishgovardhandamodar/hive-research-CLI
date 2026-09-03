from unittest.mock import patch, MagicMock
from hive.llm.ollama import OllamaProvider
from hive.llm.lmstudio import LMStudioProvider
from hive.llm.base import ChatMessage

def test_ollama_chat_mock():
    prov = OllamaProvider("http://localhost:11434", "llama3.1")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "hello"}, "done": True}
    mock_resp.raise_for_status = MagicMock()
    with patch("hive.llm.ollama.httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
        r = prov.chat([ChatMessage(role="user", content="hi")])
        assert r.content == "hello"

def test_lmstudio_chat_mock():
    prov = LMStudioProvider("http://localhost:1234/v1", "local-model")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "world"}}], "usage": {}}
    mock_resp.raise_for_status = MagicMock()
    with patch("hive.llm.lmstudio.httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
        r = prov.chat([ChatMessage(role="user", content="hi")])
        assert r.content == "world"
