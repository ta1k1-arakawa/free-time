---
layout: default
title: プライバシーポリシー
permalink: /privacy.html
---

# プライバシーポリシー

free-timeは、運営者本人が面談・面接の日程調整に使用する個人用のSlack Botです。

## 取得する情報と利用目的

Google CalendarのFreeBusy APIから、指定期間の予定が埋まっている時間帯を取得します。
取得した時間帯から空き時間を計算し、Slackの指定チャンネルのスレッドへ返信します。

Google Calendarへの読み取り権限を使用しますが、イベントのタイトル、説明、参加者、場所、会議URLは取得しません。
予定の作成・変更・削除も行いません。

Slackからは、メッセージ本文、チャンネルID、メッセージやスレッドを識別する情報を処理に使用します。

## 保存と管理

取得した予定の時間帯はメモリ上で計算に使用し、アプリ専用のデータベースやファイルには保存しません。
Googleへのアクセスに必要なOAuth認証情報は、ローカルの認証ファイルまたはGoogle Cloud Secret Managerで管理します。
認証情報はアクセス権を取り消すか運営者が削除するまで保管されます。

計算した空き時間はSlackに投稿され、ワークスペースの保存設定に従って保持されます。
指定チャンネルの参加者は、その投稿を閲覧できます。

## 外部サービスとデータの共有

本アプリの処理にはGoogle Calendar、Google Cloud、Slackを使用します。
説明ページはGitHub Pagesで公開しています。
各サービスによるデータの取り扱いには、各サービスの規約とプライバシーポリシーが適用されます。

Googleユーザーデータを販売せず、広告目的でも利用しません。
OpenAI APIなどの生成AIサービスへ送信しません。
Google APIから取得した情報の利用・他のアプリへの転送は、
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy)のLimited Use要件に従います。

## アクセスの取り消しと削除

[Googleアカウントの接続設定](https://myaccount.google.com/connections)から、本アプリへのアクセス権限を取り消せます。
取り消した後は、その認証情報で新しいCalendar情報を取得できません。

保存済み認証情報の削除は、ローカルファイルやSecret Managerで運営者が行います。
既存のSlack投稿はアクセス権の取り消しでは削除されません。Slack上で削除するか、ワークスペース管理者へ依頼してください。
削除についてのお問い合わせは、下記の連絡先で受け付けます。

## お問い合わせ

運営者：ta1k1-arakawa

連絡先：[taiki0305ara@gmail.com](mailto:taiki0305ara@gmail.com)

最終更新日：2026年10月9日

[ホームへ戻る](./)
