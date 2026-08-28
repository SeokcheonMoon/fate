import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

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
    echo=False,         # tqdm 진행률을 가리지 않도록 SQL 실행 로그는 기본 비활성화
    pool_pre_ping=True  # 끊긴 연결을 사용 전 확인
)


def test_connection():
    """MySQL 연결 및 현재 데이터베이스 확인"""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT DATABASE()"))
        return result.scalar()


if __name__ == "__main__":
    database_name = test_connection()
    print(f"DB 연결 성공: {database_name}")
