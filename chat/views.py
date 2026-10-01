from django.shortcuts import render

from .agent.llm import chat_llm
from .utils import parse_user_message, clone_repo


def index(request):
    reply = ""
    user_message = ""

    if request.method == "POST":
        user_message = request.POST.get("message", "").strip()

        try:
            url, query = parse_user_message(user_message)
        except ValueError as e:
            reply = str(e)
        else:
            try:
                repo_path = clone_repo(repo_url=url)
                result = chat_llm(query=query, repo_path=repo_path)

                reply = result["answer"]
            except Exception as e:
                reply = f"Error: {e}"

    return render(request, "chat.html", {
        "message": user_message,
        "reply": reply,
    })