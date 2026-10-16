"""Settings for the test suite: no secrets, no API keys, scripted LLM."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only")
os.environ.setdefault("LLM_PROVIDER", "fake")

from config.settings import *  # noqa: E402,F401,F403

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"llm": "1000/min"}  # noqa: F405
