# Generated Web-Search Prompts

This folder contains prompt-only CSV files for sharing and reviewing the current experiments.

## Scope

- Dataset sets: random 100 and top 10 requested/downloaded datasets.
- Providers: OpenAI API and Gemini API.
- Mode: web search only.
- Variants: V1, V2, V3, and V6.
- CSV separator: semicolon (`;`).
- CSV content: one column named `prompt`, containing the complete web-search prompt sent by the pipeline.

## Files and Row Counts

| Dataset set | File | Prompts |
| --- | --- | ---: |
| Random 100 | `v1_prompts.csv` | 85 |
| Random 100 | `v2_prompts.csv` | 250 |
| Random 100 | `v3_prompts.csv` | 100 |
| Random 100 | `v6_prompts_openai.csv` | 87 |
| Random 100 | `v6_prompts_gemini.csv` | 87 |
| Top 10 | `v1_prompts.csv` | 6 |
| Top 10 | `v2_prompts.csv` | 67 |
| Top 10 | `v3_prompts.csv` | 10 |
| Top 10 | `v6_prompts_openai.csv` | 5 |
| Top 10 | `v6_prompts_gemini.csv` | 5 |

V1 requires topic, country, and time metadata. V6 additionally requires an abstract from which the natural-language research need can be generated. Records missing required metadata do not produce prompts. V2 can contain several prompts per dataset because it creates one prompt per topic.

V1, V2, and V3 prompts are identical for OpenAI and Gemini and therefore appear only once. V6 is kept in separate provider files because its abstract-derived natural-language research need differs between the existing OpenAI and Gemini runs. This difference must be considered when comparing V6 provider results.

Regenerate these files from the experiment `queries.csv` files with:

```bash
python -m src.export_generated_prompts
```
