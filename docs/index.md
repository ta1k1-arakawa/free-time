---
layout: default
title: free-time
---

# free-time

個人利用のための、面談・面接の日程調整を支援するSlack Botです。

Slackの指定チャンネルで「今週」「来週」と投稿すると、
Google Calendarの予定が埋まっている時間帯を確認し、
調整可能な空き時間を計算してスレッドに返信します。

## Google Calendar情報の利用

Google Calendarへの読み取り権限を使用します。
FreeBusy APIで予定が埋まっている時間帯のみを取得します。

イベントのタイトル、説明、参加者、場所は取得しません。
計算した空き時間を、指定されたSlackチャンネルに表示します。

## 運営・お問い合わせ

運営者：ta1k1-arakawa
連絡先：taiki0305ara@gmail.com

## 関連ページ

- [プライバシーポリシー](privacy.html)
- [利用規約](terms.html)