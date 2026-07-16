"""SINGLE SOURCE OF TRUTH for funnels & price bands.
Both analyze_variants.py (xlsx) and build_report.py (HTML) import from here.
Edit funnels/prices in ONE place — everything downstream updates on re-run.

Plan/upsell classification is INFERRED from the EUR amount, because price_id is
empty in the Stripe payment export. When a new funnel launches or a price changes,
add/adjust a line below."""
import pandas as pd

# funnel slug -> (label, type, maturation window days, annual/yearly min €, upsell band €)
FUNNELS = {
 "quiz_v1_jp_ft_11800yen-60-eur": ("JP-01 A  ¥11,800/€60", "free trial", 7, 45, (15, 30)),
 "quiz_v1_jp_ft_14800yen-80-eur": ("JP-01 B  ¥14,800/€80", "free trial", 7, 70, (15, 30)),
 "quiz_v1_gr_nt_m10_y50eur":      ("GR-02  plan picker",   "no trial",   0, 40, (15, 30)),
 "quiz_v1_ro_nt_m10_y50eur":      ("RO-01  plan picker",   "no trial",   0, 30, (15, 30)),
 "quiz_v1_pt2":                   ("Paid trial v2 (GR)",   "paid trial", 7, 45, (15, 30)),
 "quiz_v1_ft":                    ("Free trial v1",        "free trial", 7, 45, (15, 30)),
 "quiz_v1_cz_pt_y60eur":          ("CZ paid trial €0.99",  "paid trial", 7, 45, (15, 30)),
 "quiz_v1_ro_pt_y60eur":          ("RO+MD paid trial €0.99","paid trial", 7, 45, (15, 30)),
}

# funnel slug -> list of (category, lo€, hi€). A paid charge is labelled by the first band it falls in.
BANDS = {
 "quiz_v1_jp_ft_11800yen-60-eur": [("annual", 55, 70), ("upsell AI Coach (¥3,699)", 16, 26), ("upsell Workbook/Infographic (¥1,899)", 7, 14)],
 "quiz_v1_jp_ft_14800yen-80-eur": [("annual", 72, 92), ("upsell AI Coach (¥3,699)", 16, 26), ("upsell Workbook/Infographic (¥1,899)", 7, 14)],
 "quiz_v1_gr_nt_m10_y50eur":      [("yearly plan", 45, 55), ("upsell AI Coach (€19.99)", 16, 26), ("monthly plan / PDF upsell (€9.99 — same price)", 8, 13)],
 "quiz_v1_ro_nt_m10_y50eur":      [("yearly plan", 33, 42), ("upsell AI Coach (RON 99)", 16, 26), ("upsell Workbook/Infographic (RON 49)", 8.5, 11), ("monthly plan", 6, 8.5)],
 "quiz_v1_pt2":                   [("annual", 55, 70), ("paid trial", 3, 5), ("upsell AI Coach (€19.99)", 16, 26), ("upsell Workbook/Infographic (€9.99)", 7, 14)],
 "quiz_v1_ft":                    [("annual", 45, 70), ("upsell AI Coach (€19.99)", 16, 26), ("upsell Workbook/Infographic (€9.99)", 7, 14)],
 "quiz_v1_cz_pt_y60eur":          [("annual", 55, 70), ("paid trial €0.99", 0.5, 2), ("upsell AI Coach (€19.99)", 16, 26), ("upsell PDF (€9.99)", 7, 14)],
 "quiz_v1_ro_pt_y60eur":          [("annual", 55, 70), ("paid trial €0.99", 0.5, 2), ("upsell AI Coach (€19.99)", 16, 26), ("upsell PDF (€9.99)", 7, 14)],
}

def classify(ff, amt):
    for cat, lo, hi in BANDS.get(ff, []):
        if lo <= amt < hi:
            return cat
    return "other"

def num(s):
    return pd.to_numeric(s.astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')
