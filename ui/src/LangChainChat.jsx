/* --------------------------------------------------------------------
   LangChainChat.jsx   – controlled UI for the T‑Mobile Home‑Internet bot
   ------------------------------------------------------------------ */
import { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Send } from "lucide-react";

/* ﹡ tiny Tailwind‑ish helper ﹡ */
const cn = (...c) => c.filter(Boolean).join(" ");

/* ─────────────── generic styled atoms ─────────────── */
const Card   = ({children,className=""}) => <div className={cn("rounded-2xl shadow bg-gradient-to-br from-magenta to-magenta-dark/80",className)}>{children}</div>;
const CardHeader  = ({children,className=""}) => <div className={cn("p-4 font-semibold text-xl tracking-wide text-white",className)}>{children}</div>;
const CardContent = ({children,className=""}) => <div className={cn("p-4 bg-white/90 text-black rounded-b-2xl",className)}>{children}</div>;
const Input  = ({className="",...r}) => <input {...r} className={cn("border-2 border-magenta-dark rounded p-2 w-full text-black placeholder:text-magenta-dark/50 focus:ring-2 focus:ring-magenta outline-none disabled:opacity-50",className)} />;
const Button = ({children,className="",...r}) => <button {...r} className={cn("bg-magenta hover:bg-magenta-dark focus:ring-4 focus:ring-magenta/40 text-white rounded px-4 py-2 transition disabled:opacity-50 disabled:pointer-events-none",className)}>{children}</button>;

/* ─────────────── quick‑reply row ─────────────── */
const QuickReplies = ({options=[], onPick}) => (
  options.length ? (
    <motion.div layout initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} className="flex flex-wrap gap-2 mt-2">
      {options.map(o => <Button key={o.value} onClick={()=>onPick(o.value)}>{o.label}</Button>)}
    </motion.div>
  ) : null
);

/* ─────────────── main chat component ─────────────── */
export default function LangChainChat({
  baseUrl="",                     // dev proxy handles CORS
  mcpUrl="https://ztaib-jpuw2rb1-e4l2dawa5a-uc.a.run.app/mcp",
  initPath="/initialize",
  invokePath="/invoke",
  heartbeatMs=600_000
}) {
  const [conversation,setConversation] = useState(null); // id
  const [messages,setMessages]         = useState([]);   // { role, content }
  const [input,setInput]               = useState("");
  const [loading,setLoading]           = useState(false);
  const [suggestions,setSuggestions]   = useState([]);   // quick‑reply buttons
  const [initErr,setInitErr]           = useState(null);

  const bottomRef = useRef(null);

  /* ① start session */
  useEffect(() => {
    if (conversation) return;
    (async () => {
      try {
        const r = await fetch(baseUrl+initPath,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mcp_url:mcpUrl})});
        const { conversation_id } = await r.json();
        conversation_id ? setConversation(conversation_id)
                        : setInitErr("init: no conversation_id");
      } catch (e){ setInitErr("init failed: "+e); }
    })();
  }, [conversation, baseUrl, initPath, mcpUrl]);

  /* ② heartbeat */
  useEffect(() => {
    if (!conversation) return;
    const id = setInterval(()=>{ fetch(baseUrl+invokePath,{method:"POST",headers:{"Content-Type":"application/json","X-Conversation-ID":conversation},body:'{"user_message":"__ping__"}'}).catch(()=>{}); }, heartbeatMs);
    return () => clearInterval(id);
  }, [conversation, baseUrl, invokePath, heartbeatMs]);

  /* autoscroll */
  useEffect(()=> bottomRef.current?.scrollIntoView({behavior:"smooth"}),[messages,suggestions]);

  /* ③ send helper */
  const sendMessage = useCallback(async (raw) =>{
    const txt = raw.trim();
    if (!txt || !conversation) return;

    setInput("");
    setSuggestions([]);                 // hide any old buttons
    setMessages(m=>[...m,{role:"user",content:txt}]);
    setLoading(true);

    try{
      const r = await fetch(baseUrl+invokePath,{
        method:"POST",
        headers:{"Content-Type":"application/json","X-Conversation-ID":conversation},
        body:JSON.stringify({user_message:txt})
      });
      const { ai_response } = await r.json();

      /* case A – plans array */
      if (Array.isArray(ai_response)){
        // build quick‑reply buttons only (no text bubble)
        setSuggestions(ai_response.map(p=>({label:`${p.name} – $${p.price}`,value:p.name})));
      }
      /* case B – plain text / object */
      else{
        const content = typeof ai_response==="string"
                      ? ai_response
                      : JSON.stringify(ai_response,null,2);
        setMessages(m=>[...m,{role:"ai",content}]);
      }
    }catch(e){
      setMessages(m=>[...m,{role:"ai",content:`Request failed: ${e}`}]);
    }finally{ setLoading(false); }
  },[conversation, baseUrl, invokePath]);

  /* ─────────────── UI ─────────────── */
  const inputDisabled = loading || !conversation || suggestions.length>0;

  return(
    <Card className="max-w-2xl mx-auto h-[90vh] flex flex-col mt-8">
      <CardHeader>T‑Mobile Home Internet AI BOT</CardHeader>

      <CardContent className="flex-1 overflow-y-auto space-y-4">
        {messages.map((m,i)=>(
          <motion.div key={i} initial={{opacity:0,y:10}} animate={{opacity:1,y:0}}
              className={cn("rounded-2xl p-3 shadow text-sm whitespace-pre-wrap",
                            m.role==="user"?"bg-magenta/10 self-end":"bg-white")}>
            {m.content}
          </motion.div>
        ))}

        {loading && <motion.div initial={{opacity:0}} animate={{opacity:1}} className="italic text-sm text-magenta-dark">thinking…</motion.div>}

        <QuickReplies options={suggestions} onPick={val=>sendMessage(val)} />

        {initErr && <div className="text-xs text-red-600">{initErr}</div>}
        <div ref={bottomRef}/>
      </CardContent>

      {/* input row – disabled when quick replies are up */}
      <form onSubmit={e=>{e.preventDefault(); sendMessage(input);}}
            className="p-4 border-t flex gap-2 bg-white/90 rounded-b-2xl">
        <Input value={input}
               onChange={e=>setInput(e.target.value)}
               placeholder={conversation?"Type address here…":"initialising…"}
               disabled={inputDisabled}/>
        <Button type="submit" disabled={inputDisabled}>
          <Send className="w-4 h-4"/>
        </Button>
      </form>
    </Card>
  );
}
