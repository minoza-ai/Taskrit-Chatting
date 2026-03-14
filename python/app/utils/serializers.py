from typing import Optional, List

def serialize_doc(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc

def serialize_docs(docs: List[dict]) -> List[dict]:
    result = []
    for doc in docs:
        doc.pop("_id", None)
        result.append(doc)
    return result