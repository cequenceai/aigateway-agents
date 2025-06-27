import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Send } from "lucide-react";

/* -------------------------------------------------- *
 *  Tiny helper components (inline-only)
 * -------------------------------------------------- */
const Card = ({ children, className = "" }) => (
  <div className={`rounded-2xl shadow bg-gradient-to-br from-magenta to-magenta-dark/80 ${className}`}>{children}</div>
);
const CardHeader = ({ children, className = "" }) => (
  <div className="p-4 font-semibold text-xl tracking-wide text-white">{children}</div>
);
const CardContent = ({ children, className = "" }) => (
  <div className={`p-4 bg-white/90 text-black rounded-b-2xl ${className}`}>{children}</div>
);
const Input = (props) => (
  <input {...props} className="border-2 border-magenta-dark rounded p-2 w-full text-black placeholder:text-magenta-dark/50 focus:ring-2 focus:ring-magenta outline-none" />
);
const Button = ({ children, className = "", ...rest }) => (
  <button {...rest} className={`bg-magenta hover:bg-magenta-dark focus:ring-4 focus:ring-magenta/40 text-white rounded px-4 py-2 disabled:opacity-50 transition ${className}`}>{children}</button>
);

/* -------------------  Chat component  ------------------- */
export default function LangChainChat({
  baseUrl = "",                    // Vite dev-proxy takes care of CORS
  mcpUrl = "https://ztaib-jpuw2rb1-e4l2dawa5a-uc.a.run.app/mcp",
  initPath = "/initialize",
  invokePath = "/invoke",
  heartbeatMs = 3600_000,           // 10 min
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [initError, setInitError] = useState(null);
  const bottomRef = useRef(null);

  /* 1️⃣  Get conversationId once --------------------------------------- */
  useEffect(() => {
    if (conversationId) return;
    (async () => {
      try {
        const r = await fetch(baseUrl + initPath, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mcp_url: mcpUrl }),
        });
        const { conversation_id } = await r.json();
        conversation_id ? setConversationId(conversation_id) : setInitError("Init: no conversation_id");
      } catch (err) {
        setInitError(`Init failed: ${err}`);
      }
    })();
  }, [conversationId, baseUrl, initPath, mcpUrl]);

  /* 2️⃣  Heartbeat every 10 min --------------------------------------- */
  useEffect(() => {
    if (!conversationId) return;               // wait for id
    const id = setInterval(async () => {
      try {
        await fetch(baseUrl + invokePath, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Conversation-ID": conversationId,
          },
          body: JSON.stringify({ user_message: "__ping__" }),
        });
      } catch (err) {
        // silent fail – heartbeat is best-effort
        console.warn("heartbeat failed", err);
      }
    }, heartbeatMs);

    return () => clearInterval(id);            // cleanup on unmount
  }, [conversationId, baseUrl, invokePath, heartbeatMs]);

  /* 3️⃣  Auto-scroll --------------------------------------------------- */
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  /* 4️⃣  Send a user message ------------------------------------------ */
  const sendMessage = async () => {
    const msg = input.trim();
    if (!msg || !conversationId) return;

    setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setLoading(true);

    try {
      const r = await fetch(baseUrl + invokePath, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Conversation-ID": conversationId,
        },
        body: JSON.stringify({ user_message: msg }),
      });
      const { ai_response } = await r.json();
      setMessages((m) => [...m, { role: "ai", content: ai_response ?? "Error: no ai_response" }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "ai", content: `Request failed: ${err}` }]);
    } finally {
      setLoading(false);
    }
  };

  /* -------------------  UI ----------------------------- */
  return (
    <Card className="max-w-2xl mx-auto h-[90vh] flex flex-col mt-8">
      <CardHeader>T-Mobile Home Internet AI BOT</CardHeader>

      <CardContent className="flex-1 overflow-y-auto space-y-4">
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-2xl p-3 shadow text-sm whitespace-pre-wrap ${m.role === "user" ? "bg-magenta/10 self-end" : "bg-white"}`}
          >
            {m.content}
          </motion.div>
        ))}

        {loading && (
          <motion.div className="italic text-sm text-magenta-dark" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            thinking…
          </motion.div>
        )}

        {initError && <div className="text-xs text-red-600">{initError}</div>}
        <div ref={bottomRef} />
      </CardContent>

      <form onSubmit={(e) => { e.preventDefault(); sendMessage(); }} className="p-4 border-t flex gap-2 bg-white/90 rounded-b-2xl">
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder={conversationId ? "Ask the LLM…" : "initialising…"} />
        <Button disabled={loading || !conversationId}>
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </Card>
  );
}
