from __future__ import annotations

from backend.app.services.knowledge import get_knowledge_service


def main() -> None:
    results = get_knowledge_service().ensure_seeded(force=True)
    for role, count in results.items():
        print(f"{role}: indexed {count} chunks")


if __name__ == "__main__":
    main()
