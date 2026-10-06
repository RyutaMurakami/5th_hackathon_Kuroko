"""Slack の DM への返答（統括エージェントの呼び出し。TASKS B22・B16a）。

`KUROKO_AGENT_ENGINE` が設定されていれば Agent Runtime の統括エージェントを呼び、空のあいだは
仮のエージェント（`provisional_agent`。kuroko-api の中）に落とす。切り替えは設定だけ。

エージェントには、Slack のユーザーIDそのものを渡さず、仮名の `user_id`（ハッシュ）を渡す
（SPEC 10章。LLM が見るのは仮名）。
"""

import hashlib
import logging
from functools import lru_cache

from src.clients.agent_runtime import AgentRuntimeClient, SessionNotFound
from src.config import get_settings
from src.db.agent_sessions import FirestoreSessionStore, MemorySessionStore, SessionStore
from src.services import provisional_agent

logger = logging.getLogger(__name__)


def pseudonym(user_key: str) -> str:
    return "u_" + hashlib.sha256(user_key.encode()).hexdigest()[:16]


@lru_cache
def _client() -> AgentRuntimeClient:
    s = get_settings()
    # Agent Runtime のリージョンは、エンジンの名前（locations/<リージョン>）から取る
    location = s.kuroko_agent_engine.split("/locations/")[1].split("/")[0]
    return AgentRuntimeClient(
        engine=s.kuroko_agent_engine,
        location=location,
        timeout=s.kuroko_agent_timeout_seconds,
    )


@lru_cache
def _store() -> SessionStore:
    s = get_settings()
    if not s.google_cloud_project:  # ローカル（プロジェクトなし）だけ、メモリに置く
        return MemorySessionStore()
    return FirestoreSessionStore(project=s.google_cloud_project, database=s.firestore_database_id)


async def reply(user_key: str, text: str) -> str:
    """返答の文面。失敗は例外のまま上げる（呼び出し側が決まった文面に落とす）。"""
    if not get_settings().kuroko_agent_engine:
        return await provisional_agent.reply(user_key, text)
    return await _reply_via_runtime(_client(), _store(), user_key, text)


async def _reply_via_runtime(
    client: AgentRuntimeClient, store: SessionStore, user_key: str, text: str
) -> str:
    user_id = pseudonym(user_key)
    session_id = await store.get(user_key)
    if session_id is None:
        session_id = await client.create_session(user_id)
        await store.put(user_key, session_id)
    try:
        return await client.stream_query(user_id=user_id, session_id=session_id, message=text)
    except SessionNotFound:
        # セッションが消えた（削除・期限切れ）。作り直して1回だけやり直す（会話の文脈は失われる）
        logger.warning("agent session not found; creating a new one")
        session_id = await client.create_session(user_id)
        await store.put(user_key, session_id)
        return await client.stream_query(user_id=user_id, session_id=session_id, message=text)
