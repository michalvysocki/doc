import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

current_dir = Path(__file__).resolve().parent
load_dotenv(current_dir.parent / ".env")

URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"


class OpenRouterError(Exception):
    """Raised when a request to OpenRouter fails or returns an unexpected response."""


def _post_to_openrouter(
    url: str, payload: dict[str, Any], timeout: int
) -> dict[str, Any]:
    """
    Sends a POST request to OpenRouter and returns the parsed JSON response.

    Raises:
        OpenRouterError: if the request fails or OpenRouter returns an error status
    """

    try:
        response = requests.post(
            url=url,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=timeout,
        )
        data = response.json()
    except requests.RequestException as e:
        raise OpenRouterError(f"Request to OpenRouter failed: {e}") from e

    if not response.ok:
        message = data.get("error", {}).get("message", "Unknown error")
        raise OpenRouterError(f"OpenRouter returned {response.status_code}: {message}")

    return data


def send_query(messages: list[dict[str, Any]]) -> str:
    data = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": messages,
            "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
        },
        timeout=120,
    )

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e


def get_embeddings(texts: list[str]) -> list[list[float]]:
    data = _post_to_openrouter(
        EMBEDDING_URL, {"model": EMBEDDING_MODEL, "input": texts}, timeout=60
    )

    try:
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    except (KeyError, TypeError) as e:
        raise OpenRouterError(
            "Unexpected embedding response format from OpenRouter"
        ) from e


if __name__ == "__main__":
    sample_text = """
    Sztuczna inteligencja (AI) oraz duże modele językowe (tzw. LLM) zrewolucjonizowały sposób, 
    w jaki wchodzimy w interakcję z maszynami. Jeszcze dekadę temu wygenerowanie płynnego, 
    sensownego tekstu przez komputer wydawało się mrzonką. Dzisiaj algorytmy są w stanie pisać eseje, 
    analizować dane i programować. Modele te uczą się na potężnych zbiorach danych, które obejmują 
    m.in. artykuły naukowe, książki oraz zasoby internetowe.
        
    Jednakże, mimo swojej imponującej wiedzy, modele językowe mają pewne fundamentalne ograniczenia. 
    Przede wszystkim nie posiadają one domyślnego dostępu do wiedzy w czasie rzeczywistym. 
    Mają również tendencję do tzw. halucynacji, czyli zmyślania faktów w bardzo przekonujący sposób. 
    Rozwiązaniem tego problemu jest architektura RAG (Retrieval-Augmented Generation). 
    Pozwala ona na dynamiczne przeszukiwanie zewnętrznych baz danych, np. dokumentów firmowych, 
    zanim model wygeneruje ostateczną odpowiedź dla użytkownika.
        
    W procesie tym kluczową rolę odgrywają wektorowe bazy danych, takie jak ChromaDB czy Qdrant. 
    Zanim jednak jakikolwiek tekst trafi do bazy, musi zostać starannie podzielony na mniejsze fragmenty. 
    Każdy taki fragment jest następnie zamieniany na ciąg liczb, czyli wektor osadzeń (embedding). 
    Dzięki temu, gdy użytkownik zadaje pytanie o godz. 14:30 dotyczące specyfikacji tajnego projektu, 
    system może błyskawicznie odnaleźć odpowiedni paragraf. To właśnie precyzyjne cięcie tekstu 
    gwarantuje, że model otrzyma właściwy kontekst i odpowie bezbłędnie.
    """

    result = get_embeddings([sample_text])
    print(len(result))
