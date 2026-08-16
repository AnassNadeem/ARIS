---
id: pit-loss-aris
source: ARIS track YAML circuit constant — data/tracks/netherlands.yaml and docs/how-recommend-works.md
url: data/tracks/netherlands.yaml
---
# Pit-loss mechanics in ARIS

A pit in simulate() adds the circuit pit-loss once and resets tyre life to 1 on the new compound. Pit loss is a measured track constant, not an FIA time penalty. For Zandvoort / Netherlands the shipped YAML value is pit_loss_s=18.5 (multi-year median 2021–2025; per-year values in the YAML source block include 2024=19.5 and 2025=16.4). docs/how-recommend-works.md describes this as “the circuit pit-loss” of about 18 s: a pit with few laps left rarely pays that cost back. Do not treat 18.5 s as a sporting-regulation number.
