<div align="center">

```
 ██████╗██╗     ███████╗███████╗████████╗██╗ ██████╗     ███████╗██╗  ██╗██╗███████╗██╗     ██████╗ 
██╔════╝██║     ██╔════╝██╔════╝╚══██╔══╝██║██╔═══██╗    ██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗
██║     ██║     █████╗  ███████╗   ██║   ██║██║   ██║    ███████╗███████║██║█████╗  ██║     ██║  ██║
██║     ██║     ██╔══╝  ╚════██║   ██║   ██║██║▄▄ ██║    ╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║
╚██████╗███████╗███████╗███████║   ██║   ██║╚██████╔╝    ███████║██║  ██║██║███████╗███████╗██████╔╝
 ╚═════╝╚══════╝╚══════╝╚══════╝   ╚═╝   ╚═╝ ╚══▀▀═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝ 
                                                                                                      
                            🛡️  AGENT CORE - AI Security Gateway  🛡️
                          Multi-Layer Defense for LLM Applications
```

[![Version](https://img.shields.io/badge/Version-1.0.0-blue?style=for-the-badge&logo=semver)](/)
[![Python](https://img.shields.io/badge/Python-3.11+-green?style=for-the-badge&logo=python&logoColor=white)](/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](/)
[![Datadog](https://img.shields.io/badge/Datadog-Integrated-632CA6?style=for-the-badge&logo=datadog&logoColor=white)](/)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini_AI-4285F4?style=for-the-badge&logo=google&logoColor=white)](/)

---

### 🎯 **Mission Statement**

**Production-grade, enterprise-ready AI Security Gateway providing comprehensive, multi-layered defense for Large Language Model applications through intelligent microservices that deliver real-time threat detection, input sanitization, output validation, and complete observability.**

---

</div>

## 📋 Table of Contents

- [🏗️ System Architecture](#-system-architecture)
- [📂 Repository Structure](#-repository-structure)
- [🔬 Service Deep Dive](#-service-deep-dive)
  - [1. Gateway Service](#1-gateway-service)
  - [2. Eagle-Eye (IAM)](#2-eagle-eye-iam)
  - [3. Sentinel (Input Security)](#3-sentinel-input-security)
  - [4. Guardian (Output Validation)](#4-guardian-output-validation)
- [🚀 Quick Start](#-quick-start)
- [📊 Observability](#-observability-datadog)

---

## 🏗️ System Architecture

Clestiq Shield protects your LLM applications using a **distributed microservices pattern**. Traffic flows through multiple security layers before reaching the LLM, and the response is validated before returning to the user.

```mermaid
graph TD
    User([User / Client])
    
    subgraph "Google Cloud Platform (Region: us-east1)"
        Gateway[Gateway Service :8000]
        
        subgraph "Observability Hub (Central)"
            DD[Datadog Agent & DaemonSet]
        end

        subgraph "Security Services"
            Sentinel[Sentinel Service :8001]
            Guardian[Guardian Service :8002]
        end
        
        subgraph "Identity & Management"
            EagleEye[Eagle-Eye Service :8003]
        end
        
        Redis[(Redis Cache)]
        DB[(PostgreSQL)]
    end
    
    subgraph "External SaaS"
        Gemini[Google Gemini API]
        DDCloud[Datadog Cloud Platform]
    end
    
    %% Traffic Flow
    User -- HTTPS --> Gateway
    Gateway -- Rate Limits --> Redis
    
    %% Semantic Routing
    Gateway -- "/auth, /apps" --> EagleEye
    EagleEye -- Data --> DB
    
    Gateway -- "/chat" --> Sentinel
    Sentinel -- Threat Check --> Gemini
    Sentinel -- Output Validation --> Guardian
    Guardian -- Hallucination Check --> Gemini
    
    %% Return Path
    Guardian -. Result .-> Sentinel
    Sentinel -. Response .-> Gateway
    Gateway -- Final Response --> User

    %% Observability Connections (The Central Hub)
    Gateway -. Metrics, Logs, Traces .-> DD
    EagleEye -. Metrics, Logs, Traces .-> DD
    Sentinel -. Logs & Traces .-> DD
    Guardian -. Logs & Traces .-> DD
    
    DD == Encrypted Export ==> DDCloud
    
    %% Styles
    style User fill:#f9f,stroke:#000,stroke-width:2px,color:#000
    style Gateway fill:#bfb,stroke:#000,stroke-width:2px,color:#000
    style EagleEye fill:#bfb,stroke:#000,stroke-width:2px,color:#000
    style Sentinel fill:#bfb,stroke:#000,stroke-width:2px,color:#000
    style Guardian fill:#bfb,stroke:#000,stroke-width:2px,color:#000
    style DD fill:#632CA6,stroke:#000,stroke-width:4px,color:#fff
    style Redis fill:#eee,stroke:#000,stroke-width:2px,color:#000
    style Gemini fill:#fbb,stroke:#000,stroke-width:2px,color:#000
    style DDCloud fill:#632CA6,stroke:#000,stroke-width:2px,color:#fff
```

---

## 📂 Repository Structure

The `services/` directory contains the independent microservices:

```bash
services/
├── 🌐 gateway/           # Entry point, Rate Limiting, Orchestration
├── 🔐 eagle-eye/         # Identity (IAM), Users, Apps, API Keys
├── 🎯 security-agent/    # "Sentinel": Input Security, PII, Threat Detection
└── 👁️ guardian/          # "Guardian": Output Validation, Hallucination, Toxicity
```

---

## 🔬 Service Deep Dive

### 1. Gateway Service
**Orchestrator & First Line of Defense**

The Gateway is the single entry point. It handles **Authentication enforcement** (delegating logic to Eagle-Eye) and **Rate Limiting** (using Redis) before routing requests to the security agents.

**Key Features:**
- 🛡️ **Rate Limiting**: Sliding window counters backed by Redis.
- 🔑 **Auth Enforcement**: Validates `X-API-Key` headers.
- 🚦 **Routing**: Directs traffic to Sentinel for inspection.
- 📊 **Telemetry**: Metric aggregation point.

```mermaid
graph LR
    Req[Request] --> Auth{Auth Check?}
    Auth -- Valid --> Limit{Rate Limit?}
    Auth -- Invalid --> 401[401 Unauth]
    
    Limit -- OK --> Sentinel[Route to Sentinel]
    Limit -- Exceeded --> 429[429 Too Many Requests]
    
    style Req fill:#fff,stroke:#000,color:#000
    style 401 fill:#fbb,stroke:#000,color:#000
    style 429 fill:#fbb,stroke:#000,color:#000
    style Sentinel fill:#bfb,stroke:#000,color:#000
```

### 2. Eagle-Eye (IAM)
**Identity & Access Management**

Manages the hierarchical relationship between **Users**, **Applications**, and **API Keys**. Use this service to generate keys for your clients.

**Key Features:**
- 🔐 **Argon2 Hashing**: Secure API key storage.
- 🏢 **Multi-Tenancy**: Users can own multiple Apps; Apps have multiple Keys.
- 🎫 **JWT Auth**: Bearer token authentication for management APIs.

### 3. Sentinel (Input Security)
**The "Security Agent" - Proactive Threat Defense**

Sentinel analyzes incoming prompts *before* they reach the LLM. It focuses on **Input Sanitization** and **Threat Detection**.

**Key Features:**
- 🧹 **Sanitization**: Strips dangerous HTML, optimizes Unicode.
- 🕵️ **PII Redaction**: Detects & masks SSNs, Emails, Phones, Credit Cards.
- 🛡️ **Threat Detection**: Blocks SQL Injection, XSS, Command Injection, and Jailbreak attempts.
- 🎭 **TOON Conversion**: Threat-Obfuscated Object Notation for safe processing.
- ⏭️ **LLM Forwarding**: Intelligent routing to allow or block LLM access based on threat level.

```mermaid
graph TD
    Input --> Sanitize[Sanitization]
    Sanitize --> PII[PII Redaction]
    PII --> Threats[Thread Detection]
    
    Threats -- Attack Detected --> Block[🚫 Block Request]
    Threats -- Safe --> LLM[LLM Processing]
    
    style Block fill:#fbb,stroke:#000,color:#000
    style LLM fill:#bfb,stroke:#000,color:#000
```

### 4. Guardian (Output Validation)
**The "Quality Agent" - Reactive Response Validation**

Guardian analyzes the LLM's response before it is returned to the user. It ensures the AI is helpful, harmless, and honest.

**Key Features:**
- 🤥 **Hallucination Detection**: Cross-references claims with knowledge base.
- ☢️ **Toxicity Check**: Filters hate speech and harmful content.
- 🏛️ **Tone Analysis**: Ensures brand-compliant response style.
- 📚 **Citation Verification**: Validates links and references.
- 🕵️ **PII Leak Detection**: Prevents sensitive data from leaking in LLM responses.
- 🛑 **False Refusal Detection**: Identifies when the LLM incorrectly refuses a safe prompt.
- 📝 **Structured Output**: Enforces valid JSON/TOON output formats.
- ⚠️ **Disclaimer Injection**: Adds necessary warnings or legal disclaimers.

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Google Gemini API Key
- Datadog API Key

### Run Locally

1. **Clone & Configure**
   ```bash
   git clone https://github.com/your-org/ClestiqShield-AgentCore.git
   cd ClestiqShield-AgentCore
   
   # Create .env from .env.example
   cp .env.example .env
   
   # ⚠️ IMPORTANT: Configure Datadog for Full Observability
   # Edit .env and add your Keys
   ```

2. **Start Services**
   ```bash
   docker-compose up --build -d
   ```

3. **Verify**
   ```bash
   curl http://localhost:8000/health
   ```

---

## 📊 Observability (Datadog)

All services are fully instrumented with **Datadog**.

- **APM**: Distributed tracing across all 4 microservices.
- **Metrics**: 
    - `clestiq.gateway.requests`
    - `clestiq.sentinel.threats_detected`
    - `clestiq.guardian.hallucinations`
- **Logs**: Structured JSON logging.

```mermaid
graph LR
    Svcs[Microservices] -- Traces --> DD[Datadog Agent]
    Svcs -- Metrics (DogStatsD) --> DD
    Svcs -- Logs --> DD
    K8s[Kube DaemonSet] -- Infra Stats / Profiling --> DD
    
    style DD fill:#ff9,stroke:#000,stroke-width:2px,color:#000
    style K8s fill:#eee,stroke:#000,color:#000
```
