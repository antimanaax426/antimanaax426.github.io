# Project Summary — Agitator Rod Liquid Level

## One-line summary

混合タンクの固定カメラ映像から、撹拌軸がスラリーに覆われている位置を求めて液面を ROI 長の % で出力する、**学習不要・OpenCV のみの PoC ツール**。

## Status

**PoC. Offline evaluation on one camera / one day of recorded video. Not production-deployed.**  
ラベル付きの誤差評価はまだ行っていません。

## My scope

- 問題設定（液面を直接探さず、固定された撹拌軸を物差しにする）
- ROI 正規化と透視変換
- スラリー確率（明度 × 平滑さ）の設計
- しきい値を使わない最適分割による境界検出と信頼度
- 水線の傾きの自動校正
- 時系列フィルタ（移動中央値・保持）
- 「液面が撹拌軸より下」と「見えない（曇り）」の判別
- 注釈動画・CSV・日次グラフの出力、ラベル付けと評価のツール
- 1 日分の映像を使った失敗例の分析

## Tech stack

`Python` · `OpenCV` · `NumPy`

## Core design decisions

1. **Use the fixed shaft as the ruler** — 模様のない液面ではなく、位置が固定された撹拌軸の露出／被覆の境界を探す。
2. **No reference video** — 空タンクの基準映像との比較（旧版）をやめ、各フレーム単独で判定する。
3. **Threshold-free split** — 境界は「上は露出・下は被覆」と最も矛盾の少ない行。信頼度も同じ式から出す。
4. **Calibrated tilt** — 水平な液面と軸の交線が斜めに見える分を、校正した傾きでせん断補正する。
5. **Explicit "cannot tell" state** — 判断できないときは値を出さず、`below_rod` と `no_surface` を区別して返す。

## What was learned

- 最初の方式（空タンクの映像との構造比較）は「軸が見えているか」しか分からず、液面の位置は求められなかった。目的に合った特徴（白さと平滑さ）に切り替えて初めて液面が出た。
- 1 日分の映像を時間帯ごとに見直すと、「出力なし」には **空タンク・排出後**、**レンズの曇り**、**軸に届く前の灰色のスラリー** の 3 種類が混ざっていた。前の 2 つは軸の下の領域の明るさで分けられたが、3 つ目は空タンクの底と明るさが同じで、単一フレームでは区別できないと判断した。

## Verification status

- 1 日分 553 クリップをオフライン処理（V1.6.2）。184 クリップで液面を出力
- `below_rod` は V1.6.3 で追加。代表クリップで、空タンク・曇り・排出後が想定どおりに分かれることを確認
- ラベル付きの誤差評価: **not yet performed**
