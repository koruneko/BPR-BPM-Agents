---
name: business-process-reviewer
description: 業務プロセスYAMLを検証し、参照不整合、到達性、排他分岐、default経路、並行Gatewayのデッドロック要因、意味上の欠落や入出力の不整合をレビューするスキルです。
---

# Business Process Reviewer

> Agent Builderでは作業ディレクトリが `/mnt/data` になることがあるため、`scripts/...` の相対パス実行を前提にしない。Skill Package内のスクリプトを絶対パスで解決してから実行する。

このスキルは `process.yaml` の構造と業務フローとしての整合性をレビューするために使用する。

## 参照仕様

`resources/process-model-spec.md` に従う。

## 必須レビュー

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'review_process_v111.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" --input /mnt/data/to-be-process.yaml --source-process /mnt/data/process.yaml --analysis /mnt/data/improvement-analysis.yaml --decisions /mnt/data/improvement-decisions.yaml --json-output /mnt/data/to-be-process-review.json --md-output /mnt/data/to-be-process-review.md
```

スクリプトは少なくとも次を機械的に確認する。

- ノード・エッジIDと参照先の不整合
- start / end の有無
- startへの流入、endからの流出
- 排他ゲートウェイの分岐、default重複、ラベル不足
- `default: true` と `condition` の同時指定
- default経路がExclusive Gateway以外から出ていないか
- Parallel GatewayのOutgoing Flowにcondition/defaultがないか
- 1つのGatewayがJoinとSplitを兼務していないか
- 排他的な複数経路がParallel Gatewayへ直接合流していないか
- 開始点から到達できないノード
- 終了点へ到達する経路が存在しないノード
- 文脈上レーンを設定できるStart / End / Gatewayの `participant` 欠落候補
- Taskの `description` 欠落
- Exclusive Gatewayの分岐Edgeで人向け `name` がない経路（default経路を含む）
- `task_type: user` なのに利用システムが未設定で、実行方式の確認が必要なTask
- 下流Taskのinputにある業務オブジェクトについて、上流に生成・添付元が見つからない明らかな系譜不整合
- schema v1.0/BPR拡張で定義されていない未知キー・誤ネストがないか（YAML parse成功だけでは合格にしない）
- BPR To-Beで `metadata.bpr.open_question_disposition` が欠落していないか
- BPRレビューではAs-Is/分析/判断YAMLも渡し、分析からTo-Beへ関係する未確認事項が全件 `resolved / carried_forward / not_applicable` で追跡されているか
- `metadata.open_questions` が `carried_forward` 項目と完全一致するか
- To-Be生成中に新たに生じたnon-blocking質問は `source: design` として追跡し、分析由来質問との混同を防いでいるか
- BPR To-BeでBlockingな未確認事項を `carried_forward` のまま残していないか
- 判断結果（承認結果・判定結果等）を出力するTaskが、その結果を条件分岐で消費せず無条件に後続へ進んでいないか
- descriptionに「〜の場合のみ」「両方成功時のみ」等の後続条件があるのに、Edge/Gatewayへ条件がモデル化されていないか
- `exception_owner` を持つ自動Taskが、成功/失敗を分けるExclusive GatewayなしでParallel Joinや後続へ進んでいないか（Error）
- 失敗/例外branchが `automation.exception_owner` の担当Taskへ接続されているか（Error）
- Parallel Split / Join がsystem実行branchを直接制御する場合、Gateway自身もtype=systemのparticipantに配置されていることを確認する。純粋な人Task並行だけは対象外。

## 到達性の表現

Reviewerが確認するのは次の2点であり、「すべての実行経路が必ず終了する」ことまでは保証しない。

- すべてのノードが少なくとも1つの開始点から到達可能か
- すべてのノードから少なくとも1つの終了点へ到達する経路が存在するか

最終回答でも、この保証範囲を超えて「すべての経路が終了する」などと表現しない。

## AIによる意味レビュー

機械レビューの後、ユーザーの説明と合理的な文脈推論を照合して次を確認する。

- ユーザーが明示した業務アクションや担当者が欠落していないか
- 担当者の引き渡しが自然か
- 分岐条件と分岐先に矛盾がないか
- 差し戻しや例外経路が説明内容に対して欠落していないか
- 並行処理として説明された処理が直列化されていないか
- XORの代替経路とParallel Joinを混同していないか
- 同じ処理が意味なく重複していないか
- 既知の開始条件・終了条件とモデルが一致しているか
- `description`、`inputs`、`outputs`、`system` の推論が文脈に対して不自然または過剰ではないか
- **同じ業務オブジェクトが、単なる状態変化のたびに別名へ増殖していないか**
- 上流`outputs`と下流`inputs`が同じ業務オブジェクトを指す場合、名称が一貫しているか
- **Taskの`description`で利用・確認すると説明している業務オブジェクトが、そのTaskの`inputs`から抜けていないか**
- 下流Taskの`inputs`にある業務オブジェクトについて、上流のどこで生成・添付・受領されたか、または外部入力であることを合理的に追跡できるか。中間Taskが利用しないオブジェクトまで機械的に通過I/Oへ追加する必要はない
- `保管されたエビデンス`、`確認済み申請`のように、別成果物ではない単なる状態変化を別名の業務オブジェクトとして生成していないか
- `確認完了`、`保管完了`、`承認完了`のような制御状態が、実際に参照されるデータでないのにI/Oへ混入していないか
- `task_type` が処理名だけから過剰に特殊化されていないか。人がPower Apps等を操作する処理を `business_rule` や `send` にしていないか、システム利用があるのに `manual` にしていないかを確認する
- `process.owner` など責任主体が、明示情報や十分な根拠なしに推論されていないか
- `metadata.inferences` が実際の補完事実に絞られており、共通モデリングルールまで推論として列挙されていないか
- 一般化した添付資料・根拠資料の名称として `証憑` が使われている場合、ユーザー指定がなければ `エビデンス` へ統一する余地がないか
- ユーザーが明示していない新規成果物をTask名だけから作っていないか。たとえば「エビデンスを保管」だけを根拠に `保管記録` を生成しない
- Start / End / Gatewayにparticipantがなくても構造上は成立するが、会話から担当レーンが明確なら未割当のまま残さず補完する
- ユーザーが明示した分岐表現（例: `不備なし`, `5万円未満`）がdefault経路になった結果、Edgeの`name`から消えていないか
- To-Beで `metadata.bpr` がある場合、条件付き採用の未確定条件を超えて `task_type`、担当、システム、経路を具体化していないか
- プロセス横断の状態管理・監視・通知だけを理由に、個別Taskが `automation.candidate: true` へ変わったり、横断改善の説明が `automation.notes` に混在していないか
- 自動化後の処理時間が未測定なのに `duration: 自動処理/件`、`即時` など時間ではない値を入れていないか
- To-Be詳細表示用の `metadata.bpr.change_log` が、改善分析のタイトル・期待効果・confidence・条件を再推測せずに保持しているか
- BPR To-Beの `metadata.open_questions` に、分岐・承認・例外経路・責任主体を変え得る未確認事項が残っていないか。残っている場合はFinal To-BeとしてErrorにする
- `承認結果` / `判定結果` / 成功状態等の結果がControl Flowへ反映されているか。文章上「非承認時は未確定」と書くだけで正常系へ無条件合流させない
- 「両方成功した場合のみ振込可能」のようなguard条件は、説明文だけでなくEdge条件またはExclusive Gatewayで明示されているか

例として、同じ申請を確認・差し戻し・修正・再申請・承認するだけなら、`経費申請`、`不備のない経費申請`、`修正済み経費申請`、`承認済み経費申請`と分けるより、同じ業務オブジェクト名 `経費申請` を維持することを優先する。

情報源にない新しい業務ルールを「不足」と断定しない。不明で確認が必要な場合は `metadata.open_questions` に追加する候補として提示する。

## 出力

- `process-review.json`: 構造化レビュー結果
- `process-review.md`: 人が確認しやすいレビュー結果
- Error がある場合はPublisherへ進めず、YAMLを修正して再レビューする。
- Warning は業務意図と照合して判断する。会話から明確に補正できる `missing_control_participant`、`missing_task_description`、`missing_branch_label`、`user_task_without_system` などの品質Warningは、可能ならYAMLを修正して再レビューしてからPublisherへ進む。

