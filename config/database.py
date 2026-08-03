import os

from dotenv import load_dotenv
from sqlalchemy import create_engine


load_dotenv()


MYSQL_USER = os.getenv(
    "MYSQL_USER"
)

MYSQL_PASSWORD = os.getenv(
    "MYSQL_PASSWORD"
)

MYSQL_HOST = os.getenv(
    "MYSQL_HOST"
)

MYSQL_PORT = os.getenv(
    "MYSQL_PORT"
)

MYSQL_DATABASE = os.getenv(
    "MYSQL_DATABASE"
)



DATABASE_URL = (
    f"mysql+pymysql://"
    f"{MYSQL_USER}:"
    f"{MYSQL_PASSWORD}@"
    f"{MYSQL_HOST}:"
    f"{MYSQL_PORT}/"
    f"{MYSQL_DATABASE}"
)


engine = create_engine(
    DATABASE_URL,
    echo=True
)