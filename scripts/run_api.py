"""Start the local CareerPilot API with analysis logging enabled."""

import argparse
import logging

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65_535:
        parser.error("port must be between 1 and 65535")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(
        "career_pilot.api:app",
        host="127.0.0.1",
        port=arguments.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
