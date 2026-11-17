# E-book files (ADR-032)

Put the textbooks for the Library here, named exactly as in
`backend/scripts/ingest_books.py`'s `BOOKS` list:

- `everything-maths-grade-10.epub`, `everything-maths-grade-11.epub`, `everything-maths-grade-12.epub`
- `everything-science-grade-10.epub`, `everything-science-grade-11.epub`, `everything-science-grade-12.epub`

Use Siyavula's **unbranded CC BY ePub** editions. Siyavula's PDFs are the
branded **CC BY-ND** editions, and the importer refuses them (it reads each
book's own licence statement). Never add DBE "Mind the Gap" guides
(non-commercial). Files in this folder are gitignored.

Windows hides file extensions: name the file `everything-maths-grade-10`
and let Windows add `.epub`, or you'll get `….epub.epub`.

Then, from `backend/`:

```powershell
python -m scripts.ingest_books --outline everything-maths-grade-10.epub   # sections + licence found
python -m scripts.ingest_books
```
