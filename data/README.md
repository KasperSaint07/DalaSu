# US-Ne2 processed data

The processed daily dataset covers 2015--2024 and is split chronologically:

- `daily.csv`: all retained daily records from 2015--2024;
- `train.csv`: 2015--2022, used for model selection and fitting;
- `test.csv`: 2023--2024, held out from training and hyperparameter tuning.

## Source variables

Daily evapotranspiration and meteorological variables are aggregated from the
AmeriFlux US-Ne2 FLUXNET hourly file. Precipitation is sourced separately from
the AmeriFlux BASE hourly column `P_PI_F_1_1_1`. Its values are already amounts
in millimetres for each hourly interval, so `build_daily.py` sums them by day
without multiplying by interval duration.

The former FLUXNET `P_F` source is not used. Measured `P` is unavailable for
2015--2024 in that product, and `P_F` is entirely filled from the unsuitable
`P_ERA` series. As a regression check, `precip_mm` on 2018-06-20 must be
`46.228`, not the former erroneous value `314.689`.

`ws_ms` is the mean FLUXNET `WS_F` wind speed measured at 6.2 m and remains at
that measurement height in these CSV files. A FAO-56 ET0 calculation must
convert it to 2 m at the physical-model stage:

```text
u2 = ws_ms * 4.87 / ln(67.8 * 6.2 - 5.42) ≈ ws_ms * 0.808
```

The ML-only models use the documented `ws_ms` feature directly and do not
perform a FAO-56 wind-height conversion.

## Rebuild

From the repository root, rebuild all three processed files from the downloaded
hourly source files:

```bash
source .venv/bin/activate
python src/ml/data/build_daily.py \
  --fluxnet-input /path/to/US-Ne2_FLUXNET_FLUXMET_HR.csv \
  --precip-input /path/to/US-Ne2_BASE_HR.csv \
  --output-dir data/processed
```

Source CSV files are treated as immutable. Coverage is calculated against a
full 86,400-second day, so physically absent input rows cannot inflate it.
Means and extrema require at least 80% daily coverage. Integrated quantities
(`LE_F_MDS`, `NETRAD`, and hourly precipitation amounts) require complete daily
coverage; this prevents missing intervals from being treated as zero. Duplicate
source intervals are rejected. The builder converts `-9999` to missing values
in memory, orders output by date, and creates the train/test split without
overlap.
