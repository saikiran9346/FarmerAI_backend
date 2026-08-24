"""FastAPI service for CapOne Agents."""

import sys
import io

# Ensure UTF-8 output encoding on Windows for currency symbols (like ₹) and emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import AgentConfig
from agents.convo_agent import ConversationalAgent
from agents.summary_service import ArtefactSummaryService
from agents.notification_service import NotificationService
from services.redis_conversation_manager import RedisConversationManager
from services.background_tasks import update_conversation_summary_task
from utils.tool_utils import tool_executor, tool_executor_sync

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="CapOne Agents API",
    description="AI Agent Service for Agricultural and Financial Assistance",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instances
conversational_agent: Optional[ConversationalAgent] = None
summary_service: Optional[ArtefactSummaryService] = None
notification_service: Optional[NotificationService] = None
redis_manager: Optional[RedisConversationManager] = None


class AgentRequest(BaseModel):
    """Request model for agent service."""
    query: str = Field(..., description="User query/question", min_length=1)
    user_id: Optional[str] = Field(None, description="User's ID")
    conversation_id: Optional[str] = Field(None, description="Conversation identifier")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation continuity")
    user_location: Optional[str] = Field(None, description="User's location (city, state, country)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context information")


class AgentResponse(BaseModel):
    """Response model for agent service."""
    success: bool = Field(..., description="Whether the request was successful")
    response: str = Field(..., description="Agent's response to the query")
    agent_used: Optional[str] = Field(None, description="Which specialized agent was used (financial_agent, agrifact_agent, or direct)")
    session_id: Optional[str] = Field(None, description="Session identifier")
    title: Optional[str] = Field(None, description="Title of the conversation")
    description: Optional[str] = Field(None, description="Description of the conversation")
    error: Optional[str] = Field(None, description="Error message if request failed")


class SummaryRequest(BaseModel):
    """Request model for conversation summary."""
    messages: List[Dict[str, str]] = Field(..., description="List of conversation messages")
    previous_summary: Optional[str] = Field(None, description="Previous summary of the conversation")
    session_id: Optional[str] = Field(None, description="Session identifier")


class SummaryResponse(BaseModel):
    """Response model for conversation summary."""
    success: bool = Field(..., description="Whether the request was successful")
    summary: str = Field(..., description="Generated conversation summary")
    session_id: Optional[str] = Field(None, description="Session identifier")
    error: Optional[str] = Field(None, description="Error message if request failed")


class ArtefactsRequest(BaseModel):
    """Request model for artefacts extraction."""
    messages: List[Dict[str, str]] = Field(..., description="List of conversation messages")
    session_id: Optional[str] = Field(None, description="Session identifier")


class ArtefactsResponse(BaseModel):
    """Response model for artefacts extraction."""
    success: bool = Field(..., description="Whether the request was successful")
    artefacts: List[Dict[str, Any]] = Field(..., description="Extracted artefacts from conversation")
    session_id: Optional[str] = Field(None, description="Session identifier")
    error: Optional[str] = Field(None, description="Error message if request failed")


class NotificationRequest(BaseModel):
    """Request model for notification generation."""
    user_id: str = Field(..., description="User's ID")
    conversation_id: str = Field(..., description="Conversation identifier")
    artefacts: List[Dict[str, Any]] = Field(..., description="Extracted artefacts relevant to the user")
    event_article: str = Field(..., description="External event article or text relevant to the user")
    session_id: Optional[str] = Field(None, description="Session identifier")


class NotificationResponse(BaseModel):
    """Response model for notification generation."""
    success: bool = Field(...)
    notification_message: str = Field(...)
    session_id: Optional[str] = Field(None)
    error: Optional[str] = Field(None)


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    message: str
    tools_available: int
    version: str


@app.on_event("startup")
async def startup_event():
    """Initialize the agent and services on startup."""
    global conversational_agent, summary_service, notification_service, redis_manager
    
    try:
        logger.info("Starting CapOne Agents service...")
        
        # Load configuration
        config = AgentConfig.from_env()
        logger.info(f"Using model: {config.model_name}")
        
        # Fetch available tools
        logger.info("Fetching available tools from MCP server...")
        tool_descriptions = config.get_tools_sync()
        logger.info(f"Loaded {len(tool_descriptions)} tools: {[tool['name'] for tool in tool_descriptions]}")
        
        # Create conversational agent (now stateless)
        conversational_agent = ConversationalAgent(
            model_name=config.model_name,
            tool_descriptions=tool_descriptions,
            tool_executor_func=tool_executor_sync
        )
        
        # Initialize summary service
        summary_service = ArtefactSummaryService(model_name=config.model_name)

        # Initialize notification service
        notification_service = NotificationService(model_name=config.model_name)
        
        # Initialize Redis conversation manager
        redis_manager = RedisConversationManager()
        logger.info("Redis conversation manager initialized")
        
        logger.info("CapOne Agents service started successfully!")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        config = AgentConfig.from_env()
        tools = config.get_tools_sync()
        
        return HealthResponse(
            status="healthy",
            message="CapOne Agents service is running",
            tools_available=len(tools),
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            message=f"Service error: {str(e)}",
            tools_available=0,
            version="1.0.0"
        )


@app.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: AgentRequest):
    """Main chat endpoint for interacting with the conversational agent."""
    global conversational_agent, redis_manager, summary_service
    
    if not conversational_agent or not redis_manager:
        raise HTTPException(
            status_code=503,
            detail="Agent service not initialized. Please check service health."
        )
    
    try:
        user_id = request.user_id or "anonymous"
        conversation_id = request.conversation_id or request.session_id or "default"
        
        logger.info(f"Received query from user {user_id}, conversation {conversation_id}: {request.query}")
        
        # Get conversation context from Redis
        conversation_history, previous_summary = redis_manager.get_conversation_context(user_id, conversation_id)
        
        print(f"Conversation history: {conversation_history}")

        if not conversation_history:
            new_conversation = True
        else:
            new_conversation = False

    
        # Run agent with conversation context
        agent_response, new_messages, title, description = conversational_agent.run_with_context(
            request.query,
            conversation_history,
            previous_summary,
            new_conversation
        )
        
        # Save new messages to Redis
        save_success = redis_manager.save_new_messages(user_id, conversation_id, new_messages)
        
        if not save_success:
            logger.warning(f"Failed to save messages to Redis for {user_id}:{conversation_id}")
        
        # Trigger background summary update if we have enough messages
        if len(conversation_history) + len(new_messages) >= 10:
            asyncio.create_task(
                update_conversation_summary_task(
                    redis_manager, 
                    summary_service, 
                    user_id, 
                    conversation_id
                )
            )
        
        logger.info(f"Agent response: {agent_response}")
        return AgentResponse(
            success=True,
            response=agent_response,
            agent_used="conversational",
            session_id=request.session_id,
            title=title,
            description=description
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return AgentResponse(
            success=False,
            response="I apologize, but I encountered an error processing your request. Please try again.",
            error=str(e),
            session_id=request.session_id
        )


@app.post("/notification", response_model=NotificationResponse)
async def generate_notification(request: NotificationRequest):
    """Generate a concise notification from artefacts and an event article."""
    global notification_service
    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not initialized. Please check service health.")

    try:
        if not isinstance(request.artefacts, list) or not request.event_article:
            raise HTTPException(status_code=400, detail="artefacts (list) and event_article (string) are required")

        notification_message = notification_service.get_notification(request.artefacts, request.event_article)

        return NotificationResponse(
            success=True,
            notification_message=notification_message,
            session_id=request.session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating notification: {e}")
        return NotificationResponse(
            success=False,
            notification_message="",
            error=str(e),
            session_id=request.session_id
        )


@app.post("/conversation/summary", response_model=SummaryResponse)
async def create_summary(request: SummaryRequest):
    """Create a summary of the conversation."""
    global summary_service
    
    if not summary_service:
        raise HTTPException(
            status_code=503,
            detail="Summary service not initialized. Please check service health."
        )
    
    try:
        logger.info(f"Creating summary for {len(request.messages)} messages")
        
        # Validate messages format
        if not request.messages or not isinstance(request.messages, list):
            raise HTTPException(
                status_code=400,
                detail="Messages must be a non-empty list of message objects"
            )
        
        # Generate summary using the ArtefactSummaryService
        summary = summary_service.get_summary(request.messages, request.previous_summary)
        
        logger.info(f"Generated summary: {summary[:100]}...")
        return SummaryResponse(
            success=True,
            summary=summary,
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Error creating summary: {e}")
        return SummaryResponse(
            success=False,
            summary="",
            error=str(e),
            session_id=request.session_id
        )


@app.post("/conversation/artefacts", response_model=ArtefactsResponse)
async def get_artefacts(request: ArtefactsRequest):
    """Extract artefacts from the conversation."""
    global summary_service
    
    if not summary_service:
        raise HTTPException(
            status_code=503,
            detail="Summary service not initialized. Please check service health."
        )
    
    try:
        logger.info(f"Extracting artefacts from {len(request.messages)} messages")
        
        # Validate messages format
        if not request.messages or not isinstance(request.messages, list):
            raise HTTPException(
                status_code=400,
                detail="Messages must be a non-empty list of message objects"
            )
        
        # Extract artefacts using the ArtefactSummaryService
        artefacts_raw = summary_service.get_artefacts(request.messages)
        
        # Parse the JSON response
        try:
            # The service returns a string, so we need to parse it as JSON
            if isinstance(artefacts_raw, str):
                # Clean any markdown formatting that might be present
                clean_content = artefacts_raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                artefacts = json.loads(clean_content)
            else:
                artefacts = artefacts_raw
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse artefacts JSON: {e}")
            logger.error(f"Raw response: {artefacts_raw}")
            # Return empty list if parsing fails
            artefacts = []
        
        logger.info(f"Extracted {len(artefacts)} artefacts")
        return ArtefactsResponse(
            success=True,
            artefacts=artefacts,
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Error extracting artefacts: {e}")
        return ArtefactsResponse(
            success=False,
            artefacts=[],
            error=str(e),
            session_id=request.session_id
        )


@app.get("/tools")
async def list_available_tools():
    """List all available tools."""
    try:
        config = AgentConfig.from_env()
        tools = config.get_tools_sync()
        
        return {
            "success": True,
            "tools": tools,
            "count": len(tools)
        }
    except Exception as e:
        logger.error(f"Error fetching tools: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching tools: {str(e)}")


@app.post("/tools/test")
async def test_tool(tool_name: str, arguments: Dict[str, Any]):
    """Test a specific tool with given arguments."""
    try:
        result = await tool_executor(tool_name, arguments)
        return {
            "success": True,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {e}")
        return {
            "success": False,
            "tool_name": tool_name,
            "arguments": arguments,
            "error": str(e)
        }


# Optional: Add endpoints for conversation management
@app.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation(user_id: str, conversation_id: str):
    """Delete a conversation from Redis."""
    global redis_manager
    
    if not redis_manager:
        raise HTTPException(status_code=503, detail="Redis manager not initialized")
    
    success = redis_manager.delete_conversation(user_id, conversation_id)
    return {"success": success, "message": f"Conversation {'deleted' if success else 'not found'}"}

@app.get("/conversations/{user_id}")
async def get_user_conversations(user_id: str):
    """Get all conversation IDs for a user."""
    global redis_manager
    
    if not redis_manager:
        raise HTTPException(status_code=503, detail="Redis manager not initialized")
    
    conversations = redis_manager.get_user_conversations(user_id)
    return {"user_id": user_id, "conversations": conversations}

@app.get("/conversations/{user_id}/{conversation_id}")
async def get_conversation_history(user_id: str, conversation_id: str):
    """Get messages and summary of a conversation from Redis."""
    global redis_manager
    if not redis_manager:
        raise HTTPException(status_code=503, detail="Redis manager not initialized")
    messages, summary = redis_manager.get_conversation_context(user_id, conversation_id)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "messages": messages,
        "summary": summary
    }

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "message": "CapOne Agents API",
        "version": "1.0.0",
        "description": "AI Agent Service for Agricultural and Financial Assistance (Redis-powered)",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "create_summary": "/conversation/summary",
            "get_artefacts": "/conversation/artefacts",
            "delete_conversation": "/conversations/{user_id}/{conversation_id}",
            "get_user_conversations": "/conversations/{user_id}",
            "tools": "/tools",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    import os
    
    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 7000)),
        reload=True,
        log_level="info"
    )
