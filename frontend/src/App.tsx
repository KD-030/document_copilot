import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from '@/lib/use-auth'
import { ChatPage } from '@/pages/chat'
import { LoginPage } from '@/pages/login'

function ProtectedRoute() {
  const { isLoading, session } = useAuth()

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center text-sm text-muted-foreground">
        Loading Document Copilot…
      </main>
    )
  }

  return session ? <ChatPage /> : <Navigate to="/login" replace />
}

export default function App() {
  const { session } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={session ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route path="/" element={<ProtectedRoute />} />
      <Route path="/chats/:chatId" element={<ProtectedRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
