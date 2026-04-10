# Adhikar AI

Adhikar AI is a civic intelligence prototype for Dhaka residents. It classifies a complaint, retrieves the relevant Citizen Charter policy, enriches it with web context, drafts a formal complaint email, and logs the issue for analytics.

## What is included

- LangGraph multi-agent workflow for validation, classification, Brave context enrichment, retrieval, violation analysis, action generation, and logging
- Groq-backed reasoning and response drafting with deterministic fallback when no API key is present
- ChromaDB-backed charter store with Bangla-aware chunking using `।`
- Passwordless login by name and email, with persistent chat history in Supabase when configured
- Formal complaint generation with policy-vs-reality breakdown, email drafting, and optional send-to-authority flow
- Streamlit dashboard with complaint intake, ward-level analytics, and map visualization
- Sample charter and contact data so the demo runs immediately

## Quick start

1. Create and activate a Python environment.
2. Install dependencies with your preferred tool, for example `uv sync` or `pip install -e .`.
3. Set any optional API keys or database credentials you want to use:

```bash
GROQ_API_KEY=...
BRAVE_SEARCH_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SMTP_HOST=...
SMTP_USERNAME=...
SMTP_PASSWORD=...
EMAIL_FROM_ADDRESS=...
```

4. Run the app:

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

The app should classify it as Waste, retrieve the waste-service charter text, enrich the answer if Brave is configured, and draft a complaint email to the relevant DNCC contact.

## Supabase setup

If you want persistent chat sessions and history, create these tables in Supabase:

```sql
create table users (
	id uuid primary key default gen_random_uuid(),
	email text unique not null,
	name text not null,
	created_at timestamptz default now()
);

create table chat_sessions (
	id uuid primary key default gen_random_uuid(),
	user_id uuid references users(id),
	created_at timestamptz default now(),
	last_activity timestamptz default now()
);

create table chat_messages (
	id uuid primary key default gen_random_uuid(),
	session_id uuid references chat_sessions(id),
	role text not null,
	content text not null,
	timestamp timestamptz default now()
);

create table policy_violations (
	id uuid primary key default gen_random_uuid(),
	session_id uuid references chat_sessions(id),
	user_id uuid references users(id),
	category text,
	location text,
	ward text,
	policy_deadline_hours int,
	user_duration_hours int,
	is_violation boolean,
	compliance_status text,
	complaint_json jsonb,
	created_at timestamptz default now()
);
```
