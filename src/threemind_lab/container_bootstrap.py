"""One-shot Compose bootstrap. Credentials are environment-only and never printed."""

import os

from .bootstrap import provision


def main():
    provision(
        {
            "host": os.getenv("THREEMIND_PG_HOST", "postgres"),
            "port": 5432,
            "dbname": "postgres",
            "user": "postgres",
            "password": os.environ["THREEMIND_PG_ADMIN_PASSWORD"],
            "connect_timeout": 10,
        },
        app_password=os.environ["THREEMIND_PG_PASSWORD"],
        owner_password=os.environ["THREEMIND_PG_OWNER_PASSWORD"],
    )
    print("Dedicated ThreeMind database and non-owner application role are ready.")


if __name__ == "__main__":
    main()
