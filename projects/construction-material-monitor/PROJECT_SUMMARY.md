# Project Summary — Construction Material Monitor

## One-line summary

固定カメラ画像から施工材料の残量比率を定期計測し、急変時の再確認・履歴保存・アラートまで行う **Demo / PoC 段階の監視システム**。

## Status

**Not production-deployed. Not customer-site operated.**  
現在は機能検証・アーキテクチャ検証を行っているプロトタイプです。

## My scope

- システム構成設計
- Camera acquisition 設計
- OpenCV による ROI / alignment / image quality / detection
- 残量算出と confidence 設計
- Change Protection 状態機械
- SQLite schema / transaction / provenance
- Scheduler / concurrency
- FastAPI backend
- Web UI 連携
- Raspberry Pi HTTP Snapshot camera の PoC
- Regression test / architecture audit

## Tech stack

`Python` · `FastAPI` · `OpenCV` · `NumPy` · `SQLite` · `JavaScript` · `Raspberry Pi` · `pytest`

## Core design decisions

1. **Single Acquisition Boundary** — 物理カメラ I/O を一箇所に限定。
2. **Atomic Measurement Identity** — remaining / confidence / validity / timestamps を同一 measurement に固定。
3. **Frame Provenance** — どの frame が正式値の根拠か追跡可能にする。
4. **Commit Before Publish** — DB commit 成功後のみ UI / alert に公開。
5. **Non-blocking Protection** — 急変確認を sleep ではなく durable state + scheduler で実行。
6. **Bounded Scheduling** — worker / queue 上限と no catch-up burst。
7. **Remaining / Confidence Orthogonality** — 材料が減っただけで confidence が下がらない設計。
8. **Atomic Baseline Registration** — filesystem / measurement / DB の半登録を防止。

## What was learned from the demo

PoC では「認識アルゴリズムを作れば終わり」ではなく、カメラ要求の競合、UI refresh、ネットワーク不安定、長時間 protection、DB 一貫性、再起動復旧などがシステム品質を左右することが分かりました。

そのため後半は機能追加よりも Architecture Invariants を明文化し、違反状態を DB constraint / trigger と regression test でも拒否する方向に設計を変えています。

## Verification status

- Final source archive: **259 tests collected**
- Final architecture audit document: **259 / 259 PASS**
- Development camera trial: Raspberry Pi + HTTP Snapshot
- Real long-term customer-site validation: **not yet performed**

## Portfolio evidence

公開データは開発中に取得した実データの抜粋です。数字を良く見せるための合成成果は作っていません。

- `evidence/measurements-development-sample.csv`
- `evidence/baseline-metrics.json`

初期データには、残量低下時に confidence が落ちる旧設計の問題もそのまま残しています。これは後の AI-06 リファクタにつながった実際の開発記録として掲載しています。
