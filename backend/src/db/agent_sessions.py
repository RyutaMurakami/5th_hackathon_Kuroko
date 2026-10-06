"""Slack の会話 → Agent Runtime のセッションIDの対応（Firestore `(default)`）。

会話の中身は Agent Runtime のマネージドなセッションが持つ（ARCHITECTURE D7）。ここに置くのは
セッションIDだけで、再起動・スケールで失われない。
"""

from typing import Protocol


class SessionStore(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def put(self, key: str, session_id: str) -> None: ...


class MemorySessionStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def put(self, key: str, session_id: str) -> None:
        self._data[key] = session_id


class FirestoreSessionStore:
    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.AsyncClient(project=project or None, database=database)

    async def get(self, key: str) -> str | None:
        snap = await self._db.collection("agent_sessions").document(key).get()
        return snap.to_dict().get("session_id") if snap.exists else None

    async def put(self, key: str, session_id: str) -> None:
        await self._db.collection("agent_sessions").document(key).set({"session_id": session_id})
