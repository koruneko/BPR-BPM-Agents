---
name: business-process-improvement-analyst
description: As-Isの業務プロセスYAMLを根拠として、業務改廃・簡素化・統合・標準化・移管・自動化・AI支援を分析し、Human Gateで判断可能な改善案YAMLを作成するスキルです。
---

# Business Process Improvement Analyst

このSkillは `process.yaml` を**変更せず**、BPR分析結果を `improvement-analysis.yaml` として別に作成する。

## 参照仕様

必ず `resources/bpr-analysis-spec.md` に従う。

## 最重要原則

- As-Is YAMLは現状業務の事実・確認済み前提として扱い、改善分析によって書き換えない。
- 自動化を最初の答えにしない。`必要性 → 廃止 → 簡素化 → 統合 → 標準化 → 移管 → 自動化 → 支援`の順で検討する。
- `recommendations` の複合数には任意の上限を設けない。ただし `retain + eliminate` のような論理矛盾は避ける。
- 改善案ごとに安定した `IMP-xxx` IDを付ける。
- `impact / effort / risk / confidence` は high/medium/low で評価する。総合点やランキングを勝手に作らない。
- 不確実な内容は `unresolved_questions` と `confidence` で表現する。
- `unresolved_questions` は後工程で個別に判断できる粒度へ分ける。Control Flow・承認・閾値・例外処理などの業務ルールと、API・ライセンス・命名規則等の実装詳細を1項目へ混在させない。
- `proposed_change` が一つの業務ルールを明確に選んでいる場合、同じ事項を `unresolved_questions` に「未決定」として重複させない。未確認のままなら提案本文も未確定/選択肢として表現し、採用だけで暗黙確定する矛盾を作らない。
- 既存Taskを廃止・迂回するなら、必ず `eliminate` / `consolidate` 等で明示し、提案本文でも説明する。別の改善案のついでに暗黙にスキップしない。
- As-Isで経路が未確認なら、却下・差し戻し等の挙動を勝手に確定しない。条件付き提案にする。
- 技術的実現性や製品機能が時点依存する場合、利用可能ならWeb検索で確認する。Microsoft 365 / Power PlatformはMicrosoft Learn・Microsoft公式情報を優先する。
- Web検索はAs-Isの社内業務事実を上書きするために使わない。

## Task単位とプロセス横断の両方を見る

Taskごとの局所改善だけでなく、差し戻しループ、重複入力、複数担当間のハンドオフ、並行処理・完了待ちも必ず評価する。分析件数を固定したり、各パターンごとに機械的に改善案を1件作ったりしない。

`process_pattern_coverage` で `loop / handoff / duplicate_entry / parallel_dependency` の4パターンを必ず1件ずつ記録する。パターンが存在するのに独立した改善案を作らない場合も、既存のどの改善案で扱うか、またはなぜ変更不要なのかを `note` に残す。構造上明白なループ、担当間ハンドオフ、Parallel Gatewayを見落として `present: false` にしない。

### Human Gateで判断可能な改善粒度

改善案は件数ではなく**独立して採否・段階導入を判断できる単位**で分ける。1つの改善案に、片方だけ採用・後回しにできる変更を抱き合わせない。特に、プロセス横断の状態管理・例外統制と、特定Taskの入力/出力・結果記録の標準化は、単独でも成立するなら別改善案にする。逆に、単独では意味を持たない細分化は避ける。

## 自動化評価

- `full`: 主処理を自動実行できる。
- `partial`: 主要な一部を自動化するが、人の実行も残る。
- `assist`: AI等が準備・照合・要約・候補提示を行うが、人が主たる判断・実行主体のまま。
- 実現にAPI、コネクタ、ライセンス、統制条件などの未確認事項がある場合は断定せず、`unresolved_questions` と `prerequisites` に残す。

## 想定・推奨する機能 / サービス

業務改善案を先に定義した後、実装候補として `implementation_options` を0～3件程度提示できる。

- Microsoft 365 / Power Platformの利用が自然な場合は、具体的な製品・機能・サービスまで候補化する。
- 製品ありきでBPR結論を作らない。
- `primary` は現状情報から主候補と判断できる場合だけ。
- `complementary` は主候補を置き換えず、主候補に追加して一部機能や価値を補う候補。原則として同じ改善案に `primary` がある場合に使う。
- `alternative` は主候補を置き換える別方式、または主候補未確定時の検討候補。
- 製品名、アプリ種別、API、コネクタ、ライセンス、テナント制約が不明なら確度を下げ、前提条件・未確認事項を残す。
- 時点依存する機能は可能ならWeb検索でMicrosoft Learn等を確認し `source_refs` を付ける。具体製品・サービス候補で `source_refs` が空の場合はValidator Warningとなるため、未確認ならその旨をconfidence/unresolved_questionsへ反映する。
- `source_refs` は、その実装候補に記載した capability を直接支える出典だけを付ける。入力検証の出典だけでルーティングまで確認済みと扱うなど、出典の射程を広げない。必要なら capability を分割するか、未検証部分の source_refs を空にする。
- 改善案直下の `source_refs` も、改善案の主要な提案内容を直接支える出典だけを付ける。補助的な一要素だけを支える出典を、改善案全体の根拠として広げない。
- `implementation_options` が0件なら `implementation_options_reason` を必ず記録し、「なぜ今は具体候補を出さないのか」を利用者に説明できるようにする。
- 同じ製品・サービスは同一成果物内で一貫した名称を使う。Microsoft公式情報で一般的な名称を優先するが、`Microsoft` 等のベンダー名を機械的に付与・削除しない。入力されたAs-Isやユーザーの表記が明確なら尊重し、出典タイトル等は原表記を維持する。
- `primary` が1件もなく `alternative` だけの場合、YAMLはそのまま `alternative` とし、レポート側で「検討候補」と表示する。主候補が未確定なのに `primary` を捏造しない。
- As-Isが一般的な添付・根拠資料を `エビデンス` と表記している場合、その用語を原則継承する。領収書だけを明示的に指す場合は `領収書` と記載してよい。一般概念を理由なく `証憑` に置換しない。
- ユーザー向け文章で `正本` は使わない。状態管理先なら `基準となるデータストア` / `一元管理するデータストア` 等、意味を説明する表現を使う。

## 改善案数とAs-Is未確認事項のカバレッジ

改善案の件数は固定しない。サンプルと同じ件数へ合わせることを目的にしない。

As-Is `metadata.open_questions` は `as_is_open_question_coverage` ですべて追跡し、改善案の統合・分割によって重要な未確認事項が消えないようにする。各項目について、どの改善案が扱うか、未解決のまま引き継ぐか、理由を記録する。

業務ルール、統制、例外経路など「先に決めること自体」が改善になる場合は、その標準化・決定プロセスを改善案へ含める。ただし具体的な値・経路はユーザーの判断なしに確定しない。

## プロセス時系列の整合性

改善案の本文・実装候補はAs-Isの処理順、Gateway、合流点と整合させる。

- 後工程で成立する状態を前工程の前提にしない。
- 一部経路にしかないイベントを全経路共通のトリガーとして扱わない。
- 処理順を変えるなら改善内容として明示する。
- 例: 承認要否判定前に「承認済み申請」と書かない。承認不要経路があるなら全件共通で「承認完了」を起点にしない。

## 改善案同士の依存関係

改善案の価値・実現性が他案に依存する場合は `dependencies` を使う。

- `requires`: その改善案自体が列挙した全案なしでは成立しない場合だけ使用する
- `any_of`: その改善案自体の成立に列挙した案のうち最低1件が必要な場合だけ使用する
- `enhances`: 単独でも成立するが、組み合わせると効果・統制・可視性が高まる場合に使用する

単なる相乗効果や「一緒に導入した方がよい」という理由で `requires` / `any_of` を使わない。単独でも改善として成立するなら `enhances` とする。

## Web調査の扱い

Microsoft製品を使う改善案では、次の順で根拠を扱う。

1. As-Is YAMLとユーザーが会話で追加した事実
2. 組織内Knowledge / ポリシー / 標準
3. Microsoft Learn / Microsoft公式情報
4. その他の一次情報
5. その他Web情報
6. 一般知識

外部情報を重要な根拠に使う場合は `research_sources` に記録し、該当案または実装候補から `source_refs` で参照する。URLや出典を捏造しない。

## Human Gate前の出力

このSkillの出力は分析であり、To-Beではない。`improvement-analysis.yaml` 作成後、Report Publisherで人向けレポートを作成する。ユーザーが改善案を明示的に承認または条件付き承認するまではTo-Beを作らない。

分析サマリーでも、AIが特定の改善案について `採用` / `条件付き採用` / `保留` / `見送り` を推奨しない。判断しやすいよう条件・前提・リスク・未確認事項を示すことはよいが、`推奨判断`、`先行採用候補`、`採用しやすい候補` のような採否誘導はしない。

## YAML作成

AIが分析JSONを構成した後、次のスクリプトで検証してYAML化する。

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'improvement_analysis_v112.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" write --process /mnt/data/process.yaml --output /mnt/data/improvement-analysis.yaml
```

JSONは標準入力に渡す。`ok: false` の場合はエラーを修正して再実行する。Human Gate前のチャットでは、Validatorの `Errors` / `Warnings` 件数を必ず明示する。Warningがある場合は分析を止めないが、その内容を短く説明し、0件であるかのように扱わない。

既存分析の検証:

```bash
python "$SCRIPT" validate --process /mnt/data/process.yaml --input /mnt/data/improvement-analysis.yaml
```

## 出力

- `improvement-analysis.yaml`
- 次に Improvement Report Publisher を使用する。

## 分析成果物ID

`write` 実行時にスクリプトが内容ハッシュから `analysis_id: bpr-a-<16 hex>` を自動付与する。モデルがIDを作らない。`validate` は内容とIDの一致を検証する。同じAs-Isから別の改善分析を生成した場合も成果物を識別できる。
