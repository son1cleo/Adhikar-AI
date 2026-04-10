# Adhikar AI

Adhikar AI is a civic intelligence prototype for Dhaka residents. It classifies a complaint, retrieves the relevant Citizen Charter policy, drafts a formal complaint email, and logs the issue for analytics.

## What is included

- LangGraph workflow for validation, classification, retrieval, drafting, and logging
- ChromaDB-backed charter store with 1000-character chunks and overlap
- Formal complaint generation with a policy-vs-reality breakdown
- Streamlit dashboard with complaint intake and heatmap-style analytics
- Sample charter and contact data so the demo runs immediately

## Quick start

1. Create and activate a Python environment.
2. Install dependencies with your preferred tool, for example `uv sync` or `pip install -e .`.
3. Run the app:

```bash
streamlit run src/adhikar_ai/app.py
```

## Using real charter PDFs

Place official DNCC and DSCC charter PDFs in `data/charters/`, or point the ingest command at the folder where you downloaded them, then run:

```bash
python -m adhikar_ai.ingest
```

If the PDFs are stored somewhere else:

```bash
python -m adhikar_ai.ingest --charter-dir "C:\\path\\to\\your\\downloaded\\charters"
```

The app will read both PDFs and text files from that folder and rebuild the persistent Chroma collection.

## Demo flow

Try this input:

- Issue: Huge garbage pile in Mirpur Ward 7 for 3 days
- Location: Mirpur Ward 7
- Wait time: 3 days

The app should classify it as Waste, retrieve the waste-service charter text, and draft a complaint email to the relevant DNCC contact.
