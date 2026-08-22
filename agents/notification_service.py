from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

class NotificationService:
    def __init__(self, model_name: str):
        if model_name.startswith("gemini"):
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.0,
                api_key=os.getenv("GOOGLE_API_KEY")
            )
        elif model_name.startswith("gpt"):
            self.llm = ChatOpenAI(
                model=model_name,
                temperature=0.0,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        else:
            raise ValueError(f"Invalid LLM name: {model_name}")

        self.notification_system_prompt = self._build_notification_system_prompt()

    def _build_notification_system_prompt(self) -> str:
        return (
            "You are an assistant that crafts a single concise notification for a user. "
            "You will be given: (1) a set of user artefacts representing needs, states, and context, "
            "and (2) an external event article text. "
            "Your task is to produce a short, actionable notification message (max 2 sentences) that: "
            "- Clearly explains why the event matters to this user given their artefacts\n"
            "- Mentions only the most relevant artefacts\n"
            "- Avoids jargon and is easy to understand\n"
            "- Contains no markdown or code blocks."
        )

    def get_notification(self, artefacts: List[Dict[str, Any]], event_article: str) -> str:
        user_prompt = (
            f"User artefacts: {artefacts}\n\n"
            f"Event article: {event_article}\n\n"
            "Return only the final notification message text."
        )

        messages = [
            {"role": "system", "content": self.notification_system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.llm.invoke(messages)
        return response.content


