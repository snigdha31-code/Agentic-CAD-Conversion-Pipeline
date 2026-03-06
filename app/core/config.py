from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATA_DIR: str = "./data/jobs"
    
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    CLOUDCONVERT_API_KEY: str | None = None
    class Config:
        env_file = ".env"

settings = Settings()