"""Start the local CareerPilot web interface and API together."""

import argparse
import logging
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--knowledge-dir",
        type=Path,
        help="Optional directory of Markdown knowledge sources",
    )
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65_535:
        parser.error("port must be between 1 and 65535")
    if arguments.knowledge_dir is not None:
        directory = arguments.knowledge_dir.resolve()
        if not directory.is_dir() or not any(directory.glob("*.md")):
            parser.error("knowledge-dir must contain Markdown sources")
        from career_pilot import api

        api.KNOWLEDGE_DIRECTORY = directory
        api.get_rag_service.cache_clear()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(
        "career_pilot.web:create_web_app",
        factory=True,
        host="127.0.0.1",
        port=arguments.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
