# CapOne Agents - AI-Powered Agricultural and Financial Assistant

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-green)
![Redis](https://img.shields.io/badge/Redis-6.4.0-red)

A sophisticated AI agent system designed to provide comprehensive agricultural and financial assistance to farmers. The system features specialized agents for different domains, Redis-powered conversation management, and a robust REST API.

## 🚀 Features

- **🤖 Multi-Agent Architecture**: Specialized agents for different domains
  - **Conversational Agent**: Main orchestrator for user interactions
  - **Agricultural Agent (AgrifactAgent)**: Weather, soil analysis, crop diseases, policies
  - **Financial Agent**: Loan calculations, EMI, insurance, market analysis
- **💬 Stateless Conversation Management**: Redis-powered multi-user support
- **🛠️ External Tool Integration**: Weather, market data, soil analysis, disease detection
- **📊 Background Processing**: Automatic conversation summarization
- **🔄 Real-time Data**: Live market prices, weather forecasts, disaster alerts
- **🏥 Health Monitoring**: Comprehensive health checks and monitoring
- **🐳 Containerized Deployment**: Docker and Docker Compose support

## 📁 Project Structure

```
CapOneAgent/
├── agents/                     # AI Agent implementations
│   ├── convo_agent.py         # Main conversational orchestrator
│   ├── financial_agent.py     # Financial calculations and advice
│   ├── agrifact_agent.py      # Agricultural information and analysis
│   ├── summary_service.py     # Conversation summarization
│   └── notification_service.py # Notification generation
├── services/                   # Core services
│   ├── redis_conversation_manager.py  # Redis conversation storage
│   └── background_tasks.py    # Background processing tasks
├── utils/                      # Utility functions
│   ├── tool_utils.py          # External tool execution
│   └── base.py                # Base classes and utilities
├── main.py                     # FastAPI application entry point
├── config.py                   # Configuration management
├── pyproject.toml             # Poetry dependencies
├── docker-compose.yml         # Docker Compose configuration
├── dockerfile                 # Docker container definition
└── README.md                  # This file
```

## 🛠️ Installation & Setup

### Prerequisites

- **Python 3.10+**
- **Redis Server** (local or cloud)
- **Poetry** (for dependency management)
- **Google API Key** (for Gemini LLM)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd CapOneAgent
```

### 2. Install Dependencies

Using Poetry (recommended):
```bash
poetry install
```

Using pip:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```bash
# LLM Configuration
GOOGLE_API_KEY=your_google_api_key_here
MODEL_NAME=gemini-2.5-flash
MAX_OUTPUT_TOKENS=1024

# MCP Tool Server
MCP_WEBSOCKET_URL=wss://caponemcp-production.up.railway.app/mcp

# Redis Configuration
REDIS_URL=redis://localhost:6379
# For Railway: REDIS_URL=redis://default:password@host.railway.app:port

# Optional
DEBUG=false
PORT=7000
```

### 4. Redis Setup

#### Option A: Local Redis
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# Windows (using Docker)
docker run -d --name redis -p 6379:6379 redis:latest
```

#### Option B: Railway Cloud Redis (Recommended)
1. Add Redis service to your Railway project
2. Copy the `REDIS_URL` from Railway dashboard
3. Update your `.env` file with the Railway Redis URL

## 🚀 Running the Application

### Development Mode

```bash
# Using Poetry
poetry run python main.py

# Using Python directly
python main.py

# The server will start on http://localhost:7000
```

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 7000 --workers 4
```

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t capone-agent .
docker run -p 7000:7000 --env-file .env capone-agent
```

## 📡 API Endpoints

### Health Check
```bash
GET /health
```

### Chat Interface
```bash
POST /chat
Content-Type: application/json

{
  "query": "What's the weather forecast for my crops?",
  "user_id": "farmer123",
  "conversation_id": "session_001",
  "user_location": "Punjab, India"
}
```

### Conversation Management
```bash
# Get user conversations
GET /conversations/{user_id}

# Delete conversation
DELETE /conversations/{user_id}/{conversation_id}
```

### Summary & Artifacts
```bash
# Generate conversation summary
POST /conversation/summary
{
  "messages": [...],
  "previous_summary": "...",
  "session_id": "session_001"
}

# Extract conversation artifacts
POST /conversation/artefacts
{
  "messages": [...],
  "session_id": "session_001"
}
```

### Notifications
```bash
POST /notification
{
  "user_id": "farmer123",
  "conversation_id": "session_001",
  "artefacts": [...],
  "event_article": "Weather alert text..."
}
```

### Tools
```bash
# List available tools
GET /tools

# Test a specific tool
POST /tools/test
{
  "tool_name": "weather",
  "arguments": {"lat": 28.7041, "lon": 77.1025}
}
```

## 🧪 Testing

### Quick Test (Railway Redis)
```bash
python test_railway_redis.py
```

### Run All Tests
```bash
python run_tests.py
```

### Individual Test Suites
```bash
# Redis unit tests (fast)
python test_redis_unit.py

# Integration tests (requires GOOGLE_API_KEY)
python test_integration.py

# API tests (requires running server)
python main.py  # In one terminal
python test_api.py  # In another terminal

# Comprehensive Redis tests
python test_redis_functionality.py
```

### Selective Testing
```bash
python run_tests.py --unit          # Only unit tests
python run_tests.py --integration   # Only integration tests
python run_tests.py --api          # Only API tests
```

## 🔧 Architecture

### Agent System

The system uses a **multi-agent architecture** with specialized agents:

1. **ConversationalAgent**: Main orchestrator that routes queries to specialized agents
2. **FinancialAgent**: Handles loan calculations, EMI, insurance, market analysis
3. **AgrifactAgent**: Manages weather, soil analysis, crop diseases, policies

### Conversation Management

- **Stateless Design**: Each request is independent
- **Redis Storage**: Last 10 messages + summary per conversation
- **Multi-user Support**: Isolated conversations per user
- **Auto-cleanup**: 24-hour TTL for conversations
- **Background Summarization**: Automatic summary updates

### Tool Integration

The system integrates with external tools via websocket connections:

- **Weather**: Forecasts and disaster alerts
- **Market**: Real-time commodity prices
- **Soil**: Composition analysis using ISRIC SoilGrids
- **Disease**: Plant disease identification
- **Policy**: Government schemes and policies
- **Insurance**: Agricultural insurance information
- **Climate**: Climate data analysis
- **Code Interpreter**: Python code execution
- **Disaster**: Real-time disaster alerts

## 🔄 Deployment

### Railway Deployment

1. **Connect Repository**: Link your GitHub repository to Railway
2. **Add Redis Service**: Add Redis addon to your Railway project
3. **Environment Variables**: Set environment variables in Railway dashboard
4. **Deploy**: Railway will automatically build and deploy

### Docker Deployment

```bash
# Build the image
docker build -t capone-agent .

# Run with environment file
docker run -p 7000:7000 --env-file .env capone-agent

# Or use Docker Compose
docker-compose up --build
```

### Environment Variables for Production

```bash
# Required
GOOGLE_API_KEY=your_api_key
REDIS_URL=your_redis_url

# Optional
MODEL_NAME=gemini-2.5-flash
MAX_OUTPUT_TOKENS=1024
DEBUG=false
PORT=7000
MCP_WEBSOCKET_URL=wss://caponemcp-production.up.railway.app/mcp
```

## 📊 Performance & Monitoring

### Performance Benchmarks

- **Redis Operations**: <5ms average
- **API Response Time**: <500ms for simple queries
- **Memory Usage**: <10MB for 100 conversations
- **Concurrent Users**: 50+ simultaneous conversations

### Monitoring

The system includes comprehensive health checks:

```bash
# Health endpoint provides:
GET /health
{
  "status": "healthy",
  "message": "CapOne Agents service is running",
  "tools_available": 10,
  "version": "1.0.0"
}
```

### Logging

Logs are structured and include:
- Request/response tracking
- Agent execution flow
- Redis operations
- Tool calls and results
- Error handling

## 🛡️ Security

- **User Isolation**: Each user's conversations are completely isolated
- **Data TTL**: Automatic cleanup of conversation data after 24 hours
- **Input Validation**: Comprehensive input validation using Pydantic models
- **Error Handling**: Graceful error handling without exposing sensitive data
- **Non-root Docker**: Docker container runs as non-root user

## 🐛 Troubleshooting

### Common Issues

#### Redis Connection Failed
```
❌ Redis connection failed: [Errno 111] Connection refused
```
**Solution**: Start Redis server or check Redis URL

#### Missing API Key
```
⚠️ GOOGLE_API_KEY not set
```
**Solution**: Add `GOOGLE_API_KEY` to `.env` file

#### Tool Execution Errors
```
❌ Error executing tool: Connection timeout
```
**Solution**: Check MCP server status and network connectivity

### Debug Mode

Enable debug mode for verbose logging:
```bash
DEBUG=true python main.py
```

### Manual Testing

Test Redis directly:
```bash
redis-cli
> ping
PONG
```

Test API endpoints:
```bash
curl -X POST "http://localhost:7000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "user_id": "test"}'
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes and add tests
4. Run the test suite: `python run_tests.py`
5. Commit your changes: `git commit -am 'Add new feature'`
6. Push to the branch: `git push origin feature/new-feature`
7. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review existing issues in the repository
3. Create a new issue with detailed information
4. Include logs and error messages

## 🙏 Acknowledgments

- **LangChain & LangGraph**: For the agent framework
- **FastAPI**: For the high-performance web framework
- **Redis**: For the fast, reliable data storage
- **Google Gemini**: For the powerful language model
- **Railway**: For the deployment platform

---

Made with ❤️ for farmers and agricultural communities
