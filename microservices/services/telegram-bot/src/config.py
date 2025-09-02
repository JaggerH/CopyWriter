"""
Telegram Bot Configuration
"""
import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TelegramConfig(BaseModel):
    """Telegram Bot Configuration"""
    token: str
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_port: int = 8443


class OrchestratorConfig(BaseModel):
    """Orchestrator Service Configuration"""
    base_url: str = "http://orchestrator-service:8000"
    timeout: int = 30


class Config(BaseModel):
    """Main Configuration"""
    telegram: TelegramConfig
    orchestrator: OrchestratorConfig
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables"""
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        return cls(
            telegram=TelegramConfig(
                token=telegram_token,
                webhook_enabled=os.getenv("TELEGRAM_WEBHOOK_ENABLED", "false").lower() == "true",
                webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL", ""),
                webhook_port=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443"))
            ),
            orchestrator=OrchestratorConfig(
                base_url=os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8000"),
                timeout=int(os.getenv("ORCHESTRATOR_TIMEOUT", "30"))
            )
        )