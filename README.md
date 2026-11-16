# DocuMind AI — Legal & Corporate Records Intelligence

A shared, permission-controlled records system for an organization's legal documents.
Upload contracts, NDAs, leases, law books, policies — printed, scanned or **handwritten** — and:

- **Look up facts** stored in a records register: *"When was the NDA with Acme signed?"* → answered from a verified database field, with the page it came from.
- **Ask questions** of long reference documents (law books, handbooks): answers cite the section and page.
- **Find documents**: hybrid keyword + semantic search.
- **Open the source**: every answer opens the PDF at the right page with the evidence highlighted.
- **RBAC**: organizations, departments, roles (Admin / Manager / Employee / Auditor), department-only and restricted documents. Permission checks happen *before* retrieval.
- **History**: (1) query history, (2) document versions with field-level comparison, (3) edit history of every corrected field, (4) an append-only audit log.

## Architecture

```
Vue 3 SPA ──REST/JWT──> Django + DRF ──> PostgreSQL 16 + pgvector (HNSW) + full-text (GIN)
                              │
                              ├── worker (python manage.py run_worker): DB-backed job queue
                              │     extract → OCR / handwriting → classify → structure-aware chunking
                              │     → embeddings → record-field extraction + grounding check
                              │
                              └── ai/ gateway: LLM (Groq gpt-oss-20b), vision LLM (Gemini) for handwriting,
                                   local MiniLM embeddings, optional fine-tuned clause classifier
```

| App | Responsibility |
|---|---|
| `accounts/` | Organizations, departments, memberships, roles, permission classes |
| `documents/` | Documents, versions, pages, chunks, record fields, field edits, ingestion pipeline, access rules (`access.py`) |
| `assistant/` | Query router (`router.py`), hybrid retrieval (`retrieval.py`), answer engine (`engine.py`), conversations |
| `audit/` | Append-only `AuditEvent` + `record()` helper |
| `ai/` | LLM gateway (`llm.py`), embeddings, OCR/handwriting, clause-classifier hook |
| `ml/` | Fine-tuning + evaluation scripts |
| `frontend/` | Vue 3 + Tailwind 4 SPA |
| `legacy/` | The original v1 code, kept for reference (not used) |

## Setup (Windows)

Prerequisites: Python 3.12+, Node 20+, Docker Desktop, [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).

```bash
# 1. database (pgvector)
docker start documind-postgres          # or: docker run -d --name documind-postgres -e POSTGRES_PASSWORD=mysecretpassword -p 5433:5432 pgvector/pgvector:pg16
docker exec documind-postgres psql -U postgres -c "CREATE DATABASE docuvault_db;"

# 2. backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env                  # then fill in GROQ_API_KEY and GEMINI_API_KEY
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py seed_demo # optional demo org + sample documents

# 3. run (three terminals)
venv\Scripts\python manage.py runserver
venv\Scripts\python manage.py run_worker
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Demo users created by `seed_demo`: `demo_admin`, `demo_manager`, `demo_employee`, `demo_hr`, `demo_auditor`.
Their password is set in `documents/management/commands/seed_demo.py` (or the `DEMO_PASSWORD` env var).

## Run everything with Docker

```bash
copy .env.example .env      # add GROQ_API_KEY / GEMINI_API_KEY and a real DJANGO_SECRET_KEY
docker compose up --build   # database, API, worker and web app
# open http://localhost:8080
docker compose exec backend python manage.py seed_demo   # optional demo data
```

## Reminders

The worker checks every hour for agreements that are about to expire (90 / 30 / 7 days and on the day) and for the
**last day to give notice** (expiry date minus the extracted notice period, e.g. "thirty (30) days written notice").
The uploader, admins and the department's managers get an in-app notification (the bell in the sidebar), but only if
they can open the document. Set `REMINDER_EMAILS=1` to also send e-mails. Run on demand with
`python manage.py send_reminders`. People are also notified when an upload finishes, fails, or has facts to review.

## Tests

```bash
venv\Scripts\python manage.py test documents assistant notifications
```
Covers: the RBAC visibility matrix, retrieval never returning forbidden chunks, forbidden document ids being ignored,
file endpoint protection, upload validation (extension + magic bytes), the PDF pipeline with page numbers,
structure-aware chunking, versioning and comparison, field correction history, append-only audit log, query routing,
reminder windows, notice-deadline parsing, de-duplication and reminder visibility.

## Fine-tuning

`ml/train_clause_classifier.py` fine-tunes a transformer on **LEDGAR** (80k contract clauses, 100 clause types) and saves
it to `ml/models/clause-classifier/`. The pipeline then labels every clause of every record, the document page lists the
clauses it found, and search uses the labels ("contracts with a confidentiality clause").

```bash
venv\Scripts\python ml/train_clause_classifier.py --train-limit 10000 --epochs 3 --batch-size 32 --max-length 128 --lr 1e-4  # CPU, ~70 min
venv\Scripts\python manage.py label_clauses      # label documents that were processed before the model existed
venv\Scripts\python ml/baselines.py tfidf         # classic baseline
venv\Scripts\python ml/baselines.py llm --eval-limit 200   # zero-shot LLM baseline
```
On a GPU (Colab/Kaggle) drop `--train-limit` and raise `--epochs` for the best score.

## Evaluation (`evaluation/`)

| Command | What it measures |
|---|---|
| `python -m evaluation.eval_retrieval --n 60` | Retrieval on CUAD contracts: semantic vs keyword vs hybrid, section-aware vs fixed chunks (Hit@k, MRR) |
| `python -m evaluation.eval_extraction --n 40` | Record-field extraction on CUAD vs lawyers' annotations (P/R/F1), grounding check, review-queue catch rate |
| `python -m evaluation.eval_router` | Routing accuracy on 100 labelled questions, LLM vs keyword fallback |
| `python -m evaluation.eval_handwriting [--folder scans]` | Tesseract vs vision model CER/WER (synthetic set by default; pass real scans) |
| `python -m evaluation.report` | Writes every result into **[docs/EVALUATION.md](docs/EVALUATION.md)** |

Raw results are kept in `evaluation/results/*.json`.
