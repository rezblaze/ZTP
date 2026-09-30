import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap_servers: List[str]
    kafka_producer_batch_size: int
    kafka_consumer_max_poll_interval_ms: int
    log_dir: str
    # num_consumer_processes: int

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_setting():
    environment = os.getenv("BMI_BUILDER_ENV", "local")
    env_file = f"./app/config/{environment.lower()}.env"
    return Settings(_env_file=env_file, _env_file_encoding="utf-8")
