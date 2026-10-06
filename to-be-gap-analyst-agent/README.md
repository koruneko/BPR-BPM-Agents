# To-Be Gap Analyst Agent

Microsoft 365 Copilot Agent Builder の Skills 機能を利用して、BPM Agent で整理した現在の業務と BPR Agent で設計した変更後の業務を比較し、Gapと次の確認・決定・準備を整理するエージェントです。

## Overview

To-Be Gap Analyst Agent は、As-Is と採用された To-Be の差分を追跡し、業務・システム・データ・人とスキル・役割・ルール・管理・測定の観点から Gap を整理します。

Gap を列挙するだけではなく、利用者との対話を通じて、優先する Next Action、最初の一歩、相談する役割、得たい結果、前後関係、持ち越す確認事項を具体化します。必要な場合は、日本の営業日を考慮した日程も追加できます。

## Flow

1. BPM の `process.yaml` と BPR の `to-be-process.yaml`、`improvement-analysis.yaml`、`improvement-decisions.yaml` を照合
2. As-Is / To-Be の差分、影響、根拠、未確認事項を Gap として整理
3. 優先する Next Action と、最初の一歩・相談相手・得たい結果・前後関係を対話で整理
4. 必要に応じて営業日ベースの日程を追加
5. Gap分析データ、一覧、詳細レポート、ロードマップ、依存関係図を生成

全ての未確認事項の解消、担当者の確定、実見積、詳細日程、実装、本番移行までをエージェントの完了条件にはしません。未確定事項は、次に誰と何を確認するかへつなげます。

## Recommended Inputs

新規の Gap 分析では、次の4ファイルを主要入力として使用します。

- BPM Agent の `process.yaml`
- BPR Agent の `to-be-process.yaml`
- BPR Agent の `improvement-analysis.yaml`
- BPR Agent の `improvement-decisions.yaml`

BPR 側の資料だけでも分析できますが、As-Is がない場合は現在との差分を暫定扱いにします。既存の `gap-analysis.json` は、継続相談や改版に利用できます。

## Contents

| Path | Role |
|---|---|
| [agent-instructions.md](./agent-instructions.md) | To-Be Gap Analyst Agent 全体の Instructions |
| [bpr-gap-analysis](./bpr-gap-analysis/) | As-Is / To-Be の比較、Gap・実施課題・根拠・未決事項の分析 |
| [gap-planning-current](./gap-planning-current/) | Next Action、優先度、順序、前後関係の対話整理 |
| [gap-delivery](./gap-delivery/) | Gap分析データからレポート・一覧・ロードマップを生成 |
| [gap-report-format](./gap-report-format/) | レポートの日本語表現・表・配色・表示処理 |
| [gap-business-calendar](./gap-business-calendar/) | 日本の営業日を使った任意の日程計算 |

各 Skill の詳細な指示や実装は、それぞれのディレクトリ内の `SKILL.md`、`references/`、`scripts/` を参照してください。

## Package

Microsoft 365 Copilot Agent Builder へのインポートには、リポジトリ直下の [To-Be Gap Analyst Agent.zip](../To-Be%20Gap%20Analyst%20Agent.zip) を利用してください。

## Relationship with BPM / BPR Agents

このエージェントは BPM Agent と BPR Agent の後工程を想定しています。

- [BPM Agent の詳細](../bpm-agent/)
- [BPR Agent の詳細](../bpr-agent/)

BPM Agent で現在の業務を構造化し、BPR Agent で採用した改善案を反映した To-Be を設計した後、その差分を実行可能な確認・決定・準備へつなげます。
