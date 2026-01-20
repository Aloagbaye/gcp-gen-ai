def make_context_block(items):
    """
    items: list of dicts with fields: chunk_id, doc_id, source, text_preview
    """
    blocks = []
    for it in items:
        blocks.append(
            f"chunk_id={it['chunk_id']} | doc_id={it['doc_id']} | source={it['source']}\n"
            f"{it['text_preview']}\n"
        )
    return "\n---\n".join(blocks)
