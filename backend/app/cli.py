"""Maintenance commands against authoritative workspace chunks."""

import argparse
import asyncio
from uuid import UUID

from app.db.models import Workspace
from app.db.session import Session
from app.services.vector_store import ensure_index, workspace_lock


async def rebuild(workspace_id):
    async with Session() as db:
        if await db.get(Workspace, workspace_id) is None:
            raise ValueError("Workspace does not exist")
        async with workspace_lock(workspace_id):
            index, _ = await ensure_index(db, workspace_id, force=True)
        print(f"Rebuilt {index.ntotal} source passages")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["rebuild-index"])
    parser.add_argument("workspace", type=UUID)
    args = parser.parse_args()
    asyncio.run(rebuild(str(args.workspace)))


if __name__ == "__main__":
    main()
