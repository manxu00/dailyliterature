from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "papers.json"
METRICS = ROOT / "data" / "journal_metrics.json"
KEYWORDS = ROOT / "data" / "keywords.json"
BERLIN = ZoneInfo("Europe/Berlin")

TARGET_DAILY = 10
MAX_ARCHIVE = 1200
RECENT_DAYS = 365
BACKFILL_YEARS = 12
PER_PAGE = 100
MAX_QUERY_PER_TOPIC = 2
MIN_SCORE = 52

OPENALEX_CONNECT_TIMEOUT = 5
OPENALEX_READ_TIMEOUT = 15
MAX_CONSECUTIVE_FAILURES = 3
REQUEST_PAUSE = 0.18

API = {"ok": 0, "failed": 0, "consecutive_failed": 0, "circuit_open": False}

DEFAULT_QUERIES = {
    "core": [
        "electrocarboxylation CO2",
        "organic electrosynthesis carbon dioxide",
        "electrochemical carboxylation CO2 organic synthesis",
        "reductive carboxylation carbon dioxide electrochemistry",
        "electrochemical CO2 fixation organic synthesis",
    ],
    "mechanism": [
        "electrocarboxylation mechanism",
        "cyclic voltammetry electrosynthesis mechanism",
        "electrochemical reaction mechanism organic synthesis",
        "radical intermediate electrocarboxylation",
    ],
    "optimization": [
        "electrocarboxylation reaction optimization",
        "supporting electrolyte organic electrosynthesis CO2",
        "solvent effect electrocarboxylation",
        "electrode potential electrocarboxylation",
    ],
}

TOPIC_LABELS = {
    "core": "Organic CO₂ electrosynthesis",
    "mechanism": "Electroanalysis & mechanism",
    "optimization": "Condition optimization",
}

CORE_WEIGHTS = {
    "electrocarboxylation": 60,
    "electrochemical carboxylation": 54,
    "reductive carboxylation": 46,
    "carboxylative cyclization": 40,
    "hydrocarboxylation": 38,
    "co2 incorporation": 28,
    "carbon dioxide incorporation": 28,
    "co2 fixation": 25,
    "carbon dioxide fixation": 25,
    "organic electrosynthesis": 28,
    "electroorganic synthesis": 28,
    "electroreductive coupling": 26,
    "electrochemical synthesis": 12,
    "carbon dioxide": 8,
    " co2 ": 8,
}

MECHANISM_WEIGHTS = {
    "reaction mechanism": 22,
    "mechanistic": 22,
    "mechanism": 12,
    "cyclic voltammetry": 20,
    "voltammetry": 12,
    "kinetic": 14,
    "electron transfer": 14,
    "radical intermediate": 18,
    "radical": 8,
    "intermediate": 8,
    "density functional theory": 10,
    " dft ": 8,
    "epr": 10,
    "isotope": 10,
    "in situ": 8,
    "operando": 8,
    "spectroelectrochem": 14,
    "redox": 6,
}

OPTIMIZATION_WEIGHTS = {
    "optimization": 20,
    "optimisation": 20,
    "reaction conditions": 16,
    "supporting electrolyte": 16,
    "electrolyte": 7,
    "solvent effect": 14,
    "solvent": 7,
    "current density": 12,
    "applied potential": 12,
    "electrode potential": 12,
    "constant current": 8,
    "constant potential": 8,
    "co2 pressure": 12,
    "carbon dioxide pressure": 12,
    "temperature": 6,
    "concentration": 6,
    "cell configuration": 12,
    "divided cell": 8,
    "undivided cell": 8,
    "faradaic efficiency": 10,
    "yield": 8,
    "selectivity": 8,
    "substrate scope": 10,
}

ORGANIC_SUBSTRATES = (
    "alkene", "diene", "alkyne", "aryl halide", "organic halide", "benzyl halide",
    "allyl", "styrene", "epoxide", "ketone", "aldehyde", "imine", "enone", "ester",
    "amide", "substrate", "organic molecule", "organic compound", "cyclization", "coupling",
)

ELECTRO_TERMS = (
    "electrochemical", "electrochemistry", "electrosynthesis", "electroreduct", "electrocarboxyl",
    "cathod", "anod", "electrolysis", "current", "potential",
)

CO2_TERMS = (" co2 ", "carbon dioxide")

HARD_EXCLUDE = (
    "direct methanol fuel cell", " dmfc ", "pem fuel cell", "proton exchange membrane fuel cell",
    "lithium-ion battery", "lithium ion battery", "sodium-ion battery", "sodium ion battery",
    "supercapacitor", "oxygen reduction reaction", "oxygen evolution reaction", "water splitting",
    "hydrogen evolution reaction",
)

CATALYST_DESIGN_TERMS = {
    "catalyst design": 35,
    "catalyst synthesis": 35,
    "electrocatalyst": 20,
    "nanoparticle": 18,
    "nanocomposite": 20,
    "single-atom": 24,
    "single atom": 24,
    "heterostructure": 20,
    "doped": 14,
    "alloy catalyst": 22,
    "metal oxide catalyst": 22,
    "active site": 16,
    "catalyst surface": 12,
    "catalytic activity": 12,
}

CO2RR_PRODUCT_TERMS = (
    "carbon monoxide", "formate", "formic acid", "methanol", "ethylene", "ethanol", "syngas",
)

METHOD_HINTS = (
    "cyclic voltammetry", "voltammetry", "electrolysis", "chronoamper", "chronopotent",
    "controlled-potential", "constant current", "constant potential", "gc-ms", "gas chromatography",
    "hplc", "nmr", "mass spectrometry", "epr", "spectroscopy", "spectroelectrochem",
    "density functional theory", "dft", "kinetic", "isotope", "radical trapping",
)

FINDING_HINTS = (
    "we found", "we show", "we demonstrate", "results show", "results indicate", "revealed",
    "yield", "selectivity", "faradaic efficiency", "conversion", "increased", "decreased",
    "improved", "optimized", "optimised", "mechanism", "intermediate", "rate-determining",
)


def session() -> requests.Session:
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "organic-co2-literature-radar/4.0"})
    return s


SESSION = session()


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize(text: str) -> str:
    text = (text or "").lower().replace("₂", "2")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return f" {text.strip()} "


def has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words = []
    for word, positions in inv.items():
        for pos in positions:
            words.append((pos, word))
    return " ".join(word for _, word in sorted(words))


def sentence_split(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text) if len(x.strip()) > 20]


def select_sentences(text: str, hints: tuple[str, ...], limit: int = 2) -> str:
    scored = []
    for idx, sentence in enumerate(sentence_split(text)):
        low = sentence.lower()
        score = sum(1 for h in hints if h in low)
        if score:
            scored.append((score, -idx, sentence))
    scored.sort(reverse=True)
    return " ".join(x[2] for x in scored[:limit])


def truncate(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def strong_core(full: str) -> bool:
    return has_any(full, (
        "electrocarboxylation", "electrochemical carboxylation", "reductive carboxylation",
        "hydrocarboxylation", "carboxylative cyclization", "co2 incorporation", "carbon dioxide incorporation",
    ))


def relevance(title: str, abstract: str) -> tuple[int, str, list[str]] | None:
    title_n = normalize(title)
    full = normalize(title + " " + abstract)

    if has_any(full, HARD_EXCLUDE):
        return None

    electro = has_any(full, ELECTRO_TERMS)
    co2 = has_any(full, CO2_TERMS)
    organic = has_any(full, ORGANIC_SUBSTRATES) or has_any(full, (
        "organic synthesis", "organic electrosynthesis", "electroorganic", "carboxylation", "carboxylative",
    ))

    if not strong_core(full) and not (electro and co2 and organic):
        return None

    # Pure CO2RR catalyst papers are not the target unless an organic coupling/carboxylation signal is clear.
    if has_any(full, CO2RR_PRODUCT_TERMS) and not strong_core(full) and not has_any(full, ("coupling", "organic substrate", "carboxylation")):
        return None

    core = 0
    mech = 0
    opt = 0
    matched = []

    for term, w in CORE_WEIGHTS.items():
        if term in full:
            core += w
            matched.append(term.strip())
            if term in title_n:
                core += max(5, round(w * 0.35))
    for term, w in MECHANISM_WEIGHTS.items():
        if term in full:
            mech += w
            matched.append(term.strip())
    for term, w in OPTIMIZATION_WEIGHTS.items():
        if term in full:
            opt += w
            matched.append(term.strip())

    catalyst_penalty = 0
    for term, penalty in CATALYST_DESIGN_TERMS.items():
        if term in full:
            catalyst_penalty += penalty

    # Hard reject papers dominated by catalyst/material development and lacking mechanistic/optimization content.
    if catalyst_penalty >= 35 and core < 45 and mech < 18 and opt < 18:
        return None

    score = core + min(mech, 42) + min(opt, 38) - catalyst_penalty
    if len(abstract) > 350:
        score += 5
    if has_any(title_n, ("mechanism", "mechanistic", "optimization", "optimisation", "electrocarboxylation")):
        score += 8

    if score < MIN_SCORE:
        return None

    if mech >= max(18, opt) and mech >= core * 0.45:
        topic = "mechanism"
    elif opt >= max(18, mech) and opt >= core * 0.42:
        topic = "optimization"
    else:
        topic = "core"

    return min(99, 70 + round((score - MIN_SCORE) * 0.34)), topic, list(dict.fromkeys(matched))[:8]


def canonical_key(p: dict) -> str:
    doi = (p.get("doi") or "").lower().strip()
    if doi:
        return doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return re.sub(r"\W+", " ", p.get("title", "").lower()).strip()[:240]


def source_info(work: dict) -> tuple[str, list[str]]:
    source = ((work.get("primary_location") or {}).get("source") or {})
    name = source.get("display_name") or "Unknown journal"
    issns = list(source.get("issn") or [])
    if source.get("issn_l") and source.get("issn_l") not in issns:
        issns.insert(0, source.get("issn_l"))
    return name, [x for x in issns if x]


def primary_url(work: dict) -> str:
    return work.get("doi") or (work.get("primary_location") or {}).get("landing_page_url") or work.get("id") or "#"


def metric_lookup(journal: str, issns: list[str], metrics: dict) -> tuple[str | None, str | None, str | None]:
    normalized_issn = {x.upper() for x in issns}
    jlow = journal.lower().strip()
    metric_year = (metrics.get("_metadata") or {}).get("metric_year")
    for name, info in metrics.items():
        if name.startswith("_") or not isinstance(info, dict):
            continue
        rec_issn = {str(x).upper() for x in info.get("issn", [])}
        aliases = [name, *info.get("aliases", [])]
        name_match = any(jlow == str(a).lower().strip() for a in aliases)
        if normalized_issn.intersection(rec_issn) or name_match:
            return info.get("impact_factor"), info.get("quartile"), metric_year
    return None, None, metric_year


def openalex_get(params: dict) -> dict:
    if API["circuit_open"]:
        raise RuntimeError("OpenAlex circuit breaker is open")
    mailto = os.getenv("OPENALEX_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    try:
        r = SESSION.get("https://api.openalex.org/works", params=params, timeout=(OPENALEX_CONNECT_TIMEOUT, OPENALEX_READ_TIMEOUT))
        r.raise_for_status()
        API["ok"] += 1
        API["consecutive_failed"] = 0
        time.sleep(REQUEST_PAUSE)
        return r.json()
    except requests.RequestException as exc:
        API["failed"] += 1
        API["consecutive_failed"] += 1
        if API["consecutive_failed"] >= MAX_CONSECUTIVE_FAILURES:
            API["circuit_open"] = True
        msg = re.sub(r"\s+", " ", str(exc))[:260]
        raise RuntimeError(msg) from exc


def load_queries() -> dict[str, list[str]]:
    raw = load_json(KEYWORDS, {})
    out = {}
    for topic, defaults in DEFAULT_QUERIES.items():
        items = (((raw.get("topics") or {}).get(topic) or {}).get("keywords") or [])
        cleaned = []
        seen = set()
        for item in items:
            q = re.sub(r"\s+", " ", str(item or "")).strip()
            if q and q.lower() not in seen:
                cleaned.append(q)
                seen.add(q.lower())
        out[topic] = cleaned or defaults
    return out


def rotating_queries(topic: str, queries: list[str], day_ordinal: int) -> list[str]:
    if not queries:
        return []
    # Always include the first (broadest) query, rotate the second slot daily.
    picked = [queries[0]]
    if len(queries) > 1 and MAX_QUERY_PER_TOPIC > 1:
        idx = 1 + ((day_ordinal + {"core": 0, "mechanism": 3, "optimization": 7}[topic]) % (len(queries) - 1))
        picked.append(queries[idx])
    return picked[:MAX_QUERY_PER_TOPIC]


def fetch(query: str, date_from: str, date_to: str, page: int = 1) -> list[dict]:
    params = {
        "search": query,
        "filter": f"from_publication_date:{date_from},to_publication_date:{date_to},is_paratext:false",
        "per-page": PER_PAGE,
        "page": page,
    }
    return openalex_get(params).get("results", [])


def build_paper(work: dict, score: int, topic: str, tags: list[str], metrics: dict, pushed_date: str) -> dict:
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    journal, issns = source_info(work)
    impact_factor, quartile, metric_year = metric_lookup(journal, issns, metrics)
    wid = (work.get("id") or "").split("/")[-1]
    title = (work.get("title") or "").strip()
    if not wid:
        wid = re.sub(r"\W+", "-", title.lower()).strip("-")[:80]

    methods = select_sentences(abstract, METHOD_HINTS, 2)
    findings = select_sentences(abstract, FINDING_HINTS, 2)
    sentences = sentence_split(abstract)

    if not methods:
        methods = "The available abstract does not describe the experimental or electroanalytical methods in enough detail."
    if not findings:
        findings = sentences[-1] if sentences else "No reliable conclusion could be extracted from the available abstract."

    return {
        "id": wid,
        "doi": work.get("doi") or "",
        "title": title,
        "topic": topic,
        "topic_label": TOPIC_LABELS[topic],
        "journal": journal,
        "journal_issn": issns,
        "impact_factor": impact_factor,
        "quartile": quartile,
        "metric_year": metric_year,
        "year": work.get("publication_year"),
        "publication_date": work.get("publication_date") or "",
        "abstract": truncate(abstract, 7000),
        "methods_summary": truncate(methods, 900),
        "key_findings": truncate(findings, 1000),
        "tags": tags[:7],
        "score": score,
        "url": primary_url(work),
        "archive": False,
        "pushed_date": pushed_date,
    }


def collect_unseen(queries: dict[str, list[str]], seen: set[str], metrics: dict, now: datetime, data: dict) -> tuple[list[dict], int]:
    recent_from = (now.date() - timedelta(days=RECENT_DAYS)).isoformat()
    today = now.date().isoformat()
    candidates = {}

    def ingest(works: list[dict]):
        for work in works:
            title = (work.get("title") or "").strip()
            if not title:
                continue
            abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
            rel = relevance(title, abstract)
            if not rel:
                continue
            score, topic, tags = rel
            paper = build_paper(work, score, topic, tags, metrics, today)
            key = canonical_key(paper)
            if key in seen:
                continue
            existing = candidates.get(key)
            if existing is None or paper["score"] > existing["score"]:
                candidates[key] = paper

    day_ordinal = now.date().toordinal()
    for topic, qlist in queries.items():
        for q in rotating_queries(topic, qlist, day_ordinal):
            if API["circuit_open"]:
                break
            try:
                works = fetch(q, recent_from, today, 1)
                ingest(works)
                print(f"recent | {topic:12s} | {q[:52]:52s} | total candidates={len(candidates)}", flush=True)
            except Exception as exc:
                print(f"OpenAlex recent fetch failed [{topic}] {q}: {exc}", file=sys.stderr, flush=True)
        if API["circuit_open"]:
            break

    # If the newest literature does not fill ten slots, rotate through older pages.
    page = int(((data.get("search_state") or {}).get("backfill_page") or 1))
    if len(candidates) < TARGET_DAILY and not API["circuit_open"]:
        old_from = (now.date() - timedelta(days=365 * BACKFILL_YEARS)).isoformat()
        for round_idx in range(2):
            for topic, qlist in queries.items():
                if API["circuit_open"] or len(candidates) >= TARGET_DAILY * 3:
                    break
                q = qlist[0]
                try:
                    works = fetch(q, old_from, today, page + round_idx)
                    ingest(works)
                    print(f"backfill page {page + round_idx} | {topic:12s} | candidates={len(candidates)}", flush=True)
                except Exception as exc:
                    print(f"OpenAlex backfill failed [{topic}] page {page + round_idx}: {exc}", file=sys.stderr, flush=True)
            if API["circuit_open"] or len(candidates) >= TARGET_DAILY * 3:
                break
        page += 2
        if page > 80:
            page = 1

    ranked = sorted(
        candidates.values(),
        key=lambda p: (int(p.get("score") or 0), p.get("publication_date") or ""),
        reverse=True,
    )

    # Prefer a mix: core synthesis first, then mechanism/optimization, then fill by score.
    selected = []
    quotas = {"core": 5, "mechanism": 3, "optimization": 2}
    for topic, quota in quotas.items():
        pool = [p for p in ranked if p["topic"] == topic and p not in selected]
        selected.extend(pool[:quota])
    if len(selected) < TARGET_DAILY:
        selected.extend([p for p in ranked if p not in selected][: TARGET_DAILY - len(selected)])

    selected = sorted(selected[:TARGET_DAILY], key=lambda p: (p["score"], p.get("publication_date") or ""), reverse=True)
    return selected, page


def main() -> None:
    now = datetime.now(BERLIN)
    data = load_json(DATA, {"papers": [], "search_state": {"backfill_page": 1}})
    metrics = load_json(METRICS, {})
    queries = load_queries()

    existing = list(data.get("papers") or [])
    seen = {canonical_key(p) for p in existing if canonical_key(p)}

    selected, next_page = collect_unseen(queries, seen, metrics, now, data)

    if API["ok"] == 0:
        print("OpenAlex did not return any successful response. Existing papers.json is preserved.", file=sys.stderr)
        sys.exit(0)

    # Previously pushed papers become history before the new daily batch is inserted.
    for p in existing:
        p["archive"] = True
        # Reapply journal metrics to old records where possible.
        impact_factor, quartile, metric_year = metric_lookup(p.get("journal", ""), p.get("journal_issn", []) or [], metrics)
        if impact_factor:
            p["impact_factor"] = impact_factor
        if quartile:
            p["quartile"] = quartile
        if metric_year:
            p["metric_year"] = metric_year

    archive = existing[:MAX_ARCHIVE]
    papers = selected + archive
    match_score = round(sum(int(p.get("score") or 0) for p in selected) / len(selected)) if selected else 0

    out = {
        "version": 4,
        "brief_date": now.strftime("%Y · %m · %d"),
        "last_updated": now.strftime("%Y-%m-%d %H:%M %Z"),
        "target_daily": TARGET_DAILY,
        "match_score": match_score,
        "search_state": {"backfill_page": next_page},
        "papers": papers,
    }
    DATA.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Selected {len(selected)} unseen papers for today's digest; archived {len(archive)} previous papers.")
    if len(selected) < TARGET_DAILY:
        print(f"Only {len(selected)} sufficiently relevant unseen papers were available; the script will not pad with catalyst-design/off-topic papers.")
    print(f"OpenAlex requests: ok={API['ok']} failed={API['failed']} circuit_open={API['circuit_open']}")


if __name__ == "__main__":
    main()
