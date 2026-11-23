"""Build the editable discussion deck for GESIS discoverability."""

from pathlib import Path
import csv

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "discoverability_improvements.pptx"
INK = "243236"
MUTED = "58686D"
TEAL = "147D73"
CORAL = "B84C3D"
WHITE = "FFFFFF"
BG = "FAFBFC"
LINE = "DCE4E5"


def box(slide, x, y, w, h, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color)
    shape.line.fill.background()
    return shape


def text(slide, value, x, y, w, h, size=19, color=INK, bold=False):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(0.015)
    frame.margin_top = frame.margin_bottom = Inches(0.015)
    for index, line in enumerate(value.split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = RGBColor.from_string(color)
        paragraph.space_after = Pt(8)
    return shape


def base(prs, number, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string(BG)
    box(slide, 0, 0, 13.333, 0.09, TEAL)
    text(slide, "GESIS / AI-MEDIATED DATA DISCOVERY", .65, .37, 11.5, .3, 11, TEAL, True)
    text(slide, title, .65, .95, 12.0, .65, 31, INK, True)
    text(slide, subtitle, .65, 1.72, 11.9, .65, 17, MUTED)
    box(slide, .65, 6.97, 12.0, .012, LINE)
    text(slide, "Discussion: proposed improvements, to be tested", .65, 7.10, 10.8, .23, 10, MUTED)
    text(slide, f"{number:02d} / 05", 11.85, 7.10, .8, .23, 10, MUTED)
    return slide


def note(slide, value):
    slide.notes_slide.notes_text_frame.text = value


def results_table(slide):
    variants = [
        ("V1  All topics + country + time", "v1_all_topics"),
        ("V2  Single topic + country + time", "v2_single_topic"),
        ("V3  Title (original wording)", "v3_title_only"),
        ("V6  V1 + abstract research need", "v6_all_topics_abstract_natural_language"),
    ]
    headings = ["Query variant", "n", "Source\nOpenAI", "Source\nGemini",
                "Relevant GESIS\nOpenAI", "Relevant GESIS\nGemini"]
    table = slide.shapes.add_table(5, 6, Inches(.65), Inches(2.55), Inches(12), Inches(2.95)).table
    for column, width in zip(table.columns, [3.40, .80, 1.65, 1.65, 2.25, 2.25]):
        column.width = Inches(width)
    table.rows[0].height = Inches(.67)
    notes = []
    for index, (label, folder) in enumerate(variants, 1):
        audits = []
        for provider_folder in ("full_metadata_model_comparison", "gemini_websearch"):
            path = ROOT / "output" / provider_folder / folder / "metrics_summary_audit.csv"
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter=";"))
            if len(rows) != 1:
                raise ValueError(f"Expected one provider/model summary in {path}")
            audits.append(rows[0])
            notes.append(f"Source: {path.relative_to(ROOT)}; model={rows[0]['model']}; "
                         f"requests={rows[0]['requests']}; responses with items={rows[0]['responses_with_items']}")
        counts = [int(row["requests"]) for row in audits]
        if counts[0] != counts[1]:
            raise ValueError(f"Different prompt counts for {folder}; show provider-specific denominators")

        def value(row, field):
            rate = float(row[field])
            hits = round(rate * int(row["requests"]))
            return f"{hits}/{row['requests']} ({rate:.0%})"

        values = [label, str(counts[0]),
                  value(audits[0], "strict_source_hit_at_k_all_queries"),
                  value(audits[1], "strict_source_hit_at_k_all_queries"),
                  value(audits[0], "strict_gesis_relevant_hit_at_k_all_queries"),
                  value(audits[1], "strict_gesis_relevant_hit_at_k_all_queries")]
        for col, content in enumerate(values):
            table.cell(index, col).text = content
    for col, heading in enumerate(headings):
        table.cell(0, col).text = heading
    for i, row in enumerate(table.rows):
        for j, cell in enumerate(row.cells):
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(TEAL if i == 0 else ("EEF4F4" if i % 2 else WHITE))
            cell.margin_left = cell.margin_right = Inches(.10)
            cell.margin_top = Inches(.10)
            cell.margin_bottom = Inches(.04)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = "Aptos"
                paragraph.font.size = Pt(14 if i == 0 else 15)
                paragraph.font.bold = i == 0 or j == 0
                paragraph.font.color.rgb = RGBColor.from_string(WHITE if i == 0 else INK)
                paragraph.space_after = Pt(0)
    return notes


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = "Improving GESIS Dataset Discoverability"
    prs.core_properties.subject = "Lessons from our experiments and two SEASON 2026 studies"
    prs.core_properties.author = "GESIS dataset-discovery study"

    slide = base(prs, 1, "Our study: finding GESIS datasets with AI",
                 "We tested discovery through OpenAI and Gemini with web search enabled.")
    box(slide, .65, 2.58, 5.62, .045, TEAL)
    box(slide, 6.93, 2.58, 5.72, .045, CORAL)
    text(slide, "WHAT WE TESTED", .65, 2.82, 5.6, .35, 13, TEAL, True)
    text(slide, "WHAT WE LEARNED", 6.93, 2.82, 5.7, .35, 13, CORAL, True)
    tested = [
        "100 random datasets and 10 popular datasets.",
        "Title searches and topic, country and time queries.",
        "Richer queries using abstract-derived research needs.",
    ]
    learned = [
        "Recognising a title does not guarantee the correct link.",
        "Richer descriptions helped discovery in some runs.",
        "Results varied across providers and repeated runs.",
    ]
    for index in range(3):
        y = 3.43 + index * .77
        text(slide, tested[index], .65, y, 5.62, .66, 20)
        text(slide, learned[index], 6.93, y, 5.72, .66, 20)
    box(slide, .65, 6.02, 12, .70, TEAL)
    text(slide, "Assess dataset identity, link correctness and repository attribution separately.",
         .88, 6.21, 11.55, .40, 17, WHITE, True)
    note(slide,
         "Overview of our saved GESIS dataset-discovery experiments: 100 sampled records and an additional "
         "set of 10 popular/requested datasets, using direct OpenAI and Gemini APIs with web search. "
         "Variants tested title-only searches, single or all topics with country and decade, and all topics "
         "plus a natural-language need generated from the abstract. Eligibility varies because not every "
         "record has the required metadata; not all variants contain 100 or 10 prompts.\n\n"
         "Dataset names can be correct while returned identifiers are missing, wrong or refer to another "
         "version. Richer query descriptions helped in some runs; this is not evidence that changing "
         "landing pages has already improved retrieval. Provider comparisons depend on exact prompts, "
         "model versions and retrieval settings; some historical V6 comparisons used differing generated "
         "queries. Repeated-run variation is observational, not a controlled attribution of its causes. "
         "This overview deliberately avoids combining numerical results from different evaluation revisions. "
         "Repository mentions must be distinguished from positive, correct provider attribution.")

    slide = base(prs, 2, "100-dataset sample: retrieval results",
                 "Saved web-search runs: strict identifier-based hits, including unanswered queries in the denominator.")
    sources = results_table(slide)
    text(slide, "Source = original sampled dataset. Relevant GESIS = any dataset in the query's reference set.",
         .65, 5.74, 12, .36, 13, MUTED)
    text(slide, "V2 has multiple prompts per dataset. V6 prompts differ between providers; that comparison is indicative.",
         .65, 6.13, 12, .38, 13, MUTED)
    text(slide, "Saved Sep-Oct 2026 audits, before the bilingual matching update. Evaluation cutoff: 10; no prompt result limit.",
         .65, 6.55, 12, .32, 11, MUTED)
    note(slide,
         "Historical results snapshot read directly from saved full-run metrics_summary_audit.csv files, "
         "not from the newer five-source-row tests or the separate download-title experiment. "
         "Rates describe prompts, not the proportion of 100 unique datasets. The displayed counts include "
         "all configured requests, including errors and empty answers. V1 has 85 eligible prompts, V2 250 "
         "single-topic prompts, V3 100 title prompts, and V6 87 eligible prompts. Metadata completeness "
         "and different prompt cohorts limit direct variant comparisons.\n\n"
         "Strict source hits use the original dataset identifier or accepted identifier aliases in the "
         "saved evaluation. Strict relevant-GESIS hits refer to identifiers in the metadata-derived qrels, "
         "not arbitrary GESIS mentions. These metrics do not independently verify live links. Original "
         "title-search wording is used here; do not combine it with the subsequent download-title run.\n\n"
         "Full-run audit snapshots are from September 23, 2026, except Gemini V3 from October 1, 2026. "
         "They have not been regenerated with the later bilingual-title and explicit-failure corrections. "
         "Title-index changes can affect version aliasing, so do not label these values as the latest "
         "corrected evaluation. V1, V2 and V3 prompt texts match across providers. V6 generated needs differ "
         "between providers in these historical runs; no causal provider ranking is justified for V6.\n\n"
         + "\n".join(sources))

    slide = base(prs, 3, "What can help AI systems discover research data?",
                 "Three sources of evidence point to richer descriptions and more reliable identification.")
    evidence = [
        ("OUR EXPERIMENTS", "Discovery and links differ",
         "Richer research prompts helped in some runs.\nCorrect dataset names sometimes came with missing or incorrect links.",
         "Prompt enrichment, not a landing-page intervention.", TEAL),
        ("SIEBENLIST & GNYP (2026)", "Improve description quality",
         "Generated summaries can enrich topic, time and place coverage.\nHuman review remains necessary.",
         "Description-quality assessment; not a retrieval trial.", TEAL),
        ("ELMALAHA (2026)", "Cover related information needs",
         "Content spanning several topic angles increased citations in a small commercial experiment.",
         "Preliminary evidence; transfer to research data is untested.", CORAL),
    ]
    for index, (label, heading, body, limit, color) in enumerate(evidence):
        x = .65 + index * 4.12
        box(slide, x, 2.65, 3.65, .045, color)
        text(slide, label, x, 2.85, 3.65, .32, 12, color, True)
        text(slide, heading, x, 3.38, 3.65, .85, 23, INK, True)
        text(slide, body, x, 4.34, 3.65, 1.55, 18)
        text(slide, limit, x, 6.10, 3.65, .55, 12, MUTED)
    note(slide,
         "Our experiments: richer query descriptions were useful in some saved runs, but model/provider "
         "differences, variable responses and evolving evaluation prevent a causal claim about landing-page design. "
         "A matching title alone does not establish correct dataset discovery.\n\n"
         "Study 38: Tobias Siebenlist and Jennifer Gnyp (2026), How Can Locally Deployed Large Language Models "
         "Improve Dataset Discovery in Open Government Data Portals? https://doi.org/10.48441/4427.3728 "
         "Evaluated 150 descriptions for 50 GovData datasets; expert review covered a subset of 15 descriptions. "
         "Results concern description quality and implications for discovery, not measured chatbot retrieval gains.\n\n"
         "Study 49: Hadeer ElMalaha (2026), Semantic Multi-Cluster Coverage and LLM Citation Frequency: "
         "A Controlled Generative Engine Optimization Experiment. https://doi.org/10.48441/4427.3734 "
         "Off-site commercial content across 11 pages and four domains, with a short before/after window. "
         "The author reports preliminary citation gains; small sample, no significance testing, and no "
         "concurrent control for later follow-up. Do not transfer the reported percentage gains to GESIS.")

    slide = base(prs, 4, "Practical improvements to test at GESIS",
                 "Make the research content understandable and the dataset identity unambiguous.")
    actions = [
        ("Complete descriptions", "Cover topics, geography, collection period, population, methods and key variables."),
        ("Researcher language", "Add grounded synonyms, research questions and concise summaries."),
        ("Clear identification", "Present title, study number, DOI, repository and access link together."),
        ("Connected records", "Explain versions, waves and series; align records across discovery catalogues."),
        ("Reviewed enrichment", "Keep authoritative metadata; add validated summaries as searchable content."),
    ]
    for index, (heading, body) in enumerate(actions):
        y = 2.62 + .77 * index
        text(slide, f"{index + 1:02d}", .65, y, .48, .4, 16, TEAL, True)
        text(slide, heading, 1.30, y, 3.05, .67, 18, INK, True)
        text(slide, body, 4.47, y, 8.12, .60, 18)
        if index < 4:
            box(slide, 1.30, y + .72, 11.30, .009, LINE)
    text(slide, "Informing evidence: our experiments; Siebenlist & Gnyp (2026); ElMalaha (2026).",
         .65, 6.66, 12, .23, 11, MUTED)
    note(slide,
         "These are proposed GESIS interventions, not effects already demonstrated by our experiment. "
         "Study 38 recommends generated descriptions as an additional weighted field alongside curated metadata, "
         "with periodic human validation. Study 49 motivates content covering related user intents, but tested "
         "off-site travel content, not dataset landing pages.\n\n"
         "Identifier presentation and version relationships are motivated by our observed title/link conflicts "
         "and ambiguous dataset versions. Our German-title evaluation bug was a matching issue and is not "
         "evidence that a GESIS page was deficient. CESSDA is a discovery catalogue; GESIS may be the data "
         "provider. Keep those roles distinct.\n\n"
         "References: https://doi.org/10.48441/4427.3728 ; https://doi.org/10.48441/4427.3734")

    slide = base(prs, 5, "Test improvements before scaling",
                 "Use a controlled pilot to distinguish useful changes from normal AI-search variation.")
    steps = [
        ("01  Establish a baseline", "Select poorly discovered datasets and comparable unchanged controls."),
        ("02  Change selected pages", "Test description enrichment and identifier presentation separately."),
        ("03  Repeat fixed prompts", "Check title and metadata queries across systems before and after changes."),
    ]
    for index, (heading, body) in enumerate(steps):
        y = 2.65 + index * .88
        text(slide, heading, .65, y, 4.10, .48, 20, TEAL, True)
        text(slide, body, 4.95, y, 7.65, .70, 18)
    box(slide, .65, 5.47, 12, .93, TEAL)
    text(slide, "MEASURE SEPARATELY", .88, 5.64, 2.50, .52, 12, WHITE, True)
    for x, label in ((3.45, "Dataset identity"), (6.42, "Link correctness"), (9.30, "Repository attribution")):
        text(slide, label, x, 5.73, 3.0, .40, 16, WHITE, True)
    text(slide, "Success means reliable discovery, beyond names or mentions alone.",
         .65, 6.60, 12, .30, 16, INK, True)
    note(slide,
         "Suggested design: use matched or randomly allocated comparable records; retain unchanged controls. "
         "Record exact prompts, input snapshots, provider/model identifiers, dates, retrieval settings and "
         "raw answers. Keep repeated measurements in both baseline and follow-up; account for re-indexing "
         "and unrelated provider changes. A title-search baseline is not a guaranteed upper bound on "
         "descriptive-query performance.\n\n"
         "Separate outcomes: correct source identity including accepted versions; DOI/URL agreement with "
         "the record, distinguishing catalogue verification from live resolution; and positive, correct "
         "repository attribution rather than a name mentioned in a failed search. For broad metadata "
         "queries also report relevant alternative GESIS datasets separately. Evaluate failures against "
         "all eligible prompts. Generated summaries need human factual review.\n\n"
         "Sources: our saved experiment responses and evaluation; Siebenlist & Gnyp (2026), "
         "https://doi.org/10.48441/4427.3728 ; ElMalaha (2026), https://doi.org/10.48441/4427.3734")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
