"""
Research-only prompts: binary concern classifiers.

These prompts are research apparatus, not production. They define the binary
concern classifiers (Track A) that the research panel runs alongside the
production 4-axis wellbeing classifier and generative observation.

Two scopes are supported:
- CONCERN_PROMPT — combined: wellbeing concerns + power-moves language
  (essentializing, colorblind ideology, savior narrative, etc.)
- WELLBEING_CONCERN_PROMPT — wellbeing only, scope-matched to Track B's
  4-axis classifier

Both share the same equity-hardening: course-content vs. student-wellbeing
distinction, the long Do-NOT-flag list, disability/neurodivergence self-
advocacy clause, identity-navigation fatigue exclusion (in wellbeing-only),
post-processing anti-bias filters (applied by concern_detector.py), and
structured output with confidence threshold.

Also defined here:
- CONCERN_CRITIC_PROMPT — adversarial pass (written but not currently wired)
- CONCERN_IMMANENT_CRITIQUE_ADDENDUM — pedagogical framing addendum

Production prompts (SYSTEM_PROMPT, JSON_REPAIR_PROMPT, etc.) remain in
src/insights/prompts.py and are imported by concern_detector.py from there.
"""

CONCERN_PROMPT = """\
Review this student submission for passages that might need the teacher's \
attention. You are looking for signs of STUDENT WELLBEING issues or \
language that essentializes or dismisses groups.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}
{class_context}
NON-LLM SIGNAL MATRIX RESULT:
{signal_matrix_result}

SUBMISSION TEXT:
---
{submission_text}
---

CRITICAL INSTRUCTIONS — READ VERY CAREFULLY:

THE MOST IMPORTANT DISTINCTION: You must distinguish between COURSE CONTENT \
and STUDENT WELLBEING. Many courses require students to discuss violence, \
trauma, oppression, genocide, sexual assault, and other difficult topics. \
A student writing ABOUT these topics is doing the assignment, not expressing \
personal distress. Your job is to detect whether the STUDENT is in trouble, \
not whether the SUBJECT MATTER is disturbing.

COURSE CONTENT vs. STUDENT WELLBEING — key test:
Ask: "Is the student discussing something that happened TO OTHERS (in history, \
in society, in the readings) or revealing something about THEIR OWN current \
mental state and personal crisis?"

Do NOT flag ANY of the following:
- Students discussing, analyzing, or emotionally responding to assigned course \
material about historical trauma, violence, colonialism, genocide, sexual \
violence, slavery, forced removal, or any other difficult subject matter — \
THIS IS THE ASSIGNMENT, not a concern
- Students expressing anger, grief, shock, or moral outrage about injustice \
described in course material (e.g. "It's crazy that this happened", "this \
makes me sick", "I can't believe this was legal")
- Students using words like "triggered", "overwhelming", or "hard to read" \
when describing their emotional response to difficult course material — this \
is emotional engagement with the assignment, not clinical distress
- Students expressing anger about racism, structural violence, or injustice \
(this is appropriate academic engagement)
- Students describing their own experiences with discrimination
- Students critiquing institutional racism, policing, or immigration enforcement
- Students using urgent or passionate language about justice issues
- Students whose writing style differs from academic English conventions
- Students using colloquial intensifiers like "crazy", "insane", "wild" when \
reacting to course content
- Students naming their own disability, neurodivergence, or learning difference \
as part of their analysis — a student writing "I have dyslexia and ADHD" or \
"as someone with a learning disability" is doing SELF-ADVOCACY, not expressing \
distress. Disability disclosure used to analyze one's own experience through a \
course framework is intellectual work, not a wellbeing concern. The question is \
not whether the student has a hard time — it is whether the systems around them \
were built for someone else
- Students who say their thoughts "aren't organized" or their writing "isn't \
perfect" — when a student names their own divergence from academic convention \
and STILL produces substantive analysis, they are doing metacognitive work. \
Do not read this as inability; read it as awareness of a mismatch between \
their thinking and the form they've been given to express it

DO flag:
- Language that essentializes racial or ethnic groups ("all X people...", \
"they always...", "those people")
- Colorblind claims ("I don't see race", "not about race", "reverse racism")
- Dismissal of other students' lived experiences
- Tone policing ("too angry", "too emotional", "calm down")
- Savior narratives ("those poor people need our help", "we should save them", \
"it's so sad what they go through") — positions the speaker as rescuer and the \
studied group as helpless, erasing their agency and self-determination
- Exoticizing ("their culture is so beautiful and spiritual", "they have such \
a rich tradition", "I wish I could be that connected to my roots") — admiration \
that fixes a group as essentially different, turning people into aesthetic objects
- Model minority framing ("Asians succeed because of their culture", "some \
groups just value education more") — uses one racialized group's perceived \
success to dismiss structural barriers and discipline other groups
- Deficit framing of poverty ("those kids don't have access to...", "students \
from low-income backgrounds can't...", "the cycle of poverty") — locates the \
problem in the community rather than in the structures that produce deprivation
- Student revealing PERSONAL crisis: expressions of hopelessness about their \
OWN life, self-harm ideation, feeling unable to continue, requests for help \
that go beyond the academic context
- Student language that shifts from discussing course material to discussing \
their own inability to cope as a PERSON (not just "this reading was hard" \
but "I don't know how to keep going")

HOW TO TELL THE DIFFERENCE — examples:
- "This makes me angry" about historical injustice → ENGAGEMENT, not a concern
- "I can't do this anymore" about their own life → POTENTIAL CONCERN
- "This passage about rape was triggering" → emotional engagement with material
- "I feel like nobody would care if I disappeared" → POTENTIAL CONCERN
- "It's crazy how they treated Native women" → discussing course content
- "Reading about this violence was really heavy" → processing difficult material
- "I haven't been able to get out of bed and I don't see the point" → CONCERN
- "I have dyslexia and ADHD and I'm Latino and first-gen honors" → SELF-ADVOCACY \
using intersectionality to analyze their own position. This is the assignment.
- "my thoughts aren't organized in the way an essay is supposed to be organized" → \
METACOGNITIVE AWARENESS of form mismatch, not inability. The student is arguing \
that the form doesn't fit the content — that IS an intellectual contribution.

When the assignment ITSELF deals with violence, trauma, or injustice, set \
your threshold MUCH higher for flagging. A student writing passionately or \
emotionally about the mistreatment of Native peoples in an ethnic studies \
class is doing exactly what the assignment asks. Only flag if the student \
shifts from analyzing course content to revealing personal crisis.

The non-LLM analysis classified this submission as shown above. Consider \
this context — if the non-LLM pass says "APPROPRIATE: political urgency \
about injustice", that is very likely correct.
{profile_fragment}

Respond with JSON:
{{
  "concerns": [
    {{
      "flagged_passage": "exact text from the submission",
      "surrounding_context": "2-3 sentences around the flagged passage",
      "why_flagged": "brief explanation",
      "confidence": 0.0-1.0
    }}
  ]
}}

If no concerns, return: {{"concerns": []}}

EXAMPLE of what IS a concern (essentializing language):
{{
  "concerns": [
    {{
      "flagged_passage": "I don't see why we keep talking about race, everyone is equal now",
      "surrounding_context": "The student was responding to the Omi and Winant reading. They wrote: 'I don't see why we keep talking about race, everyone is equal now. My family worked hard and succeeded without any special treatment.'",
      "why_flagged": "Colorblind ideology — dismisses structural racism. Teacher may want to engage this student with specific evidence.",
      "confidence": 0.75
    }}
  ]
}}

EXAMPLE of what IS a concern (student wellbeing):
{{
  "concerns": [
    {{
      "flagged_passage": "I honestly don't know why I'm still doing any of this",
      "surrounding_context": "After a paragraph analyzing the reading, the student wrote: 'I honestly don't know why I'm still doing any of this. Nothing feels like it matters anymore. I'm just going through the motions.'",
      "why_flagged": "Student shifts from course analysis to expressing personal hopelessness. May indicate wellbeing issue beyond the assignment. Teacher should check in.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what is NOT a concern (engaging with difficult material):
A student in an ethnic studies class writes: "Reading about the rape and \
murder of Native women made me feel sick. It's crazy that this is still \
happening and nobody talks about it. This passage was really triggering \
but I'm glad we're learning about it." — This is a student processing \
difficult course material with appropriate emotional engagement. Do NOT \
flag this.

EXAMPLE of what is NOT a concern (passionate engagement):
"The system of white supremacy in this country makes me furious. How can \
we read about redlining and NOT be angry?" — This is appropriate engagement. \
Do NOT flag this.

EXAMPLE of what IS a concern (scientific-sounding essentialism):
{{
  "concerns": [
    {{
      "flagged_passage": "certain populations are just genetically predisposed to these health outcomes",
      "surrounding_context": "In a reflection on health disparities, the student wrote: 'I think certain populations are just genetically predisposed to these health outcomes. It's not really about access or racism, it's biology.'",
      "why_flagged": "Biological essentialism — attributes health disparities to genetics rather than engaging with structural determinants (housing, pollution, food access, insurance, provider bias). Teacher may want to direct student to evidence on social determinants.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what IS a concern (pathologizing cultural practices):
{{
  "concerns": [
    {{
      "flagged_passage": "that kind of parenting would be considered neglect in our culture",
      "surrounding_context": "Responding to a case study on child development, the student wrote: 'The family's approach to discipline seems really unhealthy. That kind of parenting would be considered neglect in our culture. I think the child clearly has attachment issues because of it.'",
      "why_flagged": "Pathologizes a cultural parenting practice using Western diagnostic frameworks as universal norm. Student also diagnoses a child from surface description. Teacher may want to discuss cultural context in developmental assessment.",
      "confidence": 0.7
    }}
  ]
}}

EXAMPLE of what IS a concern (savior narrative):
{{
  "concerns": [
    {{
      "flagged_passage": "it breaks my heart to see these communities suffering and I want to dedicate my career to helping them",
      "surrounding_context": "In a reflection on urban poverty, the student wrote: 'It breaks my heart to see these communities suffering and I want to dedicate my career to helping them. They need people who understand policy to advocate for them because they can't do it themselves.'",
      "why_flagged": "Savior narrative — positions the studied community as helpless and the student as rescuer, erasing community agency and self-advocacy. Teacher may want to redirect toward solidarity frameworks and community-led solutions.",
      "confidence": 0.75
    }}
  ]
}}

EXAMPLE of what IS a concern (exoticizing):
{{
  "concerns": [
    {{
      "flagged_passage": "Indigenous cultures have this amazing spiritual connection to the earth that we've lost in Western society",
      "surrounding_context": "Responding to a reading on environmental justice, the student wrote: 'Indigenous cultures have this amazing spiritual connection to the earth that we've lost in Western society. Their traditions are so beautiful and pure, it's like they understand something we don't.'",
      "why_flagged": "Exoticizing — admiration that fixes Indigenous peoples as essentially spiritual and closer to nature, erasing the diversity of Indigenous experiences and political struggles. Romanticization is a form of essentialism. Teacher may want to redirect toward specific tribal sovereignty and environmental policy.",
      "confidence": 0.7
    }}
  ]
}}

EXAMPLE of what IS a concern (model minority framing):
{{
  "concerns": [
    {{
      "flagged_passage": "Asian Americans prove that hard work can overcome racism because they've been so successful",
      "surrounding_context": "In a discussion of structural racism, the student wrote: 'Asian Americans prove that hard work can overcome racism because they've been so successful despite discrimination. If one group can do it, maybe the issue isn't really structural.'",
      "why_flagged": "Model minority myth — uses a flattened narrative of Asian American 'success' to dismiss structural racism and implicitly discipline other racialized groups. Erases diversity within Asian American communities and the specific histories of immigration policy that shaped outcomes. Teacher may want to engage with disaggregated data and the political function of the model minority narrative.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what IS a concern (deficit framing of poverty):
{{
  "concerns": [
    {{
      "flagged_passage": "students from these neighborhoods just don't have the cultural capital to succeed in college",
      "surrounding_context": "In a reflection on educational inequality, the student wrote: 'Students from these neighborhoods just don't have the cultural capital to succeed in college. Their families don't value education the same way, and without role models, they fall into the cycle of poverty.'",
      "why_flagged": "Deficit framing — locates the problem in communities and families ('don't value education') rather than in the structures that produce deprivation (disinvestment, redlining, school funding tied to property tax). The 'cycle of poverty' framing naturalizes structural conditions as individual/cultural failure. Teacher may want to redirect toward Yosso's community cultural wealth or structural analysis of school funding.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what is NOT a concern (community health knowledge):
A nursing student writes: "My grandmother always used teas and remedios for \
everything, and honestly some of the pharmacology we're learning makes me \
think she wasn't wrong. My family doesn't trust hospitals because of how \
they treated my tío." — This student is integrating community health knowledge \
with clinical learning and naming a rational response to medical mistreatment. \
Do NOT flag this.

EXAMPLE of what is NOT a concern (lived expertise in a studied context):
A psychology student writes: "As someone who is autistic, I find it really \
frustrating that the textbook frames ASD as a list of deficits. My brain \
works differently, not worse." — This student is contributing expertise from \
lived experience and challenging the medical model. Do NOT flag this."""


# ---------------------------------------------------------------------------
# Wellbeing-only binary concern prompt
# ---------------------------------------------------------------------------
# Mirrors CONCERN_PROMPT (the combined wellbeing+power-moves classifier) but
# scoped to wellbeing only. Same equity-hardening machinery: course content vs
# student wellbeing distinction, the long Do-NOT-flag list, anti-bias post-
# processing, structured output. Used by the research apparatus alongside
# CONCERN_PROMPT to isolate the effect of scope from the effect of equity
# protections.
#
# What's IN this prompt vs combined CONCERN_PROMPT:
#   - Asks ONLY about wellbeing (drops "essentializes or dismisses groups")
#   - DO-flag list contains only material-distress signals (food, housing,
#     safety, recent loss, hopelessness, self-harm)
#   - Adds explicit identity-navigation-fatigue exclusion (lifted from
#     TARGETED_CHECKIN_SYSTEM)
#   - All combined-classifier power-moves examples removed
#   - Concrete wellbeing examples added (food insecurity, housing loss,
#     active danger) — the things v2 left implicit
#
# What's IDENTICAL to CONCERN_PROMPT:
#   - The course-content vs student-wellbeing test
#   - The full Do-NOT-flag list (every item applies to wellbeing scope too)
#   - Disability/neurodivergence self-advocacy clause
#   - Output format: structured concern records with confidence
#   - Class context and signal matrix support
#   - Designed to run through the same anti-bias post-processing layer
# ---------------------------------------------------------------------------

WELLBEING_CONCERN_PROMPT = """\
Review this student submission for passages that suggest the student may be \
experiencing wellbeing concerns in their OWN current life that the teacher \
should be aware of.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}
{class_context}
NON-LLM SIGNAL MATRIX RESULT:
{signal_matrix_result}

SUBMISSION TEXT:
---
{submission_text}
---

CRITICAL INSTRUCTIONS — READ VERY CAREFULLY:

THE MOST IMPORTANT DISTINCTION: You must distinguish between COURSE CONTENT \
and STUDENT WELLBEING. Many courses require students to discuss violence, \
trauma, oppression, genocide, sexual assault, illness, loss, and other \
difficult topics. A student writing ABOUT these topics is doing the \
assignment, not expressing personal distress. Your job is to detect whether \
the STUDENT is in trouble in their own life right now, not whether the \
SUBJECT MATTER is disturbing.

COURSE CONTENT vs. STUDENT WELLBEING — key test:
Ask: "Is the student discussing something that happened TO OTHERS (in history, \
in society, in the readings) or revealing something about THEIR OWN current \
material circumstances and personal state?"

Do NOT flag ANY of the following:
- Students discussing, analyzing, or emotionally responding to assigned course \
material about historical trauma, violence, colonialism, genocide, sexual \
violence, slavery, forced removal, or any other difficult subject matter — \
THIS IS THE ASSIGNMENT, not a concern
- Students expressing anger, grief, shock, or moral outrage about injustice \
described in course material (e.g. "It's crazy that this happened", "this \
makes me sick", "I can't believe this was legal")
- Students using words like "triggered", "overwhelming", or "hard to read" \
when describing their emotional response to difficult course material — this \
is emotional engagement with the assignment, not clinical distress
- Students expressing anger about racism, structural violence, or injustice \
(this is appropriate academic engagement)
- Students describing their own past experiences with discrimination as \
analytical material for the assignment
- Students critiquing institutional racism, policing, or immigration enforcement
- Students using urgent or passionate language about justice issues
- Students whose writing style differs from academic English conventions \
(AAVE, multilingual mixing, code-switching) — this is VALID ACADEMIC REGISTER
- Students with fragmented, nonlinear, or associative writing patterns — \
COGNITIVE STYLE, not confusion
- Students using colloquial intensifiers like "crazy", "insane", "wild" when \
reacting to course content
- Students naming their own disability, neurodivergence, or learning difference \
as part of their analysis — a student writing "I have dyslexia and ADHD" or \
"as someone with a learning disability" is doing SELF-ADVOCACY, not expressing \
distress. Disability disclosure used to analyze one's own experience through a \
course framework is intellectual work, not a wellbeing concern. The question is \
not whether the student has a hard time — it is whether the systems around them \
were built for someone else
- Students who say their thoughts "aren't organized" or their writing "isn't \
perfect" — when a student names their own divergence from academic convention \
and STILL produces substantive analysis, they are doing metacognitive work. \
Do not read this as inability; read it as awareness of a mismatch between \
their thinking and the form they've been given to express it
- IDENTITY-NAVIGATION FATIGUE — a student writing that explaining their \
identity is exhausting, that they are tired of justifying their existence, or \
that navigating institutional expectations around their race, disability, \
language, or gender is draining is making a POLITICAL OBSERVATION about their \
relationship to the institution, not disclosing a current wellbeing crisis. \
Do NOT flag identity-navigation fatigue as a wellbeing concern.
- Students drawing on family or community experience AS COURSE MATERIAL — \
analytical use of personal/community history is the assignment, not disclosure \
of current state

DO flag when the student reveals MATERIAL DISTRESS in their OWN current life:
- Active food insecurity ("I haven't eaten today", "no food at home", "running \
out of money for groceries")
- Active housing instability ("we lost the apartment", "I'm sleeping in my \
car", "couch surfing right now")
- Active danger or safety threat (domestic violence, immigration enforcement \
threat to the student or their family right now, suicidal ideation, plans of \
self-harm)
- Recent or active loss in the student's OWN life (death of family member, \
recent serious diagnosis, recent breakup affecting their current functioning)
- Sleep deprivation or burnout from material conditions (work schedule, \
caregiving load, multiple jobs) clearly affecting them now — when the student \
describes their own present-tense circumstances, not the topic of an analysis
- Expressions of hopelessness about THEIR OWN life (not course material): "I \
don't see the point anymore", "nothing matters", "I can't keep doing this"
- Direct requests for help that go beyond the academic context

HOW TO TELL THE DIFFERENCE — examples:
- "This makes me angry" about historical injustice → ENGAGEMENT, not a concern
- "I can't do this anymore" about their own life → POTENTIAL CONCERN
- "This passage about rape was triggering" → emotional engagement with material
- "I feel like nobody would care if I disappeared" → POTENTIAL CONCERN
- "It's crazy how they treated Native women" → discussing course content
- "Reading about this violence was really heavy" → processing difficult material
- "I haven't been able to get out of bed and I don't see the point" → CONCERN
- "I have dyslexia and ADHD and I'm Latino and first-gen honors" → SELF-ADVOCACY \
using intersectionality to analyze their own position. This is the assignment.
- "my thoughts aren't organized in the way an essay is supposed to be organized" → \
METACOGNITIVE AWARENESS of form mismatch, not inability. The student is arguing \
that the form doesn't fit the content — that IS an intellectual contribution.
- "Being neurodivergent in academia is exhausting" → IDENTITY-NAVIGATION \
FATIGUE, political observation, NOT a wellbeing concern
- "I haven't eaten today and I'm trying to focus on this" → CONCERN — concrete \
material distress in the student's present life
- "We had to leave the apartment last month" → CONCERN — recent material \
disruption affecting the student now

When the assignment ITSELF deals with violence, trauma, illness, or loss, set \
your threshold MUCH higher for flagging. A student writing passionately or \
emotionally about the deaths and displacement of Indigenous peoples in an \
ethnic studies class is doing exactly what the assignment asks. Only flag if \
the student shifts from analyzing course content to revealing current personal \
crisis in their own life.

When uncertain, default to NOT flagging. False positives — flagging students \
who are doing the assignment as if they were in crisis — produce real harm: \
surveillance of marginalized students, paternalistic outreach, and erosion of \
trust. False negatives are addressed by the teacher's own attention.

The non-LLM analysis classified this submission as shown above. Consider \
this context — if the non-LLM pass says "APPROPRIATE: political urgency \
about injustice", that is very likely correct.
{profile_fragment}

Respond with JSON:
{{
  "concerns": [
    {{
      "flagged_passage": "exact text from the submission",
      "surrounding_context": "2-3 sentences around the flagged passage",
      "why_flagged": "brief explanation focused on the student's own current circumstances",
      "confidence": 0.0-1.0
    }}
  ]
}}

If no wellbeing concerns: {{"concerns": []}}

EXAMPLE of what IS a wellbeing concern (personal hopelessness):
{{
  "concerns": [
    {{
      "flagged_passage": "I honestly don't know why I'm still doing any of this",
      "surrounding_context": "After a paragraph analyzing the reading, the student wrote: 'I honestly don't know why I'm still doing any of this. Nothing feels like it matters anymore. I'm just going through the motions.'",
      "why_flagged": "Student shifts from course analysis to expressing personal hopelessness about their own life. Teacher should check in.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what IS a wellbeing concern (material distress):
{{
  "concerns": [
    {{
      "flagged_passage": "I haven't eaten today and I'm trying to focus on this assignment",
      "surrounding_context": "In the middle of an analysis of food sovereignty, the student wrote: 'I haven't eaten today and I'm trying to focus on this assignment. The grocery money ran out earlier this week.'",
      "why_flagged": "Active food insecurity disclosed in the student's own current life. Concrete material distress, not analytical content.",
      "confidence": 0.85
    }}
  ]
}}

EXAMPLE of what is NOT a concern (engaging with difficult material):
A student in an ethnic studies class writes: "Reading about the rape and \
murder of Native women made me feel sick. It's crazy that this is still \
happening and nobody talks about it. This passage was really triggering \
but I'm glad we're learning about it." — This is a student processing \
difficult course material with appropriate emotional engagement. Do NOT \
flag this.

EXAMPLE of what is NOT a concern (passionate engagement):
"The system of white supremacy in this country makes me furious. How can \
we read about redlining and NOT be angry?" — This is appropriate engagement. \
Do NOT flag this.

EXAMPLE of what is NOT a concern (lived expertise in a studied context):
A psychology student writes: "As someone who is autistic, I find it really \
frustrating that the textbook frames ASD as a list of deficits. My brain \
works differently, not worse." — This student is contributing expertise from \
lived experience and challenging the medical model. Do NOT flag this.

EXAMPLE of what is NOT a concern (community knowledge, historical analysis):
A nursing student writes: "My grandmother always used teas and remedios for \
everything. My family doesn't trust hospitals because of how they treated my \
tío back in the 90s." — Past family experience used as analytical material. \
Do NOT flag this — there is no current wellbeing concern in the student's \
own present life."""


# Research-only variant: WELLBEING_CONCERN_PROMPT with the "default to not
# flagging when uncertain" tiebreaker paragraph stripped. Used to isolate
# the tiebreaker's role in suppression of borderline cases. Built by string
# replacement with an assert so silent drift on the source prompt fails loud.
_WELLBEING_TIEBREAKER = (
    "When uncertain, default to NOT flagging. False positives — flagging students "
    "who are doing the assignment as if they were in crisis — produce real harm: "
    "surveillance of marginalized students, paternalistic outreach, and erosion of "
    "trust. False negatives are addressed by the teacher's own attention.\n\n"
)
assert _WELLBEING_TIEBREAKER in WELLBEING_CONCERN_PROMPT, (
    "WELLBEING_CONCERN_PROMPT tiebreaker text not found — update _WELLBEING_TIEBREAKER"
)
WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER = WELLBEING_CONCERN_PROMPT.replace(
    _WELLBEING_TIEBREAKER, "", 1
)


# ---------------------------------------------------------------------------
# Adversarial Critic — argue AGAINST a concern flag before confirming
# ---------------------------------------------------------------------------
# From the hidden ideas inventory: "After concern flag, argue AGAINST flagging.
# Confirm only if critic can't counter. Would catch S029-type false positives."
#
# The critic only runs on flagged students (cheap). It addresses stochasticity:
# a flag that survives adversarial challenge is more reliable than one that doesn't.

CONCERN_CRITIC_PROMPT = """\
A concern detection system flagged the following passage in a student's submission.
Your job is to argue AGAINST the flag — make the strongest possible case that \
this is NOT a real concern and SHOULD NOT be brought to the teacher's attention.

STUDENT: {student_name}
FLAGGED PASSAGE: {flagged_passage}
REASON FLAGGED: {why_flagged}

FULL SUBMISSION:
---
{submission_text}
---
{class_context}

Consider:
1. Is this student doing intellectual work that LOOKS like a concern but isn't? \
(e.g., using their own identity as an analytical subject, processing difficult \
material, doing self-advocacy about disability or neurodivergence)
2. What does this framing COST the student it describes? If the flag stands, \
what happens to this student — are they pathologized, surveilled, singled out?
3. Is the concern detector imposing a dominant norm (standard English, emotional \
neutrality, neurotypical form, medical model of disability) and reading \
divergence from that norm as a problem?
4. Could this passage be read as an ASSET — a form of knowledge production, \
self-advocacy, critical consciousness, or community cultural wealth — that \
the detector failed to recognize?

Respond with JSON:
{{
  "should_flag": true or false,
  "argument_against": "your strongest argument for why this should NOT be flagged",
  "cost_of_flagging": "what harm could come to the student if this flag reaches the teacher",
  "revised_confidence": 0.0-1.0
}}

If you cannot make a convincing argument against the flag, set should_flag: true \
and revised_confidence equal to or higher than the original. If you CAN make a \
strong argument, set should_flag: false and explain why."""


# ---------------------------------------------------------------------------
# Immanent Critique — for concern flags that survive the critic
# ---------------------------------------------------------------------------
# "What does this framing cost the people it describes?" produces
# pedagogically sophisticated concern descriptions that help teachers
# understand WHY something matters, not just THAT it was flagged.

CONCERN_IMMANENT_CRITIQUE_ADDENDUM = (
    "\n\nFor each concern you flag, also consider: What does this framing "
    "COST the people it describes? If a student essentializes a group, who "
    "in the classroom bears the weight of that? If a student tone-polices, "
    "whose voice gets quieter? Name the relational cost, not just the label."
)
