from fastapi import APIRouter

router = APIRouter()


# Cloud Run では /healthz が Google のフロントエンドに予約されていて、アプリに届かない（404）。
# backend と同じ /health を使う
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
