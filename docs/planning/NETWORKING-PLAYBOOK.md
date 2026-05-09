# NETWORKING PLAYBOOK — From "I have nothing yet" to "I shipped it"

**The question this document answers:** *"What am I going to say to them? I'm building this and currently doing CS50p?"*

That fear is wrong but understandable. **You don't need a finished product to message people.** What you need is a clear, specific, low-friction reason for them to reply. Most CS undergrads don't message anyone because they think they have to wait until they're "ready." They're never ready. You'll start now.

This document gives you exact scripts for each stage of the build — including the stage you're in right now, where you have a plan and a half-finished CS50p and nothing else.

---

## The Three Stages

| Stage | Window | Cred you have | What you lead with |
|---|---|---|---|
| **1. Pre-cred** | Wk 1–4 (May 4 – May 31) | A plan, daily commits, CS50p in progress | The *thinking* and the *commitment* |
| **2. Mid-build** | Wk 5–14 (Jun 1 – Aug 9) | Live Streamlit URL + ~80 commits + first chart with real numbers | The *artifact in motion* — public URL |
| **3. Post-ship** | Wk 15+ (Aug 10 onwards) | v1.0 tag, demo video, backtest report, blog posts | The *shipped product* |

You message different audiences differently in each stage. The biggest mistake is using a Stage 3 script in Stage 1 ("here's my project") — you don't have a project yet, so it sounds delusional. Use the right script for where you actually are.

---

## Why people will reply to a CS first-year (the principle)

Most outreach fails for the same reason: it's about *what the sender wants*, not *what makes the recipient's day easier*. "I'd love to connect" is asking for time without offering anything. **The reply rate on those is 2–5%.**

Replies happen when one of three things is true:
1. **You're specific about what you've built or are building** — they can immediately tell if it's interesting (most of your peers are vague).
2. **You're asking a precise, answerable question** — replying takes them <2 minutes, not 20.
3. **You've engaged with something they specifically did** — read their paper, used their open-source repo, watched their conference talk. They're flattered.

Every script in this document hits at least one of these three. Most hit two.

---

## STAGE 1 — Pre-cred (Wk 1–4)

**Your reality:** You don't have a demo. You have CS50p in progress, a plan, and a public GitHub repo with mostly setup commits. **Don't lie about being further along — interviewers will check.** Lead with the *plan* and the *direction of travel*.

### What you CAN credibly say in Stage 1

- *"I'm starting Year 2 in September and building [specific project] over the summer."*
- *"I've planned out a 17-week build, here's the architecture I'm working toward."*
- *"I'm currently working through CS50p and starting on FastF1 / pandas."*
- *"My GitHub is here — daily commits from May 4 onwards."*

### What you should NOT say in Stage 1

- ❌ "I built ARIS" (you didn't, you're about to start)
- ❌ "I'm an ML engineer" (you're not, you're a CS first-year)
- ❌ "I'd love to connect" (no specific reason, no question — unactionable)
- ❌ Long pitches about what ARIS *will* be (sounds delusional from a Y1 with no shipped code)

---

### Script 1A — Brunel CS alumnus at a target company (the warmest path)

**Audience:** Anyone with "Brunel University London" + "Computer Science" on their LinkedIn who now works at a placement-relevant company. Search LinkedIn: `"Brunel" "Computer Science"` filtered by company.

**Why this works:** Shared university makes you 5–10× more likely to get a reply than a cold message. Most Brunel alumni at decent firms get one or two messages a year from current students; they remember being you, and they have a soft spot for the ask if it's specific.

**The message** (LinkedIn DM, sent with a connection request):

> Hi [Name] — fellow Brunel CS here, currently finishing first year. I noticed you're at [Company] working on [specific thing — found on their profile/posts]. I'm starting a summer build of an F1 race-strategy tool (always-on FastF1 ingest + lightweight physics + ML residual + LLM narration) targeting placement applications in September.
>
> One quick question if you have a minute: when you applied to [Company] from Brunel, what did the screening process look like? I'm trying to calibrate how much DSA prep vs project depth to weight before I sit my OAs.
>
> No worries if you're slammed — happy to share what I build either way.
>
> [Your name]

**Why each line is there:**
- "Fellow Brunel CS" → the warmth hook (they'll read on)
- "I noticed you're at [Company] working on [thing]" → proof you actually looked at their profile, not spam
- The build description → specific, technical, shows you can already speak the language
- "One quick question" → the ask is bounded, easy to reply to
- The actual question → answerable in one paragraph; not "how do I get a job"
- "No worries if you're slammed" → low pressure
- "Happy to share what I build" → offers them something (vicarious interest in your project)

**Send 3 of these per week from Wk 1.** Track in `MASTER-PLANNER.xlsx` Networking sheet.

---

### Script 1B — Engineer at an F1 team (LinkedIn, no shared connection)

**Audience:** Engineers with public profiles at Williams, McLaren, Mercedes, RB, Aston Martin, Alpine, Haas, M-Sport. Filter by job title "Software Engineer," "Race Engineer," "Vehicle Performance," "Strategy."

**Reality check:** Reply rate here is much lower than to Brunel alumni — maybe 5–15%. Don't take silence personally. Volume matters.

**The message:**

> Hi [Name] — I'm a CS undergrad in London building a hobby F1 race-strategy tool over the summer (FastF1 + a small physics + ML predictor with conformal-calibrated intervals).
>
> I'm not looking for a job — I'm a year off applications. I'm trying to scope what's realistic for a single-author summer build. Quick question if you have a moment: in your experience, what's the gap between an academic lap-time predictor and what's actually useful in a strategy room? I'd rather build the right thing than chase ML metrics that don't matter operationally.
>
> Either way — appreciate the work you do, especially [specific recent thing they posted / talk they gave / paper they wrote, if anything].
>
> [Your name]

**Why this works:**
- "I'm not looking for a job" → defuses the recruiter fatigue. They get DMs from juniors angling for jobs constantly.
- The technical detail (conformal intervals, single-track physics) → shows you're not a hype-merchant.
- The question → genuinely interesting to a working strategy engineer; cheap to answer.
- The closing engagement (specific reference) → only include if you genuinely have one.

**Send 2 per week from Wk 2 onwards.** Don't send if you can't credibly cite something specific about them.

---

### Script 1C — Brunel Racing (WhatsApp, only-once outreach)

**This is the single message described in `ARIS-FINAL-PLAN.md`.** Send it Wk 5, Day 1 of Phase 3, right after you commit the leakage tripwire. Why then: by then you have *something* — a live URL, a chart, a real commit graph. Sending in Wk 1 with nothing is too early.

**The message** (WhatsApp / Brunel Racing's official contact channel):

> Hi — I'm [Name], CS first-year at Brunel. I've been building an F1 race-strategy analysis tool over the summer and wanted to reach out before the door fully closes.
>
> Live demo (running on FastF1 right now): [public Streamlit URL]
>
> One example output: [attach the per-stint lap-time chart with the conformal intervals]
>
> What I'd love to ask: if there's any chance of getting a slice of test-day telemetry (even one session, anonymised, even rough CSV format), I think there's a real chance of a useful artefact for the team — predicted vs actual lap times with calibrated uncertainty, undercut/overcut sensitivity, that kind of thing. I'd share everything back, no strings.
>
> If timing or data-policy doesn't work, no worries at all. Either way — good luck with the season.
>
> [Your name] | [GitHub URL]

**Critical rules for this one:**
1. **Send once.** One polite follow-up at Day 14 if no reply. After that, stop. The plan must succeed without them.
2. **The live URL must work** when they click it. Test before sending.
3. **The chart must be real** — pulled from a real FastF1 race, with real numbers. No mock data.
4. **Do NOT chase past the one follow-up.** Hard kill date in your plan is Wk 7. Pivot story to "validated on held-out FastF1 races" and move on.

---

### Script 1D — Cold email to a small motorsport tech company

**Audience:** Cosworth, McLaren Applied, Pi Innovo, Ricardo, AB Dynamics, IPG Automotive, dSPACE, MathWorks (motorsport accounts), Catapult Sports (race analytics). Smaller companies than the F1 teams; reply rates are 2–5× higher.

**The email** (NOT LinkedIn — find an actual email; use Hunter.io free tier or company contact pages):

> Subject: CS undergrad — quick question on F1 strategy tooling
>
> Hi [Name],
>
> I'm a CS undergrad at Brunel, building an open-source F1 race-strategy analysis tool over the summer (FastF1-based, hybrid physics + ML, conformal-calibrated). My GitHub: [URL].
>
> I'm reaching out because [Company] does work in [specific technical area I researched]. I'd be very interested to know if your team takes summer placement applications, and if so what stack/skill set you weight most.
>
> I'm not asking for a referral — just trying to scope my year-2 application list intelligently. Two-line answer would be huge if you have a moment.
>
> Best,
> [Your name]
> [GitHub URL] · [LinkedIn URL]

**Why this works for cold email:** Most companies' careers pages are useless for CS-undergrad placement intel. A two-line email to a real engineer often gets a more useful answer than five hours of careers-page research.

---

### Script 1E — When a recruiter reaches out to you (inbound)

This will start happening once your GitHub is active, even at Stage 1. Reply to *every* recruiter, even if the role doesn't match, even if you're not interested. Recruiters move firms; the relationship compounds.

**Reply template:**

> Hi [Name] — thanks for reaching out, appreciate it.
>
> Quick context: I'm a Brunel CS first-year, looking specifically at *Year 2 → placement year* applications opening this September. So I'm not currently available for a junior/grad role, but I'd be very interested in placement opportunities at [their company / similar firms] for the 2027/28 academic year.
>
> If [their company] runs a placement scheme, I'd love a heads-up when applications open. If not, no worries — happy to stay in touch for grad-scheme conversations later.
>
> Either way: my current build is [one-line ARIS pitch + GitHub link]. Always open to chat with engineers there if it's useful.
>
> Best,
> [Your name]

---

## STAGE 2 — Mid-build (Wk 5–14)

**Your reality:** You have a live Streamlit URL. ~80–150 commits. First real charts with real data. You can show *something working*. The conversation shifts from "I'm planning" to "I'm doing — here's the link."

The one structural change vs Stage 1 is that **every message now leads with the URL.** People click links. They don't click GitHub repos as readily as they click a deployed `*.streamlit.app` URL — that's the asymmetric leverage of having shipped to a public address.

### Script 2A — The "build update" cold message

> Hi [Name] — fellow Brunel CS [if applicable] / saw your work on [thing] [if not].
>
> Mid-summer update: I've been building an F1 strategy tool — currently live at [streamlit URL]. Works on real FastF1 data, predictor MAE is around [your real number]s on held-out races, conformal intervals coming in next week.
>
> Two questions if you have a minute:
> 1. [Specific technical question about a decision you're wrestling with]
> 2. When did [their company] last open placement apps for CS undergrads?
>
> No worries if you're heads-down — happy to share the writeup when it's done.
>
> [Your name]

The key shift: you have a *real number* now. Use it. Numbers are credibility — vague claims are noise.

### Script 2B — Reply-bait LinkedIn post (Wk 7 LinkedIn post #3 specifically)

A *public post* you make on LinkedIn that's designed for engineers at target companies to discover (via mutual connections, hashtags, or shared interest). This isn't a DM — it's a post.

**Structure:**

> Three weeks ago I committed a leakage tripwire test as the first line of code in my F1 lap-time predictor. Today the model hit [X]s MAE on held-out 2024 races. Without the tripwire I'd have hit 0.3s — and been lying to myself.
>
> [chart image]
>
> Race-by-race CV is the only fair split for this problem. Per-lap CV trains on the race you're predicting; the model just memorises pace.
>
> Next: conformal-calibrated 90% intervals — because a point estimate alone is useless to a strategy engineer. *"This driver will lap 1:32.4"* is a worse answer than *"1:32.4 ± 0.5s with 90% confidence."*
>
> Tool is live: [streamlit URL]. Repo: [GitHub URL].
>
> #f1 #machinelearning #racingdata

**Why this works:**
- It's a *technical insight*, not "look what I built" — engineers pass insights along.
- It signals you understand a non-trivial ML failure mode (leakage).
- The chart gives the post visual weight in the LinkedIn feed.
- The links are at the bottom — readers who clicked through have already self-qualified as interested.

LinkedIn posts compound in a way DMs don't. One good post = up to 100 quiet readers. Most won't reply, but several will check your GitHub. Some of those will be at target companies.

### Script 2C — Twitter/X engagement (a different game)

X is *not* for cold DMs. It's for *replying to public threads* with substantive technical comments. The pattern:

1. Follow ~30 accounts: F1 engineers, FastF1 maintainers, motorsport ML researchers, F1 strategy commentators (Bernie Collins, Mark Hughes, Will Buxton, Tom Clarkson, etc.), the FastF1 / OpenF1 / TUMFTM accounts.
2. When one posts something technical you have a *real* opinion on, reply with substance — not "great post."
3. Examples of substantive replies:
   - "This — and the conformal interval coverage drops to 75% on Monaco specifically because the lap distribution has heavy left tails. Working on it."
   - "We saw similar in [TUMFTM repo / paper]. Their fix was [specific thing]. Whether it generalises depends on [specific factor]."
4. Link to your build *only when directly relevant* — never as a tagline.

**Outcome:** You become recognisable to ~5–15 people in the F1-ML niche over a few months. That's a different category of "warm" than LinkedIn alum cold DMs. Some of these people work at F1 teams.

---

## STAGE 3 — Post-ship (Wk 15+)

**Your reality:** v1.0 shipped. 90-second demo video. Backtest report. Two blog posts. HF Space.

The framing shifts from "look at what I'm doing" to "here's what I built — and here's what's next." You're now leading with a finished artefact.

### Script 3A — The placement application cover letter / cold email

Length: 6 short paragraphs. Sent to careers@ or to a specific named contact. Embedded with your CV.

> Subject: Placement application — [Role title] — [Your name]
>
> Hi [hiring manager name if known, else "team"],
>
> I'm applying for the [exact role title] placement starting [year]. I'm a CS undergraduate at Brunel University London, finishing my second year next summer.
>
> Over the last 17 weeks I built ARIS, an always-on F1 race-strategy analysis tool: live FastF1 ingest, hybrid physics + ML lap-time predictor with conformal-calibrated 90% intervals (MAE [X]s on held-out 2024 races), counterfactual strategy simulator, and a local Llama 3.1 narration layer. The MATLAB/Simulink port of the bicycle physics module is in a separate validation repo.
>
> Two-minute demo: [video URL]
> Live tool: [streamlit URL]
> Repo: [GitHub URL]
> Strategy backtest report: [docs/strategy-backtest.md URL — 1 page]
>
> I'm applying because the work [their team] does on [specific named project / vehicle / paper / public talk] is exactly what I'd want to spend a placement year contributing to. [One-sentence specific connection between ARIS and what they do.]
>
> CV attached. Available for first-stage interview from [date] onwards.
>
> Best,
> [Your name]

**The placement-application cover letter is a different document than your CV.** It's the human story; the CV is the structured data. Don't repeat your CV in prose — use the cover letter to demonstrate that you understand *what they specifically do*, and that you can connect *what you've built* to *what they need*.

---

## Follow-up cadence (rules)

**The 7/14/30 rule:**
- **Day 0:** Initial message.
- **Day 7:** No follow-up. They saw it. They're busy. Don't be the third "just bumping this" message in their inbox.
- **Day 14:** *One* polite follow-up — only if there's a *new* reason to message (a new chart, a new milestone, the URL is now live, etc.). Never just "hi did you see this?"
- **Day 30:** Move on. Don't message again unless they message you first or the situation materially changes.

**Example Day-14 follow-up that is acceptable:**

> Hi [Name] — the conformal calibration I mentioned shipped this week, here's the coverage curve [image]. Empirical 88% vs nominal 90%, which I'm pretty happy with. No expectation of reply, just wanted to close the loop on the question I asked you.

**Example Day-14 follow-up that is NOT acceptable:**

> Hi just wanted to bump this in case you missed it!

The first reads as a builder closing a loop. The second reads as someone who needs validation.

---

## What to do if they don't reply (decision tree)

1. **Did they read it?** LinkedIn shows "Seen" status. If seen + no reply: they consciously chose not to reply. Move on.
2. **Was it a Brunel alum?** If yes and they didn't reply: don't take it personally. About 50% of Brunel alumni won't reply to anything from a current student because of inbox volume. Try a different alumnus next week.
3. **Did your message have all three of: specificity, low-friction question, recent reference to their work?** If not, your message is the problem. Rewrite the template before sending more.
4. **Have you sent fewer than 30 messages?** If yes: keep sending. The base rate is 10–20% reply for warm-cold messages. You need volume.
5. **Have you sent more than 60 messages with <5 replies?** Your script is broken. Stop, audit, rewrite. Don't burn through the warm pool with bad messages.

---

## Anti-patterns — never send any of these

- ❌ "I'd love to connect and learn more about [Company]." — There's nothing to reply to. The recipient has to do all the work.
- ❌ "Are you hiring?" — Of course they don't know off the top of their head. The careers page exists.
- ❌ "Can you review my CV?" — Asking for 30 minutes of unpaid work from a stranger.
- ❌ "I'm passionate about [topic]" without evidence. — The evidence *is* your build. Show it; don't claim it.
- ❌ Multi-paragraph life story before the ask. — They need the ask in the first 3 lines or they bounce.
- ❌ Apologising before asking ("Sorry to bother you but…"). — Confidence is a signal; pre-emptive apology is a counter-signal.
- ❌ "Just following up on my last message" three times in a row. — Annoying, never works.
- ❌ Sending the same script verbatim to 20 people on LinkedIn. — They will spot the copy-paste, especially when their colleagues mention they got the same one.

---

## Brunel-specific tactics (your warmest path)

These should be your first port of call. The reply rate from Brunel alumni is roughly 4× the rate from cold strangers, and many Brunel CS grads are at target companies — Williams, McLaren, JP Morgan, Bloomberg, Stripe, Goldman, plenty of fintechs.

### LinkedIn search syntax to find them

In LinkedIn search:
1. Filter by School: "Brunel University London"
2. Filter by Industry: "Software Development" / "Motor Vehicle Manufacturing"
3. Filter by current company: rotate through your target list (Williams, McLaren, etc.)
4. Sort by 2nd-degree connections first if available

For each, check:
- Did they study CS specifically (vs other engineering)? If yes, your message is even warmer.
- How long ago did they graduate? Aim for 3–10 years out — recent enough to remember Brunel, senior enough to actually answer questions.
- Are they active on LinkedIn (any post in the last year)? If not, your DM probably won't get seen.

### Brunel Careers Service

This is genuinely useful and underused. They have:
- A 1:1 booking system (book your first slot in May, listed as a Phase 8 deliverable in `ARIS-PHASES-WEEKLY-PLAN.md`)
- Past placement reports from previous Brunel CS students (read them — they show what gets people in)
- Direct contacts at firms that have hired Brunel students before
- CV review (use after Wk 16 CV rewrite, not before — let them critique the polished version)

### Brunel Racing (Formula Student team)

Already covered in Script 1C. The single biggest constraint: **send once, follow up once, then move on.** It's an upside dimension, not a load-bearing dependency.

---

## What you'll actually do this week (Wk 1, May 4–10)

If you read this whole document and don't act, it's worthless. So:

1. **Today/tomorrow:** Open LinkedIn. Search "Brunel University London" + "Computer Science" filtered by McLaren, Williams, Bloomberg, JP Morgan. Find 5 alumni who graduated 3–10 years ago. Save them in `MASTER-PLANNER.xlsx` Networking sheet.
2. **By Friday:** Send Script 1A to 3 of them. Spread across Tue/Wed/Thu (don't fire all 3 the same day).
3. **Sunday review:** Did anyone reply? If so, reply within 24 hours. If not, send Script 1A to the other 2 next week, and add 3 more to the pipeline.

Set the cadence: **3 outreach messages / week from Wk 1, ramping to 5/week from Wk 8.** That's 60+ messages by Wk 16. Even at a 15% reply rate, that's 9 conversations — and each conversation that goes well gives you a soft introduction, a referral, or a much better understanding of what placement applications actually look at.

The goal isn't to find a job in May. The goal is to have *warm* conversations going *before* applications open in September, so that when the placement DM arrives, you're not a cold name in their inbox — you're "the Brunel CS one building the F1 thing."

That's the entire game.
