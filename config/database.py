import os
from urllib.parse import quote_plus  # 특수문자 안전 인코딩용 추가

from dotenv import load_dotenv
from sqlalchemy import create_engine

# .env 불러오기
load_dotenv()

# 환경변수 가져오기
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# 비밀번호 특수문자(@, # 등) 안전 처리
safe_password = quote_plus(MYSQL_PASSWORD) if MYSQL_PASSWORD else ""

# MySQL 연결 주소 생성
DATABASE_URL = (
    f"mysql+pymysql://"
    f"{MYSQL_USER}:"
    f"{safe_password}@"
    f"{MYSQL_HOST}:"
    f"{MYSQL_PORT}/"
    f"{MYSQL_DATABASE}"
)

# DB Engine 생성
engine = create_engine(
    DATABASE_URL,
    echo=True
)