# Evidence

## Important scope note

このページの数値は、**1 台のカメラ・1 日分（2026-10）の録画映像をオフライン処理した実際の出力**です。
ラベル付きの正解との誤差評価はまだ行っていないため、**精度（mm や % の誤差）は示していません**。

映像は顧客現場のものなので、画像・動画は掲載していません。CSV のクリップ名は通し番号に置き換えています。

## 1. One day of clips (V1.6.2)

[`../evidence/day-summary-v1.6.2.csv`](../evidence/day-summary-v1.6.2.csv) — 553 クリップ（1 本約 2.7 分）の集計です。

![Liquid level per clip](../evidence/day-level-v1.6.2.png)

| Item | Value |
|---|---|
| Clips | 553 |
| Clips with a level | 184（09:10〜17:13） |
| Level range (clip median) | 9.5〜47.8% |
| Valid-frame ratio of clips with a level | median 0.91 / P10 0.73 / min 0.21 |
| P90 − P10 within a clip | median 5.3 / P90 9.5 points |

有効フレーム率が 0.75 未満のクリップは 29 本で、そのうち 27 本は液面が低い 09:10〜10:22（液面 約 9〜26%）に集まっています。残りは 13:17 と、排出中の 17:13 です。液面が下端に近いと被覆部が短く、信頼度が 0.6 に届きにくいためと考えています（未検証）。

## 2. Per-frame examples

| Clip (time) | Version | Frames | Output |
|---|---|---|---|
| 11:42 | V1.6.2 | 668 | `ok` 654 frames, level 43.8〜46.9%, median IQR 2.4 points |
| 10:14 | V1.6.2 | 668 | `ok` 653 frames, level 24.5〜25.6%, median IQR 1.0 point |
| 09:08 | V1.6.3 | 668 | `no_surface` 0〜53 s (lens fog, probe L ≈ 241) → `below_rod` 53〜160 s (probe L ≈ 225) |
| 19:24, 23:16 | V1.6.2 | 668 each | すべて `no_surface`（V1.6.2 には `below_rod` がない） |

- [`../evidence/frames-level-v1.6.2.csv`](../evidence/frames-level-v1.6.2.csv) — 11:42 のクリップ。先頭の約 14 フレームは、10 秒窓に有効フレームがたまるまでの立ち上がり
- [`../evidence/frames-below-rod-v1.6.3.csv`](../evidence/frames-below-rod-v1.6.3.csv) — 09:08 のクリップ。`probe_l` 列で曇りから晴れへの変化が分かる

## 3. below_rod check (V1.6.3)

`below_rod` を追加したときに、時間帯の異なる代表 23 クリップで出力を確認しました。

| Time | Scene | V1.6.2 | V1.6.3 |
|---|---|---|---|
| 00:13〜08:51 | 空タンク | 出力なし | `below_rod` |
| 08:53〜09:08 | 投入時のレンズ曇り | 出力なし | `no_surface` |
| 09:09〜09:12 | タンク底にスラリー、軸には未到達 | 出力なし | `below_rod`（曇りが晴れた後） |
| 09:12〜17:13 | 液面あり | 液面 | 液面（クリップの中央値は V1.6.2 と一致） |
| 17:16 以降 | 排出後、軸が全長露出 | 出力なし | `below_rod` |

この確認は目視による状況判定との突き合わせで、件数ベースの評価ではありません。

## 4. What is not shown

- ラベル付きの誤差（MAE など）— 評価ツールはあるが未実施
- 複数カメラ・複数日での再現性
- リアルタイム処理での性能
