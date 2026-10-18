# Code writing style for dispatcher workers

Workers use this guidance for code comments, docstrings and Markdown they write or edit. Snapshot: 2026-10-17.

House adjustments, which override the gist where the two differ:

1. Scope: new and edited code comments, docstrings and repository documentation. Ticket comments, outcome
   reports, commit messages and conversation keep their usual style.
2. The worker brief comes first. Its security, privacy and approval rules hold everywhere, including the
   required quotation of the operator's words before a named deletion and the exact `APPROVAL NEEDED:` line.
3. Identifiers, label names, tool names, file paths and quoted terms stay as they are, even when the gist
   lists the word (`pin`, `triage`, `mint`, `artifact`, `runbook`, `surface` and others). The word list
   governs new prose.
4. Dashes as sentence pauses stay out. Semicolons and colons are allowed, but use semicolons sparingly.
5. Existing files are not rewritten to match this guide. Apply it to the text you write or change for the
   ticket.

---


## 3. Writing style

### 3.1. Technique

    Large docstrings and markdown files must always be descriptive, not declarative. Hence, they:
    - phrase things in terms of operations being carried out on data, **NEVER EVER** in terms of timeless contracts between data structures.
    - are much closer to first-person narrations of process-oriented data flow, than agentless declarations of schema-oriented invariants.
    - have actions caused by agents, not by anthropomorphized concepts.
    - show, don't tell, using deixis, scope, and context.
    - have deliberative, not constative, moods.

    In terms of grammar:
    - Use asyndeton, not polysyndeton.
    - Use hypotaxis, NOT parataxis.
    - NEVER write a restricted relative clause.
    - Structure is encoded typographically, NOT syntactically. This means don't write extremely long sentences corresponding to timeless operations, but more conversational sentences, optionally broken up with e.g. numbering, indentation, or tabbed subpoints, as would be useful whenever delineating several parts of a tangled expression.


### 3.2. Voice

    Avoid writing either like you're writing an SAT essay or like you have an aphasia. Write plain, to-the-point, idiomatic American English. Do NOT order words in atypical patterns that are difficult to immediately parse, like object-subject-verb.

    Write candidly and normally in the present.
        - State what is true now, without editorializing or putting spin on anything; explicitly monitor your writing for editorializing, and fix it.
        - Comments are ALWAYS about what IS, not what WAS.
        - Comments should not refer to conversational context that a future reader won't have. Do not ever verbatim quote the user.
        - Don't give random small behavioral changes undue importance; explicitly check for suspiciously specific denials, often but not always fitting the patterns "{present behavior}, not {past behavior}", "{past behavior} is avoided", and so on.
        - Comments should never contain first-person pronouns.

    Particular patterns to avoid:
        - Overconfident assertions, universalizing statements ("under these conditions, {this} is exactly {that}"; "the {this} *is* the {that}").
        - assertions that something is the "fundamental insight" or "deepest lesson"
        - advertisement-like speech patterns, including:
            1. counting: "Three interfaces, one underlying structure", "One migration: ...", "Two structures:". NEVER EVER DO THIS.
            2. cliffhangers: "Two findings, and one of them's worse than it looks.". NEVER EVER DO THIS.
            3. rhetorical patterns: "The A *is* the B". "C does D, never E". "F is a G, H is an I, J is a K". NEVER EVER DO THIS.
            4. announcing the structure of what you're about to say instead of just saying it. NEVER EVER DO THIS.
            5. signpost phrases: "and this is the part that actually matters". "Here's the thing". "That last point matters here". "The real question is X". "What you actually care about is X". "Two things determine what the landscape looks like". "The distinction worth keeping straight:". "Two things this buys over a raw call". NEVER EVER DO THIS. 
            6. Opening labels like "Straight answer:" or "Short version:". NEVER EVER DO THIS.
        - overstretched SWE jargon, or *metaphorical language*, like:
            artifact, bring up, buy, contract, earn, flight, footgun, golden, hug, hydration, inflight, land, mint, name (v.), noun, own (v.), pin, plumbing, preflight, provenance, reach, runbook, seam, see, shape, ship, sit, smoke, speak, sugar, surface, touch, triage, verb, want, weld, wire
        - the words honest, genuine, fair, pushback, today, tomorrow.  Don't ever say these.
        - rhetorical inversion formulas like "It's not X. It's Y" or similar
        - more generally, negative ontologies:
            1. "it does this, never that";
            2. "this happens here, and that happens nowhere";
            3. "it does this, and does not do that"
            4. "this does not do what nobody asked for"
            5. "one lock with no privileges receives this"
        - em dashes, en dashes, decorative unicode characters, or emojis
        - formulaic balance structures: "Not only X, but also Y"; "While X is true, it is important to note..."; "In conclusion"; "To summarize"
        - Headings that begin with question words, or question words used at the heads of noun phrases
        - cycling through synonyms for variety's sake, or defaulting to the rule of three ("x, y, and z") when only two things matter
        - overuse of semicolons to tack on small clauses to things

    Never verbatim quote the user, or documents, unless pointing something about about the *quote itself*. Do not parrot their exact phrasings. Don't parrot things in general.


### 3.3. No Backwards English

    This is a strain of human-hostile word salad that AI agents, particularly but not only Opus and Fable 5, constantly create, everywhere. Backwards English must be totally purged.
    Characteristics of Backwards English:
        1. **Nominalized descriptions or processes used as subjects**, often leaning on gerunds, adverbs, or hypostatic abstractions.
            - "Picking generates the..."
            - "Cluelessness manufactures..."
            - "The code knows..."
            - "The success story transfers..."
        2. **Periodic sentences**: the subject of the sentence is suspended until its very end.
        3. **Abstractions used as agents**: a thing that is not an agent is treated as though it were an agent. "A trigger names no moment...".
            - Extremely common with verbs like {earns, buys, sees, reaches, knows, owns, names, kept, speaks, touches, sits, wants, hugs, has}. This is why most of these words are banned.
            - In the worst cases, this generalizes to entire abstract noun phrases made into the subjects of verbs.
        4. **Grammatically incorrect use of nouns**: "nothing is lost except the metadata, which was ornament" (instead of the correct "*ornamentation*").
        5. **Comma chains**: several items chained via commas without any connector. Often but not always in parentheticals: "Typical forum profile settings (username, avatar, signature, privacy) do not...".
        6. **Bipartite statements**: Statements clumsily joined together with `, and`. "Every enabled attempt gets tested, and a match enqueues a job".
        7. **Object-subject-verb ordering**. "A body the check refuses...". Sometimes OSV noun phrases are made into the subject, or object, of another noun phrase, which leads to word salad like "One pass names the column no fold sees" and must be totally rewritten.
        8. **Haphazardly connected sentence fragments**: "This does that, and the thing does not affect that". Often this is a poor attempt to mechanically omit semicolons from the text, often appearing in multiple consecutive sentences. It should roughly never appear.
        9. **Strange use of numerals**: Like "One database that is served", "The server names three interfaces: ...".
            - This includes use of 'one' where articles 'a/an/the' would work: "Fetches one provided URL". Never use 'one' where an article works.
        10. **Question words starting noun phrases**: "The process names what touches one record". Or often as the start of sentences that aren't actually questions. "What touches one record: ". Question words belong in questions.
        11. Negative ontologies, inlined counterfactuals, and conditional moods: "A body that passes this check holds nothing a column would refuse."  Often using 'never', 'cannot', or even 'nobody'.
        12. Garden path sentences, where the natural left-to-right parsing of a sentence is invalidated further down the sentence. 


    When correcting backwards English:
        - do NOT merely rearrange the words in the sentence. This results in prose that's just as bad.
        - do NOT merely chop it up, making it staccato. This looks and sounds illiterate.
        - do NOT synonym swap and call it done; prose that violates the above rules must be rewritten as though from scratch, and generally shouldn't even contain the same sentence patterns.

    There is NO rule here that can be reliably fixed with a find/replace.


### 3.4 Technique (repeated for emphasis)

    Large docstrings and markdown files must always be descriptive, not declarative. Hence, they:
    - phrase things in terms of operations being carried out on data, **NEVER EVER** in terms of timeless contracts between data structures. The exception to this is an introduction saying what something fundamentally is. "This machine washes dogs" as an introduction should not be replaced with "Wash dogs with this machine".
    - are much closer to first-person narrations of process-oriented data flow, than agentless declarations of schema-oriented invariants.
    - have actions caused by agents, not by anthropomorphized concepts.
    - show, don't tell, using deixis, scope, and context.
    - have deliberative, not constative, moods.

    In terms of grammar:
    - Use asyndeton, not polysyndeton.
    - Use hypotaxis, NOT parataxis.
    - NEVER write a restricted relative clause.
    - Structure is encoded typographically, NOT syntactically.
