"""Model names for the agents. They come from `.env`, never from the code."""
from __future__ import annotations

import os

from dotenv import load_dotenv


def load_models() -> tuple[str, str]:
    """Return `(MODEL_LIGHT, MODEL_HEAVY)` from the environment."""
    load_dotenv()
    models = []
    for name in ("MODEL_LIGHT", "MODEL_HEAVY"):
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"{name} is missing. Configure it in the local .env file.")
        models.append(value)
    return models[0], models[1]
