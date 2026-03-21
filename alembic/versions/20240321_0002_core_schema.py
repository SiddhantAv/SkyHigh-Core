"""Core schema: flights, passengers, seats, checkin_sessions + enums.

Revision ID: 0002_core_schema
Revises: 0001_initial
Create Date: 2024-03-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_core_schema"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # create_type=False: we create types explicitly below; otherwise
    # op.create_table() would emit CREATE TYPE again (checkfirst=False there).
    seat_status = postgresql.ENUM(
        "AVAILABLE",
        "HELD",
        "CONFIRMED",
        name="seat_status",
        create_type=False,
    )
    seat_status.create(bind, checkfirst=True)

    checkin_status = postgresql.ENUM(
        "IN_PROGRESS",
        "WAITING_FOR_PAYMENT",
        "COMPLETED",
        name="checkin_status",
        create_type=False,
    )
    checkin_status.create(bind, checkfirst=True)

    payment_status = postgresql.ENUM(
        "PENDING",
        "PAID",
        "FAILED",
        name="payment_status",
        create_type=False,
    )
    payment_status.create(bind, checkfirst=True)

    op.create_table(
        "flights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flight_number", sa.String(length=32), nullable=False),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flights_flight_number", "flights", ["flight_number"], unique=False)

    op.create_table(
        "passengers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "seats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flight_id", sa.Integer(), nullable=False),
        sa.Column("seat_number", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            seat_status,
            nullable=False,
            server_default=sa.text("'AVAILABLE'::seat_status"),
        ),
        sa.Column("held_by", sa.Integer(), nullable=True),
        sa.Column("held_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["flight_id"], ["flights.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["held_by"], ["passengers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flight_id", "seat_number", name="uq_seats_flight_seat_number"),
    )
    op.create_index("ix_seats_flight_id", "seats", ["flight_id"], unique=False)
    op.create_index("ix_seats_held_by", "seats", ["held_by"], unique=False)

    op.create_table(
        "checkin_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("passenger_id", sa.Integer(), nullable=False),
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            checkin_status,
            nullable=False,
            server_default=sa.text("'IN_PROGRESS'::checkin_status"),
        ),
        sa.Column("baggage_weight", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "payment_status",
            payment_status,
            nullable=False,
            server_default=sa.text("'PENDING'::payment_status"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["passenger_id"], ["passengers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seat_id"], ["seats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_checkin_sessions_passenger_id",
        "checkin_sessions",
        ["passenger_id"],
        unique=False,
    )
    op.create_index(
        "ix_checkin_sessions_seat_id",
        "checkin_sessions",
        ["seat_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("checkin_sessions")
    op.drop_table("seats")
    op.drop_table("passengers")
    op.drop_table("flights")

    op.execute(sa.text("DROP TYPE IF EXISTS payment_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS checkin_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS seat_status"))
