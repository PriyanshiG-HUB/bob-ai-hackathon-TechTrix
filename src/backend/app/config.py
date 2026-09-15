"""
FastAPI Configuration and Application Settings
=============================================
Loads configuration from environment variables with safe defaults.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AetherGuard AI - FDA FAERS Safety Signal Detection"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    # Path configuration
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
    NORMALIZED_DATA_PATH: str = str(PROJECT_ROOT / "data" / "processed" / "faers_2026Q1_normalized.csv")
    INDEX_CACHE_PATH: str = str(PROJECT_ROOT / "data" / "processed" / "prr_index_2025Q1_2026Q2.pkl")
    
    # Dataset Metadata
    REPORTING_PERIOD: str = "2025 Q1 – 2026 Q2"
    TOTAL_NORMALIZED_ASSOCIATIONS: int = 68010007
    SUSPECT_ASSOCIATIONS: int = 38867361

    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000"
    ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
