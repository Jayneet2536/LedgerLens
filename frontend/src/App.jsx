import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock3,
  DatabaseZap,
  Loader2,
  RefreshCcw,
  Send,
  SlidersHorizontal,
  User,
  X,
} from "lucide-react";
import {
  getHealth,
  getReindexStatus,
  getStrategies,
  sendChat,
  startReindex,
  updateRetrievalStrategy,
} from "./api";

const POLL_INTERVAL_MS = 2200;

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [health, setHealth] = useState(null);
  const [strategies, setStrategies] = useState({
    chunking_strategies: [],
    retrieval_strategies: [],
  });
  const [selectedRetrieval, setSelectedRetrieval] = useState("");
  const [selectedChunking, setSelectedChunking] = useState("");
  const [pendingChat, setPendingChat] = useState(false);
  const [loadingApp, setLoadingApp] = useState(true);
  const [statusMessage, setStatusMessage] = useState("");
  const [retrievalStatus, setRetrievalStatus] = useState("idle");
  const [retrievalError, setRetrievalError] = useState("");
  const [reindexStatus, setReindexStatus] = useState("idle");
  const [reindexDetail, setReindexDetail] = useState("");
  const [showReindexBanner, setShowReindexBanner] = useState(false);
  const [sourceDisclosure, setSourceDisclosure] = useState({});
  const listRef = useRef(null);

  useEffect(() => {
    let alive = true;

    async function loadInitialState() {
      try {
        const [healthData, strategiesData] = await Promise.all([getHealth(), getStrategies()]);

        if (!alive) {
          return;
        }

        setHealth(healthData);
        setStrategies(strategiesData);
        setSelectedRetrieval(healthData.retrieval_strategy || strategiesData.retrieval_strategies[0] || "");
        setSelectedChunking(healthData.chunking_strategy || strategiesData.chunking_strategies[0] || "");
        setReindexStatus(healthData.reindex_status || "idle");
        setReindexDetail(healthData.detail || "");
        setShowReindexBanner(healthData.reindex_status === "reindexing" || healthData.reindex_status === "error");
      } catch (error) {
        if (alive) {
          setStatusMessage(error.message || "Couldn't load backend status.");
        }
      } finally {
        if (alive) {
          setLoadingApp(false);
        }
      }
    }

    loadInitialState();

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!listRef.current) {
      return;
    }

    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, pendingChat]);

  useEffect(() => {
    if (!showReindexBanner || reindexStatus !== "reindexing") {
      return undefined;
    }

    let cancelled = false;

    async function pollStatus() {
      try {
        const status = await getReindexStatus();

        if (cancelled) {
          return;
        }

        setReindexStatus(status.status);
        setReindexDetail(status.detail || "");

        if (status.status === "idle") {
          setShowReindexBanner(false);
          refreshHealth();
        }

        if (status.status === "error") {
          setShowReindexBanner(true);
        }
      } catch (error) {
        if (!cancelled) {
          setReindexStatus("error");
          setReindexDetail(error.message || "Reindex status could not be checked.");
          setShowReindexBanner(true);
        }
      }
    }

    pollStatus();
    const intervalId = window.setInterval(pollStatus, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [showReindexBanner, reindexStatus]);

  const noIndexLoaded = health && !health.index_loaded && reindexStatus !== "reindexing";
  const chatDisabled = pendingChat || showReindexBanner || noIndexLoaded;
  const activeSummary = useMemo(() => {
    if (!health) {
      return "Checking index...";
    }

    if (!health.index_loaded) {
      return "No index loaded";
    }

    return `${health.chunking_strategy} / ${health.retrieval_strategy} / top ${health.top_k_results}`;
  }, [health]);

  async function refreshHealth() {
    try {
      const healthData = await getHealth();
      setHealth(healthData);
      setSelectedRetrieval(healthData.retrieval_strategy || selectedRetrieval);
      setSelectedChunking(healthData.chunking_strategy || selectedChunking);
      setReindexStatus(healthData.reindex_status || "idle");
      setReindexDetail(healthData.detail || "");
    } catch (error) {
      setStatusMessage(error.message || "Couldn't refresh backend status.");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const message = input.trim();

    if (!message || chatDisabled) {
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    };

    setMessages((current) => [...current, userMessage]);
    setInput("");
    setPendingChat(true);

    try {
      const response = await sendChat(message);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          latencyMs: response.latency_ms,
          sources: response.sources || [],
        },
      ]);
    } catch (error) {
      if (error.status === 503) {
        await refreshHealth();

        if (/reindex/i.test(error.message)) {
          setReindexStatus("reindexing");
          setShowReindexBanner(true);
          setReindexDetail(error.message);
          return;
        }
      }

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "error",
          content:
            error.status === 503
              ? "No document indexed yet. Start a rebuild to make chat available."
              : error.message || "Couldn't reach the server - try again",
        },
      ]);
    } finally {
      setPendingChat(false);
    }
  }

  async function handleRetrievalChange(event) {
    const nextStrategy = event.target.value;
    const previousStrategy = selectedRetrieval;

    if (!nextStrategy || nextStrategy === selectedRetrieval) {
      return;
    }

    setRetrievalStatus("saving");
    setRetrievalError("");

    try {
      const response = await updateRetrievalStrategy(nextStrategy);
      setSelectedRetrieval(response.retrieval_strategy);
      setHealth((current) =>
        current
          ? {
              ...current,
              retrieval_strategy: response.retrieval_strategy,
              top_k_results: response.top_k_results,
            }
          : current,
      );
      setRetrievalStatus("saved");
      window.setTimeout(() => setRetrievalStatus("idle"), 1300);
    } catch (error) {
      setSelectedRetrieval(previousStrategy);
      setRetrievalError(error.message || "Strategy update failed.");
      setRetrievalStatus("error");

      if (error.status === 503 && /reindex/i.test(error.message)) {
        setReindexStatus("reindexing");
        setReindexDetail(error.message);
        setShowReindexBanner(true);
      }
    }
  }

  async function handleReindex() {
    if (!selectedChunking || reindexStatus === "reindexing") {
      return;
    }

    setShowReindexBanner(true);
    setReindexStatus("reindexing");
    setReindexDetail("");

    try {
      await startReindex(selectedChunking);
      await refreshHealth();
      setShowReindexBanner(true);
      setReindexStatus("reindexing");
    } catch (error) {
      if (error.status === 409) {
        setShowReindexBanner(true);
        setReindexStatus("reindexing");
        setReindexDetail(error.message);
        return;
      }

      setReindexStatus("error");
      setReindexDetail(error.message || "Reindex could not be started.");
      setShowReindexBanner(true);
    }
  }

  function dismissReindexError() {
    setShowReindexBanner(false);
    setReindexStatus("idle");
    setReindexDetail("");
    refreshHealth();
  }

  function toggleSource(id) {
    setSourceDisclosure((current) => ({
      ...current,
      [id]: !current[id],
    }));
  }

  return (
    <main className="shell">
      <section className="workspace">
        <aside className="strategy-panel">
          <div className="brand-row">
            <div className="brand-mark">
              <DatabaseZap size={20} />
            </div>
            <div>
              <p className="eyebrow">RAG Console</p>
              <h1>Document Chat</h1>
            </div>
          </div>

          <div className="status-card">
            <span className={`status-dot ${health?.index_loaded ? "ready" : "offline"}`} />
            <div>
              <p>Active configuration</p>
              <strong>{activeSummary}</strong>
            </div>
          </div>

          <div className="control-section instant">
            <div className="section-title">
              <SlidersHorizontal size={17} />
              <span>Switch retrieval mode</span>
            </div>
            <label htmlFor="retrieval-strategy">Instant update</label>
            <div className="select-wrap">
              <select
                id="retrieval-strategy"
                value={selectedRetrieval}
                onChange={handleRetrievalChange}
                disabled={retrievalStatus === "saving" || showReindexBanner || noIndexLoaded}
              >
                {strategies.retrieval_strategies.map((strategy) => (
                  <option key={strategy} value={strategy}>
                    {formatStrategyName(strategy)}
                  </option>
                ))}
              </select>
              <ChevronDown size={16} />
            </div>
            <InlineStatus status={retrievalStatus} error={retrievalError} />
          </div>

          <div className="control-section rebuild">
            <div className="section-title">
              <RefreshCcw size={17} />
              <span>Rebuild index</span>
            </div>
            <label htmlFor="chunking-strategy">Slow operation</label>
            <div className="chunking-row">
              <div className="select-wrap">
                <select
                  id="chunking-strategy"
                  value={selectedChunking}
                  onChange={(event) => setSelectedChunking(event.target.value)}
                  disabled={reindexStatus === "reindexing"}
                >
                  {strategies.chunking_strategies.map((strategy) => (
                    <option key={strategy} value={strategy}>
                      {formatStrategyName(strategy)}
                    </option>
                  ))}
                </select>
                <ChevronDown size={16} />
              </div>
              <button
                className="reindex-button"
                type="button"
                onClick={handleReindex}
                disabled={!selectedChunking || reindexStatus === "reindexing"}
                title="Rebuild the vector index with the selected chunking strategy"
              >
                {reindexStatus === "reindexing" ? <Loader2 size={17} className="spin" /> : <RefreshCcw size={17} />}
                Reindex
              </button>
            </div>
          </div>
        </aside>

        <section className="chat-panel">
          {showReindexBanner && (
            <ReindexBanner
              status={reindexStatus}
              detail={reindexDetail}
              onDismiss={dismissReindexError}
              onRetry={handleReindex}
            />
          )}

          {statusMessage && (
            <div className="inline-alert">
              <AlertCircle size={18} />
              <span>{statusMessage}</span>
              <button type="button" onClick={() => setStatusMessage("")} aria-label="Dismiss status">
                <X size={16} />
              </button>
            </div>
          )}

          <div className="chat-header">
            <div>
              <p className="eyebrow">Ask across indexed documents</p>
              <h2>Chat</h2>
            </div>
            <div className="health-pill">
              {loadingApp ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
              {health?.index_loaded ? "Index ready" : "Index unavailable"}
            </div>
          </div>

          {noIndexLoaded ? (
            <NoIndexState selectedChunking={selectedChunking} onReindex={handleReindex} />
          ) : (
            <>
              <div className="message-list" ref={listRef}>
                {messages.length === 0 && (
                  <div className="empty-chat">
                    <Bot size={28} />
                    <h3>Ready for questions</h3>
                    <p>Ask about the indexed Amazon filing and inspect the cited chunks under each response.</p>
                  </div>
                )}

                {messages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    expanded={Boolean(sourceDisclosure[message.id])}
                    onToggleSources={() => toggleSource(message.id)}
                  />
                ))}

                {pendingChat && (
                  <div className="message assistant pending">
                    <div className="avatar">
                      <Bot size={18} />
                    </div>
                    <div className="bubble">
                      <Loader2 size={18} className="spin" />
                      <span>Searching the index...</span>
                    </div>
                  </div>
                )}
              </div>

              <form className="composer" onSubmit={handleSubmit}>
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      handleSubmit(event);
                    }
                  }}
                  disabled={chatDisabled}
                  placeholder={showReindexBanner ? "Chat is paused while the index rebuilds" : "Ask a question..."}
                  rows={1}
                />
                <button type="submit" disabled={!input.trim() || chatDisabled} title="Send message">
                  <Send size={18} />
                </button>
              </form>
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function InlineStatus({ status, error }) {
  if (status === "saving") {
    return (
      <p className="inline-status">
        <Loader2 size={14} className="spin" />
        Updating retrieval mode...
      </p>
    );
  }

  if (status === "saved") {
    return (
      <p className="inline-status success">
        <CheckCircle2 size={14} />
        Retrieval mode updated
      </p>
    );
  }

  if (status === "error") {
    return (
      <p className="inline-status error">
        <AlertCircle size={14} />
        {error}
      </p>
    );
  }

  return null;
}

function ReindexBanner({ status, detail, onDismiss, onRetry }) {
  const isError = status === "error";

  return (
    <div className={`reindex-banner ${isError ? "error" : ""}`}>
      <div className="banner-icon">{isError ? <AlertCircle size={20} /> : <Loader2 size={20} className="spin" />}</div>
      <div>
        <strong>{isError ? "Rebuild needs attention" : "Rebuilding index with the new strategy"}</strong>
        <p>{isError ? detail || "The index rebuild failed." : "This can take a minute. Chat is paused until it finishes."}</p>
      </div>
      {isError && (
        <div className="banner-actions">
          <button type="button" onClick={onRetry}>
            Retry
          </button>
          <button type="button" onClick={onDismiss} aria-label="Dismiss reindex error">
            <X size={17} />
          </button>
        </div>
      )}
    </div>
  );
}

function NoIndexState({ selectedChunking, onReindex }) {
  return (
    <div className="no-index">
      <DatabaseZap size={34} />
      <h3>No document indexed yet</h3>
      <p>Build the first index with {formatStrategyName(selectedChunking) || "the selected"} chunking strategy to begin chatting.</p>
      <button type="button" onClick={onReindex}>
        <RefreshCcw size={17} />
        Build index
      </button>
    </div>
  );
}

function MessageBubble({ message, expanded, onToggleSources }) {
  const isUser = message.role === "user";
  const isError = message.role === "error";
  const sources = message.sources || [];

  return (
    <div className={`message ${isUser ? "user" : "assistant"} ${isError ? "error" : ""}`}>
      <div className="avatar">{isUser ? <User size={18} /> : isError ? <AlertCircle size={18} /> : <Bot size={18} />}</div>
      <div className="bubble-wrap">
        <div className="bubble">
          {isUser || isError ? message.content : <MessageContent content={message.content} />}
        </div>

        {!isUser && !isError && (
          <div className="message-meta">
            <span className="latency-badge">
              <Clock3 size={13} />
              {formatLatency(message.latencyMs)}
            </span>
            <button className="sources-toggle" type="button" onClick={onToggleSources} aria-expanded={expanded}>
              Sources ({sources.length})
              <ChevronDown size={14} className={expanded ? "open" : ""} />
            </button>
          </div>
        )}

        {expanded && sources.length > 0 && (
          <div className="sources-list">
            {sources.map((source, index) => (
              <SourceCard key={`${message.id}-${index}`} source={source} index={index} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SourceCard({ source, index }) {
  const [expanded, setExpanded] = useState(false);
  const metadata = source.metadata || {};
  const content = source.content || "";
  const shouldTruncate = content.length > 440;
  const visibleText = shouldTruncate && !expanded ? `${content.slice(0, 440).trim()}...` : content;
  const metadataEntries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined && value !== "");

  return (
    <article className="source-card">
      <header>
        <strong>Source {index + 1}</strong>
        {metadataEntries.length > 0 && <span>{metadataEntries.slice(0, 2).map(([key, value]) => `${formatStrategyName(key)}: ${value}`).join(" - ")}</span>}
      </header>
      <p>{visibleText}</p>
      {shouldTruncate && (
        <button type="button" onClick={() => setExpanded((current) => !current)}>
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
      {metadataEntries.length > 2 && (
        <dl>
          {metadataEntries.slice(2, 8).map(([key, value]) => (
            <div key={key}>
              <dt>{formatStrategyName(key)}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

function MessageContent({ content }) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="message-content">
      {blocks.map((block, index) => {
        if (block.type === "list") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
              ))}
            </ul>
          );
        }

        return <p key={index}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}

function parseMarkdownBlocks(content) {
  const lines = String(content || "").split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let listItems = [];

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  }

  function flushList() {
    if (listItems.length > 0) {
      blocks.push({ type: "list", items: listItems });
      listItems = [];
    }
  }

  lines.forEach((line) => {
    const trimmed = line.trim();
    const listMatch = /^[-*]\s+(.+)$/.exec(trimmed);

    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch[1]);
      return;
    }

    flushList();
    paragraph.push(trimmed);
  });

  flushParagraph();
  flushList();

  return blocks.length > 0 ? blocks : [{ type: "paragraph", text: "" }];
}

function renderInlineMarkdown(text) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    return part;
  });
}

function formatLatency(latencyMs) {
  if (typeof latencyMs !== "number") {
    return "0.0s";
  }

  return `${(latencyMs / 1000).toFixed(1)}s`;
}

function formatStrategyName(value) {
  if (!value) {
    return "";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default App;
