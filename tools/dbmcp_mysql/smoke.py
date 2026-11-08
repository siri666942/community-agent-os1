"""Read-only protocol smoke test; never creates or changes database records."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from server import validate


async def main():
    invalid = ["DELETE FROM users", "SELECT 1; SELECT 2", "SELECT SLEEP(1)",
               "SELECT body INTO OUTFILE '/tmp/export' FROM messages",
               "SELECT * FROM users FOR UPDATE", "SELECT @x := 1",
               "SELECT unknown_stored_function()"]
    for sql in invalid:
        try:
            validate(sql)
        except ValueError:
            continue
        raise AssertionError("Unexpectedly accepted disallowed SQL")
    params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).with_name("server.py").resolve())])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            names = sorted(t.name for t in (await session.list_tools()).tools)
            assert names == ["describe_schema", "use_sql"]
            result = await session.call_tool("use_sql", {"sql": "SELECT COUNT(*) n FROM users"})
            value = json.loads(result.content[0].text)
            assert value["read_only"] and value["rows"][0]["n"] > 0
            rejected = await session.call_tool("use_sql", {"sql": "DELETE FROM users"})
            assert json.loads(rejected.content[0].text)["error"] == "ValueError"
            print(json.dumps({"protocol": "passed", "tools": names,
                "users": value["rows"][0]["n"], "disallowed_queries_rejected": len(invalid),
                "remote_writes": 0}))


asyncio.run(main())
