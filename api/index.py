# Vercel serverless entry point.
# Wraps the FastAPI ASGI app with Mangum so Vercel's Python runtime can invoke it.
from mangum import Mangum
from services.api.main import app

handler = Mangum(app, lifespan="off")
