# Tableau dashboard build specification

Status: designed and supplied with computed data; not yet implemented or tested in Tableau. Suggested dashboard name: **Smoking Trends & Disparities | CDC BRFSS, 2019–2023**.

## Layout — one executive dashboard, 1280 × 900

```
Title, selected year/state and scope note
Year parameter | Selected state parameter | Demographic category parameter
States/DC median | Selected state prevalence | State YoY (pp) | Coverage
US state map, overall prevalence     | Top 10 reporting states/DC + CIs
Selected-state annual trend          | Selected-state demographic comparison + CIs
Review table: five-year elevation and evidence | Source / missingness notes
```

Use navy titles, teal marks, orange only for selected state or above-median emphasis, gray for missing data. Always show units and source. The supplied Python visual summary demonstrates the data/story; it is not a screenshot of Tableau and does not implement this map/interaction layout.

## Data connections and model

1. Text file `coverage.csv` as the primary logical table. **Left physical join** `state_overall.csv` on both `year` and `state_code`, one-to-one. Retain all 255 rows. Use coverage's year, state code and state name as primary dimensions. Duplicate join field names will be renamed by Tableau; label them explicitly.
2. Left join `persistent_elevation.csv` on state code (many-to-one), adding five-year availability and elevation pattern to the main source. This flag always describes the full fixed 2019–2023 period, regardless of selected year.
3. Connect `demographics.csv` as a **separate data source**, not a physical join to overall. It is one row per state/year/category/segment. The file already includes overall and reference metrics.
4. `demographic_ranges.csv` and `benchmark.csv` are optional audit connections. They are not required joins.

Do not physically join demographics to overall: it would multiply overall records. Do not use a sum of prevalence. Set all rates, CIs, pp changes and ratios to `MIN` for one selected grain. Parameters work across the two independent sources.

## Parameters
- `pYear`: integer list 2019, 2020, 2021, 2022, 2023; initial 2023.
- `pState`: string list of 51 two-letter codes from `coverage.csv`; initial WV.
- `pCategory`: string list Sex, Age Group, Education Attained, Household Income, Race/Ethnicity; initial Education Attained.

Create the following calculations separately in each source that uses them:
```tableau
// Selected year (filter True for current-year views)
[year] = [pYear]
// Selected state (filter True for selected-state views)
[state_code] = [pState]
// Selected category (demographics source only; filter True)
[category] = [pCategory]
// Rate as fraction for Tableau's native percentage formatting
[prevalence_pct] / 100.0
```
Keep SQL pp fields in their original numeric scale and format with custom suffix ` pp`; e.g. −0.6 pp, not −60%. Ratios use `0.00` with × in the label. Set Year to a discrete whole-number dimension, not a summed measure. Geographic role of state name: State/Province; country context United States.

## Worksheets
| Sheet | Source and filters | Encoding / aggregation |
|---|---|---|
| Benchmark KPI | Main; selected year only | `MIN(states_dc_median_pct)/100`, percent format; label “CDC states/DC median” |
| State KPI | Main; selected year + state | `MIN(prevalence_pct)/100`; show unavailable when null; CI in tooltip |
| YoY KPI | Main; selected year + state | `MIN(yoy_change_pp)`; keep null for missing prior calendar year |
| Coverage KPI | Main; selected year only | `SUM(IIF([coverage_status]='Available',1,0))` out of `COUNTD(state_code)` |
| State map | Main; selected year only | State geographic role; color `MIN(prevalence_pct)`; gray/null missing states; state code on Detail |
| Top reporting states/DC | Main; selected year; available only; rank ≤10 | Rows state, Columns prevalence/100; descending; CI Gantt or reference intervals; `RANK` ties may produce >10 marks |
| Selected-state trend | Main; selected state only, **no selected-year filter** | Continuous year 2019–2023; prevalence/100 and median/100 lines; retain null gaps, do not bridge missing years |
| Demographic comparison | Demographics; selected year + state + category | Rows segment; Columns prevalence/100; CIs; overall as reference line from `MIN(state_overall_pct)/100` |
| Sustained elevation review | Main; selected year; five-year pattern='Above median in all 5 years' | State name, latest rate, median gap, YoY, years available; sort rate descending |

Benchmark KPI: for a missing selected state-year, use the all-state year-only sheet so the benchmark remains visible. Map tooltip on a missing state should explicitly say “No source estimate,” not zero.

For CI bars, create fraction fields `ci_low/100` and `(ci_high-ci_low)/100`; use low as Gantt start and width as Size on an overlaid axis with prevalence circles. Hide unavailable intervals, retaining unavailable labels in a companion table. Use source bounds directly, without inventing uncertainty for differences.

Tooltips: year, state, subgroup where applicable, prevalence, source 95% CI, median comparison label, YoY pp, availability and source note. No “statistically significant” labels.

## Interactions
Use a **Change Parameter** dashboard action from map and state ranking, writing selected `state_code` to `pState`. Run on Select; clearing selection keeps current value. The state parameter updates both the trend and demographics source. Keep year as an explicit parameter control so it does not accidentally filter the full trend. No demographic filter should affect overall KPI rates or state ranks. State rank is the SQL rank across all available reporting states/DC in that year, not recalculated after selecting one state.

Income selections show a fixed note: “Income categories changed in 2021; compare within year.” Category selections do not imply joint demographic segments. Show source confidence bounds and missingness rather than using low sample size as an invented quality score.

## Presentation acceptance checks in Tableau
- 2023 coverage is 49/51; KY/PA are missing. WV selected rate is 20.4%, median 12.1%, YoY −0.6 pp.
- WV education: less than HS 42.4%, college graduate 8.7%; reference gap 33.7 pp, ratio 4.87× in tooltip or supporting table.
- Selecting FL 2022 gives null YoY because 2021 is absent. Selecting NJ 2020 also gives null YoY.
- Switching state or category does not change the year-only benchmark or coverage card.
- The trend keeps all five years even when pYear=2023; missing values create gaps.
- Each main state-year remains unique after joins. No totals sum prevalence or count demographic rows as people.
- Nulls stay visually distinct from 0%; map geography resolves all 50 states and DC.
- Save `.twbx` with CSVs packaged; reopen on a machine without original absolute paths and confirm all sheets load. Only then claim a completed Tableau dashboard or publish it.
