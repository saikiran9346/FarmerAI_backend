# FarmerAI Backend - Agentic AI Agricultural & Financial Assistant

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Flash%20LLM-purple)
![Redis](https://img.shields.io/badge/Redis-Upstash%20%2F%20Local-red)

A scalable, state-of-the-art **Multi-Agent Agricultural and Financial AI Platform** built with **LangGraph, FastAPI, Google Gemini, and Redis**. The platform dynamically routes farmer inquiries across specialized domain agents, persists cross-session contextual memory, extracts structured farm profiles (crops, acreage, district, financial loans), and generates real-time personalized agronomic advisories.

---

## 🚀 Key Features

- **🤖 Multi-Agent Orchestration (LangGraph)**:
  - **Conversational Agent**: Core orchestrator routing queries based on dynamic intent classification.
  - **Agricultural Expert Agent (`AgrifactAgent`)**: Weather forecasts, soil analysis, crop pest/disease diagnosis, and government schemes.
  - **Financial Agent (`FinancialAgent`)**: KCC loan calculations, monthly EMI analysis, insurance evaluation, and budgeting via Python Code Interpreter.
- **🌐 Multilingual Support**: Automatic detection and native responses in **Telugu, Hindi, and English**.
- **💬 Stateful & Scalable Memory**: Redis-backed session management maintaining conversation history and auto-extracting user artefacts.
- **🏷️ Structured Artefact Extraction**: Dedicated `SummaryService` & `ArtefactSummaryAgent` that parse unstructured conversations into structured farm profiles.
- **⚡ Event-Driven Notification Agent**: Generates real-time, proactive advisories by correlating farmer artefacts with live weather and market data.
- **🛠️ MCP External Tool Integration**: Real-time tools for weather, soil grids, commodity prices, disease detection, and code execution.
- **🏥 Production-Grade Monitoring**: Comprehensive health checks, structured logging, and automated test suites.
- **🐳 Containerized Deployment**: Ready for Docker, Render, Railway, and cloud setups.

---

## 📁 Project Structure

```
FarmerAI/
├── agents/                     # Specialized Agent implementations
│   ├── convo_agent.py          # LangGraph conversational orchestrator
│   ├── financial_agent.py      # Financial calculations & code interpreter
│   ├── agrifact_agent.py       # Agricultural analysis, weather & soil
│   ├── summary_service.py      # Conversation summarization & artefact extractor
│   └── notification_service.py # Event-driven personalized alerts
├── services/                   # Core business services
│   ├── redis_conversation_manager.py  # Redis session storage & retrieval
│   └── background_tasks.py     # Asynchronous background workers
├── utils/                      # Utilities and tool execution
│   ├── tool_utils.py           # External tool & MCP client integration
│   └── base.py                 # Base agent abstractions
├── main.py                     # FastAPI application entry point
├── config.py                   # Pydantic configuration & settings
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Docker orchestration
└── README.md                   # Backend documentation
```

---

## 🛠️ Installation & Local Setup

### Prerequisites

- **Python 3.10+**
- **Redis Server** (Local instance or Upstash cloud Redis)
- **Google Gemini API Key**

### 1. Clone the Repository

```bash
git clone https://github.com/saikiran9346/FarmerAI_backend.git
cd FarmerAI_backend
```

### 2. Set Up Virtual Environment & Dependencies

```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```env
# Gemini LLM Configuration
GOOGLE_API_KEY=your_google_api_key_here
MODEL_NAME=gemini-2.5-flash
MAX_OUTPUT_TOKENS=1024

# Redis Configuration (Local or Upstash Cloud)
REDIS_URL=rediss://default:your_password@your-endpoint.upstash.io:6379

# MCP Tool Server
MCP_WEBSOCKET_URL=wss://caponemcp-production.up.railway.app/mcp

# Server Configuration
DEBUG=false
PORT=7000
```

### 4. Running the Backend

#### Development Mode:
```bash
python main.py
# Server runs at http://localhost:7000
```

#### Production Mode with Uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 7000 --workers 4
```

#### Docker:
```bash
docker build -t farmerai-backend .
docker run -p 7000:7000 --env-file .env farmerai-backend
```

---

## 📡 API Endpoints

### 1. Health Check
```http
GET /health
```

### 2. Multi-Agent Chat
```http
POST /chat
Content-Type: application/json

{
  "query": "I have 5 acres of cotton in Warangal. What fertilizer should I use and what is the EMI for 2 lakh loan?",
  "user_id": "farmer_101",
  "conversation_id": "conv_1740000000"
}
```

### 3. Conversation & Session Management
```http
# Fetch list of conversations for a user
GET /conversations/{user_id}

# Fetch complete message history for a conversation
GET /conversations/{user_id}/{conversation_id}

# Delete a specific conversation session
DELETE /conversations/{user_id}/{conversation_id}
```

### 4. Artefact Extraction & Summarization
```http
# Generate session summary
POST /conversation/summary

# Extract structured farm profile entities (crops, land, district, loans)
POST /conversation/artefacts
```

### 5. Personalized Smart Advisories
```http
POST /notification
Content-Type: application/json

{
  "user_id": "farmer_101",
  "conversation_id": "conv_1740000000",
  "artefacts": [...],
  "event_article": "Weather alert: heavy unseasonal rainfall expected in Telangana"
}
```

---

## 🧪 Testing Suite

Run the built-in test scripts:

```bash
# Test Redis connection
python test_redis_unit.py

# Test Multi-Agent API integration
python test_api.py

# Run all test suites
python run_tests.py
```

---

## 🏗️ Architecture Flow

```mermaid
flowchart TD
    User([Farmer / Client]) -->|Query + Multilingual Audio/Text| API[FastAPI /chat]
    API --> Memory[Redis Session Manager]
    API --> Orchestrator[ConvoAgent - LangGraph]
    
    Orchestrator -->|Intent: Financial / Loan| FinAgent[Financial Agent + Python Code Interpreter]
    Orchestrator -->|Intent: Farming / Pest / Disease| AgriAgent[Agrifact Agent + MCP Tools]
    Orchestrator -->|Intent: Direct / Greeting| DirectResp[Direct Multi-lingual LLM Response]
    
    FinAgent --> Synthesis[Response Synthesizer]
    AgriAgent --> Synthesis
    DirectResp --> Synthesis
    
    Synthesis --> Memory
    Synthesis --> ArtefactAgent[Artefact & Summary Agent]
    ArtefactAgent -->|Extracted Farm Profile| Upstash[(Upstash Redis DB)]
    Synthesis --> User
```

---

## 📄 License

This project is licensed under the MIT License.
