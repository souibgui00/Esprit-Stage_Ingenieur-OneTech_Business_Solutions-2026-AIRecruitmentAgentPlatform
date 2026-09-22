<div align="center">

# 🤖 Plateforme de Recrutement IA

### AI-Powered Intelligent Recruitment Platform

An intelligent, AI-powered recruitment platform that aggregates real job listings from multiple sources, parses and vectorizes CVs, and performs semantic matching between candidates and job offers using state-of-the-art NLP models.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/pgvector-336791?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Groq_LLM-F55036?style=flat-square" />
  <img src="https://img.shields.io/badge/Llama_3.3_70b-0467DF?style=flat-square&logo=meta&logoColor=white" />
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=flat-square" />
  <img src="https://img.shields.io/badge/JWT-000000?style=flat-square&logo=jsonwebtokens&logoColor=white" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-completed-brightgreen?style=flat-square" />
  <img src="https://img.shields.io/badge/6_live_connectors-success?style=flat-square" />
  <img src="https://img.shields.io/badge/172%2B_job_offers_indexed-success?style=flat-square" />
  <img src="https://img.shields.io/badge/architecture-hexagonal-8B5CF6?style=flat-square" />
</p>

> **Author:** Souibgui Mohamed Amine — Stage 4ème année, OneTech Business Solutions

</div>

---

## 🎬 Demo

> 📸 *Add a screenshot or short GIF here showing the app in action — e.g. uploading a CV, watching it get parsed, or browsing matched job offers.*
>
> Recommended: record a 10–15s GIF with [ScreenToGif](https://www.screentogif.com/) (Windows), [Kap](https://getkap.co/) (Mac), or [Peek](https://github.com/phw/peek) (Linux), save it to `docs/assets/demo.gif`, then embed it here:
> ```markdown
> ![Demo](docs/assets/demo.gif)
> ```
>
> No UI yet? Show a Swagger UI screenshot (`/docs`) or a sample request/response instead — it still demonstrates the API works.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Technology Stack](#2-architecture--technology-stack)
3. [Repository Structure](#3-repository-structure)
4. [Module Breakdown](#4-module-breakdown)
   - [User Management](#41-user-management)
   - [CV Management](#42-cv-management)
   - [Job Sourcing Engine](#43-job-sourcing-engine)
5. [Data Flow & Pipelines](#5-data-flow--pipelines)
6. [Database Schema](#6-database-schema)
7. [API Endpoints Reference](#7-api-endpoints-reference)
8. [Job Source Connectors](#8-job-source-connectors)
9. [AI & Machine Learning Components](#9-ai--machine-learning-components)
10. [Docker & Infrastructure](#10-docker--infrastructure)
11. [Getting Started](#11-getting-started)
12. [Environment Variables](#12-environment-variables)
13. [Progress & Roadmap](#13-progress--roadmap)

---

## 1. Project Overview

This platform is an **end-to-end AI recruitment assistant** designed for the Tunisian and international job market. Its goal is to:

- **Aggregate real job offers** from multiple platforms automatically, parsing and deduplicating them in real time.
- **Parse and understand CVs** using a combination of PDF text extraction and an LLM (Groq/Llama-3) to extract structured entities (skills, experience, education).
- **Generate semantic vector embeddings** for both CVs and job offers using the multilingual `intfloat/multilingual-e5-large` sentence transformer model.
- **Match candidates to jobs** (and vice versa) using cosine similarity search over pgvector in PostgreSQL.
- **Explain matches in plain language** using a RAG (Retrieval-Augmented Generation) pipeline backed by Groq's Llama-3 inference API.

---

## 2. Architecture & Technology Stack

The project follows a clean **Ports & Adapters (Hexagonal Architecture)** pattern to ensure decoupling between business logic, infrastructure, and external integrations.

```mermaid
graph LR
    subgraph Client
        FE[Next.js Frontend<br/>Port 3000]
    end

    subgraph Server
        BE[FastAPI Backend<br/>Port 8000]
    end

    subgraph Data
        DB[(PostgreSQL 16<br/>+ pgvector<br/>Port 5432)]
    end

    FE -->|REST / JSON| BE
    BE -->|SQLAlchemy| DB
```

### Backend Technology Stack

| Layer | Technology |
|:------|:-----------|
| Web Framework | **FastAPI 0.115** (Python 3.12) |
| ORM | **SQLAlchemy 2.0** (mapped_column, modern API) |
| Database | **PostgreSQL 16** + **pgvector extension** |
| Authentication | **JWT (python-jose)** + **bcrypt (passlib)** |
| AI Embedding Model | **intfloat/multilingual-e5-large** (via sentence-transformers) |
| LLM Inference | **Groq API** (Llama-3.3-70b-versatile) |
| PDF Parsing | **pdfplumber** |
| Web Scraping | **Playwright** + **playwright-stealth** + **BeautifulSoup4** |
| HTTP Client | **httpx**, **requests** |
| Containerization | **Docker** + **Docker Compose** |

### Frontend Technology Stack

| Layer | Technology |
|:------|:-----------|
| Framework | **Next.js** (React) |
| Containerization | **Docker** |

---

## 3. Repository Structure

```
recruitment-platform/
│
├── docker-compose.yml          # Orchestrates all 3 services (db, backend, frontend)
├── .env                        # Environment variables (DB credentials, API keys)
├── .gitignore
│
├── backend/
│   ├── Dockerfile              # Python 3.12 + PyTorch CPU + Playwright Chromium
│   ├── requirements.txt        # All Python dependencies
│   ├── main.py                 # FastAPI app entry point, CORS, router registration
│   ├── create_tables.py        # Utility script to create all DB tables
│   │
│   ├── shared/
│   │   └── database.py         # SQLAlchemy engine, SessionLocal, get_db dependency
│   │
│   ├── user_management/        # Authentication & Authorization Module
│   │   ├── models.py           # User SQLAlchemy model
│   │   ├── schemas.py          # Pydantic DTOs (UserCreate, Token, etc.)
│   │   ├── router.py           # /auth endpoints (register, login, me)
│   │   ├── security.py         # JWT creation/verification, password hashing
│   │   └── dependencies.py     # get_current_user FastAPI dependency
│   │
│   ├── cv_management/          # CV Upload, Parsing & Embedding Module
│   │   ├── models.py           # CV, Experience, Education, CVSkill SQLAlchemy models
│   │   ├── schemas.py          # Pydantic response schemas
│   │   ├── router.py           # /cvs endpoints (upload, parse, list, get)
│   │   ├── parsing_service.py  # Orchestrates PDF→Text→LLM→Embedding pipeline
│   │   ├── skill_normalization.py  # Skill name normalization utility
│   │   ├── date_parsing.py     # Date string normalization utility
│   │   ├── ports/              # Interface definitions (ITextExtractor, IEmbeddingProvider, ILLMExtractor)
│   │   └── adapters/           # Implementation of ports (PDF extractor, Groq LLM, E5 embeddings)
│   │       ├── pdf_text_extractor.py
│   │       ├── groq_llm_extractor.py
│   │       └── e5_embedding_provider.py
│   │
│   ├── job_sourcing/           # Job Offer Aggregation Engine
│   │   ├── models.py           # JobSource, JobOffer, JobOfferEmbedding, CollectionRun
│   │   ├── schemas.py          # Pydantic response schemas
│   │   ├── router.py           # /jobs endpoints (sources, collect, offers, runs)
│   │   ├── services/
│   │   │   ├── collection_service.py     # Pipeline orchestrator
│   │   │   ├── normalization_service.py  # Raw data → unified model
│   │   │   ├── deduplication_service.py  # SHA-256 fingerprint dedup
│   │   │   └── embedding_service.py      # E5 embedding for job offers
│   │   └── connectors/
│   │       ├── base.py                   # IJobConnector interface + registry
│   │       ├── __init__.py               # Connector registration on startup
│   │       ├── remotive/                 # Remotive API connector
│   │       ├── arbeitnow/                # Arbeitnow API connector
│   │       ├── jobicy/                   # Jobicy API connector
│   │       ├── themuse/                  # The Muse API connector
│   │       ├── bundesagentur/            # German Employment Agency API connector
│   │       ├── welcometothejungle/       # WTTJ Algolia API connector
│   │       ├── tanitjobs/                # TanitJobs Playwright scraper (Cloudflare blocked)
│   │       ├── indeed_rss/               # Indeed RSS connector (403 blocked)
│   │       ├── indeed/                   # Indeed scraper
│   │       └── linkedin/                 # LinkedIn connector (mock/stub)
│   │
│   ├── applications/           # Candidate Applications Module
│   │   ├── models.py           # Application, UserAutoApplySettings models
│   │   ├── schemas.py          # Pydantic response schemas
│   │   ├── router.py           # /applications endpoints
│   │   ├── application_service.py  # Business logic for applications
│   │   ├── ports/              # IApplicationChannel interface
│   │   ├── adapters/           # Playwright and SMTP channel implementations
│   │   │   ├── playwright_application_channel.py
│   │   │   └── smtp_application_channel.py
│   │   └── agents/             # ATS-specific agents (Greenhouse, Lever, etc.)
│   │
│   ├── notifications/          # Notifications Module
│   │   ├── models.py           # Notification model
│   │   ├── schemas.py          # Pydantic response schemas
│   │   ├── router.py           # /notifications endpoints
│   │   └── services.py         # Notification business logic
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── app/                    # Next.js app directory
```

---

## 4. Module Breakdown

### 4.1 User Management

Handles all identity, authentication, and authorization logic.

**Files:**
- [`models.py`](backend/user_management/models.py) — `User` table with `id`, `email`, `hashed_password`, `is_active`, `created_at`.
- [`security.py`](backend/user_management/security.py) — Password hashing via `bcrypt`, JWT token creation and verification using `python-jose`.
- [`router.py`](backend/user_management/router.py) — Exposes `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
- [`dependencies.py`](backend/user_management/dependencies.py) — FastAPI dependency `get_current_user` that extracts and validates the JWT Bearer token from request headers.

**Auth Flow:**

```mermaid
sequenceDiagram
    actor Client
    participant API as FastAPI
    Client->>API: POST /auth/login {email, password}
    API->>API: Validate password hash
    API-->>Client: JWT access_token (HS256, 30-day expiry)
    Client->>API: Request + Bearer token
    API->>API: Depends(get_current_user) validates token
    API-->>Client: Protected resource
```

---

### 4.2 CV Management

Handles CV file upload, structured data extraction, and semantic vector generation.

**Files:**
- [`models.py`](backend/cv_management/models.py) — `CV`, `Experience`, `Education`, `CVSkill`, `CVEmbedding` SQLAlchemy models.
- [`parsing_service.py`](backend/cv_management/parsing_service.py) — Orchestrates the full pipeline (text extraction → LLM extraction → DB save → embedding).
- [`adapters/e5_embedding_provider.py`](backend/cv_management/adapters/e5_embedding_provider.py) — Lazy-loaded singleton E5 model (loaded once on first call, cached in memory).
- [`router.py`](backend/cv_management/router.py) — Exposes CV upload and retrieval endpoints.

**CV Parsing Pipeline:**

```mermaid
flowchart TD
    A[User uploads PDF file] --> B["pdfplumber extracts raw text"]
    B --> C["Groq LLM (Llama-3.3-70b) extracts entities"]
    C --> C1["Full name, Email, Phone"]
    C --> C2["Skills list"]
    C --> C3["Work experiences<br/>title, company, dates, description"]
    C --> C4["Education<br/>diploma, institution, year"]
    C1 & C2 & C3 & C4 --> D["SQLAlchemy saves structured entities to PostgreSQL"]
    D --> E["E5-large encodes<br/>'query: name - skills - experiences'<br/>into 1024-dim vector"]
    E --> F[("pgvector stores vector<br/>in cv_embeddings table")]
```

**Ports & Adapters (SOLID, DDD):**
The CV parsing module uses interface-based injection to decouple business logic from AI implementations:
- `ITextExtractor` → implemented by `PDFPlumberExtractor`
- `ILLMExtractor` → implemented by `GroqLLMExtractor`
- `IEmbeddingProvider` → implemented by `E5EmbeddingProvider`

Singletons are instantiated once at module level in `router.py` and injected into `parse_cv()`.

---

### 4.3 Job Sourcing Engine

The core engine of the platform. Fetches real job listings from multiple external sources, normalizes them, deduplicates them, generates semantic vectors, and stores everything in PostgreSQL.

#### Services

| Service | File | Responsibility |
|:--------|:-----|:---------------|
| Collection Service | `services/collection_service.py` | End-to-end pipeline orchestrator |
| Normalization Service | `services/normalization_service.py` | Raw DTO → Clean `JobOffer` model |
| Deduplication Service | `services/deduplication_service.py` | SHA-256 fingerprint collision detection |
| Embedding Service | `services/embedding_service.py` | E5 vector generation for job offers |

#### Connectors

The **connector registry** (`connectors/__init__.py`) uses a plug-and-play registration system. Any connector implementing `IJobConnector` can be registered with a string key:

```python
register_connector("remotive", RemotiveConnector())
register_connector("jobicy", JobicyConnector())
register_connector("welcometothejungle", WelcomeToTheJungleAlgoliaConnector())
# etc.
```

The `CollectionService` then resolves the connector by the `JobSource.name` key from the database.

---

## 5. Data Flow & Pipelines

### Job Collection Pipeline

```mermaid
flowchart TD
    A["POST /jobs/sources/{id}/collect?keywords=python"] -->|Returns 202 immediately| B["FastAPI BackgroundTask spawned"]
    B --> C["CollectionService.run_collection()"]
    C --> D["1. Create CollectionRun record (status=RUNNING)"]
    D --> E["2. Resolve IJobConnector by source name"]
    E --> F["3. connector.fetch_offers(source, keywords)<br/>calls external API/Algolia/RSS endpoint<br/>returns List[JobOfferDTO]"]
    F --> G{"4. For each JobOfferDTO"}
    G --> H["NormalizationService.normalize()<br/>HTML strip, whitespace clean,<br/>contract type detection,<br/>SHA-256 fingerprint"]
    H --> I{"DeduplicationService.is_duplicate()?"}
    I -->|Yes| J[Skip]
    I -->|No| K["db.add(offer) + db.flush()"]
    K --> L["EmbeddingService.generate_embedding(offer)<br/>E5 encodes passage, saves 1024-dim vector"]
    G --> M["5. Update CollectionRun<br/>(status=SUCCESS, offers_collected=N)"]
```

---

## 6. Database Schema

```mermaid
erDiagram
    USERS ||--o{ CVS : owns
    CVS ||--o{ EXPERIENCES : has
    CVS ||--o{ EDUCATIONS : has
    CVS ||--o{ CV_SKILLS : has
    CVS ||--o| CV_EMBEDDINGS : generates

    JOB_SOURCES ||--o{ JOB_OFFERS : provides
    JOB_SOURCES ||--o{ COLLECTION_RUNS : tracked_by
    JOB_OFFERS ||--o| JOB_OFFER_EMBEDDINGS : generates
```

### Tables

#### `users`
| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | UUID (PK) | Auto-generated |
| `email` | VARCHAR(255) | Unique |
| `hashed_password` | VARCHAR | bcrypt hash |
| `is_active` | BOOLEAN | Default true |
| `created_at` | DATETIME | Auto |

#### `cvs`
| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK → users) | |
| `filename` | VARCHAR | Original file name |
| `full_name` | VARCHAR | Extracted by LLM |
| `email` | VARCHAR | Extracted |
| `phone` | VARCHAR | Extracted |
| `raw_text` | TEXT | Full PDF text |
| `parsed_at` | DATETIME | |

Related: `experiences`, `educations`, `cv_skills`, `cv_embeddings`

#### `job_sources`
| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | UUID (PK) | |
| `name` | VARCHAR | Key used to resolve connector (e.g. `"jobicy"`) |
| `type` | ENUM | `OFFICIAL_API`, `SCRAPER`, `MOCK` |
| `base_url` | VARCHAR | Platform URL |
| `is_active` | BOOLEAN | Can enable/disable per source |

#### `job_offers`
| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | UUID (PK) | |
| `source_id` | UUID (FK → job_sources) | |
| `source_url` | VARCHAR | Unique — the direct link to the offer |
| `fingerprint` | VARCHAR(64) | SHA-256 hash for dedup, unique + indexed |
| `title` | VARCHAR(300) | Normalized job title |
| `company` | VARCHAR(300) | Company name |
| `location` | VARCHAR(300) | City/Country |
| `description` | TEXT | Full job description |
| `required_skills` | TEXT | Skills (CSV or JSON) |
| `contract_type` | ENUM | `CDI`, `CDD`, `STAGE`, `FREELANCE` |
| `posted_at` | DATETIME | Original pub date |
| `collected_at` | DATETIME | When we scraped it |
| `status` | ENUM | `NEW`, `ANALYZED`, `ARCHIVED` |

#### `job_offer_embeddings`
| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | UUID (PK) | |
| `job_offer_id` | UUID (FK → job_offers, unique) | 1-to-1 relationship |
| `vector` | `Vector(1024)` | pgvector float array |
| `model_name` | VARCHAR | `"intfloat/multilingual-e5-large"` |
| `created_at` | DATETIME | |

#### `collection_runs`
| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | UUID (PK) | |
| `source_id` | UUID (FK → job_sources) | |
| `started_at` | DATETIME | |
| `finished_at` | DATETIME | Nullable |
| `offers_collected` | INT | New unique offers added |
| `status` | ENUM | `SUCCESS`, `FAILED`, `PARTIAL` |
| `error_message` | TEXT | Nullable, error traceback if failed |

---

## 7. API Endpoints Reference

### Auth Routes (`/auth`)
| Method | Path | Description | Auth |
|:-------|:-----|:------------|:-----|
| `POST` | `/auth/register` | Register a new user | Public |
| `POST` | `/auth/login` | Login, get JWT token | Public |
| `GET` | `/auth/me` | Get current user info | 🔒 JWT |

### CV Routes (`/cvs`)
| Method | Path | Description | Auth |
|:-------|:-----|:------------|:-----|
| `POST` | `/cvs/upload` | Upload & parse a CV (PDF) | 🔒 JWT |
| `GET` | `/cvs/` | List all CVs for current user | 🔒 JWT |
| `GET` | `/cvs/{cv_id}` | Get full CV details with experiences | 🔒 JWT |

### Job Sourcing Routes (`/jobs`)
| Method | Path | Description | Auth |
|:-------|:-----|:------------|:-----|
| `POST` | `/jobs/sources` | Create/configure a new job source | 🔒 JWT |
| `GET` | `/jobs/sources` | List all configured job sources | 🔒 JWT |
| `POST` | `/jobs/sources/{id}/collect` | Trigger a collection run (async, returns 202) | 🔒 JWT |
| `GET` | `/jobs/runs` | List history of all collection runs | 🔒 JWT |
| `GET` | `/jobs/offers` | List/filter collected job offers | 🔒 JWT |
| `GET` | `/jobs/offers/{id}` | Get a specific job offer details | 🔒 JWT |

### Health
| Method | Path | Description |
|:-------|:-----|:------------|
| `GET` | `/health` | Liveness check, returns `{"status": "ok"}` |

**Full interactive documentation:** `http://localhost:8000/docs` (Swagger UI)

---

## 8. Job Source Connectors

### Active & Working

| Connector | Source | Method | Status |
|:----------|:-------|:-------|:-------|
| `RemotiveConnector` | remotive.com | Official Public JSON API | ✅ Working |
| `ArbeitnowConnector` | arbeitnow.com | Official Public JSON API | ✅ Working |
| `JobicyConnector` | jobicy.com | Official Public JSON API | ✅ Working |
| `WelcomeToTheJungleAlgoliaConnector` | welcometothejungle.com | Reverse-engineered Algolia search index | ✅ Working |
| `TheMuseConnector` | themuse.com | Official Public JSON API | ✅ Working |
| `BundesagenturConnector` | arbeitsagentur.de | Official German Federal Employment API | ✅ Working |

### Blocked / Inactive

| Connector | Source | Block Reason |
|:----------|:-------|:-------------|
| `TanitJobsScraper` | tanitjobs.com | Cloudflare Turnstile (persistent browser bot detection) |
| `IndeedRSSConnector` | fr.indeed.com | 403 Forbidden (anti-bot measures on RSS feed) |
| `LinkedIn` | linkedin.com | No public API; scraping prohibited by ToS |

### WTTJ Algolia Deep Dive

Welcome to the Jungle's public website uses **Algolia** as its search backend. By intercepting browser XHR requests, we discovered the public search-only credentials embedded in their JavaScript bundle:
- **Endpoint:** `https://csekhvms53-dsn.algolia.net/1/indexes/wk_cms_jobs_production/query`
- **App ID:** `CSEKHVMS53`
- **API Key:** `4bd8f6215d0cc52b26430765769e65a0` *(search-only, read-only)*
- **Required Header:** `Referer: https://www.welcometothejungle.com/`

This allows us to query their entire job index as pure HTTP POST requests — no browser, no JavaScript, and no cookie walls needed.

### Connector Interface

All connectors implement the same `IJobConnector` interface defined in `connectors/base.py`:

```python
class IJobConnector(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """Health check — can we reach the platform?"""
        ...

    @abstractmethod
    def fetch_offers(self, source: JobSource, keywords: str) -> List[JobOfferDTO]:
        """Fetch raw job listings and return as unified DTOs."""
        ...
```

The `JobOfferDTO` data class is the universal intermediary object:

```python
@dataclass
class JobOfferDTO:
    raw_title: str
    raw_company: str
    raw_location: str
    raw_description: str
    raw_url: str
    raw_posted_date: Optional[str]
```

---

## 9. AI & Machine Learning Components

### E5 Embedding Model (`intfloat/multilingual-e5-large`)

The project uses a **locally cached** copy of `intfloat/multilingual-e5-large`, a multilingual sentence transformer trained specifically for semantic search and retrieval tasks.

- **Dimensions:** 1024 floats per vector
- **Supports:** French, Arabic, English, German, and 100+ other languages
- **E5 Prompting Convention:**
  - For **documents** (job offers, CVs to index): prefix with `"passage: "`
  - For **queries** (search terms, CV summaries to query with): prefix with `"query: "`
- **Storage:** The model weights are cached locally inside the Docker container at `/app/model_cache` to avoid re-downloading on every restart.
- **Loading Strategy:** Lazy-loaded singleton — the heavy model is only loaded into RAM on the first API call, then cached in a module-level global variable.

### Groq LLM (Llama-3.3-70b-versatile)

Used in two places:
1. **CV Parsing** — When a user uploads a PDF, the raw extracted text is sent to Groq's API which runs Llama-3.3-70b to extract structured entities (name, email, skills list, experiences with dates, education).
2. **Matching Explanation** — The RAG engine uses Groq to explain *why* a candidate matches a specific job, generating match scores, cover letters, and optimization tips.

### pgvector (Vector Similarity Search)

The PostgreSQL database has the `pgvector` extension enabled (`pgvector/pgvector:pg16` Docker image). Vectors are stored as `Vector(1024)` columns and can be queried using the cosine distance operator:

```sql
SELECT job_offer_id, 1 - (vector <=> query_vector) AS similarity_score
FROM job_offer_embeddings
ORDER BY vector <=> query_vector
LIMIT 10;
```

This enables **sub-second semantic similarity search** over hundreds of thousands of job offers without any external vector database.

---

## 10. Docker & Infrastructure

The entire platform is containerized and orchestrated with Docker Compose.

### Services

```yaml
services:
  db:        # PostgreSQL 16 + pgvector extension (port 5432)
  backend:   # Python/FastAPI API server (port 8000)
  frontend:  # Next.js frontend (port 3000)
```

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium   # Installs Headless Chromium (~300MB)

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

> **Note:** PyTorch is installed from the CPU-only wheel registry to avoid shipping the full CUDA build (~2GB), keeping the image lean.

### Key Docker Details
- **Volume mount:** `./backend:/app` — live code reload without rebuilds during development.
- **`--reload` flag:** Uvicorn watches for file changes and hot-reloads the server.
- **Playwright Chromium:** Installed inside the Docker image for headless browser scraping (currently used for TanitJobs/WTTJ fallback attempts).

---

## 11. Getting Started

### Prerequisites
- Docker Desktop (Windows/Mac/Linux)
- Docker Compose v2+

### 1. Clone the repository
```bash
git clone https://github.com/souibgui00/recruitment-platform.git
cd recruitment-platform
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your credentials (see section 12)
```

### 3. Build and start all services
```bash
docker compose up --build
```
> ⚠️ First build takes ~10-15 minutes due to PyTorch and Playwright Chromium downloads.

### 4. Initialize the database
After containers are running, create all tables:
```bash
docker exec recruitment-platform-backend-1 python create_tables.py
```

### 5. Seed job sources
```bash
docker exec recruitment-platform-backend-1 python -c "
from shared.database import SessionLocal
from job_sourcing.models import JobSource, SourceType

db = SessionLocal()
sources = [
    ('remotive',           SourceType.OFFICIAL_API, 'https://remotive.com/api/remote-jobs'),
    ('arbeitnow',          SourceType.OFFICIAL_API, 'https://www.arbeitnow.com/api/job-board-api'),
    ('jobicy',             SourceType.OFFICIAL_API, 'https://jobicy.com/api/v2/remote-jobs'),
    ('themuse',            SourceType.OFFICIAL_API, 'https://www.themuse.com/api/public/jobs'),
    ('bundesagentur',      SourceType.OFFICIAL_API, 'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs'),
    ('welcometothejungle', SourceType.OFFICIAL_API, 'https://csekhvms53-dsn.algolia.net/1/indexes/wk_cms_jobs_production/query'),
]
for name, stype, url in sources:
    if not db.query(JobSource).filter_by(name=name).first():
        db.add(JobSource(name=name, type=stype, base_url=url, is_active=True))
db.commit()
print('Sources seeded!')
"
```

### 6. Access the platform
| Service | URL |
|:--------|:----|
| **API Swagger UI** | http://localhost:8000/docs |
| **Frontend** | http://localhost:3000 |
| **API Health** | http://localhost:8000/health |

---

## 12. Environment Variables

Create a `.env` file at the root of the repository:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/recruitment_platform

# Security (JWT signing key)
# You can use either SECRET_KEY or JWT_SECRET_KEY - both are supported
SECRET_KEY=your-super-secret-jwt-key-here
# Alternative: JWT_SECRET_KEY=your-super-secret-jwt-key-here

# Groq AI API (for LLM CV parsing and matching evaluation)
GROQ_API_KEY=your_groq_api_key_here
```

> **Get a free Groq API key at:** https://console.groq.com

---

## 13. Progress & Roadmap

### ✅ Completed

- [x] **Infrastructure Setup** — Docker Compose with PostgreSQL (pgvector), FastAPI backend, Next.js frontend.
- [x] **User Management** — Registration, JWT login, protected routes.
- [x] **CV Management** — PDF upload, LLM-powered parsing, entity extraction, semantic E5 embedding, pgvector storage.
- [x] **Job Sourcing Engine** — Full pipeline (fetch → normalize → deduplicate → embed → store).
- [x] **6 Live API Connectors** — Remotive, Arbeitnow, Jobicy, TheMuse, Bundesagentur, WTTJ (Algolia).
- [x] **172+ Real Live Job Offers** stored with 1024-dim semantic embeddings in the database.
- [x] **Asynchronous collection** — FastAPI BackgroundTasks for non-blocking sourcing.
- [x] **Audit Logging** — `collection_runs` table tracking every collection execution.
- [x] **Matching Engine** — Cosine similarity search (`<=>` pgvector), CV ↔ Job recommendations.
- [x] **RAG Explanation** — Groq/Llama-3 powered match analysis, cover letter generation, CV optimization tips.
- [x] **Applications Module** — Candidates apply to jobs, track application status.
- [x] **Notifications Module** — Alerts candidates when new matching offers appear.
- [x] **Frontend UI** — Complete Next.js user interface for all features.
- [x] **Deployment** — Production Docker configuration, environment hardening.

---

## 📝 Notes

- The E5 model (`intfloat/multilingual-e5-large`) is **downloaded once** and cached inside the Docker volume. On first startup, it may take a few minutes to download.
- The database is **persistent** across container restarts via Docker volumes.
- TanitJobs and Indeed scraping are **not functional** due to Cloudflare Turnstile bot protection. This is a known limitation. We compensate with 6 other real-data sources.
- All job sourcing runs are **idempotent** — running the same keyword collection twice will not create duplicates thanks to SHA-256 fingerprinting.

---

<div align="center">

*Plateforme de Recrutement IA — Stage 4ème année, OneTech Business Solutions — 2026*

</div>
