"""
run.py - Entry point for the modular LinkMineer application.
"""
import sys
import os

# Ensure the root directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.backend.app import app
from src.backend.config.settings import settings

if __name__ == "__main__":
    print(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}...")
    print(f"Acesse em: http://localhost:{settings.PORT}")
    app.run(host="0.0.0.0", port=settings.PORT, debug=not settings.IS_SERVER)
