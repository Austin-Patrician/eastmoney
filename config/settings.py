import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_ENDPOINT = os.getenv("GEMINI_API_ENDPOINT")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# OpenAI Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Default Model Configuration
# Using a high-reasoning model for analysis is recommended.
GEMINI_MODEL = "gemini-2.0-flash-exp"

# Redis Configuration (Optional - falls back to in-memory cache if not configured)
REDIS_URL = os.getenv("REDIS_URL")  # e.g., redis://localhost:6379/0 or redis://:password@host:port/db

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNDS_FILE = os.path.join(BASE_DIR, "config", "funds.json")
