import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = "http://127.0.0.1:8000";
const USER_ID = (() => {
  let id = sessionStorage.getItem("docassist_user");
  if (!id) { id = "user_" + Math.random().toString(36).slice(2, 10); sessionStorage.setItem("docassist_user", id); }
  return id;
})();

const INTENT_META = {
  question:      { icon: "?",  label: "Question",     color: "#60a5fa", bg: "rgba(96,165,250,0.12)"  },
  complaint:     { icon: "!",  label: "Complaint",    color: "#f87171", bg: "rgba(248,113,113,0.12)" },
  request:       { icon: "→",  label: "Request",      color: "#a78bfa", bg: "rgba(167,139,250,0.12)" },
  feedback:      { icon: "♦",  label: "Feedback",     color: "#34d399", bg: "rgba(52,211,153,0.12)"  },
  check_status:  { icon: "◎",  label: "Status Check", color: "#fbbf24", bg: "rgba(251,191,36,0.12)"  },
  general_query: { icon: "✦",  label: "General",      color: "#94a3b8", bg: "rgba(148,163,184,0.12)" },
  unknown:       { icon: "~",  label: "Unknown",      color: "#64748b", bg: "rgba(100,116,139,0.12)" },
};

// const INTENT_META = {
//   question:      { icon: "❓", label: "Question",     color: "#60a5fa", bg: "rgba(96,165,250,0.12)"  },
//   complaint:     { icon: "⚠️", label: "Complaint",    color: "#f87171", bg: "rgba(248,113,113,0.12)" },
//   request:       { icon: "📋", label: "Request",      color: "#a78bfa", bg: "rgba(167,139,250,0.12)" },
//   feedback:      { icon: "💬", label: "Feedback",     color: "#34d399", bg: "rgba(52,211,153,0.12)"  },
//   check_status:  { icon: "🔍", label: "Status Check", color: "#fbbf24", bg: "rgba(251,191,36,0.12)"  },
//   general_query: { icon: "💡", label: "General",      color: "#94a3b8", bg: "rgba(148,163,184,0.12)" },
//   unknown:       { icon: "🤔", label: "Unknown",      color: "#64748b", bg: "rgba(100,116,139,0.12)" },
// };

// const EMOTION_META = {
//   happy:      { icon: "◡", label: "Happy",      color: "#34d399", bg: "rgba(52,211,153,0.12)"  },
//   neutral:    { icon: "—", label: "Neutral",    color: "#94a3b8", bg: "rgba(148,163,184,0.12)" },
//   frustrated: { icon: "≈", label: "Frustrated", color: "#fbbf24", bg: "rgba(251,191,36,0.12)"  },
//   angry:      { icon: "↯", label: "Angry",      color: "#f87171", bg: "rgba(248,113,113,0.12)" },
// };

const EMOTION_META = {
  happy:      { icon: "😊", label: "Happy",      color: "#34d399", bg: "rgba(52,211,153,0.12)"  },
  neutral:    { icon: "😐", label: "Neutral",    color: "#94a3b8", bg: "rgba(148,163,184,0.12)" },
  frustrated: { icon: "😤", label: "Frustrated", color: "#fbbf24", bg: "rgba(251,191,36,0.12)"  },
  angry:      { icon: "😠", label: "Angry",      color: "#f87171", bg: "rgba(248,113,113,0.12)" },
};

const TONE_META = {
  formal:     { label: "Formal",     color: "#60a5fa", bg: "rgba(96,165,250,0.1)"  },
  empathetic: { label: "Empathetic", color: "#a78bfa", bg: "rgba(167,139,250,0.1)" },
  apologetic: { label: "Apologetic", color: "#f87171", bg: "rgba(248,113,113,0.1)" },
  friendly:   { label: "Friendly",   color: "#34d399", bg: "rgba(52,211,153,0.1)"  },
  urgent:     { label: "Urgent",     color: "#fbbf24", bg: "rgba(251,191,36,0.1)"  },
};

const S = {
  app: { display:"flex", flexDirection:"column", height:"100vh", background:"#0f0f11", color:"#e2e8f0", fontFamily:"'DM Sans',system-ui,sans-serif", overflow:"hidden" },
  header: { display:"flex", alignItems:"center", justifyContent:"space-between", padding:"10px 20px", borderBottom:"1px solid rgba(255,255,255,0.07)", background:"rgba(15,15,17,0.97)", flexShrink:0 },
  logo: { display:"flex", alignItems:"center", gap:10 },
  logoIcon: { width:28, height:28, borderRadius:8, background:"linear-gradient(135deg,#7c3aed,#2563eb)", display:"flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:12, color:"#fff" },
  logoText: { fontWeight:600, fontSize:14 },
  logoSub: { color:"#334155", fontWeight:400 },
  tabBar: { display:"flex", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.08)", borderRadius:10, padding:3, gap:2 },
  tab: (active) => ({ padding:"5px 14px", borderRadius:8, fontSize:12, fontWeight:500, cursor:"pointer", border:"none", transition:"all 0.2s", background: active ? "rgba(255,255,255,0.1)" : "transparent", color: active ? "#e2e8f0" : "#475569" }),
  body: { display:"flex", flex:1, minHeight:0 },
  sidebar: { width:240, display:"flex", flexDirection:"column", background:"#0c0c0e", borderRight:"1px solid rgba(255,255,255,0.07)", flexShrink:0 },
  sidebarTop: { padding:"14px 14px 12px", borderBottom:"1px solid rgba(255,255,255,0.07)" },
  sidebarLabel: { fontSize:10, fontFamily:"'DM Mono',monospace", color:"#475569", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:10 },
  dropZone: (drag) => ({ border:`1.5px dashed ${drag?"#60a5fa":"rgba(255,255,255,0.12)"}`, background: drag?"rgba(96,165,250,0.06)":"rgba(255,255,255,0.02)", borderRadius:12, padding:"14px 10px", textAlign:"center", cursor:"pointer", transition:"all 0.2s" }),
  dropIcon: { fontSize:20, marginBottom:4, color:"#475569" },
  dropText: { fontSize:12, color:"#475569", margin:0 },
  dropSub: { fontSize:11, color:"#334155", fontFamily:"'DM Mono',monospace", marginTop:2 },
  docList: { flex:1, overflowY:"auto", padding:"10px 10px" },
  docItem: { background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:8, padding:"8px 10px", marginBottom:6, display:"flex", justifyContent:"space-between", alignItems:"flex-start" },
  docName: { fontSize:12, color:"#cbd5e1", fontWeight:500, wordBreak:"break-word", flex:1 },
  docChunks: { fontSize:11, color:"#475569", fontFamily:"'DM Mono',monospace", marginTop:2 },
  docDel: { background:"none", border:"none", color:"#334155", cursor:"pointer", fontSize:12, padding:"0 0 0 6px", flexShrink:0 },
  pipeline: { padding:"12px 14px", borderTop:"1px solid rgba(255,255,255,0.07)" },
  pipeLabel: { fontSize:10, fontFamily:"'DM Mono',monospace", color:"#334155", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:8 },
  pipeRow: { display:"flex", alignItems:"center", gap:8, marginBottom:5 },
  pipeDot: (c) => ({ width:6, height:6, borderRadius:"50%", background:c, flexShrink:0 }),
  pipeText: { fontSize:11, color:"#475569" },
  main: { flex:1, display:"flex", flexDirection:"column", minWidth:0 },
  messages: { flex:1, overflowY:"auto", padding:"20px 20px 10px" },
  sessionBar: { display:"flex", alignItems:"center", justifyContent:"space-between", padding:"7px 20px", borderBottom:"1px solid rgba(255,255,255,0.06)", background:"rgba(0,0,0,0.2)", flexShrink:0 },
  sessionDot: (active) => ({ width:7, height:7, borderRadius:"50%", background: active?"#34d399":"#334155", boxShadow: active?"0 0 6px #34d399":"none", transition:"all 0.3s", marginRight:8 }),
  sessionText: { fontSize:11, color:"#475569", fontFamily:"'DM Mono',monospace" },
  resetBtn: { background:"none", border:"none", color:"#334155", cursor:"pointer", fontSize:11, fontFamily:"'DM Mono',monospace" },
  scenarios: { display:"flex", flexWrap:"wrap", gap:8, padding:"10px 20px", borderBottom:"1px solid rgba(255,255,255,0.05)" },
  scenLabel: { fontSize:10, color:"#334155", fontFamily:"'DM Mono',monospace", letterSpacing:"0.06em", textTransform:"uppercase", width:"100%", marginBottom:2 },
  scenBtn: { fontSize:11, color:"#94a3b8", background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.08)", borderRadius:20, padding:"5px 12px", cursor:"pointer", fontFamily:"'DM Mono',monospace" },
  quickLabel: { fontSize:10, color:"#334155", fontFamily:"'DM Mono',monospace", letterSpacing:"0.06em", textTransform:"uppercase", marginBottom:6 },
  quickWrap: { padding:"8px 20px 12px" },
  quickBtn: { fontSize:12, color:"#64748b", background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.08)", borderRadius:20, padding:"5px 12px", cursor:"pointer", marginRight:6, marginBottom:4 },
  inputBar: { display:"flex", gap:10, padding:"14px 16px", borderTop:"1px solid rgba(255,255,255,0.07)", background:"rgba(0,0,0,0.25)", flexShrink:0 },
  input: { flex:1, background:"rgba(255,255,255,0.05)", border:"1px solid rgba(255,255,255,0.1)", borderRadius:12, padding:"10px 16px", fontSize:13, color:"#e2e8f0", outline:"none", fontFamily:"'DM Sans',system-ui,sans-serif" },
  sendBtn: (active) => ({ width:40, height:40, borderRadius:12, border:"none", cursor: active?"pointer":"not-allowed", fontSize:16, color:"#fff", display:"flex", alignItems:"center", justifyContent:"center", transition:"all 0.2s", flexShrink:0 }),
  msgWrap: (user) => ({ display:"flex", flexDirection: user?"row-reverse":"row", gap:10, marginBottom:20, alignItems:"flex-start" }),
  avatar: (g) => ({ width:28, height:28, borderRadius:8, background:g, display:"flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:11, color:"#fff", flexShrink:0, boxShadow:"0 2px 8px rgba(0,0,0,0.3)" }),
  msgInner: { flex:1, maxWidth:"78%" },
  metaRow: { display:"flex", flexWrap:"wrap", gap:6, marginBottom:6 },
  pill: (color,bg) => ({ display:"inline-flex", alignItems:"center", gap:4, padding:"2px 8px", borderRadius:20, fontSize:11, fontWeight:500, color, background:bg, border:`1px solid ${color}28`, fontFamily:"'DM Mono',monospace" }),
  bubble: (user) => ({ background: user?"rgba(96,165,250,0.1)":"rgba(255,255,255,0.04)", border: user?"1px solid rgba(96,165,250,0.2)":"1px solid rgba(255,255,255,0.08)", borderRadius:16, borderTopRightRadius: user?4:16, borderTopLeftRadius: user?16:4, padding:"10px 14px" }),
  bubbleGreen: { background:"rgba(52,211,153,0.08)", border:"1px solid rgba(52,211,153,0.15)", borderRadius:16, borderTopRightRadius:4, padding:"10px 14px" },
  msgText: { fontSize:13, lineHeight:1.6, color:"#cbd5e1", margin:0 },
  srcToggle: { fontSize:11, color:"#475569", background:"none", border:"none", cursor:"pointer", padding:"4px 0", marginTop:4, fontFamily:"'DM Mono',monospace" },
  srcItem: { background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:8, marginTop:4, overflow:"hidden" },
  srcHeader: { display:"flex", justifyContent:"space-between", alignItems:"center", padding:"6px 10px", cursor:"pointer", background:"none", border:"none", width:"100%", textAlign:"left" },
  srcFilename: { fontSize:11, color:"#60a5fa", fontFamily:"'DM Mono',monospace" },
  srcBar: { display:"flex", alignItems:"center", gap:6 },
  srcTrack: { width:50, height:3, background:"rgba(255,255,255,0.08)", borderRadius:4, overflow:"hidden" },
  srcContent: { fontSize:11, color:"#475569", padding:"6px 10px", borderTop:"1px solid rgba(255,255,255,0.06)", lineHeight:1.6 },
  dots: { display:"flex", gap:5, padding:"12px 14px" },
  dot: { width:6, height:6, borderRadius:"50%", background:"#475569" },
  noDoc: { fontSize:12, color:"#334155", textAlign:"center", padding:"20px 0" },
  versionText: { fontSize:11, color:"#1e293b", fontFamily:"'DM Mono',monospace" },
};

function Pill({ color, bg, icon, label }) {
  return <span style={S.pill(color,bg)}><span>{icon}</span>{label}</span>;
}

function TypingDots() {
  return (
    <div style={S.dots}>
      {[0,1,2].map(i=>(
        <span key={i} style={{...S.dot, animation:`bounce 1s ${i*0.18}s infinite`}}/>
      ))}
    </div>
  );
}

function MsgText({ text }) {
  const html = text
    .replace(/\*\*(.+?)\*\*/g,"<strong style='color:#e2e8f0'>$1</strong>")
    .replace(/`(.+?)`/g,"<code style='background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:4px;font-size:0.85em;font-family:DM Mono,monospace'>$1</code>")
    .replace(/\n/g,"<br/>");
  return <p style={S.msgText} dangerouslySetInnerHTML={{__html:html}}/>;
}

function SourceChunk({ chunk, index }) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(chunk.score * 100);
  const barColor = pct > 80 ? "#34d399" : pct > 60 ? "#fbbf24" : "#94a3b8";
  return (
    <div style={S.srcItem}>
      <button style={S.srcHeader} onClick={()=>setOpen(o=>!o)}>
        <span style={S.srcFilename}>[{index+1}] {chunk.filename}{chunk.page?` · p${chunk.page}`:""}</span>
        <div style={S.srcBar}>
          <div style={S.srcTrack}><div style={{width:`${pct}%`,height:"100%",background:barColor,borderRadius:4}}/></div>
          <span style={{fontSize:10,color:"#475569",fontFamily:"'DM Mono',monospace"}}>{pct}%</span>
          <span style={{fontSize:10,color:"#475569"}}>{open?"▴":"▾"}</span>
        </div>
      </button>
      {open && <div style={S.srcContent}>{chunk.content}</div>}
    </div>
  );
}

function RagMsg({ msg }) {
  const [showSrc, setShowSrc] = useState(false);
  if (msg.role==="user") return (
    <div style={S.msgWrap(true)}>
      <div style={S.avatar("linear-gradient(135deg,#1d4ed8,#7c3aed)")}>U</div>
      <div style={S.msgInner}><div style={S.bubble(true)}><MsgText text={msg.content}/></div></div>
    </div>
  );
  const intent = INTENT_META[msg.meta?.intent?.intent] || INTENT_META.unknown;
  const emotion = EMOTION_META[msg.meta?.emotion?.emotion] || EMOTION_META.neutral;
  const tone = TONE_META[msg.meta?.response_tone] || TONE_META.formal;
  return (
    <div style={S.msgWrap(false)}>
      <div style={S.avatar("linear-gradient(135deg,#7c3aed,#2563eb)")}>D</div>
      <div style={S.msgInner}>
        {msg.meta && (
          <div style={S.metaRow}>
            <Pill color={tone.color} bg={tone.bg} icon="◈" label={tone.label}/>
            <Pill {...intent}/>
            <Pill {...emotion}/>
            {msg.meta.latency_ms && <span style={{fontSize:10,color:"#334155",fontFamily:"'DM Mono',monospace"}}>{msg.meta.latency_ms}ms</span>}
          </div>
        )}
        <div style={S.bubble(false)}><MsgText text={msg.content}/></div>
        {msg.meta?.retrieved_chunks?.length > 0 && (
          <>
            <button style={S.srcToggle} onClick={()=>setShowSrc(s=>!s)}>
              {showSrc?"▴":"▾"} {msg.meta.retrieved_chunks.length} source{msg.meta.retrieved_chunks.length>1?"s":""}
              {msg.meta.fallback_triggered && <span style={{color:"#fbbf24",marginLeft:6}}>· no match</span>}
            </button>
            {showSrc && msg.meta.retrieved_chunks.map((c,i)=><SourceChunk key={c.chunk_id} chunk={c} index={i}/>)}
          </>
        )}
      </div>
    </div>
  );
}

function ChatMsg({ msg }) {
  if (msg.role==="user") return (
    <div style={S.msgWrap(true)}>
      <div style={S.avatar("linear-gradient(135deg,#065f46,#0891b2)")}>U</div>
      <div style={S.msgInner}><div style={S.bubbleGreen}><MsgText text={msg.content}/></div></div>
    </div>
  );
  const intent = INTENT_META[msg.meta?.intent];
  const emotion = EMOTION_META[msg.meta?.emotion];
  return (
    <div style={S.msgWrap(false)}>
      <div style={S.avatar("linear-gradient(135deg,#059669,#0891b2)")}>V</div>
      <div style={S.msgInner}>
        {msg.meta && (
          <div style={S.metaRow}>
            {intent && <Pill {...intent}/>}
            {emotion && <Pill {...emotion}/>}
            {msg.meta.slots && Object.entries(msg.meta.slots).map(([k,v])=>(
              <span key={k} style={S.pill("#94a3b8","rgba(148,163,184,0.1)")}>{k.replace("_"," ")}: <strong style={{color:"#e2e8f0"}}>{v}</strong></span>
            ))}
            {msg.meta.context_switched && <span style={S.pill("#fbbf24","rgba(251,191,36,0.1)")}>↺ switched</span>}
            {msg.meta.escalate_to_agent && <span style={S.pill("#f87171","rgba(248,113,113,0.1)")}>● escalated</span>}
          </div>
        )}
        <div style={S.bubble(false)}><MsgText text={msg.content}/></div>
      </div>
    </div>
  );
}

function DocSidebar() {
  const [docs, setDocs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef();

  const fetchDocs = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/documents/${USER_ID}`);
      const d = await r.json();
      setDocs(d.documents || []);
    } catch {}
  }, []);

  useEffect(()=>{ fetchDocs(); },[fetchDocs]);

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    const tmp = { document_id:"up_"+Date.now(), filename:file.name, num_chunks:0, uploading:true };
    setDocs(d=>[...d,tmp]);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("user_id", USER_ID);
      const r = await fetch(`${API_BASE}/documents/upload`,{method:"POST",body:form});
      const data = await r.json();
      if (data.status==="success") await fetchDocs();
      else setDocs(d=>d.filter(x=>x.document_id!==tmp.document_id));
    } catch {
      setDocs(d=>d.filter(x=>x.document_id!==tmp.document_id));
    }
    setUploading(false);
  };

  const del = async (id) => {
    await fetch(`${API_BASE}/documents/${USER_ID}/${id}`,{method:"DELETE"}).catch(()=>{});
    setDocs(d=>d.filter(x=>x.document_id!==id));
  };

  return (
    <div style={S.sidebar}>
      <div style={S.sidebarTop}>
        <p style={S.sidebarLabel}>Documents</p>
        <div style={S.dropZone(dragging)}
          onDragOver={e=>{e.preventDefault();setDragging(true)}}
          onDragLeave={()=>setDragging(false)}
          onDrop={e=>{e.preventDefault();setDragging(false);upload(e.dataTransfer.files[0])}}
          onClick={()=>fileRef.current?.click()}>
          <div style={S.dropIcon}>{uploading?"⟳":"⊕"}</div>
          <p style={S.dropText}>{uploading?"Uploading…":"Drop or click to upload"}</p>
          <p style={S.dropSub}>pdf · docx · txt · md</p>
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.md,.csv" style={{display:"none"}}
            onChange={e=>upload(e.target.files[0])}/>
        </div>
      </div>

      <div style={S.docList}>
        {docs.length===0 && <p style={S.noDoc}>No documents yet</p>}
        {docs.map(doc=>(
          <div key={doc.document_id} style={S.docItem}>
            <div style={{flex:1,minWidth:0}}>
              <p style={S.docName}>{doc.filename}</p>
              <p style={S.docChunks}>{doc.uploading?"embedding…":`${doc.num_chunks} chunks`}</p>
            </div>
            {!doc.uploading && (
              <button style={S.docDel} onClick={()=>del(doc.document_id)}
                onMouseOver={e=>e.target.style.color="#f87171"}
                onMouseOut={e=>e.target.style.color="#334155"}>✕</button>
            )}
          </div>
        ))}
      </div>

      <div style={S.pipeline}>
        <p style={S.pipeLabel}>Pipeline</p>
        {[["#60a5fa","Extract text"],["#a78bfa","Chunk (512+64)"],["#34d399","Embed (ada-3)"],["#fbbf24","Store in ChromaDB"]].map(([c,t])=>(
          <div key={t} style={S.pipeRow}><div style={S.pipeDot(c)}/><span style={S.pipeText}>{t}</span></div>
        ))}
      </div>
    </div>
  );
}

function RagPanel() {
  const [msgs, setMsgs] = useState([{role:"assistant",content:"Upload a document and ask me anything. I'll detect your **intent** and **emotion** to craft the perfect response.",id:"w",meta:null}]);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const bottomRef = useRef();
  useEffect(()=>{ bottomRef.current?.scrollIntoView({behavior:"smooth"}); },[msgs,loading]);

  const send = async (q) => {
    const query = (q||input).trim(); if(!query||loading) return;
    setInput("");
    setMsgs(m=>[...m,{role:"user",content:query,id:Date.now()}]);
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/query`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,user_id:USER_ID})});
      const data = await r.json();
      setMsgs(m=>[...m,{role:"assistant",content:data.answer,meta:data,id:Date.now()+1}]);
    } catch {
      setMsgs(m=>[...m,{role:"assistant",content:"⚠️ Backend unreachable. Run: `uvicorn backend.main:app --port 8000`",id:Date.now()+1,meta:null}]);
    }
    setLoading(false);
  };

  const quick = ["What is your return policy?","This is ridiculous, my refund is still not processed","How many days does a refund take?"];
  const canSend = input.trim() && !loading;

  return (
    <div style={{display:"flex",flexDirection:"column",height:"100%"}}>
      <div style={{flex:1,overflowY:"auto",padding:"20px"}} ref={undefined}>
        {msgs.map(m=><RagMsg key={m.id} msg={m}/>)}
        {loading && (
          <div style={S.msgWrap(false)}>
            <div style={S.avatar("linear-gradient(135deg,#7c3aed,#2563eb)")}>D</div>
            <div style={S.bubble(false)}><TypingDots/></div>
          </div>
        )}
        <div ref={bottomRef}/>
      </div>
      {msgs.length<=2 && (
        <div style={S.quickWrap}>
          <p style={S.quickLabel}>Try these</p>
          {quick.map(q=><button key={q} style={S.quickBtn} onClick={()=>send(q)}
            onMouseOver={e=>e.target.style.color="#94a3b8"} onMouseOut={e=>e.target.style.color="#64748b"}>{q}</button>)}
        </div>
      )}
      <div style={S.inputBar}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()}
          placeholder="Ask about your documents…" style={S.input}
          onFocus={e=>e.target.style.borderColor="rgba(96,165,250,0.5)"}
          onBlur={e=>e.target.style.borderColor="rgba(255,255,255,0.1)"}/>
        <button onClick={()=>send()} disabled={!canSend}
          style={{...S.sendBtn(canSend), background: canSend?"#2563eb":"rgba(255,255,255,0.06)"}}>↑</button>
      </div>
    </div>
  );
}

function VoicePanel() {
  const [msgs, setMsgs] = useState([{role:"assistant",content:"Hi! I'm your VoiceBot. I handle **loan status**, **complaints**, and **general queries** with full multi-turn memory.",id:"w",meta:null}]);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [turnCount, setTurnCount] = useState(0);
  const bottomRef = useRef();
  useEffect(()=>{ bottomRef.current?.scrollIntoView({behavior:"smooth"}); },[msgs,loading]);

  const send = async (msg) => {
    const message = (msg||input).trim(); if(!message||loading) return;
    setInput("");
    setMsgs(m=>[...m,{role:"user",content:message,id:Date.now()}]);
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/chat`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message,user_id:USER_ID,session_id:sessionId})});
      const data = await r.json();
      if(!sessionId) setSessionId(data.session_id);
      setTurnCount(data.turn_count);
      setMsgs(m=>[...m,{role:"assistant",content:data.message,meta:data,id:Date.now()+1}]);
    } catch {
      setMsgs(m=>[...m,{role:"assistant",content:"⚠️ Backend unreachable.",id:Date.now()+1,meta:null}]);
    }
    setLoading(false);
  };

  const reset = async () => {
    if(sessionId) await fetch(`${API_BASE}/chat/${sessionId}`,{method:"DELETE"}).catch(()=>{});
    setSessionId(null); setTurnCount(0);
    setMsgs([{role:"assistant",content:"Session reset. How can I help you?",id:Date.now(),meta:null}]);
  };

  const runScenario = async (steps) => {
    reset();
    for(const step of steps){ await new Promise(r=>setTimeout(r,600)); await send(step); }
  };

  const canSend = input.trim() && !loading;
  const scenarios = [
    {label:"◎ Slot filling",    steps:["Check my loan status","12345"]},
    {label:"! Complaint flow",  steps:["I want to raise a complaint","Payment failed"]},
    {label:"↺ Context switch",  steps:["Check my loan status","Actually I want to raise complaint"]},
  ];

  return (
    <div style={{display:"flex",flexDirection:"column",height:"100%"}}>
      <div style={S.sessionBar}>
        <div style={{display:"flex",alignItems:"center"}}>
          <div style={S.sessionDot(!!sessionId)}/>
          <span style={S.sessionText}>{sessionId?`session active · turn ${turnCount}`:"no session"}</span>
        </div>
        <button style={S.resetBtn} onClick={reset}
          onMouseOver={e=>e.target.style.color="#94a3b8"} onMouseOut={e=>e.target.style.color="#334155"}>↺ reset</button>
      </div>
      {msgs.length<=2 && (
        <div style={S.scenarios}>
          <span style={S.scenLabel}>Scenarios</span>
          {scenarios.map(s=><button key={s.label} style={S.scenBtn} onClick={()=>runScenario(s.steps)}
            onMouseOver={e=>e.target.style.color="#e2e8f0"} onMouseOut={e=>e.target.style.color="#94a3b8"}>{s.label}</button>)}
        </div>
      )}
      <div style={{flex:1,overflowY:"auto",padding:"20px"}}>
        {msgs.map(m=><ChatMsg key={m.id} msg={m}/>)}
        {loading && (
          <div style={S.msgWrap(false)}>
            <div style={S.avatar("linear-gradient(135deg,#059669,#0891b2)")}>V</div>
            <div style={S.bubble(false)}><TypingDots/></div>
          </div>
        )}
        <div ref={bottomRef}/>
      </div>
      <div style={S.inputBar}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()}
          placeholder="Type your message…" style={S.input}
          onFocus={e=>e.target.style.borderColor="rgba(52,211,153,0.5)"}
          onBlur={e=>e.target.style.borderColor="rgba(255,255,255,0.1)"}/>
        <button onClick={()=>send()} disabled={!canSend}
          style={{...S.sendBtn(canSend), background: canSend?"#059669":"rgba(255,255,255,0.06)"}}>↑</button>
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("rag");
  return (
    <div style={S.app}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:4px}
        @keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
        button:focus{outline:none}
        input:focus{outline:none}
      `}</style>
      <header style={S.header}>
        <div style={S.logo}>
          <div style={S.logoIcon}>D</div>
          <span style={S.logoText}>DocAssist+ <span style={S.logoSub}>/ VoiceBot</span></span>
        </div>
        <div style={S.tabBar}>
          {[["rag","◈ DocAssist+"],["voice","◎ VoiceBot"]].map(([id,label])=>(
            <button key={id} style={S.tab(tab===id)} onClick={()=>setTab(id)}>{label}</button>
          ))}
        </div>
        <span style={S.versionText}>v1.0</span>
      </header>
      <div style={S.body}>
        {tab==="rag" && <DocSidebar/>}
        <main style={S.main}>
          {tab==="rag" ? <RagPanel/> : <VoicePanel/>}
        </main>
      </div>
    </div>
  );
}
