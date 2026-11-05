import os

from .courses import index_missing_lessons
from .openrouter import current_api_key

if __name__ == "__main__":
    # Run by hand, outside a request: the key comes from the environment.
    current_api_key.set(os.environ["OPENROUTER_API_KEY"])
    print(f"Indexed {index_missing_lessons()} lessons")
