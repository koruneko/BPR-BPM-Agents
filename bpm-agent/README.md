# BPM Agent

Microsoft 365 Copilotで業務の内容を聞き取り、**現在の業務（As-Is）を再確認できる業務フロー**に整理するAgentです。

## 何ができる？

担当者、業務タスク、承認・判断、差し戻し、例外、システム、情報の受け渡しを対話で整理します。`process.yaml` を業務プロセスの基準定義として作り、検証後に図とHTMLを生成します。

## 使い方

1. [ルートREADMEの導入手順](../README.md#利用を開始する方法)に従い、[BPM Agent ZIP](../BPM%20Agent.zip)を導入するか、[Instructions](./agent-instructions.md)と3つのSkillをAgent Builderに登録します。
2. Agentに**対象業務、開始・終了、担当者、処理の順番**を説明します。すべてを最初から確定させる必要はありません。
3. Agentの質問に答え、分岐条件・例外・入出力などを補います。
4. `process.yaml` と図を確認し、違う箇所を修正依頼します。定義と成果物は同じ内容に揃えて更新されます。

最初の依頼例：

```text
経費精算の現在の業務フローを整理したいです。
開始は社員の申請、終了は経理担当者の振込です。
まず担当者と処理の流れを質問しながら整理してください。
```

## 入力と成果物

| 入力 | 主な成果物 |
|---|---|
| 業務の説明、既存の手順書、業務フローの修正指示 | `process.yaml`（As-Isの基準定義）、`process.bpmn`（BPMN 2.0）、`process.puml`（PlantUML）、`process.html`、レビュー結果 |

`process.yaml` は後工程の [BPR Agent](../bpr-agent/) と [To-Be Gap Analyst Agent](../to-be-gap-analyst-agent/) で再利用できます。サンプル：[sample-outputs](./sample-outputs/)。

## 処理の流れ

1. 業務の説明をもとに、担当者・Task・Gateway・入出力を整理
2. `process.yaml` を生成・更新
3. 構造・参照・分岐・到達性などをレビューし、必要なら修正
4. 同じYAMLからBPMN・PlantUML・HTMLを生成

## 構成ファイル

| ファイル / フォルダー | 役割 |
|---|---|
| [agent-instructions.md](./agent-instructions.md) | Agent全体のInstructions |
| [business-process-modeler](./business-process-modeler/) | 業務をYAMLに構造化するSkill |
| [business-process-reviewer](./business-process-reviewer/) | 定義と制御フローを確認するSkill |
| [business-process-publisher](./business-process-publisher/) | 図・HTMLを生成するSkill |
| [sample-outputs](./sample-outputs/) | 架空の経費精算業務のサンプル |

各Skillの詳細はフォルダー内の `SKILL.md` と同梱コードを参照してください。

## 注意事項

入力資料にない重要な業務ルールを勝手に確定するものではありません。業務責任者がAs-Isの実態を確認してください。Agentの導入方式と機能の前提条件は[ルートREADME](../README.md)を参照してください。
