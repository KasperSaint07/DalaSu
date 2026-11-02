# US-Ne2 crop-stage evidence and NDVI proxy labels

## Decision and status (2026-11-02)

No verifiable, year-specific planting, harvest or field-observed phenological
intervals for 2023–2024 were retrieved in this audit. The local repository has
meteorological/ET series and Landsat NDVI but no BIF or field phenology records.
**Actual stages, including actual off-season, remain unknown.** A usable NDVI
proxy does not close the evidence gap or complete analysis by actual crop stage.
This is an access/evidence limitation, not a claim that such records do not exist.

The official AmeriFlux site description reports an alternating rotation after
2014. The annual context table therefore marks 2023 maize and 2024 soybean as
`inferred_rotation`, not as observations confirmed for those individual years.
The crop field means the year's expected crop, not evidence of standing plants
on that date, especially in winter. Planting/harvest dates are explicitly unknown.

## Evidence audit

Machine-readable sources and access outcomes are in
`data/metadata/phenology/sources.json`; crop context is in `crop_context.csv`.

| Source | Evidence and use | Limitation |
|---|---|---|
| [AmeriFlux US-Ne2 DOI page](https://ameriflux.lbl.gov/doi/FLUXNET/US-Ne2/) | Site rotation description; inference of annual crop context | Indexed official text retrieved; direct page returned 403. No 2023/2024 stage dates obtained |
| [BADM product](https://ameriflux.lbl.gov/data/aboutdata/badm-data-product/) | Explains ancillary records and BIF distribution | Documentation does not establish site-year availability; download endpoint returned 403 |
| [BADM planting standard](https://ameriflux.lbl.gov/data/badm/badm-standards/DM_PLANTING) | Defines date and date-uncertainty fields | Schema only; not a measured event |
| [UNL CSP](http://csp.unl.edu/Public/sites.htm) | Potential site management archive | Not accessible through retrieval in this audit |
| [Zhang et al., 2023](https://doi.org/10.1029/2022WR032967) | Reports historical management records for Mead | Period 2001–2012 does not establish 2023/2024 dates |
| [Ground spectra primary dataset article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10883924/) | Older crop-season observations | Dataset covers 2016–2021; dates are not transferred to test years |
| DAL-29/30 local export | Site NDVI observations, quality flags and acquisition provenance | Vegetation signal, not an agronomic stage observation |

Searches targeted US-Ne2, both test years, planting, harvest and phenology. No
messages were sent to site investigators. Next evidence to obtain: site-specific
BADM BIF and field management/phenology records for 2023 and 2024. Preserve the
original file/version and exact record locator when those become available.
Regional crop calendars, older experiments and rotation parity cannot establish
daily planting/harvest or reproductive-stage dates for this field.

## Fixed exploratory proxy policy

`data/metadata/phenology/policy.json` defines version v1. The rule is fixed here
before any stage-specific error comparison. Earlier overall and calendar-season
ET results were already available; this is **not** prospective preregistration.
No ET values, model forecasts, residuals or stage-error scores enter the rule.
No threshold is optimized against test performance.

1. Load usable DAL-29 observations with the DAL-30 adapter. Use fixed UTC−6
   station standard time. Select one scene per local date using coverage, later
   acquisition and image ID, exactly as DAL-30; ignore other sites.
2. Calculate the 25th and 75th NDVI percentiles (NumPy linear quantiles) from
   **unique selected usable dates in 2015–2022 only**. Do not weight repeated
   carried-forward daily values. Reject insufficient or degenerate training data.
3. On each date select only the latest snapshot on or before that date. No
   interpolation, future peak search or future-scene smoothing is used.
4. Reject a snapshot older than 32 days. This declared freshness limit and the
   32-day trend-gap limit are exploratory constants, not validated crop timings.
5. Apply the following mutually exclusive rules in order:

| Condition | Proxy stage | Meaning |
|---|---|---|
| No previous usable snapshot, or snapshot age >32 days | `unknown` | Missing/stale evidence |
| NDVI ≤ training 25th percentile | `proxy_low_vegetation` | Low greenness; candidate non-growing condition, **not confirmed off-season** |
| NDVI ≥ training 75th percentile | `proxy_high_vegetation` | High greenness, **not flowering or peak reproductive stage** |
| Middle range, previous distinct snapshot ≤32 days earlier, NDVI increase >0.05 | `proxy_greenup` | Increasing greenness |
| Middle range, same gap condition, NDVI decrease <−0.05 | `proxy_decline` | Decreasing greenness, **not confirmed maturity or harvest** |
| Other middle-range conditions | `unknown` | Ambiguous change or insufficient recent trend evidence |

The 0.05 change threshold is an explicitly declared noise deadband, not a
published agronomic cutoff. Trend is the difference between two distinct
selected snapshots, not between two repeated daily forward-held values.
Snapshots no later than the labelled day are permitted, including a 2022 scene
carried into early 2023. An acquisition available later within the same day is
allowed for retrospective daily labels; this does not guarantee dawn availability.

NDVI saturation, clouds, mixed pixels in the 100 m buffer, irregular sampling,
weeds/residue and crop differences limit interpretation. Do not infer growth
stage or crop coefficients directly from these labels. Proxy groups are also
related to the NDVI predictors used by the hybrid, so future grouped error
comparisons are descriptive and do not independently validate phenology.

## Observed evidence and precedence

`observed_intervals.csv` is intentionally header-only. It is an input contract,
not fabricated evidence. Each future row needs:

- `start_date,end_date`: inclusive, day-precision, within the label window;
- `crop,stage`: documented crop and one of `emergence`, `vegetative`,
  `reproductive`, `maturation`, `off_season`;
- `source_id`: registered source with kind `field_record`;
- `evidence_locator`: exact file/version and record, table or page reference;
- `status`: `observed`.

A planting or harvest event alone does not establish all intervening stages.
Do not expand point measurements into unsupported intervals. Dates with only
month/year precision or uncertain boundaries must remain unknown until a
conservative day-level interval can be supported. Off-season needs evidence
of absence of the crop, not just a low NDVI or an assumed calendar month.

The validator rejects overlaps, including shared inclusive endpoints, reversed
ranges, unknown sources and unsupported stage/status combinations. It validates
structure and provenance presence, **not the truth of the source**; source records
still need human review. Observed intervals override final stage/crop, while
independent NDVI proxy fields remain visible. Actual and proxy labels never
share an unqualified stage name.

## Reproduction and outputs

```bash
PYTHONPATH=src python -m ml.data.build_phenology
```

No network, model inference or training is required. Optional CLI paths support
isolated rebuilds. Outputs in `data/processed/phenology/`:

- `daily_labels.csv`: every calendar day in 2023–2024 (731 rows).
- `test_labels.csv`: one row for each of the 561 canonical test dates.
- `label_intervals.csv`: contiguous non-overlapping calendar intervals,
  including unknown runs. Missing ET dates are not mistaken for phase changes.
- `fitted_policy.json`: fixed policy, derived training-only thresholds,
  training-date limits and hash of selected training snapshots.
- `coverage.json`: coverage by year/status/stage/reason, input and code hashes.
- `coverage.md`: readable counts and readiness limitation.

Main label columns: date, crop, crop_status/source, stage, source, status,
actual_stage/source, evidence_locator, proxy_stage/reason, scene dates/IDs,
NDVI value/age/change and policy_version. `status` is observed, approximate or
unknown. **For actual-stage evaluation, filter status=observed; never silently
substitute proxy groups.** Current actual-stage coverage is zero.

The output is deterministic for unchanged inputs and environment. Changes to
policy or evidence require a new documented version before comparing grouped
errors; never select the best-looking rule after viewing holdout results.
