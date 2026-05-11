# Primary Source Documents

Place all provided textbook or corpus files directly in this directory before running ingestion.

Expected layout:

```text
source_docs/
  book-1.pdf
  book-2.pdf
  notes.txt
```

Supported file types are `.pdf`, `.txt`, `.md`, and `.markdown`.

During ingestion, supported files directly inside `source_docs/` are mapped into role-specific vector collections. The AI/ML role uses the core provided ML books, and the Data / Applied ML role uses the applied ML books. Other roles use the Markdown fallback corpora one level above this directory unless matching primary sources are added in code.

README files and assignment/spec PDFs are ignored so the RAG pipeline only embeds knowledge material.
