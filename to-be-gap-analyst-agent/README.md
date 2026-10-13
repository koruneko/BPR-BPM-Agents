# To-Be Gap Analyst Agent

Microsoft 365 Copilot Agent Builder 向けに、BPM Agent の As-Is と BPR Agent の採用済み To-Be を比較し、業務上のGapと実行可能な Next Action を整理するエージェントです。

## 現在の実装

本ディレクトリは **v3 workflow構成**です。`gap-planning-current` は廃止し、5つのSkillを使用します。

| Skill | 役割 |
|---|---|
| [bpr-gap-analysis](./bpr-gap-analysis/) | As-Is / To-Beの比較、根拠・未決事項・プロセス対応表 |
| [gap-planning](./gap-planning/) | 優先度、Next Action、依存・実行順の整理 |
| [gap-business-calendar](./gap-business-calendar/) | 日本の祝日・営業日日程の計算 |
| [gap-delivery](./gap-delivery/) | 原本索引・検証ゲート・HTML/CSV/Markdown/ZIPの一括生成 |
| [gap-report-format](./gap-report-format/) | HTML表示・レポートの形式と日本語表現 |

Agent Instructionsは [agent-instructions.md](./agent-instructions.md) です。

## 標準ワークフロー

`gap-delivery/scripts/gap_workflow.py` が正式な統合入口です。

1. **prepare**：主要原本4ファイル（`process.yaml`、`to-be-process.yaml`、`improvement-analysis.yaml`、`improvement-decisions.yaml`）から、`source-pack.txt`・`source-index.json`・`gap-analysis.template.json`・`workflow-preparation.json` を生成します。
2. **分析・対話**：As-Is / To-Beの意味の差分、Gap・ACT・Q・NA、依存条件、相談役割、未解決事項を整理してテンプレートを改版します。全参加者・ノード・フロー・改善IDと原質問の原文出典を追跡します。
3. **calendar（任意）**：営業日日程を希望する場合、登録スクリプトで計算します。
4. **draft（任意）**：進行中の成果物を暫定として生成できます。正式検証済みとは表現しません。
5. **final**：`--pack` を指定して原本照合、分析スキーマ、依存・ID、原文系譜、HTML再生成一致を検証します。`overall_status=pass` かつ `formal_verified=true` の場合のみ正式ZIPを生成します。

利用者が今回の整理・直近の行動案を了承した場合、Agentはレポート作成依頼を待たず、最終生成へ進む設計です。実業務への導入承認、未確認の業務質問の全解決、実装・受入・移行はエージェントの対話完了条件ではありません。

### CLI実行例

```bash
python gap-delivery/scripts/gap_workflow.py prepare \
  --source process.yaml \
  --source to-be-process.yaml \
  --source improvement-analysis.yaml \
  --source improvement-decisions.yaml \
  --output-dir ./work

# 出力された gap-analysis.template.json を原本と対話結果に基づいて更新。
# 以下は、更新・検証済みの gap-analysis.json を用意した後に実行します。
python gap-delivery/scripts/gap_workflow.py final \
  --analysis ./work/gap-analysis.json \
  --pack ./work/source-pack.txt \
  --preparation ./work/workflow-preparation.json \
  --output-dir ./work/delivery \
  --report-view full \
  --zip ./work/gap-analysis-final.zip
```

生成失敗時は原因を確認し、原本・分析データ・依存条件を修正したうえで再実行してください。見積や未確認事項を推測で埋めないでください。

## ダウンロードとソース

- [Agent Builder向けAgentパッケージ](../To-Be%20Gap%20Analyst%20Agent.zip)
- [Agent Instructions](./agent-instructions.md)
- [v3修正・検証記録](./REBUILD_NOTES_v3.md)

`SKILL.md` と `scripts/` は本ディレクトリに展開されています。GitHub上のファイルを確認・レビューできます。

## 入力の基準

主要入力はBPMの `process.yaml` とBPRの `to-be-process.yaml`・`improvement-analysis.yaml`・`improvement-decisions.yaml` です。レビューや追加資料は補助入力として利用します。資料の不足を黙って補完したり、採否を独自に変更したりしません。

## 検証の限界

v3はローカルのスクリプトテストで `prepare` と `final` の正常系、必須入力不足や不正内部priorityの異常系を確認しています。**Agent Builderのプレビュー実行環境で複数Skillが常に正しく呼び出されることを保証するものではありません。** 計画やGapの意味上の妥当性は、元資料と担当者の判断によるレビューも必要です。

## 他Agentとの関係

- [BPM Agent](../bpm-agent/)
- [BPR Agent](../bpr-agent/)
