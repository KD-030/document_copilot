import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.assistant.outputs import GroundedAnswer
from app.auth.dependencies import AuthenticatedUser
from app.chat import service
from app.retrieval.models import SourcePassage


class FakeInferenceClient:
    def __init__(self, **kwargs):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


class FakeStreamResult:
    def __init__(self, answer):
        self.answer = answer

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def stream_output(self, *, debounce_by):
        yield SimpleNamespace(answer="Grounded")
        yield SimpleNamespace(answer="Grounded answer.")

    async def get_output(self):
        return self.answer


class FakeAgent:
    def __init__(self, result):
        self.result = result

    def run_stream(self, prompt):
        assert "Question:\nCompare revenue." in prompt
        return self.result


def source_passage() -> SourcePassage:
    return SourcePassage(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("00000000-0000-0000-0000-000000000010"),
        content="Revenue grew.",
        section_title="Business",
        page_start=None,
        page_end=None,
        ticker="AAPL",
        company_name="Apple Inc.",
        form_type="10-K",
        fiscal_year=2025,
        filed_at=date(2025, 10, 31),
        source_url="https://www.sec.gov/filing",
    )


def test_stream_chat_turn_persists_after_grounding_and_emits_citations(monkeypatch):
    passage = source_passage()
    chat_id = UUID("00000000-0000-0000-0000-000000000020")
    user_message_id = UUID("00000000-0000-0000-0000-000000000021")
    assistant_message_id = UUID("00000000-0000-0000-0000-000000000022")
    client = FakeInferenceClient()
    persisted = []

    async def retrieve_passages(*args, **kwargs):
        return [passage]

    async def persist_chat_turn(*args):
        persisted.append(args)
        return user_message_id, assistant_message_id

    answer = GroundedAnswer(
        answer="Grounded answer.",
        citation_ids=[passage.chunk_id],
    )
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: client)
    monkeypatch.setattr(service, "retrieve_passages", retrieve_passages)
    monkeypatch.setattr(service, "persist_chat_turn", persist_chat_turn)
    monkeypatch.setattr(service, "agent", FakeAgent(FakeStreamResult(answer)))

    async def collect_events():
        user = AuthenticatedUser(
            id=UUID(int=1), email="analyst@gmail.com", supabase=None
        )
        return [
            event
            async for event in service.stream_chat_turn(
                user, chat_id, "Compare revenue."
            )
        ]

    events = asyncio.run(collect_events())

    assert [event["type"] for event in events] == ["delta", "delta", "complete"]
    assert [event["text"] for event in events[:2]] == ["Grounded", " answer."]
    assert events[-1]["turn"]["assistant_message_id"] == str(assistant_message_id)
    assert events[-1]["turn"]["citations"][0]["chunk_id"] == str(passage.chunk_id)
    assert persisted[0][1:] == (
        chat_id,
        "Compare revenue.",
        "Grounded answer.",
        [passage.chunk_id],
    )
    assert client.closed
