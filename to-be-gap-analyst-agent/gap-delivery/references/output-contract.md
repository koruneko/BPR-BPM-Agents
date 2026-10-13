# 出力契約 v1.6

## Gapの理解と次の行動

`next_actions` は id/title/kind/priority/reason/first_step/consult_with/owner_status/expected_result/related_action_ids/question_ids/depends_on/status/source の配列。kindは確認・決定・準備。depends_onはNext Action ID、related_action_idsはACT-ID、question_idsはQ-ID。status=confirmedは行動内容への合意であり実施完了ではない。最初の一歩と得たい結果を具体化し、担当未定なら相談する役割と候補確認の行動を残す。

`dialogue` は status(in_progress/completed)/agreed_scope/summary/deferred_topics/confirmation_source。deferred_topicsは持ち越す確認事項を示す文字列の配列。completedには今回の整理範囲への利用者の了承とその出典が必要。全業務Qの回答、日程・見積・担当の確定、実装・受入・本番移行を要求しない。持ち越すQをNext Actionへ結び、行動への合意だけでQをresolvedにしない。

`report_view=full` は全GAP/ACT詳細と依存図を開いた最終HTMLを生成する指定。既存の詳細一覧、比較、質問、実行順、後工程条件は保持し、冒頭にNext Actionと合意内容を加える。日程は任意。

JSONはUTF-8。項目の意味を保ち、未知は null または明示状態とする。資料由来のIDは原文通り保持する。

正式成果物では `gap_workflow.py prepare` から始まり、同じsource packとtemplate系統を `gap_workflow.py final` まで維持する。finalは原文パック必須で、`verification-manifest.json` が `overall_status=pass` かつ `formal_verified=true` の場合だけ正式版とする。

## 最上位

- `schema_version`: "1.0"
- `analysis_id`: 案件内で安定した識別子
- `workflow`: `gap_workflow.py prepare` が記録した `prepared_by`、`source_pack_sha256`、`source_index_sha256`、`prepared_from_files`。finalまで保持し、手作業で作り替えない。
- `analysis_version`: "1.0" 等
- `status`: provisional / analysis_complete（対象業務の準備完了とは別）
- `readiness`: unknown / blocked / ready_for_validation / ready_for_transition と根拠。実行試験証拠がなければ ready_for_transition としない。
- `source_manifest`: ファイル名、artifact_role、読込状態、process_id/version または analysis_id/version、読めた範囲
- `input_validation`: 版/採否/適用ID/参照/条件の照合結果。不一致は issueと出典
- `mappings`: 種別、as_is_ids、to_be_ids、change_type、意味上の差分、improvement_ids、source_refs
- `gaps`: 下記Gap
- `actions`: 下記課題
- `questions`: 下記質問
- `coverage`: ノード/フロー対応数、IMP別採否とGap/課題または維持理由、全未確認事項の引継ぎ/解消対応。`source_question_lineage` と `improvement_lineage` を含む。
- `roadmap`: 段階、action_ids、entry_conditions、exit_conditions、提案の根拠
- `change_log`: 改版した場合に前版/変更/理由/影響/出典
- `verification`: 実施した成果物チェック、未実施の業務テストと限界

## 原質問の正確な追跡

`coverage.source_question_lineage` は同梱inspect_sources.pyが返す全原質問行。各行は `file,field_path,original_text,question_id,status,resolution_source`。元資料の各位置が一行。重複内容でも別ファイル/位置の行を省略しない。原文は要約せず完全一致。metadataの配置は実際の索引で判定する。索引検証がfailならanalysis_completeにしない。

`coverage.improvement_lineage` は改善分析原本の各IMPを一度ずつ保持し、`improvement_id,status,gap_ids,action_ids,no_gap_reason` を記録する。Gap/ACTへつながらない改善は、なぜ実施Gapにならないかを `no_gap_reason` に残す。`unmapped` のままfinalへ進めない。

## source_refs

ファイルごとのオブジェクトで `file`、`entity_id`（なければnull）、`field`、`note`、`evidence_kind`（documented / undocumented / inference / user_confirmation）。事実と推論を混ぜない。

## 内部値と表示値

`priority` は分析JSON内部では `critical / high / medium / low` のみを使用する。人向け表示はレンダラーが「最優先 / 優先 / 通常 / 低め」へ変換する。「最優先候補」等の表示文言を内部値へ保存しない。担当候補や相談先は人向け文字列で保持し、Python配列の文字列表現を表示値として保存しない。

## Gap

`id`, `title`, `category`, `kind`（design_change / readiness_unknown / source_inconsistency）, `as_is`, `to_be`, `delta`, `implementation_status`（unknown 等）, `improvement_ids`, `source_refs`, `action_ids`, `question_ids`, `priority`, `priority_reason`, `confidence`, `acceptance_criteria`, `status`。

category: process / organization / rules / data / technology / control / operations / measurement。必要なら複数分類を追加フィールドで示す。

as_is/to_beは記載された状態と未確認部分を区別して説明。acceptance_criteriaは実施後に検証可能な条件と期待結果を文字列の配列で保持する。

## 課題

`id`, `gap_ids`, `title`, `deliverable`, `owner_candidate`, `owner_status`（proposed / confirmed / unknown）, `priority`, `priority_reason`, `depends_on`（ACT-ID配列）, `dependency_reason`, `start_status`（ready / blocked / unknown）, `entry_conditions`, `acceptance_criteria`, `source_refs`。

期限/工数は入力根拠があれば追加。なければ null または省略する。source_refsには課題の根拠と新たな推論の区分を含める。

## 質問

`id`, `question`, `gap_ids`, `source_refs`, `respondent_candidate`, `impact`, `status`（open / resolved / superseded）, `resolution`, `resolution_source`。解消済みは回答と出典を必須とする。

## CSV列

`action_id,gap_ids,title,category,as_is,to_be,delta,improvement_ids,owner_candidate,owner_status,priority,priority_reason,start_status,depends_on,entry_conditions,acceptance_criteria,question_ids,source_refs`

複数IDはセミコロン区切り。CSVは派生成果物で採否/業務ルールの原本にはしない。

## 対話で確認した計画（任意）

planning_decisions: topic, decision, status(proposed/confirmed), sourceの配列。
schedule: basisとtasks[{action_id,start,end,status}]。start/endはISO日付、endは完了直後の境界。見積・稼働日・休日・担当別同時上限・待ち時間・出典をbasisへ記載。未知の期間を創作しない。全先行ACTの日程を含め、依存と担当の重複を検証。日程なしでも全ACTの依存図を表示する。

execution_sequence: order, name, action_ids, status, reason の配列。全ACTを一度ずつ含め、まとまりの中の依存も保持。提案と了承済み条件を区別する。

営業日計画: 各actionsにduration_business_days（不明はnull）、estimate_source（見積根拠。不明はnull）、estimate_statusを追加できる。未定を一律1日に置き換えない。schedule.calendarにはmode=japan_business_days、公式一覧のsource、verified_on、verified_years、extra_holidaysを記録する。各tasksにはaction_id/start/last_work_date/end/duration_business_days/work_dates/estimate_source/owner/statusを記録する。endは後続開始可能な次の営業日、last_work_dateは最後の作業日である。未確認の対象年は日程を確定しない。会社独自の休業日と承認待ちも別途確認する。


## 判断材料と前後関係の区別（1.7）

各actions/next_actionsのdependency_relationsは配列。各要素はpredecessor_id/type(required,optional,unknown)/gate(start,finalize,execute,unknown)/condition/reason/can_proceed/if_deferred/source/status(proposed,confirmed)/deferral_agreed。着手前、確定前、実施・移行前を区別する。必須には必要な具体条件と根拠、任意には後回しの制約と先に進められる範囲を必須で記録する。「確認を始める」「案を作る」と「正式に確定・実施する」を分ける。sourceは実資料・回答位置または推論の理由。推論を合意済みにしない。

depends_onは既存参照を保持するが、必須・着手前の意味を自動付与しない。詳細がない旧データは要確認として表示。判断できる根拠があれば改版理由を残してdependency_relationsで分類する。前項目全体の完了が必要とは限らず、conditionで必要な情報・承認・成果だけを特定する。複数必須条件は該当段階で全条件を満たす。代替可能な条件は選択肢と採用根拠を確認してから一本化する。

図は実線=必須、破線=任意、点線=要確認。必要な段階、提案・確認済み、理由、先に進められる範囲、後回しの制約、根拠を続く表へ表示する。列や段階図は配置・検討の目安で着手停止や日時の確定を意味しない。必須の着手条件の循環は検出して停止。任意関係を待機条件に使わない。

日程では合意した必須着手条件だけを完了待ちに使う。要確認関係は先に確認する。確定・実施前の必須条件は作業を調査・案作成・確定・実施の必要な単位へ分け、条件を対応する段階へ置く。未分割のまま開始待ちへ変換しない。任意を日程から外すには後回しの制約を説明し、status=confirmedかつdeferral_agreed=trueで了承を記録する。

gaps[].decision_contextにimpact/root_cause/preserve/target_outcome/response_strategy/scope/success_measure/priority_assessment/tradeoff/source_refsを記録。文字列には確認済み事実・提案・未確認を区別。影響は誰に何が起きるか、原因は根拠と未検証を区別、対応は廃止・維持・変更・追加・教育/ルール・対象外等の選択肢と理由。到達条件は業務の観察可能な状態、評価指標は現状値/目標/測定方法/役割/根拠。不明な数値・費用・難易度は未確認にして、必要な確認をQ/Next Actionへ結びつける。すべてを必須要件やシステム化対象にしない。

scope_summaryはincluded/excluded/later/external/temporaryの文字列。実業務の変更範囲と今回の分析・対話範囲を明示して区別する。分析範囲への了承だけで業務スコープを承認済みにしない。

analysis_dimensionsはprocess/technology/data/people/organization/rules/control/measurementをキーとし、status（日本語の確認状況）、summary、gap_ids、question_ids、source_refsを保持。該当・不足・対象外の理由を示し、観点不足だけでGapを水増ししない。必要な判断だけ対話で確認し、全欄の確定や費用対効果の算定を対話完了条件にはしない。
