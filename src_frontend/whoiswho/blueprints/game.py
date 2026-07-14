from flask import Blueprint, redirect, render_template, url_for

from .. import storage
from ..users import get_user, login_required

bp = Blueprint("game", __name__)


def _build_employee_summary(employee):
    name = employee.get("name", "Colleague")
    role = employee.get("role", "Team member")
    department = employee.get("department", "The company")
    return f"{name} is a {role.lower()} in {department.lower()} and loves sharing ideas across the team."


def _employee_initials(name):
    parts = name.split(" ") if name else []
    if not parts:
        return "?"
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][0].upper()


def _build_game_employee(row, index):
    name = row.get("name", "Colleague")
    return {
        "name": name,
        "role": row.get("role"),
        "department": row.get("department"),
        "summary": _build_employee_summary(row),
        "hobbies": row.get("hobbies", []),
        "two_truths": row.get("two_truths"),
        "initials": _employee_initials(name),
        "color_index": index % 6,
    }


@bp.get("/game")
@login_required
def game_page():
    employees = [
        _build_game_employee(row, index)
        for index, row in enumerate(storage.load_table("Employees"))
    ]
    featured_employee = employees[0] if employees else None
    return render_template("game/game.html", employees=employees, featured_employee=featured_employee, user=get_user())


@bp.get("/home/visit/game")
def legacy_game_page():
    return redirect(url_for("game.game_page"))
