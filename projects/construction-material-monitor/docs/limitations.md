# Limitations & Next Steps

## Current limitations

### 1. Demo / PoC stage

このシステムはまだ production deployment されておらず、customer site での長期運用実績はありません。現時点で示せるのは、開発環境の camera trial、実データ、software regression の結果です。

### 2. Fixed-camera and ROI assumption

基本設計は固定 camera と手動 ROI に依存します。大きな camera movement、材料置場そのものの変更、ROI 外への移動は再設定または新 Baseline が必要です。

### 3. Relative area, not physical quantity

主指標は image area に基づく relative remaining ratio です。本数、重量、m 数などの物理量へ自動変換する機能は未実装です。

### 4. Detector calibration still needs field data

AUTO_FUSION は color / background difference / alignment / quality guard を組み合わせていますが、環境条件ごとの weight / threshold は実際の施工現場データで継続調整する必要があります。

### 5. Occlusion model is heuristic

一時遮蔽を protection と ROI background change で吸収しますが、人・工具・車両などを semantic class として認識しているわけではありません。

### 6. Optional YOLO path is not the primary mode

YOLO segmentation compatibility は残していますが、現在の新規 ROI の主経路は AUTO_FUSION です。YOLO は複雑な対象に対する将来オプションとして位置付けています。

## Next validation steps

実用化へ進める場合、優先順位は機能追加より field validation です。

1. 実施工環境で複数日〜複数週の固定 camera データを取得
2. 昼夜・照明変動・人の遮蔽・材料補充・カメラ微振動を含む ground truth を作成
3. material / scene ごとの error distribution を評価
4. false alert / missed change / recovery time を計測
5. camera/network failure の長時間 soak test
6. Windows 常時稼働方式と backup/restore の実機試験
7. その結果を基に threshold と運用手順を固定

現段階では「完成済み製品」として見せるより、**PoC から engineering constraints を発見し、architecture guardrails まで設計したプロジェクト**として位置付けています。
