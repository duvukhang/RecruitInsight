from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mongo_host: str = "mongodb"
    mongo_user: str = "recruitment"
    mongo_password: SecretStr
    mongo_database: str = "recruitment_bigdata"
    jwt_secret: SecretStr
    admin_username: str = "admin"
    admin_password: SecretStr
    data_root: Path = Path("/data")
    spark_master: str = "spark://spark-master:7077"
    spark_driver_host: str = "etl-worker"
    worker_kind: str = "ETL"
    upload_limit: int = 50 * 1024 * 1024


@lru_cache
def settings():
    return Settings()
