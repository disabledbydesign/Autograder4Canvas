# Autograder4Canvas

**Ethics-first pedagogical infrastructure for community college instructors.**

A tool for reading your class — not scoring it. Autograder4Canvas reads student submissions to surface what students are reaching for and why that might be interesting: the intellectual moves they're making, the connections they're drawing to personal and community experience, the places they're pushing back or recentering dominant frames. It also surfaces classwide patterns — emergent themes, tensions and dialectics between students, and dynamics that are only visible when you read the whole class together (one student saying "I don't see race" reads differently alongside classmates describing how race shaped their families).

The goal is to give teachers a richer picture of where students are intellectually before walking into the room — not to produce grades or verdicts. Built for complete/incomplete and contract grading, turning assignments into launching points for classroom discussion. Runs locally on instructor hardware — student work and analysis stay on the teacher's own machine. (FERPA compliance ultimately depends on how the instructor and institution handle the data; the architecture is built to keep it local.)

---

## Why This Exists

I built Autograder4Canvas while teaching as one of two full-time Ethnic Studies faculty at a California community college, carrying 175–200 students per semester — with enrollment climbing toward 250 as the state's Ethnic Studies transfer requirement (AB 1460, the law making Ethnic Studies a CSU graduation prerequisite) drove every CSU-bound student through our department. I left that position in April 2026; the tool was built under those conditions and is shared here for other instructors who may face them.

The requirement changed what it meant to teach the course. Where enrollment had been self-selecting — students who chose Ethnic Studies and arrived committed — the mandate meant every transfer-track student came through regardless of starting point. In the current political climate, that means students who are actively hostile toward marginalized communities sit in the same room as the students those views target — and are told to discuss race, identity, and power as a condition of graduating. As a transgender professor of Ethnic Studies, I was not outside these dynamics — I was in them alongside my students, navigating the same hostility the course material was designed to examine. I built Autograder4Canvas to solve real problems that emerged from teaching in these conditions at this scale.

The tool grew in stages:

**Stage 1 — Automation.** A script that pulled assignments from Canvas and assessed word counts — a limited proxy for engagement, but defensible when set conservatively: low enough to mean more than bare compliance, high enough that students who didn't engage meaningfully didn't receive credit. This freed hours per week from administrative grading.

**Stage 2 — Integrity analysis.** I added academic integrity detection, but almost immediately ran into a tension I couldn't engineer around: as an Ethnic Studies professor with abolitionist commitments, I was building a surveillance tool for the very students my discipline exists to advocate for. I didn't want to police students in an Ethnic Studies course. But I also couldn't ignore students who were genuinely abusing the system — submitting AI-generated text or recycled work while classmates put in real intellectual effort. That ambivalence drove the design: the tool had to surface patterns for teacher review without acting as judge, and it had to do so without reproducing the demographic biases I was discovering in the signals — ESL students, AAVE speakers, neurodivergent writers, and first-generation students triggered false positives at rates that made the tool a liability unless bias was addressed structurally.

**Stage 3 — Design infrastructure.** The tension between abolitionism and accountability forced a deeper question: how do you build detection tools that don't reproduce the sorting systems Ethnic Studies exists to critique? I designed a system that used an LLM to simulate an assembly of specialists across critical theory — critical race theory, disability studies, abolitionist pedagogy, feminist technoscience — to pressure-test every design decision. One of those assembled voices was an abolitionist, and it became clear almost immediately that the framework I'd built was far too powerful to spend on catching cheating. That system became [Reframe](https://github.com/disabledbydesign/Reframe), a general-purpose critical theory engine that now shapes the design of everything in this project.

**Stage 4 — Insights.** The system I'd built to detect disengagement patterns became the seed for something more ambitious: qualitative insight generation at scale. The design problem is significant — how do you get a local model running on an instructor's laptop to produce the kind of layered, contextual reading of student work that a human reader would, across 200 submissions per assignment? The answer required both architectural innovation and engineering discipline. The pipeline decomposes the cognitive work into 10+ discrete stages: a full-class reading pass that sees students as a community in conversation before any individual analysis; per-student coding for themes, quotes, and emotional register; a separate wellbeing assessment on raw text; generative observations that describe what the model notices rather than classify what it judges; theme generation; outlier surfacing; and a class-level synthesis narrative. Each stage asks the model a single focused question, grounding the next pass and preventing the hallucination and nuance-flattening that plague multi-step LLM pipelines. The entire pipeline runs on a 12B parameter model (Gemma) on a 16GB MacBook — no cloud, no GPU cluster, no institutional server.

An early version of this system surfaced a patterned uptick in disengagement signals across all my regular-semester sections in Week 6. In the spring 2026 political climate, I was paying close attention to student wellbeing, and I read those signals as consistent with burnout rather than cheating. I gave the class a week off with instructions to focus on self-care and community connection, then assigned readings from the Ethnic Studies literature on collective care.

### What this enables

The intended use is contract or complete/incomplete grading where assignments are inputs to teaching rather than endpoints. Students submit; the system reads the class as a whole and surfaces what individual students are reaching for; the instructor walks into the next class session knowing where the room is. The grade is a byproduct of completing the work; the analytical reading is what the next class session can respond to.

Two practical consequences for the people in the room. Students aren't being scored on output, so the pressure shifts to process — what they're working through, what they're trying. Instructors don't have to approximate a student's intellectual trajectory with a quantitative figure, because the system gives them qualitative observations about each student and patterns across the class.

The engineering and the pedagogy come together rather than separately. Reading students as knowledge creators rather than as scoring targets is the design commitment; making that legible at the scale of 200 submissions is the engineering problem. Running locally on a laptop instead of on cloud infrastructure is what makes the tool usable for an instructor with no IT department or budget. Reducing false-positive integrity flags on ESL, AAVE, neurodivergent, and first-generation student writing is what makes it safe to use at the scale where it's needed.

### In development / on the roadmap

These are works-in-progress, not shipped features. They are described here because the design choices are part of the project's argument, not because they are ready to deploy.

**Agent-assisted inbox (in development).** A Canvas message workflow that goes beyond draft generation toward a command center for instructor communication at scale. The backend in `src/inbox/` is partially built — it currently handles fetching unread Canvas conversations, SQLite persistence, context assembly with temporal decay across semesters, and TF-IDF retrieval over prior responses, exposed through a CLI (`fetch`, `context`, `send`, `log`, `skip`, `flag`). The roadmap pieces — diagnosing Canvas issues (unpublished modules, broken submissions), executing bulk admin actions, posting course-wide announcements from the same surface, and grouping similar messages for systematic response — are not yet implemented. The intended design is a fixed action menu with deterministic execution: the LLM suggests, the instructor approves, Python acts.

**Overnight grading automation (built, not currently deployed).** A scheduling layer (`src/automation/`, `src/gui/scheduler.py`) that can run autograding overnight via macOS launchd, Windows Task Scheduler, or systemd, applying Complete/Incomplete grading with configurable thresholds. The code is in the repo and was used in production during my teaching, but I am not currently running it — I left Cabrillo in April 2026 and disabled the cron on my own machine. Other instructors can set it up via `setup_automation.sh` and the in-app scheduler.

---

## Features

### Desktop GUI
Custom retro-futurist amber terminal interface (PySide6/Qt6) with:
- Course browser with semester grouping, modality badges, and ungraded-assignment counts
- Assignment timeline view with deadline grouping (Past | This Week | Upcoming)
- Layered results viewer for grading outcomes, integrity analysis, and insights
- Configurable font-scale accessibility (0.75x–2.0x)
- All Canvas API calls and LLM analysis run in background worker threads

### Insights Engine
Two-phase analytical pipeline that reads student submissions for pedagogical insight — running locally on instructor hardware via Ollama or Apple MLX, or against an OpenAI-compatible/Anthropic API if the instructor configures one. Submissions and intermediate analytical artifacts are persisted to a local SQLite database on the instructor's own machine for crash-resumability and longitudinal review. With Ollama or MLX selected, nothing is sent off the machine; with a remote API selected, prompts and submission text reach that provider — instructors choose the backend with that tradeoff in mind. The model's job is not to assess whether students got the content right. It's to figure out what a student is reaching for and why that might be interesting. This distinction matters especially for courses like Ethnic Studies and Native American Studies, where the concern that AI models lack historical or political knowledge is well-founded — but also beside the point, because the system isn't checking facts. It's reading moves.

The pipeline surfaces three things: what individual students are doing intellectually (theme tags, notable verbatim quotes, emotional register, concepts applied, personal and community knowledge being used as intellectual resource); what the class is doing collectively (emergent themes, tensions and dialectics between students, power moves like recentering or re-normalization of dominant perspectives that silence marginalized voices); and who may need a check-in (burnout signals, disengagement, truncated submissions). Burnout and academic dishonesty correlate strongly — surfacing the former is often more useful than trying to detect the latter directly.

The architecture is designed around a set of commitments about how student work should be read:

**Community reading, not individual surveillance.** The pipeline runs a full class reading *before* per-student coding. Students are read as a community in conversation — what they're reaching for, where they connect, where they disagree — because relational harms like tone policing or essentializing are only visible in context. A student writing "I don't see race" reads differently alone than alongside classmates describing how race shaped their families.

**Reader-not-judge architecture.** The LLM reads first as a human reader would — open prose, no JSON, no rubric — then a second pass extracts structured fields grounded in what the model actually noticed. The prose pass is what the structured pass references, so the model has to read before it can extract (rather than slot-filling preset categories without engaging the content). The system generates *observations*, not verdicts. Teachers read what the model noticed and decide what warrants action.

**Structured data preserves nuance.** Every pipeline stage produces Pydantic-validated structured data, never free-form prose synthesis. Each coding record captures theme tags, notable quotes (always verbatim — teachers hear student voice, not model paraphrase), emotional register, concepts applied, and lens observations. A student cannot be reduced to an engagement score. Theme confidence scores preserve uncertainty rather than hiding it.

**Political urgency is not distress.** Concern detection is always a dedicated, separately-scoped LLM call — never bundled with coding. The prompts instruct the model to treat anger about injustice, engagement with assigned material about trauma, analytical disclosure of disability, and passionate language about justice as legitimate intellectual moves rather than distress signals. A post-processing layer pattern-matches the model's output for tone-policing language, demotes flags whose justification language matches structural-critique patterns, and surfaces a teacher-visible warning when the post-processor detects a likely-bias pattern. The post-processor is heuristic, not exhaustive.

**Asset-based framing encoded in prompts.** Every prompt reframes deficit language: "engagement signals" not "concern levels," "what the student is reaching for" not "what they failed to articulate." Non-standard English, AAVE, multilingual syntax, and neurodivergent writing styles are treated as valid academic registers — assets, not deficits.

**Decomposed cognition for small models.** The 12B-on-16GB pipeline decomposes the reading work into stages a smaller model can handle reliably — comprehension, interpretation, concerns — each asking a single cognitive skill. Each pass grounds the next. The design choice is to produce structured readings useful to teachers, runnable on instructor hardware with no cloud dependency, instead of one-shot frontier-model output that depends on cloud infrastructure most instructors don't have. Runs take time (roughly 2–4 minutes per student); the pipeline is crash-resumable and designed to run overnight.

**The pipeline:**
- **Phase 1 — Quick Analysis (instant, no LLM required):** Word frequency, VADER sentiment, embedding-based clustering, submission statistics, and pattern-based signal detection. Available in seconds.
- **Phase 2 — LLM Analysis (background):** Class reading → per-submission coding (theme tags, emotional register, notable quotes) → emergent theme generation → outlier surfacing → class-level synthesis narrative → draft student feedback. All intermediary results persisted to SQLite for crash-resumability.
- **Longitudinal Trajectories:** Per-student semester arcs tracking intellectual growth, theme evolution, and engagement patterns — framed around what students *built*, not what they lack. Variable output is described, never pathologized.
- **Subject-Area Lenses:** Pre-built analysis templates for Ethnic Studies, STEM, humanities, and more — each with equity-aware prompt fragments and custom strength patterns.
- **Teacher Profile Learning:** Theme renames, sensitivity adjustments, and coding corrections accumulate into a persistent profile that shapes future runs. The teacher is always the final authority.

### Multilingual & Multimodal Submissions
Full preprocessing pipeline so students can submit in any language or medium:
- Audio transcription via faster-whisper (CTranslate2)
- Multilingual translation via Ollama (70+ languages, langdetect)
- PDF and DOCX text extraction
- Image-to-text OCR

### Academic Integrity Analysis
Population-aware pattern detection designed as **a conversation starter, not a verdict.**
- Linguistic pattern analysis with externalized, YAML-configurable markers
- Cohort-calibrated baselines (class-relative, not absolute thresholds)
- Two-axis bias calibration (see [Research](#research) below)
- Context-aware adjustments for ESL, first-generation, neurodivergent, and working students
- Requires informed consent before running; makes detection biases visible

### Grading Automation
- Complete/Incomplete grading with configurable word-count thresholds
- Discussion forum grading (posts and replies)
- Bulk runs across multiple courses and assignments
- Optional scheduled automation via macOS launchd, Windows Task Scheduler, or systemd (set up by the instructor; not enabled by default)

---

## Download

**No Python or technical setup required.** Just download and run.

**[Download the latest release](https://github.com/disabledbydesign/Autograder4Canvas/releases/latest)**

| Platform | File |
|----------|------|
| macOS    | `Autograder4Canvas-Mac.dmg` |
| Windows  | `Autograder4Canvas-Windows.zip` |
| Linux    | `Autograder4Canvas-Linux.tar.gz` |

### Installation

**macOS:**
1. Download `Autograder4Canvas-Mac.dmg`
2. Open the DMG and drag the app to your Applications folder
3. Right-click the app and select "Open" (first time only, to bypass Gatekeeper)

**Windows:**
1. Download `Autograder4Canvas-Windows.zip` and extract it
2. Run `Autograder4Canvas.exe`
3. If Windows SmartScreen appears, click "More info" → "Run anyway" (the app is not code-signed)

**Linux:**
1. Download `Autograder4Canvas-Linux.tar.gz`
2. Extract: `tar -xzf Autograder4Canvas-Linux.tar.gz`
3. Run the `Autograder4Canvas` executable inside

---

## Quick Start

1. **Get your Canvas API token:** Log into Canvas → Account → Settings → New Access Token

2. **Launch Autograder4Canvas** — on first run, enter your Canvas URL and API token in the setup dialog (or explore with built-in demo data)

3. **Select a course** from the semester-grouped sidebar, then **select assignments** from the timeline view

4. **Run an analysis:**
   - **Quick Run** — grade or analyze a single assignment
   - **Bulk Run** — batch process multiple courses and assignments
   - **Insights** — launch the two-phase pedagogical analysis pipeline

5. **Review results** in the layered results viewer — grading outcomes, integrity analysis, and insights are all accessible from the Review tab

---

## Research

### Output Format as the Activation Function for Bias

This project includes original research producing significant findings on how LLM output structure activates structural bias in academic integrity detection.

**The core finding:** Binary classification formats (FLAG/CLEAR) produce systematically disparate false positive rates on minoritized students. The same model, with the same data, switched from classification to generative observation, eliminates the disparity entirely. This is not about the model's knowledge, the prompt, or training data — it's the output structure itself.

**Evidence:**
- Tested across 6+ model families (Gemma, Llama, Qwen, Gemini, DeepSeek)
- 32-student synthetic corpus with controlled demographic patterns (ESL, AAVE, neurodivergent writing, righteous anger, burnout)
- 43% of incorrectly flagged students had explanations that *argued against the flag* — the model wrote "passion is understandable and appropriate," then flagged the student anyway
- Observation-only architecture: 7/7 correct readings where the classifier produced 3 false positives on protected students
- Replication across 5 runs: 100% true positive detection, 0% false positive rate on protected students (45 checks)

**Key insights:**
1. **LLMs identify bias patterns but reproduce them anyway** — classification task overrides conceptual understanding
2. **Output format determines epistemological frame** — JSON-first produces deficit framing; reading-first produces asset framing
3. **Class context improves generation but worsens classification** — models use richer context to find *more* things to flag
4. **Self-contradiction reveals bias structure** — the flag and the explanation disagree, exposing the classificatory mechanism
5. **Generative tasks produce more equitable outputs than classificatory tasks** — across all comparisons

These findings inform the two-axis bias calibration system built into the tool:
- **CohortCalibrator** — class-relative engagement baselines with Bayesian cold-start blending and exponential moving average evolution across assignments
- **WeightComposer** — composes effective detection weights from education-level profiles × population overlays (ESL/multilingual, first-generation, neurodivergent). Per-student overrides always resolve to the more protective setting.

Theory grounding: Ruha Benjamin (*Race After Technology*), Bowker & Star (*Sorting Things Out*), Eve Tuck ("Suspending Damage"), Bonilla-Silva (*Racism without Racists*).

Research documents are in [`docs/research/`](docs/research/).

---

## Core Values

- **Student dignity & agency** — Students are knowledge creators, not potential cheaters
- **Educational equity** — Calibrated for ESL, first-gen, neurodivergent, and working students
- **Data sovereignty** — Processes locally on the instructor's own machine; nothing is sent to a cloud service. Submissions and analysis are persisted to a local SQLite database for crash-resumability and longitudinal review, under the instructor's control
- **Transparency** — Human judgment over algorithmic "accuracy"; detection biases made visible
- **Bias as architecture** — Per-institution and per-population calibration is built into the system, not bolted on

---

## Tech Stack

**GUI:** PySide6 (Qt6)  
**LLM Backends:** Ollama (local), Apple MLX, OpenAI-compatible APIs  
**NLP & ML:** sentence-transformers, scikit-learn, VADER Sentiment, textstat, langdetect  
**Audio:** faster-whisper (CTranslate2)  
**Data:** SQLite, Pydantic, pandas, NumPy  
**Documents:** pdfminer.six, python-docx, Pillow  
**Canvas Integration:** REST API (requests)  
**Distribution:** PyInstaller (macOS .dmg, Windows .exe, Linux .tar.gz)  

## Requirements

- Canvas LMS account with API access
- Internet connection for Canvas API calls
- For Insights Engine: [Ollama](https://ollama.com) (recommended) or Apple Silicon Mac with MLX
- Python 3.7+ (bundled in pre-built apps)

## Building from Source

```bash
git clone https://github.com/disabledbydesign/Autograder4Canvas.git
cd Autograder4Canvas
pip install -e .
```

## Documentation

- [User Guide](src/docs/USER_GUIDE.md) — Detailed usage instructions
- [Automation Guide](AUTOMATION_README.md) — Set up automated grading workflows
- [Academic Integrity Check](Academic_Dishonety_check_README.txt) — Ethical considerations and usage
- [Research Tracks Architecture](docs/research/research_tracks_architecture.md) — Bias calibration research design
- [April 2026 Live Data Findings](docs/research/findings_from_live_data_run_2026-04-27.md) — Empirical results from a live classroom run

## Support

For questions or issues, please [open an issue](https://github.com/disabledbydesign/Autograder4Canvas/issues) on GitHub.

## License

GNU GPL v3 — See LICENSE file for details.

## Credits

Built by a community college Ethnic Studies instructor (2024–2026) for educators teaching humanities and social sciences, particularly at Hispanic Serving Institutions.
