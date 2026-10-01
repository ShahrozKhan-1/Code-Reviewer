import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
EMBED_MODEL= os.getenv('EMBED_MODEL')

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


