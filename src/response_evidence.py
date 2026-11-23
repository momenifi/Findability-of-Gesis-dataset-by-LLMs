"""Conservative, inspectable evidence extracted from saved dataset answers.

These rules describe model claims; they do not verify live pages or external
repository ownership. Ambiguous attribution is left unresolved.
"""

import json
import re
from urllib.parse import urlparse


REPOSITORIES = {
    "GESIS": r"\bGESIS\b",
    "ICPSR": r"\bICPSR\b",
    "CESSDA": r"\bCESSDA\b",
    "DANS": r"\bDANS\b",
    "UK Data Service": r"\bUK Data Service\b",
    "Dataverse": r"\b(?:Harvard\s+)?Dataverse\b",
    "Zenodo": r"\bZenodo\b",
    "PsychArchives": r"\bPsychArchives\b",
    "Kaggle": r"\bKaggle\b",
    "Mendeley Data": r"\bMendeley Data\b",
}
FAILURE = re.compile(
    r"\b(?:no (?:verified |matching |exact |specific )*(?:dataset|download link|database record)"
    r"|(?:could not|couldn't|cannot|can't|unable to|did not) (?:be )?"
    r"(?:find|locate|identify|verify)\b|(?:could|can) not be found"
    r"|not (?:deposited|available|found)|hosting .*?unconfirmed)", re.I,
)
ATTRIBUTION = re.compile(
    r"(?:hosted|archived|deposited|provided|published|distributed|available|accessible|"
    r"accessed|download(?:ed)?|belongs|sourced|archiving|data provider|database\s*:|"
    r"catalog(?:ue|ued|ed)|indexed|listed)", re.I,
)
CATALOGUE = re.compile(r"catalog(?:ue|ued|ed)|indexed|listed", re.I)


def clean(value):
    text = str(value).strip() if value is not None else ""
    return "" if text.lower() in {"nan", "none", "<na>"} else text


def response_evidence(justification, link):
    text, link = clean(justification), clean(link)
    mentions, providers, catalogues = set(), set(), set()
    # Sentence-level rules intentionally abstain on mixed negative claims.
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        names = {name for name, pattern in REPOSITORIES.items() if re.search(pattern, sentence, re.I)}
        mentions.update(names)
        if FAILURE.search(sentence) or not ATTRIBUTION.search(sentence):
            continue
        for name in names:
            if name == "CESSDA":
                if CATALOGUE.search(sentence):
                    catalogues.add(name)
            else:
                providers.add(name)
    failure_only = bool(not link and FAILURE.search(text))
    host = (urlparse(link).hostname or "").lower()
    link_repository = ""
    for domain, name in (("gesis.org", "GESIS"), ("cessda.eu", "CESSDA"),
                         ("icpsr.umich.edu", "ICPSR"), ("dans.knaw.nl", "DANS"),
                         ("zenodo.org", "Zenodo"), ("ukdataservice.ac.uk", "UK Data Service")):
        if host == domain or host.endswith("." + domain):
            link_repository = name
            break
    return {
        "reports_not_found_without_link": int(failure_only),
        "repository_mentions": json.dumps(sorted(mentions)),
        "claimed_data_providers": json.dumps(sorted(providers)),
        "claimed_catalogues": json.dumps(sorted(catalogues)),
        "mentions_gesis": int("GESIS" in mentions),
        "claims_gesis_provider": int("GESIS" in providers),
        "claims_cessda_catalogue": int("CESSDA" in catalogues),
        "returned_link_repository": link_repository,
        "repository_attribution_status": "positive_claim" if providers else "unresolved",
    }
