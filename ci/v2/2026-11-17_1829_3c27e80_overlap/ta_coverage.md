# Technical coverage overlap check (development data only, before 2024-10-30)

Descriptive overlap, no forward returns. Within-asset = pooled Spearman of each asset's own ranks; cross-sectional = Spearman across assets on the same day, averaged over days.

## stock (61 assets, 106872 asset-days)

Median share of zero-volume days: 0.0%

### Key pairs (within-asset)

| Pair | Spearman |
|---|---|
| OBV vs OBV without volume (within-asset) | 0.93 |
| Flow vs Stretch | 0.78 |
| OBV part vs 7-day move part | 0.68 |
| Heavy-volume part vs Stretch | 0.21 |
| CMF vs Flow | 0.46 |
| CMF vs Stretch | 0.45 |
| BB width rank vs ATR% rank | 0.52 |
| Realised vol vs ATR% | 0.85 |
| RS 63d vs Trend | 0.64 |
| Distance from 1-year high vs Trend | 0.75 |
| 55-day range position vs Stretch | 0.69 |
| Traded value vs ATR% | 0.40 |

### Cross-sectional (same day, across assets)

| Pair | Spearman |
|---|---|
| rs_63 vs trend | 0.77 |
| rs_126 vs trend | 0.61 |
| rs_21 vs stretch | 0.69 |
| dist_high_252 vs trend | 0.70 |
| range_pos_55 vs stretch | 0.66 |
| traded_value_20 vs atr_pct | 0.28 |
| amihud_20 vs atr_pct | 0.08 |
| bb_width vs atr_pct | 0.64 |
| cmf_20 vs flow | 0.44 |
| flow vs stretch | 0.72 |

### Every candidate against Trend, Stretch, Flow and ATR% (within-asset)

| | trend | stretch | flow | atr_pct |
| --- | --- | --- | --- | --- |
| trend | 1.00 | 0.59 | 0.57 | -0.40 |
| stretch | 0.59 | 1.00 | 0.78 | -0.22 |
| flow | 0.57 | 0.78 | 1.00 | -0.23 |
| obv_comp | 0.60 | 0.79 | 0.97 | -0.24 |
| heavy_comp | 0.09 | 0.21 | 0.38 | -0.04 |
| momentum_comp | 0.45 | 0.91 | 0.68 | -0.17 |
| obv_vs_avg | 0.60 | 0.79 | 0.97 | -0.24 |
| obv_no_volume | 0.54 | 0.73 | 0.90 | -0.23 |
| cmf_20 | 0.55 | 0.45 | 0.46 | -0.20 |
| rs_21 | 0.67 | 0.57 | 0.52 | -0.09 |
| rs_63 | 0.64 | 0.28 | 0.29 | -0.07 |
| rs_126 | 0.50 | 0.20 | 0.21 | -0.05 |
| dist_high_252 | 0.75 | 0.43 | 0.42 | -0.54 |
| dist_low_252 | 0.56 | 0.27 | 0.26 | -0.08 |
| range_pos_55 | 0.92 | 0.69 | 0.64 | -0.37 |
| atr_pct | -0.40 | -0.22 | -0.23 | 1.00 |
| atr_pct_rank_252 | -0.39 | -0.23 | -0.23 | 0.67 |
| bb_width | -0.08 | 0.07 | 0.04 | 0.56 |
| bb_width_rank_252 | -0.07 | 0.08 | 0.05 | 0.38 |
| realised_vol_20 | -0.28 | -0.08 | -0.11 | 0.85 |
| traded_value_20 | -0.09 | -0.06 | -0.08 | 0.40 |
| amihud_20 | -0.20 | 0.00 | -0.02 | 0.44 |
| volume_cv_20 | 0.01 | -0.03 | -0.03 | 0.06 |
| adx | 0.22 | 0.06 | 0.08 | -0.02 |

## crypto (25 assets, 53599 asset-days)

Median share of zero-volume days: 0.0%

### Key pairs (within-asset)

| Pair | Spearman |
|---|---|
| OBV vs OBV without volume (within-asset) | 0.94 |
| Flow vs Stretch | 0.73 |
| OBV part vs 7-day move part | 0.65 |
| Heavy-volume part vs Stretch | 0.24 |
| CMF vs Flow | 0.55 |
| CMF vs Stretch | 0.55 |
| BB width rank vs ATR% rank | 0.65 |
| Realised vol vs ATR% | 0.87 |
| RS 63d vs Trend | 0.40 |
| Distance from 1-year high vs Trend | 0.65 |
| 55-day range position vs Stretch | 0.64 |
| Traded value vs ATR% | 0.41 |

### Cross-sectional (same day, across assets)

| Pair | Spearman |
|---|---|
| rs_63 vs trend | 0.72 |
| rs_126 vs trend | 0.56 |
| rs_21 vs stretch | 0.63 |
| dist_high_252 vs trend | 0.58 |
| range_pos_55 vs stretch | 0.58 |
| traded_value_20 vs atr_pct | -0.24 |
| amihud_20 vs atr_pct | 0.29 |
| bb_width vs atr_pct | 0.62 |
| cmf_20 vs flow | 0.39 |
| flow vs stretch | 0.53 |

### Every candidate against Trend, Stretch, Flow and ATR% (within-asset)

| | trend | stretch | flow | atr_pct |
| --- | --- | --- | --- | --- |
| trend | 1.00 | 0.57 | 0.50 | -0.07 |
| stretch | 0.57 | 1.00 | 0.73 | -0.20 |
| flow | 0.50 | 0.73 | 1.00 | -0.14 |
| obv_comp | 0.53 | 0.75 | 0.98 | -0.14 |
| heavy_comp | 0.11 | 0.24 | 0.46 | -0.07 |
| momentum_comp | 0.44 | 0.90 | 0.65 | -0.16 |
| obv_vs_avg | 0.53 | 0.75 | 0.98 | -0.14 |
| obv_no_volume | 0.47 | 0.71 | 0.90 | -0.16 |
| cmf_20 | 0.58 | 0.55 | 0.55 | -0.08 |
| rs_21 | 0.50 | 0.41 | 0.36 | -0.04 |
| rs_63 | 0.40 | 0.17 | 0.16 | 0.08 |
| rs_126 | 0.34 | 0.14 | 0.15 | 0.15 |
| dist_high_252 | 0.65 | 0.29 | 0.26 | -0.14 |
| dist_low_252 | 0.58 | 0.27 | 0.27 | 0.38 |
| range_pos_55 | 0.92 | 0.64 | 0.57 | -0.15 |
| atr_pct | -0.07 | -0.20 | -0.14 | 1.00 |
| atr_pct_rank_252 | 0.04 | -0.21 | -0.16 | 0.68 |
| bb_width | 0.11 | 0.04 | 0.05 | 0.71 |
| bb_width_rank_252 | 0.16 | 0.05 | 0.05 | 0.43 |
| realised_vol_20 | 0.10 | -0.01 | 0.03 | 0.87 |
| traded_value_20 | 0.20 | -0.01 | 0.01 | 0.41 |
| amihud_20 | -0.19 | 0.02 | 0.01 | -0.20 |
| volume_cv_20 | 0.20 | 0.10 | 0.09 | 0.21 |
| adx | 0.05 | 0.06 | 0.04 | 0.24 |

