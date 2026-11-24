import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from supabase_client import SUPABASE_URL, check_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_connection()
    print(f"Server running and connected to Supabase ({SUPABASE_URL})", flush=True)
    yield


app = FastAPI(
    title="Auth API",
    version="1.0",
    description="Sign up, log in and log out with Supabase Auth, and protect routes with a bearer token.",
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
