---
name: business-process-tobe-modeler
description: Human Gateで明示的に採用または条件付き採用されたBPR改善案だけをAs-Isプロセスへ反映し、変更追跡可能なTo-Be業務プロセスYAMLを新規生成するスキルです。
---

# Business Process To-Be Modeler v1.21

このSkillは、ユーザーが**明示的に採用または条件付き採用した改善案だけ**を反映したTo-Beプロセスを作成する。

## 参照仕様

- `resources/bpr-analysis-spec.md`
- `resources/process-model-spec.md`
- `resources/material-gate-spec.md`

## Human Gate

次の3つが揃うまで実行しない。

1. As-Is `process.yaml`
2. `improvement-analysis.yaml`
3. ユーザーの明示判断を構造化した `improvement-decisions.yaml`

`approved` / `conditional_approved` の改善案だけをTo-Beへ反映する。`hold` / `rejected` / 未判断は反映しない。

`conditional_approved` は判断メモが必須。条件を `metadata.bpr.conditional_improvements` にそのまま保持する。さらに、条件がその改善案のタイトル・`proposed_change`・`prerequisites`・`unresolved_questions` と意味的に対応するか確認する。別改善案の条件と考える方が自然な場合や対応が曖昧な場合は、To-Be生成を止めてユーザーへ改善IDと条件の対応を確認する。スクリプトも明白な取り違えを保守的に検知する。

### Material Business Rule Gate

改善案の採用は、その改善案に残る業務ルールまで確定したことを意味しない。採用/条件付き採用後、**未確定のままでは製品非依存のControl Flowを一意に描けない事項だけ**をBlockingとして確認する。

Blockingの典型例:
- 上限到達後にどの経路へ進むか
- 閾値判定に使う金額の定義
- 非承認時に却下/差し戻しのどちらへ進み、どこへ戻すか
- 職務分離や二重承認の有無が経路を増減させる場合

一方、**Control Flowを抽象的に確定できるパラメータや実装詳細は原則non-blocking**とする。例: 再申請の具体的な回数、SLA時間、エスカレーション時刻/宛先、API/コネクタ/CSV方式、命名規則、保持期間。これらは `carried_forward` としてFinal To-Beへ残せる。

Blocking事項が未確定なら `validate-decisions` をErrorとして停止し、Final To-Beを生成しない。ユーザーが確定した回答は `improvement-decisions.yaml` の `business_rule_resolutions` に、分析上の質問文を完全一致で `question`、出所を `source`、回答を `resolution` として記録する。1回の回答が複数の既存質問を解決した場合は、各質問へ個別にresolutionを記録する。

### Material Gateの質問提示

Blocking事項の**意味内容**（元質問との対応、Question、Option、推奨有無と根拠）をこのSkillで構造化する。v1.21以降は、会話Markdownの文字列一致よりも**Material Gate YAMLの意味論とlineageを正しく固定すること**を優先する。

To-Be Modeler Packageは `scripts/material_gate_v110.py` を同梱する。Material Gateのために別Skillを追加導入する必要はない。`/mnt/data/material-gate-input.yaml` は `gate_version: '1.1'` とし、各Questionに次を必須化する。

- `source_refs`: 元の `IMP-xxx.unresolved_questions` / `analysis_open_questions` / `design` 質問への対応
- `recommendation.status`: `recommended` または `none`
- `recommended` の場合だけ、既存Optionを指す `recommendation.option_id`
- `recommendation.rationale`: 推奨理由または推奨なし理由
- Option ID / label

Rendererは `improvement-analysis.yaml` と照合し、分析ID、元質問の完全一致、重複参照、存在しないOptionへの推奨、定義外キーをErrorにする。

```bash
MG_SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'material_gate_v110.py' -path '*/business-process-tobe-modeler*/scripts/*' 2>/dev/null | head -n 1)
if [ -z "$MG_SCRIPT" ]; then
  MG_SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'material_gate_v110.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
fi
python "$MG_SCRIPT" render \
  --input /mnt/data/material-gate-input.yaml \
  --analysis /mnt/data/improvement-analysis.yaml \
  --output /mnt/data/material-gate-response.md \
  --result /mnt/data/material-gate-validation.json
```

`material-gate-validation.json` の `ok: true` を確認してから質問を提示する。`material-gate-response.md` は構造化YAMLを人が確認しやすくする**canonical reference**であり、会話応答を一字一句同じにすることは要求しない。Agentは自然な文章へ整えてよいが、推奨Option、推奨なし、Optionの意味、元質問との対応は `material-gate-input.yaml` と矛盾させない。

推奨は業務根拠または最小変更・単純化・既存Role維持などから合理的に推せる場合だけ `recommendation.status: recommended` とし、根拠が弱ければ `status: none` とする。改善案そのものの採否を推奨してはならない。

同じ判断で複数の `unresolved_questions` を同時に解決できる場合は、ユーザー向けには1つの質問へまとめて認知負荷を下げる。ただし回答後の `business_rule_resolutions` では各元質問へ個別に展開する。元質問が「上限を設けるか」で回答が「上限到達時は…」のように存在自体も確定する場合や、「どのTaskへ戻すか」まで回答本文で確定した場合も、該当する全元質問を `resolved` にする。具体値だけが残る場合は、元質問を未解決のまま残さず `source: design` の新しいnon-blocking質問（例: `再申請の具体的な上限回数は何回か。`）として分離する。

## 依存関係

採用/条件付き採用された改善案の `dependencies` を検証する。

- `requires`: 列挙した改善案がすべて採用/条件付き採用されていなければエラー
- `any_of`: 最低1件が採用/条件付き採用されていなければエラー
- `enhances`: 情報提供上の相乗効果。未採用でも生成可能で、WarningにもErrorにもしない

## As-Is保護

- As-Is YAMLを上書きしない。
- 出力は `/mnt/data/to-be-process.yaml` など別名にする。
- 変更しないノード・エッジのIDは維持する。
- 新しいTask/Gateway/Edgeだけ新しいIDを作る。
- AIが分析時に提案しただけで、ユーザーが採用していない変更を追加しない。

## 変更追跡

`metadata.bpr` に必ず以下を保持する。

- As-Is process ID/version
- analysis version
- `applied_improvements`
- `conditional_improvements`
- `change_log`
- `source_node_context`（As-Is Taskの name / participant / system / duration / frequency / issues のスナップショット）
- `performance_targets`（As-Is baselineに対してTo-Beで目指すKPI/期待方向）
- `open_question_disposition`（分析/As-Isの未確認事項を `resolved / carried_forward / not_applicable` で全件追跡）

`change_log` には改善ID、改善タイトル、変更概要、Human Gate前分析からそのまま引き継いだ期待効果、confidence、条件付き採用条件、変更対象となったsource/target node/edge IDsを記録する。期待効果をTo-Be生成時に新しく作り直さない。

## モデリング

To-Be自体のBPMN/YAML構造は `resources/process-model-spec.md` に従う。廃止・統合・自動化でフローが変わる場合も、Gateway semantics、participant、入出力、task_typeを正しく再構成する。

自動化後のTask Typeは実装方式に応じて選ぶ。`implementation_options` は候補であり、Human Gateで採用された改善内容や確定済み前提を超えて特定製品を勝手に固定しない。

- 条件付き採用の条件が `API / 標準コネクタ / CSV` のように複数方式を許し、方式によって `task_type`・担当・システム・経路が変わる場合、未確定方式を推論して `service` 等へ決め打ちしない。ソースTaskを保守的に維持し、To-Be目標と条件を説明・追跡情報へ保持する。
- プロセス横断の状態管理・監視・通知改善を反映しただけで、各Task自体の `automation.candidate` を `true` に変更しない。また、その横断改善の説明をTaskの `automation.notes` に混在させない。Task実行の自動化/支援と横断状態管理を分離し、横断改善は `metadata.bpr.change_log` で追跡する。
- To-Beは提案・目標設計であり、導入後実績ではない。To-Be Taskの `duration` / `frequency` は原則として持たせない。As-Is実績は `source_node_context` にのみ保持する。
- 将来の改善意図は `metadata.bpr.performance_targets` で表す。各項目は `metric / baseline / target / direction / note / related_improvements / source_node_ids / target_node_ids` を持つ。`direction` は `decrease / increase / maintain`。
- `target` の具体値は、ユーザーが明示した目標またはTask廃止など設計から決定的に導ける値だけを記載する。根拠がなければ `target: null` とし、`note` に目標値未設定・導入後測定などの理由を書く。
- performance targetは時短・件数だけに限定しない。差し戻し率、エラー率、例外率、リードタイム、SLA、手作業量、再処理、統制・監査に関する測定指標など、採用改善が変えたい成果を表す。
- `source_node_context` はスクリプトがAs-Isから決定的に注入する。To-Be HTMLはこれを使ってAs-Isの所要時間・頻度・課題を表示するため、To-Beノードの `issues` をAs-Is課題の保存場所にしない。
- To-Be `nodes[].issues` には**To-Beでも残る課題だけ**を書く。変更Taskだけでなく、採用改善の `target_tasks` に含まれる存続TaskにAs-Is課題がある場合も、`metadata.bpr.issue_disposition.<node_id>` で各As-Is課題を `resolved / remaining / changed` のいずれかに分類し、理由を残す。`remaining` は同じ課題をTo-Beにも残す。`resolved` はTo-Beから削除する。`changed` は、現在も課題として残るなら古い文言を削除して `to_be_issue` へ置換する。As-Is実績・比率・件数をKPI/Baselineとして扱う場合は `to_be_issue` の代わりに `performance_target_metric` を指定し、同名の `performance_targets[].metric` へ追跡する。この場合As-Is文言をTo-Be `issues` に残さない。`changed` では `to_be_issue` と `performance_target_metric` を同時に指定しない。
- `scope: process` の採用改善は、分析時の `target_tasks` のうちTo-Beにも残るノードを `change_log.target_node_ids` に保持する。横断改善でTask本体を変更しなくても、詳細ペインで改善追跡できるようにするためであり、自動化属性の変更を意味しない。
- 自動実行する `service` / `script` Taskでは、`participant` は `type: system` の実行主体を使う。実行製品が未選定なら `automation_system` / `自動処理` など製品非依存のsystem participantを追加してよい。人が正常系Taskを実行しているように見せない。保存先や利用先は `system` に記録し、例外対応する人/部門は `automation.exception_owner` にparticipant IDで記録する。
- 採用改善が人の定型判定Taskを `automation.level: full` で廃止し、その判定をExclusive Gatewayへ置換・統合する場合、そのGatewayの `participant` も `type: system` の実行主体にする。人が判断するGatewayまで一律にsystem化しない。
- To-Beトップレベルの `metadata.assumptions` は**将来設計を成立させる前提だけ**にする。As-Isの件数、所要時間、frequency算定、差し戻し率等の計算前提をコピーしない。As-Is baselineは `source_node_context` / `performance_targets` で追跡する。As-Is由来でもTo-Beで継続する業務ルール（例: 5万円以上は部門長承認）や、将来設計で明示的に継続する保存先等はTo-Be前提として書き直してよい。
- 分析またはAs-IsからTo-Beへ関係する未確認事項を黙って落とさない。`metadata.bpr.open_question_disposition` で**全件**を `resolved / carried_forward / not_applicable` のいずれかに分類する。未解決で持ち越すものだけをトップレベル `metadata.open_questions` に完全一致で残す。
- `materiality: blocking` の未確認事項は `carried_forward` のままFinal To-Beに残せない。non-blockingは未確定のまま持ち越せる。 To-Beで新しく生じた実装・運用パラメータの未確認事項は `open_question_disposition.source: design` として追加できる。分析由来の元質問を、より具体的なdesign質問へ黙って置換しない。
- YAMLがparseできるだけでは合格としない。Modeler Validatorのstrict schema validationで、定義外キー・誤ったネスト・型崩れをErrorにする。
- Taskのdescriptionに「〜の場合のみ後続へ進む」「両方成功した場合のみ」等の条件を書く場合、その条件をEdgeまたはExclusive GatewayへControl Flowとして表す。文章だけで条件を保持しない。
- `承認結果`・`判定結果`等をTaskが出力する場合、結果を後続の条件分岐で消費する。非承認/失敗経路が未確定ならFinal To-Beとして発行しない。
- `service / script` Taskに `automation.exception_owner` がある場合、TaskからParallel Joinへ直接接続しない。各自動branch内で `Task → Exclusive Gateway（成功 / 失敗・期限超過等）` を置き、成功だけをJoinへ、例外は `exception_owner` の人Taskへ流して解消後に再実行する。並行改善が「滞留」を扱う場合、具体SLAが未確定でも `期限超過/タイムアウト` を失敗側の意味に含め、Join後で初めて失敗判定しない。
- Parallel Split / Join が `service / script` Task等のsystem実行branchを含む並行制御を表す場合、Split / Join自身の `participant` も `type: system` とする。人Taskだけの並行作業を人が明示的に調整するケースまで一律にsystem化しない。

## Human Gate判断の事前検証

`improvement-decisions.yaml` を作成したら、To-Be JSONを考える前に判断整合性を検証する。

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'tobe_model_v118.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" validate-decisions \
  --source-process /mnt/data/process.yaml \
  --analysis /mnt/data/improvement-analysis.yaml \
  --decisions /mnt/data/improvement-decisions.yaml
```

Errorが1件でもあればTo-Beを生成しない。特に条件メモが別改善案へ結び付いている可能性を示すErrorでは、AIが勝手に付け替えずユーザーへ確認する。

## To-Be YAML作成

AIが完全なTo-Be JSONを作成した後、次のスクリプトで書き出す。

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'tobe_model_v118.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" write \
  --source-process /mnt/data/process.yaml \
  --analysis /mnt/data/improvement-analysis.yaml \
  --decisions /mnt/data/improvement-decisions.yaml \
  --output /mnt/data/to-be-process.yaml
```

JSONは標準入力へ渡す。

この検証は、採用されていない改善案の混入、条件付き採用の条件喪失、依存関係違反、As-Is上書き、変更追跡漏れを防ぐためのもの。構造レビューは続けてBusiness Process Reviewerで実施する。

## 次工程

1. To-Be YAMLをBusiness Process Reviewerでレビューする。
2. Errorを修正する。
3. Business Process Publisherで `to-be-process.bpmn` / `.puml` / `.html` を生成する。

## 用語

ユーザー向けの説明では `正本` を使わない。状態管理先は `基準となるデータストア` / `一元管理するデータストア`、YAMLは `基準となる定義` 等、意味が分かる表現を使う。As-Isで一般的な添付資料を `エビデンス` と表記している場合は、その用語を原則継承する。

## 分析世代と実装候補

判断YAMLは `decision_version: '1.3'` とし、`source_analysis_id` を現在の改善分析 `analysis_id` と完全一致させる。不一致はErrorで停止する。

`implementation_options` は候補であり、`primary` でも自動選定しない。ユーザーが明示的に選択した場合だけ decision entry の `selected_implementation_options` に候補の `product_or_service` 名を完全一致で記録できる。候補だけに現れる製品名を、選択なしにTo-Be `system` へ固定してはならない。
