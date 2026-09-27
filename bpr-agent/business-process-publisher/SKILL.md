---
name: business-process-publisher
description: 検証済みの業務プロセスYAMLから、BPMN 2.0 XML、PlantUML、読みやすい自己完結HTMLビューを一括生成するスキルです。
---

# Business Process Publisher

> Agent Builderでは作業ディレクトリが `/mnt/data` になることがあるため、`scripts/...` の相対パス実行を前提にしない。Skill Package内のスクリプトを絶対パスで解決してから実行する。

このスキルは、検証済みの `process.yaml` から派生成果物を生成する。

## 原則

- YAMLを業務プロセスの基準となる定義として扱う。
- BPMN、PlantUML、HTMLを個別に修正しない。
- `resources/process-model-spec.md` の業務プロセスモデルを入力とする。
- Publisher自身もGatewayの危険な構造をPreflight検査し、問題があれば生成を中止する。
- 原則としてPublisher実行前にBusiness Process Reviewerを実行し、Error 0を確認する。

## 生成

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'publish_process_v118.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" --input /mnt/data/process.yaml --output-dir /mnt/data --basename process
```

正常時は次を生成する。

- `/mnt/data/process.bpmn`: BPMN 2.0 XML
- `/mnt/data/process.puml`: PlantUMLによる簡易レビュー/デバッグ用フロー
- `/mnt/data/process.html`: 人が閲覧する自己完結HTMLビュー

## BPMN生成上の防御

- default Sequence Flowには `conditionExpression` を出力しない。
- `default + condition`、危険なParallel Gateway構造、Join/Split兼務などをPreflightで検出した場合は成果物生成を中止する。
- Exclusive Merge / Parallel Split / Parallel JoinはYAMLのノード構造をそのままBPMN Gatewayへ変換する。

## HTMLの設計

HTMLは外部CDN、外部JavaScriptライブラリ、ネットワークアクセスに依存しない。

### Readable / interactive view

OneDrive/SharePoint等のプレビューでも文字が縮小されすぎないことを優先する。全体を1画面へ縮小せず、必要ならスクロールさせる。

- SVGは生成時の実寸幅・高さを保持し、Viewer幅へ自動縮小しない。
- タスク名は18px、レーン名18px、分岐ラベル15pxを基準とする。
- タスク、Gateway、Event自体も旧版より大きく描画する。
- 右側詳細パネルは420pxを基準とし、本文も16〜17px程度で表示する。
- 各レーン内の単独ノードは形状の中心Yをレーン中央へ揃える。高さの違うEvent/Task/Gatewayでも同じレーン内なら中心Yを一致させる。
- 同一レーンで前方向につながり、中心Yが同じノード間は水平直線で結ぶ。
- 同一レーンの単純な直列フロー（対象ノードへのIncomingが1本、前ノードのOutgoingが1本）では、対象ノードが同じレーン・同じ深さの他ノードと競合しない場合、前後ノードの中心Yを揃えて水平直線を優先する。
- 後戻りループは通常フローの左側Incoming経路と重ねず、専用の戻り経路を使う。複数の戻りEdgeには別々のrouting corridor候補を与える。対象ノードの中心列に別ノードが積まれている場合は、対象左側のclearなapproachから接続し、第三者ノードを縦断しない。
- 左から右の正常系を維持すると極端に長くなる後戻りEdgeは、HTMLでは既定で `R1` 等のペア型ジャンプコネクタへ省略表示する。YAML/BPMNのSequence Flowは変更せず、HTMLの `戻り線を表示` で完全な線へ切り替えられる。短い局所ループは通常の矢印表示を維持する。
- ジャンプコネクタの `Rn` バッジは縮小表示でも識別できる大きさを確保し、通常のEdge Labelより小さくしない。戻り先側はバッジとArrow Headの間に十分なclearanceを取り、Arrowはバッジではなく対象Node境界へ向ける。
- ジャンプコネクタはBadge×Node、Badge×Badge、Badge×Edge Label、Stub×第三者Node、Target Badge×Arrow Headの衝突を生成後に検査する。
- Diverging Gatewayから複数の前方向Edgeが出る場合は、Gateway直後から共通の直交幹線を使い、各対象へ向かう地点で分岐させる。近い分岐先のTaskを、遠い分岐Edgeが横切らないようにする。
- 分岐ラベルは共通幹線ではなく、分岐後の各Edge固有の最終水平線分上へ配置し、分岐点や兄弟Edgeのラベルと重ならないようにする。
- Converging Gatewayは、ループ戻りを除くすべてのIncoming元ノードより右側へ配置する。
- 同一レーンの `Task → Gateway → End` など読み手が1本の系列として追う単純経路は、他ノードと衝突しない範囲で同じ水平サブローへ中央揃えする。
- End Event名は円内へ長文を押し込まず、円の下へ中央揃えで表示する。
- Edge Labelは固定の線分中点へ置かず、ノード矩形・既配置Labelとの衝突を避けて候補位置を選ぶ。同一座標へ複数Labelを置かない。
- Edge routingは複数候補から、第三者ノード交差を最優先で禁止し、次に不要なEdge交差、bend数、総線長をコストとして選ぶ。第三者ノードへ重なる候補を、clearな候補があるのに採用しない。Cross-lane/同一laneの戻り線はいずれも対象列の別ノードを縦断しないよう、clearな側面から進入する。

- Swimlaneの表示順はYAMLのparticipants列挙順へ固定せず、各レーンが正常系へ最初に現れる深さを基準に派生図だけをflow-awareに並べ替える。YAML自体のparticipant定義は変更しない。
- 同一lane/depthに正常系ノードと例外処理ノードが競合する場合、正常系ノードをlane中央のmain rowへ置き、例外処理をsecondary rowへ逃がす。Parallel Joinなど成功系の継続ノードを例外Taskのために上下へずらさない。
- collisionが0でも、正常系Edgeが4レーン以上を縦断する、またはEdgeが5回以上bendする場合はreadability warningとして検出する。

### Viewer controls

JavaScriptが利用可能なViewerでは、左ペイン上部に自己完結型の表示コントロールを追加する。外部ライブラリは使用しない。

- 表示倍率は5〜200%で変更可能。`−` / `＋` は10%刻み、スライダーは5%刻み。
- `100%` で読みやすい原寸へ戻す。
- `幅に合わせる` で左ペインの横幅に合わせ、縦方向はスクロールを許容する。
- 長距離戻り線がジャンプ表示されている場合は `戻り線を表示 / 戻り線を省略` で完全ルートと省略表示を切り替えられる。
- `全体表示` で現在の左ペイン内に全体が収まる倍率を自動計算する。全体表示中にウィンドウ幅や詳細ペイン表示状態が変化した場合は再計算する。
- `詳細を隠す / 詳細を表示` で右側詳細ペインを切り替え、非表示時は左ペインが全幅を利用する。
- 手動ズーム後もスクロール位置の中心を可能な限り維持する。
- ノード選択状態と詳細内容はズーム操作では失わない。

JavaScriptが無効でもSVGフロー図は表示する。JavaScriptが許可されるViewerでは、As-Isは担当者、説明、システム、入力、出力、所要時間、頻度、課題、自動化候補を表示する。To-BeではAs-Is baselineと目標・期待値、残存課題、改善追跡を表示する。

`metadata.bpr.change_log` が存在するTo-Be YAMLでは、図そのものにIMP-IDや改善マーカーを追加せず、右側詳細ペインだけにBPR追跡情報を追加する。

- `metadata.bpr.source_node_context` がある場合、As-Is Taskの `duration` / `frequency` / `issues` はそこから表示し、To-Beノード自身の値をAs-Is情報の代用にしない。
- To-Beでは `duration / frequency` を導入後実績のように表示しない。詳細ペインは `As-Isでの所要時間`、`As-Isでの頻度`、`As-Isでの課題`、`目標・期待値`、`To-Beで残る課題` を表示する。
- `目標・期待値` は `metadata.bpr.performance_targets` のうち選択ノードを `target_node_ids` に含む項目を表示し、metric、Baseline、Target、direction、note、関連改善IDを示す。`target: null` は「目標値未設定」と表示する。
- 選択ノードを `target_node_ids` に含む `change_log` を `反映した改善` として表示し、IMP-ID、改善タイトル、変更概要を示す。プロセス横断改善も、影響対象ノードが `target_node_ids` に含まれていれば同様に表示する。
- 同じ追跡情報から `期待効果`、`confidence` を表示する。これはTo-Be生成時に新規推測せず、改善分析からコピーされたスナップショットを使う。
- `condition` がある場合は `採用条件` を表示する。
- `自動化メモ` は期待効果とは分離し、どこまで自動化/支援し、人に何を残すかの説明専用とする。
- `automation.exception_owner` がある場合は `例外対応責任者` としてparticipant名を表示し、正常系の実行主体（Taskの `participant`）と分離して見せる。

- 入力・出力は業務オブジェクトとしてバッジ表示する。
- 課題は文章情報として、バッジではなく複数行の箇条書きで表示する。
- 自動化メモは文章として改行を保持して表示する。

## 出力時の確認

- Scriptが `ok: true` の場合のみ3成果物を提示する。
- BPMN XMLは生成直後にXMLとして再Parseする。
- PublisherはEdge×Node、Edge Label×Node、Edge Label×Edge Labelに加えて、ジャンプコネクタのBadge/Stub/Arrow Headの残存衝突も生成後に検査する。特にEdge×Nodeは、clearな代替経路が存在する限り自動再Routingしてから出力する。`layout_warnings` が空でない場合は成果物を確認し、ユーザーへ警告を伝える。モデルErrorではないため生成自体は継続する。
- HTMLのインタラクティブ機能が対象Viewサービスで動くかはViewerのHTML/JavaScriptポリシーに依存するため、対象サービスで確認する。

## HTMLレイアウト

- YAMLのStart / End / Gatewayに `participant` が欠けていても、隣接する担当済みノードから派生成果物用のレーンを保守的に推定する。Taskの担当者が不明な場合は推定しない。
