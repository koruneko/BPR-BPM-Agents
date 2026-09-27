# Material Business Rule Gate structured contract v1.1

Material Gateの**正規データは構造化YAML**である。ユーザー可視Markdownは参考出力であり、会話応答の文面を一字一句固定するためのものではない。

```yaml
gate_version: '1.1'
analysis_id: bpr-a-example
intro: optional text
questions:
  - id: '1'
    source_refs:
      - source: IMP-004
        question: 部門長が承認しない場合は却下終了、社員差し戻し、上長差し戻しのどの経路か。
    question: 部門長が申請を承認しない場合、どの経路へ進めますか？
    recommendation:
      status: recommended
      option_id: A
      rationale: 既存の差し戻しループを再利用できるため。
      basis: minimal_change
      confidence: medium
      provisional: false
    options:
      - id: A
        label: 社員へ差し戻し、修正後に上長確認から再開する
        explanation: optional explanation
      - id: B
        label: 非承認として終了する
        explanation: optional explanation
  - id: '2'
    source_refs:
      - source: IMP-003
        question: 閾値判定に使用する金額定義は税込、税抜、申請合計のどれか。
    question: 5万円以上の判定には、どの金額を使用しますか？
    recommendation:
      status: none
      rationale: As-Isから優劣を判断できる根拠がないため。
      confidence: low
      provisional: true
    options:
      - id: A
        label: 税込の申請合計額
      - id: B
        label: 税抜の申請合計額
footer_note: optional text
```

## Structured YAML rules

- `gate_version` は `1.1`。
- `analysis_id` は `improvement-analysis.yaml` の `analysis_id` と完全一致。
- 各Questionは数値文字列 `id`、`source_refs`、質問文、`recommendation`、2件以上のOptionを持つ。
- `source_refs[].source` は `IMP-xxx` / `analysis` / `design`。
  - `IMP-xxx`: 対象改善の `unresolved_questions` と `question` を完全一致させる。
  - `analysis`: `analysis_open_questions` と完全一致させる。
  - `design`: To-Be設計中に新しく生じた質問。分析YAMLとの完全一致検証は行わない。
- 同じ元質問を複数のユーザー向けQuestionへ重複参照しない。
- `recommendation.status` は `recommended` または `none`。
  - `recommended`: 既存Optionを指す `option_id` と非空 `rationale` が必須。
  - `none`: `option_id` を持たず、推奨なしの理由を `rationale` に保持する。
- `basis` は任意で `source_evidence / design_consistency / minimal_change / control_safety / other`。
- `confidence` は任意で `low / medium / high`。
- `provisional` は任意のboolean。
- 定義外キーはError。YAML parse成功だけでは合格にしない。

## Canonical Markdown

Rendererは機械契約の可視確認用にcanonical Markdownも生成する。

- `recommended` は `#### 【推奨】A: ...` と `推奨理由: ...`。
- `none` は `**推奨なし**` と `理由: ...`。

ただし、**Agentの会話応答をcanonical Markdownと完全一致させることは要求しない**。モデルは読みやすく自然な表現へ整えてよい。守るべきなのは次の意味論である。

- 推奨Optionを述べる場合はYAMLの `recommendation.option_id` と一致する。
- YAMLが `status: none` のQuestionに推奨Optionを新しく作らない。
- Optionの意味、元質問との対応、推奨理由を逆転・捏造しない。
- ユーザー回答後の `business_rule_resolutions` は `source_refs` の元質問へ展開して記録する。
