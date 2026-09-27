"""Retrieval-augmented generation over the airport knowledge base.

The problem this solves: the bot used to find answers with hand-written loops
that compared substrings (`query in name or name in query`). That breaks on any
rephrasing, and it never worked across languages - users ask in Ukrainian while
the reference files are in English.

RAG replaces the string matching with meaning matching. The pipeline:

    INDEXING (offline, `manage.py reindex_kb`)
    ------------------------------------------
    sources.py    each file and reference table is cut into chunks along its
                  natural boundaries: one department, one airport, one row
        |
    embeddings.py every chunk goes through a neural model that turns text into
                  a 384-number vector. Texts with similar meaning land close
                  together in that space, whatever language they are written in
        |
    indexer.py    vectors are stored in Postgres in a `vector` column (pgvector).
                  A SHA-256 of the chunk text is kept per source, so unchanged
                  sources are skipped on the next run

    ANSWERING (online, per user question)
    -------------------------------------
    retrieval.py  the question is embedded with the same model, then Postgres is
                  asked for the chunks whose vectors sit nearest to it. The
                  nearest ones are handed to the LLM as context, so it answers
                  from retrieved text instead of inventing something
        |
    fallback.py   if nothing is near enough (distance above the threshold), the
                  old exact lookups run instead - an exact department name must
                  never lose to a fuzzy semantic neighbour

The model never touches the files directly. It calls the `search_knowledge_base`
tool, gets passages back, and writes its answer from them.
"""
