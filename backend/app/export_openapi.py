"""Write the OpenAPI schema without needing Postgres or Redis running.

    python -m app.export_openapi openapi.json

(Writes UTF-8 directly - PowerShell's `>` redirect would write UTF-16 and break the
TypeScript generator.)

The frontend's typed client (frontend/src/api/schema.d.ts) is generated from this
output, and CI regenerates it and fails if the committed client has drifted.
"""

import json
import sys
from pathlib import Path

import fakeredis
from sqlalchemy import create_engine

from app.config import Settings
from app.main import create_app
from app.providers.triage.rules import RuleBasedTriage


def main() -> None:
    app = create_app(
        Settings(triage_provider="rules"),
        engine=create_engine("sqlite://"),
        redis_client=fakeredis.FakeRedis(decode_responses=True),
        triage_provider=RuleBasedTriage(),
    )
    text = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
