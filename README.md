# Agentic RAG Financial Planner

The **Agentic RAG Financial Planner** is a multi-agent, enterprise-grade SaaS financial planning platform. It analyses users' equity portfolios through a coordinated team of specialised AI agents and produces narrative reports, interactive charts, retirement projections, and up-to-date market research — all backed by retrieval-augmented generation (RAG) against a curated vector index of financial knowledge (pulled from real-time Polygon AI API).

Access the website here: https://www.darren-agentic-financial-advisor.click/

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture Diagram](#architecture-diagram)
3. [Data Flow Diagram](#data-flow-diagram)
4. [Build and Deployment Sequence Diagram](#build-and-deployment-sequence-diagram)
5. [Build Dependencies Diagram](#build-dependencies-diagram)
6. [Assumptions & Notes](#assumptions--notes)

---

## Tech Stack

### Frontend
- **Next.js 15** (Pages Router, TypeScript)
- **React 18**
- **Tailwind CSS** for styling
- **Recharts** for portfolio / retirement charting
- **Clerk** for authentication (JWT + JWKS verification)
- **CloudFront** CDN + **S3** static hosting

### Backend / Application Layer
- **FastAPI** + **Mangum** adapter running on AWS Lambda (`alex-api`)
- **API Gateway HTTP API (v2)** fronting the FastAPI Lambda
- **API Gateway REST API** (separate, API-key protected) fronting the ingest Lambda
- Agents written against the **OpenAI Agents SDK** (`openai-agents`) with `Runner` / `Agent` / `trace`
- **LiteLLM** (`LitellmModel(model=f"bedrock/{model_id}")`) bridging Agents SDK → Bedrock
- **Python 3.12**, dependency management via **uv**

### AI / ML
- **AWS Bedrock** — **Amazon Nova Pro** (`us.amazon.nova-pro-v1:0` or `eu.amazon.nova-pro-v1:0`) via cross-region inference profiles
- **Amazon SageMaker Serverless Inference** — embedding endpoint `alex-embedding-endpoint` hosting HuggingFace `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **Playwright MCP server** (headless browser) used as a tool by the Researcher agent
- **OpenAI Agents SDK tracing** (requires `OPENAI_API_KEY` for the trace dashboard)

### Agents (5 Lambda + 1 App Runner)
- **Planner** (`alex-planner`) — orchestrator, SQS-triggered
- **Tagger** (`alex-tagger`) — classifies instruments (ETF / stock / sector etc.)
- **Reporter** (`alex-reporter`) — narrative portfolio report (uses context-aware tools)
- **Charter** (`alex-charter`) — structured chart specs for Recharts
- **Retirement** (`alex-retirement`) — Monte-Carlo / projection specialist
- **Researcher** (`alex-researcher`) — long-running, autonomous web researcher on **AWS App Runner** (Docker, linux/amd64), writes vectors back through the ingest API

### Data & Storage
- **Aurora Serverless v2 PostgreSQL** (`alex-aurora-cluster`) with **Data API enabled** (no VPC required)
  - Tables: `users`, `instruments`, `accounts`, `positions`, `jobs`
  - Seeded with 22 ETFs
- **Amazon S3 Vectors** — native vector bucket `alex-vectors-{account_id}`, index `financial-research`, 384 dims, Cosine distance (~90% cheaper than OpenSearch)
- **S3 standard bucket** for raw ingested documents (dual-bucket architecture)
- **S3 bucket** `alex-lambda-packages-{account_id}` for Lambda deployment artefacts > 50 MB
- **AWS Secrets Manager** — Aurora master credentials
- **Polygon.io** API — real-time market prices

### Messaging & Scheduling
- **Amazon SQS** — `alex-analysis-jobs` (main) + DLQ, triggers Planner Lambda
- **Amazon EventBridge Scheduler** — every 2 hours, invokes scheduler Lambda → Researcher *(optional, Guide 4)*

### Infrastructure as Code
- **Terraform** — independent directories per guide (`2_sagemaker`, `3_ingestion`, `4_researcher`, `5_database`, `6_agents`, `7_frontend`, `8_enterprise`), each with **local state** and its own `terraform.tfvars`
- **Docker** — used by `package_docker.py` to build Lambda zips on `linux/amd64` and by the Researcher App Runner image
- **Amazon ECR** — registry for the Researcher image

### Observability & Enterprise (Guide 8)
- **Amazon CloudWatch** — structured JSON logs, dashboards, alarms
- **AWS X-Ray** style tracing via OpenAI Agents SDK traces
- **LangFuse** — agent-level observability (self-host or cloud)
- **Pydantic Logfire** — structured Python logging
- **AWS WAF** — web-ACL on CloudFront / API Gateway *(optional enterprise add-on)*
- **AWS GuardDuty** — account-level threat detection *(optional)*
- **VPC Endpoints** — private Bedrock / Secrets Manager / S3 access *(optional)*
- **tenacity** — retry/back-off around Bedrock and tool calls
- Guardrails: JSON-schema validation of agent outputs, input sanitisation, explainability `rationale` fields, audit log table

### Authentication & Identity
- **Clerk** — user management, JWT issuance, JWKS
- **IAM** — `AlexAccess` group, `aiengineer` IAM user, custom policies `AlexS3VectorsAccess`, `AlexCustomRDSAccess`
- **KMS** — default AWS-managed keys for Secrets Manager, S3, Aurora

### Optional / Guide 9
- **Route 53** — domain registration + hosted zone
- **ACM** — TLS certificate in `us-east-1` for CloudFront
- **Clerk** allowed-origins update for custom domain

---

## Architecture Diagram

High-level runtime architecture. Dashed lines = optional / enterprise add-ons.

```mermaid
graph TB
    subgraph User["User Browser"]
        U[End User]
    end

    subgraph Edge["Edge / CDN"]
        CF[CloudFront Distribution]
        WAF[AWS WAF<br/>optional]
    end

    subgraph Frontend["Frontend Hosting"]
        S3F[S3 Bucket<br/>Next.js static export]
    end

    subgraph Auth["Authentication"]
        CL[Clerk<br/>JWT + JWKS]
    end

    subgraph APIs["API Layer"]
        APIGW2[API Gateway<br/>HTTP API v2<br/>alex-api]
        APIGW1[API Gateway<br/>REST + API Key<br/>ingest]
    end

    subgraph AppLambda["Application Lambda"]
        FASTAPI[FastAPI + Mangum<br/>alex-api Lambda]
    end

    subgraph Queue["Orchestration"]
        SQS[(SQS<br/>alex-analysis-jobs)]
        DLQ[(DLQ)]
    end

    subgraph Agents["Agent Lambdas (OpenAI Agents SDK + LiteLLM)"]
        PL[Planner<br/>alex-planner]
        TG[Tagger<br/>alex-tagger]
        RP[Reporter<br/>alex-reporter]
        CH[Charter<br/>alex-charter]
        RT[Retirement<br/>alex-retirement]
    end

    subgraph Research["Research Service"]
        AR[App Runner<br/>alex-researcher<br/>Docker + Playwright MCP]
        SCHED[EventBridge Scheduler<br/>every 2h - optional]
        SLAM[Scheduler Lambda<br/>optional]
    end

    subgraph Ingest["Ingestion"]
        IL[Ingest Lambda<br/>alex-ingest]
    end

    subgraph Vector["Vector Search"]
        S3V[(S3 Vectors<br/>financial-research index<br/>384-dim Cosine)]
        S3R[(S3 Raw Docs)]
        SM[SageMaker Serverless<br/>all-MiniLM-L6-v2]
    end

    subgraph DB["Relational Data"]
        AUR[(Aurora Serverless v2<br/>PostgreSQL<br/>Data API)]
        SEC[Secrets Manager]
    end

    subgraph LLM["LLM"]
        BR[AWS Bedrock<br/>Nova Pro<br/>cross-region inference]
    end

    subgraph Market["Market Data"]
        POLY[Polygon.io]
    end

    subgraph Obs["Observability - optional"]
        CW[CloudWatch<br/>Logs + Dashboards + Alarms]
        LF[LangFuse]
        LOGF[Pydantic Logfire]
        OAI[OpenAI Agents<br/>Trace Dashboard]
    end

    U -->|HTTPS| CF
    WAF -.protects.-> CF
    CF -->|static| S3F
    CF -->|/api/*| APIGW2
    U -->|Sign in / JWT| CL
    APIGW2 -->|Bearer JWT| FASTAPI
    FASTAPI -->|JWKS verify| CL
    FASTAPI -->|Data API SQL| AUR
    AUR --> SEC
    FASTAPI -->|enqueue job| SQS
    SQS -->|event source| PL
    SQS -.failed.-> DLQ

    PL -->|invoke| TG
    PL -->|invoke| RP
    PL -->|invoke| CH
    PL -->|invoke| RT

    TG --> BR
    RP --> BR
    CH --> BR
    RT --> BR
    PL --> BR

    RP -->|query vectors| S3V
    RP -->|prices| POLY
    RP -->|Data API| AUR
    RT -->|Data API| AUR
    CH -->|Data API| AUR
    TG -->|Data API| AUR
    PL -->|Data API| AUR

    SCHED --> SLAM --> AR
    AR -->|POST docs| APIGW1
    APIGW1 -->|API Key| IL
    IL -->|embed text| SM
    IL -->|upsert vectors| S3V
    IL -->|raw copy| S3R
    AR --> BR

    Agents -.logs.-> CW
    FASTAPI -.logs.-> CW
    IL -.logs.-> CW
    AR -.logs.-> CW
    Agents -.traces.-> OAI
    Agents -.traces.-> LF
    Agents -.metrics.-> LOGF
```

---

## Data Flow Diagram

Three primary flows — (A) user-triggered portfolio analysis, (B) scheduled autonomous research & ingestion, (C) direct document ingest.

```mermaid
flowchart LR
    subgraph A["Flow A: User Analysis"]
        A1[User clicks<br/>Analyze Portfolio] --> A2[Next.js page<br/>with Clerk JWT]
        A2 --> A3[API Gateway v2<br/>+ JWT auth]
        A3 --> A4[FastAPI Lambda]
        A4 --> A5[Insert job row<br/>in Aurora]
        A4 --> A6[Send SQS message<br/>with job_id]
        A6 --> A7[Planner Lambda<br/>triggered]
        A7 --> A8{Plan subtasks}
        A8 --> A9[Tagger<br/>classify holdings]
        A8 --> A10[Reporter<br/>narrative + RAG]
        A8 --> A11[Charter<br/>chart specs]
        A8 --> A12[Retirement<br/>projections]
        A9 --> A13[(Aurora:<br/>update instruments)]
        A10 --> A14[(S3 Vectors<br/>similarity search)]
        A10 --> A15[Polygon.io<br/>live prices]
        A11 --> A13
        A12 --> A13
        A10 --> A16[(Aurora:<br/>write report JSON)]
        A11 --> A16
        A12 --> A16
        A7 --> A17[(Aurora:<br/>mark job complete)]
        A4 -->|poll status| A17
        A4 -->|results| A2
    end

    subgraph B["Flow B: Scheduled Research"]
        B1[EventBridge Scheduler<br/>every 2h] --> B2[Scheduler Lambda]
        B2 --> B3[App Runner<br/>Researcher]
        B3 --> B4[Playwright MCP<br/>browse web]
        B3 --> B5[Bedrock Nova Pro<br/>summarise + extract]
        B3 --> B6[POST to Ingest API<br/>with API Key]
        B6 --> B7[Ingest Lambda]
        B7 --> B8[SageMaker<br/>embed 384-dim]
        B7 --> B9[(S3 Vectors<br/>upsert)]
        B7 --> B10[(S3 Raw Docs<br/>archive)]
    end

    subgraph C["Flow C: Ad-hoc Ingest"]
        C1[External caller<br/>with API Key] --> C2[API Gateway REST]
        C2 --> B7
    end
```

---

## Build and Deployment Sequence Diagram

End-to-end first-time deployment, following Guides 1 → 8 (Guide 9 optional).

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant AWS as AWS Console / CLI
    participant TF as Terraform
    participant Docker as Docker Desktop
    participant ECR as ECR
    participant S3P as S3 (lambda-packages)
    participant Clerk as Clerk Dashboard
    participant Poly as Polygon.io

    Note over Dev,AWS: Guide 1 — Permissions
    Dev->>AWS: Create IAM user `aiengineer` + AlexAccess group
    Dev->>AWS: Attach AlexS3VectorsAccess, AlexCustomRDSAccess policies
    Dev->>AWS: Bedrock console → request Nova Pro access (multi-region)
    Dev->>Dev: aws configure + populate .env
    Dev->>Poly: Create API key → POLYGON_API_KEY

    Note over Dev,TF: Guide 2 — SageMaker
    Dev->>TF: cd terraform/2_sagemaker
    Dev->>TF: cp tfvars.example terraform.tfvars
    TF->>AWS: Deploy alex-embedding-endpoint (Serverless, MiniLM)
    Dev->>AWS: Test embedding via test script

    Note over Dev,TF: Guide 3 — Ingestion
    Dev->>TF: cd terraform/3_ingestion
    TF->>AWS: Create S3 Vectors bucket + `financial-research` index
    TF->>AWS: Create standard S3 docs bucket
    Dev->>Docker: package_docker.py → build ingest.zip
    TF->>AWS: Deploy alex-ingest Lambda + REST API Gateway + API key
    Dev->>AWS: Smoke test via test_ingest.py

    Note over Dev,Clerk: Guide 7 prerequisite — Clerk
    Dev->>Clerk: Create app, copy keys to frontend/.env.local

    Note over Dev,ECR: Guide 4 — Researcher
    Dev->>TF: cd terraform/4_researcher
    TF->>AWS: Create ECR repo + App Runner service skeleton
    Dev->>Docker: docker build --platform linux/amd64
    Docker->>ECR: docker push
    Dev->>TF: terraform apply (wires image URI + env vars)
    Dev->>TF: (optional) deploy scheduler Lambda + EventBridge rule

    Note over Dev,TF: Guide 5 — Database
    Dev->>TF: cd terraform/5_database
    TF->>AWS: Deploy Aurora Serverless v2 + Data API + Secrets Manager
    Dev->>AWS: run_migrations.py → schema + 22 ETF seeds
    Dev->>AWS: verify_database.py

    Note over Dev,S3P: Guide 6 — Agent Orchestra
    Dev->>TF: cd terraform/6_agents
    TF->>AWS: Create alex-lambda-packages S3, SQS + DLQ, IAM roles
    Dev->>Docker: package_docker.py for each of 5 agents
    Dev->>S3P: aws s3 cp *.zip
    Dev->>TF: terraform apply → Lambdas + SQS event source
    Dev->>AWS: deploy_all_lambdas.py (optional refresh)
    Dev->>AWS: test_simple.py (mocks) then test_full.py (live)

    Note over Dev,TF: Guide 7 — Frontend & API
    Dev->>Docker: backend/api/package_docker.py → api_lambda.zip
    Dev->>TF: cd terraform/7_frontend
    TF->>AWS: Deploy API Gateway v2, FastAPI Lambda
    Dev->>Dev: scripts/deploy.py (next build + export + s3 sync + cf invalidate)
    TF->>AWS: CloudFront + S3 static site wired

    Note over Dev,TF: Guide 8 — Enterprise (optional)
    Dev->>TF: cd terraform/8_enterprise
    TF->>AWS: CloudWatch dashboards, alarms, (optional) WAF, GuardDuty, VPC endpoints

    Note over Dev,AWS: Guide 9 — Custom Domain (optional)
    Dev->>AWS: Route 53 register domain + ACM cert in us-east-1
    Dev->>TF: Update CloudFront aliases
    Dev->>Clerk: Add domain to allowed origins
```

---

## Build Dependencies Diagram

Which artefacts/outputs are required before the next component can be deployed. Arrows read "must exist before". Boxes in blue-ish ovals are Terraform directories; rectangles are artefacts; diamonds are external prerequisites.

```mermaid
graph TD
    %% External prereqs
    IAM{{"Guide 1: IAM<br/>aiengineer + AlexAccess"}}
    BEDROCK{{"Bedrock model access<br/>Nova Pro - multi-region"}}
    CLERK{{"Clerk app<br/>publishable + secret keys"}}
    POLY{{"Polygon.io API key"}}
    DOCKER{{"Docker Desktop running"}}

    %% Terraform dirs
    TF2(["terraform/2_sagemaker"])
    TF3(["terraform/3_ingestion"])
    TF4(["terraform/4_researcher"])
    TF5(["terraform/5_database"])
    TF6(["terraform/6_agents"])
    TF7(["terraform/7_frontend"])
    TF8(["terraform/8_enterprise"])

    %% Artefacts / outputs
    SMEP[/"SageMaker endpoint name<br/>alex-embedding-endpoint"/]
    VEC[/"S3 Vectors bucket + index ARN"/]
    INGESTAPI[/"Ingest API URL + API key"/]
    ECRIMG[/"ECR image URI<br/>alex-researcher:latest"/]
    RESURL[/"App Runner URL"/]
    DBARN[/"Aurora cluster ARN +<br/>Secret ARN"/]
    AGENTZIPS[/"5 x agent.zip<br/>built by package_docker.py"/]
    LAMBDAPKG[/"S3: alex-lambda-packages bucket"/]
    SQSARN[/"SQS alex-analysis-jobs ARN"/]
    APIZIP[/"api_lambda.zip"/]
    FEBUNDLE[/"Next.js static export<br/>out/"/]
    CFDIST[/"CloudFront distribution ID"/]

    %% Edges
    IAM --> TF2
    IAM --> TF3
    IAM --> TF4
    IAM --> TF5
    IAM --> TF6
    IAM --> TF7
    IAM --> TF8

    BEDROCK --> TF4
    BEDROCK --> TF6

    TF2 --> SMEP
    SMEP --> TF3
    TF3 --> VEC
    TF3 --> INGESTAPI

    DOCKER --> ECRIMG
    ECRIMG --> TF4
    VEC --> TF4
    INGESTAPI --> TF4
    POLY --> TF4
    TF4 --> RESURL

    TF5 --> DBARN
    DBARN --> TF6
    DBARN --> TF7

    DOCKER --> AGENTZIPS
    AGENTZIPS --> LAMBDAPKG
    LAMBDAPKG --> TF6
    VEC --> TF6
    SMEP --> TF6
    INGESTAPI --> TF6
    POLY --> TF6
    TF6 --> SQSARN

    CLERK --> TF7
    DOCKER --> APIZIP
    APIZIP --> TF7
    SQSARN --> TF7
    TF7 --> CFDIST
    FEBUNDLE --> CFDIST

    CFDIST --> TF8
    DBARN --> TF8
    SQSARN --> TF8
    RESURL --> TF8
```

**How to read it:**
- Each `terraform/X_*` directory has its own local state and `terraform.tfvars`; there is no remote backend.
- Later directories consume **outputs** from earlier directories (typically copied into `.env` and the next `terraform.tfvars`).
- Docker is a cross-cutting prerequisite for every Lambda zip and for the Researcher ECR image.
- Destroying works in reverse: `8 → 7 → 6 → 5 → 4 → 3 → 2` for cleanest teardown (Aurora in Guide 5 is by far the largest cost).

---

## Assumptions & Notes

Stated explicitly so nothing here is inferred silently:

- **Model:** Nova Pro is the default per `CLAUDE.md` and the guides. `agent_architecture.md` mentions "Claude 4 Sonnet" in prose but the code path uses Nova Pro via LiteLLM/Bedrock with a cross-region inference profile.
- **Region env var:** LiteLLM requires `AWS_REGION_NAME` (not `AWS_REGION`); this is set in every agent Lambda.
- **Terraform state:** Local `terraform.tfstate` in each directory. No S3 remote backend is configured.
- **EventBridge scheduler + scheduler Lambda** (Guide 4) are **optional**. The Researcher can also be invoked ad-hoc.
- **Enterprise add-ons** in Guide 8 (WAF, GuardDuty, VPC endpoints, custom guardrails beyond JSON-schema validation) are described as **optional hardening**, not baseline deployment.
- **Custom domain** (Guide 9 — Route 53 + ACM) is **optional**. Without it, the app is served from the CloudFront default domain.
- **OpenAI Agents SDK** requires `OPENAI_API_KEY` only for the hosted **trace viewer**; the LLM itself is Bedrock via LiteLLM.
- **Python:** All commands use `uv` (`uv add`, `uv run`). Never `pip install`, never bare `python script.py` outside a uv project.
- **Docker packaging** (`package_docker.py`) targets `linux/amd64`. On Apple Silicon, BuildKit emulation is used automatically.
- **Dual ingest buckets:** S3 Vectors stores embeddings only; the raw markdown/JSON source doc is archived in a standard S3 bucket for audit and re-embedding.
- **Structured outputs + tool use:** Due to a current LiteLLM + Bedrock limitation, a single agent uses *either* structured outputs *or* tools, never both simultaneously.

If anything above doesn't match the current state of your deployment (for example, you disabled the scheduler, renamed a bucket, or added an extra agent), update the relevant section and regenerate the diagrams.
