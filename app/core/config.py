from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "dev-insecure-secret-change-me"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://stagecraft:password@postgres:5432/stagecraft"
    REDIS_URL: str = "redis://redis:6379/0"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:3000/api/auth/callback"

    GITHUB_APP_SLUG: str = ""

    AWS_REGION: str = "us-east-1"
    SQS_QUEUE_URL: str = "https://sqs.us-east-1.amazonaws.com/123456789/stagecraft-webhooks"
    BEDROCK_MODEL_ID: str = "anthropic.claude-sonnet-4-6"

    BEDROCK_CHAT_MODEL_ID: str = "anthropic.claude-sonnet-4-6"

    BEDROCK_CROSS_ACCOUNT_ROLE_ARN: str = ""

    BEDROCK_API_KEY: str = ""

    ENVIRONMENT: str = "development"

    SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    TOKEN_ENCRYPTION_KEY: str = ""

    FRONTEND_URL: str = "http://localhost:3000"

    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    COOKIE_SECURE: bool = False

    GITHUB_APP_ID: str = ""
    GITHUB_APP_PRIVATE_KEY: str = ""

    INTERNAL_API_KEY: str = ""

    WORKER_INTERNAL_URL: str = "http://stagecraft-worker.stagecraft.svc.cluster.local:8080"

    BEDROCK_KB_ID: str = ""

    BEDROCK_GUARDRAIL_ID: str = ""
    BEDROCK_GUARDRAIL_VERSION: str = ""

    GRAPH_BACKEND: str = "postgres"
    NEO4J_URI: str = "bolt://stagecraft-neo4j.stagecraft.svc.cluster.local:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"prod", "production"}

    @property
    def cookie_secure(self) -> bool:
        return self.COOKIE_SECURE or self.is_production

settings = Settings()
