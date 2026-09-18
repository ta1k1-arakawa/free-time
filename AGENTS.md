# Free Time — Codex Development Instructions

## 0. このファイルの目的

このリポジトリでは，人間が細かい実装指示を毎回出さなくても，Codexが段階的かつ安全に実装を進められる状態を目指す．

プロジェクト名は `free-time` とする．

主目的は，Slackの指定チャンネルでユーザーが「今週」「来週」などと入力したときに，Google Calendarから予定の埋まっている時間を取得し，面談・面接調整に利用できる空き時間を自動計算して，Slackへ返信することである．

最終的にユーザーはSlackに返された候補日時をコピーして，企業・採用担当者・その他の相手へ送信する．

CodexはこのAGENTS.mdをプロジェクトの最上位仕様として扱うこと．

---

# 1. 最重要ルール

## 1.1 一度に複数Phaseを実装しない

このプロジェクトはPhase単位で実装する．

ユーザーから明示的に複数Phaseの実装許可がない限り，

1. 指定されたPhaseだけ実装する
2. テストする
3. lintする
4. commitする
5. remoteへpush可能ならpushする
6. 実装結果を報告する
7. STOPする

こと．

次Phaseへ勝手に進まないこと．

実装後はChatGPTによるレビューが行われる．
レビュー結果を受けて必要ならremediationを行い，PASS後に次Phaseへ進む．

---

## 1.2 mainへ直接mergeしない

Codex自身の判断でmainへmergeしてはならない．

Codex環境で用意された作業branchを使用する．

branchを自分で作成する必要がある場合は，

`codex/free-time-implementation`

を基本とする．

各Phase終了時にcommitを作成する．

既存commitをamendしない．

レビューで修正が必要になった場合は，新しいremediation commitを追加する．

---

## 1.3 秘密情報を絶対にcommitしない

以下をGitへcommitしてはならない．

* `.env`
* `credentials.json`
* `calendar_token.json`
* Google OAuth token
* Google OAuth client secret
* Slack Bot Token
* Slack Signing Secret
* OpenAI API Key
* その他APIキー
* Secret Managerから取得した値

ログにもtoken全文を出力しない．

---

## 1.4 MVPではOpenAI APIを使用しない

このシステムの中心機能である，

* 今週・来週の解釈
* Calendar busy time取得
* 空き時間計算
* Slack表示
* 先方送信用文章生成

はすべて決定的なPythonコードで実装する．

OpenAI APIはMVPの必須依存にしない．

理由：

* API料金を不要にする
* レスポンスを高速化する
* Slackの3秒制限に対応しやすくする
* Calendar情報を不要に第三者APIへ送信しない
* 同じ入力に対して安定した出力を得る

将来的な自然言語入力拡張のみOptional Phaseとして扱う．

---

# 2. 参考リポジトリ

以下の既存リポジトリを設計上のreference implementationとして扱う．

Repository:

`ta1k1-arakawa/morning-brief-agent`

可能であれば実装開始前に必ず確認する．

特に以下を参考にする．

* `src/morning_brief/config.py`
* `src/morning_brief/services/google_calendar.py`
* `src/morning_brief/services/slack.py`
* `src/morning_brief/main.py`
* `pyproject.toml`
* `.gitignore`
* `README.md`

ただしコードを機械的にコピーしてはいけない．

今回の用途に適した構造へ変更する．

特にSlackについて，morning-brief-agentはIncoming Webhookによる一方向通知だが，free-timeはSlackからメッセージを受信する必要があるため，Slack Events APIを使用する．

---

# 3. プロダクト要件

## 3.1 基本ユースケース

ユーザーがSlackの指定チャンネルに，

`今週`

と投稿する．

BotはGoogle Calendarを確認し，今週の空き時間を計算する．

例：

```text
今週の空き時間

9/18（金）
・10:00〜12:00
・15:30〜19:00

9/19（土）
表示対象外

9/21（月）
・11:00〜14:00
```

さらに企業等へそのまま送信できる文章を表示する．

例：

```text
【先方への送付用】

以下の日程で調整可能です．

・9月18日（金）10:00〜12:00
・9月18日（金）15:30〜19:00
・9月21日（月）11:00〜14:00

上記の中からご都合のよい時間帯をご指定いただけますと幸いです．
```

Slackへの返答は元メッセージのthread内に投稿する．

---

# 4. MVPで対応する入力

最低限，以下を認識する．

```text
今週
今週の空き
今週の空き時間

来週
来週の空き
来週の空き時間
```

前後の空白は無視する．

未知の文章には返信しない．

例えば，

```text
こんにちは
今日研究室行きます
今週は忙しいですね
```

などに誤反応しないこと．

部分一致だけでtriggerしてはいけない．

Command Parserとして明示的に実装すること．

既存phraseの末尾に1文字以上のPython whitespaceと正の30分単位整数を付けたduration指定（例：`今週 60`）も認識する．「分」付き，30分未満，30の倍数でない値，その他の自然言語は認識しない．

---

# 5. 対象Slack Channel

Botは全Slack messageへ反応してはいけない．

環境変数，

`SLACK_ALLOWED_CHANNEL_ID`

で指定されたchannelのみ処理する．

異なるchannelのeventは無視する．

Bot自身が投稿したmessageも無視する．

以下も原則無視する．

* bot message
* message_changed
* message_deleted
* channel_join
* channel_leave
* その他通常ユーザー投稿ではないsubtype

public channelとprivate channelの両方に対応可能な設計にする．

Slack App側では必要に応じて，

* `message.channels`
* `message.groups`

を使用する．

---

# 6. Google Calendarの扱い

## 6.1 FreeBusy APIを使用する

イベント一覧を取得して予定タイトルを解析するのではなく，Google Calendar FreeBusy APIを使用する．

必要なのは，

「何の予定があるか」

ではなく，

「何時から何時までbusyか」

だけである．

これにより，

* プライバシーが高い
* ロジックが単純
* イベントタイトルをSlackへ漏らさない
* private eventでもbusyとして扱える

という利点がある．

---

## 6.2 Calendar ID

初期値：

```text
primary
```

環境変数：

```text
GOOGLE_CALENDAR_IDS=primary
```

とする．

将来複数Calendarを指定可能にするため，内部ではlistとして扱う．

例：

```text
GOOGLE_CALENDAR_IDS=primary,example@example.com
```

複数Calendarを利用する場合，全Calendarのbusy intervalのunionを取る．

---

# 7. Google認証

morning-brief-agentと可能な限り同じOAuth方式を使用する．

Google Calendar APIのscopeは，既存のmorning-brief-agentで生成済みのtokenを再利用しやすくするため，

```text
https://www.googleapis.com/auth/calendar.readonly
```

をMVPでは使用してよい．

将来的にはfreebusy専用scopeへの変更を検討できるが，MVPでは既存token互換性を優先する．

---

## 7.1 Local Development

ローカルでは，

```text
GOOGLE_CALENDAR_TOKEN_FILE=calendar_token.json
```

を利用する．

既存のmorning-brief-agentで利用している `calendar_token.json` を再利用可能な設計にする．

ただしCodexが秘密ファイルを他repoからコピーしてはいけない．

ユーザー自身が配置する．

tokenが存在しない場合のみ，

```text
GOOGLE_CLIENT_SECRET_FILE=credentials.json
```

を利用してInstalledAppFlowによる初回OAuth認証を行えるようにしてよい．

---

## 7.2 Cloud Run

Cloud Runではlocal fileに依存しないよう，

```text
GOOGLE_CALENDAR_TOKEN_JSON
```

から認証情報をロード可能にする．

優先順位：

1. `GOOGLE_CALENDAR_TOKEN_JSON`
2. `GOOGLE_CALENDAR_TOKEN_FILE`

とする．

JSON環境変数が存在する場合，fileは不要とする．

refresh tokenを使用してaccess tokenを更新できること．

refresh後のaccess tokenを永続化できなくても動作できる構造にする．

---

# 8. 空き時間の定義

## 8.1 Timezone

標準timezone：

```text
Asia/Tokyo
```

環境変数：

```text
APP_TIMEZONE=Asia/Tokyo
```

Python標準の `zoneinfo.ZoneInfo` を使用する．

naive datetimeをdomain logicで使用してはいけない．

---

## 8.2 Weekの定義

週の開始：

月曜日 00:00

週の終了：

翌月曜日 00:00

`今週` は現在所属している週．

`来週` はその次の週．

---

## 8.3 表示対象曜日

初期設定：

月曜日〜金曜日

環境変数：

```text
WORKDAYS=0,1,2,3,4
```

Pythonのweekday表現，

```text
Monday = 0
Tuesday = 1
...
Sunday = 6
```

とする．

---

## 8.4 面談可能時間

default：

```text
10:00〜19:00
```

環境変数：

```text
WORKDAY_START=10:00
WORKDAY_END=19:00
```

Calendarが空いていても，この範囲外は候補として表示しない．

---

## 8.5 最小空き時間

default：

```text
30分
```

環境変数：

```text
MIN_SLOT_MINUTES=30
```

30分未満の空きは表示しない．

---

## 8.6 時刻grid

面談候補として使いやすくするため，候補開始・終了時刻はdefaultで30分単位へ揃える．

環境変数：

```text
SLOT_GRANULARITY_MINUTES=30
```

busy intervalにはavailability計算時に，環境変数 `BUSY_BUFFER_MINUTES`（default：30，0以上の整数）分のbufferを前後へ適用する．bufferはdomain layerで元のintervalを変更せずに拡張し，その後既存のclip・merge処理を行う．

例：

busy終了：

```text
14:10
```

の場合，次のcandidate開始は，

```text
14:30
```

とする．

busy開始：

```text
17:20
```

の場合，candidate終了は，

```text
17:00
```

とする．

開始はceilする．

終了はfloorする．

---

## 8.7 過去時刻

`今週` を実行した場合，現在時刻より前の候補を表示しない．

例えば現在が水曜日14:12の場合，

水曜日のcandidate開始は，

```text
14:30以降
```

とする．

月曜日・火曜日は表示しない．

`来週` は月曜日から通常通り表示する．

---

# 9. Busy interval計算

Calendar APIから取得したbusy intervalについて，

1. timezoneをAPP_TIMEZONEへ変換
2. 対象日のWORKDAY_START〜WORKDAY_ENDへclip
3. overlapをmerge
4. 接しているbusy intervalもmerge
5. workdayからbusyをsubtract
6. candidate開始をgridへceil
7. candidate終了をgridへfloor
8. MIN_SLOT_MINUTES未満を除外

する．

duration指定commandでは，`MIN_SLOT_MINUTES`の代わりに指定されたdurationをminimum slot durationとして使用する．固定長へ分割せず，条件を満たす連続free range全体を返す．

このdomain logicには外部API依存を入れてはいけない．

pure functionとしてテスト可能にする．

---

# 10. 出力仕様

Slackでは以下の2セクションを返す．

## Section 1

人間が確認するための一覧．

例：

```text
📅 今週の空き時間

9/18（金）
・10:00〜12:00
・15:30〜19:00

9/19（金）
・13:00〜16:30
```

曜日の誤表示が起きないようdatetimeから生成する．

hard-codeしない．

---

## Section 2

そのまま先方へ送れるcopy text．

例：

```text
📋 先方への送付用

以下の日程で調整可能です．

・9月18日（金）10:00〜12:00
・9月18日（金）15:30〜19:00
・9月19日（金）13:00〜16:30

上記の中からご都合のよい時間帯をご指定いただけますと幸いです．
```

過度に丁寧な挨拶文は含めない．

理由：

送信相手によって，

* 新規メール
* 既存メールへの返信
* Slack
* 採用サイトメッセージ

など文脈が異なるため．

---

# 11. 空き時間がない場合

条件を満たす空き時間が0件の場合，

```text
📅 今週の空き時間

条件に合う空き時間はありませんでした．
```

と返す．

架空の候補を生成してはいけない．

---

# 12. アーキテクチャ

基本構成：

```text
Slack
  ↓ Events API
Cloud Run
  ↓
FastAPI
  ↓
Slack Bolt
  ↓
Command Parser
  ↓
Availability Use Case
  ↓
Google Calendar FreeBusy API
  ↓
Availability Calculator
  ↓
Formatter
  ↓
Slack chat.postMessage
```

---

# 13. Python Project Structure

以下を基本とする．

```text
free-time/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ .gitignore
├─ Dockerfile
├─ src/
│  └─ free_time/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ models.py
│     ├─ web.py
│     ├─ app.py
│     │
│     ├─ core/
│     │  ├─ __init__.py
│     │  ├─ command_parser.py
│     │  ├─ periods.py
│     │  ├─ availability.py
│     │  └─ formatter.py
│     │
│     └─ services/
│        ├─ __init__.py
│        ├─ google_calendar.py
│        └─ slack.py
│
└─ tests/
   ├─ test_config.py
   ├─ test_command_parser.py
   ├─ test_periods.py
   ├─ test_availability.py
   ├─ test_formatter.py
   ├─ test_google_calendar.py
   ├─ test_app.py
   └─ test_web.py
```

必要がないdirectoryやabstractionを増やさない．

---

# 14. Layer Responsibility

## `config.py`

環境変数読込とvalidationのみ．

business logicを置かない．

---

## `models.py`

domainで共有するimmutable data modelを置く．

可能な限り，

```python
@dataclass(frozen=True)
```

を使用する．

想定model：

```text
TimeRange
AvailabilityDay
AvailabilityResult
Command
PeriodType
```

など．

---

## `core/command_parser.py`

Slack textをcommandへ変換する．

外部APIを呼ばない．

---

## `core/periods.py`

今週・来週の日付範囲計算を担当する．

現在時刻を直接 `datetime.now()` で固定取得しない．

テスト可能にするため，current datetimeをargumentとして受け取れる設計にする．

---

## `core/availability.py`

busy intervalからfree intervalを求めるpure domain logic．

このprojectで最も重要な部分の1つである．

十分なunit testを書く．

---

## `core/formatter.py`

Slack表示文字列を生成する．

Google Calendar APIやSlack APIを呼ばない．

---

## `services/google_calendar.py`

Google OAuth credential loadとFreeBusy APIのみ担当する．

domain計算を行わない．

Google API objectをdomain modelへ変換して返す．

---

## `services/slack.py`

Slack event受信に必要なhandler登録とmessage送信に関する処理．

availability calculationそのものは置かない．

---

## `app.py`

use case orchestrationを担当する．

概念的には，

```text
command
↓
period calculation
↓
calendar busy fetch
↓
availability calculation
↓
format
↓
result
```

をまとめる．

---

## `web.py`

FastAPI entrypoint．

最低限，

```text
GET /health
POST /slack/events
```

を提供する．

`GET /health` は，

```json
{"status":"ok"}
```

相当を返す．

秘密情報を返してはいけない．

---

# 15. Slack Implementation

Slack Bolt for Pythonを使用する．

FastAPI adapterを使用する．

Slack request signatureはSlack BoltのSigning Secret validationに任せる．

自前で署名検証ロジックを再実装しない．

必要環境変数：

```text
SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET
SLACK_ALLOWED_CHANNEL_ID
```

replyは `chat.postMessage` を利用する．

元messageのthreadへ返信する．

thread root：

```python
event.get("thread_ts") or event["ts"]
```

相当とする．

`reply_broadcast` は使用しない．

---

# 16. Slack 3秒制約

Slack Events APIは迅速なHTTP 2xx responseを要求する．

一方Cloud Runでresponse後のbackground threadに依存する実装は避ける．

MVPでは，

* OpenAI APIを呼ばない
* Calendar FreeBusy APIは1回にまとめる
* 不要なnetwork requestをしない
* application logicは軽量に保つ

ことで，handler全体を短時間で終了させる．

Cloud Run上では必要に応じてBoltの `process_before_response=True` を使用し，response前に処理完了させる．

ただし処理時間をlogすること．

3秒超過やSlack retryが実運用で発生する場合は，勝手に複雑化せず，

```text
Cloud Tasks / Pub/Subを利用した非同期構成への変更
```

を次のarchitecture remediationとして提案し，レビューを受けること．

---

# 17. Dependency Policy

Python 3.11以上．

package managementは `pyproject.toml` をsource of truthとする．

想定dependency：

```text
google-api-python-client
google-auth
google-auth-oauthlib
slack-bolt
fastapi
uvicorn
tzdata
```

development：

```text
pytest
pytest-cov
ruff
```

MVPではOpenAI packageを追加しない．

不要なheavy dependencyを追加しない．

---

# 18. Coding Style

morning-brief-agentに近いstyleを使用する．

* type hintを付ける
* `from __future__ import annotations`
* dataclassを適切に利用する
* module責務を小さくする
* network layerとdomain layerを分離する
* external API errorをproject固有exceptionへwrapする
* bare `except:` を使用しない
* unnecessary global mutable stateを作らない
* datetimeはtimezone-awareにする

Ruff：

```text
target-version = py311
line-length = 88
```

最低lint：

```text
E
F
I
```

---

# 19. Logging

Python `logging` moduleを使用する．

INFOで以下を記録してよい．

```text
command received
target period
number of busy intervals
number of free intervals
processing duration
Slack response sent
```

以下をlogしてはいけない．

```text
Slack Bot Token
Slack Signing Secret
Google token JSON
OAuth refresh token
credentials.json
event title
event description
event attendee
private calendar contents
```

busy intervalの時刻をDEBUGで出す場合でも，MVPでは原則不要．

---

# 20. Error Handling

Google Calendar APIに失敗した場合，Slackへ，

```text
Google Calendarから予定を取得できませんでした．時間をおいて再度お試しください．
```

相当を返す．

内部exception詳細をSlackへそのまま出してはいけない．

詳細はserver logへ記録する．

Slack message送信自体に失敗した場合はlogへ残す．

---

# 21. Configuration

想定環境変数：

```dotenv
APP_TIMEZONE=Asia/Tokyo

WORKDAY_START=10:00
WORKDAY_END=19:00
WORKDAYS=0,1,2,3,4

MIN_SLOT_MINUTES=30
SLOT_GRANULARITY_MINUTES=30
BUSY_BUFFER_MINUTES=30

GOOGLE_CALENDAR_IDS=primary
GOOGLE_CALENDAR_TOKEN_FILE=calendar_token.json
GOOGLE_CALENDAR_TOKEN_JSON=
GOOGLE_CLIENT_SECRET_FILE=credentials.json

SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
SLACK_ALLOWED_CHANNEL_ID=

LOG_LEVEL=INFO
```

config validationを実装する．

runtimeに必要な必須値が欠けている場合，起動時または利用前に明確なConfigErrorを出す．

---

# 22. `.gitignore`

最低限，

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

.env
.env.*

credentials.json
*credentials*.json
calendar_token.json
*token*.json

.DS_Store
```

等を除外する．

ただしexample設定ファイル，

```text
.env.example
```

はcommitしてよい．

秘密値は入れない．

---

# 23. Testing Policy

外部APIへ接続しないunit testを中心とする．

network accessなしで，

```text
pytest
```

が成功する状態を維持する．

Google Calendar API，Slack APIはmock/fakeを使用する．

---

# 24. Availability Tests

最低限以下をtestする．

### Case 1

business hours：

```text
10:00〜19:00
```

busyなし．

期待：

```text
10:00〜19:00
```

---

### Case 2

busy：

```text
12:00〜13:00
```

期待：

```text
10:00〜12:00
13:00〜19:00
```

---

### Case 3

busy：

```text
09:00〜11:00
```

期待：

```text
11:00〜19:00
```

---

### Case 4

busy：

```text
18:00〜20:00
```

期待：

```text
10:00〜18:00
```

---

### Case 5

busy：

```text
09:00〜20:00
```

期待：

```text
no availability
```

---

### Case 6

overlap：

```text
12:00〜14:00
13:00〜15:00
```

merge：

```text
12:00〜15:00
```

---

### Case 7

adjacent：

```text
12:00〜13:00
13:00〜14:00
```

merge：

```text
12:00〜14:00
```

---

### Case 8

odd minute：

```text
busy end = 14:10
```

candidate：

```text
14:30〜...
```

---

### Case 9

free end：

```text
17:20
```

candidate end：

```text
17:00
```

---

### Case 10

30分未満slot．

discardする．

---

### Case 11

現在時刻が今週途中．

過去の曜日と過去時刻を出さない．

---

### Case 12

来週．

月曜日から対象になる．

---

### Case 13

年末年始を跨ぐweek．

date calculationが正しい．

---

### Case 14

月跨ぎ．

正しい日付になる．

---

### Case 15

複数calendarのbusy interval．

unionされる．

---

# 25. Command Parser Tests

以下を認識：

```text
今週
 今週
今週 
今週の空き
今週の空き時間

来週
来週の空き
来週の空き時間
```

duration付きcommandとして，既存phraseに続くwhitespaceと30分単位の正の整数（例：`今週 60`）を認識する．`今週30`，`今週 45`，`今週 30分`などは認識しない．

以下には反応しない：

```text
今週は忙しい
こんにちは
空いてる？
今月
今日
明日
```

MVPで仕様にないものを推測して処理しない．

---

# 26. Slack Tests

最低限，

* allowed channelからのtriggerを処理
* 他channelを無視
* bot messageを無視
* subtype messageを無視
* unknown commandを無視
* thread rootを正しく選択
* Slack APIへ正しいchannel IDを送る
* Slack APIへ正しいthread_tsを送る

ことをtestする．

可能であればFastAPI TestClientを使用し，

* `/health`
* Slack URL verification
* invalid Slack signature

についてもtestする．

---

# 27. Google Calendar Tests

Google APIをmockして，

* token JSONからcredentialsを読み込める
* token fileからcredentialsを読み込める
* JSONが優先される
* multiple calendar IDをqueryする
* FreeBusy responseをTimeRangeへ変換する
* API errorをproject-specific exceptionへ変換する

ことをtestする．

実Google Calendarへの接続はunit testで行わない．

---

# 28. Quality Gate

各Phase終了前に最低限，

```bash
ruff check .
ruff format --check .
pytest
```

を実行する．

Phaseによってcoverage導入後は，

```bash
pytest --cov=free_time --cov-report=term-missing
```

も実行する．

core/domain logicは高いcoverageを維持する．

目標：

```text
core package >= 90%
```

外部adapterのcoverageを無理に100%へする必要はない．

---

# 29. Phase Plan

## PHASE 0 — Repository Bootstrap

目的：

安全に開発できる最小project skeletonを作る．

実装対象：

```text
pyproject.toml
.gitignore
.env.example
README.md skeleton
src/free_time/__init__.py
config.py
models.py
tests/
```

このPhaseでは，

* Slack APIを呼ばない
* Google APIを呼ばない
* Cloud Run deployしない
* business logicを完成させない

こと．

config parsingと最低限のtestsのみ作る．

Commit message例：

```text
phase-0: bootstrap free-time project
```

終了後STOP．

---

## PHASE 1 — Time Domain and Availability Engine

目的：

外部APIなしで空き時間計算を完成させる．

実装対象：

```text
core/periods.py
core/availability.py
models.py
tests/test_periods.py
tests/test_availability.py
```

完成条件：

* 今週
* 来週
* workday
* work hours
* busy merge
* subtraction
* 30分grid
* minimum slot
* current time filtering

がpure Pythonで動作する．

外部API接続は禁止．

Commit：

```text
phase-1: implement availability engine
```

終了後STOP．

---

## PHASE 2 — Command Parser and Formatter

目的：

Slack textからqueryを解釈し，結果をSlack向け文章へ変換する．

実装対象：

```text
core/command_parser.py
core/formatter.py
tests/test_command_parser.py
tests/test_formatter.py
```

Calendar API・Slack API接続は禁止．

Commit：

```text
phase-2: add command parser and formatter
```

終了後STOP．

---

## PHASE 3 — Google Calendar FreeBusy Integration

目的：

morning-brief-agentと互換性のあるGoogle OAuth credential handlingを追加し，FreeBusy APIからbusy intervalを取得する．

実装対象：

```text
services/google_calendar.py
config.py
tests/test_google_calendar.py
README.md
```

必須：

```text
GOOGLE_CALENDAR_TOKEN_JSON
GOOGLE_CALENDAR_TOKEN_FILE
GOOGLE_CALENDAR_IDS
```

既存 `calendar_token.json` をユーザーが再利用できるようにする．

testではnetworkを呼ばない．

Commit：

```text
phase-3: integrate Google Calendar freebusy
```

終了後STOP．

---

## PHASE 4 — Application Use Case

目的：

domainとCalendar serviceを接続する．

実装対象：

```text
app.py
tests/test_app.py
```

処理：

```text
Slack command
↓
period resolve
↓
FreeBusy取得
↓
availability calculation
↓
format
```

まだHTTP serverは実装しない．

fake Calendar serviceでtestする．

Commit：

```text
phase-4: wire availability use case
```

終了後STOP．

---

## PHASE 5 — Slack Events API

目的：

Slackからcommandを受け取り，replyできるようにする．

実装対象：

```text
services/slack.py
web.py
tests/test_web.py
README.md
```

使用：

```text
Slack Bolt
FastAPI
SlackRequestHandler
```

endpoint：

```text
GET /health
POST /slack/events
```

Slack request signature verification必須．

channel filtering必須．

bot message filtering必須．

thread reply必須．

Commit：

```text
phase-5: add Slack events integration
```

終了後STOP．

---

## PHASE 6 — Container and Cloud Run Readiness

目的：

Cloud Runへ安全にdeployできる状態にする．

実装対象：

```text
Dockerfile
README.md
deployment documentation
```

Docker containerは，

```text
PORT
```

環境変数を使用する．

Cloud Runではmin instancesを要求しない．

scale-to-zero可能な構成にする．

Codexはユーザーから明示的な許可がない限り，

* GCP project作成
* Cloud Run deploy
* Secret Manager作成
* billing変更
* IAM変更

を実行してはいけない．

このPhaseではdeploy commandをREADMEへ記載するだけでよい．

Commit：

```text
phase-6: prepare Cloud Run deployment
```

終了後STOP．

---

## PHASE 7 — Production Setup Documentation

目的：

ユーザーがSlackとGoogle Cloudの設定を迷わず完了できるようにする．

READMEへ以下を詳細記載する．

Slack App：

```text
Bot Token
Signing Secret
Event Subscriptions
message.channels
message.groups
chat:write
channels:history
groups:history
Request URL
Botのchannelへの招待
Channel ID取得
```

Google：

```text
Calendar API有効化
既存OAuth credential再利用
calendar_token.json再利用
Cloud Run用token JSON設定
```

Cloud Run：

```text
environment variables
secret handling
public endpoint
Slack request URL
health check
```

Commit：

```text
phase-7: document production setup
```

終了後STOP．

---

# 30. Manual Production Acceptance Test

実deploy後，人間と一緒に以下を確認する．

### Test A

Slack：

```text
今週
```

期待：

今週の空き時間がthread返信される．

---

### Test B

Slack：

```text
来週
```

期待：

来週月曜〜金曜の空き時間が返る．

---

### Test C

Google Calendarへテスト予定追加：

```text
13:00〜14:00
```

再実行．

期待：

その時間が候補から消える．

---

### Test D

別channel：

```text
今週
```

期待：

返信なし．

---

### Test E

通常文章：

```text
今週は研究が忙しい
```

期待：

返信なし．

---

### Test F

Calendar API unavailable想定．

期待：

安全なerror message．

stack traceやcredentialはSlackへ出ない．

---

# 31. Future Optional Phase — Duration Command

MVP完成後のみ検討する．

例えば，

```text
今週 60分
来週 30分
```

を追加する．

指定時間以上のslotだけを表示する．

MVP実装中に勝手に追加しない．

---

# 32. Future Optional Phase — Natural Language

将来的に，

```text
来週1時間空いてるところ
今週面接できる時間
金曜までで30分空いてるところ
```

等へ対応してもよい．

この段階でのみOpenAI API利用を検討する．

ただしLLMにはCalendar event titleを渡さず，原則busy/free intervalだけを渡す．

LLMの結果をavailabilityのsource of truthにしてはいけない．

日時計算は必ずPython domain logicで行う．

---

# 33. Future Optional Phase — Overseas Timezone

海外企業との面談用に，

```text
来週 America/New_York
来週 Europe/London
```

などを追加できる．

内部availabilityはAsia/Tokyo基準で計算し，表示時にtarget timezoneへ変換する．

DSTは `zoneinfo` に任せる．

固定UTC offsetをhard-codeしない．

MVP中に実装しない．

---

# 34. Future Optional Phase — Queue Architecture

以下が確認された場合のみ検討する．

```text
Slack requestが3秒を超える
Cloud Run cold startでtimeoutする
Slack retryによる重複返信が発生する
```

候補：

```text
Slack
↓
Cloud Run ingress
↓
Cloud Tasks / Pub/Sub
↓
worker
↓
Google Calendar
↓
Slack
```

MVPの段階で過剰設計しない．

---

# 35. Security Requirements

必須：

* Slack Signing Secret validation
* Allowed Channel filtering
* secretsをenvironment/secret storeで管理
* Calendar event detailsをSlackへ出さない
* Calendar event titlesをlogしない
* `.env`をcommitしない
* token JSONをcommitしない
* API exception全文をSlackへ返さない
* user inputからcalendar IDを直接指定させない
* user inputからshell commandを実行しない

---

# 36. Privacy Requirements

このBotの目的はavailability確認である．

以下の情報は不要なので取得・表示しない．

```text
event title
event description
event attendees
meeting URL
location
email address
private notes
```

FreeBusy APIからbusy rangesだけを扱う．

---

# 37. Performance Requirements

通常のSlack commandは可能な限り3秒以内に完了させる．

domain計算はmillisecond orderで完了するべきである．

1 commandにつきGoogle Calendar FreeBusy requestは原則1回．

calendarごとに個別HTTP requestを繰り返さない．

---

# 38. Do Not Overengineer

MVPで使用しないもの：

```text
database
Redis
Firestore
Celery
Kubernetes
React
frontend
OpenAI
LangChain
vector database
```

必要性が確認されるまで追加しない．

---

# 39. README Requirements

READMEは最終的に以下を含む．

```text
Project overview
Architecture
Local setup
Environment variables
Google OAuth setup
Existing calendar_token.json reuse
Slack App setup
Local run
Tests
Cloud Run deployment
Troubleshooting
Security notes
```

READMEだけ読めばユーザー自身がsetupできる状態を目指す．

---

# 40. Review Report Format

各Phase終了後，Codexは必ず以下の形式を最後に出力する．

```text
MODEL=Codex
PROJECT=free-time
PHASE=<phase number and name>

STARTING_HEAD=<sha>
ENDING_HEAD=<sha>

STATUS=AWAITING_GPT_REVIEW

CHANGED_FILES=<comma separated paths>

IMPLEMENTED=
- ...
- ...
- ...

TESTS=
- ruff check . : PASS/FAIL
- ruff format --check . : PASS/FAIL
- pytest : <result>
- coverage : <result if available>

NETWORK_CALLS_DURING_TESTS=0
SECRETS_COMMITTED=false
REAL_SLACK_MESSAGES_SENT=false
REAL_CALENDAR_MUTATIONS=0

KNOWN_LIMITATIONS=
- ...

NEXT_PHASE=<next phase>
NEXT_PHASE_STARTED=false
```

実際に実行していないtestをPASSと書いてはいけない．

分からない値を推測してはいけない．

---

# 41. Review Remediation Rules

ChatGPT reviewで問題が見つかった場合，

1. 指摘された問題だけを理解する
2. 最小修正案を立てる
3. regression testを追加する
4. 修正する
5. 全testを再実行する
6. 新規commitを作る
7. 結果を報告する
8. STOP

する．

review未完了のまま次Phaseへ進まない．

---

# 42. Definition of Done

MVP完了条件：

```text
Slack指定channelで「今週」と入力
↓
Google Calendar FreeBusy API
↓
今週のbusy time取得
↓
Pythonで空き時間計算
↓
30分gridへ正規化
↓
Slack threadへ一覧返信
↓
先方へ送れるcopy textも表示
```

加えて，

```text
「来週」が動作
他channelでは反応しない
Bot自身に反応しない
Calendar内容を漏らさない
secretをGitへ保存しない
unit testsが成功
Cloud Runで動作可能
```

こと．

---

# 43. 最初に実行する作業

このAGENTS.mdを初めて読んだCodexは，ユーザーから別のPhase指定がない限り，

```text
PHASE 0 — Repository Bootstrap
```

のみ実行する．

実装前に，

```bash
git status
git branch --show-current
git rev-parse HEAD
```

を確認する．

`ta1k1-arakawa/morning-brief-agent` を参照可能なら，関連実装を確認する．

その後Phase 0だけを実装する．

test・commit・可能ならpushを行い，Review Reportを出してSTOPする．

PHASE 1へ進んではならない．
