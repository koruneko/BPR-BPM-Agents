# BPM Agent

Microsoft 365 Copilot Agent Builder の Skills 機能を利用して、ユーザーとの対話から業務プロセスを整理・構造化・可視化するエージェントです。

## Overview

BPM Agent は、業務内容をヒアリングしながら担当者、処理、条件分岐、差し戻し、例外、並行処理、利用システム、入出力を整理し、業務プロセスの基準定義となる `process.yaml` を作成します。

作成した定義はレビュー後、BPMN 2.0 XML、PlantUML、HTML として出力できます。

## Flow

1. ユーザーとの対話から業務内容を整理
2. `process.yaml` を生成
3. 業務プロセス定義をレビュー
4. 検証済み定義から各形式の成果物を生成

## Contents

| Path | Role |
|---|---|
| [agent-instructions.md](./agent-instructions.md) | BPM Agent 全体の Instructions |
| [business-process-modeler](./business-process-modeler/) | 業務プロセスの構造化と `process.yaml` の生成 |
| [business-process-reviewer](./business-process-reviewer/) | 構造・参照・Gateway・到達性・入出力などのレビュー |
| [business-process-publisher](./business-process-publisher/) | BPMN 2.0 XML、PlantUML、HTML の生成 |
| [sample-outputs](./sample-outputs/) | サンプル成果物 |

各 Skill の詳細な指示や実装は、それぞれのディレクトリ内の `SKILL.md`、`resources/`、`scripts/` を参照してください。

## Package

Microsoft 365 Copilot Agent Builder へのインポートには、リポジトリ直下の [BPM Agent.zip](../BPM%20Agent.zip) を利用してください。

## Relationship with BPR Agent

BPM Agent が生成した `process.yaml` は、BPR Agent における As-Is 業務プロセスの入力として利用できます。

[BPR Agent の詳細](../bpr-agent/)
