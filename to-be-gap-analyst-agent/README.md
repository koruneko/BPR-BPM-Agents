# To-Be Gap Analyst Agent

Microsoft 365 Copilotで、**現在の業務（As-Is）と採用済みの改善後業務（To-Be）を比較し、変更点から次の行動を決める**Agentです。

## 何ができる？

単なる差分一覧にとどまらず、業務・システム・データ・人とスキル・役割・ルール・管理・測定の観点からGapを整理します。利用者と対話し、優先するNext Action、最初の一歩、相談する役割、判断の前後関係を具体化してレポートにまとめます。

## 使い方

1. [ルートREADMEの導入手順](../README.md#利用を開始する方法)に従い、[To-Be Gap Analyst Agent ZIP](../To-Be%20Gap%20Analyst%20Agent.zip)を導入するか、[Instructions](./agent-instructions.md)と5つのSkillをAgent Builderに登録します。
2. BPM/BPRで作成した**主要4ファイル**（下表）を渡して、As-IsとTo-BeのGap分析を依頼します。
3. Agentが提示するGap・優先候補・Next Actionを確認し、重視する成果や今回の範囲、最初に取る行動を対話で整理します。
4. 今回の行動整理に合意すると、正式レポートの作成・検証へ進みます。日程は希望する場合だけ追加します。
5. 生成されたレポートと検証結果を確認します。確認事項や実施条件が残っていても、次の行動を決めた段階で対話を完了できます。

最初の依頼例：

```text
次の4ファイルをもとに、As-IsとTo-BeのGapを分析してください。
- process.yaml
- to-be-process.yaml
- improvement-analysis.yaml
- improvement-decisions.yaml

重要な変更点と、まず誰と何を確認・決定・準備すべきかを整理したいです。
```

資料の添付が環境で受け付けられない場合、4ファイルの**原文をファイル名付きで区切ったUTF-8テキスト**として渡す方法もあります。原文の省略や書換えはしないでください。

## 入力と成果物

| 入力ファイル | 内容 |
|---|---|
| BPMの `process.yaml` | 現在の業務（As-Is） |
| BPRの `to-be-process.yaml` | 改善後の業務（To-Be） |
| BPRの `improvement-analysis.yaml` | 改善案・根拠・未確認事項 |
| BPRの `improvement-decisions.yaml` | 改善案の採否・条件 |

**主な成果物：** `gap-analysis.json`、`gap-register.csv`、詳細レポート（Markdown・HTML）、実行ロードマップ、依存関係図、検証結果、成果物ZIP。

As-Isがない場合の比較は暫定扱いです。また、レポートが完成しても**業務の実装・受入・本番移行が完了したことにはなりません**。

## 処理の流れ

1. 原本を索引化し、改善採否・質問・参加者・Task・Flowの対応を準備
2. As-Is / To-Beの意味の差分と影響を分析
3. 優先するNext Action・依存関係・持ち越す確認事項を対話で整理
4. 了承後、原本との照合・品質検証を行い、正式成果物を一括生成

正式生成は登録済み `gap-delivery/scripts/gap_workflow.py` を使います。検証に失敗した成果物は正式版として提供しません。Agent Builder上でのすべての自動実行を保証するものではないため、プレビューでの検証が必要です。

## 構成ファイル

| ファイル / フォルダー | 役割 |
|---|---|
| [agent-instructions.md](./agent-instructions.md) | Agent全体のInstructions |
| [bpr-gap-analysis](./bpr-gap-analysis/) | As-Is / To-Beと原本の照合、Gap分析 |
| [gap-planning](./gap-planning/) | 優先度、次の行動、実行順の整理 |
| [gap-business-calendar](./gap-business-calendar/) | 希望された日本の営業日日程 |
| [gap-delivery](./gap-delivery/) | 原本準備、検証、レポートとZIP生成 |
| [gap-report-format](./gap-report-format/) | レポート形式と表示処理 |
| [REBUILD_NOTES_v3.md](./REBUILD_NOTES_v3.md) | v3の変更内容とローカル検証の記録 |

各Skillの詳細はフォルダー内の `SKILL.md` と同梱コードを参照してください。

## 開発者向け：CLIによる検証

Agent BuilderへのSkill登録にはCLI操作は不要です。以下はローカルでワークフローを確認する際の例です（Pythonと4つのYAML原本を用意してください）。

```bash
python gap-delivery/scripts/gap_workflow.py prepare \
  --source process.yaml \
  --source to-be-process.yaml \
  --source improvement-analysis.yaml \
  --source improvement-decisions.yaml \
  --output-dir ./work

# work/gap-analysis.template.jsonを分析・対話結果で更新し、
# 検証対象のwork/gap-analysis.jsonを作成してから実行します。
python gap-delivery/scripts/gap_workflow.py final \
  --analysis ./work/gap-analysis.json \
  --pack ./work/source-pack.txt \
  --preparation ./work/workflow-preparation.json \
  --output-dir ./work/delivery \
  --report-view full \
  --zip ./work/gap-analysis-final.zip
```

検証が不合格の場合は、実際のエラーに基づいて原本・分析データの不整合を修正してください。独自の生成コードで検証を回避しないでください。

## 注意事項

根拠のない効果・見積・責任者を作らず、未確認事項は明示します。利用者が入力した業務内容はレポートにも含まれるため、顧客資料・個人情報をPublicリポジトリへPushしないでください。導入条件は[ルートREADME](../README.md)を参照してください。
