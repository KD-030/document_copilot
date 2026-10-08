"""Switch chunk embeddings to Hugging Face BGE small.

Revision ID: 0005_huggingface_embeddings
Revises: 0004_persist_chat_turn
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_huggingface_embeddings"
down_revision: str | None = "0004_persist_chat_turn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_vector_search_function(dimensions: int) -> None:
    op.execute(
        "DROP FUNCTION public.search_chunks_by_embedding(vector, integer, text, integer)"
    )
    op.execute(
        f"""
        CREATE FUNCTION public.search_chunks_by_embedding(
            query_embedding vector({dimensions}),
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


def _require_empty_chunks() -> None:
    op.execute(
        """
        DO $migration$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.chunks) THEN
                RAISE EXCEPTION
                    'Cannot change embedding dimensions while chunks exist; '
                    'rebuild the corpus with the selected embedding model first.';
            END IF;
        END
        $migration$
        """
    )


def upgrade() -> None:
    _require_empty_chunks()
    op.drop_index("ix_chunks_embedding", table_name="chunks")
    _replace_vector_search_function(384)
    op.execute(
        """
        ALTER TABLE public.chunks
        ALTER COLUMN embedding TYPE vector(384)
        USING embedding::vector(384)
        """
    )
    op.create_index(
        "ix_chunks_embedding",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    _require_empty_chunks()
    op.drop_index("ix_chunks_embedding", table_name="chunks")
    _replace_vector_search_function(1536)
    op.execute(
        """
        ALTER TABLE public.chunks
        ALTER COLUMN embedding TYPE vector(1536)
        USING embedding::vector(1536)
        """
    )
    op.create_index(
        "ix_chunks_embedding",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
