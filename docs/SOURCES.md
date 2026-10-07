# 公式資料と設計判断

確認日：2026年10月7日（日本時間）。公式資料は更新されるため、導入時とバージョン更新時に再確認する。以下の要約は公式の事実、採用欄はこのキットの設計判断である。改善効果の実測値はない。

| ID | 一次資料 | 確認した要点 | 採用・影響 |
| --- | --- | --- | --- |
| S01 | [Claude Codeのベストプラクティス](https://code.claude.com/docs/en/best-practices) | 調査・計画・実装を分け、結果を検証できる手段を用意する | 小さな変更では工程を軽くし、大きな変更では検証条件を先に整理 |
| S02 | [プロジェクトの記憶](https://code.claude.com/docs/en/memory) | CLAUDE.md、rules、メモリ、AGENTS.md対応と読み込み条件 | 短いCLAUDE.mdを入口にし、詳細は必要時参照 |
| S03 | [権限](https://code.claude.com/docs/en/permissions) | Manual、Plan、auto、bypassなどのモードと権限ルール | 明示的なモード選択。AIの判定を人の承認と同一視しない |
| S04 | [フック](https://code.claude.com/docs/en/hooks) | PreToolUse等の入出力、停止判定、失敗・タイムアウト時の挙動 | フック単独を安全境界にしない。異常系を試験 |
| S05 | [スキル](https://code.claude.com/docs/en/skills) | 必要時読み込み、手動呼び出し、allowed-toolsの意味 | 実装系は手動呼び出し。権限を増やすfrontmatterを置かない |
| S06 | [モデル設定](https://code.claude.com/docs/en/model-config) | モデル名・別名・利用条件・effort設定 | 実際のモデルと推論設定を記録。最大設定を常用しない |
| S07 | [設定ファイルと優先順位](https://code.claude.com/docs/en/settings) | 管理・ユーザー・プロジェクト等の設定と状態確認 | 既存設定に統合し、実際に読み込まれた設定を確認 |
| S08 | [Bashのサンドボックス](https://code.claude.com/docs/en/sandboxing) | シェルの隔離と、その外で動くツール・プロセス | OS隔離と権限ルールを組み合わせる |
| S09 | [Claude Codeのセキュリティ](https://code.claude.com/docs/en/security) | 外部入力の攻撃と利用者によるレビュー | 取得データを権限の根拠にしない |
| S10 | [費用と文脈の管理](https://code.claude.com/docs/en/costs) | 使用量・キャッシュの確認と文脈管理 | 読む量と再読を減らし、取得できる使用量だけ記録 |
| S11 | [プロンプトの構成](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | XMLで指示・資料・入力を区切る方法 | 必要時だけXML。制約強制や安全保証とは扱わない |
| S12 | [プロンプトキャッシュ](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | APIへの共通プロンプトの再利用 | `.claude_cache`の作成では代替できない |
| S13 | [Claude CodeとVS Code](https://code.claude.com/docs/en/vs-code) | 拡張とCLIの利用・会話の継続 | VS Codeを維持し、拡張・CLIの版と設定を別々に確認 |
| S14 | [VS Codeのセッション管理](https://code.visualstudio.com/docs/agents/run/sessions/manage-sessions) | Chat: Export Chat...でJSON保存、Copy AllでMarkdownコピー | Copilotログは人が選んで取り出す |
| S15 | [MITライセンス原文](https://opensource.org/license/mit) | 標準のライセンス本文 | LICENSEは原文を保持。公開前に権利者・対象範囲を確認 |
| S16 | [設定キーのリファレンス](https://code.claude.com/docs/en/settings-reference.md) | 権限・サンドボックスのキー、型、配置先 | JSON例のキーを照合。実効動作は未検証 |

## バージョン依存として扱う事項

- 確認時のモデル資料にはSonnet 5.5、Opus 5.5、Fable 5.1などが掲載されている。対象アカウントで使えるかは未確認。S06。
- Sonnet 5.5はClaude Code v2.1.284以降、Opus 5.5はv2.1.280以降が要件として記載されている。S06。
- AGENTS.mdの直接読み込みにはバージョン・設定・CLAUDE.mdの有無による条件がある。本キットは`CLAUDE.md`を明示的な入口にする。S02。
- 標準の開始モードも版・プランで変わる。導入時に`/permissions`と画面のモードを確認する。S03。
- フックは起動失敗・一般的なエラー・タイムアウトで、常に処理を遮断するわけではない。SDKコールバックとコマンドフックを混同しない。S04。
- スキルの`allowed-tools`は事前許可であり、列挙外のツールを除去する設定ではない。S05。

## 更新方針

公式資料の変更から採用を自動決定しない。変更した公式項目、影響するファイル、互換性、確認した実行結果をPRに記載する。公式の説明、キットの提案、現場での実測を同じ根拠として扱わない。公式資料全文の複製・翻訳は保存しない。
