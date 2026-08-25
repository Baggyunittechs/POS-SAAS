import os


class Config:
    # TODO: move these into real environment variables before adding real data
    SECRET_KEY = os.environ.get("SECRET_KEY", "secret123")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:3736@localhost:5432/posaas",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Legacy sqlite DB used for user auth (register/login/reset).
    # This still needs migrating into the User table in Postgres —
    # see the pos-system migration plan.

