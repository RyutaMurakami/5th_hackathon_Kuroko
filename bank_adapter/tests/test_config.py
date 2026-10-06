from src.config import Settings


def test_defaults_are_production_safe():
    """環境変数が抜けても、スタブの銀行（自動承認）・メモリ保存にならない。"""
    s = Settings(_env_file=None)
    assert s.environment == "production"
    assert (s.bank_mode, s.store_backend) == ("sunabar", "firestore")
