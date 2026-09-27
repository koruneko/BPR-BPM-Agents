---
name: business-process-improvement-report-publisher
description: BPR改善分析YAMLを、非技術者が改善案を比較・判断できるHTML/Markdownレポートへ変換し、Human Gateで改善ID単位の採否を選べるようにするスキルです。
---

# Business Process Improvement Report Publisher

`improvement-analysis.yaml` を人が読むレポートへ変換する。利用者にYAMLを読ませることを前提にしない。

## 参照仕様

`resources/bpr-analysis-spec.md` に従う。

## レポートに必ず含める内容

- 改善ID (`IMP-xxx`)
- 提案タイトル
- 対象Task / プロセス横断範囲
- 改善分類
- 提案内容と理由
- `impact / effort / risk / confidence`
- 自動化/AI支援の評価（該当する場合）
- 想定・推奨する機能 / サービス。具体候補がない場合は、その理由
- 関連・依存する改善案（存在する場合）
- 前提条件
- 未確認事項
- As-Is上の根拠
- 外部調査ソース
- `process_pattern_coverage` のプロセス横断評価（ループ / ハンドオフ / 重複入力 / 並行依存）。改善案数とは別のカバレッジとして、関連Task・関連改善ID・評価理由を表示する。

## Human Gate UI

HTMLでは改善案ごとに以下を選べる。

- `未判断（要判断）`
- `採用`
- `条件付き採用`
- `保留`
- `見送り`

視覚的に判断状態を把握できるよう、カードの左境界・背景・状態ラベルを状態ごとに控えめに変える。色だけに依存せず状態ラベルも表示する。

`未判断` は「人による判断がまだ必要」であることをHuman Gate上部とカード内の `要判断` ラベルで示す。画面を過度にビジーにしないため、強い全面色や点滅は使わない。

条件付き採用では採用条件の判断メモを必須とする。Human Gate上部にも「条件付き採用では採用条件の入力が必須です」と明示する。条件付き採用を選んだ時点でメモ欄を自動展開し、見出しを `採用条件（必須）` に変え、必須理由をインライン表示する。条件が未入力の間は状態ラベルを `条件入力待ち` とし、「判断結果をコピー」を実行した場合は該当カードへスクロールして入力欄へフォーカスする。

通常の判断メモは `判断メモ（任意）` として `<details>` 内に格納し、必要なときだけ展開できるようにする。

## 実装候補の表示順と強調

`implementation_options` のYAML順に依存せず、レポートでは次の順に表示する。

1. `primary`（推奨候補）
2. `complementary`（補完候補）
3. `alternative`（代替候補）
4. 同じ `fit` なら `confidence: high → medium → low`
5. 同順位なら元のYAML順

`推奨候補` バッジを控えめに強調し、`補完候補` は弱い補助色、`代替候補` はニュートラル表示とする。先頭に出た候補がたまたま推奨に見える状態を作らない。

## 判断結果コピー

埋め込みブラウザーやSharePoint/Teams等ではClipboard APIが制限される場合があるため、次の順でコピーを試す。

1. `navigator.clipboard.writeText`
2. 一時textarea + `document.execCommand('copy')`
3. どちらも失敗した場合、判断結果textareaを画面に表示して手動コピーできるようにする

`prompt()` だけに依存しない。

ブラウザー上の選択は永続化されない。最終判断は会話でユーザーから明示的に受け取る。

## 外部リンク

外部調査ソースは通常のリンクとして出力し、新しいタブで開くことを要求する。SharePoint/Teams等のプレビュー環境では iframe/sandbox の制約により新規タブが禁止される場合があるため、クリック時に `window.open` を試し、失敗した場合はURLをクリップボードへコピーして利用者へ明示する。リンクを開けないことを無反応のままにしない。

## 生成

```bash
SCRIPT=$(find /home/oai/skills/appCatalog /app/skills -type f -name 'publish_improvement_report.py' -path '*/scripts/*' 2>/dev/null | head -n 1)
python "$SCRIPT" \
  --process /mnt/data/process.yaml \
  --analysis /mnt/data/improvement-analysis.yaml \
  --output-html /mnt/data/improvement-report.html \
  --output-md /mnt/data/improvement-report.md
```

## Human Gate

レポート生成後、主要な改善案をチャットでも簡潔に要約し、ユーザーへ改善ID単位で採否を求める。チャットの改善一覧はMarkdown表を原則使わず、1改善1行の箇条書きで表示する。条件付き採用の案内は「条件メモを入力できます」ではなく「条件メモの入力が必要です」とする。

- `採用`: To-Beへ反映可能
- `条件付き採用`: 条件をTo-Beの追跡情報へ保持したうえで反映可能
- `保留`: To-Beへ反映しない
- `見送り`: To-Beへ反映しない
- `未判断`: To-Beへ反映しない。判断が必要な状態として表示する

**ユーザーが明示的に採用または条件付き採用するまでTo-Be Modelerを実行しない。**

- `alternative` だけで `primary` がない改善案は、YAMLを変えずにレポート上では「検討候補」と表示する。

## 分析IDの引継ぎ

レポートに `analysis_id` を表示し、「判断結果をコピー」の先頭に `分析ID: <analysis_id>` を必ず含める。これを後続の `source_analysis_id` として利用し、別世代の分析判断を混在させない。
