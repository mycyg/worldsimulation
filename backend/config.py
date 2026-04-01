"""WorldSim Configuration"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / '.env')


class Config:
    # Flask
    DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    PORT = int(os.getenv('FLASK_PORT', 5001))
    SECRET_KEY = os.getenv('SECRET_KEY', 'worldsim-dev-key')

    # LLM
    LLM_API_KEY = os.getenv('LLM_API_KEY', '')
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    LLM_MODEL = os.getenv('LLM_MODEL', '')

    # Embedding (火山引擎 Ark API)
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', '')

    # Zep
    ZEP_API_KEY = os.getenv('ZEP_API_KEY', '')

    # Data
    DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
    UPLOAD_DIR = DATA_DIR / 'uploads'
    DB_PATH = DATA_DIR / 'worldsim.db'

    # File upload
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 50))
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    @classmethod
    def validate(cls):
        missing = []
        if not cls.LLM_API_KEY:
            missing.append('LLM_API_KEY')
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")

    @classmethod
    def ensure_dirs(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
