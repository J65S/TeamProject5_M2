"""MCP adapter; all retrieval logic also runs offline in workload.py."""
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP
import os
import json
from .workload import load_assignments
from .paths import SYLLABI_FOLDER

mcp = FastMCP('Student Assignments')


@mcp.tool()
def get_assignments(as_of: str | None = None) -> dict:
    """Retrieve syllabus records, retaining overdue work. as_of is an ISO date."""
    snapshot = os.getenv('TASKPILOT_SNAPSHOT')
    if snapshot:
        data = json.loads(snapshot)
        if as_of and as_of != data['today']:
            return {'error': 'Use the date of the current conversation snapshot.'}
        return data
    return load_assignments(os.getenv('WORKLOAD_SYLLABI', str(SYLLABI_FOLDER)), as_of=as_of)


if __name__ == '__main__':
    mcp.run(transport='stdio')
