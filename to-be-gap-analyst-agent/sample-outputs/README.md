# To-Be Gap Analyst Agent — Sample Outputs

このフォルダーは、BPM Agent・BPR Agent の公開サンプルにある**架空の経費精算業務**を引き継いだ、Gap分析の閲覧用サンプルです。

## 対応する入力

- [BPMのAs-Is `process.yaml`](../../bpm-agent/sample-outputs/process.yaml)
- [BPRのTo-Be `to-be-process.yaml`](../../bpr-agent/sample-outputs/to-be-process.yaml)
- [BPRの `improvement-analysis.yaml`](../../bpr-agent/sample-outputs/improvement-analysis.yaml)
- [BPRの `improvement-decisions.yaml`](../../bpr-agent/sample-outputs/improvement-decisions.yaml)

4ファイルのSHA-256は、今回のGap分析の原本参照値とすべて一致することを確認しています。

## 成果物

| ファイル | 用途 |
|---|---|
| [gap-report.html](./gap-report.html) | ブラウザーで読む詳細Gap分析・依存関係図（推奨） |
| [gap-analysis.json](./gap-analysis.json) | Gap・実施課題・依存・質問・合意を含む分析データ |
| [gap-register.csv](./gap-register.csv) | Gap・対応一覧を表計算ソフトで確認するためのCSV |
| [gap-report.md](./gap-report.md) | Markdown形式の詳細レポート |
| [implementation-roadmap.md](./implementation-roadmap.md) | 段階・実行順・前提条件を整理したロードマップ |
| [sample-quality-check.json](./sample-quality-check.json) | 入力の出典と今回のサンプルに対して実施した検証の記録 |

**概要：** Gap 8件、ACT 17件、原本由来Q 49件、最初のNext Action 1件。日程・工数・担当人数は未確定です。

## サンプルの位置付けと注意

- 以前のAgent Builderによるv3実行結果をもとに、**公開デモとして**分析全体の架空の最終了承、タスク工程の分割、具体的な依存条件を編集しています。元の利用者回答「D → OK」を全体了承と偽っていません。
- レポート・CSV・ロードマップは登録済み生成コードから出力し、最新の品質チェックと派生成果物整合チェックはローカルでPASSしています。
- **4原本を用いる `gap_workflow.py final` のエンドツーエンド再実行はしていません。** `sample-quality-check.json` のPASSは正式成果物の `formal_verified=true` と同義ではありません。正式な業務利用時はAgentによる `prepare → final` を実行してください。
- 出力中の業務データ・了承は架空の例です。実在する顧客や従業員の資料ではありません。実装・運用・本番移行は完了していません。

本サンプルの目的は**閲覧と形式の理解**です。運用上の正本、確定したプロジェクト計画、または現行Agentの実行結果を無条件に保証するものではありません。
