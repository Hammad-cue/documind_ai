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

## Tests

```bash
venv\Scripts\python manage.py test documents assistant
```
Covers: the RBAC visibility matrix, retrieval never returning forbidden chunks, forbidden document ids being ignored,
file endpoint protection, upload validation (extension + magic bytes), the PDF pipeline with page numbers,
structure-aware chunking, versioning and comparison, field correction history, append-only audit log, query routing.

## Fine-tuning and evaluation (`ml/`)

| Script | Purpose |
|---|---|
| `ml/train_clause_classifier.py` | Fine-tune Legal-BERT on LEDGAR (100 clause types). Run on Colab/Kaggle GPU; copy the output to `ml/models/clause-classifier/` and the pipeline labels every clause automatically. |
| `ml/baselines.py tfidf` / `llm` | TF-IDF + logistic regression and zero-shot LLM baselines for the same task. |
| `ml/eval_handwriting.py` | Tesseract vs vision model on your handwritten set: CER / WER / latency. |

## Status

**Done (≈60%)**: everything above, running end-to-end with the real models.

**Remaining (≈40%)**
1. Run the fine-tuning on a GPU, record metrics against both baselines, and show clause labels in the UI.
2. Evaluation datasets and runs:
   - handwriting: about 30 forms you write and transcribe yourself, plus an IAM sample
   - field extraction: F1 on about 50 CUAD contracts
   - query routing: accuracy on about 100 labelled questions
   - law-book answers: answer and citation accuracy on about 50 questions
3. Expiry/renewal reminders (email or in-app notifications).
4. Search scoped to selected documents in the UI (the API already supports `document_ids`).
5. UI polish, a deployment configuration, and the report chapters.
