# free-time

Slackの指定チャンネルで「今週」または「来週」を受け取ると、Google Calendar FreeBusy APIからbusy intervalだけを取得し、面談・面接調整用の候補時間を計算してSlack threadへ返信するBotです。

MVPのPython実装、Google Calendar FreeBusy連携、Slack Events API連携、FastAPI、Dockerfile、Cloud Run runtime対応、およびproduction setup documentationまで完成しています。実際のSlack workspace設定、Google Cloud resource作成、OAuth実行、Cloud Run deployはユーザーが行う作業であり、このrepositoryでは完了していません。

## Architecture

~~~text
Slack Events API -> Cloud Run -> FastAPI / Slack Bolt
  -> Command Parser -> FreeTimeApplication
  -> Google Calendar FreeBusy API -> Availability Calculator
  -> Formatter -> Slack thread reply
~~~

Calendar eventのタイトル、説明、参加者、場所、Meet URLなどは取得せず、busy intervalだけを扱います。MVPで認識するcommandは、今週、今週の空き、今週の空き時間、来週、来週の空き、来週の空き時間、および既存phrase末尾の30分単位のduration指定です。

## 前提条件

production setupを始める前に、次を準備してください。

- Google Cloud projectを選択または作成できること
- Google accountと、そのaccountから参照するGoogle Calendar
- Slack workspace
- Slack Appを作成・installできるworkspace権限
- Google Cloud CLI（gcloud）
- local Docker、またはDocker imageをbuildできる環境

Dockerを使えない場合は、Cloud BuildなどGoogle Cloud公式のimage build手順を選択できます。ただし、このprojectに新しいbuild infrastructureは追加していません。

Cloud RunとArtifact Registryは同一または近いregionに置くと管理しやすくなります。例としてasia-northeast1を使えますが、利用可能なregionを次のplaceholderに指定してください。

~~~text
<PROJECT_ID>
<REGION>
<REPOSITORY>
<IMAGE_URL>
<SERVICE_NAME>
<CLOUD_RUN_SERVICE_ACCOUNT>
<SLACK_CHANNEL_ID>
~~~

## Google Calendar準備

### 1. Google Cloud projectを選択

Google Cloud Consoleで対象projectを選択します。project IDはREADMEへ実値を書かず、以降のコマンドではPROJECT_ID placeholderを使います。

### 2. Google Calendar APIを有効化

Google Cloud ConsoleのAPI LibraryでGoogle Calendar APIを検索し、対象projectに対して有効化します。gcloudを使う場合の概念例は次のとおりです。これはユーザーが実行するコマンドであり、このrepositoryでは実行していません。

~~~powershell
gcloud services enable calendar-json.googleapis.com --project=<PROJECT_ID>
~~~

### 3. 参照対象Calendarを確認

初期設定はprimaryです。複数Calendarを使う場合は、Google Calendar上で対象CalendarのIDを確認し、GOOGLE_CALENDAR_IDSへcomma区切りで指定します。

~~~text
GOOGLE_CALENDAR_IDS=primary
GOOGLE_CALENDAR_IDS=primary,<CALENDAR_ID>
~~~

Calendar IDはSlack user inputから指定させず、Cloud Runの設定として管理してください。

## Google OAuth token準備

このprojectのOAuth scopeは次のreadonly scopeです。calendar write scopeは要求しません。

~~~text
https://www.googleapis.com/auth/calendar.readonly
~~~

scopeの意味とGoogle Calendar API固有の認可情報は、[Google Calendar API scopes](https://developers.google.com/workspace/calendar/api/auth)を確認してください。

### 既存 morning-brief-agent tokenを再利用する場合

既存のmorning-brief-agentで作成した calendar_token.json が、上記の calendar.readonly scopeを持つauthorized-user credentialであれば、localのfree-timeでも再利用できます。

Codexやscriptが別repositoryから自動copyすることはありません。ユーザー自身が必要に応じて、free-timeのrepository rootへ配置してください。

~~~text
free-time/
  calendar_token.json
~~~

配置後は次のlocal設定を使います。

~~~dotenv
GOOGLE_CALENDAR_TOKEN_FILE=calendar_token.json
GOOGLE_CALENDAR_TOKEN_JSON=
GOOGLE_CLIENT_SECRET_FILE=credentials.json
~~~

calendar_token.jsonはOAuth access token、refresh token、client information、scopeを含むsecretです。Gitへcommitせず、ログやSlack messageへ出力しないでください。scopeが不足している、またはrefresh tokenが無効になっている場合は、fresh OAuth手順で作り直してください。

### fresh Google OAuthを行う場合

Cloud Run上でInstalledAppFlowやbrowser OAuthを行わないでください。browser OAuthはlocalで完了させ、生成されたauthorized-user credentialをCloud Runへ安全に渡します。

1. Google Cloud ConsoleのGoogle Auth PlatformでBrandingを設定します。アプリ名、support email、developer contact informationなどを入力します。
2. Audienceで対象を設定します。個人でテストする場合は通常Externalを選択し、必要ならtest userを登録します。組織内専用ならorganizationの設定に従います。
3. ClientsでCreate clientを選び、OAuth client typeとしてDesktop appを作成します。
4. 生成したclient credentialをcredentials.jsonとして取得し、localのfree-time repository rootへ配置します。
5. GOOGLE_CALENDAR_TOKEN_JSONを設定せず、calendar_token.jsonがまだ存在しない状態にします。
6. GOOGLE_CLIENT_SECRET_FILE=credentials.json、GOOGLE_CALENDAR_TOKEN_FILE=calendar_token.jsonを設定します。
7. localのアプリケーション入口から、認証が必要なCalendar requestを一度発生させます。validな「今週」または「来週」の処理をlocalで実行すると、InstalledAppFlowがbrowserを開きます。
8. browserでGoogle accountとscopeを確認して許可します。
9. localにcalendar_token.jsonが生成されたことを確認します。

Google OAuthの一般的なDesktop app flowは、[Google OAuth 2.0 for installed applications](https://developers.google.com/identity/protocols/oauth2)を参照してください。credentials.jsonとcalendar_token.jsonはともにGitへcommitしないでください。

Cloud Runではlocal fileをimageへCOPYせず、authorized-user credential JSON全体をGOOGLE_CALENDAR_TOKEN_JSONとしてSecret Managerから注入します。JSONにはrefresh_token、client_id、client_secret、token URI、scopesなどが含まれるため、全体をsecretとして扱います。

## Slack App作成・設定

このprojectはsingle-workspace MVPです。複数workspace向けのSlack OAuth install flowは実装していません。

### 1. Slack Appを作成

Slack APIの管理画面でCreate New Appから新しいAppを作成し、対象workspaceを選択します。Appの設定画面は変更されることがあるため、最新の導線は[Slack authentication documentation](https://api.slack.com/authentication)を確認してください。

| Slack側の値 | free-timeの設定 | 用途 |
| --- | --- | --- |
| Bot User OAuth Token | SLACK_BOT_TOKEN | botがchat.postMessageで返信する |
| Signing Secret | SLACK_SIGNING_SECRET | Slack requestの署名検証 |
| 対象channelのID | SLACK_ALLOWED_CHANNEL_ID | 処理を許可するchannelの限定 |

Verification Tokenを使用する手順にはしないでください。実装はSlack Signing Secretによるrequest verificationを使用します。

### 2. Bot Token Scopes

OAuth & PermissionsのBot Token Scopesには、対象channelの種類に応じて必要最小限のscopeを追加します。

| 対象channel | Subscribe to bot events | 追加するhistory scope | 共通 |
| --- | --- | --- | --- |
| public channel | message.channels | channels:history | chat:write |
| private channel | message.groups | groups:history | chat:write |

public channelだけを使う場合はgroups:historyを要求せず、private channelだけを使う場合はchannels:historyを要求しません。public/privateの両方を使う場合だけ両方を設定します。

botを対象channelへinviteする前提なので、chat:write.publicは必須scopeとして要求しません。Slackのscopeは[Slack authentication](https://api.slack.com/authentication)と[OAuth scopes](https://api.slack.com/legacy/oauth-scopes)を参照してください。

このMVPで不要な設定はmessage.im、message.mpim、app_mention、slash command、Socket Modeです。

### 3. Install to Workspace

OAuth & PermissionsでInstall to Workspaceを実行し、Bot User OAuth Tokenを取得します。token実値をREADME、source code、Dockerfile、通常のenv fileへ書かず、Secret Managerへ保存してください。

scopeを後から変更した場合は、Reinstall to Workspaceが必要になることがあります。再install後のtokenを安全に保管し、古いtokenを不要なversionとして扱ってください。

### 4. Signing Secretを取得

Basic InformationのApp CredentialsにあるSigning Secretを取得し、Secret ManagerのSLACK_SIGNING_SECRETへ登録します。Signing Secretをログ出力したり、Verification Tokenで代用したりしないでください。

### 5. Botをchannelへinvite

Slack UIからbotを対象channelのmemberへ追加します。public channelでもprivate channelでも、botが参加していなければmessage eventを受け取れません。

対象channelのIDを確認し、channel名ではなくIDを設定します。

~~~text
SLACK_ALLOWED_CHANNEL_ID=<SLACK_CHANNEL_ID>
~~~

これにより、別channelのmessageはapplicationとCalendarへ渡らず、Slack replyも発生しません。

### 6. Event Subscriptions

Cloud Runへdeployした後、Slack AppのEvent SubscriptionsをOnにし、Request URLへ次を設定します。

~~~text
<CLOUD_RUN_URL>/slack/events
~~~

ここで<CLOUD_RUN_URL>はscheme込みの完全なURLを表します。たとえばhttps://xxxxx.run.appのような値をそのまま置換してください。<CLOUD_RUN_URL>の前にhttps://を追加しないでください。

public channelはmessage.channels、private channelはmessage.groupsをSubscribe to bot eventsへ追加します。DM、MPIM、app_mention、slash commandは対象外です。

SlackはRequest URLへsigned url_verification requestを送り、challengeを返せることを確認してから保存します。詳細は[Slack HTTP request URLs](https://api.slack.com/apis/http)と[Slack Events API](https://api.slack.com/apis/connections/events-api)を参照してください。

## Google Cloud / Secret Manager準備

### 1. 必要なGoogle Cloud service

productionではCloud Run、Artifact Registry、Secret Manager、Google Calendar APIを利用します。Cloud BuildはCloud Buildでimageをbuildする場合だけ必要です。

ConsoleのAPI Libraryから有効化するか、次のplaceholder commandをユーザーのprojectで実行します。このrepositoryからは実行していません。

~~~powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com calendar-json.googleapis.com --project=<PROJECT_ID>
~~~

Cloud Buildを使う場合だけcloudbuild.googleapis.comも有効化します。

### 2. Artifact Registry repository

Docker repositoryを作成します。Artifact RegistryとCloud Runは同一または近いregionを選ぶと管理しやすくなります。

~~~powershell
gcloud artifacts repositories create <REPOSITORY> --repository-format=docker --location=<REGION> --project=<PROJECT_ID>
~~~

image URLは次の形式です。

~~~text
<REGION>-docker.pkg.dev/<PROJECT_ID>/<REPOSITORY>/free-time:<TAG>
~~~

### 3. Cloud Run service identity

Cloud Runのservice identityとして、専用または既存の次のservice accountを選択します。

~~~text
<CLOUD_RUN_SERVICE_ACCOUNT>
~~~

このservice accountには、Cloud Runが参照する各secretについてroles/secretmanager.secretAccessorを付与します。project全体へ広く付与せず、必要なsecret単位のIAM bindingを優先してください。

~~~powershell
gcloud secrets add-iam-policy-binding <SECRET_NAME> --member="serviceAccount:<CLOUD_RUN_SERVICE_ACCOUNT>" --role="roles/secretmanager.secretAccessor" --project=<PROJECT_ID>
~~~

上記はIAM mutationの例です。実行前にorganization policy、service account、secret単位の権限を確認してください。このrepositoryからは実行していません。

### 4. Secret Managerへ登録

次の3つを別々のsecretとして管理します。

| Environment variable | Secret nameの例 | 内容 |
| --- | --- | --- |
| SLACK_BOT_TOKEN | free-time-slack-bot-token | SlackのBot User OAuth Token |
| SLACK_SIGNING_SECRET | free-time-slack-signing-secret | Slack AppのSigning Secret |
| GOOGLE_CALENDAR_TOKEN_JSON | free-time-google-calendar-token | authorized-user credential JSON全体 |

secret nameはplaceholderとして扱い、実際の名前はユーザーのprojectの命名規則に合わせます。secretの値をgcloud commandの引数へ直接書いたり、shell historyへ残したりしないでください。

Google token JSONはlocalのcalendar_token.jsonのfile contentをSecret Managerへ登録する方法を推奨します。

~~~powershell
gcloud secrets create <GOOGLE_TOKEN_SECRET_NAME> --replication-policy=automatic --project=<PROJECT_ID>
gcloud secrets versions add <GOOGLE_TOKEN_SECRET_NAME> --data-file=<PATH_TO_CALENDAR_TOKEN_JSON> --project=<PROJECT_ID>
~~~

SlackのtokenとSigning SecretはGoogle Cloud ConsoleのSecret Manager UIから入力するか、保護されたlocal fileをdata-fileへ渡します。actual valueをREADMEへ貼り付けないでください。

Cloud Runへenvironment variableとして渡すsecretは、latestではなく明示的なversion number（例：1、2）を優先します。secret environment variableはinstance startup時に解決されるため、versionを固定するとrotationとrevisionの関係を明確にできます。詳細は[Cloud Run secrets configuration](https://cloud.google.com/run/docs/configuring/services/secrets)を参照してください。

## Container image build / push

Phase 6のDockerfileはPython 3.11 slim image、production dependencyのみ、non-root user、Uvicorn factoryを使用します。コンテナは0.0.0.0でCloud Runが注入するPORTをlistenします。PORTをDockerfileやCloud Run設定で固定しないでください。

local Dockerが使える場合は次の順でbuildします。

~~~powershell
docker build -t <IMAGE_URL> .
gcloud auth configure-docker <REGION>-docker.pkg.dev
docker push <IMAGE_URL>
~~~

Artifact Registryのimage pathとpush手順は[Artifact Registry Docker quickstart](https://cloud.google.com/artifact-registry/docs/docker/store-docker-container-images)を参照してください。Dockerが使えない場合はCloud Buildなど公式image build手段を選択してください。Phase 6時点ではこの環境でDocker CLIが利用できず、Docker buildは検証していません。

Docker build contextへ.env、calendar_token.json、credentials.json、Google token JSON、Slack token、Signing Secret、.git、.venv、tests、cacheを含めないでください。これらは.dockerignoreで除外されています。

## Cloud Run deploy

### 1. non-secret env fileを作る

secretを入れないnon-secret env fileだけをlocalで作成します。ファイルはGitへcommitせず、secret値を混在させないでください。

~~~dotenv
APP_TIMEZONE=Asia/Tokyo
WORKDAY_START=10:00
WORKDAY_END=19:00
WORKDAYS=0,1,2,3,4
MIN_SLOT_MINUTES=30
SLOT_GRANULARITY_MINUTES=30
BUSY_BUFFER_MINUTES=30
GOOGLE_CALENDAR_IDS=primary
SLACK_ALLOWED_CHANNEL_ID=<SLACK_CHANNEL_ID>
LOG_LEVEL=INFO
~~~

複数Calendarを使う場合はGOOGLE_CALENDAR_IDS=primary,<CALENDAR_ID>相当です。commaを含む値をshellのset-env-varsへ直接渡すとdelimiterの扱いで誤ることがあるため、env-vars-fileを推奨します。GOOGLE_CALENDAR_TOKEN_FILEとGOOGLE_CLIENT_SECRET_FILEはCloud Run productionの基本経路では設定しません。

BUSY_BUFFER_MINUTESはCalendarのbusy intervalを前後へ広げるbufferです。既定値は30分で、0を指定するとbufferを無効化できます。commandは「今週 60」のように既存phraseの後へ空白と30分単位の正の整数を付けられます。

### 2. deployする

Cloud Run serviceはデフォルトでは認証が必要です。Slack Events APIから認証なしのHTTPS requestを受けるにはpublic invocationが必要です。現行Cloud Run documentationで推奨されるpublic化はInvoker IAM checkを無効にする方法です。

次のcommandは完全なplaceholder例です。ユーザーが自分のprojectで実行するものであり、このrepositoryからは実行していません。

~~~powershell
gcloud run deploy <SERVICE_NAME> --project=<PROJECT_ID> --region=<REGION> --image=<IMAGE_URL> --service-account=<CLOUD_RUN_SERVICE_ACCOUNT> --env-vars-file=<NON_SECRET_ENV_FILE> --set-secrets="SLACK_BOT_TOKEN=<SLACK_BOT_TOKEN_SECRET_NAME>:1,SLACK_SIGNING_SECRET=<SLACK_SIGNING_SECRET_NAME>:1,GOOGLE_CALENDAR_TOKEN_JSON=<GOOGLE_TOKEN_SECRET_NAME>:1" --no-invoker-iam-check
~~~

organization policyやCLI versionにより別のpublic access手順が必要な場合は、Cloud Run ConsoleのAllow public accessを選択するか、代替として次を使います。

~~~powershell
gcloud run deploy <SERVICE_NAME> --project=<PROJECT_ID> --region=<REGION> --image=<IMAGE_URL> --allow-unauthenticated
~~~

--allow-unauthenticatedは環境によってallUsersへのInvoker IAM bindingを使う従来方式です。いずれの方式でもSlack requestはSigning Secretで検証されます。公開endpointとSlack署名検証を役割分担させます。

Cloud RunはPORTを自動注入するため、ユーザーがPORTを手動設定する必要はありません。Dockerfileは0.0.0.0とPORTを使います。minimum instanceを指定せず、MVPはscale-to-zero可能な構成にします。--min=1やalways-on instanceを必須にしないでください。

### 3. URLとhealth checkを確認

deploy成功後にCloud RunがHTTPS URLを提供します。

~~~powershell
gcloud run services describe <SERVICE_NAME> --region=<REGION> --project=<PROJECT_ID> --format="value(status.url)"
~~~

得られたURLをCLOUD_RUN_URLとして次を確認します。

~~~text
GET <CLOUD_RUN_URL>/health
期待値: {"status":"ok"}
~~~

healthはGoogle Calendar、Slack API、OAuth refreshを呼びません。起動時のnetwork dependencyがないことも確認してください。

## Slack Request URL設定

Cloud Run deployとhealth checkが成功したら、Slack AppのEvent Subscriptionsへ戻ります。

1. Event SubscriptionsをOnにします。
2. Request URLへ<CLOUD_RUN_URL>/slack/eventsを入力します。
3. Slackのsigned url_verificationを通過し、challengeが返ることを確認します。
4. public channelならmessage.channels、private channelならmessage.groupsをSubscribe to bot eventsへ追加します。
5. Save Changes後、botが対象channelへinvite済みであることを確認します。

Request URLはcase-sensitiveです。SlackのURL verificationが成功しない場合は、Troubleshooting — Slackを確認してください。

## 動作確認

次の順番でmanual acceptanceを行います。

- GET <CLOUD_RUN_URL>/healthがHTTP 200で、bodyが{"status":"ok"}である
- Slack Event SubscriptionsのRequest URL verificationが成功する
- botがallowed channelへinvite済みである
- allowed channelで「今週」を投稿すると、同じmessage threadへ空き時間が返信される
- allowed channelで「来週」を投稿すると、来週の候補が同じthreadへ返信される
- top-level messageにはそのmessageのtsをthread rootとして返信される
- thread内のmessageには既存thread_tsへ返信される
- 他channelの「今週」には返信しない
- 「こんにちは」「今週は忙しい」には返信しない
- Calendar上のbusy intervalが候補から除外される
- 空きがない場合は「条件に合う空き時間はありませんでした．」となり、先方送信用sectionを出さない

### Calendar busyのmanual test

Google Calendarへ、ユーザー自身が一時的な15:00〜16:00の予定を追加します。次にSlackで「今週」を投稿し、その時間帯が候補から除外されることを確認してください。確認後はテスト予定をユーザー自身で削除してください。Codexや本projectはCalendar eventを作成・削除しません。

Botの返答は新しいtop-level messageではなく、元のSlack messageのthread内に表示されることが成功条件です。

## Troubleshooting

### Slack

- Request URL verificationに失敗する場合：Cloud Run URLにhttps://を付け、末尾が/slack/eventsであること、public invocationが許可されていること、コンテナが起動していることを確認します。
- invalid Slack signatureになる場合：SLACK_SIGNING_SECRETが対象AppのSigning Secretと一致することを確認します。actual secretをログへ出して確認しないでください。
- botが返信しない場合：Event Subscriptionsのmessage.channelsまたはmessage.groups、Bot Token Scopes、botのchannel invite、Cloud Run logsを順番に確認します。
- 他channelで返信しない場合：仕様どおりの動作です。SLACK_ALLOWED_CHANNEL_IDが対象channelのIDと完全一致することだけを確認します。
- scopeを追加した後に動かない場合：Slack AppをReinstall to Workspaceし、更新後のBot User OAuth TokenをSecret Managerの新versionへ登録してCloud Run revisionを更新します。
- botがchannelへinviteされていない場合：対象channelへbotをmemberとして追加します。scopeだけではprivate channelのmessageを受け取れません。
- SlackのEvent typeとchannel typeが合わない場合：publicはmessage.channelsとchannels:history、privateはmessage.groupsとgroups:historyの組み合わせを確認します。

### Google Calendar

- 「Google Calendarから予定を取得できませんでした」と返る場合：Cloud Run logsの安全なエラー情報を確認し、tokenの実値やcredential JSONをログへ出さないでください。
- refresh tokenがinvalidまたはrevokedの場合：localでOAuthをやり直し、新しいcalendar_token.jsonを作成します。
- calendar_token.json由来JSONが古い場合：localで再認証し、Secret Managerへ新versionとして登録します。
- Calendar APIが有効でない場合：対象PROJECT_IDのAPI LibraryでGoogle Calendar APIを有効化します。
- OAuth clientまたはconsent設定に問題がある場合：Google Auth PlatformのBranding、Audience、Clients、test user設定を確認します。
- GOOGLE_CALENDAR_TOKEN_JSONが正しいJSONでない場合：localのauthorized-user credential JSON全体をfileから再登録し、JSON本文をshell argumentに貼り付けないでください。
- Calendar IDが間違っている場合：Google Calendar側でIDを確認し、GOOGLE_CALENDAR_IDSを更新します。
- 修正後はSecret Managerへ新versionを追加し、Cloud Runを新secret versionを参照するrevisionへ更新します。Cloud RunではInstalledAppFlowを実行せず、OAuthはlocalで完了させます。

### Cloud Run

- container startup failureの場合：Cloud Run revision logsでimport error、dependency install、Uvicorn起動失敗を確認します。secret値をログへ出さないでください。
- secret permission failureの場合：Cloud Run service identityに、必要な各secretへのroles/secretmanager.secretAccessorが付与されているか確認します。
- /healthが開けない場合：service URL、region、revision status、public invocation、containerが0.0.0.0でlistenしていることを確認します。
- public invocation設定に問題がある場合：Cloud RunのAllow public accessまたは--no-invoker-iam-checkの状態を確認します。組織のpolicyにより許可されない場合は管理者へ相談します。
- PORTを手動overrideした場合：Cloud Runが注入するPORTを上書きせず、Dockerfileの0.0.0.0とPORT相当の起動を維持します。
- Cloud Run logsを確認する場合：token、Signing Secret、refresh token、credential JSON、private Calendar dataを出力しないでください。

## Security / secret rotation

### Security checklist

- .envをcommitしない
- calendar_token.jsonをcommitしない
- credentials.jsonをcommitしない
- Slack Bot Tokenをcommitしない
- Slack Signing Secretをcommitしない
- Docker imageへsecretをCOPYしない
- logsへsecretやCalendar event detailsを出力しない
- Slack Signing Secret verificationを無効化しない
- Cloud Run secretはSecret Managerからversion固定で注入する
- Google Calendar scopeはcalendar.readonlyを使用し、write scopeを要求しない
- allowed channelはSLACK_ALLOWED_CHANNEL_IDで限定する
- Calendar eventのtitle、description、attendees、location、Meet URLを取得・表示しない

### Slack secret rotation

1. Slack AppでtokenまたはSigning Secretをrotateします。
2. Secret Managerへ新versionを追加します。
3. Cloud Run deployまたはservice updateで新しいversion numberを指定します。
4. 新revisionのhealth、Slack URL verification、thread replyを確認します。
5. 動作確認後、旧secret versionをdisableまたは削除します。

tokenやSigning Secretのactual valueを表示して確認する手順は行いません。

### Google secret rotation

1. localでGoogle OAuthを再認証します。
2. 新しいcalendar_token.jsonを作成します。
3. 既存のGoogle token secretへ新versionを追加します。
4. Cloud Runを新versionへ更新して新revisionを作成します。
5. 「今週」「来週」とhealthを確認します。
6. 旧versionを不要になった時点でdisableします。

Secret Managerの値をCloud Runへenvironment variableとして渡す場合は、latestではなくversion numberを使う運用を推奨します。

## Known limitations

- Slack Events APIはprocess_before_response=Trueで、Google FreeBusy request、availability計算、Slack chat.postMessageをHTTP response前に実行します。
- Cloud Run cold startやGoogle API latencyによってSlackの3秒response制限に近づく可能性があります。production validationで実測してください。
- 遅延やSlack retryが実測された場合のfuture improvementとしてCloud Tasks、Pub/Sub、Redis、Celery、background workerを検討できますが、このMVPには導入していません。
- single-workspace MVPであり、Slack OAuthのmulti-workspace install flowは実装していません。
- Slack DM、MPIM、app_mention、slash commandは対象外です。
- command parserは今週・来週の固定phraseと、末尾に空白区切りで指定した30分単位のdurationだけを認識します。自然言語、durationの「分」表記、timezone指定は対象外です。
- 実際のSlack workspace setup、Google OAuth、Secret Manager、Artifact Registry、Cloud Run deploy、IAM変更はmanual user operationです。

## Local setup

Python 3.11以上とsrc layoutを使用します。dependencyとtool設定のsource of truthはpyproject.tomlです。

~~~powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
~~~

local developmentでは、GOOGLE_CALENDAR_TOKEN_FILE=calendar_token.jsonを使うか、credentials.jsonを配置してInstalledAppFlowを開始します。Cloud RunではGOOGLE_CALENDAR_TOKEN_JSONをSecret Managerから注入し、local file OAuth fallbackを基本経路にしません。

## Tests

~~~powershell
ruff check .
ruff format --check .
pytest
pytest --cov=free_time --cov-report=term-missing
~~~

unit testはGoogle Calendar、Slack、networkへ接続しません。Google credential loader、FreeBusy response parsing、Slack request verification、channel filtering、application flowはfakeまたはmockで確認します。

## Phase plan

1. Phase 0 — Repository Bootstrap（complete）
2. Phase 1 — Time Domain and Availability Engine（complete）
3. Phase 2 — Command Parser and Formatter（complete）
4. Phase 3 — Google Calendar FreeBusy Integration（complete）
5. Phase 4 — Application Use Case（complete）
6. Phase 5 — Slack Events API（complete）
7. Phase 6 — Container and Cloud Run Readiness（complete）
8. Phase 7 — Production Setup Documentation（complete）

MVP implementation and production setup documentation are complete. Actual production deployment、Slack workspace setup、Google Cloud resource creation、OAuth実行、IAM変更はユーザーのmanual operationとして残っています。

## Official references

- [Slack authentication](https://api.slack.com/authentication)
- [Slack Events API](https://api.slack.com/apis/connections/events-api)
- [Slack HTTP request URLs](https://api.slack.com/apis/http)
- [Slack message events](https://api.slack.com/events/message)
- [Slack request verification](https://api.slack.com/docs/verifying-requests-from-slack)
- [Google Calendar API scopes](https://developers.google.com/workspace/calendar/api/auth)
- [Google OAuth 2.0 for installed applications](https://developers.google.com/identity/protocols/oauth2)
- [Artifact Registry Docker images](https://cloud.google.com/artifact-registry/docs/docker/store-docker-container-images)
- [Cloud Run container runtime contract](https://cloud.google.com/run/docs/container-contract)
- [Cloud Run secrets](https://cloud.google.com/run/docs/configuring/services/secrets)
- [Cloud Run public access](https://cloud.google.com/run/docs/authenticating/public)

このREADMEのcommandはplaceholderを使ったユーザー向け例です。CodexはGoogle Cloud、Slack、Google OAuth、Secret Manager、Artifact Registry、Cloud Runのmutationを実行していません。
