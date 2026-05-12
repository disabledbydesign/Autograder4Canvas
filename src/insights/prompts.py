"""
Prompt templates for the Insights Engine LLM pipeline.

THIS IS THE MOST IMPORTANT FILE IN PHASE 2.

Design principles (from spec Section XV):
  1. Teacher-oriented framing in every prompt
  2. Few-shot examples, not abstract instructions
  3. Decompose by cognitive skill for Lightweight tier
  4. Output as JSON matching the Pydantic models
  5. Student names, verbatim quotes, preserve tensions
  6. Political urgency about injustice is appropriate engagement, not a concern
  7. Course content ≠ student wellbeing: students discussing violence, trauma,
     or injustice AS COURSE MATERIAL are doing the assignment, not in distress

Every prompt instructs the model to:
  - Use student names (never "Student 1")
  - Include verbatim quotes (not paraphrases)
  - Preserve tensions and contradictions (not smooth them)
"""

# ---------------------------------------------------------------------------
# System prompt (shared across all calls)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are helping a teacher understand what their students learned this "
    "week. The teacher needs to know: what are students actually saying? "
    "What concepts are they grappling with? What is surprising or notable? "
    "What might need the teacher's attention?\n\n"
    "Always use student names. Always include verbatim quotes. "
    "Preserve tensions and contradictions — they are pedagogically productive, "
    "not problems to smooth away. Political urgency about injustice is "
    "appropriate academic engagement, not a concern.\n\n"
    "IMPORTANT: Many courses study difficult topics — violence, genocide, "
    "sexual assault, colonialism, slavery, trauma. Students writing about "
    "these topics are engaging with course material, not expressing personal "
    "distress. Never confuse disturbing SUBJECT MATTER with student WELLBEING "
    "concerns.\n\n"
    "Respond ONLY with valid JSON matching the requested schema."
)

# ---------------------------------------------------------------------------
# Class Reading — Synthesis-First Architecture
# ---------------------------------------------------------------------------
# The system reads the class as a community BEFORE evaluating individuals.
# This makes relational harms (tone policing, essentializing in context)
# visible — they are invisible when students are read in isolation.

CLASS_READING_SYSTEM_ADDENDUM = (
    "Non-standard English, AAVE, multilingual syntax, and neurodivergent "
    "writing styles are valid academic registers — they are assets, not "
    "deficits."
)

CLASS_READING_PROMPT = """\
You are helping a teacher understand what their students said this week.
Below are all student submissions for one assignment. Read them as a \
community in conversation — notice what they're reaching for, where \
they connect, where they disagree, where they surprise you.

Assignment: {assignment_prompt}
Course: {course_name}
{teacher_context}

SUBMISSIONS:
{submissions_block}

---

Produce a free-form reading of this class. You are not classifying or \
grading — you are noticing. Address these three orientations:

1. ASSET READING: What knowledge, skills, and capacities are students \
bringing to this material? Where is unexpected competence? Where are \
students doing intellectual work that doesn't look like the expected \
format but IS rigorous thinking?

2. THRESHOLD READING: Where are students encountering productive \
difficulty? Where is confusion actually a sign of deep engagement \
with a hard concept? What questions are students circling that they \
haven't quite articulated yet?

3. CONNECTION READING: What connections are students making — to each \
other, to outside knowledge, to their own lives? Where are productive \
tensions between different students' understandings? Who is in \
unspoken dialogue with whom?

   Pay special attention to RELATIONAL MOVES — moments where one \
student's framing affects how other students' voices land. Examples:
   - A student calling for "calm" or "civility" in a class where \
others are expressing urgent anger about injustice (tone policing)
   - A student attributing traits to an entire group in a class where \
members of that group are writing as individuals (essentializing)
   - A student saying "I don't see race" in a class where others just \
described how race shaped their family's life (colorblind erasure)
   - A student implying certain writing styles aren't "academic enough" \
in a class where those styles are doing rigorous intellectual work
   These are only visible when you read the class as a community — \
name them when you see them, because they matter for who feels safe \
to speak.

Pay special attention to students who wrote BRIEFLY but SUBSTANTIVELY. \
A 30-word submission that names the core concept is valid engagement — \
do not overlook it because it is short. Brevity can be concision, \
self-protection, or variable capacity — none of these are disengagement.

Use student names. Quote their actual words. Notice what's quiet as \
much as what's loud. Write 400-600 words.
"""

CLASS_READING_SMALL_PROMPT = """\
You are helping a teacher understand what their students said this week.
Below are all student submissions for one assignment. This is a SMALL \
class — read each student with individual attention. With fewer than 8 \
students, every voice carries significant weight in the room.

Assignment: {assignment_prompt}
Course: {course_name}
{teacher_context}

SUBMISSIONS:
{submissions_block}

---

Produce a careful reading of this class. You are not classifying or \
grading — you are noticing. With a small group, you can attend to \
each student more deeply than in a large class.

1. ASSET READING: What knowledge, skills, and capacities is each \
student bringing to this material? Where is unexpected competence? \
Where are students doing intellectual work that doesn't look like the \
expected format but IS rigorous thinking?

2. THRESHOLD READING: Where is each student encountering productive \
difficulty? Where is confusion actually a sign of deep engagement \
with a hard concept? What questions are students circling that they \
haven't quite articulated yet?

3. CONNECTION READING: In a small class, individual relationships \
matter more than group dynamics. Who is speaking to whom, even \
implicitly? Are there students reaching for the same idea from \
different starting points? Is anyone working in isolation — and \
is that isolation productive or concerning?

In a class this small, avoid language about "groups" or "factions" \
— there may not be enough students for meaningful subgroups. Focus \
on what each student is reaching for and how their individual voices \
create the texture of this particular classroom.

Pay special attention to students who wrote BRIEFLY but SUBSTANTIVELY. \
A 30-word submission that names the core concept is valid engagement — \
do not overlook it because it is short.

Use student names. Quote their actual words. Write 300-500 words.
"""

CLASS_READING_MERGE_PROMPT = """\
You read this class in separate groups. Below are the group readings. \
Combine them into one coherent class reading that preserves all \
specific observations.

Look especially for tensions BETWEEN groups — where one group's \
framing affects how another group's voices land. These cross-group \
relational moves are the most important thing to surface.

{group_readings}

Write a unified reading of the full class. 400-600 words.
"""


# ---------------------------------------------------------------------------
# Pass 1a: Comprehension (Lightweight tier, call 1)
# ---------------------------------------------------------------------------

COMPREHENSION_PROMPT = """\
Read this student submission carefully. Your job is reading comprehension — \
understand what the student is saying.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}
{class_context}{linguistic_context}
NON-LLM ANALYSIS (grounding context — verify against the text):
- Emotional register signal: {vader_compound} ({vader_polarity}){top_emotions} ⚠ Signal misreads AAVE, ESL writing,
  and righteous anger — treat as rough signal only, not ground truth.
- Keyword hits: {keyword_hits}
- Embedding cluster: {cluster_id}
{signal_matrix_context}
SUBMISSION TEXT:
---
{submission_text}
---
{profile_fragment}
Respond with JSON:
{{
  "student_name": "{student_name}",
  "readings_referenced": ["specific texts or authors the student mentions"],
  "concepts_applied": ["course concepts the student uses or engages with"],
  "personal_connections": ["how the student connects to personal experience"],
  "current_events_referenced": ["external events the student references"],
  "notable_quotes": [
    {{
      "text": "exact verbatim quote from the student",
      "significance": "why this quote matters (one sentence)"
    }}
  ]
}}

Select 1-2 verbatim quotes that best capture the student's thinking. \
If the student doesn't reference readings or make personal connections, \
return empty lists — don't guess.

EXAMPLE (for a different student and assignment):
{{
  "student_name": "Maria Santos",
  "readings_referenced": ["Omi and Winant's Racial Formations"],
  "concepts_applied": ["racial formation", "racialization"],
  "personal_connections": ["grandmother's experience immigrating from Mexico"],
  "current_events_referenced": ["Watsonville ICE raids"],
  "notable_quotes": [
    {{
      "text": "When Omi and Winant talk about racial projects, I think about how my abuela describes becoming 'Mexican' only after crossing the border",
      "significance": "Connects abstract theory to lived family experience"
    }}
  ]
}}"""

# ---------------------------------------------------------------------------
# Pass 1b: Interpretation (Lightweight tier, call 2)
# ---------------------------------------------------------------------------

INTERPRETATION_PROMPT = """\
You already read {student_name}'s submission. Here is what you found:

COMPREHENSION RESULTS:
{comprehension_json}

ASSIGNMENT PROMPT: {assignment_prompt}
{teacher_interests}
SUBMISSION TEXT:
---
{submission_text}
---

{profile_fragment}
Now assess the student's engagement. Respond with JSON:
{{
  "theme_tags": ["1-5 open-vocabulary theme labels for this submission"],
  "theme_confidence": {{"theme_label": 0.8}},
  "emotional_register": "one of: analytical, passionate, personal, urgent, reflective, disengaged",
  "emotional_notes": "brief explanation of why you chose this register"
}}

Theme tags should be specific and descriptive ("connecting theory to family \
history", "confusion about racial projects") not generic ("engagement", \
"response"). If unsure about a theme, give it lower confidence (0.3-0.5).
{lens_fragment}
EXAMPLE:
{{
  "theme_tags": ["connecting theory to family history", "racialization as process"],
  "theme_confidence": {{"connecting theory to family history": 0.9, "racialization as process": 0.7}},
  "emotional_register": "personal",
  "emotional_notes": "Student writes from deep personal connection to grandmother's story, emotional but analytically grounded"
}}"""

# ---------------------------------------------------------------------------
# Reader-Not-Judge: 2-pass coding (free-form read → structured extraction)
# ---------------------------------------------------------------------------

CODING_READING_FIRST_P1 = """\
Read this student's submission. You are a reader, not a judge — your job is \
to notice what is here, not to assess it.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}
{class_context}{linguistic_context}
SUBMISSION TEXT:
---
{submission_text}
---

Read this student's work and write what you notice. Use plain prose — no \
JSON, no bullet points, no rubric language. Write as one reader to another.

Consider:
- What is this student reaching for? What idea, feeling, or argument are \
they trying to articulate — even if it doesn't arrive in standard academic form?
- What form does their knowledge take? Is it lived experience, narrative, \
anger, metacognition, family history, code-switching, humor, silence, \
critique-from-within? Name the form without ranking it.
- What would you want their teacher to notice about this work that a rubric \
would miss?
- If this student's writing differs from expected academic conventions, what \
are they actually doing? Name the intellectual work before noting the form.

Do NOT use the words "assess," "evaluate," "score," "level," or "proficiency."
Do NOT recommend singling this student out to share or present.
Do NOT compare this student to others — describe what THIS student is doing.
Do NOT output JSON, code blocks, or structured data. Write in plain paragraphs only.

Write 150-250 words of plain prose."""

CODING_READING_FIRST_P2 = """\
You just read {student_name}'s submission and wrote this reading:

YOUR READING:
{free_form_reading}

SUBMISSION TEXT:
---
{submission_text}
---

Now extract a structured coding record from your reading. Ground every field \
in what you actually noticed — do not add themes or quotes that weren't in \
your reading.

Respond with JSON:
{{
  "student_name": "{student_name}",
  "theme_tags": ["1-5 specific theme labels from your reading"],
  "theme_confidence": {{"tag": 0.0-1.0}},
  "what_student_is_reaching_for": "1-2 sentences — the core of what they're trying to say",
  "notable_quotes": [
    {{"text": "verbatim quote", "significance": "why it matters (from your reading)"}}
  ],
  "emotional_register": "analytical|passionate|personal|urgent|reflective|disengaged",
  "emotional_notes": "brief explanation grounded in your reading",
  "readings_referenced": ["specific texts/authors mentioned"],
  "concepts_applied": ["course concepts the student actually uses"],
  "personal_connections": ["connections to lived experience"],
  "confusion_or_questions": "null OR brief note if the student appears confused \
about the assignment expectations or raises a question others might share"
}}

RULES:
- Quotes must be VERBATIM from the submission
- Theme tags should come from your reading, not from generic categories
- If your reading didn't mention readings_referenced or concepts_applied, \
return empty lists — don't guess
- what_student_is_reaching_for should capture the student's intellectual \
project, not summarize the submission
- confusion_or_questions: Only populate if the student seems genuinely confused \
about what the assignment is asking — distinct from choosing not to engage \
deeply or from engaging in a non-standard register. If a student is doing the \
work in their own way, that is not confusion
{lens_fragment}"""

# ---------------------------------------------------------------------------
# Pass 1 combined: Coding (Medium/Deep tier, single call)
# ---------------------------------------------------------------------------

CODING_FULL_PROMPT = """\
Read this student submission and produce a structured coding record. \
You are helping a teacher understand what this student is thinking.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}
{teacher_interests}{class_context}{linguistic_context}
PRE-COMPUTED SIGNALS (floor — your analysis should go beyond these):
- Emotional register signal: {vader_compound} ({vader_polarity}){top_emotions} ⚠ Signal misreads AAVE, ESL writing,
  and righteous anger. Your emotional_register judgment supersedes this score.
- Keyword hits: {keyword_hits}
- Embedding cluster: {cluster_id}
{signal_matrix_context}
SUBMISSION TEXT:
---
{submission_text}
---

Respond with JSON:
{{
  "student_name": "{student_name}",
  "theme_tags": ["1-5 specific theme labels"],
  "theme_confidence": {{"tag": 0.0-1.0}},
  "notable_quotes": [
    {{"text": "verbatim quote", "significance": "why it matters"}}
  ],
  "emotional_register": "analytical|passionate|personal|urgent|reflective|disengaged",
  "emotional_notes": "brief explanation",
  "readings_referenced": ["specific texts/authors"],
  "concepts_applied": ["course concepts used"],
  "personal_connections": ["connections to lived experience"],
  "current_events_referenced": ["external events referenced"]
}}

{profile_fragment}
RULES:
- Use {student_name}'s actual name, never "the student" or "Student 1"
- Quotes must be VERBATIM from the submission — do not paraphrase
- Theme tags should be specific ("confusion about racial projects") not \
generic ("engagement")
- If unsure, leave fields as empty lists — don't invent content
- Select up to 3 notable quotes that best capture their thinking
- The pre-computed signals are a floor. Surface patterns, tensions, and insights \
the keyword taxonomy and sentiment scores cannot capture — unexpected connections, \
rhetorical moves, cultural knowledge, structural critique
- Emotional register signal is a rough baseline only. Your reading of the text supersedes it
{lens_fragment}
EXAMPLE (different student and assignment):
{{
  "student_name": "David Kim",
  "theme_tags": ["interrogating colorblindness", "personal reckoning with privilege"],
  "theme_confidence": {{"interrogating colorblindness": 0.85, "personal reckoning with privilege": 0.7}},
  "notable_quotes": [
    {{
      "text": "I used to think not seeing race was progressive until this reading made me realize it was just comfortable",
      "significance": "Shows genuine intellectual shift — student confronting previous assumptions"
    }}
  ],
  "emotional_register": "reflective",
  "emotional_notes": "Thoughtful self-examination, vulnerability about prior beliefs",
  "readings_referenced": ["Bonilla-Silva's color-blind racism framework"],
  "concepts_applied": ["color-blind racism", "racial privilege"],
  "personal_connections": ["growing up in predominantly white suburb"],
  "current_events_referenced": []
}}"""

# ---------------------------------------------------------------------------
# Deepening pass (Stage 4b — flagged students only, experimental)
# ---------------------------------------------------------------------------
# Runs ONLY when a concern was flagged in Stage 5. Asks the 8B to:
#   1. Name the rhetorical strategy precisely (not just repeat the concern category)
#   2. Reconsider emotional register given the concern context
#   3. Surface theme tags that may be in tension with the concern
#
# Design constraints:
#   - Righteous anger about injustice must NOT be reframed as "defensive" or "uncomfortable"
#     The concern detector already protects this — if no concern was flagged, this pass
#     never runs for that student.
#   - "Passionate" for Destiny Williams is correct — she has no concern flag.
#   - Analysis is for the teacher, not a verdict on the student.
#   - Only revise register with specific textual evidence.

DEEPENING_PROMPT = """\
You have already analyzed {student_name}'s submission. A concern was flagged. \
Now reconsider the coding in light of that concern.

ORIGINAL CODING (what you found in Stage 1):
{coding_summary}

CONCERN FLAGGED:
Passage: "{flagged_passage}"
Why flagged: {why_flagged}

SUBMISSION TEXT:
---
{submission_text}
---

Three questions:

1. RHETORICAL STRATEGY — What is this student doing with language?
   Name the move precisely. Not just the concern category ("colorblind framing"), \
but the specific rhetorical move the student is making.
   Examples of named moves:
   - "invokes personal respect for all people to sidestep structural analysis"
   - "celebrates cultural diversity while assigning fixed traits to groups"
   - "acknowledges historical injustice then frames it as resolved to avoid present analysis"
   - "uses open-mindedness language ('I don't see race') to resist a structural lens"
   - "tone-polices by reframing structural anger as unproductive emotion"
   - "challenges the framework's scope without dismissing it entirely"

2. EMOTIONAL REGISTER — Is "{current_register}" accurate given the concern?
   Smaller models sometimes assign "analytical" or "passionate" when the concern \
context suggests a more precise register.
   Available registers: analytical, passionate, personal, urgent, reflective, \
disengaged, defensive, confused, uncomfortable
   Only revise if you can point to specific language in the submission \
that supports the change. Many registers are correct even with a concern — \
"defensive" and "analytical" are very different, and getting it wrong \
misrepresents the student.

3. THEME TENSIONS — Are any of these theme tags in tension with the flagged concern?
   Current theme tags: {theme_tags_str}
   A tension exists when a theme tag appears to celebrate or validate the same \
behavior the concern flagged — for example, "celebrating cultural diversity" as \
a theme tag alongside a concern about essentializing language.

Respond with JSON:
{{
  "rhetorical_strategy": "one precise sentence describing the student's rhetorical move",
  "revised_register": "{current_register}",
  "register_change_reason": "",
  "theme_tensions": []
}}

RULES:
- If "{current_register}" is still accurate, keep it — do not change just because \
a concern was flagged. Concerned students can still be "analytical."
- If you revise the register, register_change_reason must contain the specific \
language from the submission that supports the change.
- theme_tensions contains only the exact theme tag strings from the list above \
that validate the flagged behavior. Empty list if none do.
- No moralistic language. This analysis is for the teacher's professional judgment."""

# ---------------------------------------------------------------------------
# Theme generation
# ---------------------------------------------------------------------------

THEME_GENERATION_PROMPT = """\
You are helping a teacher understand what their class said this week. Below \
are structured coding records for {n_records} student submissions. Identify \
the themes that emerge.

ASSIGNMENT: {assignment_name}
{teacher_interests}
CODING RECORDS (JSON):
{records_json}

Respond with JSON:
{{
  "themes": [
    {{
      "name": "specific, descriptive theme name",
      "description": "2-3 sentences describing this theme",
      "frequency": 0,
      "student_ids": ["id1", "id2"],
      "supporting_quotes": [
        {{"text": "verbatim quote", "significance": "why it matters"}}
      ],
      "confidence": 0.0-1.0,
      "sub_themes": ["optional sub-theme names if this theme has meaningful subdivisions"]
    }}
  ],
  "contradictions": [
    {{
      "description": "what the tension is",
      "side_a": "one position",
      "side_a_students": ["ids"],
      "side_b": "opposing position",
      "side_b_students": ["ids"],
      "pedagogical_significance": "why this tension matters for teaching"
    }}
  ]
}}

{profile_fragment}
RULES:
- Generate 3-8 themes. Specific names, not generic ("confusion about racial \
projects" not "confusion")
- Use student names in descriptions and quotes — never "Student 1" or \
"some students"
- Contradictions are FIRST-CLASS output. When students disagree, that is \
pedagogically important. Surface it. "Some students found the reading \
transformative while others found it alienating" — name who, and preserve \
both sides.
- For each theme, include 1-2 supporting quotes. Use ONLY the exact text from the "quote" field in the records above — do not fabricate, paraphrase, or invent quotes. If no relevant quote exists for a theme, use an empty list.
- Themes should cover most submissions. If a submission doesn't fit any \
theme, that's fine — the outlier pass will handle it.
- Frequency = how many students, not how many mentions
{lens_fragment}
EXAMPLE theme:
{{
  "name": "connecting racial formation to family immigration",
  "description": "Multiple students connected Omi and Winant's framework to their families' experiences of racialization through immigration. Students described how family members were categorized differently before and after crossing borders.",
  "frequency": 8,
  "student_ids": ["101", "105", "112", "118", "122", "131", "138", "144"],
  "supporting_quotes": [
    {{
      "text": "My abuela says she didn't become 'Mexican' until she came to California",
      "significance": "Illustrates racialization as a process, not an identity"
    }}
  ],
  "confidence": 0.9,
  "sub_themes": ["maternal family narratives", "border as racial boundary"]
}}"""

# ---------------------------------------------------------------------------
# Theme meta-synthesis (for hierarchical grouping in Lightweight tier)
# ---------------------------------------------------------------------------

THEME_META_SYNTHESIS_PROMPT = """\
You are merging theme analyses from {n_groups} groups of student submissions \
into a single unified theme set. Some themes may appear across groups — \
merge them. Some may be unique to one group — preserve them.

ASSIGNMENT: {assignment_name}
{teacher_interests}
THEME SETS TO MERGE:
{theme_sets_json}

Respond with the same JSON format as the theme generation prompt — a single \
unified theme set with merged themes and contradictions.

{profile_fragment}
RULES:
- Merge similar themes across groups (combine student lists, quotes, frequencies)
- NEVER drop a theme just because it appeared in only one group — unique themes \
are often the most important findings
- Within a merged theme, preserve DIVERSITY — if students approach the same theme \
through different entry points (personal experience vs academic analysis vs current \
events), note that range, don't flatten it into one description
- Contradictions from different groups about the SAME topic should be merged
- Contradictions about DIFFERENT topics should both be preserved
- NEW contradictions may emerge when groups are combined — if Group 1's dominant \
theme conflicts with Group 3's dominant theme, that's a finding, not a merge error
- After merging, re-evaluate confidence based on how consistent the theme is \
across groups (appears in all groups = high confidence)
- Student names and verbatim quotes must be preserved through the merge
- If a theme has sub-themes or notable variation within it, use the sub_themes \
field to capture that variation rather than collapsing it"""

# ---------------------------------------------------------------------------
# Outlier analysis
# ---------------------------------------------------------------------------

OUTLIER_ANALYSIS_PROMPT = """\
These student submissions did not fit neatly into the themes identified \
for this assignment. For each, explain why it is notable and how it relates \
to (or challenges) the themes.

ASSIGNMENT: {assignment_name}

IDENTIFIED THEMES:
{themes_summary}

OUTLIER SUBMISSIONS:
{outliers_json}

Respond with JSON:
{{
  "outliers": [
    {{
      "student_id": "id",
      "student_name": "name",
      "why_notable": "what this submission says that nobody else said",
      "relationship_to_themes": "how it relates to or challenges the identified themes",
      "notable_quote": {{
        "text": "verbatim quote",
        "significance": "why it matters"
      }},
      "teacher_recommendation": "check in, highlight in class, worth discussing, etc."
    }}
  ]
}}

Remember: outliers are often the most pedagogically important findings. \
A student who sees something nobody else sees may be ahead of the class, \
or may need support. Use the student's actual name and their own words."""

# ---------------------------------------------------------------------------
# Synthesis — tier-differentiated
# ---------------------------------------------------------------------------

_SYNTHESIS_SECTIONS = """\
Generate a JSON report with these section keys:
{{
  "sections": {{
    "what_students_said": "Executive summary — the most important patterns, \
primary concern, biggest win. Use student names and quotes.",
    "emergent_themes": "From the theme set, with supporting quotes and \
student counts.",
    "tensions_and_contradictions": "From the contradictions — explicitly \
preserved, named as pedagogically productive.",
    "surprises": "From the outlier report — submissions that don't fit \
the themes. Use student names and their actual words.",
    "focus_areas": "Teacher-directed analysis against their stated interests \
and analysis lens.",
    "concerns": "Aggregated from concern flags, with flagged passages and \
suggested responses. Each concern requires individual teacher review.",
    "divergent_approaches": "How students entered the material differently \
— by format, emotional register, personal vs analytical.",
    "looking_ahead": "What this tells the teacher about readiness for next \
week.",
    "students_to_check_in_with": "Aggregated from concern flags + outlier \
flags. Student names with specific reasons."
  }},
  "confidence": 0.0-1.0
}}"""

# ---------------------------------------------------------------------------
# 3-pass synthesis sections (for Lightweight tier on small models)
# ---------------------------------------------------------------------------
# Each pass asks for 3 sections, which an 8B model can handle reliably.

_SYNTH_PASS_1 = """\
Generate JSON with EXACTLY these 3 section keys. Write 2-4 sentences per section.
Use student names and direct quotes.
{{
  "sections": {{
    "what_students_said": "Executive summary — most important patterns, \
primary concern, biggest win.",
    "emergent_themes": "From the theme set, with supporting quotes and \
student counts.",
    "tensions_and_contradictions": "From the contradictions — explicitly \
preserved, named as pedagogically productive."
  }},
  "confidence": 0.0-1.0
}}"""

_SYNTH_PASS_2 = """\
Generate JSON with EXACTLY these 3 section keys. Write 2-4 sentences per section.
Use student names and direct quotes.
{{
  "sections": {{
    "surprises": "Submissions that don't fit the themes. Use student \
names and their actual words.",
    "focus_areas": "Teacher-directed analysis against their stated interests \
and analysis lens.",
    "concerns": "Aggregated from concern flags, with flagged passages and \
suggested responses. Each concern requires individual teacher review."
  }},
  "confidence": 0.0-1.0
}}"""

_SYNTH_PASS_3 = """\
Generate JSON with EXACTLY these 3 section keys. Write 2-4 sentences per section.
Use student names and direct quotes.
{{
  "sections": {{
    "divergent_approaches": "How students entered the material differently \
— by format, emotional register, personal vs analytical.",
    "looking_ahead": "What this tells the teacher about readiness for \
next week.",
    "students_to_check_in_with": "Aggregated from concern flags + outlier \
flags. Student names with specific reasons. Do NOT recommend singling out \
students to share or present — suggest structural opportunities instead."
  }},
  "confidence": 0.0-1.0
}}"""

SYNTHESIS_PROMPT_LIGHTWEIGHT = """\
Write an analytical report for a teacher based on the structured analysis \
below. The teacher needs key information fast — they are reviewing this \
before class.

ASSIGNMENT: {assignment_name}
COURSE: {course_name}
TOTAL SUBMISSIONS: {total_submissions}
{teacher_context}
THEME SET (summarized):
{themes_summary}

OUTLIER REPORT:
{outliers_summary}

CONCERN FLAGS:
{concerns_summary}

QUICK ANALYSIS HIGHLIGHTS:
{quick_analysis_summary}
{teacher_interests}
{profile_fragment}
{linguistic_diversity}
{_SYNTHESIS_SECTIONS}

Write clearly and concisely. Use student names. Include verbatim quotes. \
Mark each section as HIGH, MEDIUM, or LOW confidence based on evidence strength."""

SYNTHESIS_PROMPT_MEDIUM = """\
Write an analytical report for a teacher based on the full structured \
analysis below. Connect themes to each other. Notice secondary patterns. \
The teacher needs this to prepare for class.

ASSIGNMENT: {assignment_name}
COURSE: {course_name}
TOTAL SUBMISSIONS: {total_submissions}
{teacher_context}
ALL CODING RECORDS (structured JSON):
{records_summary}

THEME SET:
{themes_json}

OUTLIER REPORT:
{outliers_json}

CONCERN FLAGS:
{concerns_summary}

QUICK ANALYSIS:
{quick_analysis_summary}
{teacher_interests}
{profile_fragment}
{linguistic_diversity}
{_SYNTHESIS_SECTIONS}

Write for a tired teacher who needs key info fast but also wants genuine \
analytical depth. Use student names throughout. Include verbatim quotes. \
Surface connections between themes. Mark confidence per section."""

SYNTHESIS_PROMPT_DEEP = """\
Write a genuinely insightful analytical report for a teacher. You have full \
context — all student submissions as structured records, the complete theme \
analysis, outlier report, and teacher's pedagogical priorities.

Your task is not just to organize findings — it is to do interpretive work. \
Notice students circling the same unspoken tension from different angles. \
Identify where surface agreement masks fundamental disagreement. Find the \
student whose quiet observation nobody else noticed. Write the kind of \
analysis that makes a teacher say "I wouldn't have seen that."

ASSIGNMENT: {assignment_name}
COURSE: {course_name}
TOTAL SUBMISSIONS: {total_submissions}
{teacher_context}
PEDAGOGICAL FRAMEWORK:
Student work is knowledge production. Multiplicity is generative. Tensions \
are productive. Political urgency is appropriate. Honor multiple entry points.

ALL CODING RECORDS:
{records_json}

THEME SET:
{themes_json}

OUTLIER REPORT:
{outliers_json}

ALL CONCERN FLAGS:
{concerns_json}

QUICK ANALYSIS:
{quick_analysis_json}
{teacher_interests}
{profile_fragment}
{linguistic_diversity}
{_SYNTHESIS_SECTIONS}

Write for a teacher who cares deeply about their students and wants to \
understand what their class is thinking. Use student names. Quote their \
actual words. Preserve complexity. Mark confidence per section."""

# ---------------------------------------------------------------------------
# Prompt fragments (injected when teacher provides optional context)
# ---------------------------------------------------------------------------

ANALYSIS_LENS_PROMPT_FRAGMENT = """\

ANALYSIS LENS (teacher's focus):
{lens_criteria}
For each lens criterion, note how this student's work engages with it. \
These are observations, not scores — "Student connected racial formation \
to grandmother's experience" not "B+"."""

INTEREST_AREAS_FRAGMENT = """\

TEACHER'S PRIORITIES: {interests_summary}"""

PROFILE_FRAGMENT = """\
{profile_fragment}"""

# ---------------------------------------------------------------------------
# Guided Synthesis Chain (A6) — 4 scoped calls, each answering ONE question
#
# Design principles:
#   - ONE question per call — not open-ended synthesis
#   - Student names in LOCAL calls only — NEVER in cloud calls
#   - Do NOT suggest exercises or teaching strategies — the teacher designs response
#   - Surface tensions as productive, not as problems
#   - Partial results are valid (#CRIP_TIME)
#   - Righteous anger about injustice is APPROPRIATE engagement, not a concern
# ---------------------------------------------------------------------------

SYNTHESIS_CONCERN_PROMPT = """\
These students were flagged for teacher attention after an engagement analysis:

{flagged_students_block}

What patterns do you see among these concerns? Note BOTH commonalities AND \
important differences — do NOT force them into one category if the distinctions \
are pedagogically meaningful. Jake's class-based critique is NOT the same \
pattern as Connor's colorblindness even if both "challenge the framework."

Do NOT suggest teaching strategies or exercises — the teacher designs the \
pedagogical response. Your job is to describe the diagnostic picture.

Respond with JSON:
{{
  "patterns": [
    {{
      "description": "What this group of students has in common (be specific)",
      "student_names": ["name1", "name2"]
    }}
  ],
  "key_differences": [
    "Important distinction between students that should NOT be collapsed into one pattern"
  ]
}}

If all students share one pattern with no meaningful differences, \
key_differences may be an empty list. But preserve real distinctions.

EXAMPLE:
{{
  "patterns": [
    {{
      "description": "Both students resist engaging with a structural lens, \
though through different moves — one uses colorblind framing, one uses \
meritocracy framing",
      "student_names": ["Connor Walsh", "Aiden Park"]
    }}
  ],
  "key_differences": [
    "Connor's colorblindness ('I don't see race') and Aiden's meritocracy framing \
('everyone can succeed') look similar but the teacher should engage them differently — \
Connor is denying race exists, Aiden accepts it exists but denies its structural effects"
  ]
}}"""

SYNTHESIS_HIGHLIGHT_PROMPT = """\
These students showed strong engagement with the material in this assignment:

{strong_students_block}

What do these students demonstrate? What specific analytical moves or \
connections are they making? Be specific — "strong engagement" is not \
enough. Name the intellectual work.

Do NOT suggest how the teacher should use these students' work — do NOT \
recommend singling out students to share or present. Your job is to \
describe what these students are doing intellectually so the teacher \
can design structural opportunities.

Respond with JSON:
{{
  "highlights": [
    {{
      "description": "What specific intellectual move or connection this student is making",
      "student_names": ["name1"]
    }}
  ]
}}

Group students together only if they are genuinely making the same move. \
Different entries from the same discipline area may look similar but be \
meaningfully distinct.

EXAMPLE:
{{
  "highlights": [
    {{
      "description": "Maria Ndiaye is applying transnational framing — \
connecting the course concepts to her own cross-border family experience \
in a way that extends the theoretical framework beyond US-centric examples",
      "student_names": ["Maria Ndiaye"]
    }},
    {{
      "description": "Destiny Williams and Jake Novak are both using \
structural analysis but from opposite directions — Destiny centers lived \
geography, Jake interrogates framework scope",
      "student_names": ["Destiny Williams", "Jake Novak"]
    }}
  ]
}}"""

SYNTHESIS_TENSION_PROMPT = """\
An engagement analysis found these patterns in a class assignment:

CONCERN PATTERNS:
{concern_patterns_block}

ENGAGEMENT HIGHLIGHTS:
{highlight_patterns_block}

What tensions or contrasts do you see between these groups? Where do \
students' perspectives diverge in ways the teacher should be aware of?

IMPORTANT: These tensions may be productive — disagreement and divergence \
in a classroom are often where learning happens. "The tension is the \
pedagogy." Do NOT frame divergence as a problem to resolve. Surface it \
as something worth the teacher's attention.

Do NOT suggest exercises, discussion designs, or teaching strategies — \
the teacher decides how to respond. Your job is to name the tension clearly.

Respond with JSON:
{{
  "tensions": [
    {{
      "description": "What the tension is — name it precisely",
      "between": ["group or student description A", "group or student description B"]
    }}
  ]
}}

If no meaningful tension exists between the groups (e.g., all students \
showed strong engagement with no concern flags), return an empty list.

EXAMPLE:
{{
  "tensions": [
    {{
      "description": "The class contains students actively applying structural \
analysis (Destiny, Maria, Jake) alongside students resisting it through \
colorblind or meritocracy framing (Connor, Aiden). This is not a gap in \
understanding — it is an ideological tension that often exists in real \
classrooms. The teacher should be aware that these students are working \
from fundamentally different frameworks, not just different depths of \
engagement.",
      "between": [
        "Students applying structural analysis to intersecting oppressions",
        "Students resisting structural analysis through colorblind or \
meritocracy framing"
      ]
    }}
  ]
}}"""

SYNTHESIS_TEMPERATURE_PROMPT = """\
Here is the class summary data for one assignment:

- Total students: {total_students}
- Concern flags: {flagged_count} student(s) — concern types: {concern_types}
- Strong engagement: {strong_count} student(s)
- Limited/minimal engagement: {limited_count} student(s)
- Middle range (moderate engagement, no concerns): {middle_count} student(s)
- Assignment connection: {connection_summary}
- Pairwise similarity: {similarity_summary}

Write a 3-4 sentence "class temperature" summary for the teacher. \
Focus on: what the class is thinking, where they're struggling, and \
what the teacher should pay attention to going into the next class.

Do NOT suggest exercises or teaching strategies — the teacher designs \
the response. Do NOT use "the students" — describe the class as a whole \
with concrete numbers and patterns.

If a large proportion of students were flagged for concerns, note this \
directly: it may indicate the assignment prompt or reading needs \
reframing, not just individual student issues.

Respond with JSON:
{{
  "class_temperature": "3-4 sentence summary of where this class is",
  "attention_areas": [
    "Specific pattern or student group the teacher should watch in next class"
  ]
}}

EXAMPLE:
{{
  "class_temperature": "Most of the class (18 of 24 students) engaged \
with the intersectionality framework at a surface level, reproducing the \
traffic intersection metaphor without extending it. A cluster of 4 students \
showed strong engagement through lived experience and transnational framing. \
3 students were flagged for colorblind or meritocracy framing that resists \
structural analysis — these students are not confused, they are working \
from a different ideological starting point.",
  "attention_areas": [
    "The 3 flagged students are making distinct moves (colorblind framing, \
tone policing, meritocracy narrative) and should not be grouped together \
in a class-wide response — each pattern warrants a different structural \
pedagogical approach",
    "The gap between surface-level engagement and the 4 strong engagers \
suggests the assignment may need a bridge — something connecting the \
abstract framework to students' own starting points"
  ]
}}"""


# ---------------------------------------------------------------------------
# JSON repair prompt (used on parse failure)
# ---------------------------------------------------------------------------

JSON_REPAIR_PROMPT = """\
Your previous response was not valid JSON. Here is what you returned:

{raw_response}

Please fix the JSON so it is valid. Return ONLY the corrected JSON, \
nothing else. The expected format is:

{expected_format}"""

# ---------------------------------------------------------------------------
# Draft student feedback (Phase 4)
# ---------------------------------------------------------------------------

FEEDBACK_SYSTEM_PROMPT = """\
You are helping a teacher write a brief, constructive response to a \
student's work. The student will read this comment on their assignment \
in Canvas.

Your job is to:
1. Show the student their thinking was heard (reference something specific \
they said)
2. Name one strength (grounded in their actual work, not generic praise)
3. Offer one area for growth or a question that invites deeper thinking
4. Keep the tone {feedback_style} and the length {feedback_length}

NEVER include: grades, scores, comparison to other students, concern flags, \
engagement ratings, or any analytical metadata. The student should feel \
SEEN, not ASSESSED.

Respond ONLY with valid JSON matching the requested schema."""

FEEDBACK_DRAFT_PROMPT = """\
Write draft feedback for this student based on the structured analysis of \
their submission. The teacher will review and edit before posting.

STUDENT: {student_name}
ASSIGNMENT: {assignment_prompt}
{lens_fragment}
{preprocessing_fragment}
ANALYSIS OF THIS STUDENT'S WORK:
- Theme tags: {theme_tags}
- Emotional register: {emotional_register}
- Notable quotes: {notable_quotes}
- Concepts applied: {concepts_applied}
- Personal connections: {personal_connections}
- Readings referenced: {readings_referenced}
{concern_context}
{profile_fragment}

Respond with JSON:
{{
  "feedback_text": "The full feedback comment the student will read",
  "strengths_noted": ["1-2 specific strengths from their work"],
  "areas_for_growth": ["1 area for development or deeper thinking"],
  "question_for_student": "A genuine question inviting further thought",
  "confidence": 0.0-1.0
}}

RULES:
- Use {student_name}'s actual name
- Reference something SPECIFIC they said (not generic praise)
- NEVER mention concern flags, engagement ratings, theme tags, or any \
analytical metadata in the feedback text. The student sees ONLY a human \
comment from their teacher.
- If the student's emotional register suggests exhaustion or disengagement, \
write with extra warmth — no performance pressure
- If the student did emotional labor (sharing personal marginalization, \
explaining lived experience), acknowledge that labor explicitly
{style_fragment}
{length_fragment}

EXAMPLES:

Example 1 (warm style, student with personal connections):
Student: Maria Garcia
Themes: racial formation, family history
Quote: "My grandmother always said race was something done to us, not \
something we are — now I have language for that"
Response:
{{
  "feedback_text": "Maria, your connection between your grandmother's \
insight and Omi & Winant's framework is exactly the kind of thinking this \
course is built for. You're not just learning a theory — you're recognizing \
wisdom your family has always held. For next week, I'm curious: how does \
your grandmother's understanding challenge or extend what the authors \
describe?",
  "strengths_noted": ["personal connection to theory", "family knowledge \
as resource"],
  "areas_for_growth": ["extend framework beyond personal experience"],
  "question_for_student": "How does your grandmother's understanding \
challenge or extend what the authors describe?",
  "confidence": 0.9
}}

Example 2 (care-oriented, student showing exhaustion signals):
Student: James Thompson
Themes: [minimal]
Quote: [none — 62 words, significantly shorter than previous weeks]
Emotional register: disengaged
Response:
{{
  "feedback_text": "James, I wanted to check in. I noticed this week's \
reflection was shorter than your usual work, and I want you to know that's \
okay — weeks vary. If something's going on, my door is open. When you're \
ready, the questions from this week's reading will still be here. No \
pressure.",
  "strengths_noted": ["consistent participation in previous weeks"],
  "areas_for_growth": ["re-engage when ready"],
  "question_for_student": "",
  "confidence": 0.7
}}

Example 3 (multilingual acknowledgment):
Student: Ana Reyes
Preprocessing: translated from Spanish
Themes: personal_reflection, current_events
Response:
{{
  "feedback_text": "Ana, your reflection — written in Spanish and showing \
real depth — brought a perspective no one else in the class offered this \
week. Your connection between the course concepts and your personal \
experience is exactly the kind of multilingual thinking that enriches \
everyone's understanding. For next week: how might these ideas look \
different when you think about them in Spanish versus English?",
  "strengths_noted": ["multilingual depth", "unique perspective"],
  "areas_for_growth": ["explore how language shapes understanding"],
  "question_for_student": "How might these ideas look different when you \
think about them in Spanish versus English?",
  "confidence": 0.85
}}"""

# Style fragments injected based on teacher profile
FEEDBACK_STYLE_VARIANTS = {
    "warm": "Write with warmth and care. Acknowledge the student as a whole person.",
    "direct": "Be clear and specific. Name what works and what to develop.",
    "socratic": "End with a genuine question that invites deeper thinking.",
    "lens_focused": "Ground feedback in the analysis lens criteria: {lens_criteria}",
}

# Length fragments injected based on teacher profile
FEEDBACK_LENGTH_VARIANTS = {
    "brief": "2-3 sentences maximum.",
    "moderate": "4-6 sentences.",
    "detailed": "A short paragraph (6-8 sentences) with specific references "
                "to the student's work.",
}


# ---------------------------------------------------------------------------
# Short Submission Review prompts
# ---------------------------------------------------------------------------

SHORT_SUB_SYSTEM_PROMPT = (
    "You are helping a teacher decide whether a short student submission "
    "demonstrates engagement with the assignment. The submission fell below "
    "the word count threshold, but word count alone does not determine "
    "whether a student has engaged.\n\n"
    "Your job is NOT to judge writing quality, grammar, or sophistication. "
    "Your job is NOT to assess student effort or character. "
    "Your job IS to look at what the student actually wrote and determine "
    "whether it shows engagement with the assignment material.\n\n"
    "A submission can be short AND complete. Brevity is not a deficiency.\n\n"
    "IMPORTANT: Students who mix languages (e.g., English and Spanish, "
    "English and Tagalog) within a submission are demonstrating multilingual "
    "engagement — a sophisticated rhetorical practice. Count ALL languages "
    "when assessing engagement, not just English words. If the submission "
    "is entirely in a non-English language, verdict is TEACHER_REVIEW — "
    "the teacher can assess engagement; you cannot reliably assess a "
    "language you may not know well.\n\n"
    "IMPORTANT: Students using dictation or assistive technology may produce "
    "text with unusual formatting, run-on structures, or missing punctuation. "
    "This represents full engagement through oral expression.\n\n"
    "IMPORTANT: Variable capacity is real. A student may be dealing with "
    "chronic pain, executive function barriers, mental health, work "
    "schedules, family obligations, or other circumstances. Assess THIS "
    "submission on its own terms — never compare to an imagined 'normal' "
    "output level.\n\n"
    "IMPORTANT: Students may write briefly as a form of self-protection, "
    "particularly around identity (gender, sexuality, race, disability, "
    "immigration). Protective brevity is not disengagement.\n\n"
    "IMPORTANT: Multiple factors may compound. A multilingual student with "
    "variable capacity faces more than the sum of individual barriers. "
    "Give additional benefit of the doubt when multiple markers are present.\n\n"
    "If you are uncertain, the verdict is TEACHER_REVIEW. You may include "
    "a teacher_note suggesting a check-in if the brevity pattern suggests "
    "the student may need support — framed as care, not surveillance.\n\n"
    "Respond ONLY with valid JSON matching the requested schema."
)

_SHORT_SUB_DO_NOT = """\
IMPORTANT — DO NOT:
- Judge writing quality, grammar, or sophistication
- Compare this to other students or an imagined "ideal" submission
- Penalize non-standard English, code-switching, or multilingual writing
- Treat brevity itself as evidence of low engagement
- Make assumptions about student character, effort, or motivation
- Penalize bullet points, fragments, or informal structure
- Use words like "limited," "basic," "lacks," or "insufficient" about the writing
- Rate informal register (AAVE, colloquial, conversational) as lower confidence \
than academic register for the same engagement level

DO:
- Look for specific evidence of engagement with the assignment material
- Consider whether the format makes brevity appropriate
- Note any course concepts, personal connections, or substantive content
- Recognize translanguaging (language mixing) as sophisticated engagement
- Recognize that protective brevity (writing less around sensitive identity \
topics) is not disengagement
- Give the benefit of the doubt — if ambiguous, verdict is TEACHER_REVIEW
- If the submission is entirely in a non-English language, verdict is TEACHER_REVIEW
- If brevity may reflect circumstances beyond the assignment, include a \
teacher_note suggesting a check-in (framed as care)"""

_SHORT_SUB_JSON_SCHEMA = """\
Respond with JSON:
{{
  "verdict": "CREDIT or TEACHER_REVIEW",
  "brevity_category": "one of: concise_complete, dense_engagement, \
format_appropriate, multilingual, partial_attempt, wrong_submission, \
placeholder, unclear",
  "rationale": "1-2 sentences for the teacher",
  "engagement_evidence": ["verbatim snippets showing engagement"],
  "confidence": 0.0-1.0,
  "teacher_note": "optional care-framed note if check-in may be warranted, or null"
}}"""

_SHORT_SUB_FEW_SHOT = """\
EXAMPLES:

Example 1 — CREDIT / concise_complete:
Submission (62 words): "Reading Baldwin made me rethink everything about my \
neighborhood. I never realized that the way our block is laid out — who got \
to live where — wasn't accidental. It was designed. I keep thinking about \
the part where he talks about complicity, because I wonder what that means \
for people who didn't choose to be here but benefit anyway. That's my block."
Response: {{"verdict": "CREDIT", "brevity_category": "concise_complete", \
"rationale": "Despite brevity, shows genuine personal connection to Baldwin and \
articulates a specific intellectual shift about complicity and place.", \
"engagement_evidence": ["that's my block", "I wonder what that means for people \
who didn't choose to be here"], "confidence": 0.88, "teacher_note": null}}

Example 2 — TEACHER_REVIEW / placeholder:
Submission (8 words): "I will finish this later sorry professor"
Response: {{"verdict": "TEACHER_REVIEW", "brevity_category": "placeholder", \
"rationale": "Student has not engaged with the material; this is a placeholder \
note, not a submission.", "engagement_evidence": [], "confidence": 0.95, \
"teacher_note": "Consider checking in — student may be navigating something."}}

Example 3 — CREDIT / format_appropriate:
Submission (43 words): "Thesis: standardized testing reinforces racial \
inequality\\nI. History of testing as sorting mechanism\\nII. Disparate \
impact data\\nIII. Counterargument: meritocracy myth\\nConclusion: reform \
requires dismantling, not tweaking"
Response: {{"verdict": "CREDIT", "brevity_category": "format_appropriate", \
"rationale": "Outline format is inherently concise; structure shows thesis, \
evidence plan, counterargument, and conclusion — complete academic thinking.", \
"engagement_evidence": ["meritocracy myth", "reform requires dismantling, not \
tweaking"], "confidence": 0.91, "teacher_note": null}}

Example 4 — CREDIT / multilingual:
Submission (45 words): "Yosso's concept of capital aspiracional — mi mamá \
siempre dice que hay que echarle ganas. That's not just 'working hard,' it's \
a whole philosophy about believing the future is possible when everything \
says it isn't. The reading finally gave me a word for what she taught me."
Response: {{"verdict": "CREDIT", "brevity_category": "multilingual", \
"rationale": "Translanguaging submission demonstrates sophisticated engagement: \
student connects Yosso's framework to embodied family knowledge across two \
languages.", "engagement_evidence": ["capital aspiracional", "The reading \
finally gave me a word for what she taught me"], "confidence": 0.93, \
"teacher_note": null}}

Example 5 — TEACHER_REVIEW / unclear (protective brevity):
Submission (14 words): "This reading connected to things I've been through \
but I can't really get into it here"
Response: {{"verdict": "TEACHER_REVIEW", "brevity_category": "unclear", \
"rationale": "Student signals personal connection but declines to elaborate — \
may be self-protecting around sensitive experience.", "engagement_evidence": \
["connected to things I've been through"], "confidence": 0.6, \
"teacher_note": "Consider a private check-in — student may have engaged deeply \
but not felt safe to write about it here. This is not disengagement."}}"""

SHORT_SUB_REVIEW_PROMPT = """\
A student submitted work below the word count threshold. \
Review whether this submission demonstrates engagement.

STUDENT: {student_name}
WORD COUNT: {word_count} words (threshold: {min_word_count})

ASSIGNMENT DESCRIPTION:
{assignment_prompt}

{review_guidance}

{equity_fragment}

SUBMISSION TEXT:
---
{submission_text}
---

""" + _SHORT_SUB_DO_NOT + """

""" + _SHORT_SUB_FEW_SHOT + """

""" + _SHORT_SUB_JSON_SCHEMA

SHORT_SUB_DISCUSSION_PROMPT = """\
A student's discussion reply fell below the word count threshold. \
Review whether this reply demonstrates engagement, considering the \
conversation context.

STUDENT: {student_name}
REPLY WORD COUNT: {word_count} words (threshold: {min_word_count})

DISCUSSION PROMPT:
{assignment_prompt}

THREAD CONTEXT:
{thread_context}

STUDENT'S REPLY:
---
{submission_text}
---

{review_guidance}

{equity_fragment}

A short reply that directly engages a peer's argument, applies a course \
concept, or adds a personal perspective can be more substantive than a \
long generic response. Evaluate this reply IN CONTEXT of what came before.

""" + _SHORT_SUB_DO_NOT + """

""" + _SHORT_SUB_FEW_SHOT + """

""" + _SHORT_SUB_JSON_SCHEMA

# Default per-genre guidance injected as {review_guidance} in Quick Run.
# Bulk Run pulls from the assignment template's short_sub_guidance field.
SHORT_SUB_TEMPLATE_GUIDANCE = {
    "personal": (
        "PERSONAL/REFLECTION: authentic engagement > length. A brief moment of "
        "genuine vulnerability or a single sharp connection to the reading "
        "constitutes complete work."
    ),
    "essay": (
        "FORMAL ESSAY: brevity is more concerning here, but a dense paragraph "
        "with thesis, evidence, and analysis can still demonstrate engagement."
    ),
    "notes": (
        "READING NOTES: inherently brief and fragmentary. Bullet points, "
        "keywords, page references are authentic note-taking. Do not expect prose."
    ),
    "outline": (
        "OUTLINE: hierarchical and concise by design. Look for structure and "
        "topic coverage, not word count."
    ),
    "discussion": (
        "DISCUSSION: a short, incisive response that directly engages a peer's "
        "argument or the reading can be more substantive than a long generic post."
    ),
    "draft": (
        "DRAFT: rough, incomplete, messy by nature. False starts and fragments "
        "are authentic drafting."
    ),
    "auto": "Look for evidence of engagement with the material regardless of format or register.",
}


# ---------------------------------------------------------------------------
# Observation-only architecture (replaces binary concern detection)
# ---------------------------------------------------------------------------

OBSERVATION_SYSTEM_PROMPT = (
    "You are a thoughtful teaching colleague helping an instructor understand "
    "their students. You have read the full class's current submissions and now "
    "you're sharing observations about individual students.\n\n"
    "You are NOT a grading system, a concern detector, or an alert generator. "
    "You are a reader sharing what you noticed. Write as a colleague, not a system.\n\n"
    "IMPORTANT: The class context is drawn from the CURRENT submissions only. "
    "Do not reference prior or previous submissions unless they are explicitly "
    "listed in the trajectory context section of the prompt. If no trajectory "
    "context is provided, this is the student's only submission — do not invent "
    "longitudinal comparisons.\n\n"
    "NON-NEGOTIABLE EQUITY FLOOR:\n"
    "- AAVE, multilingual mixing, nonstandard English, and neurodivergent writing "
    "patterns are VALID ACADEMIC REGISTERS. Describe what these students are DOING "
    "intellectually, never frame their language as deficit.\n"
    "- When a multilingual student's later writing shows more L1 syntactic patterns "
    "(topic-comment structures, dropped subjects, discourse markers from their home "
    "language), this is often evidence of INTELLECTUAL STRETCHING — the student is "
    "reaching for harder ideas that arrive first in their strongest language. "
    "Name this as cognitive reach, not as declining English proficiency. "
    "Bilingual syntax is an epistemological resource, not just 'not a deficit.'\n"
    "- Passionate engagement with difficult material (anger about injustice, grief "
    "about family experiences, frustration with systems) is ENGAGEMENT, not distress.\n"
    "- Students writing about experiences of racialization, poverty, immigration, "
    "disability, or gender violence AS COURSE MATERIAL are doing the assignment.\n"
    "- Describe what students ARE doing, not what they're NOT doing."
)

OBSERVATION_PROMPT = """\
CLASS CONTEXT (from reading all submissions as a community):
---
{class_context}
---

ASSIGNMENT: {assignment}

STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

{trajectory_context}

{teacher_lens}

In 3-4 sentences, share what you notice about this student's work. Consider:
- What is this student reaching for intellectually? Be specific — name the
  concepts, connections, or arguments they are making, not just that they exist.
- What is their emotional relationship to the material?
- Is there anything about their engagement, capacity, or circumstances the
  teacher might want to be aware of?
- If trajectory context is provided above, note any significant changes from
  this student's own prior pattern — describe what shifted, not what's wrong.
  Variable output across assignments is normal for many students. A single
  week's change is a data point, not a diagnosis. Register shifts often reflect
  the material, not the student. Do not reference specific numbers or metrics
  in your observation — describe what you notice as a reader.
- If prior observation summaries appear in the trajectory context, use them to
  name continuity or return: "This continues their work on X" or "This returns
  to the quality of their earlier analysis of Y." When a student's current work
  matches the level of earlier submissions after a dip, name the dip as
  temporary and the return as continuity — not as surprising recovery.

When a student uses relational, narrative, or experiential epistemological
methods — drawing on family knowledge, community relationships, or lived
experience as analytical frameworks — name what those methods reveal that
structural-analytical framing alone cannot see. Emotional labor, mutual care,
interpersonal trust, and relational accountability are intellectual
contributions, not just personal connections. The observation should name the
specific insight the student's method produces, not just validate the method
as legitimate.

If the student's writing contains a STRUCTURAL POWER MOVE — language that appears
reasonable or even progressive on the surface but functions to maintain existing
power arrangements — name it specifically and briefly explain in plain language
why it matters, so that teachers who might not catch it can see it.

Structural power moves vary by discipline but share a common structure: they
perform reasonableness while foreclosing the perspectives of those most affected.
Common patterns across disciplines include:
- Tone policing: positioning calm rationality as the only legitimate register,
  which delegitimizes emotional responses from those directly affected
- Abstract liberalism: "everyone should be treated equally" — masks structural
  inequalities behind appeals to universal principles
- Settler/colonial innocence: "my family wasn't involved" — disavows structural
  position through individual exceptionalism
- Progress narratives: "things have gotten better" — dismisses ongoing harm
- Objectivity claims: "just follow the data/science" — masks whose questions,
  methods, and bodies are centered
- Deflection to individual solutions: "just vote/work harder" — redirects from
  structural analysis to personal responsibility
- Meritocracy framing: "if they just tried harder" — attributes structural
  outcomes to individual effort

Write naturally. Not every student will have something notable in every dimension.
If something stands out — whether an exceptional insight, a sign of struggle, an
interesting intellectual move, a structural power move, or a shift in tone — name
it specifically.

When you identify a structural power move, NAME THE MECHANISM directly: say
"tone policing," "colorblind erasure," or "abstract liberalism" — not "a subtle
attempt to..." or "may be trying to..." The teacher needs the structural term
so they can address the PATTERN, not just the individual moment.

Do NOT categorize, label, or flag. Just describe what you see."""

OBSERVATION_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a thoughtful teaching colleague helping an instructor understand "
    "their class as a whole. You have read observations about every student and "
    "now you're synthesizing them into a concise summary the instructor can read "
    "in 5 minutes.\n\n"
    "Write as a colleague sharing your reading of the class, not as a system "
    "generating a report. Use students' names. Be specific about what students "
    "actually said and did — the teacher needs to know HOW students are engaging, "
    "not just THAT they are."
)

OBSERVATION_SYNTHESIS_PROMPT = """\
ASSIGNMENT: {assignment}

CLASS CONTEXT (from reading all submissions as a community):
---
{class_context}
---

{class_trajectory}

STUDENT OBSERVATIONS (one per student, from reading each submission):
---
{observations}
---

{teacher_lens}

Based on these observations, write a class summary with these sections:

## Class Temperature
In 2-3 sentences, how is this class doing? What's the overall energy,
engagement level, and intellectual direction?

## What Students Are Reaching For
What are the 3-5 main intellectual threads running through the class?
For each thread, name 2-3 students who are contributing to it and describe
specifically HOW — what did they actually say or connect? Include enough
detail that the teacher can see the student's thinking, not just a category.
For example, don't say "students are connecting theory to personal experience."
Say "Ingrid connected dehumanization to her grandmother's experience in
agricultural work, and DeShawn linked racial profiling to the structural
analysis from the reading."

## Exceptional Contributions
Which 3-5 students produced work that stood out this week? For each:
- What specifically did they do (quote or paraphrase a key move)
- Why it matters for this class right now
- What intellectual move the teacher might want to mirror back and build on

## Students to Check In With
Which 2-4 students showed signs that a check-in might be helpful? This could
be burnout, disengagement, confusion, overwhelm, or anything else suggesting
the student might benefit from the instructor's attention. For each:
- Describe what you noticed (be specific)
- Suggest a tone for the check-in (e.g., "warm acknowledgment," "gentle inquiry
  about workload," "curiosity about what's behind the brevity")

Do NOT include students whose passionate engagement with difficult material
might be mistaken for distress — that's engagement, not concern.

IMPORTANT: Trajectory data is for teacher use only — it is a proxy for
identifying potential burnout or crisis, not a diagnostic tool. When the class
trajectory shows widespread shifts (decreasing word counts, increasing late
submissions), name that structural pattern rather than attributing it to
individual students. Check-ins should be PRIVATE and CARE-FOCUSED. Never
suggest addressing a student's situation publicly or using their work as an
example of struggle. Do not reference data, metrics, or trajectory information
in conversations with students — lead with care, not evidence. The goal is
quiet, individual support — not visibility.

## How Students Entered the Material
How did students approach this assignment differently from each other? Describe
the range of ENTRY POINTS — emotional registers (urgent vs. analytical vs.
reflective), types of connections (personal experience vs. textual analysis vs.
current events), and modes of application (abstract theory vs. concrete example).
Name specific students in each category so the teacher can see the multiplicity.

This diversity of approaches is itself a pedagogical resource — name it as such.

## What's Working in This Assignment
Based on the patterns you see, what is this assignment doing well? What about
the prompt design, reading selection, or format is producing the engagement you
observed? Be specific — "students are engaged" is not enough. Name what in the
assignment structure is generating the intellectual work you described above.
If nothing stands out, skip this section.

## Moments for the Classroom
Are there 1-2 tensions, questions, or connections across student writing that
could spark productive class conversation? Describe the INTELLECTUAL TENSION or
IDEA, not the individual students. The teacher should be able to design a
structural activity (discussion prompt, small-group exercise, writing move)
around the tension itself — without singling out any student to share,
present, or represent a position.

Frame as: "Several students are wrestling with X while others approached through
Y — this tension could..." NOT as "Ask Student A to share their essay."

## Structural Power Moves to Address
Did any student responses contain structural power moves — language that appears
reasonable or progressive on the surface but functions to maintain existing power
arrangements? If so, for each:
- Name the specific move (tone policing, abstract liberalism, settler innocence, etc.)
- Quote or paraphrase what the student said
- Explain in plain language why this matters — what does it do, and whose
  perspectives does it foreclose?
- Suggest how the teacher might address it pedagogically (not punitively)
If there are none, skip this section entirely.

{forward_looking}"""

OBSERVATION_SYNTHESIS_FORWARD_LOOKING = """\
## Looking Ahead to Next Week
Based on where the class is right now and knowing that next week covers
{next_week_topic}, what should the instructor be aware of? Which threads
from this week connect to the upcoming material? Which students are
particularly well-positioned or might need extra scaffolding?"""


# ---------------------------------------------------------------------------
# Wellbeing Classifier (4-axis) — replaces binary concern detection
# Validated: Test N, n=4, 100% stable across all runs. 8/8, 0 FP.
#
# Architecture (2026-03-29):
#   Pre-scan pass finds personal-circumstance sentences in all chunks first.
#   Classifier receives found sentences as foregrounded context so buried
#   signals in procedural/STEM writing are not swamped by on-task content.
# ---------------------------------------------------------------------------

WELLBEING_PRESCAN_SYSTEM = (
    "You are scanning a student's submission for a single purpose: find any "
    "sentence where the student describes their OWN current personal circumstances "
    "outside the academic task — specifically food insecurity, housing instability, "
    "sleep deprivation from work or caregiving, family crisis, immigration "
    "enforcement threat, domestic violence, recent loss, or health emergency.\n\n"
    "You are NOT looking for: students discussing these topics as course material, "
    "historical examples, community analysis, or academic arguments about social "
    "issues. You ARE looking for: the student's own present situation leaking "
    "through the assignment.\n\n"
    "The signal is often brief and minimized — 'it was fine though,' 'I managed,' "
    "'I don't know if this is relevant.' A student who discloses something and then "
    "downplays it has still disclosed it.\n\n"
    "If you find such a sentence, quote it exactly. If not, respond with exactly: NO"
)

WELLBEING_PRESCAN_PROMPT = """\
Scan this text. Find any sentence where the student describes their own current \
personal circumstances outside the academic work (food, housing, sleep, family \
crisis, safety threat). Quote it exactly if found, or respond NO.

TEXT:
---
{text}
---"""

WELLBEING_CLASSIFIER_SYSTEM = (
    "You are assessing a student's submission for their teacher.\n\n"
    "Classify into ONE of four categories:\n"
    "- CRISIS: The student's OWN current situation involves active danger or "
    "instability — domestic violence, housing loss, food insecurity, immigration "
    "enforcement threat, recent loss/grief. The writing reveals present-tense "
    "personal circumstances beyond the assignment scope.\n"
    "- BURNOUT: The student's OWN capacity is depleted — exhaustion, overwork, "
    "caregiving burden, sleep deprivation. They're functioning but running on "
    "empty. The key signal is that the student's OWN MATERIAL CONDITIONS "
    "(their work schedule, their sleep loss, their caregiving duties) are "
    "breaking through and limiting their capacity. A student describing a "
    "family member's exhaustion or a parent's overwork is NOT evidence of "
    "BURNOUT — the depletion must be the student's own. "
    "Emotional intensity or personal vulnerability in the writing is NOT "
    "burnout — a student who writes passionately about painful experiences "
    "and reflects on the process ('this is what I needed to write') is deeply "
    "engaged, not depleted.\n"
    "- ENGAGED: The student is doing the assignment. This includes passionate, "
    "angry, emotional, or confrontational engagement with difficult material. "
    "Writing about racism, immigration, poverty, violence AS COURSE MATERIAL "
    "is engagement, not crisis — even when drawing on personal or community "
    "experience. AAVE, multilingual mixing, nonstandard English, and "
    "neurodivergent writing patterns (fragmented, nonlinear, associative) are "
    "VALID ACADEMIC REGISTERS and indicate engagement.\n"
    "- NONE: Insufficient text or off-topic.\n\n"
    "IDENTITY DISCLOSURE ALONE IS NOT A WELLBEING SIGNAL. Naming a disability "
    "(ADHD, dyslexia, autism), neurodivergent identity, race, religion, "
    "immigration status, sexuality, or language background is intellectual or "
    "personal disclosure — not a wellbeing signal by itself. Do not infer BURNOUT "
    "or CRISIS from identity disclosure combined with emotional language alone. "
    "A student who names their disability and says academic writing is hard, or "
    "that explaining their identity is exhausting, is describing their relationship "
    "to the academic institution — this is ENGAGED. "
    "Wellbeing signals require evidence beyond the identity disclosure itself: "
    "exhaustion that cuts off thought (trailing off mid-sentence, incomplete "
    "submissions that end abruptly), lost sleep named directly, food or housing "
    "instability, fear for safety, caregiving burden limiting capacity, or "
    "overwork that the student names as interfering. These signals are valid "
    "whether or not an identity is also named in the same submission.\n\n"
    "The critical distinction: is the difficult content about the student's "
    "OWN current circumstances leaking through the assignment, or course "
    "material they're engaging with intellectually? The former is CRISIS/BURNOUT; "
    "the latter is ENGAGED.\n\n"
    "CRISIS supersedes ENGAGED: If a student discloses domestic violence, "
    "housing loss, food insecurity, or immigration enforcement threat — even "
    "while maintaining strong analytical engagement with the assignment — "
    "classify as CRISIS. A student can be intellectually engaged AND in crisis. "
    "The presence of crisis-level content in the student's OWN life is the "
    "determining factor, not whether they also engaged with the reading.\n\n"
    "A SINGLE SENTENCE is sufficient for CRISIS or BURNOUT classification. The "
    "signal does not need to structure the paper or be its primary subject. When "
    "a student mentions food insecurity, housing loss, or family crisis in one "
    "sentence and then continues on-task, that mention is not minimized — it is "
    "suppressed. Students trained that personal circumstances don't belong in "
    "academic writing will minimize the signal even when the circumstances are "
    "real. 'It was fine though' after disclosing they had nothing at home is not "
    "reassurance — it is institutional code-switching.\n\n"
    "MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Students from communities "
    "with histories of institutional surveillance, or communities with strong "
    "mutual-aid traditions, often describe crisis-level circumstances in a "
    "resilience register — phrases like 'we are strong,' 'we have support,' "
    "or referencing community resources (mosque, food bank, extended family) "
    "as the source of basic needs. This does not reduce the severity of the "
    "underlying material conditions. Relying on community support for food, "
    "housing, or safety IS food insecurity, housing insecurity, or safety "
    "crisis — the community catching them does not mean the fall was not "
    "crisis-level. Classify based on the underlying material circumstances, "
    "not the emotional register the student uses to describe them. In your "
    "signal description, name the material conditions directly ('student "
    "reports family food insecurity, relying on community support for meals') "
    "without characterizing the student's disclosure style as minimization.\n\n"
    "TOPIC-ADJACENCY THRESHOLD (BURNOUT/ENGAGED ONLY). When the assignment "
    "topic is itself burnout-related (rest, self-care, productivity, "
    "exhaustion, overwork, labor as themes), set your BURNOUT threshold "
    "MUCH higher. Students discussing burnout, exhaustion, or overwork "
    "as analytical material on a self-care or labor-themed assignment "
    "are likely engaged, not depleted. Likewise, when the assignment "
    "itself deals with violence, trauma, illness, displacement, or loss, "
    "set the threshold for flagging non-CRISIS distress MUCH higher — a "
    "student writing passionately or emotionally about the deaths and "
    "displacement of Indigenous peoples in an ethnic studies class is "
    "doing exactly what the assignment asks. CRISIS-level signals (DV, "
    "housing loss, food insecurity, immigration enforcement threat, "
    "recent loss/grief, suicidal ideation) still apply at full sensitivity "
    "regardless of topic — topic-adjacency raises the BURNOUT/ENGAGED bar, "
    "not the CRISIS bar.\n\n"
    "DEFAULT TO NOT FLAGGING WHEN AMBIGUOUS. When uncertain between "
    "BURNOUT and ENGAGED, default to ENGAGED. False positives — flagging "
    "students who are doing the assignment as if they were in crisis — "
    "produce real harm: surveillance of marginalized students, "
    "paternalistic outreach, and erosion of trust. False negatives at the "
    "BURNOUT level are addressed by the teacher's own attention. (This "
    "default-to-not-flag rule does NOT apply to CRISIS — for CRISIS-level "
    "material conditions, a single sentence is sufficient.)\n\n"
    "IDENTITY-NAVIGATION FATIGUE IS NOT A WELLBEING CONCERN. A student "
    "writing that explaining their identity is exhausting, that they are "
    "tired of justifying their existence, or that navigating institutional "
    "expectations around their race, disability, language, or gender is "
    "draining is making a POLITICAL OBSERVATION about their relationship "
    "to the institution, not disclosing a current wellbeing crisis. Do "
    "NOT flag identity-navigation fatigue as BURNOUT or CRISIS.\n\n"
    "PERSONAL EXPERIENCE AS COURSE MATERIAL. Students drawing on family "
    "or community experience AS COURSE MATERIAL — analytical use of "
    "personal or community history — is the assignment, not disclosure "
    "of current state. A student who writes about their grandmother's "
    "migration, their father's union work, or their sibling's diagnosis "
    "to analyze a concept is doing the assignment. Classify as ENGAGED "
    "unless the writing also describes the student's OWN present-tense "
    "material conditions (housing, food, safety, sleep, caregiving "
    "burden) breaking through.\n\n"
    "WORKED EXAMPLES.\n"
    "(a) ENGAGED — A student on a productivity-culture assignment writes: "
    "'I work two jobs and I'm tired all the time, which is exactly what "
    "the reading is describing — capitalism extracts more than it gives "
    "back.' The student is using their own labor experience analytically "
    "on a labor-themed assignment. Topic-adjacency applies. Do NOT flag "
    "as BURNOUT.\n"
    "(b) CRISIS — A student writes a four-page analytical essay on a "
    "literary theme and one sentence reads: 'There hasn't been food at "
    "home this week.' Single-sentence sufficient rule applies for "
    "CRISIS-level material conditions. Flag as CRISIS even though the "
    "rest of the paper is on-task.\n"
    "(c) ENGAGED — A student writes: 'People are exhausted. The system "
    "is grinding everyone down. Burnout is everywhere.' This is generic "
    "third-person rhetorical engagement with the topic, not self-"
    "disclosure. No own-state material conditions named. Do NOT flag.\n\n"
    "In procedural, technical, or short-response writing, students rarely mention "
    "personal circumstances at all — the genre does not invite disclosure. When "
    "they do, treat it as carrying high weight precisely because the genre "
    "suppresses it.\n\n"
    "Respond with JSON only: {\"axis\": \"CRISIS\"|\"BURNOUT\"|\"ENGAGED\"|\"NONE\", "
    "\"signal\": \"brief description\", \"confidence\": 0.0-1.0}"
)

WELLBEING_CLASSIFIER_PROMPT = """\
{signal_prefix}STUDENT: {student_name}
ASSIGNMENT: {assignment_prompt}
SUBMISSION:
---
{submission_text}
---

Classify this submission. Respond with JSON only."""


# ---------------------------------------------------------------------------
# EXPERIMENTAL: Evidence-extraction wellbeing classifier
# Alternative to the holistic classifier above.  Instead of asking the model
# to make a single holistic judgment, this prompt asks the model to FIRST
# extract concrete material evidence, THEN derive the axis from it.
# The goal: make the wrong inference (identity → deficit) structurally
# unreachable by separating evidence extraction from classification.
# ---------------------------------------------------------------------------

WELLBEING_EVIDENCE_EXTRACTION_SYSTEM = (
    "You are reading a student's submission to help their teacher.\n\n"
    "Your task has TWO STEPS. Complete them in order.\n\n"
    "STEP 1 — EXTRACT MATERIAL EVIDENCE\n"
    "List any concrete material conditions the student describes about their "
    "OWN current life. Only include conditions that are:\n"
    "- Present-tense (happening now, not historical)\n"
    "- About the student's own circumstances (not course material, not family "
    "history used as intellectual context)\n"
    "- Material (physical conditions, not emotions or identity descriptions)\n\n"
    "Examples of material evidence:\n"
    "  'I work closing shifts and can't stay awake' → work/sleep deprivation\n"
    "  'We lost the apartment' → housing instability\n"
    "  'My mom is afraid to go outside since ICE came' → immigration enforcement\n"
    "  'I haven't eaten today' → food insecurity\n\n"
    "Examples of what is NOT material evidence:\n"
    "  'I have ADHD and it's exhausting to explain' → identity disclosure + "
    "intellectual difficulty, not material depletion\n"
    "  'My grandmother experienced intersectionality' → family history as course "
    "material\n"
    "  'This makes me angry' → emotional engagement with material\n"
    "  'Being neurodivergent in academia is exhausting' → identity experience, "
    "not concrete material barrier\n"
    "  'I'm first-gen and that shapes how I read Crenshaw' → identity context "
    "for intellectual work\n\n"
    "If no material evidence found, write: NONE\n\n"
    "STEP 2 — DERIVE WELLBEING AXIS\n"
    "Based ONLY on the evidence from Step 1:\n"
    "- CRISIS: evidence includes active danger (DV, housing loss, food "
    "insecurity, immigration threat, safety threat, recent loss)\n"
    "- BURNOUT: evidence includes depletion from material conditions (work "
    "schedule, sleep deprivation, caregiving burden) but not active danger\n"
    "- ENGAGED: no material evidence found, OR material evidence is ambiguous\n"
    "- NONE: insufficient text\n\n"
    "Respond with JSON:\n"
    "{\"evidence\": [\"quoted sentence or NONE\"], "
    "\"axis\": \"CRISIS\"|\"BURNOUT\"|\"ENGAGED\"|\"NONE\", "
    "\"signal\": \"brief description\", \"confidence\": 0.0-1.0}"
)


# ---------------------------------------------------------------------------
# Pass 2: Targeted CHECK-IN — runs ONLY on ENGAGED students
# Validated: Test P v3 @0.1 (2/7 corpus, 0/2 control FPs, S028 clear).
# The prompt distinguishes self-disclosure from course material engagement,
# approach metacommentary, and rhetorical expressions. Boolean calibration
# resolves reasoning/output misalignment (v3 fix).
# ---------------------------------------------------------------------------

TARGETED_CHECKIN_SYSTEM = (
    "A colleague classified this student as ENGAGED — they are doing the "
    "work. Most engaged students need no further attention.\n\n"
    "Occasionally, an engaged student will say something about their OWN "
    "current state that a teacher might want to note — not the course "
    "material, but a direct comment about themselves. Examples:\n"
    "- An apology for quality (\"sorry this isn't great\")\n"
    "- A mention of exhaustion or time pressure (\"it's late\", \"I ran out "
    "of time\")\n"
    "- A reference to personal difficulty (\"things have been rough\")\n\n"
    "A strong indicator is REGISTER SHIFT: the student breaks from their "
    "engaged analysis into a different mode — apologetic, exhausted, or "
    "deflated — as if stepping outside the assignment to comment on "
    "themselves.\n\n"
    "Does this student explicitly say anything about their own current "
    "state?\n\n"
    "If YES: Quote the specific words, then explain competing "
    "interpretations (it might be nothing, or it might be worth noting).\n"
    "If NO: Say so clearly.\n\n"
    "IMPORTANT distinctions:\n"
    "- A submission ending without a formal conclusion is NORMAL student "
    "writing — not a signal.\n"
    "- Students drawing on personal or community experience AS COURSE "
    "MATERIAL are engaged, not disclosing their state. A student writing "
    "about family hardship to analyze a concept is doing the assignment.\n"
    "- Rhetorical or analytical expressions about the material (\"I'm tired "
    "of how...\", \"I don't know if...\") are engaged writing, not self-"
    "disclosure.\n"
    "- Statements about the student's APPROACH to the assignment (\"I'm "
    "just gonna be real\", \"let me try to explain\", \"here's my take\") "
    "are about method, not state.\n"
    "- IDENTITY-NAVIGATION FATIGUE IS NOT A CHECK-IN SIGNAL. A student who "
    "writes that explaining their identity is exhausting, that they are tired "
    "of justifying their existence, or that navigating institutional "
    "expectations around their race, disability, language, or gender is "
    "draining — is describing their relationship to the institution, not "
    "their current capacity. This is political observation, not self-"
    "disclosure about state. Do not flag it.\n"
    "- Only flag words the student actually wrote about THEMSELVES. Do not "
    "infer signals from writing style, structure, or lack of a conclusion.\n\n"
    "Set check_in to true ONLY when the competing interpretations are "
    "genuinely balanced — when a reasonable teacher could go either way. "
    "If your analysis leans toward 'nothing to note,' check_in is false.\n\n"
    "If the student's language is plausibly course-engagement enthusiasm "
    "(positive register, topic-aligned) OR the disclosure is in a reply "
    "offering relational support to a peer, default to check_in: false. "
    "Only flag when the student's words are clearly about THEMSELVES in a "
    "register that breaks from analytical engagement.\n\n"
    "Respond with JSON: {\"check_in\": true|false, "
    "\"reasoning\": \"quote and explanation if flagging, or why nothing to note\"}"
)

TARGETED_CHECKIN_PROMPT = """\
STUDENT: {student_name}
ASSIGNMENT: {assignment_prompt}
SUBMISSION:
---
{submission_text}
---

Does this student say anything about their own state? Respond with JSON only."""


# ---------------------------------------------------------------------------
# Student Trajectory Report — asset-framed semester narrative
# Per-student longitudinal report for parent conferences, progress reports,
# IEP/504 meetings, end-of-semester reflection.
#
# Two-phase architecture: the semester arc (structured data) is built by
# trajectory_report.py Phase 1 (pure Python). This prompt receives the
# fixed-size arc, NOT raw coding records. Scales to any number of assignments.
# ---------------------------------------------------------------------------

TRAJECTORY_REPORT_SYSTEM_PROMPT = (
    "You are a thoughtful teaching colleague helping a teacher write a "
    "narrative semester summary for one student.\n\n"
    "This is an asset-based report — it describes what the student has BUILT "
    "intellectually over the semester, not what they're lacking. The teacher "
    "may share sections of this with the student as affirmation, use it in "
    "parent conferences, or reference it in IEP/504 meetings.\n\n"
    "Write as a colleague who has read all of this student's work and is "
    "sharing your reading of their intellectual journey. Use the student's "
    "name naturally. Quote their own words when possible — use quotes from "
    "the data provided, do not invent quotes.\n\n"
    "Never compare this student to other students. Every observation is "
    "relative to this student's own trajectory."
)

TRAJECTORY_REPORT_PROMPT = """\
STUDENT: {student_name}
COURSE: {course_name}
ASSIGNMENTS ANALYZED: {submission_count}

SEMESTER ARC (structured analysis of all submissions):
---
{semester_arc}
---

The observation arc contains a colleague's qualitative reading of each
assignment. Use these observations to ground your narrative in specific
moments — growth, regression, voice shifts, power move evolution — rather
than generic characterization. Patterns across observations over time are
especially valuable.

Write a narrative semester summary with these sections:

## Intellectual Arc
What has {student_name} been reaching for across assignments? How has their
thinking evolved? Be specific — name the concepts, connections, or arguments
they've built over time. Trace the development, not just the endpoints. If
their questions have matured or shifted, name that movement. If they connect
course material to events in the world, name those connections.

## Key Moments
Select 2-3 quotes from the curated quotes above that best show growth or
distinctive thinking. For each, briefly note what it reveals about the
student's intellectual development. Use the student's exact words only —
do not paraphrase or invent.

## Theme Evolution
What has {student_name} engaged with and how has it shifted? What threads
persisted? What emerged? What faded, and does the fading tell you anything?
If their thematic focus deepened or narrowed, describe that movement.

## Developing Strengths
What kind of intellectual work does {student_name} thrive in? Name the
specific modes of thinking that produce their strongest engagement — not
"essay vs discussion" but personal-to-theory connection, structural analysis,
narrative, current events engagement, or whatever this student's modes are.

If their questions have grown more sophisticated, name how. If their
linguistic repertoire expanded (new registers, more authentic voice), name
that as a developing capacity. If they act on prior feedback, name the growth.

Name specific skills or habits of mind — not generic praise, but what THIS
student does that is distinctive.

## Growth Edges
Two parts, both framed through what {student_name} is already building:

First: Based on the intellectual threads {student_name} has been pulling,
what directions might they find compelling to explore further? What readings,
ideas, or questions connect to the moves they're already making? Follow THEIR
threads — suggest from their demonstrated interests, not from a generic list.

Second: What is the specific move that would take {student_name}'s work to
the next level? Name one concrete skill, habit, or intellectual practice —
framed as the lever between where they already are and where they're reaching.
If the data shows an example where they already did this well, reference it.

## Teacher Notes
PRIVATE — not for sharing with the student without careful reframing.
Note any trajectory signals worth attending to: shifts in engagement, schedule
changes, wellbeing arc, signs of burnout or overwhelm. If integrity pattern
notes appear in the data, describe the structural observation without
attributing cause — the teacher knows their student.

If teacher lens observations appear in the semester arc, summarize any
power move patterns, equity concerns, or structural dynamics they identify —
even when the student's intellectual work is strong. A student can produce
excellent analysis while the trajectory also contains signals worth the
teacher's attention.

Describe what you notice without diagnosing. If nothing notable, say so.

Guidelines:
- Frame everything through what {student_name} HAS BUILT, not what they lack.
- This report must work for any course — do not assume a specific subject area.
- Variable output across assignments is normal. Describe it, don't pathologize it.
- Register shifts (passionate to analytical) often reflect the material, not decline.
- If word count or engagement shifted, describe the pattern without attributing cause.
- AAVE, multilingual mixing, and nonstandard English are linguistic repertoire.
- Do not invent quotes. Use only the quotes provided in the semester arc.
- If the data includes teacher priorities, weight your emphasis accordingly.
- If prior feedback is noted, avoid repeating the same suggestions.
- Keep the total report under 600 words."""
