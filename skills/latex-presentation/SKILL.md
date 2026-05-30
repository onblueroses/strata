---
name: latex-presentation
description: |
  Create distinctive, publication-grade LaTeX Beamer presentations with professional chart design.
  Auto-trigger: when creating or editing LaTeX Beamer presentations, pgfplots charts, or academic slides. Provides color system, chart styling, typography, layout, and speaker notes guidance. Targets PhD-defense / McKinsey-deck quality.
license: Internal
---

## Skip Conditions

- **Skip if** the task is not LaTeX/Beamer related
- **Skip if** editing a single chart value or fixing a typo - no design guidance needed
- **Skip if** the user explicitly wants a quick draft with no styling concern

## Priority Mode

**Quick mode:** Apply only Color System + Chart Styling + Anti-Patterns. Skip layout, notes, and full design thinking.

**Full mode (default):** Complete design thinking + all sections. Use for new presentations, significant redesigns, or full rewrites.

---

This skill guides creation of publication-grade LaTeX Beamer presentations that look like a team of researchers spent weeks polishing them. Every chart fills the frame. Every color is intentional. Every font size is optimized for projection at 3+ meters.

## Design Thinking

<details>
<summary>Design Thinking</summary>

Before writing LaTeX, commit to the presentation's visual identity:

- **Purpose**: What is this presentation doing? Teaching, persuading, reporting?
- **Audience**: Technical peers, students, executives? This sets information density.
- **Tone**: Academic authority, casual expertise, corporate precision?
- **Chart density**: How many chart slides vs text slides? (Aim for 70%+ chart/visual slides)
- **One rule**: Every slide has ONE job. If you're explaining two things, you need two slides.

**The test**: Print any slide at 50% size. Can you still read everything? If not, there's too much on it.

</details>

---

## Color System

<details>
<summary>Color System</summary>

Commit to a refined palette. Academic presentations use deep, muted tones - never primary RGB colors.

### Recommended Palette: Dark Professional

```latex
% Primary palette - sophisticated, high-contrast on white
\definecolor{primary}{HTML}{1B2A4A}      % Near-black navy (titles, frame bg)
\definecolor{accent}{HTML}{2E6DB4}       % Professional blue (highlights, links)
\definecolor{success}{HTML}{1D7A4B}      % Forest green (positive data)
\definecolor{warning}{HTML}{B8860B}      % Dark goldenrod (caution, mid-range)
\definecolor{danger}{HTML}{A63D2F}       % Burnt sienna (negative data, alerts)
\definecolor{muted}{HTML}{6B7280}        % Neutral gray (secondary text)
\definecolor{lightbg}{HTML}{F8F9FB}      % Near-white (card backgrounds)
\definecolor{cardbg}{HTML}{EAECF0}       % Light gray (alternating rows)
```

### Chart Series Colors (6 distinguishable, muted)

```latex
% For multi-series charts - ordered by visual weight
\definecolor{series1}{HTML}{2E5090}      % Deep blue
\definecolor{series2}{HTML}{A63D2F}      % Burnt red
\definecolor{series3}{HTML}{1D7A4B}      % Forest green
\definecolor{series4}{HTML}{B8860B}      % Dark gold
\definecolor{series5}{HTML}{6B4C9A}      % Muted purple
\definecolor{series6}{HTML}{0E7C7B}      % Dark teal
```

### Category Colors (Western vs Chinese models)

```latex
\definecolor{western}{HTML}{2E5090}      % Deep blue
\definecolor{chinese}{HTML}{A63D2F}      % Burnt red
```

### Beamer Color Assignments

```latex
\setbeamercolor{palette primary}{bg=primary, fg=white}
\setbeamercolor{frametitle}{bg=primary, fg=white}
\setbeamercolor{title separator}{fg=accent}
\setbeamercolor{progress bar}{fg=accent, bg=primary!15}
\setbeamercolor{alerted text}{fg=danger}
\setbeamercolor{example text}{fg=success}
```

### Banned Colors

- Pure red (#FF0000), blue (#0000FF), green (#00FF00) - childish, screaming
- Bright orange (#FFA500) - screams "warning dialog"
- Any neon or fluorescent color
- Default pgfplots cycle list colors
- PowerPoint template colors

</details>

---

## Typography

<details>
<summary>Typography</summary>

### Font Hierarchy for 16:9 Projection

```
Slide title:      Handled by metropolis (\Large, ~14pt) - keep SHORT
Subtitle/desc:    \small\color{muted} - one line only, on chart slides this goes in notes
Chart axis:       \small (11pt) minimum - must read at 3m
Chart ticks:      \footnotesize (10pt) minimum
Data labels:      \scriptsize (8pt) - direct on data points
Speaker notes:    \small - dense is fine, only presenter sees
Body text:        \small to \normalsize - rare on slides
Stat numbers:     \Large\bfseries - big, bold, colored for emphasis
```

### Font Size Rules

- **NEVER** use \tiny on anything projected. It's invisible at 2m.
- **\scriptsize** is the absolute minimum for chart data labels.
- **Frame titles**: 3-5 words maximum. "GPQA Diamond" not "GPQA Diamond Benchmark Results Over Time".
- **If you need smaller text to fit content**, you have too much content. Move it to notes.

### Metropolis Theme Setup

```latex
\usetheme{metropolis}
\metroset{
  titleformat=regular,         % Not ALL CAPS
  sectionpage=progressbar,     % Progress bar on section dividers
  numbering=fraction,          % "3/22" format
  progressbar=frametitle,      % Thin line under frame titles
  block=fill,                  % Filled block backgrounds
}
```

</details>

---

## Chart Design

<details>
<summary>Chart Design</summary>

Charts are the presentation. They fill the frame. They speak for themselves.

### Global pgfplots Configuration

Put this in the preamble. Every chart inherits it.

```latex
\pgfplotsset{
  compat=1.18,
  every axis/.append style={
    axis line style={draw=black!20, line width=0.4pt},
    tick style={draw=black!20, thin},
    grid=major,
    grid style={draw=black!6, line width=0.25pt},
    tick label style={font=\footnotesize, color=black!65},
    label style={font=\small, color=black!55},
    legend style={
      draw=none, fill=white, fill opacity=0.9, text opacity=1,
      font=\footnotesize, inner sep=3pt, row sep=2pt,
    },
  },
}
```

### Chart Sizing: Fill the Frame

For 16:9 Beamer with frame title:

```latex
% Standard: chart with frame title
width=14.5cm, height=7.0cm

% Tight: frame title + one-line subtitle
width=14.5cm, height=6.5cm

% Maximum: plain frame, no title
width=15.5cm, height=8.5cm
```

**The rule**: A chart that doesn't fill at least 80% of the frame area is too small. If you're putting a chart in a column layout, stop. Give it the full frame.

### Line Charts (Progress Curves, Time Series)

```latex
\begin{frame}{Kurzer Titel}
\begin{center}
\begin{tikzpicture}
  \begin{axis}[
    width=14.5cm, height=7.0cm,
    xmin=2022.8, xmax=2026.5,
    ymin=0, ymax=105,
    xtick={2023, 2024, 2025, 2026},
    xticklabel style={font=\small, /pgf/number format/1000 sep={}},
    ylabel={Score (\%)},
    ylabel style={font=\small, color=black!55},
    yticklabel style={font=\small},
    grid=major,
    grid style={draw=black!6},
    axis line style={draw=black!20},
    tick style={draw=black!20},
  ]
    % Primary line - thick, solid markers
    \addplot[
      series1, very thick, mark=*, mark size=3.5pt,
      mark options={fill=series1, draw=series1!70!black, line width=0.3pt},
      smooth, tension=0.4,
    ] coordinates {
      (2023.25, 36) (2024.25, 60) (2024.75, 78) (2026.15, 91.3)
    };

    % Direct labels (not legends) - positioned to avoid overlap
    \node[above right, font=\scriptsize, text=black!55]
      at (axis cs:2023.25, 36) {GPT-4};
    \node[above left, font=\scriptsize\bfseries, text=series1]
      at (axis cs:2026.15, 91.3) {91,3\%};

    % Baseline reference line
    \draw[dashed, black!25, thin]
      (axis cs:2022.8, 34) -- (axis cs:2026.6, 34);
    \node[right, font=\scriptsize, text=black!40]
      at (axis cs:2022.9, 31) {Nicht-Experten: 34\%};
  \end{axis}
\end{tikzpicture}
\end{center}
\note{Speaker notes with context, anecdotes, transition cues.}
\end{frame}
```

**Line chart rules:**
- `very thick` (1.2pt) minimum line width for projection
- `mark size=3.5pt` minimum for data point markers
- Label data points directly - no legends for <4 series
- Dashed lines for reference values (human baseline, perfect score)
- German number format: comma for decimal (91,3% not 91.3%)
- Smooth tension 0.3-0.5 for organic curves
- Multiple series: vary both color AND mark shape (*, square*, triangle*, diamond*)

### Scatter Plots

```latex
\begin{axis}[
  width=14.5cm, height=7.0cm,
  xmode=log,
  xlabel={Kosten pro 1M Tokens (\$)},
  ylabel={Leistungsfähigkeit (Composite)},
  scatter/classes={
    western={mark=*, draw=western, fill=western, mark size=4.5pt},
    chinese={mark=square*, draw=chinese, fill=chinese, mark size=4pt},
  },
]
  \addplot[scatter, only marks, scatter src=explicit symbolic]
    coordinates { ... };

  % Direct labels - position to avoid overlap
  \node[above, font=\scriptsize\bfseries, text=western]
    at (axis cs:15, 95) {Claude Opus 4.6};

  % Cluster annotation with rounded dashed box
  \draw[chinese, dashed, rounded corners=6pt, line width=0.8pt]
    (axis cs:0.07, 76) rectangle (axis cs:3.0, 87);
  \node[below right, font=\footnotesize\bfseries, text=chinese]
    at (axis cs:0.07, 75.5) {Chinesische Modelle: 10--100x günstiger};
\end{axis}
```

**Scatter plot rules:**
- `mark size=4pt` minimum
- Different shapes per category (circles vs squares)
- Labels directly on or near each point
- Cluster annotations with dashed rounded rectangles
- Log scale when data spans >10x range

### Horizontal Bar Charts

```latex
\begin{axis}[
  width=14.5cm, height=7.0cm,
  xbar,
  bar width=0.4cm,
  xlabel={Input-Kosten pro 1M Tokens (\$)},
  symbolic y coords={...sorted by value...},
  ytick=data,
  yticklabel style={font=\small, anchor=east, text width=3.5cm, align=right},
  nodes near coords,
  nodes near coords style={
    font=\small\bfseries, anchor=west, xshift=2pt,
  },
  point meta=explicit symbolic,
  enlarge y limits=0.06,
  xmin=0,
]
  % Single series - gradient from green (cheap) to red (expensive)
  % Or: different colors per category
  \addplot[fill=series3!60, draw=series3!80] coordinates { ... };
\end{axis}
```

**Bar chart rules:**
- `bar width=0.4-0.5cm` for projection readability
- Always sort by value (ascending or descending)
- Always include value labels (`nodes near coords`)
- `enlarge y limits=0.06` for breathing room
- Color-code by category or gradient by value
- Y-axis labels: `text width` + `align=right` for clean alignment

### Training Cost / Grouped Bar Charts

```latex
\begin{axis}[
  width=14.5cm, height=7.0cm,
  xbar,
  bar width=0.6cm,
  symbolic y coords={DeepSeek V3, GPT-4, GPT-5},
  ytick=data,
  yticklabel style={font=\normalsize\bfseries},
  xmin=0, xmax=600,
  nodes near coords,
  nodes near coords style={font=\normalsize\bfseries, anchor=west},
  point meta=explicit symbolic,
]
  \addplot[fill=chinese!50, draw=chinese!70] coordinates {
    (5.6, DeepSeek V3) [\$5,6M]
  };
  \addplot[fill=western!50, draw=western!70] coordinates {
    (100, GPT-4) [\$100M+]
    (500, GPT-5) [\$500M+]
  };
\end{axis}
```

</details>

---

## Slide Layout Patterns

<details>
<summary>Slide Layout Patterns</summary>

### Pattern 1: Full Chart (70% of slides should be this)

```latex
\begin{frame}{3-5 Word Title}
\begin{center}
\begin{tikzpicture}
  \begin{axis}[width=14.5cm, height=7.0cm, ...]
    % Chart fills the frame
  \end{axis}
\end{tikzpicture}
\end{center}
\note{All explanatory text, context, anecdotes, transition cues here.}
\end{frame}
```

### Pattern 2: Full Table

```latex
\begin{frame}{3-5 Word Title}
\vspace{0.2cm}
\renewcommand{\arraystretch}{1.4}
{\small
\begin{tabularx}{\textwidth}{lXX}
  \toprule
  \textbf{Header} & \textbf{Col 1} & \textbf{Col 2} \\
  \midrule
  \rowcolor{lightbg} Row 1 & Value & Value \\
  Row 2 & Value & Value \\
  \bottomrule
\end{tabularx}
}
\note{Talking points for each row.}
\end{frame}
```

### Pattern 3: Two-Column Comparison (rare)

```latex
\begin{frame}{Title}
\begin{columns}[T]
  \begin{column}{0.47\textwidth}
    \begin{tcolorbox}[colback=danger!5, colframe=danger, ...]
      % Left side (e.g., "Chat")
    \end{tcolorbox}
  \end{column}
  \begin{column}{0.47\textwidth}
    \begin{tcolorbox}[colback=success!5, colframe=success, ...]
      % Right side (e.g., "Agent")
    \end{tcolorbox}
  \end{column}
\end{columns}
\note{Explain the comparison, provide examples.}
\end{frame}
```

### Pattern 4: Standout / Demo Title Card

```latex
\begin{frame}[standout]
  \vspace{0.5cm}
  {\huge\faIcon{play-circle}}\\[12pt]
  {\Large Demo: Titel}\\[8pt]
  {\normalsize\color{white!80} Untertitel}
\end{frame}
```

### Pattern 5: Showcase (text bullets - rare)

```latex
\begin{frame}{Showcase Title}
{\small
\begin{itemize}
  \setlength\itemsep{6pt}
  \item[\faIcon{icon}] \textbf{Bold lead} -- one-line explanation
  \item[\faIcon{icon}] \textbf{Bold lead} -- one-line explanation
  \item[\faIcon{icon}] \textbf{Bold lead} -- one-line explanation
\end{itemize}
}
\note{Full stories, examples, context for each point.}
\end{frame}
```

**Layout rules:**
- Charts ALWAYS get the full frame. No columns around charts.
- Column layouts only for comparison patterns (Pattern 3).
- Maximum 5 bullet points on any slide. Prefer 3.
- If content doesn't fit, split into two slides. Never shrink fonts.

</details>

---

## Speaker Notes

<details>
<summary>Speaker Notes</summary>

### Setup in Preamble

```latex
% Show notes on second screen (for dual-monitor presenting)
\usepackage{pgfpages}
\setbeameroption{show notes on second screen=right}
```

For PDF export with notes visible (for printing/review):
```latex
% Comment out the above, uncomment this:
% \setbeameroption{show notes}
```

### Note Structure

```latex
\note{%
  \textbf{Kernaussage:} Die eine Sache, die hängenbleiben soll.\\[4pt]
  \textbf{Daten:} Vor zwei Jahren lag GPT-4 bei 36\% - auf dem Niveau
  eines Nicht-Experten mit Google. Heute: 91,3\%.\\[4pt]
  \textbf{Beispiel:} GPQA-Fragen sind so schwer, dass selbst Doktoranden
  in benachbarten Fächern nur 34\% schaffen.\\[4pt]
  \textbf{Überleitung:} Das war Wissenschaft. Jetzt schauen wir uns
  Mathematik an - da ist die Kurve noch dramatischer.
}
```

**Note rules:**
- Structure: Kernaussage, Daten, Beispiel/Anekdote, Überleitung
- Write in the language you present in (German)
- Include specific numbers you want to mention verbally
- Include transition phrases to the next slide
- Keep under 8 lines - you're presenting, not reading

</details>

---

## Table Styling

<details>
<summary>Table Styling</summary>

```latex
\usepackage{booktabs}
\usepackage{colortbl}

% Increase row height for projection readability
\renewcommand{\arraystretch}{1.4}
```

**Rules:**
- Always `\toprule`, `\midrule`, `\bottomrule` - never `\hline`
- Never vertical rules (`|` in column spec)
- Alternating `\rowcolor{lightbg}` for readability
- Left-align text, right-align numbers
- `\small` or `\footnotesize` for table content
- `tabularx` with `X` columns for auto-width text columns
- Bold headers, regular content
- Highlight special rows (e.g., "FREE" tier) with `\rowcolor{success!15}`

</details>

---

## Diagram Styling (tikz)

<details>
<summary>Diagram Styling (tikz)</summary>

```latex
% Node styles for workflow diagrams
\tikzset{
  box/.style={
    draw=primary!60, fill=lightbg, rounded corners=4pt,
    minimum height=0.7cm, minimum width=1.8cm,
    font=\footnotesize, align=center, line width=0.6pt,
  },
  agent/.style={
    draw=accent!60, fill=accent!8, rounded corners=4pt,
    minimum height=0.7cm, minimum width=1.6cm,
    font=\footnotesize, align=center, line width=0.6pt,
  },
  arrow/.style={
    -{Stealth[length=5pt]}, primary!50, line width=0.8pt,
  },
}
```

**Rules:**
- Rounded corners (3-5pt) on all boxes
- Subtle fills (8-15% opacity of border color)
- Thin lines (0.6-0.8pt) - not heavy borders
- Arrows: `Stealth` style, 5pt length, muted color
- Font: `\footnotesize` minimum in diagram nodes
- Scale diagrams to fill frame width

</details>

---

## German Academic Copy

<details>
<summary>German Academic Copy</summary>

### Section Titles (short, direct)
- "Stand der KI" (not "Der aktuelle Stand der künstlichen Intelligenz")
- "Die Modelllandschaft"
- "Jenseits des Browsers"
- "Praxis"

### Frame Titles (3-5 words, punchy)
- "GPQA Diamond -- PhD-Niveau"
- "AIME -- Mathematik-Olympiade"
- "Token-Preise im Vergleich"
- "Vom Chatbot zum Mitarbeiter"

### Keep English
- Benchmark, Token, Agent, Sub-Agent, Prompt, API, Coding, Multimodal
- All model names (GPT-5.3, Claude Opus 4.6, DeepSeek V3)
- Open Source, SWE-bench, GPQA, AIME

### Translate to German
- capability -> Leistungsfähigkeit
- training cost -> Trainingskosten
- use case -> Anwendungsfall
- subscription -> Abonnement
- context window -> Kontextfenster
- co-worker -> Mitarbeiter
- working memory -> Arbeitsspeicher

### Tone
- Informed, direct, slightly casual for university students
- Short sentences, active voice
- State facts, let data carry the argument
- No marketing language, no superlatives, no "revolutionär"
- Humor is fine when natural - don't force it

### German Number Format
- Decimal comma: 91,3% not 91.3%
- Thousands separator: dot or thin space: 5.600 or 5\,600
- Currency: \$5,00 or 5\,\$ for German context (but keep $ for international comparisons)

### Always grep for false umlauts after writing German: `üll|ünz|üe|ürft`

</details>

---

## Anti-Patterns (Never Do These)

<details>
<summary>Anti-Patterns (Never Do These)</summary>

1. **Charts in columns** - Charts share space with explanatory text. The chart IS the content.
2. **tcolorbox quotes under every chart** - "Two years ago AI was at non-expert level." Put this in notes.
3. **Explanatory subtitles** on chart slides - One muted line max, rest goes to notes.
4. **Default pgfplots colors** - Always define custom series colors.
5. **Primary RGB colors** - Never pure red/blue/green. Always muted, dark variants.
6. **Tiny chart in big frame** - Charts must fill 80%+ of frame area.
7. **Text walls** - More than 5 bullets means you need two slides or notes.
8. **Long frame titles** - "GPQA Diamond Benchmark Results Over Time (2023-2026)" is a crime. Just "GPQA Diamond".
9. **\tiny on projected content** - Invisible at 2 meters. Use \scriptsize minimum.
10. **Excessive fontawesome** - One icon per item max. Not every line needs a pictogram.
11. **Column layouts for charts + text** - The old version's biggest sin. Chart gets the full slide.
12. **tcolorbox/infocard everywhere** - Reserve for 1-2 truly impactful statements per talk.
13. **Inconsistent chart styling** - Same chart type = same dimensions, colors, font sizes.
14. **Missing speaker notes** - Every slide needs notes. The chart alone doesn't tell the user what to say.
15. **Translated English** - "Das dramatischste Verbesserungskurve" reads like Google Translate. Write German from scratch.

</details>

---

## Fitting Content to Slides

<details>
<summary>Fitting Content to Slides</summary>

When something overflows:

1. **First**: Is the chart at `width=14.5cm, height=7.0cm`? If not, increase it.
2. **Second**: Is there text on the slide that should be in notes? Move it.
3. **Third**: Are fonts too large? (Unlikely - check this last)
4. **Fourth**: Use `\resizebox{\textwidth}{!}{...}` as last resort for charts.
5. **NEVER**: Shrink a chart to fit alongside text. Give the chart the full frame.

### Common overflow fixes:
- pgfplots years showing "2,023": Add `/pgf/number format/1000 sep={}` to xticklabel style
- Chart wider than column: Don't use columns. Give it the full frame.
- Table too wide: Switch to `tabularx` with `X` columns, reduce `\arraystretch`
- Too many items: Split into two slides. Two clean slides > one cramped slide.

</details>

---

## Quality Self-Check

After writing any slide:

1. **3-second test** - Can the audience understand this slide's ONE point in 3 seconds from the visual alone?
2. **Fill test** - Does the chart/visual fill at least 80% of the frame area?
3. **Font test** - Is everything readable at 3m? Nothing smaller than \scriptsize?
4. **Color test** - Are all colors from the defined palette? No defaults?
5. **Notes test** - Are speaker notes present? Do they include Kernaussage, Daten, Überleitung?
6. **Title test** - Is the frame title 3-5 words?
7. **Text test** - Is there explanatory text on the slide that should be in notes?
8. **German test** - Does the text sound natural, not translated? Grep for `üll|ünz|üe|ürft`
9. **Consistency test** - Do same-type charts use the same dimensions, colors, and fonts?
10. **Compile test** - Does `lualatex` produce the PDF without hbox/vbox overflows?

**Concrete test**: Print the slide at 50% size. If you can't read every label, the font is too small. If the chart looks tiny with whitespace around it, the chart is too small.

---

<!-- Removed redundant DO NOT section - all these rules are already covered with context
     in the Anti-Patterns section above (line ~556). Having both creates token waste
     and risks the model following the bare version instead of the reasoned one. -->
