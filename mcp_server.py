from mcp.server import MCPServer

mcp = MCPServer("Student Assignments")


@mcp.tool()
def get_assignments() -> list[dict[str, object]]:
    """Return sample assignments for the workload planner."""
    return [
        {
            "course": "Algorithms",
            "task": "Study for sorting quiz",
            "due_date": "2026-10-01",
            "estimated_hours": 2,
        },
        {
            "course": "Senior Project",
            "task": "Write interview summary",
            "due_date": "2026-10-04",
            "estimated_hours": 4,
        },
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
