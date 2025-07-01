/* ------------------------------------------------------------------
   TMobileChatWidget.jsx – bubble launcher + Home-Internet chat
   (scroll-fix + minimise) – 2025-07-01 patch 3
------------------------------------------------------------------ */
import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, X, ChevronDown, ChevronUp } from "lucide-react";

/* tiny util */
const cn = (...c) => c.filter(Boolean).join(" ");

/* -------- basic atoms -------- */
const Card = ({ children, className = "" }) => (
  <div className={cn("flex flex-col rounded-2xl shadow-lg overflow-hidden", className)}>
    {children}
  </div>
);

const Input = (p) => (
  <input
    {...p}
    className="border-2 border-magenta-dark rounded px-3 py-1.5 w-full text-black
               placeholder:text-magenta-dark/50 focus:ring-2 focus:ring-magenta
               outline-none disabled:opacity-50"
  />
);

const Button = ({ children, className = "", ...rest }) => (
  <button
    {...rest}
    className={cn(
      "bg-gradient-to-r from-magenta to-magenta-dark hover:brightness-110 text-white rounded transition",
      "disabled:opacity-50 disabled:pointer-events-none",
      className,
    )}
  >
    {children}
  </button>
);

/* -------- quick-reply pills -------- */
const QuickReplies = ({ options = [], picked, onPick }) =>
  options.length ? (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-wrap gap-2"
    >
      {options.map((o) => (
        <Button
          key={o.value}
          onClick={() => onPick(o)}
          className={cn("text-[14px] font-medium px-3 py-1", o.value === picked && "opacity-70")}
        >
          {o.value === picked && "✓ "}
          {o.label}
        </Button>
      ))}
    </motion.div>
  ) : null;

/* -------- chat component -------- */
function LangChainChat({
  baseUrl       = "",
  initPath      = "/initialize",
  invokePath    = "/invoke",
  heartbeatMs   = 600_000,
  onBotMsg,
  minimized     = false,
}) {
  const [conversation, setConversation] = useState(null);
  const [messages,     setMessages]     = useState([]);
  const [input,        setInput]        = useState("");
  const [loading,      setLoading]      = useState(false);
  const [suggestions,  setSuggestions]  = useState([]);
  const [picked,       setPicked]       = useState(null);
  const [reviewURL,    setReviewURL]    = useState(null);

  const bottomRef = useRef(null);

  /* ---- session bootstrap + heartbeat ---- */
  useEffect(() => {
    if (conversation) return;
    fetch(baseUrl + initPath, { method: "POST" })
      .then((r) => r.json())
      .then(({ conversation_id }) => setConversation(conversation_id))
      .catch(console.error);
  }, [conversation, baseUrl, initPath]);

  useEffect(() => {
    if (!conversation) return;
    const id = setInterval(
      () =>
        fetch(baseUrl + invokePath, {
          method : "POST",
          headers: { "Content-Type": "application/json", "X-Conversation-ID": conversation },
          body   : '{"user_message":"__ping__"}',
        }).catch(() => {}),
      heartbeatMs,
    );
    return () => clearInterval(id);
  }, [conversation, baseUrl, invokePath, heartbeatMs]);

  /* ---- scroll helpers ---- */
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, suggestions]);
  useEffect(() => { if (!minimized) bottomRef.current?.scrollIntoView({ behavior: "smooth" }); },
            [minimized]);

  /* ---- helpers ---- */
  const addMsg = (role, content) => setMessages((m) => [...m, { role, content }]);

  const send = useCallback(async (txt, label = txt) => {
    const body = txt.trim();
    if (!body || !conversation) return;

    setInput("");          /* clear field */
    setSuggestions([]);    /* hide quick replies */
    addMsg("user", label); /* echo */
    setLoading(true);

    try {
      const r    = await fetch(baseUrl + invokePath, {
        method : "POST",
        headers: { "Content-Type": "application/json", "X-Conversation-ID": conversation },
        body   : JSON.stringify({ user_message: body }),
      });
      const data = await r.json();

      if (data.review_cart_url) setReviewURL(data.review_cart_url);

      /* candidate plans? => quick-reply pills */
      if (Array.isArray(data.ai_response)) {
        const opts = data.ai_response.map((p) => {
          const name  = p.name || p.displayName || p.planName || "Unnamed plan";
          const price = typeof p.price === "number"
                        ? p.price.toFixed(2)
                        : p.price?.amount ?? p.price?.value ?? "";
          return { label: price ? `${name} – $${price}` : name,
                   value: p.id ?? p.offerFamilyId ?? p.value ?? name };
        });
        setPicked(null);
        setSuggestions(opts);
        return;
      }

      /* plain response */
      const bot = typeof data.ai_response === "string"
                  ? data.ai_response
                  : JSON.stringify(data.ai_response, null, 2);
      if (bot) {
        addMsg("ai", bot);
        onBotMsg?.();
      }
    } catch (e) {
      addMsg("ai", `Request failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [conversation, baseUrl, invokePath, onBotMsg]);

  const disabled = loading || suggestions.length > 0;

  return (
    <div className="flex flex-col h-full">
      {/* -------- scrollable message list -------- */}
      <div
        className="flex-1 overflow-y-auto overscroll-contain
                   scrollbar-thin scrollbar-thumb-magenta/70 scrollbar-track-transparent
                   space-y-3 pr-1"
      >
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "rounded-2xl p-3 shadow text-[13px] leading-snug break-words",
              m.role === "user" ? "bg-magenta/10 self-end" : "bg-white text-black",
            )}
            dangerouslySetInnerHTML={{
              __html: String(m.content).replace(
                /(https?:\/\/[^\s]+)/g,
                (url) => `<a class="text-magenta-dark underline" target="_blank" href="${url}">${url}</a>`,
              ),
            }}
          />
        ))}

        {loading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                      className="italic text-[13px] text-magenta-dark">
            thinking…
          </motion.div>
        )}

        <QuickReplies
          options={suggestions}
          picked={picked}
          onPick={(o) => { setPicked(o.value); send(o.value, o.label); }}
        />

        {reviewURL && (
          <Button
            onClick={() => window.open(reviewURL, "_blank", "noopener,noreferrer")}
            className="mt-4 px-5 py-2 rounded-full self-center text-[14px] font-semibold"
          >
            Review Cart
          </Button>
        )}

        <div ref={bottomRef} />
      </div>

      {/* -------- input row -------- */}
      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="flex gap-2 pt-3 shrink-0"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter service address…"
          disabled={disabled}
        />
        <Button type="submit" disabled={disabled} className="px-3 py-[6px] flex items-center justify-center">
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
}

/* -------- wrapper with minimise -------- */
export default function TMobileChatWidget() {
  const [open,      setOpen]      = useState(false);
  const [unread,    setUnread]    = useState(0);
  const [minimized, setMinimized] = useState(false);

  useEffect(() => { if (open) setUnread(0); }, [open]);
  const bumpUnread = () => !open && setUnread((u) => u + 1);

  const Logo = () => (
    <img
      src="https://www.t-mobile.com/content/dam/t-mobile/ntm/branding/logos/corporate/tmo-logo-v4.svg"
      alt="T-Mobile"
      className="w-6 h-6 rounded bg-white p-[2px] object-contain shrink-0"
    />
  );

  return (
    <>
      {/* launcher bubble */}
      <AnimatePresence>
        {!open && (
          <motion.button
            key="bubble"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300 }}
            onClick={() => { setOpen(true); setMinimized(false); }}
            className="fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 pl-3 pr-4 py-1.5
                       rounded-full shadow-xl bg-gradient-to-r from-magenta to-magenta-dark text-white"
          >
            {unread > 0 && (
              <span className="absolute -top-1 -left-1 text-[11px] font-bold bg-red-600 rounded-full w-5 h-5 flex items-center justify-center">
                {unread}
              </span>
            )}
            <span className="text-2xl">👩‍💼</span>
            <span className="font-semibold text-[14px]">Need Internet? 💬</span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.8, y: 50 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 50 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
            className={cn(
              "fixed bottom-6 right-6 z-50 w-[22rem] flex flex-col",
              minimized ? "h-[3.25rem]" : "h-[40vh]",
            )}
          >
            <Card className="w-full h-full overflow-hidden">
              {/* header */}
              <div className="flex items-center justify-between px-4 py-2
                              bg-gradient-to-r from-magenta to-magenta-dark text-white">
                <div className="flex items-center gap-2 text-[15px] font-semibold">
                  <Logo /> Hello, let’s chat!
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setMinimized((m) => !m)}
                    className="p-1 rounded-full hover:bg-white/20 focus:outline-none"
                    aria-label={minimized ? "Restore chat" : "Minimize chat"}
                  >
                    {minimized ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>

                  <button
                    onClick={() => setOpen(false)}
                    className="p-1 rounded-full hover:bg-white/20 focus:outline-none"
                    aria-label="Close chat"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* body */}
              <div
                className={cn(
                  "flex-1 min-h-0 bg-gradient-to-br from-magenta/5 to-white/70 flex flex-col",
                  "transition-[max-height,padding] duration-200 ease-out",
                  minimized ? "max-h-0 p-0 overflow-hidden" : "max-h-[1000px] p-4"
                )}
              >
                <LangChainChat minimized={minimized} onBotMsg={bumpUnread} />
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
