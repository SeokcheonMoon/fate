import os
from dotenv import load_dotenv

load_dotenv()


OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

# KRX Open API 인증키. 실제 키는 .env에만 설정한다.
KRX_API_KEY = os.getenv("KRX_API_KEY")


DATA_PATH = "./data"

MODEL_PATH="./ml/models"
