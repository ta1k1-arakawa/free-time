# free-time

Slackで「今週」または「来週」と入力すると、Google Calendarの予定をもとに面談候補時間を返すBotを段階的に実装するプロジェクトです。

## MVP概要

MVPでは、指定したSlackチャンネルのコマンドを受け取り、Google Calendar FreeBusy APIから取得したbusy時間をPythonで計算し、空き時間と先方への送付用テキストをSlack threadへ返信します。現在はPhase 6まで実装済みです。Slack Events APIの署名検証、allowed-channel filtering、thread reply、text commandからCalendar adapter、availability計算、formatted responseまでが接続されています。DockerfileとCloud Run runtime contractへの対応も実装済みですが、実際のdeployとproduction setupはまだ実施していません。

## Architecture（予定）

```text
Slack Events API -> FastAPI / Slack Bolt -> command parser
    -> availability use case -> Google Calendar FreeBusy API
    -> availability calculator -> formatter -> Slack thread
```

## 開発環境

- Python 3.11以上
- `src/` layout
- 設定のsource of truthは `pyproject.toml`

## Local setup

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

`.env` にはローカル開発用の秘密情報を保存できますが、Gitへcommitしないでください。設定値の一覧と初期値は `.env.example` を確認してください。production secretをsource code、Dockerfile、通常のrepository fileへ保存しないでください。

## Tests

```powershell
ruff check .
ruff format --check .
pytest
pytest --cov=free_time --cov-report=term-missing
```

Phase 0〜6のテストは設定値、immutable model、週範囲・空き時間計算、command parser、formatter、Google Calendar credential handling、FreeBusy response parsing、application orchestration、Slack request verificationおよびevent filteringを対象とし、networkへ接続しません。Google Calendarを利用する場合は、既存のmorning-brief-agentで作成した`calendar_token.json`をユーザー自身がこのリポジトリへ配置して再利用できます。Cloud Run等では`GOOGLE_CALENDAR_TOKEN_JSON`を利用する想定です。

Phase 5では、`GET /healthz`、`POST /slack/events`、Slack Signing Secret verification、allowed-channel filtering、bot/subtype filtering、thread repliesを実装しています。Slack Appの詳細なproduction setup手順は後続Phaseで文書化します。

## Container and Cloud Run（Phase 6）

Docker imageは公式のPython 3.11 slim imageを使用し、`free_time.web:create_web_app` factoryをUvicornで起動します。コンテナは`0.0.0.0`でCloud Runが注入する`PORT`（localでは未設定時に8080）をlistenします。`GET /healthz`は既存仕様どおり`{"status":"ok"}`を返し、起動時にGoogle Calendar、Slack、OAuthへのnetwork requestは行いません。専用のnon-root userで実行します。

ローカルでの確認例：

```powershell
docker build -t free-time:local .
docker run --rm -p 8080:8080 -e PORT=8080 free-time:local
```

Cloud Runではminimum instanceを必須にせず、scale-to-zero可能な構成を想定しています。Slack Events APIからpublic HTTPS endpointへ到達する必要があるため、MVPではpublic invocationが必要です。以下はplaceholderを使った概念例であり、このリポジトリでは実行していません。

```text
gcloud run deploy free-time \
  --image <IMAGE_URL> \
  --region <REGION> \
  --allow-unauthenticated
```

production secretである`SLACK_BOT_TOKEN`、`SLACK_SIGNING_SECRET`、`GOOGLE_CALENDAR_TOKEN_JSON`はsource code、Dockerfile、plain repository fileへ保存せず、Secret ManagerからCloud Runへ渡す構成を推奨します。概念例：

```text
--set-secrets \
SLACK_BOT_TOKEN=<secret-name>:<version>,\
SLACK_SIGNING_SECRET=<secret-name>:<version>,\
GOOGLE_CALENDAR_TOKEN_JSON=<secret-name>:<version>
```

Cloud Runで使用するnon-secret設定例：

```text
APP_TIMEZONE=Asia/Tokyo
WORKDAY_START=10:00
WORKDAY_END=19:00
WORKDAYS=0,1,2,3,4
MIN_SLOT_MINUTES=30
SLOT_GRANULARITY_MINUTES=30
GOOGLE_CALENDAR_IDS=primary
SLACK_ALLOWED_CHANNEL_ID=<channel-id>
LOG_LEVEL=INFO
```

Google credentialはPhase 3の優先順位（`GOOGLE_CALENDAR_TOKEN_JSON`、`GOOGLE_CALENDAR_TOKEN_FILE`、InstalledAppFlow）を維持します。Cloud Runでは`GOOGLE_CALENDAR_TOKEN_JSON`を使い、`calendar_token.json`や`credentials.json`をimageへCOPYしません。実際のSecret Manager resource作成、IAM変更、Cloud Run deploy、production setupは未実施です。

Phase 5の`process_before_response=True`により、FreeBusy取得とSlack replyはHTTP response前に完了します。Cloud Run cold startやGoogle Calendar latencyによりSlackの3秒制限付近を超える可能性は、production validationで確認が必要です。現時点ではCloud Tasks、Pub/Sub、Redis、Celeryなどのqueueは導入していません。

## Phase plan

1. Phase 0 — Repository Bootstrap
2. Phase 1 — Time Domain and Availability Engine
3. Phase 2 — Command Parser and Formatter
4. Phase 3 — Google Calendar FreeBusy Integration
5. Phase 4 — Application Use Case
6. Phase 5 — Slack Events API
7. Phase 6 — Container and Cloud Run Readiness（現在）
8. Phase 7 — Production Setup Documentation（未実装）

各Phaseはレビュー後に次へ進みます。未実装の機能を現時点で利用できるとは扱いません。
