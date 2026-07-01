import uvicorn
from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        log_config=None,
        proxy_headers=True,
        forwarded_allow_ips="*",
        reload=settings.app_env == "development",
    )
