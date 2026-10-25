"""Create a static SVG chart summary from computed SQL exports (stdlib only)."""
from pathlib import Path
import csv,json,html
R=Path(__file__).resolve().parent
results=json.loads((R/'reports/results.json').read_text())
overall=list(csv.DictReader((R/'tableau/state_overall.csv').open()))
demo=list(csv.DictReader((R/'tableau/demographics.csv').open()))
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1000" viewBox="0 0 1400 1000">',
 '<rect width="1400" height="1000" fill="#f3f6f8"/>',
 '<style>text{font-family:Arial,sans-serif;fill:#183247}.muted{fill:#536c7c}.small{font-size:15px}.label{font-size:18px}.title{font-size:23px;font-weight:bold}</style>']
def text(x,y,s,size=18,color=None,weight=None):
    attrs=(f' fill="{color}"' if color else '')+(f' font-weight="{weight}"' if weight else '')
    # inline style takes precedence over the global text fill rule
    if color: attrs+=f' style="fill:{color}"'
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}"{attrs}>{html.escape(str(s))}</text>')
def rect(x,y,w,h,fill,rx=0): parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" rx="{rx}"/>')
def line(x1,y1,x2,y2,color='#bed0da',width=1): parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>')
text(42,47,'Smoking trends & disparities',32,weight='bold')
text(42,76,'CDC BRFSS | Historical 2019–2023 analysis | Static analytical summary, not a Tableau workbook',17,'#536c7c')
for x,value,label in [(42,'12.1%','2023 states/DC median'),(376,'20.4%','West Virginia, 2023'),(710,'17 states','Above median in all 5 years'),(1044,'49 / 51','2023 reporting jurisdictions')]:
    rect(x,102,314,111,'white',10);text(x+21,149,value,33,weight='bold');text(x+21,183,label,16,'#536c7c')
rect(42,236,640,365,'white',10);rect(704,236,654,365,'white',10)
text(65,272,'Highest 2023 point estimates',23,weight='bold')
text(65,296,'Top 8 reporting states/DC; whiskers show source 95% CIs',15,'#536c7c')
for i,r in enumerate(results['latest_top10'][:8]):
    y=326+i*32;text(65,y+6,r['state_name'],17)
    x=lambda v:235+float(v)*16
    line(x(0),y,x(23),y,'#eef3f5')
    line(x(r['ci_low']),y,x(r['ci_high']),y,'#6f8796',2)
    line(x(r['ci_low']),y-4,x(r['ci_low']),y+4,'#6f8796',2)
    line(x(r['ci_high']),y-4,x(r['ci_high']),y+4,'#6f8796',2)
    parts.append(f'<circle cx="{x(r["prevalence_pct"])}" cy="{y}" r="5" fill="#087f8c"/>')
    text(615,y+6,f'{r["prevalence_pct"]:.1f}%',16)
text(65,588,'KY and PA unavailable; point-estimate ranks are descriptive.',15,'#536c7c')
text(728,272,'West Virginia vs states/DC median',23,weight='bold')
text(728,296,'Overall current cigarette smoking prevalence (%)',15,'#536c7c')
def xp(year):return 783+(year-2019)*130
def yp(rate):return 548-(rate-10)*15
for v in [10,15,20,25]:
    line(782,yp(v),1303,yp(v),'#e6edf1');text(742,yp(v)+5,f'{v}%',15,'#536c7c')
wv=sorted([r for r in overall if r['state_code']=='WV'],key=lambda r:r['year'])
for records,color,key in [(wv,'#087f8c','prevalence_pct'),(results['benchmark'],'#c0782c','states_dc_median_pct')]:
    pts=' '.join(f'{xp(int(r["year"]))},{yp(float(r[key]))}' for r in records)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3"/>')
    for r in records:
        parts.append(f'<circle cx="{xp(int(r["year"]))}" cy="{yp(float(r[key]))}" r="4" fill="{color}"/>')
for year in range(2019,2024):text(xp(year)-19,577,year,15,'#536c7c')
text(1035,320,'West Virginia',16,'#087f8c');text(1035,344,'States/DC median',16,'#c0782c')
rect(42,623,770,264,'white',10);rect(834,623,524,264,'white',10)
text(65,660,'West Virginia: education disparity, 2023',23,weight='bold')
text(65,685,'Published subgroup prevalence; 95% CIs shown',15,'#536c7c')
ed={r['segment']:r for r in demo if r['state_code']=='WV' and r['year']=='2023' and r['category']=='Education Attained'}
for i,name in enumerate(['Less than H.S.','H.S. or G.E.D.','Some post-H.S.','College graduate']):
    r=ed[name];y=718+i*39;x=lambda v:258+float(v)*8
    text(65,y+6,name,17);rect(258,y-9,float(r['prevalence_pct'])*8,18,'#cae7e9',2)
    line(x(r['ci_low']),y,x(r['ci_high']),y,'#466578',2)
    parts.append(f'<circle cx="{x(r["prevalence_pct"])}" cy="{y}" r="5" fill="#087f8c"/>')
    text(720,y+6,f'{float(r["prevalence_pct"]):.1f}%',17)
text(858,660,'Planning interpretation',23,weight='bold')
for i,s in enumerate(['Review sustained geographic elevation','alongside demographic disparities.','WV less-than-HS vs college gap: 33.7 pp.','Check uncertainty, local needs and capacity','before selecting outreach resources.','No intervention effect or savings measured.']):
    text(858,698+i*29,s,17,'#536c7c')
text(42,921,'Weighted crude survey estimates; not age-adjusted. Median is not US population-weighted prevalence.',16,'#536c7c')
text(42,948,'Do not sum subgroup rates. Missing estimates remain null. Comparisons do not establish causality or statistical significance.',16,'#536c7c')
text(42,975,'Source: data.cdc.gov/d/dttw-5yxu | Extracted 2026-10-20 | Reproducible SQL metrics and validation included',15,'#536c7c')
parts.append('</svg>')
(R/'reports/visual_summary.svg').write_text('\n'.join(parts))
print(R/'reports/visual_summary.svg')
