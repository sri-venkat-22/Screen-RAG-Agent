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

During ingestion, every supported file directly inside `source_docs/` is treated as a primary RAG source for every role. README files and assignment/spec PDFs are ignored. The Markdown files one level above this directory are fallback corpora so the app still runs when no provided source is present locally.
