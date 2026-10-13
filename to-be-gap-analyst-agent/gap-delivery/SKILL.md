---
name: gap-delivery
description: Gap分析のデータから、業務の変更点、実施すること、確認事項、進める順序を読みやすいレポートと一覧にまとめ、内容の一致を確認する。
---

## 判断材料と前後関係の区別（1.7）

各actions/next_actionsのdependency_relationsは配列。各要素はpredecessor_id/type(required,optional,unknown)/gate(start,finalize,execute,unknown)/condition/reason/can_proceed/if_deferred/source/status(proposed,confirmed)/deferral_agreed。着手前、確定前、実施・移行前を区別する。必須には必要な具体条件と根拠、任意には後回しの制約と先に進められる範囲を必須で記録する。「確認を始める」「案を作る」と「正式に確定・実施する」を分ける。sourceは実資料・回答位置または推論の理由。推論を合意済みにしない。

depends_onは既存参照を保持するが、必須・着手前の意味を自動付与しない。詳細がない旧データは要確認として表示。判断できる根拠があれば改版理由を残してdependency_relationsで分類する。前項目全体の完了が必要とは限らず、conditionで必要な情報・承認・成果だけを特定する。複数必須条件は該当段階で全条件を満たす。代替可能な条件は選択肢と採用根拠を確認してから一本化する。

図は実線=必須、破線=任意、点線=要確認。必要な段階、提案・確認済み、理由、先に進められる範囲、後回しの制約、根拠を続く表へ表示する。列や段階図は配置・検討の目安で着手停止や日時の確定を意味しない。必須の着手条件の循環は検出して停止。任意関係を待機条件に使わない。

日程では合意した必須着手条件だけを完了待ちに使う。要確認関係は先に確認する。確定・実施前の必須条件は作業を調査・案作成・確定・実施の必要な単位へ分け、条件を対応する段階へ置く。未分割のまま開始待ちへ変換しない。任意を日程から外すには後回しの制約を説明し、status=confirmedかつdeferral_agreed=trueで了承を記録する。

gaps[].decision_contextにimpact/root_cause/preserve/target_outcome/response_strategy/scope/success_measure/priority_assessment/tradeoff/source_refsを記録。文字列には確認済み事実・提案・未確認を区別。影響は誰に何が起きるか、原因は根拠と未検証を区別、対応は廃止・維持・変更・追加・教育/ルール・対象外等の選択肢と理由。到達条件は業務の観察可能な状態、評価指標は現状値/目標/測定方法/役割/根拠。不明な数値・費用・難易度は未確認にして、必要な確認をQ/Next Actionへ結びつける。すべてを必須要件やシステム化対象にしない。

scope_summaryはincluded/excluded/later/external/temporaryの文字列。実業務の変更範囲と今回の分析・対話範囲を明示して区別する。分析範囲への了承だけで業務スコープを承認済みにしない。

analysis_dimensionsはprocess/technology/data/people/organization/rules/control/measurementをキーとし、status（日本語の確認状況）、summary、gap_ids、question_ids、source_refsを保持。該当・不足・対象外の理由を示し、観点不足だけでGapを水増ししない。必要な判断だけ対話で確認し、全欄の確定や費用対効果の算定を対話完了条件にはしない。

# Gap分析の成果物提供

## 登録ワークフローを唯一の実行入口にする

このAgentでの原本準備、原文索引、営業日確認、正式成果物生成は、同梱の `scripts/gap_workflow.py` を入口にする。Skill名から `/home/oai/skills/...` の場所を推測して個別スクリプトを探したり、モデル自身が `build_gap.py` 等の代替オーケストレーションコードを作ったりしない。

### 1. 分析開始前: prepare

4主要資料または利用可能な原本を読める状態にしたら、意味分析より先に `prepare` を実行する。

例:

`python scripts/gap_workflow.py prepare --source process.yaml --source to-be-process.yaml --source improvement-analysis.yaml --source improvement-decisions.yaml --output-dir gap-work`

`prepare` は次を生成する。

- `source-pack.txt`: 実際に受領した原本を改変せずまとめたパック。
- `source-index.json`: 原質問、参加者、ノード、フロー、改善IDの機械索引。
- `gap-analysis.template.json`: 今回の分析JSONの唯一の起点。原質問lineage、原本ID、source manifest、workflowハッシュを含む。
- `workflow-preparation.json`: prepareで使用した原本・ハッシュ・件数の記録。

以後の分析では `gap-analysis.template.json` を正本候補として更新する。原資料の要約から別のJSONを新規構築しない。`source_question_lineage`、prepareで検出した原本ID、`workflow` のハッシュを消したり、手作業の索引へ置き換えたりしない。

### 2. 対話中: canonical analysisを更新する

bpr-gap-analysis、gap-planning、利用者回答に基づき、prepareで作成したanalysisを更新する。独自の分析生成スクリプトで原本からJSONを再構築しない。必要なファイル編集は正本候補JSONへの更新として行う。

内部値の `priority` は `critical / high / medium / low` を使用し、表示用の「最優先候補」「優先」等を保存しない。担当候補や相談先は人向け文字列で保持する。`analysis_dimensions` や `decision_context` を全項目同じ定型文で埋めず、各観点・各Gapの具体的な根拠と不足を記録する。

営業日の単純な確認には `python scripts/gap_workflow.py calendar --start YYYY-MM-DD --duration N` を使用できる。最終日程は最終analysis内のscheduleを登録コードで再検証する。

### 3. 利用者了承後: finalを同じ処理で実行する

利用者が今回の整理内容を了承したら、会話の要約だけで終了せず、同じ応答処理の中でanalysisへ了承内容を反映し、`dialogue.status=completed` として直ちに `final` を実行する。利用者に「レポートは？」と改めて依頼させない。レポート作成の要否を再確認しない。

例:

`python scripts/gap_workflow.py final --analysis gap-analysis.json --pack gap-work/source-pack.txt --preparation gap-work/workflow-preparation.json --output-dir delivery-output --report-view full`

`final` は原文パックを必須とする。原文照合、全参加者・ノード・フロー・改善ID、分析品質、依存関係、登録レンダラー、派生成果物の一致を検証し、すべて通った場合だけ正式ZIPを作成する。

正式版として提示できる条件は、`verification-manifest.json` が `overall_status: pass` かつ `formal_verified: true` であり、finalコマンドが終了コード0であること。finalが失敗した場合は正式ZIPを作らず、実際のエラーに基づいてanalysisを修正して再実行するか、入力不足を利用者へ示す。独自HTML・独自ZIPで代替しない。

### 4. draftは正式版と分ける

対話途中に成果物が必要な場合だけ `gap_workflow.py draft` を使用できる。draftは正式版・検証済み・完成とは表現しない。正式な完了応答では必ずfinalを使う。

`generate_delivery.py`、`render_report.py`、`planning_report.py`、`business_calendar.py`、`inspect_sources.py`、`report_format.py` はworkflow内部の実装依存であり、正式成果物の入口として直接使用しない。

## Gapを理解して次の行動を選べるレポート

このAgentの完了は、Gapと優先するNext Action、最初の一歩、相談する役割、得たい結果、前後関係と持ち越しが整理され、今回の範囲を利用者が了承すること。実見積、日程、全業務質問の回答、実装や本番移行は必須ではない。既存の詳細レポートは維持し、対話完了後にNext Actionと合意内容を冒頭へ加える。途中で必要なら案として出す。

next_actionsの定義は主指示に従う。dialogueにはstatus/agreed_scope/summary/deferred_topics/confirmation_sourceを記録する。completedには利用者の今回の了承の出典が必要。行動への合意を業務Qの解消や実装完了にしない。未確認を役割候補と具体的な確認行動へつなげ、確認を始めることと実装着手を分ける。

「フル」「全体を表示」が求められた場合は `--report-view full` を指定する。全GAP/ACT詳細と依存図、全Next Action、合意内容、持ち越し、比較・質問・依存・実行順・任意日程・後工程条件・根拠を省略しない。最終レポートを出すために全Qの回答を強制しない。

分析結果を業務責任者と実装担当者が引き継げるファイルとして提供する。未決事項を隠して移行完了を宣言しない。

## 分析データ

詳細フィールドは [references/output-contract.md](references/output-contract.md) を参照。`gap-analysis.json` を共通の正本とし、その最終内容からすべての派生成果物を作る。入力プロセス/採否原本は変更しない。

final workflowは次を出力する。

- `gap-analysis.json`: 実際に派生成果物へ使用した最終分析データ。
- `gap-register.csv`: Gapごとの実施課題、担当候補/確定状態、優先度、着手状態、依存、根拠、受入条件。
- `gap-report.md`: 人向けの詳細レポート。
- `gap-report.html`: 登録済み `render_report.py` による自己完結HTML。
- `implementation-roadmap.md`: 段階、着手条件、成果/受入条件、移行前に解消する事項、任意日程。
- `source-index.json` / `source-verification.json`: 原文パックを指定した場合の原本索引と照合結果。
- `verification-manifest.json`: 実施した生成・検証、ハッシュ、未実施項目、正式検証可否。
- `scripts/`: 実際に使用した生成・検証スクリプト一式。
- `gap-analysis-delivery.zip`: 上記成果物をまとめたZIP。

## 分析品質の必須条件

固定のGap件数・ACT件数・質問件数は要求しない。入力内容に応じて件数は変わる。一方、詳細レポートに必要な情報モデルは省略しない。

- `scope_summary` で今回扱う範囲、扱わない範囲、後続、外部確認、暫定事項を区別する。
- `analysis_dimensions` で process / technology / data / people / organization / rules / control / measurement の8観点を記録する。観点不足だけでGapを水増ししない。
- 各Gapの `decision_context` に impact / root_cause / preserve / target_outcome / response_strategy / scope / success_measure / priority_assessment / tradeoff / source_refs を保持する。
- actions / next_actions の `dependency_relations` で必須・任意・要確認と、着手前・確定前・実施/移行前を区別する。
- `execution_sequence` を作る場合は全ACTを一度ずつ含める。
- completedの対話ではNext Actionと利用者了承の根拠を保持する。

これらを満たさない分析データから正式成果物を生成しない。件数を合わせるためにGapや課題を創作しない。

## 原本索引と照合

prepare/final workflowが同梱の `inspect_sources.py` を使って索引と照合を実行する。finalでは原文パックは必須であり、手作業で索引を推測して作らない。

索引のsource_question_lineageは、元の `file` / `field_path` / `original_text` を改変せず `coverage.source_question_lineage` と照合する。全ノード・フロー・参加者は原本ID集合と `mappings` を照合する。unsupported、未知参照、欠落、原文不一致を合格扱いにしない。

原本照合がfailした場合、正式ZIPは生成しない。finalでは原文パック未指定自体を失敗にする。draftだけは原文照合未実施を許容するが正式版とは扱わない。

## 派生成果物とHTMLの検証

final workflowは内部の `generate_delivery.py` を使い、同じ最終 `gap-analysis.json` からCSV、Markdown、ロードマップ、HTMLを再生成し、次を機械検証する。

1. JSON再読込、GAP/ACT/Q/NAのID重複、未知参照、必須着手依存の循環。
2. CSVのACT-IDと件数が分析データと一致すること。CSVはUTF-8 BOMで正しくクオートし、数式として解釈され得る入力由来セルをテキスト化する。
3. Markdown・ロードマップ・HTMLが正本の主要IDを保持すること。
4. HTMLが登録済み `render_report.py` の生成元マーカーを持ち、必要な主要セクションを含むこと。
5. 同じ最終分析データを登録済み `render(data)` へ再投入したHTML文字列が保存HTMLと完全一致すること。
6. 実行したスクリプト一式を成果物ZIPへ収録し、`verification-manifest.json` にSHA-256を記録すること。

検証失敗後に派生成果物だけを手修正して合格扱いにしない。分析データを直し、単一入口から全成果物を再生成する。

## 業務担当者が読みやすいHTML

HTMLはfinal workflow内部の `generate_delivery.py` が登録済み `render_report.py` の `render(data)` を呼び出して生成する。Markdownをpやpreで囲む簡易変換、モデル独自のHTML生成、別のレンダラーへの置換は禁止する。

概要、優先事項カード、番号の読み方、判断の材料と範囲、現在/変更後/必要対応の比較、Next Action、実施課題、確認事項、段階別実施計画、資料と確認範囲を保持する。全体図、Next Action依存図、ACT依存図、日程がある場合のガント表示は登録コードに従う。

生成するHTMLレポートでは、自動配色と「自動/白い表示/暗い表示」を維持する。この配色ルールはHTMLレポートにのみ適用し、チャット応答の文字色・背景色は指定しない。色だけに意味を依存させず、ラベルや線種でも状態・関係を判別できるようにする。

## 対話で整理した計画と図解

利用者と優先事項、前提、並行作業、担当の空き、開始日、見積、稼働日、承認待ちを段階的に確認し、一回に最大3つの質問で進める。回答と提案を区別し、既存IDを維持する。優先度と順序と着手可能性を別々に説明する。

planning_decisionsはtopic/decision/status(proposed/confirmed)/sourceの配列。日程条件が揃った場合のみscheduleを追加する。scheduleはbasisとtasksを保持し、未知の期間を創作しない。日程なしでも全ACTの依存図を表示する。

営業日の日程では、全作業一律1日を既定値にしない。所要日数と見積根拠を記録し、不明は未定とする。通常レポートへテスト版やテスト用の工数・開始日・担当を引き継がない。

## 後続更新

利用者の回答や資料の改版を受けたら対象Qと関連Gap/課題を更新する。既存IDは維持し、新項目だけ採番する。削除は `superseded` と理由で追跡する。analysis_versionを上げ、change_logへ変更理由、前提、影響、回答の出典を残す。

更新後は `gap-analysis.json` だけを正本として修正し、CSV/Markdown/ロードマップ/HTML/ZIPを個別編集しない。必ず `gap_workflow.py final` を再実行して全成果物とmanifestを更新する。旧採否が変わった場合は、新しい採否を受領した事実に基づく。自身の判断で改善採否を変えない。

