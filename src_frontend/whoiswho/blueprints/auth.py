from flask import Blueprint, flash, redirect, request, session, url_for

from .. import auth as auth_provider

bp = Blueprint("auth", __name__)


@bp.get("/login")
@bp.post("/login")
def login():
    provider = auth_provider.get_provider()
    if request.method == "POST":
        return provider.login_post(request)
    return provider.login_get()


@bp.get("/auth/callback")
def callback():
    return auth_provider.get_provider().callback(request)


@bp.get("/logout")
def logout():
    provider = auth_provider.get_provider()
    redirect_url = provider.logout_redirect_url()
    session.clear()
    if redirect_url:
        return redirect(redirect_url)
    flash("You have been logged out", "info")
    return redirect(url_for("auth.login"))
