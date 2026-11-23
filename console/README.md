# THUTOra Console

Zynora's internal tool (ADR-051). Not a school product: schools never see it.

```powershell
cd console
npm install      # first time
npm run dev      # http://localhost:5174 (the API must be running on :8000)
```

Create the first director from `backend` with the venv active:

```powershell
python -m scripts.console_staff create --email you@zynoratech.co.za --name "Your Name" --role director
```

Production: see `docs/RUNBOOK.md`, section 4c.
