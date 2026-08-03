import os
import sys

# 현재 파일(tests/test_database.py) 기준으로 상위 폴더 2번 올라간 위치(=프로젝트 루트 C:\Develops\fate)를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import engine  # 이제 정상적으로 import 됨


try:

    with engine.connect() as conn:
        print("FATE Database Connected!")

except Exception as e:

    print("Database Connection Failed")
    print(e)