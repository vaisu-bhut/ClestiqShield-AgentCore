# Clestiq Shield - Agent Core

Production-grade FastAPI proxy service for LLM applications with **multi-layer security** and **distributed microservices**.

## 🛡️ Security Features

### Multi-Layer Defense Architecture

The system implements a **defense-in-depth** strategy with multiple security layers across distributed agents:

```
Request → Auth (Eagle-Eye) → Threat Detection (Sentinel) → LLM → Output Validation (Guardian) → Response
```

#### 1. **Authentication & Management** (Eagle-Eye)
- **API Key Validation**: Secure, hashed API key verification.
- **Application Management**: Multi-app support with distinct configurations.
- **User Management**: Role-based access control.

#### 2. **Input Security Assessment** (Sentinel)
- **Input Sanitization**: Unicode normalization, null byte removal, HTML escaping.
- **PII Redaction**: Auto-redaction of SSNs, emails, phone numbers, etc.
- **Threat Detection**:
    - **SQL Injection**: Pattern matching for common injection vectors.
    - **XSS**: Detection of malicious scripts and event handlers.
    - **Command Injection**: OS command detection.
- **LLM-Based Analysis**: Deep semantic analysis using Gemini Pro.
- **TOON Conversion**: Context-aware input transformation.

#### 3. **Output Validation** (Guardian)
- **Hallucination Detection**: Verifies LLM output against source facts.
- **Tone Analysis**: Ensures brand consistency and appropriate tone.
- **Toxicity Check**: Filters harmful or offensive content.
- **PII Leakage Prevention**: Double-check for sensitive data in responses.

### Configuration

Security features are configurable via environment variables in `docker-compose.yml`:

```bash
# Sentinel Settings
SECURITY_SANITIZATION_ENABLED=true
SECURITY_SQL_INJECTION_DETECTION_ENABLED=true
SECURITY_LLM_CHECK_THRESHOLD=0.85

# Guardian Settings
HARMFUL_CONTENT_THRESHOLD=0.7
INAPPROPRIATE_CONTENT_THRESHOLD=0.6
```

## 🚀 Quick Start

### Development

```bash
# Install dependencies (managed via Poetry in each service)
# Example for Gateway:
cd services/gateway
poetry install

# Run the full distributed system
docker-compose up --build
```

### Testing

Run the comprehensive security test suite in Docker:

**Windows (PowerShell):**
```powershell
.\run-tests.ps1
```

**Linux/Mac:**
```bash
chmod +x run-tests.sh
./run-tests.sh
```

## 🏗️ Architecture

### Distributed Microservices Architecture

Clestiq Shield is a **distributed system** with five specialized services:

```mermaid
graph TB
    Client[Client] -->|HTTP Request| Gateway[Gateway Service :8000]
    
    subgraph "Control Plane"
        Gateway -->|Verify Key| EagleEye[Eagle-Eye Auth :8003]
        EagleEye -->|DB Access| DB[(PostgreSQL :5432)]
    end
    
    subgraph "Security Plane"
        Gateway -->|Analyze Input| Sentinel[Sentinel Input Agent :8001]
        Gateway -->|Validate Output| Guardian[Guardian Output Agent :8002]
        Gateway -->|DB Access| DB
    end
    
    subgraph "Observability"
        Gateway -->|Traces/Logs| OTEL[OTEL Collector :4317]
        Sentinel -->|Traces/Logs| OTEL
        Guardian -->|Traces/Logs| OTEL
        EagleEye -->|Traces/Logs| OTEL
        OTEL -->|Export| Datadog[Datadog]
    end

    style Gateway fill:#4CAF50
    style EagleEye fill:#9C27B0
    style Sentinel fill:#2196F3
    style Guardian fill:#E91E63
    style OTEL fill:#FF9800
    style Datadog fill:#632CA6
```

#### Services

1. **Gateway Service** (`services/gateway/`)
   - **Port**: 8000
   - **Role**: Entry point, Orchestrator
   - **Responsibilities**: Request routing, authentication coordination, response aggregation.

2. **Eagle-Eye Service** (`services/eagle-eye/`)
   - **Port**: 8003
   - **Role**: Identity & Access Management (IAM)
   - **Responsibilities**: API Key generation/validation, User/App management.

3. **Sentinel Service** (`services/security-agent/`)
   - **Port**: 8001
   - **Role**: Input Security Agent
   - **Responsibilities**: Input sanitization, threat detection (SQLi, XSS), PII redaction, TOON conversion.
   - **Tech**: LangGraph, Gemini Pro.

4. **Guardian Service** (`services/guardian/`)
   - **Port**: 8002
   - **Role**: Output Validation Agent
   - **Responsibilities**: Hallucination detection, tone/toxicity checks, output cleanup.
   - **Tech**: LangGraph, Gemini Pro.

5. **OTEL Collector** (`services/otel-collector/`)
   - **Ports**: 4317 (gRPC), 4318 (HTTP)
   - **Role**: Telemetry Aggregator
   - **Responsibilities**: Collects and exports traces, metrics, and logs to Datadog.

### Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant EagleEye
    participant Sentinel
    participant ExternalLLM
    participant Guardian

    Client->>Gateway: POST /api/v1/chat
    
    rect rgb(240, 240, 240)
        Note over Gateway, EagleEye: Authentication
        Gateway->>EagleEye: Validate API Key
        EagleEye-->>Gateway: OK (App Context)
    end
    
    rect rgb(230, 245, 255)
        Note over Gateway, Sentinel: Input Security
        Gateway->>Sentinel: Analyze Input
        Sentinel->>Sentinel: Sanitize -> Detect Threats
        Sentinel-->>Gateway: Verdict (Safe/Blocked)
    end
    
    alt Input Safe
        Gateway->>ExternalLLM: Generate Response (via Provider)
        ExternalLLM-->>Gateway: Raw Response
        
        rect rgb(255, 240, 245)
            Note over Gateway, Guardian: Output Validation
            Gateway->>Guardian: Validate Response
            Guardian->>Guardian: Hallucination Check -> Tone Check
            Guardian-->>Gateway: Validated Response
        end
        
        Gateway-->>Client: 200 OK (Secure Response)
    else Input Blocked
        Gateway-->>Client: 400 Bad Request (Security Alert)
    end
```

## 🔧 Technology Stack

- **Framework**: FastAPI (All services)
- **Language**: Python 3.11+
- **LLM**: Google Vertex AI (Gemini 2.5 Pro / 2.0 Flash)
- **Agent Framework**: LangChain + LangGraph
- **Database**: PostgreSQL (Asyncpg + SQLAlchemy)
- **Observability**: OpenTelemetry + Datadog
- **Security & Util Libraries**: 
  - `bleach` - HTML sanitization
  - `argon2-cffi` - Password hashing
  - `python-jose` - JWT handling
  - `structlog` - Structured logging
  - `email-validator` & `phonenumbers` - PII detection

## 📝 License

MIT License
