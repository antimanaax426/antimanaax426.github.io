# Agitator Rod Liquid Level

> Fixed-camera liquid-level estimation from how far an agitator shaft is covered by white slurry  
> **Status: PoC — offline evaluation on recorded video from one camera. Not production-deployed.**

化学プラントの混合タンクを上方から撮影した固定カメラ映像から、**撹拌軸（撹拌棒）が白いスラリーにどこまで覆われているか**を求め、液面位置を出力するツールです。

学習済みモデル・GPU・空タンクの基準動画を使わず、**OpenCV と NumPy だけ**で動く単体ツールとして設計しました。
出力は撹拌軸上に設定した ROI の長さに対する百分率（ROI 上端 = 100%、下端 = 0%）で、物理的な高さ（mm・L）ではありません。

## Project status

| Item | Status |
|---|---|
| Development stage | PoC |
| Production deployment | **Not deployed** |
| Data used | 1 camera, 1 day of recorded video (553 clips, about 2.7 min each) |
| Labelled accuracy evaluation | **Not yet performed** (a labelling / evaluation tool exists) |
| Real-time operation | Not evaluated (offline processing of recorded MP4) |

このページの数値は、録画済み映像をオフライン処理した**実際の出力**です。現場での精度・稼働率を示すものではありません。

## Problem

混合工程では液面の推移を記録したいが、タンク内は次の理由で画像認識が難しい環境です。

- スラリーは白く、照明でほぼ白飛びする。液面そのものに模様がない
- 撹拌軸が回転し、波・飛沫で液面付近が常に乱れる
- 投入時の湯気でレンズが曇り、画面全体が白くなる時間帯がある
- 液面と撹拌軸の交線が、カメラの角度のため画面上で斜めに見える

そこで「液面を直接探す」のではなく、**画面上で位置が固定されている撹拌軸を物差しとして使い、露出部と被覆部の境界を探す**方針にしました。

## Method overview

```mermaid
flowchart LR
    F[Frame] --> R[ROI rectification<br/>512 x 96 strip]
    R --> P[Slurry probability<br/>brightness x smoothness]
    P --> S[Tilt shear<br/>calibrated waterline slope]
    S --> K[Optimal split<br/>exposed above / covered below]
    K --> C{conf >= 0.6?}
    C -- yes --> M[10 s rolling median]
    C -- no --> H[hold 10 s]
    M --> OK[status = ok<br/>level %]
    H --> B{Probe region under rod<br/>clear in >= 70% of window?}
    B -- yes --> BR[status = below_rod<br/>level < 0 %]
    B -- no --> NS[status = no_surface]
```

1. **ROI rectification** — 撹拌軸の上端線・下端線（4 点）を透視変換で 512 × 96 の帯に展開（1 行 ≒ 0.2%）。
2. **Slurry probability** — Lab の明度（L 222→236 で 0→1）と局所標準偏差による平滑さから、画素ごとに被覆らしさを計算。
3. **Tilt shear** — 事前校正した水線の傾きで帯をせん断し、各行が実際の水線 1 本に対応するようにする。
4. **Optimal split** — 「上は露出・下は被覆」と最も矛盾の少ない行を求める。経験的しきい値を使わない。信頼度 = 下側被覆率 − 上側被覆率。
5. **Temporal filter** — 信頼度 0.6 以上のフレームだけで 10 秒移動中央値。
6. **below_rod / no_surface** — 撹拌軸上に液面がないとき、軸のすぐ下の領域が白飛びしていなければ「液面は軸より下（空タンクを含む）」、白飛びしていれば「判断不能」とする。

詳細: [Method](docs/method.md)

## Results (one day, offline)

![Liquid level per clip over one day](evidence/day-level-v1.6.2.png)

*V1.6.2 の全日出力（553 クリップ）。濃い線 = クリップごとの中央値、薄い帯 = P10–P90、灰色の点 = 液面出力なし。*

- 液面ありと判定されたクリップ: 184 / 553（09:10〜17:13）。液面の範囲は 9.5〜47.8%
- 液面ありのクリップの有効フレーム率: 中央値 0.91（P10 0.73）
- クリップ内の P90−P10 の幅: 中央値 5.3 ポイント

V1.6.2 では液面が撹拌軸より下にある時間も「出力なし」でした。V1.6.3 で `below_rod` を追加し、空タンク・排出後（撹拌軸が全長露出）と、レンズの曇りを区別できるようにしました。

詳細: [Evidence](docs/evidence.md)

## Technology

- Python 3
- OpenCV / NumPy
- Perspective rectification, Lab colour space, local statistics
- Threshold-free optimal split, rolling median with hold-over

## Selected source code

コアの処理を `rod_level_v16.py` と `geometry.py` から抜粋しています（関数の中身は原文のまま。抜粋だけで動作する）。→ [Code examples](code-examples/)

- [ROI rectification](code-examples/roi_rectification.py)
- [Boundary detection](code-examples/boundary_detection.py) — slurry probability, tilt shear, optimal split
- [Tilt calibration](code-examples/tilt_calibration.py)
- [Temporal filter & below_rod](code-examples/temporal_filter.py)

ツール全体（CLI・注釈動画・一括処理・ラベル付けツール）と、カメラ固有の ROI 設定は公開していません。

## Evidence included

- [Day summary (V1.6.2, 553 clips)](evidence/day-summary-v1.6.2.csv)
- [Per-frame output, level visible (V1.6.2)](evidence/frames-level-v1.6.2.csv)
- [Per-frame output, below_rod case (V1.6.3)](evidence/frames-below-rod-v1.6.3.csv)

映像・画像・カメラ設定は顧客現場のものであるため掲載していません。

## Documents

- [Project summary](PROJECT_SUMMARY.md)
- [Method](docs/method.md)
- [Engineering evolution](docs/engineering-evolution.md)
- [Evidence](docs/evidence.md)
- [Limitations & next steps](docs/limitations.md)

---

**Development period:** 2026  
**Role:** problem framing, computer vision algorithm, calibration procedure, offline evaluation tooling, failure analysis
