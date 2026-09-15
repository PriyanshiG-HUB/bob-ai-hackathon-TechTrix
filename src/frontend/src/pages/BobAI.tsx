import { useState, useRef, useEffect } from 'react'
import { PaperPlaneTilt, Robot, CircleNotch } from '@phosphor-icons/react'
import TopBar from '../components/TopBar'
import { bobChat, extractErrorMessage } from '../services/api'
import styles from './BobAI.module.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  ts: Date
  toolUsed?: string
  isError?: boolean
}

const SUGGESTED = [
  'Show me the highest priority safety signals',
  'What is the PRR for MEDROXYPROGESTERONE ACETATE and Meningioma?',
  'How many reports are in the dataset?',
  'What should I fix first in my submission?',
  'Is my submission ready?',
  'What is missing from Module 3?',
]

export default function BobAIPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        'Hello. I am Bob AI, backed by the AetherGuard AI pharmacovigilance and ICH M4 regulatory readiness engine. Ask me about statistical safety signals (PRR/χ²), dataset metrics, submission completeness, or gap remediation.',
      ts: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || isLoading) return

    const userMsg: Message = { role: 'user', content: q, ts: new Date() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const res = await bobChat({ message: q })
      const assistantMsg: Message = {
        role: 'assistant',
        content: res.response,
        ts: new Date(),
        toolUsed: res.tool_used,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err)
      const errorAssistantMsg: Message = {
        role: 'assistant',
        content: `Error connecting to AetherGuard backend: ${errMsg}. Please ensure the backend server is running on http://127.0.0.1:8000.`,
        ts: new Date(),
        isError: true,
      }
      setMessages(prev => [...prev, errorAssistantMsg])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    send(input)
  }

  const fmt = (d: Date) =>
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })

  return (
    <div className={styles.page}>
      <TopBar
        title="Bob AI"
        subtitle="Pharmacovigilance intelligence assistant — Local Tool-Backed Bridge"
        actions={
          <span className={styles.statusBadge}>
            <span className={styles.statusDot} style={{ background: 'var(--success, #10b981)' }} />
            AetherGuard Engine Connected
          </span>
        }
      />

      <div className={styles.layout}>
        {/* Suggested prompts */}
        <aside className={styles.sidebar}>
          <h3 className={styles.sidebarTitle}>Suggested Questions</h3>
          <ul className={styles.promptList}>
            {SUGGESTED.map(s => (
              <li key={s}>
                <button
                  className={styles.promptBtn}
                  onClick={() => send(s)}
                  disabled={isLoading}
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
          <div className={styles.integrationNote}>
            <Robot size={16} />
            <span>
              Bob AI is operating via the local AetherGuard deterministic tool bridge. (Direct IBM Bob hosted conversational API integration is planned).
            </span>
          </div>
        </aside>

        {/* Chat */}
        <div className={styles.chatPane}>
          <div className={styles.messages} role="log" aria-live="polite" aria-label="Chat messages">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`${styles.bubble} ${
                  msg.role === 'user'
                    ? styles.userBubble
                    : styles.assistantBubble
                }`}
                style={msg.isError ? { borderColor: 'var(--danger, #ef4444)' } : undefined}
              >
                <div className={styles.bubbleHeader}>
                  <span className={styles.bubbleRole}>
                    {msg.role === 'user' ? 'You' : 'Bob AI'}
                  </span>
                  {msg.toolUsed && (
                    <span
                      style={{
                        fontSize: '10px',
                        padding: '1px 6px',
                        borderRadius: '10px',
                        background: 'var(--accent-pale, #eff6ff)',
                        color: 'var(--accent, #2563eb)',
                        fontFamily: 'var(--font-mono, monospace)',
                      }}
                    >
                      {msg.toolUsed}
                    </span>
                  )}
                  <span className={styles.bubbleTime}>{fmt(msg.ts)}</span>
                </div>
                <div
                  className={styles.bubbleContent}
                  style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className={`${styles.bubble} ${styles.assistantBubble}`}>
                <div className={styles.bubbleHeader}>
                  <span className={styles.bubbleRole}>Bob AI</span>
                </div>
                <div
                  className={styles.bubbleContent}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--gray-500)' }}
                >
                  <CircleNotch size={16} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Querying AetherGuard engine…</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form className={styles.inputRow} onSubmit={handleSubmit}>
            <input
              className={styles.chatInput}
              type="text"
              placeholder="Ask about signals, submission readiness, or regulatory gaps…"
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={isLoading}
              aria-label="Message input"
            />
            <button
              className={styles.sendBtn}
              type="submit"
              disabled={!input.trim() || isLoading}
              aria-label="Send"
            >
              <PaperPlaneTilt size={16} weight="bold" />
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
