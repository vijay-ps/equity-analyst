# 🇮🇳 Personal Agentic AI Indian Equity Analyst

> A production-ready, cloud-deployed RAG-based equity research assistant for NSE/BSE stocks.
> Built on LangGraph + FastAPI + React + PostgreSQL/pgvector + AWS ECS Fargate.

---

## 🚀 Quick Start (Local Dev)

### Prerequisites
- Docker Desktop installed
- Python 3.11+ (for backend dev without Docker)
- Node.js 20+ (for frontend dev)

### 1. Clone & configure

```bash
git clone <repo-url>
cd AgenticInternPractise
cp .env .env.local  # already configured with your keys
```

### 2. Start with Docker Compose

```bash
docker-compose up --build
```

Services start at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **PostgreSQL**: localhost:5432

### 3. Google OAuth Setup (required)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Open **APIs & Services → OAuth consent screen**
3. Under **Credentials → OAuth 2.0 Client IDs**, add:
   - Authorized JS origins: `http://localhost:5173`
   - Authorized redirect URIs: `http://localhost:8000/api/auth/callback`

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CloudFront / ALB                     │
└────────────────┬───────────────────────┬────────────────┘
                 │                       │
        ┌────────▼───────┐     ┌────────▼────────┐
        │  Frontend ECS  │     │  Backend ECS    │
        │  (React/Nginx) │     │  (FastAPI)      │
        │  Port 80       │     │  Port 8000      │
        └────────────────┘     └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │  RDS PostgreSQL │
                               │  + pgvector     │
                               │  (private VPC)  │
                               └─────────────────┘
```

### Data Flow

```
User follows RELIANCE →
  yfinance fetches fundamentals →
    LLM tags sentiment →
      all-MiniLM embeds chunks →
        pgvector stores docs

User chats "What's the sentiment on TCS?" →
  Intent classifier (Groq Llama 3.1 8B) →
    pgvector similarity search →
      Grade relevance →
        Groq Llama 3.3 70B generates cited answer →
          Citations with source URLs returned
```

---

## 🤖 Agent Features

### RAG Pipeline
| Feature | Implementation |
|---|---|
| Embeddings | `all-MiniLM-L6-v2` (384-dim, local, free) |
| Vector Store | PostgreSQL + pgvector (cosine similarity) |
| Chunking | 500-token chunks with 50-token overlap |
| Deduplication | SHA-256 content hash per article |
| Concurrent Safety | PostgreSQL advisory locks per ticker |

### Intent Classification
The agent classifies user messages into:
- **PERSONA_UPDATE** — "I'm a conservative investor" → updates investor profile
- **STOCK_QUERY** — "What's RELIANCE's P/E?" → retrieves + cites answer
- **SENTIMENT_QUERY** — "Any news on TCS?" → retrieves news docs
- **RECOMMENDATION** — "What should I buy?" → algorithmic screening + cites

### Stock Screening (Algorithmic, not LLM)
Stocks are scored on:
- ROE quality (25% weight)
- Dividend yield (20% weight)
- P/E value (20% weight)
- News sentiment (20% weight)
- Debt safety (15% weight)

Hard filters applied from user persona (e.g. D/E < 1x for conservative profiles).

---

## 🗃️ Data Sources

| Source | Data | Method |
|---|---|---|
| Yahoo Finance (yfinance) | Prices, fundamentals, financials | `.NS` ticker suffix |
| Economic Times | Market news | RSS feed |
| Moneycontrol | Top financial news | RSS feed |
| LiveMint | Markets news | RSS feed |
| Business Standard | Markets news | RSS feed |

All monetary values stored and displayed in **INR (Rs.)**.

---

## ☁️ AWS Deployment

### GitHub Secrets Required

```
AWS_ACCESS_KEY_ID       → YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY   → YOUR_AWS_SECRET_ACCESS_KEY

GROQ_API_KEY            → gsk_...
GOOGLE_CLIENT_ID        → 35232388850-...
GOOGLE_CLIENT_SECRET    → GOCSPX-...
JWT_SECRET              → your-random-secret
PRIVATE_SUBNET_ID       → subnet-xxx (from Terraform output)
ECS_SG_ID               → sg-xxx (from Terraform output)
```

### Terraform Setup

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Fill in your values

# Create S3 backend (one-time)
aws s3 mb s3://equity-analyst-tfstate --region ap-south-1
aws dynamodb create-table \
  --table-name equity-analyst-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1

# Deploy infrastructure
terraform init
terraform plan
terraform apply
```

### CI/CD Pipeline

Push to `main` branch triggers:
1. ✅ Python syntax + import tests
2. 🐳 Docker build + push to ECR
3. 🗃️ Alembic DB migrations via ECS task
4. 🚢 Rolling ECS deployment
5. ⏳ Waits for service stability

---

## 📁 Project Structure

```
AgenticInternPractise/
├── backend/                    # FastAPI + LangGraph
│   ├── app/
│   │   ├── main.py             # FastAPI entry, CORS, lifespan
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # Async SQLAlchemy + pgvector
│   │   ├── models.py           # ORM models (User, Stock, Document, etc.)
│   │   ├── auth/               # Google OAuth + JWT
│   │   ├── stocks/             # Follow/unfollow + yfinance
│   │   ├── ingestion/          # fundamentals + RSS news + embedder
│   │   └── agent/              # LangGraph graph + nodes + memory
│   ├── alembic/                # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React + Vite
│   ├── src/
│   │   ├── App.jsx             # Router + auth
│   │   ├── pages/              # Login, Dashboard, Research
│   │   ├── components/         # Layout, StockCard, Citation
│   │   └── lib/                # API client, auth utils
│   ├── Dockerfile
│   └── nginx.conf
├── terraform/                  # IaC for AWS
│   ├── main.tf                 # Provider + S3 backend
│   ├── vpc.tf                  # Network
│   ├── ecr.tf                  # Container registries
│   ├── rds.tf                  # PostgreSQL
│   ├── ecs.tf                  # Fargate services
│   ├── alb.tf                  # Load balancer
│   └── security_groups.tf      # Network ACLs
├── .github/workflows/
│   └── deploy.yml              # CI/CD pipeline
├── docker-compose.yml          # Local development
└── .env                        # Credentials (gitignored in prod)
```

---

## 🔒 Security

- JWT HS256 tokens (7-day expiry)
- Google OAuth for authentication (no passwords)
- RDS in private VPC subnet (no public access)
- ECS tasks in private subnet (NAT for outbound)
- ALB for public traffic termination
- All secrets via GitHub Secrets / env vars (not hardcoded)

---

## 📝 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/auth/login` | GET | Initiate Google OAuth |
| `/api/auth/callback` | GET | OAuth callback |
| `/api/stocks/follow` | POST | Follow a ticker |
| `/api/stocks/unfollow/{ticker}` | DELETE | Unfollow |
| `/api/stocks/followed` | GET | Get watchlist |
| `/api/stocks/search/{q}` | GET | Search tickers |
| `/api/chat/send` | POST | Send message to agent |
| `/api/chat/history/{id}` | GET | Get thread history |
| `/api/chat/threads` | GET | List all threads |

Full OpenAPI docs at: `http://localhost:8000/api/docs`
