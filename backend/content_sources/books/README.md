# E-book PDFs (ADR-032)

Put the textbook PDFs for the Library here, named exactly as in
`backend/scripts/ingest_books.py`'s `BOOKS` list, e.g.
`everything-maths-grade-10.pdf`. PDFs in this folder are gitignored.

Use the **unbranded Siyavula editions (CC-BY 3.0)**, which allow commercial use
with attribution. Do not add DBE "Mind the Gap" guides (non-commercial
licence). Check the licence page inside each PDF first.

Then, from `backend/`:

```powershell
python -m scripts.ingest_books --outline everything-maths-grade-10.pdf   # helps fill topic page ranges
python -m scripts.ingest_books
```
