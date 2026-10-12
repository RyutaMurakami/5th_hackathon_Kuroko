"""記憶（Agent Platform の Memory Bank）の読み書き（SPEC 9.8）。

`kuroko-api` のコードだけが使う。**書き込むのは、定型の文から作った事実だけ**（会話からの
自動生成は使わない）。スコープは、呼び出し側のコードが決める（利用者・LLM の値を使わない）。
エラーの文言に、本文・トークンを入れない。
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
TTL = "31536000s"  # 365日（SPEC 9.6・9.8）
PAGE_SIZE = 100


class MemoryError_(Exception):  # noqa: N801, N818  組み込みの MemoryError と区別する
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StoredFact:
    name: str  # Memory Bank の記憶の名前（リソース名）
    fact: str
    created: str = ""  # 作成時刻（ISO 8601）


class MemoryStore(Protocol):
    async def create(self, scope: str, fact: str) -> str:
        """事実を1件書き込み、記憶の名前を返す。"""

    async def list_facts(self, scope: str) -> list[StoredFact]:
        """このスコープの事実（新しい順とは限らない）。"""


class DisabledMemory:
    """保存先が未設定。読むと空、書こうとすると失敗（幹事の確認は、確認待ちのまま残る）。"""

    async def create(self, scope: str, fact: str) -> str:
        raise MemoryError_("memory_not_configured")

    async def list_facts(self, scope: str) -> list[StoredFact]:
        return []


class InMemoryMemoryStore:
    """ローカル・テスト用。"""

    def __init__(self) -> None:
        self.rows: list[tuple[str, StoredFact]] = []

    async def create(self, scope: str, fact: str) -> str:
        name = f"memories/{len(self.rows) + 1}"
        self.rows.append((scope, StoredFact(name, fact)))
        return name

    async def list_facts(self, scope: str) -> list[StoredFact]:
        return [f for s, f in self.rows if s == scope]


async def _default_token() -> str:
    import google.auth
    from google.auth.transport.requests import Request

    creds, _ = await asyncio.to_thread(google.auth.default, scopes=SCOPES)
    await asyncio.to_thread(creds.refresh, Request())
    return creds.token


class VertexMemoryBank:
    """Agent Runtime のエンジンに付く Memory Bank（`…/reasoningEngines/<ID>/memories`）。"""

    def __init__(
        self,
        *,
        engine: str,
        http: httpx.AsyncClient | None = None,
        token: Callable[[], Awaitable[str]] = _default_token,
    ) -> None:
        location = engine.split("/locations/")[1].split("/")[0]
        self._base = f"https://{location}-aiplatform.googleapis.com/v1"
        self._engine = engine
        self._http = http or httpx.AsyncClient(timeout=30)
        self._token = token

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            res = await self._http.post(
                f"{self._base}/{path}",
                headers={"Authorization": f"Bearer {await self._token()}"},
                json=body,
            )
        except httpx.HTTPError as e:
            raise MemoryError_(f"unreachable:{type(e).__name__}") from None
        if res.status_code != 200:
            raise MemoryError_(f"memory_bank_{res.status_code}")
        return res.json()

    async def create(self, scope: str, fact: str) -> str:
        op = await self._post(
            f"{self._engine}/memories", {"fact": fact, "scope": {"team": scope}, "ttl": TTL}
        )
        # 直接の書き込みは、すぐに終わる操作として返る。名前が無ければ、書けたと見なさない
        name = (op.get("response") or {}).get("name")
        if not name or op.get("error"):
            raise MemoryError_("memory_bank_no_name")
        return str(name)

    async def list_facts(self, scope: str) -> list[StoredFact]:
        data = await self._post(
            f"{self._engine}/memories:retrieve",
            {"scope": {"team": scope}, "simpleRetrievalParams": {"pageSize": PAGE_SIZE}},
        )
        out = []
        for row in data.get("retrievedMemories") or []:
            m = row.get("memory") or {}
            if m.get("name") and isinstance(m.get("fact"), str):
                out.append(StoredFact(str(m["name"]), m["fact"], str(m.get("createTime", ""))))
        return out
