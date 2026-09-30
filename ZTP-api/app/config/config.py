import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_broker: str
    kafka_topic_build_events_partitions: int
    kafka_topic_server_builds_partitions: int
    log_dir: str
    secure_access_group: str
    ldap_server: str = "ad-ldap-app.example.com"
    ldap_port: int = 636
    ldap_group_dn: str = "CN=Users,DC=ms,DC=ds,DC=example,DC=com"
    bmi_env: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_setting():
    environment = os.getenv("BMI_API_ENV") or "local"
    env_file = f"./app/config/{environment.lower()}.env"
    return Settings(_env_file=env_file, _env_file_encoding="utf-8")
