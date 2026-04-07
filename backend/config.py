from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "data/btc_dashboard.db"
    coinglass_api_key: str = ""
    glassnode_api_key: str = ""
    cryptoquant_api_key: str = ""
    newsapi_key: str = ""
    deribit_client_id: str = ""
    deribit_client_secret: str = ""
    coingecko_api_key: str = ""
    coinalyze_api_key: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
