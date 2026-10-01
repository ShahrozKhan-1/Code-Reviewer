from .graph import graph


def chat_llm(query: str, repo_path: str) -> dict:
    result = graph.invoke({
        "user_query": query,
        "repo_path": repo_path,
    })
    return {
        "answer": result.get("answer", ""),
        "plan": result.get("plan", {}),
        "files_read": result.get("files_read", []),
    }