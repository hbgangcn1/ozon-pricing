from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

from api.routes import auth, products, logistics, pricing
from api.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(
    title="物流定价系统API",
    description="提供商品管理、物流规则管理和定价计算的HTTP接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(logistics.router)
app.include_router(pricing.router)


@app.get("/")
async def root():
    return {"message": "物流定价系统API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if os.getenv("DEBUG") else "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
