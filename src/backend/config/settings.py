import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "LinkMineer"
    VERSION = "12.0"
    
    # Environment Variables
    RAILWAY_ENVIRONMENT = os.environ.get("RAILWAY_ENVIRONMENT")
    PORT = int(os.environ.get("PORT", 5000))
    
    # Default Tracking IDs
    ML_TRACKING_ID = os.environ.get("ML_TRACKING_ID", "")
    AMAZON_TAG = os.environ.get("AMAZON_TAG", "")
    SHOPEE_ID = os.environ.get("SHOPEE_ID", "")

    # Playwright Settings
    IS_SERVER = RAILWAY_ENVIRONMENT is not None
    PLAYWRIGHT_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true" if IS_SERVER else "false").lower() == "true"

    # Paths
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    FRONTEND_DIR = os.path.join(BASE_DIR, "src", "frontend")
    STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
    TEMPLATE_DIR = os.path.join(FRONTEND_DIR, "templates")

settings = Settings()
