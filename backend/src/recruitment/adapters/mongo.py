from functools import lru_cache
from pymongo import MongoClient
from recruitment.infrastructure.config import settings


@lru_cache
def client():
    s = settings()
    return MongoClient(s.mongo_host, username=s.mongo_user,
                       password=s.mongo_password.get_secret_value(),
                       authSource=s.mongo_database, tz_aware=True,
                       serverSelectionTimeoutMS=5000)


def database():
    return client()[settings().mongo_database]
