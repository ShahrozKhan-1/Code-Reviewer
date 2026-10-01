from pydantic import BaseModel, Field
from typing import TypedDict


class RepoPlan(BaseModel):
    reasoning: str = Field(description="Why these files and search terms were chosen")
    files_to_inspect: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)


class RepoState(TypedDict, total=False):
    # inputs
    user_query: str
    repo_path: str

    # planner output
    repo_tree: str
    file_list: list[str]
    plan: dict
    files_to_inspect: list[str]
    search_terms: list[str]

    # explorer output
    exploration_report: str

    # responder output
    answer: str