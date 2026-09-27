---
name: business-process-modeler
description: ユーザーとの対話から業務プロセスを構造化し、基準となるYAML定義を作成・更新するスキルです。担当者、処理、条件分岐、差し戻し、並行処理、利用システム、入出力などを保持します。
---

# Business Process Modeler

> Agent Builderでは作業ディレクトリが `/mnt/data` になることがあるため、`scripts/...` の相対パス実行を前提にしない。Skill Package内のスクリプトを絶対パスで解決してから実行する。

このスキルは、会話で確認した業務内容から `process.yaml` を作成・更新するために使用する。

## 参照仕様

必ず `resources/process-model-spec.md` に従う。

特に次のGateway規則を守る。

- `default: true` のEdgeには `condition` を設定しない。
- 排他的な代替経路を合流させる場合は `gateway_exclusive` のMergeを使用する。
- 排他的な複数経路を `gateway_parallel` に直接合流させない。
- 排他分岐の後に並行処理を開始する場合は、`Exclusive split -> Exclusive merge -> Parallel split` の順に明示する。
- v1.0では1つのGatewayにJoinとSplitを兼務させない。必要なら連続する2つのGatewayを作成する。
- Parallel GatewayのOutgoing Edgeに `condition` / `default` を付けない。

## 情報の扱い

- ユーザーが明示した業務アクション、担当者、判断条件、差し戻し、例外、システム利用を省略しない。
- `description`、`inputs`、`outputs`、`system` は、会話と前後関係から合理的に導ける場合は補完してよい。これらが未指定でも、主要フローを構造化できるなら初回出力を止めない。
- 新しい承認条件、責任者、例外ルール、工数、頻度、規制要件など、業務上の結論を変える内容は十分な根拠がなければ確定しない。特に `process.owner` は担当者の配置だけから推定しない。
- 重要な未確認事項は `metadata.open_questions` に保持する。
- 重要な推論で後から前提を追跡した方がよいものは `metadata.inferences` に簡潔に記録できる。
- 既存YAMLの更新では、変更されていない確認済み情報と既存IDを保持する。
- `metadata.inferences` には、利用システムなどユーザー入力にない業務事実を補完した重要な推論を記録する。`経費申請`の名称を維持する、といった共通モデリングルール自体は推論として記録しない。

## 最小構成を先に出力する

- 開始から終了までの主要な処理、担当者、分岐条件、差し戻し・例外、並行処理を表現できれば、owner、duration、frequency、issues、automationなどが未設定でもYAMLを作成する。
- 不明点がフローの接続や分岐結果そのものを変える場合だけ、初回出力前に確認する。
- 初回成果物を出した後で、業務分析に有用な不足情報をAgentがユーザーへ追加提案する前提で、オプション項目を埋めるためだけにモデル作成を待たせない。

## Task Typeの選択

- 人がアプリケーションを操作するTaskは `user` を使用する。
- 実行方式が不明な人の作業は `generic` でよい。
- `manual` はアプリケーション等の支援なしに人が行うことが明確な場合だけ使用する。
- `business_rule` はBusiness Rules Engine等によるルール評価であることが明確な場合だけ使用し、人が金額や条件を確認するTaskには使用しない。
- `send` / `receive` はBPMN上のメッセージ送受信Taskであることが明確な場合だけ使用し、単なる「差し戻し」「通知」という名称だけで選ばない。
- `service` / `script` も自動実行方式が明確な場合だけ使用する。

## 用語

- 領収書や添付資料などを一般化した業務オブジェクト名が必要な場合は `エビデンス` を使用する。
- ユーザーが `領収書`、`請求書` など具体的な名称を指定した場合は、その名称を維持する。

## 入出力のモデリング

- `inputs` / `outputs` は、Taskが実際に受け取る・引き渡す業務オブジェクトや情報を表す。
- **同じ業務オブジェクトは、確認・承認・差し戻し・修正・再申請などで状態が変わっても、別物にならない限り同じ名称を使う。**
- 状態を表すためだけに `不備のない経費申請`、`金額確認済み経費申請`、`承認済み経費申請` のような派生名を増やさない。実体が同じなら `経費申請` のまま維持し、状態や判断はTask、Gateway、Edge condition、`description` で表現する。
- 前Taskの`outputs`と後Taskの`inputs`で同じ業務オブジェクトを受け渡す場合は、表記を完全に一致させる。
- **後続Taskで参照する業務オブジェクトは、上流のどこで生成・添付・受領されたか追跡できるようにする。** Taskの`description`で「エビデンスを確認する」と書くなら、そのTaskの`inputs`にも`エビデンス`を含める。下流Taskが`エビデンス`を使うなら、上流側にその由来となる`outputs`または明示的な外部入力が存在するようにする。
- **差し戻し理由、修正指示、指摘内容、入力エラー情報など、後続Taskが修正・再処理の根拠として実際に参照する情報はI/Oへ保持する。** 差し戻しTaskが指摘を伝え、後続Taskがその指摘に基づいて修正する場合は、`差し戻し指摘`等を前者の`outputs`と後者の`inputs`に含める。エラー内容を確認して修正する場合も、上流で得られる`入力エラー情報`等を修正Taskの`inputs`へ含める。
- 中間Taskがそのオブジェクトを実際には利用・更新しない場合、系譜をつなぐ目的だけで機械的に全Taskの`inputs` / `outputs`へ通過させる必要はない。
- Taskが業務オブジェクトを確認・更新・差し戻し・承認・保管しただけで、その実体が別成果物へ変わっていない場合は、出力する際も元の名称を維持する。
- たとえば `エビデンス -> 保管されたエビデンス` のように**状態だけを名称へ埋め込んだ派生名を作らない**。保管という状態はTask名や`description`で表現し、別の保管記録そのものを生成する場合だけ `保管記録` などを別オブジェクトとして追加する。
- 「確認完了」「保管完了」「承認完了」のような**制御上の完了状態だけ**を、後続Taskが実際にデータとして参照しない限り `inputs` / `outputs` にしない。順序や待ち合わせはSequence FlowやGatewayで表現する。
- 本当に新しい成果物・記録・通知・外部データが生成される場合だけ、新しい業務オブジェクト名を追加する。

例：同じ経費申請を確認・差し戻し・修正・再申請する場合

```yaml
- id: submit_expense
  type: task
  name: 経費精算を申請
  inputs: [経費情報, エビデンス]
  outputs: [経費申請, エビデンス]

- id: manager_review
  type: task
  name: 申請内容を確認
  inputs: [経費申請, エビデンス]
  outputs: [経費申請]

- id: return_application
  type: task
  name: 社員へ差し戻し
  inputs: [経費申請]
  outputs: [経費申請, 差し戻し指摘]

- id: revise_resubmit
  type: task
  name: 内容を修正して再申請
  inputs: [経費申請, 差し戻し指摘]
  outputs: [経費申請]
```

## 品質セルフチェック

YAMLを書き出す前後に、次を確認する。これらは初回可視化を遅らせるための追加質問ではなく、会話から合理的に補える範囲をモデルへ反映するための品質確認である。

- 文脈から内容が分かるTaskには、簡潔な `description` を設定する。
- 担当者が分かるTaskには `participant` を設定する。Start / End / Gatewayも、前後関係から担当レーンが明確なら `participant` を設定する。特にDecision Gatewayは判断者のレーン、Endは最終処理担当のレーンを優先する。
- Exclusive Gatewayの分岐Edgeには、default経路を含めて人が読める `name` を付ける。`default: true` は `condition` を持たないが、`不備なし`、`5万円未満` などの明示ラベルは保持する。
- `task_type: user` を使う場合は、アプリケーション利用が文脈上確認できるか確認する。実行方式が不明で `system` も特定できない作業は `generic` を優先する。
- Task名や説明から自然に導けない新規Outputを作らない。たとえば単に「エビデンスを保管」とあるだけで `保管記録` を新規生成しない。
- Taskの`description`で `指摘内容`、`差し戻し理由`、`却下理由`、`入力エラーの内容`などを参照して修正・再処理すると説明している場合、その根拠情報が`inputs`にあり、上流`outputs`まで追跡できるか確認する。
- `process_model.py` がWarningを返した場合、会話から修正可能な品質WarningはYAMLを修正してから次へ進む。

## Strict Schema Validation

- YAMLがparseできるだけでは合格としない。`resources/process-model-spec.md` のschema v1.0で定義されていないキーや誤ネストはErrorとする。
- 例: `descripton` のようなtypo、`automation.candidates` のような未定義キー、`metadata.bpr` のようなBPM schema外の拡張を黙って受理しない。
- 既存YAMLの更新でも同じ検証を行い、未知キーを保持したまま成果物を生成しない。

## YAML作成

AIが完全なJSONモデルを組み立てた後、次のスクリプトで正規化・検証してYAMLを書き出す。

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'process_model.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" write --stdin-format json --output /mnt/data/process.yaml
```

JSONは標準入力へ渡す。短い場合のみ `--json` を使用してよい。

スクリプトが `ok: false` を返した場合は成果物として扱わない。エラー内容に従ってモデルを修正し、再実行する。特にGateway構造エラーの場合は、業務ルールを勝手に変更せず、必要なControl-flow Gatewayを追加して解消する。

既存YAMLを検証するときは次を使う。

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'process_model.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" validate --input /mnt/data/process.yaml
```

## 出力

- 正常に生成できたら `process.yaml` を業務プロセス定義として扱う。
- BPMN、PlantUML、HTMLが必要な場合は、YAMLをReviewerへ渡し、Errorがないことを確認してからPublisherへ進む。
