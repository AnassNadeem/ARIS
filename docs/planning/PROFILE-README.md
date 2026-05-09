# Hi, I'm Muhammad Anas Nadeem 👋
**BSc Computer Science (AI) @ Brunel University London**

> Currently building **[ARIS](https://github.com/AnassNadeem/ARIS)** — an always-on race-strategy system that watches live F1 telemetry, predicts the next decision, and proposes it with a quantified lap-time delta and a calibrated confidence interval.

---

### 🏎️ Current Focus: ARIS

**A hybrid AI race strategist — physics + machine learning + LLM narration.**

*Most student F1 projects either fit a black-box model to lap times or build a "world model" they can't actually train. ARIS does neither. The core is a hand-coded vehicle-dynamics simulator (bicycle model + tire-degradation curve + fuel-burn + pit-loss) corrected by a machine-learning residual trained on FastF1 data. An action-search engine evaluates dozens of candidate driver and strategy actions per tick, scores them with Monte Carlo confidence intervals, and a local LLM turns the top recommendation into a sentence. It runs always-on against a live race replay, validated end-to-end on held-out races with conformal prediction intervals.*

**It is not a world model and not reinforcement learning** — it is classical decision support stitched together with modern ML and LLMs, which is what real F1 strategy software actually looks like.

**The Roadmap:**
*   **Phase 1 — Foundations:** FastF1 ingest, Postgres, Streamlit dashboard, public URL.
*   **Phase 2 — Predictor:** bicycle model + tire degradation + residual ML, race-by-race CV, conformal intervals.
*   **Phase 3 — Counterfactuals + always-on loop:** perturbation engine + tiered tick architecture.
*   **Phase 4 — Narration + eval:** local LLM narrator, conformal calibration, strategy-language backtest, 90-second demo.

**The Stack:** Python · NumPy/Pandas · scikit-learn · XGBoost · PyTorch · FastF1 · Postgres · Streamlit · Ollama (Llama 3.1 8B) · MATLAB/Simulink · CUDA 12.x (RTX 5070)

📍 **[Execution plan](https://github.com/AnassNadeem/ARIS/blob/main/ARIS-EXECUTION-PLAN.md)** · 🪵 **[Build log](https://github.com/AnassNadeem/ARIS/blob/main/BUILD-LOG.md)** · 🏁 **[Follow the build](https://github.com/AnassNadeem/ARIS)**

---

### 🛠️ Selected Work & Hackathons

*   🏥 **[Patient Continuity in Crisis Zones](https://www.linkedin.com/feed/update/urn:li:activity:7398763440254898176/)** *(Imperial College Crisis Zones Hackathon)*
    Built a centralized hospital system for conflict regions. Implemented biometric matching via face-to-vector embeddings (no raw image storage) and an offline-first architecture with local caching for unstable networks.
*   🛡️ **[AssertionOS](https://github.com/alvisk/encode-spoonOS)** *(Encode × SpoonOS Hackathon)*
    Developed an AI-powered multi-chain wallet security agent providing real-time threat detection for DeFi.

---

### 💼 Experience

*   **Student Leader @ Electech Lab** *(Jan – Mar 2026)*
    Taught logic, robotics, and coding fundamentals to primary-school students using Tinkercad and Code Monkey in-person at St Andrews C of E Primary School.
*   **PHP Intern @ Tally Marks Consulting** *(Jul – Aug 2024)*
    Optimized database operations and authored complex SQL queries for enterprise data management systems.

---

### 💻 Tech Stack

| Category | Technologies |
| :--- | :--- |
| **Languages** | Python, Java, C, SQL |
| **AI & Compute** | PyTorch, scikit-learn, XGBoost, NumPy, Pandas, CUDA |
| **Data & Infra** | PostgreSQL, FastF1, Streamlit, Docker |
| **LLM & Sim** | Ollama (Llama 3.1 8B), MATLAB / Simulink |
| **Tools** | Git, GitHub Actions, VS Code |

---

### 📫 Let's Connect
**[LinkedIn](https://linkedin.com/in/MuhammadAnasNadeem)** | 📧 **[anass.nadeem42@gmail.com](mailto:anass.nadeem42@gmail.com)**
