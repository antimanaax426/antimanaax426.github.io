# PoC / Development Evidence

## Important scope note

このページのデータは **customer-site deployment の成果ではありません**。開発中の Demo / PoC で Raspberry Pi camera と実物のケーブルを使って取得した試験データです。

## Camera trial

開発環境では Raspberry Pi camera を HTTP Snapshot server として使用し、Windows 側の backend から定期取得しました。

実験中には、短すぎる撮影間隔、protection の追加撮影、UI 側の画像取得が重なることで camera busy / timeout が起きやすくなる問題も確認しました。これが unified acquisition と bounded scheduling の設計を進める理由の一つになりました。

公開版では、実際に使用したホスト名・ネットワーク情報は掲載していません。

## Actual measurement excerpt

[`../evidence/measurements-development-sample.csv`](../evidence/measurements-development-sample.csv) は、2026-09-28 の開発試験データから抜き出した実測 record です。

特徴的なのは、旧版では材料を大きく減らした直後に次のような record が出ている点です。

| State | remaining_ratio | confidence | quality_status |
|---|---:|---:|---|
| baseline / near baseline | 1.0000 | 0.871 | OK |
| small change | 0.9884 | 0.856 | OK |
| large reduction (old design) | blank | 0.486 | LOW_CONFIDENCE |
| protection pending | blank | 0.504 | PENDING_CONFIRMATION |
| later confirmed | 0.2807 | 0.509 | OK |

これは「残量が少ないこと」と「測定品質が低いこと」が結合していた旧設計の問題を示す実データです。

その後の最終版では、この問題を AI-06 として修正し、100 / 80 / 50 / 20% の正常な material change が remaining の大小だけで invalid / low-confidence 化しない regression test を追加しました。

ここで重要なのは、**自動テストで quantity coupling を除去したことは確認しているが、最終版アルゴリズムの長期現場精度を示す実地データはまだ無い**という点です。

## Baseline evidence

[`../evidence/baseline-metrics.json`](../evidence/baseline-metrics.json) は実際の Baseline metadata から、公開に不要な user / host 情報を除いたものです。

この例では、1920×1080 frame 上で ROI area 548,193 px、Baseline material area 81,311 px、occupancy 14.8325% が記録されています。

## Test evidence

Final source archive で `pytest --collect-only` を実行すると **259 tests** が収集されます。付属の final architecture audit は、それらを複数 batch に分けて **259 / 259 PASS** と記録しています。

テスト対象には、通常の vision/API test だけでなく次が含まれます。

- measurement identity / frame provenance
- unified acquisition
- acquisition priority
- atomic baseline registration
- commit-before-publish fault injection
- protection persistence / restart / lifecycle
- database architecture guards
- confidence / validity / semantic separation
- bounded scheduling behavior

この test count は「現場性能 259 件」を意味するものではなく、software regression の件数です。

## Why raw images / logs / DB are not published here

手元の `data/` には実画像、alert image、log、camera configuration、SQLite DB が残っていますが、作品集にはそのまま載せていません。

理由は、画像背景や設定に開発環境を特定できる情報が含まれるためです。作品として必要な evidence は、実 measurement と baseline metrics の匿名化済み抜粋で示しています。
