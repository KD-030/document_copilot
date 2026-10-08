"""Link application users to Supabase Auth and enable row-level security.

Revision ID: 0002_auth_user_rls
Revises: 0001_initial
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_auth_user_rls"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_users_id_auth_users",
        "users",
        "users",
        ["id"],
        ["id"],
        source_schema="public",
        referent_schema="auth",
        ondelete="CASCADE",
    )

    for table in (
        "users",
        "chats",
        "messages",
        "message_citations",
        "documents",
        "chunks",
    ):
        op.execute(sa.text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))

    op.execute(
        """
        CREATE POLICY users_select_own
        ON public.users FOR SELECT TO authenticated
        USING (id = (SELECT auth.uid()))
        """
    )
    for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        using_clause = (
            " USING (user_id = (SELECT auth.uid()))" if action != "INSERT" else ""
        )
        check_clause = (
            " WITH CHECK (user_id = (SELECT auth.uid()))"
            if action in {"INSERT", "UPDATE"}
            else ""
        )
        op.execute(
            sa.text(
                f"""
                CREATE POLICY chats_{action.lower()}_own
                ON public.chats FOR {action} TO authenticated{using_clause}{check_clause}
                """
            )
        )

    for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        using_clause = (
            """
            USING (
                EXISTS (
                    SELECT 1
                    FROM public.chats
                    WHERE chats.id = messages.chat_id
                      AND chats.user_id = (SELECT auth.uid())
                )
            )
            """
            if action != "INSERT"
            else ""
        )
        check_clause = (
            """
            WITH CHECK (
                EXISTS (
                    SELECT 1
                    FROM public.chats
                    WHERE chats.id = messages.chat_id
                      AND chats.user_id = (SELECT auth.uid())
                )
            )
            """
            if action in {"INSERT", "UPDATE"}
            else ""
        )
        op.execute(
            sa.text(
                f"""
                CREATE POLICY messages_{action.lower()}_own
                ON public.messages FOR {action} TO authenticated
                {using_clause}
                {check_clause}
                """
            )
        )

    for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        using_clause = (
            """
            USING (
                EXISTS (
                    SELECT 1
                    FROM public.messages
                    JOIN public.chats ON chats.id = messages.chat_id
                    WHERE messages.id = message_citations.message_id
                      AND chats.user_id = (SELECT auth.uid())
                )
            )
            """
            if action != "INSERT"
            else ""
        )
        check_clause = (
            """
            WITH CHECK (
                EXISTS (
                    SELECT 1
                    FROM public.messages
                    JOIN public.chats ON chats.id = messages.chat_id
                    WHERE messages.id = message_citations.message_id
                      AND chats.user_id = (SELECT auth.uid())
                )
            )
            """
            if action in {"INSERT", "UPDATE"}
            else ""
        )
        op.execute(
            sa.text(
                f"""
                CREATE POLICY message_citations_{action.lower()}_own
                ON public.message_citations FOR {action} TO authenticated
                {using_clause}
                {check_clause}
                """
            )
        )

    op.execute(
        """
        CREATE POLICY documents_select_authenticated
        ON public.documents FOR SELECT TO authenticated
        USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY chunks_select_authenticated
        ON public.chunks FOR SELECT TO authenticated
        USING (true)
        """
    )


def downgrade() -> None:
    for table, policies in (
        ("users", ("users_select_own",)),
        (
            "chats",
            tuple(
                f"chats_{action}_own"
                for action in ("select", "insert", "update", "delete")
            ),
        ),
        (
            "messages",
            tuple(
                f"messages_{action}_own"
                for action in ("select", "insert", "update", "delete")
            ),
        ),
        (
            "message_citations",
            tuple(
                f"message_citations_{action}_own"
                for action in ("select", "insert", "update", "delete")
            ),
        ),
        ("documents", ("documents_select_authenticated",)),
        ("chunks", ("chunks_select_authenticated",)),
    ):
        for policy in policies:
            op.execute(sa.text(f"DROP POLICY {policy} ON public.{table}"))
        op.execute(sa.text(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY"))

    op.drop_constraint(
        "fk_users_id_auth_users",
        "users",
        type_="foreignkey",
        schema="public",
    )
