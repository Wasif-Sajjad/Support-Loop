# Epic B — Knowledge Base & Retrieval
- B1: Script to clone/scrape Ubuntu/AWS/K8s docs into /data/kb/ as clean Markdown/text.
- B2: Chunking script (semantic or fixed-size w/ overlap) + embedding via MiniLM, loaded into kb_chunks.
- B3: Retriever agent: given intent/category + ticket text, return top-k chunks with similarity scores.