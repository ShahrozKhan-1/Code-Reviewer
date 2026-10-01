from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from .config import GEMINI_API_KEY, GEMINI_MODEL
from .schema import RepoState
from .planner import plan_repo
from .explorer import run_explorer
from chat.utils import get_directory_tree, get_file_list
from .system_msg import PLANNER_SYSTEM_PROMPT, RESPONDER_SYSTEM_PROMPT


responder_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=0.3,
    api_key=GEMINI_API_KEY,
)


# ---- planner ----------------------------------------------------------

def planner_node(state: RepoState):
    tree = get_directory_tree(state["repo_path"])
    files = get_file_list(state["repo_path"])

    plan = plan_repo(
        user_query=state["user_query"],
        repo_tree=tree,
        file_list=files,
    )

    return {
        "repo_tree": tree,
        "file_list": files,
        "plan": plan.model_dump(),
        "files_to_inspect": plan.files_to_inspect,
        "search_terms": plan.search_terms,
    }


# ---- explorer (agent) -------------------------------------------------

def explorer_node(state: RepoState):
    report, files_read = run_explorer(
        repo_path=state["repo_path"],
        user_query=state["user_query"],
        plan=state.get("plan", {}),
    )
    return {"exploration_report": report, "files_read": files_read}


# ---- responder --------------------------------------------------------

# graph.py — responder_node
import json

def responder_node(state: RepoState):
    plan = state.get("plan", {}) or {}
    plan_view = {
        "question_type": plan.get("question_type"),
        "success_criteria": plan.get("success_criteria", []),
        "repo_hint": plan.get("repo_hint"),
    }

    human = f"""USER QUESTION:
{state['user_query']}

NAVIGATION PLAN (question_type and success_criteria):
{json.dumps(plan_view, indent=2)}

FINDINGS REPORT:
{state.get('exploration_report', '(no report produced)')}

Answer the user's question now, following your answer shape for this question_type."""

    response = responder_llm.invoke(
        [
            ("system", RESPONDER_SYSTEM_PROMPT),
            ("human", human),
        ]
    )

    content = response.content
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            for item in content
        )

    return {"answer": content}


# ---- graph ------------------------------------------------------------

builder = StateGraph(RepoState)
builder.add_node("planner", planner_node)
builder.add_node("explorer", explorer_node)
builder.add_node("responder", responder_node)

builder.add_edge(START, "planner")
builder.add_edge("planner", "explorer")
builder.add_edge("explorer", "responder")
builder.add_edge("responder", END)

graph = builder.compile()