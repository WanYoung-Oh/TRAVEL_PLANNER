from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import TravelState
from graph.nodes import node_analyze, node_search, node_plan, node_wait, node_export


def _ok_or_end(next_node: str):
    """state.error가 있으면 END로, 없으면 next_node로 라우팅하는 조건부 엣지 팩토리."""
    def _route(state: TravelState) -> str:
        return END if state.get("error") else next_node
    return _route


def build_graph(checkpointer=None) -> StateGraph:
    builder = StateGraph(TravelState)

    builder.add_node("analyze", node_analyze)
    builder.add_node("search", node_search)
    builder.add_node("plan", node_plan)
    builder.add_node("wait", node_wait)
    builder.add_node("export", node_export)

    builder.set_entry_point("analyze")
    # 각 노드 후 error 발생 시 즉시 END로 종료 (PRD §11 에러 처리 전략)
    builder.add_conditional_edges("analyze", _ok_or_end("search"))
    builder.add_conditional_edges("search", _ok_or_end("plan"))
    builder.add_conditional_edges("plan", _ok_or_end("wait"))
    builder.add_conditional_edges("wait", _ok_or_end("export"))
    builder.add_edge("export", END)

    # interrupt(node_wait)가 동작하려면 반드시 checkpointer 필요
    return builder.compile(checkpointer=checkpointer or MemorySaver())


graph = build_graph()
