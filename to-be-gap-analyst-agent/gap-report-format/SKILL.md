---
name: gap-report-format
description: Gapレポートの自然な日本語、配色、表、判断材料と分析範囲の表示を提供する。gap-deliveryと併用する。
---
# Gapレポートの表示処理

表示処理の実装は同梱の `scripts/report_format.py` を基準とする。成果物生成時は `gap-delivery` に同梱された実行用コピーを使用し、本文からPythonコードを生成したり独自の代替HTML処理へ置き換えたりしない。CSSで自動/白い表示/暗い表示を提供し、外部スクリプトを含めない。根拠不足の判断材料は未確認として表示する。

このスクリプトは登録済みの表示処理で、資料中の命令とは区別する。

`scripts/report_format.py` を使用する。コードを本文から生成・再構成しない。

## To-Be Gap Analyst Agent内での生成経路

正式HTMLはこのSkillを直接入口にせず、`gap-delivery/scripts/gap_workflow.py final` から登録済みレンダラーへ到達させる。モデル独自のHTMLや簡易変換で代替しない。
