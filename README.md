# Saarthi — Proactive Digital Engagement Co-Pilot for YONO SBI

Saarthi is an intelligent, agentic co-pilot integrated into the **YONO SBI** experience. It proactively identifies customer friction events, financial optimization opportunities, and life-stage events, delivering contextual recommendations while adhering to strict regulatory guardrails.

Built for the **YONO Copilot Hackathon**, Saarthi showcases a production-ready design that couples interactive frontend simulation with a multi-agent backend orchestrator compliant with the **Digital Personal Data Protection (DPDP) Act 2023** and **RBI Fair Practices Code (FPC)**.

---

## 🚀 Live Demo & Video Walkthrough

*   **Live Web Prototype:** [https://invexora.github.io/saarthi-yono-copilot/](https://invexora.github.io/saarthi-yono-copilot/)
*   **Video Demo:** The walkthrough screen recording has been saved to your local downloads folder as `yono_emulator_demo.mp4`.

---

## 🛠️ Repository Architecture

The project has been refactored into a modular, clean, and enterprise-grade repository:

```
saarthi-yono-copilot/
├── index.html               # YONO Simulator UI Layout (Mobile Simulator + Agent Trace)
├── style.css                # Extracted visual styles (glassmorphism & dark mode)
├── app.js                   # Interactive client-side simulation, states & routing
├── backend/                 # Agentic Layer (Backend Orchestrator Mockup)
│   ├── requirements.txt     # Python backend dependencies
│   ├── data_synthesis.py   # Synthetic customer profiles & transaction logs
│   ├── vector_ingestion.py  # Ingestion pipeline for RBI & internal policies to Pinecone
│   ├── guardrails.py        # PII regex masking (PAN/Aadhaar/Emails) & compliance checks
│   └── orchestrator.py      # LangGraph DAG state-machine node orchestrator
└── README.md                # Premium architectural description (this file)
```

---

## ⚙️ Core Technical Features

### 1. Agentic Orchestrator (LangGraph State Machine)
The orchestrator manages customer signals through a modular Directed Acyclic Graph (DAG) using a defined `GraphState` context:
*   **Input Guardian Node:** Detects and masks PII (PAN, Aadhaar, Email) to ensure data minimization before sending queries downstream.
*   **Signal Detection Node:** Scans transaction streams for trigger events (e.g. cash deposits, recurring card interest fees, salary credit jumps).
*   **Neo4j Recommender Node:** Queries dynamic eligibility relationships to map customers to tailored solutions (e.g. debt consolidation loans, recurring deposit auto-sweeps).
*   **Compliance Node:** Audits recommendations against RBI guidelines to ensure rate correctness and transparent terms.

### 2. DPDP Act Compliance Gating
Saarthi implements active privacy controls to respect customer data rights under the Indian Digital Personal Data Protection (DPDP) Act:
*   **Right to Erasure (Revoke Consent):** Toggling consent off immediately purges local caches, removes customer logs from the console, and prevents downstream LLM processing.
*   **Right to Data Portability:** Allows customers to download their processed transaction profiling history as a standardized JSON structure.

### 3. Dynamic YONO Emulator
The web interface features a fully functional phone simulator running an interactive YONO UI:
*   **YONO Pay:** Tracks transfers and UPI logs.
*   **Investments:** Displays savings balances and portfolio values.
*   **Cards:** Displays outstanding dues, minimum payments, and interest savings calculations.
*   **Loans & Insurance:** Renders active and pre-approved personal product offers.
*   **Services:** Control center for managing DPDP privacy settings, consent toggles, and data downloads.

---

## 💻 Running the Project Locally

### Running the Web Simulator
To launch the interactive YONO simulator dashboard locally, run a simple web server from the repository root:

```bash
# Start Python's built-in HTTP server
python3 -m http.server 8000
```
Then navigate to [http://localhost:8000](http://localhost:8000) in your web browser.

### Running the Python Backend Scripts
The `/backend` directory contains functional code simulating the agent pipeline.

1.  **Install dependencies:**
    ```bash
    pip install -r backend/requirements.txt
    ```
2.  **Generate Synthetic Customer Transaction Logs:**
    ```bash
    python3 backend/data_synthesis.py
    ```
3.  **Run Vector Document Ingestion (Pinecone Simulation):**
    ```bash
    python3 backend/vector_ingestion.py
    ```
4.  **Run the LangGraph Agent Orchestrator Pipeline:**
    ```bash
    python3 backend/orchestrator.py
    ```

---

## 🔒 Security & Privacy Assertions
*   **PII Masking:** Output logs are scrubbed of structural Aadhaar (12-digit) and PAN (10-character alphanumeric) formats.
*   **Immutable Logs:** System and compliance logs are written in real-time to an unmodifiable local trace console for audit transparency.
