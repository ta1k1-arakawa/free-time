# GitHub Actions CI / CD

## このrepositoryの設定状況（2026-10-19）

既存projectへのCD初期設定を完了しました。GitHubの接続variablesと`CD_ENABLED=true`を登録し、`production` environmentのdeployment branchをmainだけに制限しています。

| 項目 | 設定値 |
| --- | --- |
| Google Cloud project | `free-time-509005`（number: `24634453019`） |
| Region | `asia-northeast1` |
| Artifact Registry / Cloud Run service | どちらも`free-time` |
| Deploy service account | `free-time-deploy@free-time-509005.iam.gserviceaccount.com` |
| Runtime service account | `free-time-run@free-time-509005.iam.gserviceaccount.com` |
| WIF pool / provider | `free-time-github` / `github` |

WIFは下記のrepository ID・owner ID・main・CI workflowの条件で制限しています。deploy用アカウントの権限は対象registryのwriter、対象Cloud Runのdeveloper、runtimeアカウントのserviceAccountUserです。service account keyは作成していません。

設定時点でPR #1は未mergeです。人間がPR #1をmainへmergeすると初回のCDが起動します。実際のGitHub OIDC認証・image push・Cloud Run更新を通した検証は、その初回実行で確認してください。設定作業だけで既存の本番revisionを変更していません。

## 自動化する範囲

`.github/workflows/ci.yml` はpush、pull request更新、Actions画面からの手動実行で起動します。

- Python 3.11 / 3.13で`pip install -e '.[dev]'`
- `ruff check .`と`ruff format --check .`
- 外部サービスをfake/mockにした全unit testとcoverage計測
- core packageのcoverageが90%以上であること
- Docker build、non-root実行、任意のPORTでの`/health`応答

CIにはSlackやGoogle Calendarの本物の認証情報は不要です。Docker smoke testは架空の設定値を使い、Slackへの投稿やCalendarアクセスを行いません。依存パッケージのダウンロードにはnetworkを使用します。

CIは自動でmergeしません。mainのruleset / branch protectionで次の3つをrequired status checksに指定すると、失敗したPRのmergeを防げます。初回の実行後に選択してください。

- `Quality (Python 3.11)`
- `Quality (Python 3.13)`
- `Container smoke test`

## CDの動作

CDは初期状態では無効です。repository variable `CD_ENABLED`が文字列`true`で、mainへのpushのCIがすべて成功した場合だけ、同じcommitをビルドしてCloud Runへ反映します。PR、他branch、手動実行からはdeployしません。mainへのmergeはmainへのpushを発生させます。

production environmentの承認ルールがある場合は承認後に続行します。完全自動にする場合、required reviewersを設定しない運用を選択できます。

imageにはcommit SHAをtagとして付け、push後のdigestをCloud Runへ指定します。既存serviceのimageを更新し、最新revisionへtrafficを100%移します。古いcommitの実行はdeploy直前にmainの先端を確認してskipします。deployは同時実行せず、実行中のdeployをcancelしません。更新直後にさらにmainが進む場合は、次の成功した実行が続けて反映します。

既存のruntime service account、環境変数、Secret Manager参照、public access設定を使用します。新規Cloud Run serviceやIAM policyをworkflowから作成しません。初回構築はREADMEのproduction setupに従って完了させてください。

deploy後は公開URLの`/health`を確認します。失敗時はActionsが失敗になり、自動rollbackは行いません。必要ならCloud Run Consoleから直前の正常revisionへtrafficを戻します。実際のSlack thread返信はmanual acceptance testで確認してください。

## 初回設定

以下は管理者が一度設定する手順です。この変更をcommit / pushするだけでは、Google Cloudのリソース・IAMやGitHubのvariablesは作成されません。

### 1. 既存のデプロイ先を用意する

- Google Cloud projectと有効なCloud Run / Artifact Registry / IAM / Security Token Service API
- Docker形式のArtifact Registry repository
- 起動・公開設定済みのCloud Run service
- runtime service accountへの必要なSecret Managerアクセスと、versionを固定した3つのsecret参照
- SlackのRequest URLと`/health`の動作確認

Slack token、Signing Secret、Calendar token JSONは引き続きSecret Managerで管理します。GitHubへコピーする必要はありません。

### 2. GitHub OIDC認証を設定する

長期のservice account key JSONではなく、Workload Identity Federationを使用します。

1. deploy用service accountを作成します。Cloud Runのruntime identityとは分けます。
2. Workload Identity PoolとGitHub OIDC Providerを作成します。issuerは`https://token.actions.githubusercontent.com`です。
3. attribute mappingを`google.subject=assertion.sub,attribute.repository_id=assertion.repository_id`にします。
4. Providerのattribute conditionを次のように制限します。このrepositoryのIDは`1374419228`、owner IDは`177127839`です。移管・別repositoryへの転用時には確認し直してください。

~~~text
assertion.repository_owner_id == '177127839' && assertion.repository_id == '1374419228' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref == 'ta1k1-arakawa/free-time/.github/workflows/ci.yml@refs/heads/main'
~~~

5. deploy用service accountに、次のprincipalSetをmemberとして`roles/iam.workloadIdentityUser`を付与します。`PROJECT_NUMBER`はproject IDではなく数値です。

~~~text
principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/attribute.repository_id/1374419228
~~~

6. deploy用service accountには、対象Artifact Registry repositoryへの`roles/artifactregistry.writer`、対象Cloud Run serviceへの`roles/run.developer`、runtime service accountへの`roles/iam.serviceAccountUser`を付与します。workflowはIAM変更をしないため`roles/run.admin`は不要です。組織policyに応じて管理者が適用範囲を確認してください。

詳細は[Google CloudのGitHub Actions向けWIF設定](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines#github-actions)、[auth Action](https://github.com/google-github-actions/auth)、[Cloud Runのdeploy権限](https://cloud.google.com/run/docs/deploying#required_roles)を参照してください。

### 3. GitHub variablesとenvironmentを設定する

Settings → Environmentsで`production`を作成し、deployment branchをmainに制限します。

Settings → Secrets and variables → Actions → Variablesで、次のrepository variablesを登録します。いずれも認証secretの実値ではありません。

| Variable | 値の例 / 意味 |
| --- | --- |
| `GCP_PROJECT_ID` | 既存のproject ID |
| `GCP_REGION` | `asia-northeast1`など、既存serviceとregistryのregion |
| `ARTIFACT_REGISTRY_REPOSITORY` | repository名のみ。例：`free-time` |
| `CLOUD_RUN_SERVICE` | 既存のCloud Run service名 |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | deploy用service accountのemail |
| `CD_ENABLED` | 準備完了後に`true`を設定。未設定または`false`ならdeployをskip |

registryとserviceが別regionにある既存環境では、workflowのregistry hostnameとCloud Run regionを分けてから有効化してください。

### 4. 有効化と確認

1. まずPRのCIがすべて成功することを確認します。
2. WIF・権限・既存service・上記variablesを設定します。
3. `CD_ENABLED=true`にして、レビュー済みPRを人間がmainへmergeします。
4. mainのCI成功後に`Deploy to Cloud Run`が成功し、health checkが通ることを確認します。
5. Slackで「再来週 90分」を送り、同じthreadに90分以上の連続した候補が返ることを確認します。

variablesを変更するだけでは新しいworkflowは起動しません。すでにmainへmerge済みの場合は、そのmain pushのworkflowをre-runするか、次のレビュー済みcommitをmainへ反映してください。Actionsの手動実行ではCIだけを実行します。

停止したい場合は`CD_ENABLED=false`にします。すでに実行中のdeployを停止する必要がある場合は、Actions画面から該当runも確認してください。
