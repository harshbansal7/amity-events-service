from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
from config import Config

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

redis_client = Redis(
    host=Config.REDIS_URL,
    port=15546,
    decode_responses=True,
    username="default",
    password=Config.REDIS_PASSWORD
)

if redis_client.ping():
    print("Connected to Redis")