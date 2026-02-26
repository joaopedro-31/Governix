import anyio
from functools import lru_cache
from app.domains.ai_text2sql.agent import build_agent_app

@lru_cache
def get_agent():
    return build_agent_app()

class AIText2SQLService:
    async def ask(self, question: str) -> dict:
        initial_state = {"question": question, "retry_count": 0}

        agent = get_agent()

        # roda o invoke em thread para não travar o event loop
        result = await anyio.to_thread.run_sync(agent.invoke, initial_state)

        return {
            "answer": result.get("final_answer", ""),
            "debug": {
                "sql_queries": result.get("sql_queries"),
                "error": result.get("error"),
                "retry_count": result.get("retry_count"),
            },
        }
