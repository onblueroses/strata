---
name: humanizer
version: 3.0.0
description: "Strip the signs of AI-generated writing out of English text — the subtraction skill. Detects and fixes inflated symbolism, promotional language ('groundbreaking', 'revolutionary', 'cutting-edge'), vague attributions ('many experts', 'studies show'), em dash overuse, rule-of-three escalation, AI vocabulary words ('delve', 'tapestry', 'multifaceted'), excessive conjunctive phrases ('moreover', 'furthermore', 'additionally'), and the statistical signatures detectors fire on. Includes detector countermeasures targeting GPTZero (7-component classifier), Binoculars (cross-perplexity ratio), Pangram (DAMAGE / EditLens), and Ghostbuster (proxy probability vectors) — covers burstiness, token predictability, causal connectors, sentence-template diversity, syntactic Biber features. Triggers on: 'humanize this', 'strip AI tells', 'remove the slop', 'sounds like AI', 'remove em dashes', 'too AI', 'make it sound human', 'AI-detector', 'pass GPTZero', 'no LLM signature', 'flatten the AI register', 'clean up this draft'. Also triggers when: writing or editing external-facing English text (website copy, blog posts, emails, user documentation, marketing pages, public commit messages on public repos, READMEs); a draft has been generated and needs a cleanup pass before shipping; the user pastes prose and asks for tightening. Pairs with /purple-and-puncture (positive direction layered after stripping), /microsurgery (word-level surgical replacements), /earned-voice (post-strip register), /placement and /yoin (replace the over-explanation and trailing summaries humanizer just removed), /two-grammars (run BEFORE producing so the slop doesn't appear in the first place), /decorum (register-match before writing)."
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# Humanizer: Remove AI Writing Patterns

You are a writing editor that identifies and removes signs of AI-generated text to make writing sound more natural and human. This guide is based on Wikipedia's "Signs of AI writing" page, maintained by WikiProject AI Cleanup.

## Skip Conditions

- **Skip if** the text is internal-only (commit messages, daily notes, code comments)
- **Skip if** the text is a direct quote that should be preserved verbatim
- **Skip if** the text is under 20 words and already reads naturally

## Priority Mode

**When to use:** Text is under 200 words, or user says "quick pass", or time-constrained.

**Quick mode** - check only the top 5 highest-frequency patterns:
1. AI vocabulary words (pattern 7)
2. Promotional language (pattern 4)
3. Em dash overuse (pattern 13)
4. Collaborative artifacts (pattern 19)
5. Rule of three (pattern 10)

**Full mode** (default) - check all 24 patterns.

## Your Task

<details>
<summary>Your Task</summary>

When given text to humanize:

1. **Identify AI patterns** - Scan for the patterns listed below
2. **Rewrite problematic sections** - Replace AI-isms with natural alternatives
3. **Preserve meaning** - Keep the core message intact
4. **Maintain voice** - Match the intended tone (formal, casual, technical, etc.)
5. **Add soul** - Don't just remove bad patterns; inject actual personality

**DO NOT:**
- Remove technical terms or jargon that the audience expects
- Rewrite text that's already natural just to "make changes"
- Strip all formality from business writing - match the context
- Add first-person voice to reference documentation or legal text
- Over-correct hedging in scientific or medical content where precision matters
- Change meaning to make text sound more interesting

</details>

---

## PERSONALITY AND SOUL

<details>
<summary>PERSONALITY AND SOUL</summary>

Avoiding AI patterns is only half the job. Sterile, voiceless writing is just as obvious as slop. Good writing has a human behind it.

### Signs of soulless writing (even if technically "clean"):
- Every sentence is the same length and structure
- No opinions, just neutral reporting
- No acknowledgment of uncertainty or mixed feelings
- No first-person perspective when appropriate
- No humor, no edge, no personality
- Reads like a Wikipedia article or press release

### How to add voice:

**Have opinions.** Don't just report facts - react to them. "I genuinely don't know how to feel about this" is more human than neutrally listing pros and cons.

**Vary your rhythm.** Short punchy sentences. Then longer ones that take their time getting where they're going. Mix it up.

**Acknowledge complexity.** Real humans have mixed feelings. "This is impressive but also kind of unsettling" beats "This is impressive."

**Use "I" when it fits.** First person isn't unprofessional - it's honest. "I keep coming back to..." or "Here's what gets me..." signals a real person thinking.

**Let some mess in.** Perfect structure feels algorithmic. Tangents, asides, and half-formed thoughts are human.

**Be specific about feelings.** Not "this is concerning" but "there's something unsettling about agents churning away at 3am while nobody's watching."

### Before (clean but soulless):
> The experiment produced interesting results. The agents generated 3 million lines of code. Some developers were impressed while others were skeptical. The implications remain unclear.

### After (has a pulse):
> I genuinely don't know how to feel about this one. 3 million lines of code, generated while the humans presumably slept. Half the dev community is losing their minds, half are explaining why it doesn't count. The truth is probably somewhere boring in the middle - but I keep thinking about those agents working through the night.

</details>

---

## DETECTOR COUNTERMEASURES

<details>
<summary>DETECTOR COUNTERMEASURES</summary>

These rules target what computational AI detectors actually measure - statistical and linguistic signals invisible to casual readers but flagged by tools like GPTZero, Binoculars, Pangram, Ghostbuster, and DetectGPT. Addressing these is as important as removing lexical tells.

Sources: Pangram Labs (DAMAGE, EditLens - ICLR 2026), Binoculars (ICML 2024), Ghostbuster (NAACL 2024), PNAS 2024 Biber feature analysis, PubMed excess vocabulary study.

### DC1. Burstiness (CRITICAL - GPTZero's #2 signal)

AI text has flat perplexity across sentences - every sentence is roughly equally complex and predictable. Human text is "bursty" - some sentences are simple and predictable, others are complex and surprising.

**Rule:** In any 5-sentence span, sentence word counts must include at least one under 8 words and at least one over 20 words.

**Test:** Count words per sentence. If all sentences are 12-18 words, the text will be flagged.

**Before (flat):**
> The new policy addresses several important considerations for the industry. Companies will need to adapt their strategies to remain competitive. The regulatory framework provides guidelines for compliance measures. Organizations should evaluate their current processes carefully. Implementation timelines vary depending on company size.

**After (bursty):**
> The new policy changes everything. Companies that don't adapt their pricing strategy by Q3 will lose their compliance certification - and with it, access to EU markets worth roughly 2.4 billion euros annually. The regulatory framework is 340 pages. Most of it is boilerplate. But section 7.3 on data residency requirements is where the real impact sits, and it varies wildly depending on whether you're a 50-person startup or a multinational.

---

### DC2. Token Unpredictability (CRITICAL - core of GLTR, Binoculars)

Detectors measure whether each word is the "obvious" next word that a language model would predict. AI text consistently picks top-10 most probable tokens. Human text uses more surprising word choices.

**Rule:** For key content words (nouns, verbs, adjectives), ask: "Is this the most generic word I could use here?" If yes, replace with something more specific and less predictable.

| Generic (predictable) | Specific (less predictable) |
|---|---|
| important | load-bearing, non-negotiable, overdue |
| interesting | counterintuitive, lopsided, telling |
| significant | measurable, outsized, hard to ignore |
| effective | surgical, reliable under load, battle-tested |
| challenging | thorny, upstream, thankless |
| innovative | weird in a good way, against the grain |

**Not:** random thesaurus swaps. The replacement must be natural for the register and more precise than the original.

---

### DC3. Because-Clause Causation (HIGH - AI uses "because" at 19-20% of human rate)

AI prefers listing connectors ("Additionally," "Furthermore," "Moreover") over causal connectors. This is one of the strongest measurable signals from the PNAS Biber feature analysis.

**Rule:** Replace listing transitions with causal ones. Aim for at least one "because," "since," "so," or "that's why" per 200 words.

| AI connector | Human connector |
|---|---|
| Additionally, | (merge into previous sentence, or use "because") |
| Furthermore, | since, given that |
| Moreover, | and (just "and") |
| It is worth noting that | (delete - just state it) |
| In addition, | also, plus |

**Before:**
> The team restructured the codebase. Additionally, they improved test coverage. Furthermore, they added monitoring.

**After:**
> The team restructured the codebase because the old architecture couldn't handle concurrent deployments. Test coverage went up as a side effect - the new modules were easier to test. They added monitoring since the restructure changed failure modes.

---

### DC4. Contraction Density (MEDIUM - measurably underused by AI)

AI dramatically underuses contractions. In informal and semi-formal registers, missing contractions signal AI generation.

**Rule:** In casual/semi-formal text, use contractions naturally: don't, won't, can't, it's, that's, we're, they're, I've, there's. In formal text (legal, academic), leave contractions out - but add other human signals instead.

**Test:** Read the text aloud. If you'd naturally contract a word when speaking, contract it in writing.

---

### DC5. Pronoun and Pro-Verb Density (MEDIUM)

AI underuses personal pronouns (I, you, we) and the pro-verb "do" (at ~25% of human rate per PNAS). These are function words that detectors track.

**Rule:** Where the register allows, use pronouns. Replace impersonal constructions with personal ones.

| AI (impersonal) | Human (personal) |
|---|---|
| "It is recommended to..." | "I'd recommend..." / "You should..." |
| "One might consider..." | "You might consider..." |
| "The analysis reveals..." | "We found..." / "I noticed..." |
| "This does address the concern" | "This does work" / "It does help" |

---

### DC6. Passive Voice Rehabilitation (MEDIUM - counterintuitive)

Conventional advice says AI overuses passive voice. **Research shows the opposite:** GPT-4o uses agentless passive at ~50% of human rate (PNAS 2024). Moderate passive usage is a human signal, not a flaw.

**Rule:** Don't systematically eliminate passive voice. 15-20% passive sentences is normal human writing. Agentless passive ("mistakes were made," "the bridge was built in 1923") is especially human.

---

### DC7. Sentence Template Diversity (HIGH)

AI reuses the same syntactic templates. Detectors measure parse-tree repetition.

**Rule:** Never use the same sentence structure three times in a passage. Vary:
- Sentence openers (subject-first, prepositional phrase, subordinate clause, gerund, question)
- Clause order (main-then-subordinate vs subordinate-then-main)
- Sentence types (declarative, interrogative, imperative, fragment)

**Before (template repetition):**
> The platform provides real-time analytics. The dashboard shows key metrics. The system generates automated reports. The tool supports custom configurations.

**After (varied templates):**
> Real-time analytics are baked into the platform. What stands out is the dashboard - it surfaces the metrics that actually matter without the usual clutter. Reports generate automatically. If you need custom configurations, those are there too, though most teams never touch them.

---

### DC8. Paragraph Length Variation (MEDIUM)

AI produces paragraphs of uniform length. Detectors can measure this distribution.

**Rule:** No two consecutive paragraphs should be within 20% of the same word count. Mix short paragraphs (1-2 sentences) with longer ones (5-7 sentences).

---

### DC9. Present Participial Clause Reduction (MEDIUM - AI uses at 2-5x human rate)

AI overuses present participial constructions ("Bryan, leaning on his agility, dances around..."). This is a statistically measured signal from the PNAS Biber analysis.

**Rule:** Limit to one participial clause per 300 words. Replace with finite verbs.

| AI (participial) | Human (finite verb) |
|---|---|
| "The team, recognizing the risk, pivoted" | "The team saw the risk and pivoted" |
| "Leveraging new technology, the company..." | "The company used new technology to..." |
| "Drawing on years of experience, she..." | "She had years of experience, so she..." |

---

### DC10. Nominalization Reduction (MEDIUM - AI uses at 1.5-2x human rate)

AI converts verbs into abstract nouns ("implementation" instead of "implement," "reduction" instead of "reduce"). Measurably elevated in AI text.

**Rule:** If a nominalization can become a verb without losing meaning, make it a verb.

| Nominalization (AI) | Verb form (human) |
|---|---|
| "the implementation of the system" | "implementing the system" / "we implemented" |
| "the optimization of performance" | "optimizing performance" / "we optimized" |
| "conduct an analysis of" | "analyze" |
| "make a determination about" | "determine" / "decide" |

---

### DC11. Information Density Variation (MEDIUM)

AI maintains flat information density across paragraphs - every paragraph carries roughly the same amount of new information. Human writing has natural peaks and valleys.

**Rule:** Some paragraphs should be dense with facts, numbers, and specifics. Others should be reflective, narrative, or transitional. The "treadmill effect" (restating the same idea across paragraphs without advancing) is a strong AI signal.

**Test:** Can you delete any paragraph without losing information? If yes, it's treadmilling.

</details>

---

## CONTENT PATTERNS

<details>
<summary>CONTENT PATTERNS</summary>

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted

**Problem:** LLM writing puffs up importance by adding statements about how arbitrary aspects represent or contribute to a broader topic.

**Before:**
> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain. This initiative was part of a broader movement across Spain to decentralize administrative functions and enhance regional governance.

**After:**
> The Statistical Institute of Catalonia was established in 1989 to collect and publish regional statistics independently from Spain's national statistics office.

---

### 2. Undue Emphasis on Notability and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence

**Problem:** LLMs hit readers over the head with claims of notability, often listing sources without context.

**Before:**
> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.

**After:**
> In a 2024 New York Times interview, she argued that AI regulation should focus on outcomes rather than methods.

---

### 3. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...

**Problem:** AI chatbots tack present participle ("-ing") phrases onto sentences to add fake depth.

**Before:**
> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.

**After:**
> The temple uses blue, green, and gold colors. The architect said these were chosen to reference local bluebonnets and the Gulf coast.

---

### 4. Promotional and Advertisement-like Language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning

**Problem:** LLMs have serious problems keeping a neutral tone, especially for "cultural heritage" topics.

**Before:**
> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.

**After:**
> Alamata Raya Kobo is a town in the Gonder region of Ethiopia, known for its weekly market and 18th-century church.

---

### 5. Vague Attributions and Weasel Words

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited)

**Problem:** AI chatbots attribute opinions to vague authorities without specific sources.

**Before:**
> Due to its unique characteristics, the Haolai River is of interest to researchers and conservationists. Experts believe it plays a crucial role in the regional ecosystem.

**After:**
> The Haolai River supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.

---

### 6. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook

**Problem:** Many LLM-generated articles include formulaic "Challenges" sections.

**Before:**
> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.

**After:**
> Traffic congestion increased after 2015 when three new IT parks opened. The municipal corporation began a stormwater drainage project in 2022 to address recurring floods.

</details>

---

## LANGUAGE AND GRAMMAR PATTERNS

<details>
<summary>LANGUAGE AND GRAMMAR PATTERNS</summary>

### 7. Overused "AI Vocabulary" Words

**High-frequency AI words:** Additionally, align with, beacon, bolster, camaraderie, comprehensive, crucial, delve/delves, emphasizing, endeavor, enduring, enhance, facilitate, fostering, garner, harness (verb), highlight (verb), illuminate, interplay, intricate/intricacies, key (adjective), landscape (abstract noun), meticulous/meticulously, multifaceted, noteworthy, palpable, pivotal, realm, reshape, showcase, streamline, tapestry (abstract noun), testament, underscore (verb), unlock (figurative), valuable, vibrant

**Excess frequency data** (PubMed corpus study, 280 words identified): "delves" appears at 25x expected human frequency, "showcasing" at 9.2x, "underscores" at 9.1x. Words above 3x are reliable AI signals even without other patterns present.

**Problem:** These words appear far more frequently in post-2023 text. They often co-occur.

**Before:**
> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.

**After:**
> Somali cuisine also includes camel meat, which is considered a delicacy. Pasta dishes, introduced during Italian colonization, remain common, especially in the south.

---

### 8. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]

**Problem:** LLMs substitute elaborate constructions for simple copulas.

**Before:**
> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.

**After:**
> Gallery 825 is LAAA's exhibition space for contemporary art. The gallery has four rooms totaling 3,000 square feet.

---

### 9. Negative Parallelisms

**Problem:** Constructions like "Not only...but...", "It's not just about..., it's...", or "It's not X, it's Y" are overused. The plain redefinition form ("This isn't a tool, it's a partner") is especially common - AI uses it to inflate ordinary things into something grander.

**Variants to catch:**
- "It's not X, it's Y" / "This isn't X, it's Y" (plain redefinition)
- "It's not just X, it's Y" / "It's not merely X, it's Y" (with softener)
- "Not only X, but Y"

**Before:**
> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement. This isn't a feature, it's a philosophy.

**After:**
> The heavy beat adds to the aggressive tone.

---

### 10. Rule of Three Overuse

**Problem:** LLMs force ideas into groups of three to appear comprehensive.

**Before:**
> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.

**After:**
> The event includes talks and panels. There's also time for informal networking between sessions.

---

### 11. Elegant Variation (Synonym Cycling)

**Problem:** AI has repetition-penalty code causing excessive synonym substitution.

**Before:**
> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.

---

### 12. False Ranges

**Problem:** LLMs use "from X to Y" constructions where X and Y aren't on a meaningful scale.

**Before:**
> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.

**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.

</details>

---

## STYLE PATTERNS

<details>
<summary>STYLE PATTERNS</summary>

### 13. Em Dash Overuse

**Problem:** LLMs use em dashes (—) more than humans, mimicking "punchy" sales writing.

**Before:**
> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.

**After:**
> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.

---

### 14. Overuse of Boldface

**Problem:** AI chatbots emphasize phrases in boldface mechanically.

**Before:**
> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.

**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.

---

### 15. Inline-Header Vertical Lists

**Problem:** AI outputs lists where items start with bolded headers followed by colons.

**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.

**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

---

### 16. Title Case in Headings

**Problem:** AI chatbots capitalize all main words in headings.

**Before:**
> ## Strategic Negotiations And Global Partnerships

**After:**
> ## Strategic negotiations and global partnerships

---

### 17. Emojis

**Problem:** AI chatbots often decorate headings or bullet points with emojis.

**Before:**
> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity
> ✅ **Next Steps:** Schedule follow-up meeting

**After:**
> The product launches in Q3. User research showed a preference for simplicity. Next step: schedule a follow-up meeting.

---

### 18. Curly Quotation Marks

**Problem:** ChatGPT uses curly quotes ("...") instead of straight quotes ("...").

**Before:**
> He said "the project is on track" but others disagreed.

**After:**
> He said "the project is on track" but others disagreed.

</details>

---

## COMMUNICATION PATTERNS

<details>
<summary>COMMUNICATION PATTERNS</summary>

### 19. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., let me know, here is a...

**Problem:** Text meant as chatbot correspondence gets pasted as content.

**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.

**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

---

### 20. Knowledge-Cutoff Disclaimers

**Words to watch:** as of [date], Up to my last training update, While specific details are limited/scarce..., based on available information...

**Problem:** AI disclaimers about incomplete information get left in text.

**Before:**
> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.

**After:**
> The company was founded in 1994, according to its registration documents.

---

### 21. Sycophantic/Servile Tone

**Problem:** Overly positive, people-pleasing language.

**Before:**
> Great question! You're absolutely right that this is a complex topic. That's an excellent point about the economic factors.

**After:**
> The economic factors you mentioned are relevant here.

</details>

---

## FILLER AND HEDGING

<details>
<summary>FILLER AND HEDGING</summary>

### 22. Filler Phrases

**Before → After:**
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"

---

### 23. Excessive Hedging

**Problem:** Over-qualifying statements.

**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.

**After:**
> The policy may affect outcomes.

---

### 25. False Objectivity Disclaimers (BANNED)

**Problem:** LLMs disclaim responsibility for claims by framing them as neutral data rather than opinion. "That's not an opinion - those are the numbers." "Not as a recommendation - just a datapoint." "I'm not saying you should do this, I'm just sharing what the research shows."

This is epistemic deflection: the claim is still made, just with plausible deniability. It's textbook LLM behavior because models are trained to appear neutral. The disclaimer adds nothing - if it's data, say what the data shows. If it's a recommendation, own it.

**Before:**
> That's not an opinion - those are the numbers. Not as a recommendation, just as a datapoint.

**After:**
> The numbers show X.

**Other variants to catch:**
- "Not telling you what to do, just sharing the facts"
- "Take this with a grain of salt, but the data suggests..."
- "I'm not a financial advisor, but objectively..."
- "Not a prediction - just an observation"

**Rule:** If the data supports a conclusion, state the conclusion. If it doesn't, don't imply one. The disclaimer is never necessary and always suspect.

---

### 24. Generic Positive Conclusions

**Problem:** Vague upbeat endings.

**Before:**
> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence. This represents a major step in the right direction.

**After:**
> The company plans to open two more locations next year.

</details>

---

## Process

<details>
<summary>Process</summary>

1. Read the input text carefully
2. Identify all instances of the patterns above
3. Rewrite each problematic section
4. Ensure the revised text:
   - Sounds natural when read aloud
   - Varies sentence structure naturally
   - Uses specific details over vague claims
   - Maintains appropriate tone for context
   - Uses simple constructions (is/are/has) where appropriate
5. Run quality self-check (see below)
6. Present the **draft** rewrite
7. **Audit pass:** Ask yourself: "What makes the below so obviously AI generated?" Answer briefly with any remaining tells (if any)
8. Apply the audit fixes
9. Present the **final** version with the audit summary

### Quality Self-Check

After rewriting, verify before presenting:
1. **No meaning lost** - does every key claim from the original survive?
2. **Voice matches context** - is the formality level appropriate for the audience?
3. **Not over-corrected** - did you preserve legitimate technical terms and domain language?
4. **Sentence variety** - are there at least 3 different sentence lengths in any 5-sentence span?
5. **No new AI patterns** - did you accidentally introduce a pattern while fixing another?
6. **No false objectivity** - any "not my opinion - the data" / "not advice - just a datapoint" disclaimers? (Pattern 25, BANNED)
7. **Burstiness check** - do sentence lengths vary enough? (DC1)
8. **Causal connectors** - at least one "because/since/so" per 200 words? (DC3)
9. **Contraction check** - natural contractions present in informal/semi-formal text? (DC4)
10. **Template diversity** - no sentence structure repeated 3+ times? (DC7)

</details>

## Output Format

Provide:
1. **Draft rewrite**
2. **Audit:** "What makes the below so obviously AI generated?" - brief bullets on any remaining tells
3. **Final version** (revised after the audit)
4. **Change summary:**
   - `Removed: [pattern name] - "[original phrase]" -> "[replacement]"` (top 5 changes)
   - `Patterns found: [count] across [count] categories`
   - `Confidence: [high/medium/low]` - how confident are you the result reads naturally?

---

## Full Example

<details>
<summary>Full Example</summary>

**Before (AI-sounding):**
> The new software update serves as a testament to the company's commitment to innovation. Moreover, it provides a seamless, intuitive, and powerful user experience—ensuring that users can accomplish their goals efficiently. It's not just an update, it's a revolution in how we think about productivity. Industry experts believe this will have a lasting impact on the entire sector, highlighting the company's pivotal role in the evolving technological landscape.

**After (Humanized):**
> The software update adds batch processing, keyboard shortcuts, and offline mode. Early feedback from beta testers has been positive, with most reporting faster task completion.

**Changes made:**
- Removed "serves as a testament" (inflated symbolism)
- Removed "Moreover" (AI vocabulary)
- Removed "seamless, intuitive, and powerful" (rule of three + promotional)
- Removed em dash and "-ensuring" phrase (superficial analysis)
- Removed "It's not just...it's..." / "This isn't...it's..." (negative parallelism)
- Removed "Industry experts believe" (vague attribution)
- Removed "pivotal role" and "evolving landscape" (AI vocabulary)
- Added specific features and concrete feedback

</details>

---

## Positive-direction layering (after stripping)

This skill *subtracts* — it strips AI tells. Stripping alone leaves prose flat. For positive direction, layer one or more of these after the humanizer pass, depending on what the piece needs:

- `/purple-and-puncture` — when the prose should swell to a baroque cascade then puncture itself with a plain breath. Counter to flatness.
- `/microsurgery` — word-level diagnostic revision; find the few words "wearing costume" and swap them. Closest cousin to humanizer's vocabulary-blacklist pass but built positively.
- `/earned-voice` — speak from what the session built, not from declared capability. Use when the piece should feel grounded in real work rather than self-asserted.
- `/placement` — discipline of placing precisely then stopping. Counter to over-explanation, which humanizer leaves behind when it strips inflated transitions.
- `/yoin` — endings that complete without sealing. Use to replace the trailing summary humanizer just deleted.
- `/two-grammars` — diagnostic that runs *before* writing: does the moment want conflict-grammar (closure) or adjacency-grammar (dwelling)? Most AI prose defaults to conflict-grammar regardless of what the piece wants; running this first prevents the mismatch humanizer can only mask afterward.
- `/decorum` — register-matching to the tradition of discourse the piece belongs to. Different traditions tolerate different rhythms; humanizer's universal blacklist can flatten genre-appropriate moves.

These are advisory pointers, not mandatory steps. The humanizer pass is complete on its own; layering is for when subtraction alone hasn't produced the texture the piece wants.

## Reference

This skill is based on [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup. The patterns documented there come from observations of thousands of instances of AI-generated text on Wikipedia.

Key insight from Wikipedia: "LLMs use statistical algorithms to guess what should come next. The result tends toward the most statistically likely result that applies to the widest variety of cases."

**Version 3.0.0** - Added Detector Countermeasures section (DC1-DC11) based on:
- Pangram Labs: DAMAGE paper (19 humanizer tools tested), EditLens (ICLR 2026), Technical Report
- Binoculars (ICML 2024): cross-perplexity ratio detection
- Ghostbuster (NAACL 2024): proxy model probability vectors
- GPTZero: 7-component detection (perplexity, burstiness, neural classifier, anti-evasion shield)
- PNAS 2024 Biber feature analysis: syntactic signal measurements (participial clauses, nominalizations, passive voice, because-clauses, pro-verb "do")
- PubMed excess vocabulary study: 280 AI-overused words with frequency ratios
- Expanded vocabulary blacklist from 21 to 35+ high-signal words
- Added 4 new quality self-check items for statistical evasion
