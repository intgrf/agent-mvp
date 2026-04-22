
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type Role = 'user' | 'agent' | 'system' | 'reasoning'

type ChatMessage = {
  id: string
  role: Role
  label: string
  body: string
  streamPos: number
  done: boolean
}

type ChatPayload =
  | { type: 'message'; user: string; text: string; suggestions: string[] }
  | { type: 'think'; text: string }

function parseChatFrame(raw: string): ChatPayload {
  try {
    const j = JSON.parse(raw) as Record<string, unknown>
    if (j.type === 'think' && typeof j.text === 'string') {
      return { type: 'think', text: j.text }
    }
    if (j.type === 'message' && typeof j.user === 'string' && typeof j.text === 'string') {
      const suggestions = Array.isArray(j.suggestions)
        ? (j.suggestions as unknown[]).filter((x): x is string => typeof x === 'string')
        : []
      return { type: 'message', user: j.user, text: j.text, suggestions }
    }
  } catch {
    /* legacy */
  }
  const colon = raw.indexOf(':')
  if (colon > 0) {
    return {
      type: 'message',
      user: raw.slice(0, colon).trim(),
      text: raw.slice(colon + 1).trim(),
      suggestions: [],
    }
  }
  return { type: 'message', user: 'System', text: raw, suggestions: [] }
}

function roleFromUser(user: string): Role {
  const u = user.toLowerCase()
  if (u === 'user') return 'user'
  if (u === 'system') return 'system'
  return 'agent'
}

let idCounter = 0
function nextId() {
  idCounter += 1
  return `m-${Date.now()}-${idCounter}`
}

let logLineCounter = 0
function nextLogLineId() {
  logLineCounter += 1
  return `l-${Date.now()}-${logLineCounter}`
}

const LS_SHOW_LOGS = 'sb_show_logs'
const LS_SHOW_TOKENS = 'sb_show_tokens'
const LS_CHAT_LAYOUT = 'sb_chat_layout'
const LS_UI_THEME = 'sb_ui_theme'

type ChatLayout = 'mobile' | 'desktop'
type UiTheme = 'forest' | 'ocean' | 'dusk' | 'ember'

function readStoredBool(key: string, defaultValue: boolean): boolean {
  try {
    const v = localStorage.getItem(key)
    if (v === null) return defaultValue
    return v === '1' || v === 'true'
  } catch {
    return defaultValue
  }
}

function readStoredLayout(): ChatLayout {
  try {
    const v = localStorage.getItem(LS_CHAT_LAYOUT)
    if (v === 'desktop') return 'desktop'
    return 'mobile'
  } catch {
    return 'mobile'
  }
}

const UI_THEMES: UiTheme[] = ['forest', 'ocean', 'dusk', 'ember']

function readStoredTheme(): UiTheme {
  try {
    const v = localStorage.getItem(LS_UI_THEME)
    if (v && (UI_THEMES as readonly string[]).includes(v)) return v as UiTheme
    return 'forest'
  } catch {
    return 'forest'
  }
}

type AppTab = 'chat' | 'settings'

type LogLine = { id: string; text: string; at: number }

type TokenStats = {
  totalTokens: number
  promptTokens: number
  completionTokens: number
  modelName: string
}

function parseLlmLog(logEntry: string): Partial<TokenStats> | null {
  const start = logEntry.indexOf('{')
  const end = logEntry.lastIndexOf('}')
  if (start === -1 || end <= start) return null
  try {
    const parsed = JSON.parse(logEntry.slice(start, end + 1)) as Record<string, unknown>
    const out: Partial<TokenStats> = {}
    if (typeof parsed.model_name === 'string') out.modelName = parsed.model_name
    if (typeof parsed.prompt_tokens === 'number') out.promptTokens = parsed.prompt_tokens
    if (typeof parsed.completion_tokens === 'number') out.completionTokens = parsed.completion_tokens
    if (typeof parsed.total_tokens === 'number') out.totalTokens = parsed.total_tokens
    return out
  } catch {
    return null
  }
}

function MarkdownBody({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>('chat')
  const [showLogs, setShowLogs] = useState(() => readStoredBool(LS_SHOW_LOGS, false))
  const [showTokens, setShowTokens] = useState(() => readStoredBool(LS_SHOW_TOKENS, true))
  const [chatLayout, setChatLayout] = useState<ChatLayout>(() => readStoredLayout())
  const [uiTheme, setUiTheme] = useState<UiTheme>(() => readStoredTheme())

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [chatConnected, setChatConnected] = useState(false)
  const [tokens, setTokens] = useState<TokenStats>({
    totalTokens: 0,
    promptTokens: 0,
    completionTokens: 0,
    modelName: '—',
  })
  const [logLines, setLogLines] = useState<LogLine[]>([])

  const chatRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const logsEndRef = useRef<HTMLDivElement | null>(null)
  const showLogsRef = useRef(showLogs)

  useEffect(() => {
    showLogsRef.current = showLogs
  }, [showLogs])

  useLayoutEffect(() => {
    if (uiTheme === 'forest') {
      document.documentElement.removeAttribute('data-theme')
    } else {
      document.documentElement.setAttribute('data-theme', uiTheme)
    }
  }, [uiTheme])

  useEffect(() => {
    if (!showLogs) return
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logLines, showLogs])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  useEffect(() => {
    const t = window.setInterval(() => {
      setMessages((prev) => {
        let changed = false
        const next = prev.map((m) => {
          if (m.done || m.streamPos >= m.body.length) return m
          changed = true
          const np = Math.min(m.body.length, m.streamPos + 2)
          return { ...m, streamPos: np, done: np >= m.body.length }
        })
        return changed ? next : prev
      })
    }, 18)
    return () => window.clearInterval(t)
  }, [])

  const appendUserMessage = useCallback((text: string) => {
    setSuggestions([])
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        role: 'user',
        label: 'You',
        body: text,
        streamPos: text.length,
        done: true,
      },
    ])
  }, [])

  const handleIncoming = useCallback(
    (raw: string) => {
      const payload = parseChatFrame(raw)
      if (payload.type === 'think') {
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role === 'reasoning') {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                body: payload.text,
                streamPos: 0,
                done: false,
              },
            ]
          }
          return [
            ...prev,
            {
              id: nextId(),
              role: 'reasoning',
              label: 'Reasoning',
              body: payload.text,
              streamPos: 0,
              done: false,
            },
          ]
        })
        return
      }
      const role = roleFromUser(payload.user)
      if (role === 'user') {
        appendUserMessage(payload.text)
        return
      }
      const sug = payload.suggestions ?? []
      setMessages((prev) => {
        const last = prev[prev.length - 1]
        if (last?.role === 'reasoning') {
          return [
            ...prev.slice(0, -1),
            {
              id: last.id,
              role,
              label: payload.user,
              body: payload.text,
              streamPos: 0,
              done: false,
            },
          ]
        }
        return [
          ...prev,
          {
            id: nextId(),
            role,
            label: payload.user,
            body: payload.text,
            streamPos: 0,
            done: false,
          },
        ]
      })
      setSuggestions(sug.length ? sug : [])
    },
    [appendUserMessage],
  )

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const chat = new WebSocket(`${proto}://${host}/chat`)
    chatRef.current = chat
    chat.onopen = () => {
      setChatConnected(true)
      setMessages((p) => [
        ...p,
        {
          id: nextId(),
          role: 'system',
          label: 'System',
          body: 'Соединение установлено.',
          streamPos: 0,
          done: false,
        },
      ])
    }
    chat.onclose = () => setChatConnected(false)
    chat.onmessage = (ev) => handleIncoming(String(ev.data))
    return () => chat.close()
  }, [handleIncoming])

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const log = new WebSocket(`${proto}://${host}/log`)
    log.onmessage = (ev) => {
      const logEntry = String(ev.data)
      if (logEntry.toLowerCase().includes('llm')) {
        const patch = parseLlmLog(logEntry)
        if (patch) {
          setTokens((prev) => ({
            modelName: patch.modelName ?? prev.modelName,
            promptTokens: patch.promptTokens ?? prev.promptTokens,
            completionTokens: patch.completionTokens ?? prev.completionTokens,
            totalTokens: prev.totalTokens + (patch.totalTokens ?? 0),
          }))
        }
      }
      if (showLogsRef.current) {
        setLogLines((prev) => {
          const next = [
            ...prev,
            { id: nextLogLineId(), text: logEntry, at: Date.now() },
          ]
          return next.length > 500 ? next.slice(-500) : next
        })
      }
    }
    return () => log.close()
  }, [])

  const send = useCallback(() => {
    const text = input.trim()
    if (!text || !chatRef.current || chatRef.current.readyState !== WebSocket.OPEN) return
    appendUserMessage(text)
    chatRef.current.send(text)
    setInput('')
  }, [input, appendUserMessage])

  const sendSuggest = useCallback(
    (text: string) => {
      if (!chatRef.current || chatRef.current.readyState !== WebSocket.OPEN) return
      appendUserMessage(text)
      chatRef.current.send(text)
      setSuggestions([])
    },
    [appendUserMessage],
  )

  const setLogsEnabled = useCallback((value: boolean) => {
    setShowLogs(value)
    try {
      localStorage.setItem(LS_SHOW_LOGS, value ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [])

  const setTokensPanelEnabled = useCallback((value: boolean) => {
    setShowTokens(value)
    try {
      localStorage.setItem(LS_SHOW_TOKENS, value ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [])

  const clearLogs = useCallback(() => setLogLines([]), [])

  const persistChatLayout = useCallback((mode: ChatLayout) => {
    setChatLayout(mode)
    try {
      localStorage.setItem(LS_CHAT_LAYOUT, mode)
    } catch {
      /* ignore */
    }
  }, [])

  const persistUiTheme = useCallback((theme: UiTheme) => {
    setUiTheme(theme)
    try {
      localStorage.setItem(LS_UI_THEME, theme)
    } catch {
      /* ignore */
    }
  }, [])

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" aria-hidden />
      <div className="ambient ambient-b" aria-hidden />
      <div className="ambient ambient-c" aria-hidden />
      <div className="ambient ambient-d" aria-hidden />
      <div className="bg-mesh" aria-hidden />
      <div className="bg-noise" aria-hidden />
      <header className="app-header">
        <div className="app-header-row">
          <div className="brand">
            <span className="brand-kicker">AI workspace</span>
            <span className="brand-title">Companion</span>
            <span className="brand-sub">Чат, reasoning и логи в одном пространстве</span>
          </div>
          <div className="header-side">
            <div className={`status-pill${chatConnected ? '' : ' off'}`}>
              <span className={`status-dot${chatConnected ? '' : ' off'}`} />
              <span>{chatConnected ? 'Подключено' : 'Нет соединения'}</span>
            </div>
            {showTokens ? (
              <div className="token-pill">
                <span className="token-pill-label">LLM usage</span>
                <div className="token-pill-value">{tokens.totalTokens.toLocaleString()}</div>
                <div className="token-pill-meta">
                  prompt {tokens.promptTokens} · completion {tokens.completionTokens}
                </div>
                <div className="token-pill-model">Модель: {tokens.modelName}</div>
              </div>
            ) : null}
          </div>
        </div>
        <nav className="app-tabs" role="tablist" aria-label="Разделы">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'chat'}
            className={`app-tab${activeTab === 'chat' ? ' active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            Чат
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'settings'}
            className={`app-tab${activeTab === 'settings' ? ' active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            Настройки
          </button>
        </nav>
      </header>

      {activeTab === 'chat' ? (
        <div className={`main-stage${showLogs ? ' with-logs' : ''} layout-${chatLayout}`}>
          <div className="phone-wrap">
            <div className="ring-deco" aria-hidden />
            <div className="ring-deco sm" aria-hidden />
            <div className="phone">
              <div className="phone-notch">
                <span />
              </div>
              <div className="phone-header">
                <h1>Диалог</h1>
                <div className={`status-dot${chatConnected ? '' : ' off'}`} title={chatConnected ? 'online' : 'offline'} />
              </div>

              <div className="messages">
                {messages.map((m) => (
                  <div key={m.id} className={`bubble ${m.role}`}>
                    {m.role === 'reasoning' ? (
                      <>
                        <div className="think-label">
                          Reasoning
                          <span className="think-shimmer" />
                        </div>
                        <div className="think-body">{m.body.slice(0, m.streamPos)}</div>
                      </>
                    ) : (
                      <>
                        <div className="bubble-meta">{m.label}</div>
                        {!m.done ? (
                          <div className="stream-plain">{m.body.slice(0, m.streamPos)}</div>
                        ) : (
                          <MarkdownBody text={m.body} />
                        )}
                      </>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {suggestions.length > 0 ? (
                <div className="suggest-strip">
                  <h3>Спросить ещё</h3>
                  <div className="suggest-scroll">
                    {suggestions.map((s) => (
                      <button key={s} type="button" className="suggest-chip" onClick={() => sendSuggest(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="input-row">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Сообщение…"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') send()
                  }}
                />
                <button type="button" className="send-btn" disabled={!chatConnected} onClick={send} aria-label="Отправить">
                  →
                </button>
              </div>
            </div>
          </div>

          {showLogs ? (
            <aside className="logs-panel" aria-label="Логи приложения">
              <div className="logs-panel-head">
                <div className="logs-panel-copy">
                  <span className="logs-panel-title">Логи</span>
                  <span className="logs-panel-subtitle">Поток событий сервера</span>
                </div>
                <button type="button" className="logs-clear-btn" onClick={clearLogs}>
                  Очистить
                </button>
              </div>
              <div className="logs-panel-body">
                {logLines.length === 0 ? (
                  <p className="logs-empty">Пока нет записей. Логи появятся здесь по мере работы сервера.</p>
                ) : (
                  logLines.map((line) => (
                    <pre key={line.id} className={`log-line${line.text.toLowerCase().includes('llm') ? ' llm' : ''}`}>
                      {line.text}
                    </pre>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </aside>
          ) : null}
        </div>
      ) : (
        <div className="settings-page">
          <h2 className="settings-title">Настройки</h2>
          <p className="settings-lead">Параметры сохраняются в этом браузере.</p>

          <div className="setting-card setting-card-stack">
            <div className="setting-text">
              <div className="setting-name">Цветовая гамма</div>
              <div className="setting-desc">Акцентные цвета, фон и подсветка интерфейса пересчитываются под выбранную тему.</div>
            </div>
            <div className="theme-grid" role="group" aria-label="Цветовая гамма">
              <button
                type="button"
                className={`theme-option${uiTheme === 'forest' ? ' active' : ''}`}
                aria-pressed={uiTheme === 'forest'}
                onClick={() => persistUiTheme('forest')}
              >
                <span className="theme-swatch theme-swatch-forest" aria-hidden />
                <span className="theme-label">Лес</span>
                <span className="theme-hint">мята</span>
              </button>
              <button
                type="button"
                className={`theme-option${uiTheme === 'ocean' ? ' active' : ''}`}
                aria-pressed={uiTheme === 'ocean'}
                onClick={() => persistUiTheme('ocean')}
              >
                <span className="theme-swatch theme-swatch-ocean" aria-hidden />
                <span className="theme-label">Океан</span>
                <span className="theme-hint">синий</span>
              </button>
              <button
                type="button"
                className={`theme-option${uiTheme === 'dusk' ? ' active' : ''}`}
                aria-pressed={uiTheme === 'dusk'}
                onClick={() => persistUiTheme('dusk')}
              >
                <span className="theme-swatch theme-swatch-dusk" aria-hidden />
                <span className="theme-label">Сумерки</span>
                <span className="theme-hint">фиолет</span>
              </button>
              <button
                type="button"
                className={`theme-option${uiTheme === 'ember' ? ' active' : ''}`}
                aria-pressed={uiTheme === 'ember'}
                onClick={() => persistUiTheme('ember')}
              >
                <span className="theme-swatch theme-swatch-ember" aria-hidden />
                <span className="theme-label">Угли</span>
                <span className="theme-hint">янтарь</span>
              </button>
            </div>
          </div>

          <div className="setting-card">
            <div className="setting-text">
              <div className="setting-name">Логи рядом с чатом</div>
              <div className="setting-desc">Отдельная панель справа от телефона (на узком экране — под чатом).</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={showLogs}
              className={`switch${showLogs ? ' on' : ''}`}
              onClick={() => setLogsEnabled(!showLogs)}
            >
              <span className="switch-knob" />
            </button>
          </div>

          <div className="setting-card">
            <div className="setting-text">
              <div className="setting-name">Панель токенов</div>
              <div className="setting-desc">Сводка по LLM в шапке (prompt / completion / модель).</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={showTokens}
              className={`switch${showTokens ? ' on' : ''}`}
              onClick={() => setTokensPanelEnabled(!showTokens)}
            >
              <span className="switch-knob" />
            </button>
          </div>

          <div className="setting-card setting-card-stack">
            <div className="setting-text">
              <div className="setting-name">Вид чата</div>
              <div className="setting-desc">
                Телефон — компактное окно как на мобильном. ПК — широкая панель диалога на весь доступный размер.
              </div>
            </div>
            <div className="segmented segmented-wide" role="group" aria-label="Вид чата">
              <button
                type="button"
                className={chatLayout === 'mobile' ? 'active' : ''}
                aria-pressed={chatLayout === 'mobile'}
                onClick={() => persistChatLayout('mobile')}
              >
                Телефон
              </button>
              <button
                type="button"
                className={chatLayout === 'desktop' ? 'active' : ''}
                aria-pressed={chatLayout === 'desktop'}
                onClick={() => persistChatLayout('desktop')}
              >
                ПК
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}