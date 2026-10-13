---
name: gap-planning
description: 優先度と実行順を対話で整理し、前提・並行作業・担当の空きを確認して依存図と日程案を作る。
---

## 判断材料と前後関係の区別（1.7）

各actions/next_actionsのdependency_relationsは配列。各要素はpredecessor_id/type(required,optional,unknown)/gate(start,finalize,execute,unknown)/condition/reason/can_proceed/if_deferred/source/status(proposed,confirmed)/deferral_agreed。着手前、確定前、実施・移行前を区別する。必須には必要な具体条件と根拠、任意には後回しの制約と先に進められる範囲を必須で記録する。「確認を始める」「案を作る」と「正式に確定・実施する」を分ける。sourceは実資料・回答位置または推論の理由。推論を合意済みにしない。

depends_onは既存参照を保持するが、必須・着手前の意味を自動付与しない。詳細がない旧データは要確認として表示。判断できる根拠があれば改版理由を残してdependency_relationsで分類する。前項目全体の完了が必要とは限らず、conditionで必要な情報・承認・成果だけを特定する。複数必須条件は該当段階で全条件を満たす。代替可能な条件は選択肢と採用根拠を確認してから一本化する。

図は実線=必須、破線=任意、点線=要確認。必要な段階、提案・確認済み、理由、先に進められる範囲、後回しの制約、根拠を続く表へ表示する。列や段階図は配置・検討の目安で着手停止や日時の確定を意味しない。必須の着手条件の循環は検出して停止。任意関係を待機条件に使わない。

日程では合意した必須着手条件だけを完了待ちに使う。要確認関係は先に確認する。確定・実施前の必須条件は作業を調査・案作成・確定・実施の必要な単位へ分け、条件を対応する段階へ置く。未分割のまま開始待ちへ変換しない。任意を日程から外すには後回しの制約を説明し、status=confirmedかつdeferral_agreed=trueで了承を記録する。

gaps[].decision_contextにimpact/root_cause/preserve/target_outcome/response_strategy/scope/success_measure/priority_assessment/tradeoff/source_refsを記録。文字列には確認済み事実・提案・未確認を区別。影響は誰に何が起きるか、原因は根拠と未検証を区別、対応は廃止・維持・変更・追加・教育/ルール・対象外等の選択肢と理由。到達条件は業務の観察可能な状態、評価指標は現状値/目標/測定方法/役割/根拠。不明な数値・費用・難易度は未確認にして、必要な確認をQ/Next Actionへ結びつける。すべてを必須要件やシステム化対象にしない。

scope_summaryはincluded/excluded/later/external/temporaryの文字列。実業務の変更範囲と今回の分析・対話範囲を明示して区別する。分析範囲への了承だけで業務スコープを承認済みにしない。

analysis_dimensionsはprocess/technology/data/people/organization/rules/control/measurementをキーとし、status（日本語の確認状況）、summary、gap_ids、question_ids、source_refsを保持。該当・不足・対象外の理由を示し、観点不足だけでGapを水増ししない。必要な判断だけ対話で確認し、全欄の確定や費用対効果の算定を対話完了条件にはしない。



# 優先度と実行計画の相談

## Gapを理解して次の行動を選べるレポート（1.6）

このAgentの完了は、Gapと優先するNext Action、最初の一歩、相談する役割、得たい結果、前後関係と持ち越しが整理され、今回の範囲を利用者が了承すること。実見積、日程、全業務質問の回答、実装や本番移行は必須ではない。既存の詳細レポートは維持し、対話完了後にNext Actionと合意内容を冒頭へ加える。途中で必要なら案として出す。

next_actionsの定義は主指示に従う。dialogueにはstatus/agreed_scope/summary/deferred_topics/confirmation_sourceを記録する。completedには利用者の今回の了承の出典が必要。行動への合意を業務Qの解消や実装完了にしない。未確認を役割候補と具体的な確認行動へつなげ、確認を始めることと実装着手を分ける。

「フル」「全体を表示」はreport_view=fullとして登録コードを実行し、全GAP/ACT詳細と依存図をopen属性付きで生成する。全Next Action、合意内容、持ち越し、全比較・質問・依存・実行順・任意日程・後工程条件・根拠を省略しない。最終レポートを出すために全Qの回答を強制しない。


このスキルはGap分析の後の計画相談と図解で利用する。分析IDと既存ACT-IDを維持し、BPM/BPRの入力や採否は変更しない。

最初に優先候補と理由、先に必要な作業、着手条件を示す。一回に最大3つの質問で、重視する成果・リスク・期限、優先順位の入替、前後関係、担当の空き、日程条件を順に確認する。回答済みを再質問しない。回答ごとに確定した条件・提案・未決事項と影響を短くまとめる。利用者の了承前は計画案として扱う。

優先度と実行順を分け、必須性と必要な段階を確認する。任意の確認を全体の着手待ちへ変換しない。依存なしでも着手条件が未解決なら着手可能と断定しない。条件が揃わない日程・工数・担当を創作しない。期限だけで受入条件を省略しない。工程の質問を業務ルールの解消・実装完了と扱わない。

planning_decisionsはtopic/decision/status(proposed/confirmed)/sourceの配列。scheduleはbasisとtasks[{action_id,start,end,status}]。ISO日付、endは完了直後の境界。basisには開始日、各作業の見積と単位、稼働日・休日、担当別同時上限、承認待ち、出典を明記。未確認なら日程未確定として依存図のみ作る。担当の重複、依存違反、循環、未知IDを検証する。クリティカルパスや最短完了日は必要な期間が揃うまで断定しない。

execution_sequence[{order,name,action_ids,status,reason}]へ対話で整理した実行順を記録する。全ACTを一回ずつ含める。作業のまとまり内にも依存があれば前後関係を保持し、無条件の並行実行可能とは表示しない。会話の優先度も自然な日本語にする。

# 図解の補助コード

同梱の `scripts/planning_report.py` を依存関係の検証と図解に使用する。成果物生成時は `gap-delivery` に同梱された実行用コピーを使用し、他Skillの `SKILL.md` からコードを抽出しない。段階の全体図、全ACTの依存図、日程が確認された場合のガント図をHTMLに埋め込む。全ノード・全矢印が分析データと一致するか集合照合する。図には説明と詳細リンクを付け、表の情報も残す。色は表示側の配色へ追従させる。外部通信や実行スクリプトは不要。画面を見ていない検証を画面確認済みとしない。

`scripts/planning_report.py` を使用する。コードを本文から生成・再構成しない。

## To-Be Gap Analyst Agent内での正本

対話で合意した優先度、Next Action、前後関係、日程条件は、`gap_workflow.py prepare` から継続している同一の `gap-analysis.json` へ更新する。別の計画JSONや独自分析生成スクリプトを正本にしない。利用者が今回の整理を了承したら、主Agentの指示に従って同じ応答処理で `gap_workflow.py final` へ進む。
