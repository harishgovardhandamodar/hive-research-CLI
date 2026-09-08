#!/usr/bin/env python3
"""
Diabetes-Management-system — Medtronic CareLink → Timeseries Report
Standalone script (also used inside Hive-Machine workflow).

Parses Medtronic CareLink CSV (Sensor Glucose), builds timeseries,
renders charts, generates markdown report; optionally enriches with local Ollama.

Usage:
  python scripts/diabetes_carelink_report.py --input /path/to/CareLink.csv
  python scripts/diabetes_carelink_report.py --input carelink.csv --output /tmp/diabetes-report --no-llm
  python scripts/diabetes_carelink_report.py --sample   # generate synthetic data

Hive-Machine integration:
  Input defaults to ~/.hive/machine/workspace/diabetes_management/local-only/datasets/carelink.csv
  Output defaults to ~/.hive/machine/workspace/diabetes_management/local-only/reports
  Run via workflow: hive machine workflow run diabetes_management
                    python scripts/run_diabetes_workflow.py
"""
from __future__ import annotations
import argparse, csv, json, statistics, datetime, sys
from pathlib import Path
from collections import defaultdict

MGDL_TO_MMOL = 18.01559
MGDL_THR = {"low": 70, "high": 180, "very_low": 54, "very_high": 250}
MMOL_THR = {k: round(v / MGDL_TO_MMOL, 1) for k, v in MGDL_THR.items()}

def mgdl_to_mmol(v): return round(v / MGDL_TO_MMOL, 1)
def mmol_to_mgdl(v): return round(v * MGDL_TO_MMOL, 0)

DEFAULT_WS = Path.home() / ".hive" / "machine" / "workspace" / "diabetes_management" / "local-only"
DEFAULT_INPUT = DEFAULT_WS / "datasets" / "carelink.csv"
DEFAULT_OUTPUT = DEFAULT_WS / "reports"

def parse_carelink(path: Path):
    rows = []
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        fieldnames = [h.strip() for h in (reader.fieldnames or [])]
        if not fieldnames:
            raise ValueError("CSV has no header — expected CareLink export")
        lower_map = {h.lower(): h for h in fieldnames}
        def pick(*names):
            for n in names:
                if n.lower() in lower_map:
                    return lower_map[n.lower()]
            for n in names:
                for k in lower_map:
                    if n.lower() in k:
                        return lower_map[k]
            return None
        sg_col = pick('Sensor Glucose (mg/dL)', 'Sensor Glucose', 'SG', 'Glucose', 'sensor')
        date_col = pick('Date', 'Timestamp', 'Datetime')
        time_col = pick('Time')
        if not sg_col and fieldnames:
            sg_col = fieldnames[2] if len(fieldnames) > 2 else fieldnames[0]
        for rec in reader:
            r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in rec.items() if k}
            sg_val = None
            if sg_col and r.get(sg_col):
                raw = str(r.get(sg_col)).strip()
                if raw and raw not in ('---', '', 'N/A'):
                    try:
                        sg_val = float(raw.replace(',', ''))
                    except Exception:
                        continue
            dt = None
            try:
                if date_col and time_col and r.get(date_col) and r.get(time_col):
                    ds = r.get(date_col); ts = r.get(time_col)
                    for fmt in ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S', '%m/%d/%y %H:%M:%S'):
                        try:
                            dt = datetime.datetime.strptime(f'{ds} {ts}', fmt)
                            break
                        except Exception:
                            continue
                elif date_col and r.get(date_col):
                    ds = r.get(date_col)
                    for fmt in ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%m/%d/%y %H:%M:%S', '%Y/%m/%d %H:%M'):
                        try:
                            dt = datetime.datetime.strptime(ds.strip(), fmt)
                            break
                        except Exception:
                            continue
                    if dt is None and 'T' in ds:
                        try:
                            dt = datetime.datetime.fromisoformat(ds.strip().replace('Z',''))
                        except Exception:
                            pass
            except Exception:
                pass
            if sg_val is not None:
                rows.append((dt, sg_val))
    return rows, fieldnames

def analyze(rows):
    rows_with_dt = [r for r in rows if r[0] is not None]
    rows_with_dt.sort(key=lambda x: x[0])
    vals = [v for _, v in rows_with_dt] if rows_with_dt else [v for _, v in rows]
    if not vals:
        raise ValueError("No Sensor Glucose values found")
    mean = statistics.mean(vals)
    median = statistics.median(vals)
    stdev = statistics.stdev(vals) if len(vals) > 1 else 0
    _min, _max = min(vals), max(vals)
    tir = sum(1 for v in vals if 70 <= v <= 180) / len(vals) * 100
    below70 = sum(1 for v in vals if v < 70) / len(vals) * 100
    below54 = sum(1 for v in vals if v < 54) / len(vals) * 100
    above180 = sum(1 for v in vals if v > 180) / len(vals) * 100
    above250 = sum(1 for v in vals if v > 250) / len(vals) * 100
    gmi = 3.31 + 0.02392 * mean
    ea1c = (mean + 46.7) / 28.7
    cv = stdev / mean * 100 if mean else 0
    daily = defaultdict(list)
    hourly = defaultdict(list)
    for dt, v in rows_with_dt:
        daily[dt.date().isoformat()].append(v)
        hourly[dt.hour].append(v)
    daily_stats = {d: {'n': len(v), 'mean': round(statistics.mean(v), 1), 'min': min(v), 'max': max(v)} for d, v in sorted(daily.items())}
    hourly_stats = {str(h): round(statistics.mean(v), 1) for h, v in sorted(hourly.items())}
    summary = {
        'readings': len(vals),
        'date_range': [rows_with_dt[0][0].isoformat() if rows_with_dt else None, rows_with_dt[-1][0].isoformat() if rows_with_dt else None],
        'mean_mgdl': round(mean, 1),
        'mean_mmol': mgdl_to_mmol(mean),
        'median_mgdl': round(median, 1),
        'median_mmol': mgdl_to_mmol(median),
        'stdev': round(stdev, 1),
        'stdev_mmol': round(stdev / MGDL_TO_MMOL, 1),
        'cv_percent': round(cv, 1),
        'min': _min, 'max': _max,
        'min_mmol': mgdl_to_mmol(_min),
        'max_mmol': mgdl_to_mmol(_max),
        'gmi_percent': round(gmi, 2),
        'ea1c_percent': round(ea1c, 2),
        'tir_70_180_percent': round(tir, 1),
        'below_70_percent': round(below70, 1),
        'below_54_percent': round(below54, 1),
        'above_180_percent': round(above180, 1),
        'above_250_percent': round(above250, 1),
        'thresholds_mgdl': MGDL_THR,
        'thresholds_mmol': MMOL_THR,
        'daily': daily_stats,
        'hourly_mean': hourly_stats,
        'hourly_mean_mmol': {k: mgdl_to_mmol(v) for k, v in hourly_stats.items()},
    }
    # also enrich daily_stats with mmol
    for d in summary['daily']:
        summary['daily'][d]['mean_mmol'] = mgdl_to_mmol(summary['daily'][d]['mean'])
        summary['daily'][d]['min_mmol'] = mgdl_to_mmol(summary['daily'][d]['min'])
        summary['daily'][d]['max_mmol'] = mgdl_to_mmol(summary['daily'][d]['max'])
    return summary, rows_with_dt, daily_stats, hourly_stats, vals, _max

def write_outputs(summary, rows_with_dt, daily_stats, hourly_stats, output_dir: Path, carelink_path: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'carelink_timeseries_summary.json').write_text(json.dumps({**summary, 'file': str(carelink_path)}, indent=2))
    with open(output_dir / 'carelink_daily_timeseries.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['date','n','mean_mgdl','mean_mmol','min_mgdl','min_mmol','max_mgdl','max_mmol'])
        for d, s in sorted(daily_stats.items()):
            w.writerow([d, s['n'], s['mean'], mgdl_to_mmol(s['mean']), s['min'], mgdl_to_mmol(s['min']), s['max'], mgdl_to_mmol(s['max'])])
    with open(output_dir / 'carelink_hourly_timeseries.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['hour','mean_mgdl','mean_mmol'])
        for h, m in sorted(hourly_stats.items(), key=lambda x: int(x[0])):
            w.writerow([h, m, mgdl_to_mmol(m)])
    with open(output_dir / 'carelink_raw_timeseries.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['timestamp','sg_mgdl','sg_mmol'])
        for dt, v in rows_with_dt:
            w.writerow([dt.isoformat(), v, mgdl_to_mmol(v)])
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from collections import defaultdict
        # --- 24h per day trend + frequency bands ---
        daily_groups = defaultdict(list)
        for dt, v in rows_with_dt:
            daily_groups[dt.date().isoformat()].append((dt, v))
        sorted_days = sorted(daily_groups.keys())
        cmap = plt.get_cmap('tab10')
        # 24h glucose trend + frequency bands — mg/dL
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        for idx, day in enumerate(sorted_days):
            pts = daily_groups[day]
            xs = [dt.hour + dt.minute/60 + dt.second/3600 for dt, _ in pts]
            ys = [v for _, v in pts]
            xy = sorted(zip(xs, ys))
            if xy:
                xs_s, ys_s = zip(*xy)
                ax1.plot(xs_s, ys_s, linewidth=1.0, alpha=0.85, label=day, color=cmap(idx % 10))
        ax1.axhspan(70, 180, color='green', alpha=0.08, label='TIR 70-180 mg/dL (3.9-10.0 mmol/L)')
        ax1.axhline(70, color='red', linestyle='--', linewidth=0.6)
        ax1.axhline(180, color='orange', linestyle='--', linewidth=0.6)
        ax1.set_title('Medtronic CareLink — 24h Trend per Day (mg/dL) + Frequency Bands')
        ax1.set_ylabel('mg/dL')
        ax1.set_xlim(0, 24)
        ax1.set_ylim(40, max(300, summary['max']+20))
        ax1.grid(alpha=0.15)
        if len(sorted_days) <= 10:
            ax1.legend(loc='upper right', fontsize=8, ncol=2)
        else:
            ax1.legend(loc='upper right', fontsize=7, ncol=3)
        # frequency bands (readings per hour) per day — bottom
        for idx, day in enumerate(sorted_days):
            pts = daily_groups[day]
            hourly_counts = [0]*24
            for dt, _ in pts:
                hourly_counts[dt.hour] += 1
            ax2.plot(range(24), hourly_counts, marker='o', linewidth=1.0, alpha=0.85, label=day, color=cmap(idx % 10))
        if sorted_days:
            avg_counts = []
            for h in range(24):
                vals_h = [sum(1 for dt,_ in daily_groups[d] if dt.hour == h) for d in sorted_days]
                avg_counts.append(sum(vals_h)/len(vals_h) if vals_h else 0)
            ax2.plot(range(24), avg_counts, linewidth=2.5, linestyle='--', color='black', label='avg', alpha=0.9)
            # frequency bands: low (<6), normal (6-12), high (>12) readings/hour
            ax2.axhspan(0, 6, color='red', alpha=0.07, label='low freq')
            ax2.axhspan(6, 12, color='green', alpha=0.07, label='expected ~12/hr')
            ax2.axhspan(12, 14, color='orange', alpha=0.07)
        ax2.set_title('Frequency Bands — Readings per Hour per Day')
        ax2.set_xlabel('Hour of day')
        ax2.set_ylabel('Frequency')
        ax2.set_xlim(0, 23)
        ax2.set_xticks(range(0, 24, 2))
        ax2.set_ylim(0, 14)
        ax2.grid(alpha=0.15)
        plt.tight_layout()
        plt.savefig(output_dir / 'carelink_timeseries.png', dpi=150)
        plt.close()
        # mmol version — same frequency bands
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        for idx, day in enumerate(sorted_days):
            pts = daily_groups[day]
            xs = [dt.hour + dt.minute/60 + dt.second/3600 for dt, _ in pts]
            ys = [mgdl_to_mmol(v) for _, v in pts]
            xy = sorted(zip(xs, ys))
            if xy:
                xs_s, ys_s = zip(*xy)
                ax1.plot(xs_s, ys_s, linewidth=1.0, alpha=0.85, label=day, color=cmap(idx % 10))
        ax1.axhspan(3.9, 10.0, color='green', alpha=0.08, label='TIR 3.9-10.0 mmol/L')
        ax1.axhline(3.9, color='red', linestyle='--', linewidth=0.6)
        ax1.axhline(10.0, color='orange', linestyle='--', linewidth=0.6)
        ax1.set_title('Medtronic CareLink — 24h Trend per Day (mmol/L) + Frequency Bands')
        ax1.set_ylabel('mmol/L')
        ax1.set_xlim(0, 24)
        ax1.set_ylim(2.2, max(16.5, mgdl_to_mmol(summary['max'])+1))
        ax1.grid(alpha=0.15)
        if len(sorted_days) <= 10:
            ax1.legend(loc='upper right', fontsize=8, ncol=2)
        else:
            ax1.legend(loc='upper right', fontsize=7, ncol=3)
        for idx, day in enumerate(sorted_days):
            pts = daily_groups[day]
            hourly_counts = [0]*24
            for dt, _ in pts:
                hourly_counts[dt.hour] += 1
            ax2.plot(range(24), hourly_counts, marker='o', linewidth=1.0, alpha=0.85, label=day, color=cmap(idx % 10))
        if sorted_days:
            avg_counts = []
            for h in range(24):
                vals_h = [sum(1 for dt,_ in daily_groups[d] if dt.hour == h) for d in sorted_days]
                avg_counts.append(sum(vals_h)/len(vals_h) if vals_h else 0)
            ax2.plot(range(24), avg_counts, linewidth=2.5, linestyle='--', color='black', label='avg', alpha=0.9)
            ax2.axhspan(0, 6, color='red', alpha=0.07)
            ax2.axhspan(6, 12, color='green', alpha=0.07)
            ax2.axhspan(12, 14, color='orange', alpha=0.07)
        ax2.set_title('Frequency Bands — Readings per Hour per Day')
        ax2.set_xlabel('Hour of day')
        ax2.set_ylabel('Frequency')
        ax2.set_xlim(0, 23)
        ax2.set_xticks(range(0, 24, 2))
        ax2.set_ylim(0, 14)
        ax2.grid(alpha=0.15)
        plt.tight_layout()
        plt.savefig(output_dir / 'carelink_timeseries_mmol.png', dpi=150)
        plt.close()
        print(f'24h trend + frequency bands saved: {output_dir / "carelink_timeseries.png"} and _mmol')
        # daily mean charts (keep)
        if daily_stats:
            plt.figure(figsize=(10, 3))
            ds = list(daily_stats.keys())
            ms = [daily_stats[d]['mean'] for d in ds]
            plt.plot(ds, ms, marker='o', linewidth=1)
            plt.axhspan(70, 180, color='green', alpha=0.08)
            plt.title('Daily Mean Glucose (mg/dL)')
            plt.xticks(rotation=30, ha='right')
            plt.tight_layout()
            plt.savefig(output_dir / 'carelink_daily.png', dpi=150)
            plt.close()
            plt.figure(figsize=(10, 3))
            ms_mmol = [mgdl_to_mmol(m) for m in ms]
            plt.plot(ds, ms_mmol, marker='o', linewidth=1, color='#4f8cff')
            plt.axhspan(3.9, 10.0, color='green', alpha=0.08)
            plt.title('Daily Mean Glucose (mmol/L)')
            plt.xticks(rotation=30, ha='right')
            plt.tight_layout()
            plt.savefig(output_dir / 'carelink_daily_mmol.png', dpi=150)
            plt.close()
            print(f'Daily charts saved')
    except Exception as e:
        print(f"[chart skipped] {e}", file=sys.stderr)
        try:
            bmin, bmax = 50, 300; blocks = ' ▁▂▃▄▅▆▇█'
            all_vals = [v for _, v in rows_with_dt] if rows_with_dt else []
            line = ''.join(blocks[min(len(blocks)-1, max(0, int((v-bmin)/(bmax-bmin)*(len(blocks)-1))))] for v in all_vals[:120])
            (output_dir / 'carelink_timeseries_ascii.txt').write_text(f'ASCII sparkline (first 120, 50-300 mg/dL):\n{line}\n')
        except Exception:
            pass

def deterministic_report(summary, output_dir: Path, unit: str = "both") -> str:
    tir = summary['tir_70_180_percent']
    cv = summary['cv_percent']
    variability = "high" if cv > 36 else "moderate" if cv > 20 else "low"
    hourly = summary.get('hourly_mean', {})
    peak_h = max(hourly, key=lambda k: hourly[k]) if hourly else "n/a"
    low_h = min(hourly, key=lambda k: hourly[k]) if hourly else "n/a"
    dr = summary['date_range']
    # helpers for dual-unit display
    def fmt_both(mg):
        return f"{mg} mg/dL ({mgdl_to_mmol(mg)} mmol/L)" if unit in ("both","mgdl") else f"{mgdl_to_mmol(mg)} mmol/L"
    def fmt_mg(mg):
        return f"{mg} mg/dL ({mgdl_to_mmol(mg)} mmol/L)" 
    # pre-format dual values
    mean_both = fmt_both(summary['mean_mgdl'])
    median_both = fmt_both(summary['median_mgdl'])
    min_both = fmt_both(summary['min'])
    max_both = fmt_both(summary['max'])
    sd_both = f"{summary['stdev']} mg/dL ({summary['stdev_mmol']} mmol/L)"
    md = f"""# Diabetes Management — Medtronic CareLink Report

> Local-only — generated without web. Educational use only; not medical advice. Consult your healthcare professional.
> Units: mg/dL ↔ mmol/L (÷{MGDL_TO_MMOL}) · Switch in dashboard or re-run with --unit mgdl|mmol|both

## Overview
- Readings: {summary['readings']} (from {dr[0]} to {dr[1]})
- Mean / Median: {mean_both} / {median_both} (SD {sd_both}, CV {cv}%)
- Range: {min_both} – {max_both}
- GMI: {summary['gmi_percent']}% · eA1c: {summary['ea1c_percent']}% (estimated from mean; not a lab A1c)
- Variability: {variability} (CV {cv}%)

## Time in Ranges (ADA targets)
- TIR 70–180 mg/dL (3.9–10.0 mmol/L): {summary['tir_70_180_percent']}% — {"meets ≥70% target" if tir >= 70 else "below ≥70% target — review with clinician"}
- Below 70 mg/dL (3.9 mmol/L): {summary['below_70_percent']}% (target <4%) · Below 54 mg/dL (3.0 mmol/L): {summary['below_54_percent']}% (target <1%)
- Above 180 mg/dL (10.0 mmol/L): {summary['above_180_percent']}% (target <25%) · Above 250 mg/dL (13.9 mmol/L): {summary['above_250_percent']}% (target <5%)

## Daily & Hourly Patterns
- Daily mean range: {fmt_both(min(v['mean'] for v in summary['daily'].values())) if summary['daily'] else 'n/a'} – {fmt_both(max(v['mean'] for v in summary['daily'].values())) if summary['daily'] else 'n/a'}
- Hourly peak mean: {peak_h}:00 → {fmt_both(hourly.get(peak_h, 0)) if peak_h!='n/a' else 'n/a'}
- Hourly low mean: {low_h}:00 → {fmt_both(hourly.get(low_h, 0)) if low_h!='n/a' else 'n/a'}
- See `carelink_hourly_timeseries.csv` and `carelink_daily_timeseries.csv` for full timeseries.

## Observations
- Hypoglycemia frequency: {summary['below_70_percent']}% <70; {summary['below_54_percent']}% <54 — {"monitor overnight/post-bolus periods" if summary['below_70_percent'] >= 4 else "within target, continue monitoring"}.
- Hyperglycemia frequency: {summary['above_180_percent']}% >180; {summary['above_250_percent']}% >250 — {"consider pattern review around meals" if summary['above_180_percent'] >= 25 else "within target"}.
- Variability CV {cv}% — {"high variability; discuss stability strategies" if cv > 36 else "stable wear; continue consistent sensor use"}.

## Next Steps (educational, non-prescriptive)
- Keep consistent sensor wear and log meals, activity, and insulin for pattern correlation.
- Review this timeseries with your care team; bring `carelink_timeseries.png` and daily/hourly CSVs.
- Consider CareLink alerts for <70 and >250 and checking overnight trends.

---

## Appendix
- Summary JSON: `carelink_timeseries_summary.json`
- Daily CSV: `carelink_daily_timeseries.csv` · Hourly CSV: `carelink_hourly_timeseries.csv` · Raw CSV: `carelink_raw_timeseries.csv`
- Charts: `carelink_timeseries.png` / `carelink_daily.png`

*Generated locally at {datetime.datetime.now().isoformat()} — no data left device.*
"""
    (output_dir / "carelink_report.md").write_text(md)
    return md

def try_local_llm(summary: dict) -> str | None:
    try:
        from hive.config import load_config
        from hive.llm import chat, ChatMessage
        cfg = load_config()
        prompt = f"""You are a diabetes educator assistant. Using ONLY the CareLink timeseries summary below, write a concise, non-diagnostic educational report in Markdown.

Summary JSON:
{json.dumps(summary, indent=2)}

Required sections:
# Diabetes Management — CareLink Timeseries Report
## Overview (readings, date range, mean, GMI/eA1c, CV)
## Time in Ranges (TIR 70-180, below 70/54, above 180/250 — with brief plain-English interpretation)
## Daily & Hourly Patterns (what hours/days trend high or low; variability)
## Observations (3-5 bullets, data-driven; flag hypo/hyper frequency and overnight patterns)
## Next Steps (educational, non-prescriptive: logging, clinician discussion, sensor wear, pattern review)

Constraints: Be concise, data-grounded, no invented values, include disclaimer that this is educational information not medical advice and to consult healthcare professional.
"""
        resp = chat(cfg, [ChatMessage(role="user", content=prompt)])
        return resp.content
    except Exception as e:
        print(f"[local LLM skipped] {e}", file=sys.stderr)
        return None

def main():
    ap = argparse.ArgumentParser(description="Medtronic CareLink → timeseries report (local-only)")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CareLink CSV path")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output reports dir")
    ap.add_argument("--no-llm", action="store_true", help="skip local LLM enrichment")
    ap.add_argument("--unit", choices=["mgdl","mmol","both"], default="both", help="display unit (default both)")
    ap.add_argument("--sample", action="store_true", help="generate synthetic CareLink CSV sample and exit")
    args = ap.parse_args()

    if args.sample:
        args.input.parent.mkdir(parents=True, exist_ok=True)
        with open(args.input, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Date','Time','Sensor Glucose (mg/dL)','BG Reading (mg/dL)'])
            base = datetime.datetime.now() - datetime.timedelta(days=7)
            import random, math
            for i in range(7*288):
                dt = base + datetime.timedelta(minutes=5*i)
                sg = max(55, min(320, int(random.gauss(150, 40) + 10*math.sin(i/50))))
                w.writerow([dt.strftime('%m/%d/%Y'), dt.strftime('%H:%M:%S'), sg, ''])
        print(f"Sample written to {args.input}")
        return

    if not args.input.exists():
        print(f"[error] CareLink CSV not found: {args.input}", file=sys.stderr)
        print(f"  Export from Medtronic CareLink (CSV) and place at {args.input}", file=sys.stderr)
        print(f"  Or run with --sample to generate synthetic data", file=sys.stderr)
        sys.exit(1)

    rows, cols = parse_carelink(args.input)
    print(f"Parsed {len(rows)} rows, columns: {cols}", file=sys.stderr)
    summary, rows_with_dt, daily_stats, hourly_stats, vals, _max = analyze(rows)
    print(json.dumps(summary, indent=2))
    # also write mmol column for raw csv for dashboard toggle
    write_outputs(summary, rows_with_dt, daily_stats, hourly_stats, args.output, args.input)
    base_md = deterministic_report(summary, args.output, unit=args.unit)
    print(f"\nReports written to {args.output}", file=sys.stderr)
    if not args.no_llm:
        llm_md = try_local_llm(summary)
        if llm_md:
            enriched = f"# Diabetes Management — Medtronic CareLink Report\n\n> Local-only — enriched via local Ollama model. Educational use only; not medical advice.\n\n{llm_md}\n\n---\n\n## Appendix: Timeseries Data\n\n- Summary: `carelink_timeseries_summary.json`\n- CSVs: `carelink_daily_timeseries.csv`, `carelink_hourly_timeseries.csv`, `carelink_raw_timeseries.csv`\n- Charts: `carelink_timeseries.png`, `carelink_daily.png`\n"
            (args.output / "carelink_report.md").write_text(enriched)
            print("[LLM enriched report written]", file=sys.stderr)
    print((args.output / "carelink_report.md").read_text()[:2000])

if __name__ == "__main__":
    main()
