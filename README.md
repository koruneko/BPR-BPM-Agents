# BPR / BPM Agents

Microsoft 365 Copilotで、**現在の業務を可視化する → 改善後の業務を設計する → 変更点から次の行動を決める**、という3つの作業を支援するAgentのサンプル集です。各Agentは単独でも利用できます。

## どのAgentを使う？

| Agent | やりたいこと | 主な入力 | 主な成果物 |
|---|---|---|---|
| **[BPM Agent](./bpm-agent/)** | 現在の業務（As-Is）をヒアリングしてフローにする | 業務の説明 | `process.yaml`、BPMN、PlantUML、HTML |
| **[BPR Agent](./bpr-agent/)** | 業務課題と改善案を整理し、採用した改善からTo-Beを設計する | BPMの `process.yaml` | 改善分析・採否のYAML、`to-be-process.yaml`、レポート、業務フロー |
| **[To-Be Gap Analyst Agent](./to-be-gap-analyst-agent/)** | As-IsとTo-Beの差から、誰と何を確認・決定・準備するか整理する | BPMとBPRの主要4ファイル | Gap一覧、Next Action、依存関係図、詳細レポート |

### 使い方の例

```text
[BPM Agent]
立替経費の申請から振込までを可視化したいです。担当者と処理の流れを説明するので整理してください。

[BPR Agent]
BPM Agentで作成したprocess.yamlを使い、課題と改善案を検討してください。
改善案を確認して採用するものを選んだ後、To-Beの業務フローを作成したいです。

[To-Be Gap Analyst Agent]
As-Isのprocess.yamlと、BPRのto-be-process.yaml、improvement-analysis.yaml、
improvement-decisions.yamlを比較してください。変更点と、最初に誰と何を確認すべきか整理したいです。
```

## 利用を開始する方法

**Agent全体のZIP**と**Skill単体のZIP**は用途が異なります。利用環境に合わせてどちらかの方法を選んでください。

### 方法A：Agentパッケージを導入する

すでに構成済みのAgentを利用する方向けです。

1. 下表の **Agent ZIP** をダウンロードします。
2. 組織でカスタムアプリのアップロードが許可されている場合、Microsoft Teamsの **［アプリ］→［アプリを管理］→［アプリをアップロード］→［カスタムアプリをアップロード］** からZIPを選択します。
3. 追加したAgentをTeams／Microsoft 365 Copilotで開いて試します。テナント設定によっては、管理者による導入が必要です。

| Agent | 配布用Agent ZIP | 個別の説明 |
|---|---|---|
| BPM | [BPM Agent.zip](./BPM%20Agent.zip) | [BPM Agentの使い方](./bpm-agent/) |
| BPR | [BPR Agent.zip](./BPR%20Agent.zip) | [BPR Agentの使い方](./bpr-agent/) |
| To-Be Gap Analyst | [To-Be Gap Analyst Agent.zip](./To-Be%20Gap%20Analyst%20Agent.zip) | [Gap Analystの使い方](./to-be-gap-analyst-agent/) |

詳細：[Microsoft Learn — 組織でのAgentのサイドロード](https://learn.microsoft.com/en-us/microsoft-365/copilot/agent-essentials/agent-policies/agent-sideload)。

### 方法B：Agent BuilderでInstructionsとSkillsを登録する

Agentの構成を確認・編集しながら試す方向けです。**上表のAgent ZIPを、Agent Builderの［スキルを追加］へアップロードする方法ではありません。**

1. このリポジトリをCloneするか、GitHubの **［Code］→［Download ZIP］** で取得して展開します。
2. Python 3で次のコマンドを実行し、登録するAgentのSkillごとにZIPを作成します。外部ライブラリは不要です。

   ```bash
   python scripts/package_skills.py --agent bpm
   python scripts/package_skills.py --agent bpr
   python scripts/package_skills.py --agent gap
   ```

3. Microsoft 365 CopilotのAgent BuilderでAgentを新規作成し、各Agentディレクトリの **Instructions** を［構成］に設定します。
4. ［構成］→［スキル］→［追加］で、`dist/skills/<agent>/` に生成された**個別のSkill ZIPを一つずつ**アップロードします（`SKILL.md`単独ではなくZIPを指定）。
5. プレビューで業務の説明や入力資料を与え、想定どおり処理されるか確認します。

| Agent | Instructions | 登録するSkill数 |
|---|---|---|
| BPM | [`bpm-agent/agent-instructions.md`](./bpm-agent/agent-instructions.md) | 3 |
| BPR | [`bpr-agent/bpr-agent-instructions.md`](./bpr-agent/bpr-agent-instructions.md) | 5 |
| To-Be Gap Analyst | [`to-be-gap-analyst-agent/agent-instructions.md`](./to-be-gap-analyst-agent/agent-instructions.md) | 5 |

詳細：[Microsoft Learn — Agent BuilderへカスタムSkillを追加](https://learn.microsoft.com/ja-jp/microsoft-365/copilot/extensibility/agent-builder-add-skills)。Skill機能はプレビューで、対象ライセンス・Frontierプログラム等の利用条件があります。UIや登録可否はテナントによって異なります。

## Agent間で受け渡すファイル

```text
業務の説明
  ↓ BPM Agent
process.yaml                         ← 現在の業務（As-Is）
  ↓ BPR Agent
improvement-analysis.yaml           ← 改善案と分析根拠
improvement-decisions.yaml          ← ユーザーによる改善案の採否
to-be-process.yaml                 ← 採用した改善を反映したTo-Be
  ↓ To-Be Gap Analyst Agent（As-IsとBPR成果物3つの計4ファイルを照合）
Gap一覧・Next Action・依存関係図・詳細レポート
```

BPR Agentは、ユーザーが**採用または条件付き採用**した改善だけをTo-Beへ反映します。Gap Analystは、業務導入の可否を自動承認するAgentではありません。各Agentの入力条件・作業例・成果物は個別READMEをご覧ください。

## ソース・サンプル

| Agent | ソース・Skill | サンプル |
|---|---|---|
| BPM | [`bpm-agent/`](./bpm-agent/) | [`bpm-agent/sample-outputs/`](./bpm-agent/sample-outputs/) |
| BPR | [`bpr-agent/`](./bpr-agent/) | [`bpr-agent/sample-outputs/`](./bpr-agent/sample-outputs/) |
| To-Be Gap Analyst | [`to-be-gap-analyst-agent/`](./to-be-gap-analyst-agent/) | 現時点では同梱なし |

公開用リポジトリです。**実際の顧客データ、個人情報、認証情報、未公開の業務資料、利用者が生成した分析レポートをPushしないでください。** Agentが出力するファイルには入力資料の内容が含まれる場合があります。

## 注意事項・利用条件

生成内容はAIの推論を含みます。元の業務、承認・権限・監査・コンプライアンス要件と照合して確認してください。これらはMicrosoftの公式製品・公式サンプル・公式サポートではありません。

- [Privacy Statement](./PRIVACY.md) / [Terms of Use](./TERMS.md)
- コードとドキュメント：[MIT License](./LICENSE)（Microsoft製品や第三者のコンテンツには各利用条件が適用されます）
