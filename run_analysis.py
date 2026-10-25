"""Rebuild offline: python3 run_analysis.py. Refresh explicitly: --refresh.
Only Python standard library is required. SQL, not Python, calculates metrics.
"""
from pathlib import Path
import csv, datetime, hashlib, json, sqlite3, sys, urllib.parse, urllib.request

ROOT = Path(__file__).resolve().parent
QUERY = {'$where': 'questionid = "_RFSMOK3" AND responseid = "RESP046" AND year between "2019" and "2023"',
         '$limit': '50000', '$order': 'year,locationabbr,breakoutcategoryid,breakoutid'}
URL = 'https://data.cdc.gov/resource/dttw-5yxu.json?' + urllib.parse.urlencode(QUERY)
raw_path = ROOT/'data/cdc_brfss_smoking_raw.json'
if '--refresh' in sys.argv:
    with urllib.request.urlopen(URL, timeout=120) as response:
        raw_path.write_bytes(response.read())
    (ROOT/'data/source_manifest.json').unlink(missing_ok=True)
rows = json.loads(raw_path.read_text())
assert isinstance(rows,list) and 0<len(rows)<50000, 'Check API result / pagination'
assert all(r['questionid']=='_RFSMOK3' and r['responseid']=='RESP046' for r in rows)
columns = ['year','locationabbr','locationdesc','break_out_category','break_out',
 'breakoutcategoryid','breakoutid','data_value','confidence_limit_low','confidence_limit_high',
 'sample_size','data_value_footnote','questionid','responseid','data_value_type','data_value_unit']
db_path=ROOT/'data/analytics.sqlite'
db_path.unlink(missing_ok=True)
db=sqlite3.connect(db_path)
db.row_factory=sqlite3.Row
db.execute('CREATE TABLE raw_estimates ('+','.join(c+' TEXT' for c in columns)+')')
db.executemany('INSERT INTO raw_estimates VALUES ('+','.join('?' for _ in columns)+')',
 [[r.get(c) for c in columns] for r in rows])
codes='AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split()
names={r['locationabbr']:r['locationdesc'] for r in rows}
db.execute('CREATE TABLE dim_state (state_code TEXT PRIMARY KEY,state_name TEXT NOT NULL)')
db.executemany('INSERT INTO dim_state VALUES (?,?)',[(c,names[c]) for c in codes])
db.executescript((ROOT/'sql/analysis.sql').read_text())

def query(sql): return [dict(r) for r in db.execute(sql)]
def export(name,sql):
    result=query(sql)
    with (ROOT/'tableau'/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    return result

overall=export('state_overall.csv','SELECT * FROM state_overall ORDER BY year,state_code')
demo=export('demographics.csv','SELECT * FROM demographic_metrics ORDER BY year,state_code,category,segment')
export('demographic_ranges.csv','SELECT * FROM demographic_ranges ORDER BY year,state_code,category')
coverage=export('coverage.csv','SELECT * FROM state_year_coverage ORDER BY year,state_code')
export('benchmark.csv','SELECT * FROM benchmark ORDER BY year')
export('persistent_elevation.csv','SELECT * FROM persistent_elevation ORDER BY state_code')
checks={}
checks['raw_rows']=len(rows)
checks['duplicate_grain_count']=len(query('SELECT year,state_code,category_id,segment_id,COUNT(*) n FROM clean_estimates GROUP BY 1,2,3,4 HAVING COUNT(*)>1'))
checks['invalid_bounds_count']=len(query('SELECT * FROM clean_estimates WHERE prevalence_pct<0 OR prevalence_pct>100 OR (ci_low IS NOT NULL AND (ci_low>prevalence_pct OR ci_high<prevalence_pct OR ci_low<0 OR ci_high>100))'))
checks['raw_to_clean_rows']=query('SELECT COUNT(*) n FROM clean_estimates')[0]['n']
checks['states_in_dimension']=len(codes)
checks['expected_state_years']=len(coverage)
checks['state_years_available']=sum(r['coverage_status']=='Available' for r in coverage)
checks['unavailable_estimates_all_locations']=query('SELECT COUNT(*) n FROM clean_estimates WHERE prevalence_pct IS NULL')[0]['n']
checks['state_overall_rows']=len(overall)
checks['state_demographic_rows']=len(demo)
checks['missing_state_years']=[r for r in coverage if r['coverage_status']!='Available']
# Independent checks: compare SQL output to source and arithmetic in Python.
source={(int(r['year']),r['locationabbr'],r['break_out_category'],r['break_out']):r for r in rows}
for r in overall:
    original=source[(r['year'],r['state_code'],'Overall','Overall')]
    assert r['prevalence_pct']==(float(original['data_value']) if original.get('data_value') else None)
    prior=source.get((r['year']-1,r['state_code'],'Overall','Overall'))
    expected=(r['prevalence_pct']-float(prior['data_value'])) if r['prevalence_pct'] is not None and prior and prior.get('data_value') else None
    assert r['yoy_change_pp']==expected
for r in demo:
    if r['prevalence_pct'] is not None and r['reference_prevalence_pct'] is not None:
        assert abs(r['reference_gap_pp']-(r['prevalence_pct']-r['reference_prevalence_pct']))<1e-10
assert checks['duplicate_grain_count']==checks['invalid_bounds_count']==0
assert checks['raw_to_clean_rows']==len(rows) and checks['expected_state_years']==255
checks['independent_source_and_arithmetic_checks']='Passed'
independent_persistent=[]
medians={int(r['year']):float(r['data_value']) for r in rows if r['locationabbr']=='UW' and r['break_out_category']=='Overall'}
for code in codes:
    observations=[source.get((year,code,'Overall','Overall')) for year in range(2019,2024)]
    if all(r and r.get('data_value') and float(r['data_value'])>medians[int(r['year'])] for r in observations):
        independent_persistent.append(code)
sql_persistent=[r['state_code'] for r in query('SELECT state_code FROM persistent_elevation WHERE pattern="Above median in all 5 years"')]
assert set(sql_persistent)==set(independent_persistent)
checks['independently_verified_persistent_states']=len(independent_persistent)
for code,year in [('FL',2022),('NJ',2020)]:
    assert query(f"SELECT yoy_change_pp FROM state_overall WHERE state_code='{code}' AND year={year}")[0]['yoy_change_pp'] is None
checks['missing_prior_calendar_year_guards']='Passed: FL 2022 and NJ 2020'
checks['database_integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]
(ROOT/'reports/validation.json').write_text(json.dumps(checks,indent=2))

results={
 'coverage_by_year':query('SELECT year,COUNT(*) expected,SUM(coverage_status="Available") available FROM state_year_coverage GROUP BY year'),
 'latest_top10':query('SELECT state_name,prevalence_pct,ci_low,ci_high,gap_vs_median_pp,yoy_change_pp FROM state_overall WHERE year=2023 AND prevalence_pct IS NOT NULL ORDER BY prevalence_rank,state_name LIMIT 10'),
 'latest_bottom5':query('SELECT state_name,prevalence_pct FROM state_overall WHERE year=2023 AND prevalence_pct IS NOT NULL ORDER BY prevalence_pct LIMIT 5'),
 'benchmark':query('SELECT * FROM benchmark ORDER BY year'),
 'persistent':query('SELECT * FROM persistent_elevation WHERE pattern="Above median in all 5 years" ORDER BY state_name'),
 'largest_education_gap':query('SELECT state_name,segment,prevalence_pct,reference_prevalence_pct,reference_gap_pp,reference_ratio FROM demographic_metrics WHERE year=2023 AND category="Education Attained" AND segment="Less than H.S." AND reference_gap_pp IS NOT NULL ORDER BY reference_gap_pp DESC LIMIT 5'),
 'largest_declines_matched':query('SELECT state_name,baseline_2019_pct,prevalence_pct,change_since_2019_pp FROM state_overall WHERE year=2023 AND change_since_2019_pp IS NOT NULL ORDER BY change_since_2019_pp LIMIT 5')}
(ROOT/'reports/results.json').write_text(json.dumps(results,indent=2))
manifest_path=ROOT/'data/source_manifest.json'
if not manifest_path.exists():
    manifest={'dataset':'CDC BRFSS Prevalence Data (2011 to present)','dataset_id':'dttw-5yxu',
      'dataset_url':'https://data.cdc.gov/d/dttw-5yxu','download_url':URL,
      'retrieved_date':'2026-10-20' if '--refresh' not in sys.argv else datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
      'sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest(),'rows':len(rows),
      'scope':'Historical 2019–2023 extract, not the latest available CDC years',
      'grain':'year × location × breakout category × breakout; aggregate survey estimates, not respondent records'}
    manifest_path.write_text(json.dumps(manifest,indent=2))
assert json.loads(manifest_path.read_text())['sha256']==hashlib.sha256(raw_path.read_bytes()).hexdigest()
db.commit();db.close()
print(json.dumps({'validation':checks,'findings':results},indent=2))
