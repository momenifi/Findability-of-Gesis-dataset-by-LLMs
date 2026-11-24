# Publication Documentation Templates

These are the canonical sources for the generated report README files.
Edit wording here rather than editing copies under `reports/`.

- `reports_README.md` generates `reports/README.md`.
- `current_results_README.md` generates `reports/current_results/README.md`.
- `link_validation_README.md` generates its supplementary-audit README.

Result tables and sample/provider pages are generated from saved data by
`scripts/build_publication_report.py`, not maintained in these templates.

Rebuild the full current package offline:

```powershell
python -m scripts.build_publication_report --include-link-audit
python -m scripts.build_publication_report --check
```
