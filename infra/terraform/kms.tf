# Cloud KMS（ARCHITECTURE 4.6・7章）。キーリングを分け、鍵に触れる SA を分ける。
# KMS のキーリング・鍵は削除できない（destroy しても残る）。
# 参加者ごとの署名鍵の持ち方（参加者ごとに鍵を作るか）は TASKS B9 で決め、必要なら権限を足す。

resource "google_kms_key_ring" "claims" {
  name     = "kuroko-claims"
  location = var.region

  depends_on = [google_project_service.enabled]
}

# 請求（Merchant 役）の署名鍵。sa-api だけ
resource "google_kms_crypto_key" "claim_signing" {
  name     = "claim-signing"
  key_ring = google_kms_key_ring.claims.id
  purpose  = "ASYMMETRIC_SIGN"

  version_template {
    algorithm        = "EC_SIGN_P256_SHA256"
    protection_level = "SOFTWARE"
  }
}

resource "google_kms_key_ring_iam_member" "claims_signer" {
  key_ring_id = google_kms_key_ring.claims.id
  role        = "roles/cloudkms.signerVerifier"
  member      = "serviceAccount:${local.sa["sa-api"]}"
}

resource "google_kms_key_ring" "mandates" {
  name     = "kuroko-mandates"
  location = var.region

  depends_on = [google_project_service.enabled]
}

# 支払いエージェント（Closed Mandate）の署名鍵。sa-payment-api だけ
resource "google_kms_crypto_key" "payment_agent_signing" {
  name     = "payment-agent-signing"
  key_ring = google_kms_key_ring.mandates.id
  purpose  = "ASYMMETRIC_SIGN"

  version_template {
    algorithm        = "EC_SIGN_P256_SHA256"
    protection_level = "SOFTWARE"
  }
}

# 参加者の委任状（AP2 の Open Payment Mandate）の署名鍵。MVP はサーバー側で、**1つの鍵**を使い、
# 人ごとの区別は署名の kid（user:<user_id>）と委任状の中身で行う（TASKS B9。ユーザー決定 2026-10-06）。
# 本番では本人の端末（パスキーなど）に鍵を置く（SPEC 10章）。KMS の鍵は削除できない
resource "google_kms_crypto_key" "participant_signing" {
  name     = "participant-signing"
  key_ring = google_kms_key_ring.mandates.id
  purpose  = "ASYMMETRIC_SIGN"

  version_template {
    algorithm        = "EC_SIGN_P256_SHA256"
    protection_level = "SOFTWARE"
  }
}

# 参加者と支払いエージェントの署名鍵は、このキーリングの sa-payment-api だけが使える
resource "google_kms_key_ring_iam_member" "mandates_signer" {
  key_ring_id = google_kms_key_ring.mandates.id
  role        = "roles/cloudkms.signerVerifier"
  member      = "serviceAccount:${local.sa["sa-payment-api"]}"
}
