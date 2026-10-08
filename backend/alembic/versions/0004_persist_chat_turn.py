"""Add an atomic, authenticated chat-turn persistence function.

Revision ID: 0004_persist_chat_turn
Revises: 0003_retrieval_functions
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_persist_chat_turn"
down_revision: str | None = "0003_retrieval_functions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.persist_chat_turn(
            p_chat_id uuid,
            p_user_content text,
            p_assistant_content text,
            p_citation_ids uuid[]
        )
        RETURNS TABLE (user_message_id uuid, assistant_message_id uuid)
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public
        AS $function$
        DECLARE
            new_user_message_id uuid;
            new_assistant_message_id uuid;
            citation record;
            citation_text text;
        BEGIN
            UPDATE public.chats
            SET updated_at = now()
            WHERE id = p_chat_id
              AND user_id = (SELECT auth.uid());

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Chat not found' USING ERRCODE = 'P0002';
            END IF;

            INSERT INTO public.messages (chat_id, role, content)
            VALUES (p_chat_id, 'user', p_user_content)
            RETURNING id INTO new_user_message_id;

            INSERT INTO public.messages (chat_id, role, content)
            VALUES (p_chat_id, 'assistant', p_assistant_content)
            RETURNING id INTO new_assistant_message_id;

            FOR citation IN
                SELECT chunk_id, ordinal
                FROM unnest(COALESCE(p_citation_ids, ARRAY[]::uuid[]))
                    WITH ORDINALITY AS cited(chunk_id, ordinal)
            LOOP
                SELECT content INTO citation_text
                FROM public.chunks
                WHERE id = citation.chunk_id;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Citation passage not found'
                        USING ERRCODE = '23503';
                END IF;

                INSERT INTO public.message_citations (
                    message_id,
                    chunk_id,
                    citation_order,
                    cited_text
                )
                VALUES (
                    new_assistant_message_id,
                    citation.chunk_id,
                    citation.ordinal - 1,
                    citation_text
                );
            END LOOP;

            RETURN QUERY
            SELECT new_user_message_id, new_assistant_message_id;
        END
        $function$
        """
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION public.persist_chat_turn(uuid, text, text, uuid[])
        FROM PUBLIC, anon
        """
    )
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION public.persist_chat_turn(uuid, text, text, uuid[])
        TO authenticated
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION public.persist_chat_turn(uuid, text, text, uuid[])")
