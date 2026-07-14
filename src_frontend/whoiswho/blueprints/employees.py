from flask import Blueprint, render_template

from .. import storage
from ..users import get_user, login_required

bp = Blueprint("employees", __name__)


@bp.get("/employees")
@login_required
def employees_page():
    employees = [
        {"name": row.get("name"), "role": row.get("role"), "department": row.get("department")}
        for row in storage.load_table("Employees")
    ]
    return render_template("employees/employees.html", employees=employees, user=get_user())
