from typing import TypedDict, List

class AgentState(TypedDict, total=False):
    question: str
    sql_queries: List[str]     # lista de SELECTs
    db_result: str             # json/str retornado (você pode trocar por dict/list)
    error: str
    retry_count: int
    final_answer: str
