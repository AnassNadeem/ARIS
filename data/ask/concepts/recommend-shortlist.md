---
id: recommend-shortlist
source: ARIS recommender menu — docs/how-recommend-works.md
url: docs/how-recommend-works.md
---
# What recommend() scores

ARIS does not search every legal strategy. It scores a fixed shortlist: stay out; pit now for the default next compound (usually HARD); pit in 1, 2, 3, 5, or 8 laps for SOFT/MEDIUM/HARD (SOFT skipped when fewer than 15 laps remain); two two-stop sketches (MEDIUM then HARD; SOFT then HARD) if those laps are still ahead; and lift or brake earlier into turns 1, 7, and 10. There is no opponent “cover” tree. Score is seconds vs stay-out (negative = faster). Stay-out is always kept on the top-three list.
