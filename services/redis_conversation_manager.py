import redis
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class RedisConversationManager:
    def __init__(self):
        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        # Railway Redis URLs are typically: redis://default:password@host:port
        # Handle SSL for cloud Redis if needed
        if "railway.app" in redis_url or redis_url.startswith("rediss://"):
            # Use SSL for Railway Redis
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=True, 
                ssl_cert_reqs=None,  # Disable SSL certificate verification for Railway
                socket_timeout=10,
                socket_connect_timeout=10
            )
        else:
            # Local Redis or non-SSL cloud Redis
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10
            )
        
        # Configuration
        self.message_ttl = 24 * 60 * 60  # 24 hours
        self.max_messages = 10  # Keep last 10 messages
        
        # Test connection
        try:
            self.redis_client.ping()
            logger.info(f"Redis connection established: {redis_url[:20]}...")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise Exception(f"Redis connection failed: {e}")
        
    def _get_conversation_key(self, user_id: str, conversation_id: str, suffix: str) -> str:
        """Generate Redis key for conversation data."""
        return f"conversation:{user_id}:{conversation_id}:{suffix}"
    
    def get_conversation_context(self, user_id: str, conversation_id: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        """
        Get last 10 messages and previous summary for a conversation.
        
        Returns:
            tuple: (messages_list, previous_summary)
        """
        try:
            messages_key = self._get_conversation_key(user_id, conversation_id, "messages")
            summary_key = self._get_conversation_key(user_id, conversation_id, "summary")
            
            # Get messages (Redis LIST - LRANGE gets latest messages)
            messages_data = self.redis_client.lrange(messages_key, -self.max_messages, -1)
            messages = []
            
            for msg_json in messages_data:
                try:
                    messages.append(json.loads(msg_json))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message: {msg_json}")
                    continue
            
            # Get previous summary
            previous_summary = self.redis_client.get(summary_key)
            
            logger.info(f"Retrieved {len(messages)} messages for {user_id}:{conversation_id}")
            return messages, previous_summary
            
        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return [], None
    
    def save_new_messages(self, user_id: str, conversation_id: str, new_messages: List[Dict[str, str]]) -> bool:
        """
        Save new messages to Redis.
        
        Args:
            user_id: User identifier
            conversation_id: Conversation identifier  
            new_messages: List of new messages to save
            
        Returns:
            bool: Success status
        """
        try:
            messages_key = self._get_conversation_key(user_id, conversation_id, "messages")
            lastupdate_key = self._get_conversation_key(user_id, conversation_id, "lastupdate")
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Add new messages to the list
            for message in new_messages:
                pipe.rpush(messages_key, json.dumps(message))
            
            # Trim list to keep only last N messages
            pipe.ltrim(messages_key, -self.max_messages, -1)
            
            # Set expiration
            pipe.expire(messages_key, self.message_ttl)
            
            # Update last update timestamp
            pipe.set(lastupdate_key, datetime.now().isoformat(), ex=self.message_ttl)
            
            # Execute all operations atomically
            pipe.execute()
            
            logger.info(f"Saved {len(new_messages)} messages for {user_id}:{conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save messages: {e}")
            return False
    
    def update_conversation_summary(self, user_id: str, conversation_id: str, summary: str) -> bool:
        """Update conversation summary in Redis."""
        try:
            summary_key = self._get_conversation_key(user_id, conversation_id, "summary")
            self.redis_client.set(summary_key, summary, ex=self.message_ttl)
            logger.info(f"Updated summary for {user_id}:{conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update summary: {e}")
            return False
    
    def get_conversation_summary(self, user_id: str, conversation_id: str) -> Optional[str]:
        """Get conversation summary from Redis."""
        try:
            summary_key = self._get_conversation_key(user_id, conversation_id, "summary")
            return self.redis_client.get(summary_key)
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return None
    
    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete entire conversation from Redis."""
        try:
            keys_to_delete = [
                self._get_conversation_key(user_id, conversation_id, "messages"),
                self._get_conversation_key(user_id, conversation_id, "summary"),
                self._get_conversation_key(user_id, conversation_id, "lastupdate")
            ]
            
            deleted_count = self.redis_client.delete(*keys_to_delete)
            logger.info(f"Deleted {deleted_count} keys for {user_id}:{conversation_id}")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    def get_user_conversations(self, user_id: str) -> List[str]:
        """Get list of conversation IDs for a user."""
        try:
            pattern = f"conversation:{user_id}:*:messages"
            keys = self.redis_client.keys(pattern)
            
            # Extract conversation IDs from keys
            conversation_ids = []
            for key in keys:
                # key format: conversation:user_id:conversation_id:messages
                parts = key.split(':')
                if len(parts) >= 3:
                    conversation_ids.append(parts[2])
            
            return list(set(conversation_ids))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Failed to get user conversations: {e}")
            return []
    
    def cleanup_expired_conversations(self) -> int:
        """Cleanup expired conversations (manual cleanup if needed)."""
        try:
            # This is automatically handled by Redis TTL, but you can implement
            # custom cleanup logic here if needed
            pass
        except Exception as e:
            logger.error(f"Failed to cleanup conversations: {e}")
            return 0
