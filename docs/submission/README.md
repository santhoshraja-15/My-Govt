# BCSE302P submission pack

| File | What it is |
|---|---|
| `MyGovt_Project_Report.docx` | Word report, sections 1–11 as required by the lab guidelines |
| `MyGovt_Final_PPT.pptx` | Final presentation (43 slides, guideline order) |
| `sql_evidence.json`, `lab_queries.sql` | Every SQL statement shown in the documents with the output PostgreSQL returned |
| `images/` | Application and ER-diagram screenshots |

**Before submitting, fill the bracketed placeholders** (student names, register numbers, faculty name) on the title page of both documents.

Rebuild (needs the demo stack, `python-docx`, `python-pptx`, `Pillow`):

```
cd backend && python -m scripts.demo_env --db mygovt_dev_report --reset      # disposable copy; never run the DML on mygovt_dev_demo
python ../docs/submission/run_sql_evidence.py --dsn postgresql://postgres@localhost:5432/mygovt_dev_report --out ../docs/submission
cd ../frontend && node audit/submission_shots.js ../docs/submission/images
python ../docs/submission/build_documents.py --dsn postgresql://postgres@localhost:5432/mygovt_dev_report
```

Honest limits: the stored procedure is illustrative (created only on the scratch DB; the app has none); 3NF is argued from the design, not tool-verified; government records are provisional.
