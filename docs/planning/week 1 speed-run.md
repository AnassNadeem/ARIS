Friday (May 8) — Day 1 catchup, ~7–8 hrs

  Morning block (3 hrs) — unblock everything

1. (15 min) Verify the local repo is wired up.
  git status                  # if "not a git repo", run: git init
  git remote -v               # should point to github.com/AnassNadeem/aris
2. If no remote: gh repo create AnassNadeem/aris --public --source=. --remote=origin --push. MIT license, public.
3. (30 min) Send the WhatsApp to Brunel Racing. Use the exact text from §4 of ARIS-FINAL-PLAN.md. Do not apologise for being "4 days   
  late" — they don't know your internal timeline. If the contact name/role is still missing, send it generically to whoever you have. The
   message asks for nothing urgent; the value is starting the relationship now so they remember you in August.
4. (45 min) GitHub profile cleanup.
- Edit github.com/AnassNadeem/AnassNadeem profile README — paste the template from ARIS-EXECUTION-PLAN.md §D (lines 74–88).
- Purge any NeuroSim references.
- Pin: aris (placeholder for now) + your 2 strongest hackathon repos.
- Profile photo, location "London, UK", one-line bio.
5. (60 min) Tooling sweep — install only what's missing. Run each --version check. Install only the failing ones:
  python --version            # need 3.11.x
  uv --version
  git --version
  gh --version
  docker --version
  nvidia-smi                  # must show RTX 5070
  nvcc --version              # CUDA 12.x
  ollama --version
6. Skip MATLAB, DBeaver, OBS, DaVinci — those are Phase 4.7 / Phase 7 problems.
7. (30 min) Pull Llama 3.1 8B and test it.
  ollama pull llama3.1:8b-instruct-q5_K_M
  ollama run llama3.1:8b-instruct-q5_K_M "Explain F1 tire degradation in one sentence."
8. If response takes >15s or VRAM is tight, fall back to llama3.2:3b. Document the choice in LOG.md.

  Afternoon block (3 hrs) — first commits

1. (45 min) Repo scaffold. Write the real README (one-line pitch + ARIS-as-summary blurb from §1d), .gitignore (Python + fastf1_cache/

- .venv/ + data/raw/ + *.parquet), and LOG.md with one bullet:

- 2026-05-08: Day 1. Tooling installed, profile cleaned, WhatsApp sent, repo scaffolded.

1. Commit: chore: scaffold repo + initial README + LOG.
2. (30 min) Free-tier accounts — bare minimum. Sign into the ones you'll use in Weeks 1–4: Streamlit Community Cloud (GitHub login),   
  Neon.tech (note connection string in a password manager, not the repo), Hugging Face. Skip Coursera/MathWorks/Medium until you actually
   need them in Phase 4.7 / Phase 6.
3. (90 min) Python refresh — sprint, not course. You said you "know Python a bit." Don't sit through CS50P Week 0–4 — that's 10 hours  
  and overkill. Instead:
- Skim Real Python — Python OOP basics (https://realpython.com/python3-object-oriented-programming/) (~45 min)
- Watch Corey Schafer — OOP series, videos 1–3 only (https://www.youtube.com/playlist?list=PL-osiE80TeTt2d9bfVyTiXJA-UTHn6WwU) at    
  1.5× (~45 min)
- Goal: write a class with __init__, methods, properties, __repr__ without looking it up. The Phase 0 deliverable test.
- Commit one file learning/01-classes-refresher.py with a small Driver or Lap class as evidence.

  Evening block (~1 hr) — kick off the long-running stuff

1. (30 min) Pre-warm FastF1 cache overnight. Critical — Saturday/Sunday work depends on this:
  uv venv
  .\.venv\Scripts\Activate.ps1
  uv pip install fastf1
2. Then write scripts/prewarm_cache.py that loops over 8 sessions (2024 Bahrain, Saudi, Australia, Japan, Miami + 2023 Bahrain, Spa,   
  Abu Dhabi, all 'R') calling fastf1.get_session(...).load(). Run it before bed; it'll be done by morning. Commit the script.
3. (15 min) Reserve the Rajamani book online. Brunel library catalogue, request Vehicle Dynamics and Control. You don't need it until 
  Wk5 but it's popular and there's a queue.
4. (15 min) Update LOG.md with the day's bullets, push everything.

---

  Saturday (May 9) — NumPy + pandas + repo polish, ~6 hrs

  Morning (2.5 hrs) — NumPy

1. (15 min) Verify FastF1 cache populated overnight. ls fastf1_cache/ should have several MB. If it failed (rate-limit, network), kick 
  it off again now while you do NumPy.
2. (2 hrs) NumPy refresher. Skip the playlist — go fast:
- NumPy quickstart (https://numpy.org/doc/stable/user/quickstart.html) — read end to end (~30 min)
- Then DO, don't watch: open notebooks/00-numpy-basics.ipynb, work through array creation, slicing, broadcasting, vectorised math,   
  np.where, np.linalg basics. Commit when done.

  Afternoon (2.5 hrs) — Pandas

1. (2 hrs) James Powell "Pandas From The Ground Up" — first half only at 1.5×. Skip his deeper sections; you only need DataFrame,      
  Series, groupby, merge, apply, datetime indexing.
2. (45 min) Kaggle Pandas micro-course Lessons 1–3 (the rest is repetition). Commit the exercises into learning/02-pandas-kaggle.ipynb.

  Evening (1 hr) — repo hygiene

1. (30 min) Project skeleton commit — create empty src/aris/{physics,models,eval}/__init__.py, tests/__init__.py, a stub pyproject.toml
   with project metadata. This is the structure Phase 1+ will fill. One commit: chore: project skeleton.
2. (30 min) LOG.md daily entry, push, take Saturday evening off. You've earned it.

---

  Sunday (May 10) — FastF1 first pull, ~4–5 hrs (lighter day)

  Morning (3 hrs) — the actual deliverable

1. (2.5 hrs) Notebook notebooks/01-fastf1-first-pull.ipynb.
- Load Bahrain 2024 R from cache.
- Plot Verstappen's lap times vs lap number (line plot, matplotlib).
- Plot all-driver lap-time scatter, color-coded by team.
- Save the Verstappen plot to docs/screenshots/01-verstappen-bahrain-2024.png.
- Commit: feat: first FastF1 pull + Verstappen lap-time plot.
2. (30 min) README hero. Embed that PNG in the README under a "First signal" section. The repo is no longer empty — anyone landing on  
  it sees a real chart within 10 seconds.

  Afternoon (1.5 hrs) — close out Week 1

1. (45 min) Stretch deliverable: stint analysis stub. Notebook 02-stint-analysis.ipynb — group laps by Driver + Stint, plot a
  tire-stint timeline for Bahrain 2024. This is technically a Week 2 Day 4–6 task; pulling it forward gives Week 2 breathing room for the
   harder pandas joins. If you're tired, defer.
2. (30 min) LinkedIn profile sync. Match your GitHub bio. Add "Building ARIS" to the headline. Don't post yet — you post in Phase 1    
  (Wk4) when there's a live URL.
3. (15 min) Final LOG.md entry, push everything, write a WEEK-1-DONE.md self-report. One paragraph: what shipped, what slipped, what's 
  the Monday Week 2 first task. This is your handoff to future-you.

---

  Things you do NOT do this weekend

- CS50P or Boot.dev cover-to-cover. You said you know Python; trust that. Use the deliverable test (the class with **init** +
  properties + a groupby+merge) as the bar.
- Set up Postgres, Docker, Streamlit projects. That's all Week 3+.
- Read Rajamani. That's Wk5.
- MATLAB, Simulink, conformal calibration, residual MLP. Months away.
- Polish the demo video, write blog posts, publish anything. Wk7+ output.
- Borrow more deeply into the deep-research docs / synthesis. The plan is locked. Reading the plan is not progress.

  Week 1 "done" checklist (verify Sunday night)

- Local repo wired to GitHub, ≥6 commits across 3 days
- WhatsApp sent
- GitHub profile NeuroSim-free, ARIS-aligned
- Tooling: Python 3.11, uv, gh, Docker, NVIDIA driver, CUDA, Ollama, Llama 3.1 8B (or 3.2 3B fallback) — all --version/run verified    
- FastF1 cache warmed (≥5 races)
- One real plot committed (docs/screenshots/01-*.png) and embedded in README
- LOG.md with 3 daily entries
- You can write a Python class + do a pandas groupby+merge from memory
- Rajamani reservation placed at Brunel library

  If 7 of 9 are checked Sunday night, you're back on pace. Don't rewrite the plan to make slipped items "Week 2 stretch goals" — be  
  honest in LOG.md about what slipped, and start Week 2 Monday on the real Phase 1 work.

  Want me to draft the actual files (README pitch, .gitignore, prewarm_cache.py, LOG.md template, the OOP refresher class) so Friday  
  morning is mostly running commands rather than writing prose?/