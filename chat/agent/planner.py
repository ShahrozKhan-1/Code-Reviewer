from langchain_google_genai import ChatGoogleGenerativeAI

from .config import GEMINI_API_KEY, GEMINI_MODEL
from .schema import  RepoPlan
from .system_msg import PLANNER_SYSTEM_PROMPT


planner_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=0,
    api_key=GEMINI_API_KEY,
)

planner_chain = planner_llm.with_structured_output(RepoPlan)

def plan_repo(
    user_query: str,
    repo_tree: str,
    file_list: list[str],
) -> RepoPlan:
    """
    Ask the planner LLM which files to inspect and what terms to search.

    Args:
        user_query: The user's natural-language question about the repo.
        repo_tree:  A pretty-printed directory tree (from get_directory_tree).
        file_list:  A flat list of repo-relative file paths (from get_file_list).

    Returns:
        RepoPlan with reasoning, files_to_inspect, search_terms, and plan.
    """
    file_list_text = "\n".join(file_list) if file_list else "(empty)"

    human_message = f"""User question:
{user_query}

Repository tree:
{repo_tree}

Flat file list:
{file_list_text}

Return only the JSON object matching the required schema.
Do not answer the user's question. Produce a navigation plan.
"""

    return planner_chain.invoke(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("human", human_message),
        ]
    )