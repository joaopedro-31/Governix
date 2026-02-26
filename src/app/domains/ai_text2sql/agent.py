import json
from typing import Any
from langchain_community.utilities import SQLDatabase
from langgraph.graph import StateGraph, END

from app.db.readonly import build_readonly_engine
from app.domains.ai_text2sql.state import AgentState
from app.domains.ai_text2sql.prompt_loader import load_prompt
from app.domains.ai_text2sql.llm import build_llm
from app.domains.ai_text2sql.sql_guard import validate_queries
from app.core.config import settings

def _extract_json(content: str) -> dict[str, Any] | None:
    c = content.strip()
    # remove cercas ```json ... ```
    if c.startswith("```"):
        c = c.split("\n", 1)[1]
        c = c.rsplit("```", 1)[0].strip()
    try:
        return json.loads(c)
    except Exception:
        return None

def build_agent_app():
    engine = build_readonly_engine()
    db = SQLDatabase(engine)
    llm = build_llm()

    SYSTEM_SQL_PROMPT = load_prompt("system_sql.md")
    SYSTEM_ANSWER_PROMPT = load_prompt("system_answer.md")

    def generate_sql(state: AgentState):
        table_info = db.get_table_info()

        prompt = (
            SYSTEM_SQL_PROMPT
            .replace("{table_info}", table_info)
            .replace("{error}", state.get("error", "Nenhum"))
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Pergunta do usuário: {state['question']}"}
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Preferência: JSON {"queries":[...]}
        data = _extract_json(content)
        if data and isinstance(data.get("queries"), list):
            queries = [str(q).strip() for q in data["queries"] if str(q).strip()]
        else:
            # fallback: tenta extrair bloco ```sql ... ```
            if "```sql" in content:
                raw = content.split("```sql")[1].split("```")[0].strip()
            else:
                raw = content

            # se vierem várias queries em linhas, tenta split simples (sem ';' permitido)
            queries = [raw.strip()]

        return {
            "sql_queries": queries,
            "retry_count": state.get("retry_count", 0) + 1
        }

    def guard_sql(state: AgentState):
        try:
            safe = validate_queries(state["sql_queries"])
            return {"sql_queries": safe, "error": ""}
        except Exception as e:
            return {"error": str(e), "db_result": "[]"}

    def execute_sql(state: AgentState):
        try:
            results = []
            for q in state["sql_queries"]:
                results.append(db.run(q))
            return {"db_result": json.dumps(results, ensure_ascii=False), "error": ""}
        except Exception as e:
            return {"error": str(e), "db_result": "[]"}

    def generate_answer(state: AgentState):
        prompt = SYSTEM_ANSWER_PROMPT.format(
            question=state["question"],
            result=state.get("db_result", "[]")
        )
        response = llm.invoke(prompt)
        return {"final_answer": response.content}

    def should_continue(state: AgentState):
        if state.get("error") and state.get("retry_count", 0) < settings.AI_MAX_RETRIES:
            return "generate_sql"
        return "generate_answer"

    workflow = StateGraph(AgentState)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("guard_sql", guard_sql)
    workflow.add_node("execute_sql", execute_sql)
    workflow.add_node("generate_answer", generate_answer)

    workflow.set_entry_point("generate_sql")
    workflow.add_edge("generate_sql", "guard_sql")
    workflow.add_edge("guard_sql", "execute_sql")
    workflow.add_conditional_edges("execute_sql", should_continue)
    workflow.add_edge("generate_answer", END)

    return workflow.compile()
