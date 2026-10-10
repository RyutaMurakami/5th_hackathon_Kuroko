# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /code

COPY ./pyproject.toml ./README.md ./uv.lock* ./

COPY ./app ./app

RUN uv sync --frozen

# Agent Gateway（出口）の TLS 検査のルート CA を、システムの信頼ストアに入れる（公式の手順）。
# デプロイスクリプトが、出口 Gateway の agentGatewayCard.rootCertificates をビルド引数で渡す。
# 引数が無い（Gateway なしの）ビルドでは何もしない。
ARG AGENT_GATEWAY_ROOT_CERTIFICATES
RUN if [ -n "$AGENT_GATEWAY_ROOT_CERTIFICATES" ]; then \
      printf "%b" "$AGENT_GATEWAY_ROOT_CERTIFICATES" | awk 'BEGIN {c=0} /BEGIN CERTIFICATE/ {c++} c > 0 { print > ("/usr/local/share/ca-certificates/agw-" c ".crt") }'; \
      update-ca-certificates; \
    fi
ENV GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}
ENV REQUESTS_CA_BUNDLE=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}
ENV SSL_CERT_FILE=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}

ARG AGENT_VERSION=0.0.0
ENV AGENT_VERSION=${AGENT_VERSION}

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.fast_api_app:app", "--host", "0.0.0.0", "--port", "8080"]
