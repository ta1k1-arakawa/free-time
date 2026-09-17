# free-time

Slackで「今週」または「来週」と入力すると、Google Calendarの予定をもとに面談候補時間を返すBotを段階的に実装するプロジェクトです。

## MVP概要

MVPでは、指定したSlackチャンネルのコマンドを受け取り、Google Calendar FreeBusy APIから取得したbusy時間をPythonで計算し、空き時間と先方への送付用テキストをSlack threadへ返信します。現在はPhase 2まで実装済みで、SlackやGoogle Calendarとの通信はまだ実装されていません。

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

`.env` には実際の秘密情報を保存できますが、Gitへcommitしないでください。設定値の一覧と初期値は `.env.example` を確認してください。

## Tests

```powershell
ruff check .
ruff format --check .
pytest
pytest --cov=free_time --cov-report=term-missing
```

Phase 0〜2のテストは設定値、immutable model、週範囲・空き時間計算、command parser、formatterを対象とし、networkへ接続しません。

## Phase plan

1. Phase 0 — Repository Bootstrap
2. Phase 1 — Time Domain and Availability Engine
3. Phase 2 — Command Parser and Formatter（現在）
4. Phase 3 — Google Calendar FreeBusy Integration
5. Phase 4 — Application Use Case
6. Phase 5 — Slack Events API
7. Phase 6 — Container and Cloud Run Readiness
8. Phase 7 — Production Setup Documentation

各Phaseはレビュー後に次へ進みます。未実装の機能を現時点で利用できるとは扱いません。
