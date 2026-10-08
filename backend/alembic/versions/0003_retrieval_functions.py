"""Add authenticated vector and full-text chunk search functions.

Revision ID: 0003_retrieval_functions
Revises: 0002_auth_user_rls
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_retrieval_functions"
down_revision: str | None = "0002_auth_user_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.search_chunks_by_embedding(
            query_embedding vector(1536),
            result_limit integer DEFAULT 20,
            filter_ticker text DEFAULT NULL,
            filter_fiscal_year integer DEFAULT NULL
        )
        RETURNS TABLE (
            chunk_id uuid,
            document_id uuid,
            content text,
            section_title text,
            page_start integer,
            page_end integer,
            ticker text,
            company_name text,
            form_type text,
            fiscal_year integer,
            filed_at date,
            source_url text,
            score double precision
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = public
        AS $function$
            SELECT
                c.id AS chunk_id,
                d.id AS document_id,
                c.content,
                c.section_title,
                c.page_start,
                c.page_end,
                d.ticker,
                d.company_name,
                d.form_type,
                d.fiscal_year,
                d.filed_at,
                d.source_url,
                (1 - (c.embedding <=> query_embedding))::double precision AS score
            FROM public.chunks AS c
            JOIN public.documents AS d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
              AND (filter_ticker IS NULL OR d.ticker = upper(filter_ticker))
              AND (filter_fiscal_year IS NULL OR d.fiscal_year = filter_fiscal_year)
            ORDER BY c.embedding <=> query_embedding
            LIMIT LEAST(GREATEST(result_limit, 1), 100)
        $function$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.search_chunks_by_text(
            query_text text,
            result_limit integer DEFAULT 20,
            filter_ticker text DEFAULT NULL,
            filter_fiscal_year integer DEFAULT NULL
        )
        RETURNS TABLE (
            chunk_id uuid,
            document_id uuid,
            content text,
            section_title text,
            page_start integer,
            page_end integer,
            ticker text,
            company_name text,
            form_type text,
            fiscal_year integer,
            filed_at date,
            source_url text,
            score double precision
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = public
        AS $function$
            SELECT
                c.id AS chunk_id,
                d.id AS document_id,
                c.content,
                c.section_title,
                c.page_start,
                c.page_end,
                d.ticker,
                d.company_name,
                d.form_type,
                d.fiscal_year,
                d.filed_at,
                d.source_url,
                ts_rank(
                    c.search_vector,
                    websearch_to_tsquery('english', query_text)
                )::double precision AS score
            FROM public.chunks AS c
            JOIN public.documents AS d ON d.id = c.document_id
            WHERE c.search_vector @@ websearch_to_tsquery('english', query_text)
              AND (filter_ticker IS NULL OR d.ticker = upper(filter_ticker))
              AND (filter_fiscal_year IS NULL OR d.fiscal_year = filter_fiscal_year)
            ORDER BY score DESC, c.id
            LIMIT LEAST(GREATEST(result_limit, 1), 100)
        $function$
        """
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION public.search_chunks_by_embedding(
            vector, integer, text, integer
        ) FROM PUBLIC, anon
        """
    )
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION public.search_chunks_by_embedding(
            vector, integer, text, integer
        ) TO authenticated
        """
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION public.search_chunks_by_text(
            text, integer, text, integer
        ) FROM PUBLIC, anon
        """
    )
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION public.search_chunks_by_text(
            text, integer, text, integer
        ) TO authenticated
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION public.search_chunks_by_embedding(vector, integer, text, integer)"
    )
    op.execute(
        "DROP FUNCTION public.search_chunks_by_text(text, integer, text, integer)"
    )
