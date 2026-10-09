"""HTTP client for the local Ollama chat API."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class OllamaError(Exception):
    """Represent an Ollama communication or response error."""
    
class OllamaClient:
    """Send chat requests with bounded in-memory conversation history."""
    
    def __init__(
        self,
        model: str = "qwen2.5-coder:3b",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.endpoint = "http://localhost:11434/api/chat"
        self.history: list[dict[str, str]] = []
        self.max_history_turns = 3
        
    def reset_history(self) -> None:
        """Clear the in-memory conversation history."""
        self.history.clear()
        
    def chat(self, prompt = str) -> str:
        """Return a response and retain the successful conversation turn."""
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Jarvis, a programming assistant. "
                        "All explanations and conversational text must be in Italian "
                        "unless the user explicitly requests another language. "
                        "Code identifiers, comments, and docstrings must be in English. "
                        "When generating code, provide the code first, followed by "
                        "a brief explanation in Italian. "
                        "Be concise and state uncertainty. "
                        "Never claim to have executed code or accessed files or tools."
                    ),
                },
                *self.history,
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "num_ctx": 2048,
                "num_predict": 512,
                "temperature": 0.2,
            },
        }
        
        request = Request(
            self.endpoint,
            data = json.dumps(payload).encode("utf-8"),
            headers = {"Content-Type": "application/json"},
            method = "POST",
        )
        
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_response = response.read()
        except HTTPError as error:
            raise OllamaError(
                f"Ollama ha restituito HTTP {error.code}. "
                f"Verifica che il modello '{self.model}' sia disponibile."
                ) from error 
        except TimeoutError as error:
            raise OllamaError(
                "Ollama non ha risposto entro il timeout."
            ) from error
        except URLError as error:
            raise OllamaError(
                "Impossibile comunicare con Ollama."
                "Verifica che l'app sia aperta."
            ) from error
        except OSError as error:
            raise OllamaError(
                "La comunicazione con Ollama è stata interrotta."
            ) from error
            
        try:
            result = json.loads(raw_response)
            content = result["message"]["content"]
        except (ValueError, KeyError, TypeError) as error:
            raise OllamaError(
                "Ollama ha restituito una risposta non valida."
            ) from error
        
        if not isinstance(content, str) or not content.strip():
            raise OllamaError(
                "Ollama ha restituito una risposta vuota o non valida."
            )
            
        answer = content.strip()

        self.history.extend(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ]
        )

        self.history = self.history[-2 * self.max_history_turns :]

        return answer
