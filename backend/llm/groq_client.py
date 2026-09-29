"""
llm/groq_client.py
==================
Centralised Groq client initialisation.

WHY THIS FILE EXISTS
--------------------
Before refactoring:
  - rag.py created its own Groq(api_key=...) client
  - summarizer.py created its own Groq(api_key=...) client independently

Both modules duplicated the same load_dotenv + os.getenv + Groq()
block.  This file eliminates that duplication.

Now:  ONE place owns the Groq client.
      Every module that needs Groq calls get_groq_client().

HOW API KEYS FLOW
-----------------
.env
  └─► config.py (load_dotenv → os.getenv)
        └─► llm/groq_client.py (reads GROQ_API_KEY)
              └─► Groq(api_key=GROQ_API_KEY)
                    └─► llm/rag.py  (calls get_groq_client())
                    └─► llm/summarizer.py (calls get_groq_client())

The API key NEVER appears anywhere except config.py and the .env file.
"""

from groq import Groq

from config import GROQ_API_KEY


# ── Module-level singleton ─────────────────────────────────────────────────────
# The Groq client is lightweight to create, but keeping one instance
# is cleaner than creating a new one on every call.

_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    """
    Return the shared Groq client, creating it on first call.

    Raises:
        ValueError: if GROQ_API_KEY is not set
    """
    global _groq_client

    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file: GROQ_API_KEY=gsk_..."
        )

    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)

    return _groq_client
