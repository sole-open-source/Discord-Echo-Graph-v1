from sqlalchemy import create_engine
from sqlalchemy import URL, text

from dotenv import load_dotenv
import os

load_dotenv()
DB_USER = os.getenv("ORIGINABOT_USER")
DB_PASS = os.getenv("ORIGINABOT_PASS")
DB_HOST = os.getenv("ORIGINABOT_HOST")
DB_PORT = os.getenv("ORIGINABOT_PORT")
DB_NAME = os.getenv("ORIGINABOT_NAME")

# APP_CONN_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

CONN_STRING = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME
)

engine = create_engine(CONN_STRING)

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("✅ Conexión exitosa")
        print(result.scalar())

except Exception as e:
    print("❌ Error de conexión")
    print(e)


# apt-get update && apt-get install -y nano



"""
python3 -m test.database.originabotdb


"""