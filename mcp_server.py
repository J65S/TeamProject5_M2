from datetime import date
from pathlib import Path

from mcp.server import MCPServer


mcp = MCPServer("Student Assignments")

# Find the syllabi folder next to this Python file.
SYLLABI_FOLDER = Path(__file__).with_name("syllabi")


@mcp.tool()
def get_assignments() -> dict:
    """
    Read syllabus files and return assignments due today or later.

    Assumption: assignments with due dates before today have been
    completed. This prototype does not check actual submission status.
    """

    if not SYLLABI_FOLDER.exists():
        return {
            "error": (
                "The syllabi folder was not found. Create a folder named "
                "'syllabi' next to mcp_server.py and add the syllabus files."
            )
        }

    syllabus_files = sorted(SYLLABI_FOLDER.glob("*.txt"))

    if not syllabus_files:
        return {
            "error": "No .txt syllabus files were found in the syllabi folder."
        }

    today = date.today()
    upcoming_assignments = []
    skipped_past_assignments = 0
    warnings = []

    for syllabus_file in syllabus_files:
        course = syllabus_file.stem
        current_assignment = {}

        def add_assignment(assignment):
            """Validate and add one assignment from the syllabus."""
            nonlocal skipped_past_assignments

            if not assignment:
                return

            required = ("task", "due_date", "estimated_hours")
            missing = [
                field for field in required
                if field not in assignment
            ]

            if missing:
                warnings.append(
                    f"{syllabus_file.name}: assignment is missing "
                    f"{', '.join(missing)}."
                )
                return

            try:
                due = date.fromisoformat(assignment["due_date"])
                hours = float(assignment["estimated_hours"])

                if hours <= 0:
                    raise ValueError("estimated hours must be greater than zero")

            except ValueError:
                warnings.append(
                    f"{syllabus_file.name}: invalid date or estimated hours "
                    f"for '{assignment['task']}'."
                )
                return

            if due < today:
                skipped_past_assignments += 1
                return

            upcoming_assignments.append({
                "course": course,
                "task": assignment["task"],
                "due_date": due.isoformat(),
                "estimated_hours": hours,
                "source_file": syllabus_file.name,
            })

        for line in syllabus_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()

            if line.startswith("COURSE:"):
                course = line.split(":", 1)[1].strip()

            elif line.startswith("Task:"):
                # Save the previous task before starting a new one.
                add_assignment(current_assignment)
                current_assignment = {
                    "task": line.split(":", 1)[1].strip()
                }

            elif line.startswith("Due:") and current_assignment:
                current_assignment["due_date"] = line.split(":", 1)[1].strip()

            elif line.startswith("Estimated hours:") and current_assignment:
                current_assignment["estimated_hours"] = (
                    line.split(":", 1)[1].strip()
                )

        # Save the final task in the file.
        add_assignment(current_assignment)

    upcoming_assignments.sort(key=lambda assignment: assignment["due_date"])

    return {
        "today": today.isoformat(),
        "assumption": (
            "Assignments due before today are assumed completed. "
            "Actual submission status is not checked."
        ),
        "past_assignments_skipped": skipped_past_assignments,
        "upcoming_assignments": upcoming_assignments,
        "warnings": warnings,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")