---
id: compound-slopes-aris
source: ARIS physical prior — docs/how-recommend-works.md; data/tracks/netherlands.yaml compound_slopes
url: docs/how-recommend-works.md
---
# Compound behaviour in ARIS (general)

Shipped ARIS tyre slopes are a physical prior, not a Pirelli datasheet: SOFT 0.08, MEDIUM 0.05, HARD 0.03 seconds per lap of tyre age. Softer is assumed to fall off faster. Fitted C-code overlays exist in the repo but are off unless opted in. FastF1 does not supply C1–C6; when a fitter was re-keyed onto true C-codes the slopes were still not ordered C1 < C2 < … C5. These numbers are model priors used by recommend()/simulate(), not FIA regulations and not a claim that lap-time fits identified C1 vs C5.
