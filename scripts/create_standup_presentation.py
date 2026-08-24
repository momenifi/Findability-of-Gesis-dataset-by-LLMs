from __future__ import annotations

import html
import zipfile
from pathlib import Path


OUT = Path("reports/model_comparison/standup_llm_findability_overview.pptx")

SLIDE_W = 13_333_333
SLIDE_H = 7_500_000


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def tx_body(lines: list[str], font_size: int = 2400, bold_first: bool = False) -> str:
    paragraphs = []
    for i, line in enumerate(lines):
        bold = ' b="1"' if bold_first and i == 0 else ""
        paragraphs.append(
            f"""
            <a:p>
              <a:r>
                <a:rPr lang="en-US" sz="{font_size}"{bold}/>
                <a:t>{esc(line)}</a:t>
              </a:r>
              <a:endParaRPr lang="en-US" sz="{font_size}"/>
            </a:p>"""
        )
    return f"""
    <p:txBody>
      <a:bodyPr wrap="square"/>
      <a:lstStyle/>
      {''.join(paragraphs)}
    </p:txBody>"""


def shape(idx: int, name: str, x: int, y: int, cx: int, cy: int, lines: list[str], font_size: int = 2400, fill: str | None = None, line: str | None = None, bold_first: bool = False) -> str:
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    line_xml = f'<a:ln><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else "<a:ln><a:noFill/></a:ln>"
    return f"""
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{idx}" name="{esc(name)}"/>
        <p:cNvSpPr txBox="1"/>
        <p:nvPr/>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        {fill_xml}
        {line_xml}
      </p:spPr>
      {tx_body(lines, font_size, bold_first)}
    </p:sp>"""


def title(text: str) -> str:
    return shape(2, "Title", 500_000, 280_000, 12_300_000, 700_000, [text], 3400, bold_first=True)


def result_table(start_id: int, x: int, y: int) -> str:
    rows = [
        ["Variant", "Provider", "Strict Source Hits", "GESIS Hits"],
        ["V3 Title", "OpenAI", "36 / 100 = 36%", "72 / 100 = 72%"],
        ["V3 Title", "Gemini", "63 / 100 = 63%", "78 / 100 = 78%"],
        ["V6 Need", "OpenAI", "23 / 87 = 26%", "46 / 87 = 53%"],
        ["V6 Need", "Gemini", "28 / 87 = 32%", "44 / 87 = 51%"],
        ["V2 Topic", "OpenAI", "14 / 250 = 6%", "58 / 250 = 23%"],
        ["V2 Topic", "Gemini", "6 / 250 = 2%", "41 / 250 = 16%"],
        ["V1 Meta", "OpenAI", "6 / 85 = 7%", "32 / 85 = 38%"],
        ["V1 Meta", "Gemini", "1 / 85 = 1%", "23 / 85 = 27%"],
    ]
    col_w = [2_300_000, 2_050_000, 3_650_000, 3_650_000]
    row_h = 460_000
    out = []
    sid = start_id
    for r, row in enumerate(rows):
        cx = x
        for c, text in enumerate(row):
            is_header = r == 0
            is_title_row = r in (1, 2)
            fill = "2F6F9F" if is_header else ("EEF3F8" if is_title_row else "FFFFFF")
            font_size = 1650 if is_header else 1500
            out.append(
                shape(
                    sid,
                    f"TableCell{r}_{c}",
                    cx,
                    y + (r * row_h),
                    col_w[c],
                    row_h,
                    [text],
                    font_size,
                    fill=fill,
                    line="D8D8D8",
                    bold_first=True,
                )
            )
            sid += 1
            cx += col_w[c]
    return "".join(out)


def variant_table(start_id: int, x: int, y: int) -> str:
    rows = [
        ["Variant", "Query Type", "Purpose"],
        ["V3 Title", "dataset title only", "discoverability baseline"],
        ["V1 Metadata", "all topics + country + decade", "structured metadata search"],
        ["V2 Topic", "one topic + country + decade", "simpler topic signal"],
        ["V6 Need", "V1 + abstract-derived query", "natural research need"],
    ]
    col_w = [2_050_000, 4_300_000, 5_300_000]
    row_h = 650_000
    out = []
    sid = start_id
    for r, row in enumerate(rows):
        cx = x
        for c, text in enumerate(row):
            is_header = r == 0
            fill = "2F6F9F" if is_header else ("EEF3F8" if row[0] == "V3 Title" else "FFFFFF")
            font_size = 1700 if is_header else 1600
            out.append(
                shape(
                    sid,
                    f"VariantCell{r}_{c}",
                    cx,
                    y + (r * row_h),
                    col_w[c],
                    row_h,
                    [text],
                    font_size,
                    fill=fill,
                    line="D8D8D8",
                    bold_first=True,
                )
            )
            sid += 1
            cx += col_w[c]
    return "".join(out)


def slide_xml(slide_num: int, body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {body}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def rels_xml(targets: list[tuple[str, str]]) -> str:
    rels = []
    for i, (typ, target) in enumerate(targets, start=1):
        rels.append(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{typ}" Target="{target}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>"""


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    slide1 = slide_xml(
        1,
        title("LLM-Based Findability of GESIS Datasets")
        + shape(
            3,
            "Goal",
            650_000,
            1_250_000,
            5_800_000,
            2_250_000,
            [
                "Goal",
                "Evaluate whether LLMs with web search can discover GESIS datasets.",
                "Sample: 100 GESIS datasets.",
                "Evaluation corpus: full GESIS metadata.",
                "Providers: OpenAI API and Gemini; OpenWebUI as context check.",
            ],
            2050,
            fill="EEF3F8",
            line="C9D6E2",
            bold_first=True,
        )
        + shape(
            4,
            "Evaluation",
            6_850_000,
            1_250_000,
            5_800_000,
            2_250_000,
            [
                "Evaluation",
                "Strict Source: exact sampled dataset via DOI/URL/ID.",
                "Source: exact sampled dataset via identifier or title match.",
                "Strict GESIS: any relevant GESIS dataset via DOI/URL/ID.",
                "GESIS: any relevant GESIS dataset via identifier or title match.",
            ],
            1950,
            fill="F7F7F7",
            line="D8D8D8",
            bold_first=True,
        )
        + shape(
            5,
            "Framing",
            650_000,
            4_150_000,
            12_000_000,
            1_600_000,
            [
                "Framing",
                "The study moves from SEO to GEO: not only whether dataset pages are indexed, but whether generative search systems can discover, identify, and cite them.",
            ],
            2200,
            fill="FFF6E8",
            line="E6C88F",
            bold_first=True,
        ),
    )

    slide2 = slide_xml(
        2,
        title("Prompt Variants")
        + variant_table(3, 840_000, 1_250_000)
        + shape(
            25,
            "VariantNote",
            650_000,
            5_250_000,
            12_000_000,
            1_000_000,
            [
                "Interpretation: V3 asks whether the dataset is discoverable at all. V6 asks whether richer natural-language context helps when the title is unknown.",
            ],
            2000,
            fill="FFF6E8",
            line="E6C88F",
            bold_first=True,
        ),
    )

    slide3 = slide_xml(
        3,
        title("Main Results: OpenAI vs Gemini")
        + result_table(3, 840_000, 1_100_000)
        + shape(
            40,
            "Takeaways",
            650_000,
            6_000_000,
            12_000_000,
            1_000_000,
            [
                "Takeaways: V3 is the title baseline; V6 is the strongest realistic non-title variant. V2 has more prompts because it splits topics. Results support the GEO framing.",
            ],
            2000,
            fill="EAF5EF",
            line="A8D0B8",
            bold_first=True,
        ),
    )

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slides/slide3.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""

    presentation = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId2"/>
    <p:sldId id="257" r:id="rId3"/>
    <p:sldId id="258" r:id="rId4"/>
  </p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

    master = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>"""

    layout = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""

    theme = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office"><a:dk1><a:srgbClr val="1F2933"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="44546A"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2><a:accent1><a:srgbClr val="2F6F9F"/></a:accent1><a:accent2><a:srgbClr val="70AD47"/></a:accent2><a:accent3><a:srgbClr val="FFC000"/></a:accent3><a:accent4><a:srgbClr val="5B9BD5"/></a:accent4><a:accent5><a:srgbClr val="A5A5A5"/></a:accent5><a:accent6><a:srgbClr val="ED7D31"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Office"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Office"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels_xml([("officeDocument", "ppt/presentation.xml")]))
        z.writestr(
            "ppt/_rels/presentation.xml.rels",
            rels_xml(
                [
                    ("slideMaster", "slideMasters/slideMaster1.xml"),
                    ("slide", "slides/slide1.xml"),
                    ("slide", "slides/slide2.xml"),
                    ("slide", "slides/slide3.xml"),
                ]
            ),
        )
        z.writestr("ppt/presentation.xml", presentation)
        z.writestr("ppt/slideMasters/slideMaster1.xml", master)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels_xml([("slideLayout", "../slideLayouts/slideLayout1.xml"), ("theme", "../theme/theme1.xml")]))
        z.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", rels_xml([("slideMaster", "../slideMasters/slideMaster1.xml")]))
        z.writestr("ppt/theme/theme1.xml", theme)
        for i, s in enumerate([slide1, slide2, slide3], start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", s)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", rels_xml([("slideLayout", "../slideLayouts/slideLayout1.xml")]))

    print(OUT)


if __name__ == "__main__":
    build()
