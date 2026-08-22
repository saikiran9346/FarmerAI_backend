import asyncio
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

async def update_conversation_summary_task(
    redis_manager,
    summary_service,
    user_id: str,
    conversation_id: str
):
    """Background task to update conversation summary."""
    try:
        # Get conversation messages
        messages, current_summary = redis_manager.get_conversation_context(user_id, conversation_id)
        
        if len(messages) >= 8:  # Update summary after every 8 messages
            # Generate new summary
            new_summary = summary_service.get_summary(messages, current_summary)
            
            # Save to Redis
            redis_manager.update_conversation_summary(user_id, conversation_id, new_summary)
            logger.info(f"Updated summary for {user_id}:{conversation_id}")
            
    except Exception as e:
        logger.error(f"Failed to update summary: {e}")
