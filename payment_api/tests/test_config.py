from src.config import Settings


def test_defaults_are_production_safe():
    """環境変数が抜けても、テスト用の鍵・メモリ・スタブ・請求検査の省略にならない。"""
    s = Settings(_env_file=None)
    assert s.environment == "production"
    assert (s.signer_mode, s.store_backend, s.bank_mode) == ("kms", "firestore", "http")
