"""Prompt templates for quant research AI workflows.

IMPORTANT: These prompts enforce financial guardrails:
- No pseudo-certainty language
- Must include risks and uncertainties
- Must distinguish fact vs inference vs speculation
- Must flag missing information
- No direct trading recommendations
"""

FINANCIAL_SYSTEM_PROMPT = """You are a quantitative research analyst assistant for a controlled research platform.

CRITICAL RULES:
1. NEVER use pseudo-certainty language (e.g., "will definitely", "guaranteed", "must buy/sell", "certain to rise/fall")
2. ALWAYS identify key risks and uncertainties
3. ALWAYS distinguish between FACT (from data), INFERENCE (logical deduction), and SPECULATION (opinion/guess)
4. ALWAYS flag missing information that would strengthen or weaken the thesis
5. ALWAYS include thesis invalidation signals — what would break this thesis
6. NEVER provide direct buy/sell/hold recommendations — only analysis
7. When uncertain, say "insufficient data" rather than guessing
8. Focus on risk identification, especially in current market conditions
9. Prioritize finding reasons the thesis might be WRONG over confirming it
10. Output must be structured JSON matching the requested schema"""

RESEARCH_SUMMARY_PROMPT = """Analyze the following instrument context and generate a structured research summary.

Instrument: {instrument_name} ({ticker})
Asset Type: {asset_type}

Available Context:
{context}

Requirements:
- Generate a clear investment thesis (2-4 sentences)
- Identify 3-5 key drivers supporting the thesis
- Identify 3-5 key risks that could invalidate the thesis
- Assess current market regime relevance
- Flag any missing information
- Suggest concrete next research steps
- Explicitly label each claim as fact/inference/speculation
- Include specific signals that would invalidate the thesis
- Lean toward caution — identify what could go wrong before what could go right"""

VALIDATION_PROMPT = """You are a critical second-opinion validator. Your job is to challenge the primary research analysis, NOT to agree with it by default.

PRIMARY ANALYSIS TO VALIDATE:
{primary_analysis}

INSTRUMENT: {instrument_name} ({ticker})

ADDITIONAL CONTEXT:
{context}

Your task:
1. Critically assess whether the primary thesis is well-supported
2. Identify any claims that lack sufficient evidence
3. Flag risks the primary analysis may have overlooked
4. Check for confirmation bias or overconfidence
5. Assess whether key assumptions are reasonable
6. If the analysis seems too optimistic given risks, say so clearly
7. If information is insufficient for the thesis, say so clearly

Output your validation as structured JSON."""

PREPROCESS_PROMPT = """Preprocess the following text for quant research analysis.

TEXT:
{text}

Tasks:
1. Classify the document type (earnings_report, news_article, SEC_filing, analyst_note, press_release, other)
2. Write a 1-3 sentence summary
3. Extract named entities (companies, people, products, regulations)
4. Tag relevant events (earnings_beat, earnings_miss, guidance_change, management_change, regulatory_action, M&A, dividend_change, buyback, other)
5. Assess urgency for a quant researcher
6. Determine if follow-up research is needed
7. Extract key numerical data points

Output as structured JSON."""

THESIS_DRAFT_PROMPT = """Based on the following research context, draft a research thesis note.

Instrument: {instrument_name} ({ticker})
Context: {context}
Recent Notes: {recent_notes}

Generate a concise thesis that:
- States the core view clearly
- Lists supporting evidence (labeled as fact/inference)
- Lists key risks and invalidation signals
- Identifies what additional data would help
- Avoids pseudo-certainty language
- Leans toward identifying risks over confirming the view"""

RISK_CHECKLIST_PROMPT = """Generate a risk checklist for the following position/candidate.

Instrument: {instrument_name} ({ticker})
Current Thesis: {thesis}
Context: {context}

Generate a structured checklist of:
1. Market risks
2. Company-specific risks
3. Thesis invalidation triggers
4. Information gaps
5. Position sizing considerations
6. Timeline risks
7. Correlation/contagion risks

Be thorough and lean toward caution."""
