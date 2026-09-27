# BPR Agent

Microsoft 365 Copilot Agent Builder の Skills 機能を利用して、As-Is 業務プロセスの分析から改善案の検討、To-Be 業務プロセスの設計までを支援するエージェントです。

## Overview

BPR Agent は、As-Is の `process.yaml` を入力として課題と改善案を分析し、改善レポートを作成します。

改善案は自動的に To-Be へ反映せず、ユーザーが採用または条件付き採用したものだけを To-Be 業務プロセスへ反映します。作成した To-Be 定義はレビュー後、BPMN 2.0 XML、PlantUML、HTML として出力できます。

## Flow

1. As-Is の `process.yaml` を分析
2. 課題・改善案と改善レポートを生成
3. 改善案ごとに採用 / 条件付き採用 / 保留 / 見送りを確認
4. 採用された改善案から To-Be 業務プロセスを生成
5. To-Be 業務プロセス定義をレビュー
6. 検証済み定義から各形式の成果物を生成

## Contents

| Path | Role |
|---|---|
| [bpr-agent-instructions.md](./bpr-agent-instructions.md) | BPR Agent 全体の Instructions |
| [business-process-improvement-analyst](./business-process-improvement-analyst/) | As-Is の分析と改善案の生成 |
| [business-process-improvement-report-publisher](./business-process-improvement-report-publisher/) | 改善レポートの生成 |
| [business-process-tobe-modeler](./business-process-tobe-modeler/) | 採用された改善案を反映した To-Be の設計 |
| [business-process-reviewer](./business-process-reviewer/) | To-Be 業務プロセス定義のレビュー |
| [business-process-publisher](./business-process-publisher/) | BPMN 2.0 XML、PlantUML、HTML の生成 |
| [sample-outputs](./sample-outputs/) | サンプル成果物 |

各 Skill の詳細な指示や実装は、それぞれのディレクトリ内の `SKILL.md`、`resources/`、`scripts/` を参照してください。

## Package

Microsoft 365 Copilot Agent Builder へのインポートには、リポジトリ直下の [BPR Agent.zip](../BPR%20Agent.zip) を利用してください。

## Relationship with BPM Agent

BPM Agent で作成した `process.yaml` を As-Is の入力として利用できます。

[BPM Agent の詳細](../bpm-agent/)
