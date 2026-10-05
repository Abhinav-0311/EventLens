"""Conservative, inspectable phrase rules; not a trained event classifier."""

import re

from eventlens.schemas import Classification, EventClass, Impact, Span

ISSUERS = {
    "Aster Energy": "energy",
    "Meridian Transport": "transport",
    "Forge Manufacturing": "manufacturing",
    "Cedar Technology": "technology",
    "Harbor Financial": "financials",
}
POLICY = re.compile(
    r"\b(?:Federal Reserve|FOMC|Federal Open Market Committee|central bank|policy rate|"
    r"target range|federal funds rate)\b",
    re.I,
)
HISTORICAL = re.compile(
    r"\b(?:last year|previously|earlier|historically|in 20\d\d|prior decision)\b", re.I
)
SPECULATION = re.compile(
    r"\b(?:may|might|could|would|will|expects?|expected|if|rumou?r\w*|reportedly|"
    r"potential|propos\w*|plans? to|consider\w*|forecast\w*)\b",
    re.I,
)
NEGATION = re.compile(r"\b(?:not(?! only)|never|no longer|denied|without)\b", re.I)
POLICY_OBJECT = r"\s+(?:(?:the|its|their|a|benchmark|policy|interest|federal|funds|overnight)\s+){0,10}(?:rates?|target range)\b"
DEBT_DEFAULT = (
    r"default(?:ed|s)? on\s+(?:(?:the|its|their|a|an|outstanding|corporate|senior|secured|unsecured)\s+){0,5}"
    r"(?:debt|bonds?|loans?|financial obligations?|interest payments?|principal payments?)\b"
)
RULES = (
    (
        EventClass.MACRO,
        "rate_hike",
        r"\b(?:rais(?:e|ed|es|ing)|increas(?:e|ed|es|ing)|hike[ds]?)\b" + POLICY_OBJECT,
    ),
    (
        EventClass.MACRO,
        "rate_cut",
        r"\b(?:cut(?:s|ting)?|lower(?:ed|s|ing)?|reduc(?:e|ed|es|ing))\b" + POLICY_OBJECT,
    ),
    (
        EventClass.CREDIT,
        "credit_deterioration",
        r"\b(?:"
        + DEBT_DEFAULT
        + r"|downgrad(?:e|ed|es)|miss(?:ed|es) (?:a |its )?(?:debt |bond )?payment)\b",
    ),
    (
        EventClass.GEO,
        "supply_disruption",
        r"\b(?:supply|shipping|oil|energy)\b.{0,100}?\b(?:disrupt\w*|blockad\w*|halt\w*)\b",
    ),
    (EventClass.MA, "acquisition", r"\b(?:acquir(?:e|ed|es)|merg(?:e|ed|es)|acquisition|merger)\b"),
    (
        EventClass.PRODUCT,
        "product_launch",
        r"\blaunch(?:ed|es)?\b.{0,60}?\b(?:product|service|platform)\b",
    ),
)
COMPILED = [
    (event_class, subtype, re.compile(pattern, re.I)) for event_class, subtype, pattern in RULES
]


def _magnitude(sentence: str, subtype: str) -> tuple[int, str, list[str]]:
    if subtype.startswith("rate_"):
        found = re.search(r"\bby\s+(\d+(?:\.\d+)?)\s*(?:basis points?|bps?)\b", sentence, re.I)
        bp = float(found.group(1)) if found else None
        if bp is None:
            found = re.search(
                r"\bby\s+(\d+(?:\.\d+)?(?:/\d+)?|¼|½|¾)\s*percentage points?\b", sentence, re.I
            )
            if found:
                number = found.group(1)
                if number in {"¼", "½", "¾"}:
                    bp = {"¼": 25, "½": 50, "¾": 75}[number]
                elif "/" in number:
                    numerator, denominator = number.split("/")
                    bp = float(numerator) / float(denominator) * 100 if float(denominator) else None
                else:
                    bp = float(number) * 100
        if bp is None:
            worded = re.search(
                r"\bby\s+(a quarter|one quarter|a half|one half|three quarters)\s+percentage points?\b",
                sentence,
                re.I,
            )
            if worded:
                bp = {
                    "a quarter": 25,
                    "one quarter": 25,
                    "a half": 50,
                    "one half": 50,
                    "three quarters": 75,
                }[worded.group(1).lower()]
        if bp is None:
            return (
                2,
                "Policy magnitude unspecified; use material baseline, require review.",
                ["magnitude_unspecified"],
            )
        points = 5 if bp >= 75 else 4 if bp >= 50 else 3 if bp >= 25 else 2 if bp > 0 else 0
        return points, f"Policy move {bp:g} bp maps to magnitude {points}.", []
    if subtype == "credit_deterioration":
        default = re.search(r"\bdefault(?:ed|s)? on\b", sentence, re.I)
        return (
            (5, "Debt default: exceptional magnitude.", [])
            if default
            else (3, "Downgrade/missed payment: major magnitude.", [])
        )
    if subtype == "supply_disruption":
        if re.search(r"\b(?:war|conflict|sanction\w*|blockade|attack)\b", sentence, re.I):
            return 4, "Explicit conflict-related supply disruption: severe magnitude.", []
        return (
            3,
            "Supply disruption without clear geopolitical cause; require review.",
            ["geopolitical_cause_unclear"],
        )
    return (
        (3, "Acquisition: major illustrative magnitude.", [])
        if subtype == "acquisition"
        else (1, "Product launch: routine magnitude.", [])
    )


def classify(text: str) -> Classification:
    candidates = []
    flags = []
    # Split sentences without splitting decimal quantities such as 0.50 percentage points.
    for sentence_match in re.finditer(r".+?(?:[.!?](?=\s|$)|$)", text, re.S):
        sentence = sentence_match.group()
        offset = sentence_match.start()
        for event_class, subtype, pattern in COMPILED:
            match = pattern.search(sentence)
            if not match or (subtype.startswith("rate_") and not POLICY.search(sentence)):
                continue
            if HISTORICAL.search(sentence):
                flags.append("historical_context_ignored")
                continue
            if NEGATION.search(sentence[: match.end()]):
                assertion = "negated"
            elif SPECULATION.search(sentence):
                assertion = "speculative"
            else:
                assertion = "asserted"
            candidates.append((event_class, subtype, assertion, sentence, offset, match))
    if not candidates:
        category, subtype = EventClass.UNKNOWN, "unknown"
        phrase = re.search(
            r"\b(?:inflation|GDP|unemployment|consumer price index)\b", text, re.I
        ) or POLICY.search(text)
        if phrase:
            category, subtype = EventClass.MACRO, "macro_announcement"
        else:
            phrase = re.search(r"\b(?:war|armed conflict|sanctions|military attack)\b", text, re.I)
            if phrase:
                category, subtype = EventClass.GEO, "geopolitical_event"
        return Classification(
            event_class=category,
            event_subtype=subtype,
            assertion_status="unclear",
            impact_score=1,
            impact_components=Impact(
                magnitude_points=0,
                scope_points=0,
                rationale="No supported current stress event; category phrases alone do not establish magnitude or direction.",
            ),
            evidence_spans=[Span(start=phrase.start(), end=phrase.end(), text=phrase.group())]
            if phrase
            else [],
            flags=sorted(set(flags + ["unsupported_event"])),
        )
    kinds = {candidate[1] for candidate in candidates}
    if len(kinds) > 1:
        return Classification(
            event_class=EventClass.UNKNOWN,
            event_subtype="ambiguous",
            assertion_status="unclear",
            impact_score=1,
            impact_components=Impact(
                magnitude_points=0,
                scope_points=0,
                rationale="Multiple event types/directions; do not select an automatic scenario.",
            ),
            evidence_spans=[
                Span(start=c[4] + c[5].start(), end=c[4] + c[5].end(), text=c[5].group())
                for c in candidates
            ],
            flags=sorted(set(flags + ["conflicting_events"])),
        )
    event_class, subtype, assertion, sentence, offset, match = candidates[0]
    if len(candidates) > 1:
        flags.append("multiple_event_clauses")
    issuers = [
        name for name in ISSUERS if re.search(r"\b" + re.escape(name) + r"\b", sentence, re.I)
    ]
    sectors = sorted({sector for name, sector in ISSUERS.items() if name in issuers})
    for sector in ("energy", "transport", "manufacturing", "technology", "financials"):
        if re.search(r"\b" + sector + r" (?:sector|industry)\b", sentence, re.I):
            sectors.append(sector)
    if subtype == "supply_disruption":
        if re.search(r"\b(?:oil|energy)\b", sentence, re.I):
            sectors.append("energy")
        if re.search(r"\bshipping\b", sentence, re.I):
            sectors.append("transport")
    regions = []
    if re.search(
        r"\b(?:Federal Reserve|FOMC|Federal Open Market Committee|United States|US|U\.S\.)\b",
        sentence,
        re.I,
    ):
        regions.append("US")
    global_scope = bool(re.search(r"\b(?:global|worldwide|cross-border)\b", sentence, re.I))
    national = bool(POLICY.search(sentence)) or bool(
        re.search(r"\b(?:nationwide|national|systemic)\b", sentence, re.I)
    )
    sector_scope = bool(re.search(r"\b(?:sector|industry|supply|shipping)\b", sentence, re.I))
    scope = 4 if global_scope else 3 if national else 1 if issuers else 2 if sector_scope else 0
    magnitude, rationale, extra_flags = _magnitude(sentence, subtype)
    flags.extend(extra_flags)
    if subtype == "credit_deterioration" and not issuers and not sectors:
        flags.append("exposure_entity_unresolved")
    if subtype.startswith("rate_") and "US" not in regions:
        flags.append("non_us_policy_requires_review")
    if assertion == "negated":
        magnitude, scope = 0, 0
        rationale = "Event phrase negated: no asserted shock."
    if assertion == "speculative":
        flags.append("speculative_event")
    return Classification(
        event_class=event_class,
        event_subtype=subtype,
        assertion_status=assertion,
        impact_score=1 + magnitude + scope,
        impact_components=Impact(
            magnitude_points=magnitude,
            scope_points=scope,
            rationale=f"{rationale} Scope points {scope}; source reliability is separate.",
        ),
        evidence_spans=[
            Span(start=offset + match.start(), end=offset + match.end(), text=match.group())
        ],
        affected_issuers=issuers,
        affected_sectors=sorted(set(sectors)),
        affected_regions=regions,
        flags=sorted(set(flags)),
    )
