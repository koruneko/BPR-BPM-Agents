---
name: gap-business-calendar
description: 作業別の見積根拠を確認し、日本の土日祝を除く営業日で日程とガント図を作る。未定の日数を補わない。
---

## 判断材料と前後関係の区別（1.7）

各actions/next_actionsのdependency_relationsは配列。各要素はpredecessor_id/type(required,optional,unknown)/gate(start,finalize,execute,unknown)/condition/reason/can_proceed/if_deferred/source/status(proposed,confirmed)/deferral_agreed。着手前、確定前、実施・移行前を区別する。必須には必要な具体条件と根拠、任意には後回しの制約と先に進められる範囲を必須で記録する。「確認を始める」「案を作る」と「正式に確定・実施する」を分ける。sourceは実資料・回答位置または推論の理由。推論を合意済みにしない。

depends_onは既存参照を保持するが、必須・着手前の意味を自動付与しない。詳細がない旧データは要確認として表示。判断できる根拠があれば改版理由を残してdependency_relationsで分類する。前項目全体の完了が必要とは限らず、conditionで必要な情報・承認・成果だけを特定する。複数必須条件は該当段階で全条件を満たす。代替可能な条件は選択肢と採用根拠を確認してから一本化する。

図は実線=必須、破線=任意、点線=要確認。必要な段階、提案・確認済み、理由、先に進められる範囲、後回しの制約、根拠を続く表へ表示する。列や段階図は配置・検討の目安で着手停止や日時の確定を意味しない。必須の着手条件の循環は検出して停止。任意関係を待機条件に使わない。

日程では合意した必須着手条件だけを完了待ちに使う。要確認関係は先に確認する。確定・実施前の必須条件は作業を調査・案作成・確定・実施の必要な単位へ分け、条件を対応する段階へ置く。未分割のまま開始待ちへ変換しない。任意を日程から外すには後回しの制約を説明し、status=confirmedかつdeferral_agreed=trueで了承を記録する。

gaps[].decision_contextにimpact/root_cause/preserve/target_outcome/response_strategy/scope/success_measure/priority_assessment/tradeoff/source_refsを記録。文字列には確認済み事実・提案・未確認を区別。影響は誰に何が起きるか、原因は根拠と未検証を区別、対応は廃止・維持・変更・追加・教育/ルール・対象外等の選択肢と理由。到達条件は業務の観察可能な状態、評価指標は現状値/目標/測定方法/役割/根拠。不明な数値・費用・難易度は未確認にして、必要な確認をQ/Next Actionへ結びつける。すべてを必須要件やシステム化対象にしない。

scope_summaryはincluded/excluded/later/external/temporaryの文字列。実業務の変更範囲と今回の分析・対話範囲を明示して区別する。分析範囲への了承だけで業務スコープを承認済みにしない。

analysis_dimensionsはprocess/technology/data/people/organization/rules/control/measurementをキーとし、status（日本語の確認状況）、summary、gap_ids、question_ids、source_refsを保持。該当・不足・対象外の理由を示し、観点不足だけでGapを水増ししない。必要な判断だけ対話で確認し、全欄の確定や費用対効果の算定を対話完了条件にはしない。



# 日本の営業日で日程を作る

gap-planningの優先度・前後関係の対話を行った後、営業日の計算にはこのスキルを使う。標準候補は月〜金、土日と日本の祝日・振替休日・国民の休日を除く。会社独自の休日、担当の稼働、承認待ちの単位は確認する。会社の年末年始休暇を国民の祝日と混同しない。

各ACTの所要日数はduration_business_days、見積根拠はestimate_source、確定状態はestimate_statusへ記録する。不明はnull/unknown。全作業を1営業日とする既定値は禁止。日数は担当者の見積、実績または利用者が明示的に認めた仮定に基づく。資料の業務タスク名だけから実装作業の工数を推測しない。端数日・時間単位の見積は一日の稼働時間と丸め方を確認し、勝手に1日に切り上げない。開始日、各作業の見積、担当別同時上限、休日、承認待ちが足りなければ日程未確定として依存図と見積欄だけを出す。一回の質問は最大3点。仮の日数は利用者の了承を得て案と明示し、実際の決定とは分ける。

このコードの祝日は2026・2027年を内閣府の一覧で2026-10-04に確認した。振替休日と祝日に挟まれた休日を含む。2028年以降や改定があれば対象期間の公式一覧を取得・確認して更新するまで日付を確定しない。推定した春分・秋分や未確認の暦は使わない。対象年と出典・確認日を成果物へ記録する。

営業日計算には同梱の `scripts/business_calendar.py` を使用する。このスクリプトが参照する `planning_report.py` も同じ `scripts/` に同梱し、Skill単体で必要な実行依存を完結させる。成果物生成時は `gap-delivery` 側に同梱された実行用コピーを使用する。serial_scheduleは同じ担当が一件ずつ実施することを確認したケースのみ。複数担当・待ち時間を含む計画は制約を個別検証する。business_spanは作業日、完了日、次の営業日を返す。endは後続を開始できる日で、last_work_dateを人向けの完了日とする。休日に開始・作業を置かず、依存順と担当の重複を検証する。稼働時間と待ち時間は別物。入手していない見積や業務承認をコードの成功で確定扱いにしない。

schedule.calendar.mode=japan_business_days、source/verified_on/verified_years/extra_holidaysを記録し、各tasksにaction_id/start/last_work_date/end/duration_business_days/work_dates/estimate_source/owner/statusを記録する。HTMLは作業日を帯、休業日を灰色にし、完了日と後続開始可能日を分ける。人向けにはexecution_sequenceを「対話で整理した実行順」、depends_onを「先に完了が必要な対応」と表示する。JSONのキーや引用原文は変更しない。

新規分析の必要資料はBPRのto-be-process.yaml（変更後の業務）、improvement-decisions.yaml（採否と条件）、improvement-analysis.yaml（理由・制約・未確認事項）と、BPMのprocess.yaml（現在の業務）。BPRだけなら変更後に必要な準備は整理できるが、現在との差分は暫定で不足を明示する。既存Gap JSONは続きの相談・表示更新に使えるが新規のYAML分析と同一視しない。受領資料を毎回明示し、資料を読んでいないのに再分析済みとしない。

「テスト版」は検証のため明示的に架空の条件を使った成果物だけに付ける。通常の成果物は業務名と内容を題名にし、未確認事項は状態・見積・日程欄で示す。テストで全作業1日とした条件は実業務レポートへ引き継がない。

# 営業日計算とHTML図のコード

`scripts/business_calendar.py` と同梱依存の `scripts/planning_report.py` を使用する。コードを本文から生成・再構成しない。

## To-Be Gap Analyst Agent内での呼び出し

統合AgentではSkill名から実行パスを推測しない。営業日の単純確認は `gap-delivery/scripts/gap_workflow.py calendar`、最終日程の検証は `gap_workflow.py final` 内の同梱 `business_calendar.py` を使用する。独立した `gap-business-calendar` の実ファイルが見つからない場合に手計算へ切り替えず、登録済みworkflowを使用する。
