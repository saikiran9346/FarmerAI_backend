from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from typing import List, Optional, Dict, Any, Callable
from pydantic import BaseModel
import json
import os
import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ArtefactSummaryService:
    def __init__(self, model_name: str):
        if model_name.startswith("gemini"):
            self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0, api_key=os.getenv("GOOGLE_API_KEY"))
        elif model_name.startswith("gpt"):
            self.llm = ChatOpenAI(model=model_name, temperature=0.0, api_key=os.getenv("OPENAI_API_KEY"))
        else:
            raise ValueError(f"Invalid LLM name: {model_name}")
        
        self.summary_system_prompt = self._build_summary_system_prompt()

        self.artefact_system_prompt = self._build_artefact_system_prompt()

    def _build_summary_system_prompt(self) -> str:
        return """
        You are an AI assistant designed to summarize conversations. You will be provided with a conversation thread, which includes an "assistant message" and a "user message list." Your task is to generate a concise and comprehensive summary that captures the core essence of the conversation.
Key Requirements for the Summary:
Essence Preservation: Accurately reflect the main topic, purpose, and overall flow of the discussion.
Important Entities: Identify and include all critical entities such as names of individuals, organizations, products, locations, dates, specific terms, or any other named items that are central to understanding the conversation.
Key Discussions: Highlight significant points of discussion, decisions made, problems identified, solutions proposed, action items, or any other crucial topics that were elaborated upon or agreed/disagreed upon during the exchange.
If the previous summary is provided, it should be updated to reflect the new conversation.
Conciseness and Clarity: The summary should be as brief as possible without omitting essential information, and it should be clear and easy to understand.

Example:
Assistant Message: "Hello! How can I help you today?"
User Message List:
- "I'm having trouble with my internet connection. It keeps dropping every few minutes."
- "I've tried restarting my router, but it didn't help."
- "My name is John Doe, and my account number is 12345."
Assistant Message: "Thank you, John. Let me check your account. Can you confirm your address?"
User Message List:
- "Sure, it's 123 Main Street, Anytown."
Assistant Message: "Okay, I see an outage reported in your area. Our technicians are working on it, estimated resolution by 5 PM today."
User Message List:
- "Ah, that explains it. Will I get a notification when it's fixed?"
Assistant Message: "Yes, we will send an SMS to your registered mobile number once service is restored."

Output Example:
"This conversation between John Doe (account 12345, address 123 Main Street, Anytown) and the assistant concerns John's intermittent internet connection. John reported trying to restart his router without success. The assistant identified an outage in John's area with an estimated resolution time of 5 PM today and confirmed an SMS notification will be sent upon service restoration."
        """

    def _build_artefact_system_prompt(self) -> str:
        return """You are an AI assistant designed to extract critical "artefacts" from user conversation threads. Your goal is to identify and structure key pieces of information, facts, entities, and user states that are valuable for building a "memory layer" about the user. This memory layer will be used to enable personalized notifications, alerts, or warnings in future interactions.
        Task:
        For each provided conversation thread (which may contain both user and assistant messages, though you'll primarily extract from user messages and relevant context), extract all pertinent "artefacts."
        Definition of an "Artefact":
        An artefact is a discrete, factual, and actionable piece of information or a defined state related to the user, their context, their needs, or their environment. These are the details you would store in a database to inform future, proactive engagements with the user.
        Key Requirements for Artefact Extraction:
        Identify Critical Information: Focus on details that indicate:
        User States/Conditions: (e.g., "crop wilting", "internet dropping", "having trouble with X")
        User Needs/Goals: (e.g., "cheapest way to irrigate", "resolve internet connection")
        User Attributes/Identifiers: (e.g., "John Doe", "account number 12345", "KCC loan holder")
        Contextual Information relevant to the user: (e.g., "no rain for X days", "district declared drought-affected", "outage in area")
        Relevant External Events/Announcements: (e.g., "new relief scheme announced", "government declaration")
        Key Dates/Deadlines: (e.g., "application deadline: August 20th", "estimated resolution by 5 PM")
        User Actions/Attempts: (e.g., "tried restarting router")
        Granularity: Each artefact should be specific and represent a single, distinct piece of information.
        Actionability: Consider if the extracted information could directly trigger a personalized alert, suggest a relevant resource, or modify future assistant behavior.
        Source Attribution: Note where the information originated from (a specific user message, an assistant message providing context, or inferred from previous conversations/external data).
        Structured Output: Present the extracted artefacts in a machine-readable format, such as a JSON array of objects.
        Output Format:
        Generate a JSON array, where each object represents an extracted artefact. Each artefact object should ideally contain the following fields:
        artefact_name: A concise, descriptive name for the artefact (e.g., "User_Crop_Condition", "Weather_Forecast_Rain_Days", "User_Has_KCC_Loan", "District_Drought_Status").
        value: The specific data extracted (e.g., "Wilting", "0", "True", "Declared Drought-Affected", "2025-08-20").
        type: A category for the artefact (e.g., "user_state", "user_need", "user_attribute", "environmental_condition", "program_information", "deadline", "location_status").
        source: Indicates where the information was primarily found (e.g., "User Message", "Assistant Message", "Inferred/External Context").
        description (optional): Any additional context or parameters relevant to the artefact (e.g., for "Weather_Forecast_Rain_Days", period: "15 days").
        Example Input Scenario:

--- Conversation Thread ---
User: "The forecast shows no rain for the next 15 days, and my crop is wilting. What is the cheapest way to do life-saving irrigation?"
Assistant: "Their district was recently declared a drought-affected area by the government. A new government relief scheme was announced yesterday, offering interest subvention and partial loan repayment waiver for drought-hit farmers with KCC loans. The farmer has an active Kisan Credit Card (KCC) loan. Last date to apply: 20th August."
Expected Output for the Example Scenario:

    [
  {{
    "artefact_name": "User_Crop_Condition",
    "value": "Wilting",
    "type": "user_state",
    "source": "User Message"
  }},
  {{
    "artefact_name": "Weather_Forecast_Rain_Days",
    "value": "0",
    "type": "environmental_condition",
    "source": "User Message",
    "description": "Period: 15 days"
  }},
  {{
    "artefact_name": "User_Need_Irrigation_Method",
    "value": "Cheapest life-saving irrigation",
    "type": "user_need",
    "source": "User Message"
  }},
  {{
    "artefact_name": "User_Has_KCC_Loan",
    "value": "True",
    "type": "user_attribute",
    "source": "Inferred/External Context"
  }},
  {{
    "artefact_name": "District_Drought_Status",
    "value": "Declared Drought-Affected",
    "type": "location_status",
    "source": "Inferred/External Context"
  }},
  {{
    "artefact_name": "Government_Relief_Scheme",
    "value": "Drought Relief Scheme",
    "type": "program_information",
    "source": "Inferred/External Context",
    "description": "A new government relief scheme was announced yesterday, offering interest subvention and partial loan repayment waiver for drought-hit farmers with KCC loans."
  }},
  {{
    "artefact_name": "New_Govt_Relief_Scheme_Application_Deadline",
    "value": "2025-08-20",
    "type": "deadline",
    "source": "Inferred/External Context"
  }}
]
"""

    def get_summary(self, messages: List[Dict[str, str]], previous_summary: Optional[str] = None) -> str:
        user_prompt = f"This is the conversation thread: {messages}"
        if previous_summary:
            user_prompt += f"\n\nThis is the previous summary of the conversation: {previous_summary}"

        msgs = [
            {"role": "system", "content": self.summary_system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = self.llm.invoke(msgs)
        return response.content

    def get_artefacts(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        user_prompt = f"This is the conversation thread: {messages}"

        msgs = [
            {"role": "system", "content": self.artefact_system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = self.llm.invoke(msgs)
        return response.content
    

