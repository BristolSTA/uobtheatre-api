# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot

snapshots = Snapshot()

snapshots["test_productions_snapshot 1"] = {
    "errors": [
        {
            "locations": [{"column": 13, "line": 2}],
            "message": """Syntax Error GraphQL (2:13) Unexpected EOF

1:
2:
               ^
""",
        }
    ]
}
