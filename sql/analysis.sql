-- SQLite 3.25+; values are percentage points on a 0-100 scale.
-- raw_estimates is loaded from the preserved CDC JSON by run_analysis.py.
CREATE VIEW clean_estimates AS
SELECT CAST(year AS INTEGER) AS year, locationabbr AS state_code,
 locationdesc AS state_name, break_out_category AS category,
 break_out AS segment, breakoutcategoryid AS category_id, breakoutid AS segment_id,
 CAST(NULLIF(data_value,'') AS REAL) AS prevalence_pct,
 CAST(NULLIF(confidence_limit_low,'') AS REAL) AS ci_low,
 CAST(NULLIF(confidence_limit_high,'') AS REAL) AS ci_high,
 CAST(NULLIF(sample_size,'') AS INTEGER) AS source_sample_size,
 data_value_footnote AS source_note,
 CASE WHEN NULLIF(data_value,'') IS NULL THEN 'Unavailable'
      WHEN NULLIF(confidence_limit_low,'') IS NULL THEN 'Estimate without CI'
      ELSE 'Available' END AS availability
FROM raw_estimates
WHERE questionid='_RFSMOK3' AND responseid='RESP046'
 AND data_value_type='Crude Prevalence' AND data_value_unit='%';

-- The UW record is a median, NOT a population-weighted national estimate.
CREATE VIEW benchmark AS
SELECT year, prevalence_pct AS states_dc_median_pct
FROM clean_estimates WHERE state_code='UW' AND category='Overall';

CREATE VIEW state_overall AS
WITH lagged AS (
 SELECT c.*, LAG(c.year) OVER w AS previous_year,
 LAG(c.prevalence_pct) OVER w AS previous_prevalence_pct
 FROM clean_estimates c JOIN dim_state s USING(state_code)
 WHERE category='Overall'
 WINDOW w AS (PARTITION BY state_code ORDER BY year)
), ranked AS (
 SELECT year,state_code,
 RANK() OVER (PARTITION BY year ORDER BY prevalence_pct DESC) AS prevalence_rank
 FROM lagged WHERE prevalence_pct IS NOT NULL
)
SELECT l.*, b.states_dc_median_pct,
 l.prevalence_pct-b.states_dc_median_pct AS gap_vs_median_pp,
 CASE WHEN previous_year= l.year-1 THEN l.prevalence_pct-previous_prevalence_pct END AS yoy_change_pp,
 CASE WHEN previous_year=l.year-1 AND previous_prevalence_pct>0
 THEN 100.0*(l.prevalence_pct-previous_prevalence_pct)/previous_prevalence_pct END AS yoy_relative_change_pct,
 r.prevalence_rank,
 base.prevalence_pct AS baseline_2019_pct,
 l.prevalence_pct-base.prevalence_pct AS change_since_2019_pp,
 CASE WHEN l.prevalence_pct IS NULL THEN 'Unavailable'
 WHEN l.prevalence_pct>b.states_dc_median_pct THEN 'Above states/DC median'
 ELSE 'At or below states/DC median' END AS descriptive_flag
FROM lagged l LEFT JOIN benchmark b USING(year)
LEFT JOIN ranked r USING(year,state_code)
LEFT JOIN clean_estimates base ON base.state_code=l.state_code
 AND base.year=2019 AND base.category='Overall';

-- Complete expected grid exposes wholly missing state-years.
CREATE VIEW state_year_coverage AS
WITH years(year) AS (VALUES(2019),(2020),(2021),(2022),(2023))
SELECT y.year,s.state_code,s.state_name,o.prevalence_pct,
 CASE WHEN o.state_code IS NULL THEN 'No source row'
 WHEN o.prevalence_pct IS NULL THEN 'Source estimate unavailable'
 ELSE 'Available' END AS coverage_status
FROM years y CROSS JOIN dim_state s
LEFT JOIN state_overall o ON o.year=y.year AND o.state_code=s.state_code;

CREATE VIEW demographic_metrics AS
SELECT c.*, o.prevalence_pct AS state_overall_pct,
 c.prevalence_pct-o.prevalence_pct AS gap_vs_state_overall_pp,
 CASE c.category WHEN 'Sex' THEN 'Female'
 WHEN 'Education Attained' THEN 'College graduate' END AS reference_segment,
 ref.prevalence_pct AS reference_prevalence_pct,
 c.prevalence_pct-ref.prevalence_pct AS reference_gap_pp,
 CASE WHEN ref.prevalence_pct>0 THEN c.prevalence_pct/ref.prevalence_pct END AS reference_ratio
FROM clean_estimates c JOIN dim_state s USING(state_code)
LEFT JOIN state_overall o ON o.year=c.year AND o.state_code=c.state_code
LEFT JOIN clean_estimates ref ON ref.year=c.year AND ref.state_code=c.state_code
 AND ref.category=c.category AND ref.segment=CASE c.category
 WHEN 'Sex' THEN 'Female' WHEN 'Education Attained' THEN 'College graduate' END
WHERE c.category<>'Overall';

-- Same-year subgroup range is descriptive, not a significance test.
CREATE VIEW demographic_ranges AS
SELECT year,state_code,state_name,category,
 COUNT(*) AS expected_segments,COUNT(prevalence_pct) AS available_segments,
 MIN(prevalence_pct) AS lowest_pct,MAX(prevalence_pct) AS highest_pct,
 MAX(prevalence_pct)-MIN(prevalence_pct) AS observed_range_pp,
 CASE WHEN COUNT(*)=COUNT(prevalence_pct) THEN 'Complete' ELSE 'Partial' END AS completeness
FROM demographic_metrics GROUP BY year,state_code,state_name,category;

CREATE VIEW persistent_elevation AS
SELECT state_code,state_name,COUNT(prevalence_pct) AS years_available,
 SUM(CASE WHEN gap_vs_median_pp>0 THEN 1 ELSE 0 END) AS years_above_median,
 CASE WHEN COUNT(prevalence_pct)=5 AND MIN(gap_vs_median_pp)>0
 THEN 'Above median in all 5 years' ELSE 'Other / incomplete' END AS pattern
FROM state_overall GROUP BY state_code,state_name;
