# BPR / BPM Agents

Microsoft 365 Copilot Agent Builder の Skills 機能を利用した、業務プロセスの可視化・分析・改善を支援するエージェントです。

## Agents

### BPM Agent

ユーザーとの対話から業務プロセスを整理し、構造化します。

主な処理:

- 担当者、処理、条件分岐、差し戻し、例外、並行処理、利用システム、入出力を整理
- `process.yaml` を業務プロセスの基準定義として生成
- 構造・参照・Gateway・到達性・入出力などをレビュー
- 検証済み YAML から BPMN 2.0 XML、PlantUML、HTML を生成

- [BPM Agent のソースと詳細](./bpm-agent/)
- [BPM Agent.zip](./BPM%20Agent.zip)

### BPR Agent

As-Is 業務プロセスをもとに課題と改善案を分析し、ユーザーが採用した改善案から To-Be 業務プロセスを設計します。

主な処理:

- As-Is の `process.yaml` をもとに BPR 分析
- 改善案と改善レポートを生成
- 改善案ごとにユーザーの採用 / 条件付き採用 / 保留 / 見送りを確認
- 採用された改善案だけを To-Be へ反映
- To-Be の YAML をレビューし、BPMN 2.0 XML、PlantUML、HTML を生成
- BPR 分析時の公開情報参照先として Microsoft Learn を利用

BPM Agent で作成した `process.yaml` を As-Is の入力として利用できます。

- [BPR Agent のソースと詳細](./bpr-agent/)
- [BPR Agent.zip](./BPR%20Agent.zip)

## Requirements

- Microsoft 365 Copilot
- Microsoft 365 Copilot Agent Builder で Skills 機能を利用できる環境

## Usage

1. 利用するエージェントの ZIP パッケージをダウンロードします。
2. Microsoft 365 Copilot Agent Builder にパッケージをインポートします。
3. BPM Agent では、可視化したい業務内容を対話形式で説明します。
4. BPR Agent では、As-Is の `process.yaml` を添付して改善分析を依頼します。

BPR Agent で To-Be を作成する場合、改善案はユーザーが明示的に採用または条件付き採用したものだけが反映されます。

## Notes

生成 AI による推論を含むため、生成された業務プロセス、改善案、BPMN、その他の成果物は、実際の業務要件・組織ルール・セキュリティ・コンプライアンス要件と照合して確認してください。

このプロジェクトは Microsoft の公式製品、公式サンプル、公式サポートではありません。

## Privacy and Terms

- [Privacy Statement](./PRIVACY.md)
- [Terms of Use](./TERMS.md)
