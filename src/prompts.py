from typing import List


def build_messages(query_text: str, top_k: int, mode: str) -> List[dict]:
    if mode == "NO_WEB":
        system_message = (
            "Do not browse the web. Use only your internal knowledge. "
            "Only include datasets that match the query. Do not invent links; if unsure, omit the item."
        )
    else:
        system_message = (
            "Use web search to find relevant datasets. "
            "Only include landing pages or DOIs. Do not invent links. "
            "Do not call time, date, timestamp, or clock tools."
        )

    user_message = (
        f"Query: {query_text}\n"
        f"Return up to {top_k} items. "
        "Respond ONLY as JSON in this exact shape: "
        '{"items":[{"title":"...","url_or_doi":"...","justification":"..."}]}. '
        "Put any DOI, URL, landing page, or link in url_or_doi."
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


def format_messages(messages: List[dict]) -> str:
    return "\n\n".join(
        f"{str(message.get('role', '')).upper()}: {message.get('content', '')}"
        for message in messages
    )


__all__ = ["build_messages", "format_messages"]
