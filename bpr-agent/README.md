# BPR Agent

Microsoft 365 Copilotで**現行業務の問題点と改善候補を整理し、採用した改善だけを反映したTo-Be業務フロー**を設計するAgentです。

## 何ができる？

BPM Agentが生成したAs-Isの `process.yaml` を分析し、改善案・期待効果・前提条件・未確認事項を提示します。改善の採否は利用者が判断し、その結果に基づいてTo-Beを作ります。

## 使い方

1. [ルートREADMEの導入手順](../README.md#利用を開始する方法)に従い、[BPR Agent ZIP](../BPR%20Agent.zip)を導入するか、[Instructions](./bpr-agent-instructions.md)と5つのSkillをAgent Builderに登録します。
2. BPM Agentの `process.yaml` を業務資料として渡し、改善分析を依頼します。
3. 改善案を読んで、**採用・条件付き採用・保留・見送り**を回答します。条件付き採用では条件も明示します。
4. 変更後の業務フローを決めるのに必要な追加質問へ回答します。実装方式など後工程でよい内容は未確認として引き継げます。
5. To-BeのYAML、図、改善レポートを確認します。採否を変えたい場合はその旨を伝えます。

最初の依頼例：

```text
添付のprocess.yamlは現在の経費精算業務です。
業務課題と改善案を分析し、採否を決めるための情報を提示してください。
採用する改善を選んだ後にTo-Beの業務フローを作りたいです。
```

## 入力と成果物

| 入力 | 主な成果物 |
|---|---|
| BPMの `process.yaml`、利用者の改善案採否、必要な業務ルールの回答 | `improvement-analysis.yaml`（改善案・根拠）、`improvement-decisions.yaml`（採否）、`to-be-process.yaml`（To-Beの基準定義）、改善レポート、To-BeのBPMN・PlantUML・HTML |

**採否未確定の改善をTo-Beに自動反映しません。** また改善案を採用しても、具体的な製品・システムを同時に採用したことにはなりません。

サンプル：[sample-outputs](./sample-outputs/)。次の段階では、As-Isと上記3つのBPR成果物を [To-Be Gap Analyst Agent](../to-be-gap-analyst-agent/) に渡せます。

## 処理の流れ

1. As-Isの課題・改善案・期待効果・未確認事項を分析
2. レポートを示し、改善案ごとの採否を確認
3. 必要な業務ルールを確認し、採用された改善だけでTo-Beを設計
4. To-BeのYAMLをレビューし、図・HTMLを生成

## 構成ファイル

| ファイル / フォルダー | 役割 |
|---|---|
| [bpr-agent-instructions.md](./bpr-agent-instructions.md) | Agent全体のInstructions |
| [business-process-improvement-analyst](./business-process-improvement-analyst/) | As-Is分析と改善案生成 |
| [business-process-improvement-report-publisher](./business-process-improvement-report-publisher/) | 改善レポート生成 |
| [business-process-tobe-modeler](./business-process-tobe-modeler/) | 採用済み改善をTo-Beへ反映 |
| [business-process-reviewer](./business-process-reviewer/) | To-Be業務プロセスをレビュー |
| [business-process-publisher](./business-process-publisher/) | To-BeのBPMN・PlantUML・HTML生成 |
| [sample-outputs](./sample-outputs/) | 架空の経費精算業務のサンプル |

各Skillの詳細はフォルダー内の `SKILL.md` と同梱コードを参照してください。

## 注意事項

改善の効果・工数は入力と根拠の範囲で扱い、未確認の前提を事実として確定しません。業務責任者による採否や妥当性の確認が必要です。導入条件は[ルートREADME](../README.md)を参照してください。
