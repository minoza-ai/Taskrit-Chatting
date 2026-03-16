from typing import List, Optional


def serialize_doc(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None

    result = dict(doc)
    result.pop("_id", None)
    return result


def serialize_docs(docs: List[dict]) -> List[dict]:
    result = []

    for doc in docs:
        item = dict(doc)
        item.pop("_id", None)
        result.append(item)

    return result