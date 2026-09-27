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
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'review_process.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" --input /mnt/data/process.yaml --json-output /mnt/data/process-review.json --md-output /mnt/data/process-review.md
```

スクリプトは少なくとも次を機械的に確認する。

- schema v1.0で定義されていない未知キー・誤ネスト（`unknown_schema_key`）
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
- 承認済みを示すTask名（例: `経費申請を承認`）の直後で、Exclusive Gatewayが承認/却下を判定している意味矛盾
- `task_type: user` なのに利用システムが未設定で、実行方式の確認が必要なTask
- 下流Taskのinputにある業務オブジェクトについて、上流に生成・添付元が見つからない明らかな系譜不整合
- Taskの`description`で `指摘内容`、`差し戻し理由`、`却下理由`、`入力エラーの内容`など修正・再処理の根拠情報を明示的に参照しているのに、対応する`inputs`がないケース（`referenced_operational_info_missing`）

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
- **差し戻し理由・修正指示・入力エラー情報など、後続Taskが修正や再処理の根拠として参照する情報がI/Oから抜けていないか。** `指摘内容に基づいて修正` と説明するなら、`差し戻し指摘`等が後続`inputs`にあり、上流`outputs`まで追跡できる状態を優先する
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

例として、同じ申請を確認・差し戻し・修正・再申請・承認するだけなら、`経費申請`、`不備のない経費申請`、`修正済み経費申請`、`承認済み経費申請`と分けるより、同じ業務オブジェクト名 `経費申請` を維持することを優先する。

情報源にない新しい業務ルールを「不足」と断定しない。不明で確認が必要な場合は `metadata.open_questions` に追加する候補として提示する。

## 出力

- `process-review.json`: 構造化レビュー結果
- `process-review.md`: 人が確認しやすいレビュー結果
- Error がある場合はPublisherへ進めず、YAMLを修正して再レビューする。
- Warning は業務意図と照合して判断する。会話から明確に補正できる `missing_control_participant`、`missing_task_description`、`missing_branch_label`、`user_task_without_system`、`referenced_operational_info_missing` などの品質Warningは、可能ならYAMLを修正して再レビューしてからPublisherへ進む。
