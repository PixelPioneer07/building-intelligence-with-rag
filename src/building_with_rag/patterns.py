from building_with_rag.contracts import QueryRequest, QueryResult


def run_pattern(request: QueryRequest) -> QueryResult:
    """Single entry point for /v1/query and the chat adapter. Placeholder for every mode."""
    return QueryResult(
        pattern=request.pattern,
        status="not_implemented",
        message=f"The '{request.pattern}' pattern is not implemented yet.",
    )
