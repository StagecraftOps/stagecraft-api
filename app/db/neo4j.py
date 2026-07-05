from neo4j import AsyncGraphDatabase

from app.core.config import settings

async_neo4j_driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
)
