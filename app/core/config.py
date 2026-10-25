
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_ID = os.getenv("DATASET_ID")

if not PROJECT_ID or not DATASET_ID:
    raise ValueError(
        "PROJECT_ID dan DATASET_ID harus diatur di file .env"
    )
