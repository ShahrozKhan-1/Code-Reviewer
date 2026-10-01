import json
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from .config import GEMINI_API_KEY, GEMINI_MODEL
from .system_msg import EXPLORER_SYSTEM_PROMPT
from .tools import explorer_toolkit, set_repo, reset_repo, get_read_files


explorer_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=0,
    api_key=GEMINI_API_KEY,
)


explorer_agent = create_agent(
    model=explorer_llm,
    tools=explorer_toolkit,
    system_prompt=EXPLORER_SYSTEM_PROMPT,
)


def _flatten(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            for item in content
        )
    return str(content)


def run_explorer(repo_path: str, user_query: str, plan: dict) -> tuple[str, list[str]]:
    """Run the explorer agent. Returns (report, files_read)."""
    tokens = set_repo(repo_path)
    try:
        plan_json = json.dumps(plan, indent=2)
        files = plan.get("files_to_inspect") or []
        budget = plan.get("tool_budget", 8)

        user_msg = f"""USER QUESTION:
{user_query}

NAVIGATION PLAN (JSON):
{plan_json}

Starting files: {files}
Tool budget: {budget} calls. Write the final report when you reach it."""

        # Hard cap the agent loop so it can't blow past the planner budget
        recursion_limit = max(10, budget * 3)

        result = explorer_agent.invoke(
            {"messages": [{"role": "user", "content": user_msg}]},
            config={"recursion_limit": recursion_limit},
        )

        report = _flatten(result["messages"][-1].content)
        return report, get_read_files()
    finally:
        reset_repo(tokens)