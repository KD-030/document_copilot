import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ApiError, api } from '@/lib/api'
import { supabase } from '@/lib/supabase'

type Chat = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

type Citation = {
  chunk_id: string
  citation_order: number
  excerpt: string
  ticker: string
  company_name: string
  form_type: string
  fiscal_year: number
  filed_at: string | null
  section_title: string | null
  page_start: number | null
  page_end: number | null
  source_url: string
}

type Message = {
  id: string
  chat_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  citations: Citation[]
  isDraft?: boolean
}

type ChatTurn = {
  chat_id: string
  user_message_id: string
  assistant_message_id: string
  user_content: string
  assistant_content: string
  citations: Citation[]
}

type ChatStreamEvent =
  | { type: 'delta'; text: string }
  | { type: 'replace'; text: string }
  | { type: 'complete'; turn: ChatTurn }

const filingDateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeZone: 'UTC',
})

function displayError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

function titleForQuestion(question: string): string {
  const title = question.trim().replace(/\s+/g, ' ')
  return title.length > 52 ? `${title.slice(0, 49)}…` : title
}

function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null

  return (
    <div className="mt-3 space-y-2">
      {citations.map((citation) => (
        <details
          className="rounded-lg border bg-background text-sm"
          key={citation.chunk_id}
        >
          <summary className="cursor-pointer list-none px-3 py-2 font-medium">
            {citation.ticker} — {citation.company_name} · {citation.form_type} · FY{' '}
            {citation.fiscal_year}
            {citation.filed_at
              ? ` · Filed ${filingDateFormat.format(new Date(citation.filed_at))}`
              : ''}
            {citation.section_title ? ` · ${citation.section_title}` : ''}
            {citation.page_start
              ? ` · p. ${citation.page_start}${citation.page_end && citation.page_end !== citation.page_start ? `–${citation.page_end}` : ''}`
              : ''}
          </summary>
          <div className="space-y-3 border-t px-3 py-3">
            <p className="whitespace-pre-wrap text-muted-foreground">
              {citation.excerpt}
            </p>
            <a
              className="inline-flex text-primary underline underline-offset-4"
              href={citation.source_url}
              rel="noreferrer"
              target="_blank"
            >
              Open SEC filing
            </a>
          </div>
        </details>
      ))}
    </div>
  )
}

export function ChatPage() {
  const { chatId } = useParams()
  const navigate = useNavigate()
  const [chats, setChats] = useState<Chat[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [pendingMessages, setPendingMessages] = useState<Message[]>([])
  const [pendingChatId, setPendingChatId] = useState<string | null>(null)
  const [messagesChatId, setMessagesChatId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const loadChats = useCallback(async () => {
    const result = await api.get<Chat[]>('/chats')
    setChats(result ?? [])
  }, [])

  useEffect(() => {
    let isMounted = true
    void (async () => {
      try {
        const result = await api.get<Chat[]>('/chats')
        if (isMounted) setChats(result ?? [])
      } catch (loadError) {
        if (isMounted) setError(displayError(loadError))
      } finally {
        if (isMounted) setIsLoading(false)
      }
    })()
    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    if (!chatId) {
      return () => {
        isMounted = false
      }
    }

    void api
      .get<Message[]>(`/chats/${chatId}/messages`)
      .then((result) => {
        if (isMounted) {
          setMessages(result ?? [])
          setMessagesChatId(chatId)
        }
      })
      .catch((loadError: unknown) => {
        if (isMounted) {
          setError(displayError(loadError))
          setMessagesChatId(chatId)
        }
      })

    return () => {
      isMounted = false
    }
  }, [chatId])

  const visibleChatId = chatId ?? pendingChatId
  const visibleMessages = visibleChatId
    ? [
        ...messages.filter((message) => message.chat_id === visibleChatId),
        ...pendingMessages.filter((message) => message.chat_id === visibleChatId),
      ]
    : []
  const isLoadingMessages = Boolean(chatId && messagesChatId !== chatId)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingMessages, chatId])

  async function createChat(title: string | null): Promise<Chat> {
    const chat = await api.post<Chat>('/chats', { title })
    if (!chat) throw new Error('The API did not return the created chat')
    setChats((current) => [chat, ...current])
    return chat
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const question = draft.trim()
    if (!question || isSending) return

    setDraft('')
    setError(null)
    setIsSending(true)
    let createdChatId: string | null = null
    const pendingUserId = `pending-${crypto.randomUUID()}`
    const pendingAssistantId = `pending-${crypto.randomUUID()}`
    try {
      let chat: Chat | undefined
      if (chatId) {
        chat =
          chats.find((item) => item.id === chatId) ??
          (await api.get<Chat[]>('/chats'))?.find((item) => item.id === chatId)
      } else {
        chat = await createChat(titleForQuestion(question))
        createdChatId = chat.id
      }

      if (!chat) throw new Error('Conversation not found')

      setPendingChatId(chat.id)
      setPendingMessages([
        {
          id: pendingUserId,
          chat_id: chat.id,
          role: 'user',
          content: question,
          created_at: new Date().toISOString(),
          citations: [],
        },
        {
          id: pendingAssistantId,
          chat_id: chat.id,
          role: 'assistant',
          content: '',
          created_at: new Date().toISOString(),
          citations: [],
          isDraft: true,
        },
      ])
      const completedTurns: ChatTurn[] = []
      await api.stream<ChatStreamEvent>(
        `/chats/${chat.id}/messages/stream`,
        { content: question },
        (event) => {
          if (event.type === 'delta' || event.type === 'replace') {
            setPendingMessages((current) =>
              current.map((message) =>
                message.id === pendingAssistantId
                  ? {
                      ...message,
                      content:
                        event.type === 'replace'
                          ? event.text
                          : message.content + event.text,
                    }
                  : message,
              ),
            )
          } else if (event.type === 'complete') {
            completedTurns.push(event.turn)
          }
        },
      )
      const turn = completedTurns.at(-1)
      if (!turn) throw new Error('The answer stream ended without a completed turn')

      setMessagesChatId(chat.id)
      setMessages((current) => [
        ...current,
        {
          id: turn.user_message_id,
          chat_id: turn.chat_id,
          role: 'user',
          content: turn.user_content,
          created_at: new Date().toISOString(),
          citations: [],
        },
        {
          id: turn.assistant_message_id,
          chat_id: turn.chat_id,
          role: 'assistant',
          content: turn.assistant_content,
          created_at: new Date().toISOString(),
          citations: turn.citations,
        },
      ])
      setPendingMessages([])
      setPendingChatId(null)
      if (createdChatId) navigate(`/chats/${createdChatId}`)
      try {
        await loadChats()
      } catch (loadError) {
        setError(displayError(loadError))
      }
    } catch (sendError) {
      setError(displayError(sendError))
      setDraft(question)
      setPendingMessages([])
      setPendingChatId(null)
      if (createdChatId) navigate(`/chats/${createdChatId}`)
    } finally {
      setIsSending(false)
    }
  }

  async function handleNewChat() {
    setError(null)
    try {
      const chat = await createChat('New conversation')
      navigate(`/chats/${chat.id}`)
    } catch (createError) {
      setError(displayError(createError))
    }
  }

  async function handleSignOut() {
    try {
      const { error: signOutError } = await supabase.auth.signOut()
      if (signOutError) setError(signOutError.message)
    } catch (signOutError) {
      setError(displayError(signOutError))
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-72 shrink-0 flex-col border-r bg-muted/20 md:flex">
        <div className="flex h-16 items-center justify-between border-b px-4">
          <Link className="font-semibold tracking-tight" to="/">
            Document Copilot
          </Link>
          <Button onClick={handleNewChat} size="sm" variant="outline">
            New chat
          </Button>
        </div>
        <nav aria-label="Conversation history" className="flex-1 space-y-1 overflow-y-auto p-3">
          {chats.map((chat) => (
            <Link
              className={`block truncate rounded-md px-3 py-2 text-sm hover:bg-accent ${chat.id === chatId ? 'bg-accent font-medium' : 'text-muted-foreground'}`}
              key={chat.id}
              to={`/chats/${chat.id}`}
            >
              {chat.title || 'New conversation'}
            </Link>
          ))}
          {!chats.length && !isLoading && (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              Your conversations will appear here.
            </p>
          )}
        </nav>
        <div className="border-t p-3">
          <Button
            className="w-full"
            onClick={() => void handleSignOut()}
            variant="ghost"
          >
            Sign out
          </Button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b px-4 md:px-8">
          <div className="flex items-center gap-3">
            <span className="font-semibold md:hidden">Document Copilot</span>
            <span className="hidden text-sm text-muted-foreground md:inline">
              {chats.find((chat) => chat.id === chatId)?.title ||
                'SEC filing research'}
            </span>
          </div>
          <div className="flex items-center gap-2 md:hidden">
            <label className="sr-only" htmlFor="mobile-chat-history">
              Conversation history
            </label>
            <select
              className="max-w-36 rounded-md border bg-background px-2 py-2 text-xs"
              id="mobile-chat-history"
              onChange={(event) =>
                navigate(event.target.value ? `/chats/${event.target.value}` : '/')
              }
              value={chatId ?? ''}
            >
              <option value="">History</option>
              {chats.map((chat) => (
                <option key={chat.id} value={chat.id}>
                  {chat.title || 'New conversation'}
                </option>
              ))}
            </select>
            <Button onClick={handleNewChat} size="sm" variant="outline">
              New
            </Button>
            <Button onClick={() => void handleSignOut()} size="sm" variant="ghost">
              Sign out
            </Button>
          </div>
        </header>

        <section
          aria-label="Conversation"
          className="mx-auto flex w-full max-w-4xl flex-1 flex-col overflow-y-auto px-4 py-6 md:px-8"
        >
          {(isLoading || isLoadingMessages) && (
            <p className="m-auto text-sm text-muted-foreground">
              Loading conversation…
            </p>
          )}
          {!isLoading && !isLoadingMessages && !visibleMessages.length && (
            <div className="m-auto max-w-xl py-12 text-center">
              <p className="text-sm font-semibold text-primary">RESEARCH COPILOT</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight">
                Ask the filings a better question.
              </h1>
              <p className="mt-3 text-muted-foreground">
                Search the SEC 10-K corpus and get an answer with the source
                passages attached.
              </p>
            </div>
          )}
          <div className="space-y-7">
            {visibleMessages.map((message) => (
              <article
                className={
                  message.role === 'user'
                    ? 'ml-auto max-w-[85%] rounded-2xl bg-primary px-4 py-3 text-primary-foreground'
                    : 'max-w-[90%] py-1'
                }
                key={message.id}
              >
                <p className="whitespace-pre-wrap text-sm leading-7">
                  {message.content}
                </p>
                {message.isDraft && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Draft answer — verifying citations before saving.
                  </p>
                )}
                {message.role === 'assistant' && (
                  <CitationList citations={message.citations} />
                )}
              </article>
            ))}
            {isSending && (
              <p className="text-sm text-muted-foreground">
                Searching filings and checking the evidence…
              </p>
            )}
          </div>
          <div ref={messagesEndRef} />
        </section>

        <div className="mx-auto w-full max-w-4xl px-4 pb-6 md:px-8">
          {error && (
            <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <form
            className="flex items-end gap-2 rounded-xl border bg-card p-2 shadow-sm"
            onSubmit={handleSubmit}
          >
            <label className="sr-only" htmlFor="question">
              Ask a question about the filings
            </label>
            <textarea
              className="max-h-40 min-h-11 flex-1 resize-y bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
              id="question"
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about revenue, risks, segments, or another filing detail…"
              value={draft}
            />
            <Button disabled={isSending || !draft.trim()} type="submit">
              {isSending ? 'Working…' : 'Send'}
            </Button>
          </form>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Answers are grounded in retrieved filing passages. Verify important
            conclusions against the source.
          </p>
        </div>
      </main>
    </div>
  )
}
