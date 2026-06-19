import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  MessageSquare, Plus, Send, Paperclip, Settings,
  Trash2, X, Edit2, Menu, Sparkles, Download, Upload,
  Folder, Archive, Brain, ChevronDown,
} from 'lucide-react';
import { streamChat } from './lib/streaming';
import { getOrCreateSessionId, resetSessionId } from './lib/session';
import ToolStatusCard from './components/ToolStatusCard';
import CsvRenderer from './components/CsvRenderer';
import ChartRenderer from './components/ChartRenderer';
import ImageRenderer from './components/ImageRenderer';
import WarningCard from './components/WarningCard';
import ResultFiles from './components/ResultFiles';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AVAILABLE_MODELS = [
  { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', desc: 'Fast, efficient, high free-tier quota.' },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', desc: 'Fast, efficient, low latency Gemini 2.5.' },
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', desc: 'Fast, efficient, low latency Gemini 2.0.' },
  { id: 'gemini-1.5-pro',   name: 'Gemini 1.5 Pro',   desc: 'High capacity for long documents.' },
];

const SUGGESTED_PROMPTS = [
  { label: "Analyze a flow network and detect community clusters",  hint: "Network Analysis" },
  { label: "Run coastal blue carbon preprocessing",                 hint: "CBC Preprocessor" },
  { label: "Calculate coastal carbon stock and sequestration",      hint: "Coastal Blue Carbon" },
  { label: "Estimate seasonal water yield and baseflow",            hint: "Seasonal Water Yield" },
  { label: "Estimate crop yield by percentile across 172 crops",    hint: "Crop Percentile" },
  { label: "Model crop yield from fertilizer rates (NPK)",          hint: "Crop Regression" },
];

// ---------------------------------------------------------------------------
// Message renderer — handles all SSE event types
// ---------------------------------------------------------------------------

// Collapsible "thinking" block (Claude Desktop style): shows a pulsing
// "Thinking…" header while the model reasons; click to expand the reasoning.
function ThinkingBlock({ content, done }) {
  const [open, setOpen] = useState(false);
  // Tidy the reasoning: drop fenced/inline code (no raw python), collapse blank
  // runs, trim — so it reads as clean prose rather than a code dump.
  const clean = (content || '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return (
    <div className="border border-gray-200 rounded-xl bg-gray-50/70 text-[13px]">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 w-full px-3 py-2 text-gray-500 hover:text-gray-700"
      >
        <Brain size={14} className={done ? '' : 'animate-pulse text-blue-500'} />
        <span className="font-medium">{done ? 'Thought process' : 'Thinking…'}</span>
        <ChevronDown size={14} className={`ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          className="px-3 pb-3 pt-1 text-gray-500 border-t border-gray-100 leading-relaxed overflow-y-auto markdown-body"
          style={{ maxHeight: '16rem' }}
        >
          <ReactMarkdown
            components={{
              p:      ({node, ...p}) => <p className="mb-1.5 last:mb-0" {...p} />,
              h1:     ({node, ...p}) => <p className="font-semibold text-gray-600 mt-2 mb-1" {...p} />,
              h2:     ({node, ...p}) => <p className="font-semibold text-gray-600 mt-2 mb-1" {...p} />,
              h3:     ({node, ...p}) => <p className="font-semibold text-gray-600 mt-2 mb-1" {...p} />,
              ul:     ({node, ...p}) => <ul className="list-disc pl-4 my-1 space-y-0.5" {...p} />,
              ol:     ({node, ...p}) => <ol className="list-decimal pl-4 my-1 space-y-0.5" {...p} />,
              strong: ({node, ...p}) => <strong className="font-semibold text-gray-600" {...p} />,
              code:   ({node, ...p}) => <span {...p} />,
              pre:    ({node, ...p}) => <div {...p} />,
            }}
          >{clean || '…'}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function MessageContent({ msg, sessionId }) {
  if (msg.role === 'user') {
    return (
      <div className="bg-[#f0f4f9] px-6 py-4 rounded-3xl max-w-[85%] ml-auto">
        {msg.file && (
          <div className="text-xs font-medium text-blue-600 mb-2 flex items-center gap-1">
            <Paperclip size={12} /> {msg.file}
          </div>
        )}
        <div className="whitespace-pre-wrap text-[15px]">{msg.content}</div>
      </div>
    );
  }

  return (
    <div className="flex gap-5 max-w-[90%]">
      <Sparkles size={24} className="text-blue-500 shrink-0 mt-1" />
      <div className="flex-1 space-y-3">
        {msg.blocks && msg.blocks.map((block, i) => {
          switch (block.type) {
            case 'thinking':
              return <ThinkingBlock key={i} content={block.content} done={block.done} />;
            case 'text':
              return (
                <div key={i} className="text-[15px] leading-relaxed markdown-body">
                  <ReactMarkdown
                    urlTransform={(url) => {
                      // Block inline base64 image data — the LLM occasionally
                      // hallucinates fake PNG bytes and tries to embed them via
                      // ![](data:image/png;base64,...). The real renders go
                      // through the render_spatial_file tool and are shown by
                      // ImageRenderer, not by markdown img.
                      if (typeof url === 'string' && url.startsWith('data:')) return '';
                      return url;
                    }}
                    components={{
                      h1: ({node, ...p}) => <h1 className="text-xl font-bold mt-3 mb-1" {...p} />,
                      h2: ({node, ...p}) => <h2 className="text-lg font-bold mt-3 mb-1" {...p} />,
                      h3: ({node, ...p}) => <h3 className="text-base font-semibold mt-2 mb-1" {...p} />,
                      strong: ({node, ...p}) => <strong className="font-semibold" {...p} />,
                      ul: ({node, ...p}) => <ul className="list-disc pl-5 my-1 space-y-0.5" {...p} />,
                      ol: ({node, ...p}) => <ol className="list-decimal pl-5 my-1 space-y-0.5" {...p} />,
                      li: ({node, ...p}) => <li className="leading-relaxed" {...p} />,
                      p: ({node, ...p}) => <p className="mb-2 last:mb-0" {...p} />,
                      pre: ({node, ...p}) => <pre className="bg-gray-100 p-2 rounded text-sm font-mono my-1 whitespace-pre-wrap overflow-x-auto" {...p} />,
                      code: ({node, ...p}) => <code className="bg-gray-100 px-1 rounded text-sm font-mono" {...p} />,
                      img: ({node, src, alt}) => {
                        // After urlTransform, fake inline images arrive with src=''.
                        // Replace them with a small explainer instead of a broken-image icon.
                        if (!src) {
                          return <span className="text-xs text-gray-400 italic">[inline image suppressed — please ask to render the map]</span>;
                        }
                        return <img src={src} alt={alt} className="max-w-full rounded" loading="lazy" />;
                      },
                    }}
                  >{block.content}</ReactMarkdown>
                </div>
              );
            case 'tool_status':
              return <ToolStatusCard key={i} tool={block.tool} message={block.message} progress={block.progress} />;
            case 'warning':
              return <WarningCard key={i} message={block.message} />;
            case 'csv_table':
              return <CsvRenderer key={i} filename={block.filename} rows={block.rows} columns={block.columns} />;
            case 'chart':
              return <ChartRenderer key={i} config={block.config} />;
            case 'image':
              return <ImageRenderer key={i} url={block.url} filename={block.filename} extent={block.extent} />;
            case 'file_download':
              return <ResultFiles key={i} files={block.files} sessionId={sessionId} />;
            default:
              return null;
          }
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Conversation export — assistant messages live in `blocks`, not `content`,
// so flatten each block (thinking + answer text + tool/file notes) to markdown.
// ---------------------------------------------------------------------------

function blockToMarkdown(b) {
  switch (b.type) {
    case 'thinking':      return `**🧠 Thought process**\n\n${(b.content || '').trim()}`;
    case 'text':          return b.content || '';
    case 'tool_status':   return `_[Tool ran: ${b.tool}]_`;
    case 'warning':       return `> ⚠️ ${b.message}`;
    case 'file_download':
      return `**Files:**\n` + (b.files || [])
        .map(f => `- ${f.filename}${f.url ? ` — ${f.url}` : ''}`).join('\n');
    case 'image':         return `_[Image: ${b.filename || ''}]_`;
    case 'csv_table':     return `_[Table: ${b.filename || ''}]_`;
    case 'chart':         return `_[Chart]_`;
    default:              return '';
  }
}

function messageToMarkdown(m) {
  if (m.role === 'user') return m.content || '';
  return (m.blocks || []).map(blockToMarkdown).filter(Boolean).join('\n\n');
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

function App() {
  const sessionId = useRef(getOrCreateSessionId());

  const [chats, setChats] = useState(() => {
    const saved = localStorage.getItem('csis_chats');
    const restored = saved ? JSON.parse(saved) : [];
    // Always open on a fresh empty chat; keep prior conversations as history
    // in the sidebar (Gemini/ChatGPT-style). Reuse an already-empty top chat
    // so we don't stack duplicate "New Chat" entries on every reload.
    const top = restored[0];
    if (top && (!top.messages || top.messages.length === 0)) {
      return restored;
    }
    const fresh = { id: `chat_${Date.now()}`, title: 'New Chat', messages: [] };
    return [fresh, ...restored];
  });
  const [activeId, setActiveId] = useState(chats[0].id);
  const [appSettings, setAppSettings] = useState(() => {
    const saved = localStorage.getItem('csis_settings');
    return saved ? JSON.parse(saved) : {
      selectedModel: 'gemini-2.5-flash',
      temperature: 0.7,
    };
  });

  const [input, setInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => window.innerWidth >= 768);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);  // {loaded, total, percent} | null
  const [editingId, setEditingId] = useState(null);
  const [tempTitle, setTempTitle] = useState('');

  const [isDragging, setIsDragging] = useState(false);

  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const currentChat = chats.find(c => c.id === activeId) || chats[0];

  useEffect(() => { localStorage.setItem('csis_chats', JSON.stringify(chats)); }, [chats]);
  useEffect(() => { localStorage.setItem('csis_settings', JSON.stringify(appSettings)); }, [appSettings]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [currentChat.messages]);

  // ---------------------------------------------------------------------------
  // State mutation helpers
  // ---------------------------------------------------------------------------

  const updateLastAssistantBlock = (chatId, updater) => {
    setChats(prev => prev.map(c => {
      if (c.id !== chatId) return c;
      const msgs = [...c.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = updater(last);
      }
      return { ...c, messages: msgs };
    }));
  };

  const appendTextBlock = (chatId, text) => {
    setChats(prev => prev.map(c => {
      if (c.id !== chatId) return c;
      const msgs = [...c.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = [...(last.blocks || [])];
        const lastBlock = blocks[blocks.length - 1];
        if (lastBlock && lastBlock.type === 'text') {
          blocks[blocks.length - 1] = { ...lastBlock, content: lastBlock.content + text };
        } else {
          blocks.push({ type: 'text', content: text });
        }
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...c, messages: msgs };
    }));
  };

  const appendBlock = (chatId, block) => {
    updateLastAssistantBlock(chatId, last => ({
      ...last,
      blocks: [...(last.blocks || []), block],
    }));
  };

  // Accumulate streamed thinking text into the trailing thinking block.
  const appendThinkingBlock = (chatId, text) => {
    updateLastAssistantBlock(chatId, last => {
      const blocks = [...(last.blocks || [])];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock && lastBlock.type === 'thinking' && !lastBlock.done) {
        blocks[blocks.length - 1] = { ...lastBlock, content: lastBlock.content + text };
      } else {
        blocks.push({ type: 'thinking', content: text, done: false });
      }
      return { ...last, blocks };
    });
  };

  // Mark thinking blocks finished (stops the pulse, relabels to "Thought process").
  const finalizeThinking = (chatId) => {
    updateLastAssistantBlock(chatId, last => ({
      ...last,
      blocks: (last.blocks || []).map(b => b.type === 'thinking' ? { ...b, done: true } : b),
    }));
  };

  const updateToolBlock = (chatId, taskId, updates) => {
    setChats(prev => prev.map(c => {
      if (c.id !== chatId) return c;
      const msgs = [...c.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = (last.blocks || []).map(b =>
          b.type === 'tool_status' && b.task_id === taskId ? { ...b, ...updates } : b
        );
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...c, messages: msgs };
    }));
  };

  // ---------------------------------------------------------------------------
  // Send handler
  // ---------------------------------------------------------------------------

  const handleSend = async (overrideMessage) => {
    const text = overrideMessage || input;
    if ((!text.trim() && selectedFiles.length === 0) || isLoading) return;

    const currentInput = text;
    const currentFiles = [...selectedFiles];
    const chatId = activeId;

    setInput('');
    setSelectedFiles([]);
    setIsLoading(true);

    const userMsg = {
      role: 'user',
      content: currentInput,
      file: currentFiles.length > 0 ? currentFiles.map(f => f.name).join(', ') : null,
    };
    setChats(prev => prev.map(c =>
      c.id === chatId
        ? {
            ...c,
            title: c.messages.length === 0 ? currentInput.substring(0, 30) : c.title,
            messages: [...c.messages, userMsg],
          }
        : c
    ));

    setChats(prev => prev.map(c =>
      c.id === chatId ? { ...c, messages: [...c.messages, { role: 'assistant', blocks: [] }] } : c
    ));

    try {
      await streamChat(
        currentInput,
        currentFiles,
        sessionId.current,
        appSettings.selectedModel,
        (event) => handleSSEEvent(chatId, event),
        { onUploadProgress: setUploadProgress },
      );
    } catch (err) {
      // Network errors are now handled silently inside streamChat (transparent
      // retry with backoff). If it still throws here, it's already past the
      // "warm up" phase — re-running would re-trigger the whole agent on the
      // server, so we just log and leave the user to retry manually. No UI
      // toast or "Connection error" banner per UX preference.
      console.warn('[chat] stream ended with error:', err);
    } finally {
      setIsLoading(false);
      setUploadProgress(null);  // hide progress bar when chat fully done (or errored)
    }
  };

  // ---------------------------------------------------------------------------
  // SSE event handler
  // ---------------------------------------------------------------------------

  const handleSSEEvent = (chatId, event) => {
    switch (event.type) {
      case 'thinking':
        appendThinkingBlock(chatId, event.content);
        break;

      case 'text_chunk':
        // Real answer started → the current thinking turn is done.
        finalizeThinking(chatId);
        appendTextBlock(chatId, event.content);
        break;

      case 'tool_start':
        finalizeThinking(chatId);
        appendBlock(chatId, {
          type: 'tool_status',
          task_id: event.task_id,
          tool: event.tool,
          message: event.message,
          progress: 0,
        });
        break;

      case 'tool_progress':
        updateToolBlock(chatId, event.task_id, {
          message: event.message,
          progress: event.progress,
        });
        break;

      case 'tool_result': {
        if (event.task_id) {
          updateToolBlock(chatId, event.task_id, { progress: 100, message: 'Completed' });
        }
        const files = event.files || [];
        const imageFiles   = files.filter(f => f.render_type === 'image');
        const downloadFiles = files.filter(f => f.render_type === 'download' || f.render_type === 'csv');

        imageFiles.forEach(f => {
          appendBlock(chatId, { type: 'image', url: f.url, filename: f.filename });
        });
        if (downloadFiles.length > 0) {
          appendBlock(chatId, { type: 'file_download', files: downloadFiles });
        }
        break;
      }

      case 'csv_data':
        appendBlock(chatId, {
          type: 'csv_table',
          filename: event.filename,
          rows: event.rows,
          columns: event.columns,
        });
        break;

      case 'chart_config':
        appendBlock(chatId, { type: 'chart', config: event.config });
        break;

      case 'image_url':
        appendBlock(chatId, { type: 'image', url: event.url, filename: event.filename, extent: event.extent });
        break;

      case 'warning':
        appendBlock(chatId, { type: 'warning', message: event.message });
        break;

      case 'error':
        appendBlock(chatId, { type: 'text', content: `❌ Error: ${event.message}` });
        break;

      case 'done':
        finalizeThinking(chatId);
        break;
      default:
        break;
    }
  };

  // ---------------------------------------------------------------------------
  // Sidebar helpers
  // ---------------------------------------------------------------------------

  const createNewChat = () => {
    // Mint a fresh backend session_id so the new chat doesn't drag along the
    // previous conversation's chat_history (which makes the LLM replay old
    // tool errors instead of actually re-dispatching tools).
    sessionId.current = resetSessionId();

    const newId = Date.now().toString();
    setChats([{ id: newId, title: 'New Chat', messages: [] }, ...chats]);
    setActiveId(newId);
    setIsLoading(false);
  };

  const deleteChat = (id, e) => {
    e.stopPropagation();
    if (chats.length === 1) {
      setChats([{ id: 'default', title: 'New Chat', messages: [] }]);
      return;
    }
    const newChats = chats.filter(c => c.id !== id);
    setChats(newChats);
    if (activeId === id) setActiveId(newChats[0].id);
  };

  const exportChat = (chat, e) => {
    e.stopPropagation();
    const content = chat.messages
      .map(m => `### ${m.role === 'user' ? 'User' : 'AI'}\n${messageToMarkdown(m)}\n`)
      .join('\n---\n');
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${chat.title}.md`; a.click();
    URL.revokeObjectURL(url);
  };

  const renameChat = (id, newTitle) => {
    if (!newTitle.trim()) { setEditingId(null); return; }
    setChats(prev => prev.map(c => c.id === id ? { ...c, title: newTitle } : c));
    setEditingId(null);
  };

  // ---------------------------------------------------------------------------
  // Drag-and-drop handlers
  // ---------------------------------------------------------------------------

  const handleDragEnter = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.includes('Files')) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    // Only hide overlay when cursor truly leaves the main area,
    // not when moving between child elements inside it.
    if (!e.currentTarget.contains(e.relatedTarget)) setIsDragging(false);
  };

  const handleDragOver = (e) => { e.preventDefault(); };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) setSelectedFiles(prev => [...prev, ...files]);
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex h-screen bg-[#f0f4f9] text-[#1f1f1f] overflow-hidden">

      {/* Mobile overlay backdrop */}
      {isSidebarOpen && (
        <div className="fixed inset-0 bg-black/30 z-30 md:hidden" onClick={() => setIsSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <div className={`
        fixed md:relative z-40 md:z-auto h-full
        ${isSidebarOpen ? 'w-72 translate-x-0' : 'w-72 -translate-x-full md:w-0'}
        bg-[#f0f4f9] transition-all duration-300 flex flex-col flex-shrink-0 overflow-hidden
      `}>
        <div className="p-4">
          <button onClick={createNewChat} className="flex items-center gap-3 px-5 py-3 bg-[#dde3ea] hover:bg-white hover:shadow-sm rounded-full transition-all text-sm font-medium text-[#444746]">
            <Plus size={18} /><span>New Chat</span>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-3">
          <p className="text-xs font-semibold text-gray-500 px-4 py-3">Recent</p>
          {chats.map(chat => (
            <div key={chat.id} onClick={() => { setActiveId(chat.id); setIsLoading(false); }}
              className={`group flex items-center justify-between px-4 py-2 rounded-full cursor-pointer mb-1 transition-all ${activeId === chat.id ? 'bg-[#d3e3fd] text-[#041e49]' : 'hover:bg-[#e6eaf1] text-[#444746]'}`}>
              <div className="flex items-center gap-3 truncate flex-1">
                <MessageSquare size={16} />
                {editingId === chat.id ? (
                  <input autoFocus className="bg-white border-blue-400 rounded px-1 text-sm w-full outline-none"
                    value={tempTitle} onChange={e => setTempTitle(e.target.value)}
                    onBlur={() => renameChat(chat.id, tempTitle)}
                    onKeyDown={e => e.key === 'Enter' && renameChat(chat.id, tempTitle)} />
                ) : (
                  <span className="text-sm truncate">{chat.title}</span>
                )}
              </div>
              <div className="flex opacity-0 group-hover:opacity-100 transition-opacity ml-1 shrink-0">
                <button onClick={e => { e.stopPropagation(); setEditingId(chat.id); setTempTitle(chat.title); }} className="p-1 hover:bg-black/10 rounded-full"><Edit2 size={12} /></button>
                <button onClick={e => exportChat(chat, e)} className="p-1 hover:bg-black/10 rounded-full"><Download size={12} /></button>
                <button onClick={e => deleteChat(chat.id, e)} className="p-1 hover:bg-black/10 rounded-full"><Trash2 size={12} /></button>
              </div>
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-gray-200">
          <button onClick={() => setIsSettingsOpen(true)} className="flex items-center gap-3 px-4 py-2 w-full hover:bg-gray-200 rounded-full text-sm text-gray-600 transition-colors">
            <Settings size={18} /><span>Settings</span>
          </button>
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 flex flex-col h-full bg-white rounded-tl-3xl shadow-sm mt-2 overflow-hidden relative"
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="absolute inset-0 z-50 bg-blue-50/80 backdrop-blur-sm border-2 border-dashed border-blue-400 rounded-tl-3xl flex flex-col items-center justify-center pointer-events-none">
            <Upload size={48} className="text-blue-400 mb-4" />
            <p className="text-blue-600 font-semibold text-lg">Drop files to attach</p>
            <p className="text-blue-400 text-sm mt-1">Release to add to your message</p>
          </div>
        )}
        <div className="flex items-center p-4">
          <button onClick={() => setIsSidebarOpen(v => !v)} className="p-2 hover:bg-gray-100 rounded-full mr-2">
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2 font-medium text-gray-700">
            CSIS <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded uppercase tracking-wider text-gray-500">
              {appSettings.selectedModel}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 md:px-[12%] pt-10">
          {currentChat.messages.length === 0 ? (
            <div className="animate-in fade-in slide-in-from-bottom-6 duration-1000">
              <h1 className="text-6xl font-medium tracking-tight mb-2">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570]">
                  Hi, CSIS
                </span>
              </h1>
              <h2 className="text-5xl font-medium text-[#c4c7c5] mb-12">How can I help you today?</h2>
              <div className="grid grid-cols-2 gap-4 max-w-2xl">
                {SUGGESTED_PROMPTS.map((p, i) => (
                  <div key={i}
                    className="p-4 bg-gray-50 rounded-2xl hover:bg-gray-100 cursor-pointer transition-colors border border-transparent hover:border-gray-200"
                    onClick={() => handleSend(p.label)}>
                    <p className="text-xs font-semibold text-blue-500 mb-1">{p.hint}</p>
                    <p className="text-sm text-gray-600">{p.label}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-8 pb-20">
              {currentChat.messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  <MessageContent msg={msg} sessionId={sessionId.current} />
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-5">
                  <Sparkles size={24} className="text-blue-500 animate-pulse" />
                  <div className="h-4 w-4 bg-blue-100 rounded-full animate-ping mt-2" />
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Upload progress bar — two phases:
              uploading  — bytes are leaving the browser, progress climbs to 100%
              processing — browser pushed all bytes, server still receiving / inspecting
                           (this is where the MSU WAF spends most of its time)
              Hidden once status === 'done' (server acked, chat phase takes over) */}
        {uploadProgress && uploadProgress.status !== 'done' && (
          <div className="px-6 pb-2">
            <div className="max-w-[800px] mx-auto bg-blue-50 border border-blue-200 rounded-2xl px-4 py-3">
              <div className="flex items-center justify-between text-xs text-blue-800 mb-1">
                <span className="font-medium">
                  {uploadProgress.status === 'processing'
                    ? 'Server receiving upload… please wait (large rasters can take a few minutes through the MSU WAF)'
                    : `Uploading files… ${(uploadProgress.loaded / (1024 * 1024)).toFixed(1)} MB / ${(uploadProgress.total / (1024 * 1024)).toFixed(1)} MB`}
                </span>
                {uploadProgress.status === 'uploading' && (
                  <span className="font-mono">{Math.round(uploadProgress.percent)}%</span>
                )}
              </div>
              <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
                <div
                  className={`h-full bg-blue-500 transition-all duration-150 ${uploadProgress.status === 'processing' ? 'animate-pulse' : ''}`}
                  style={{ width: `${Math.min(100, uploadProgress.percent)}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="p-6">
          <div className="max-w-[800px] mx-auto bg-[#f0f4f9] rounded-3xl px-5 py-3 flex flex-col gap-2 focus-within:bg-white focus-within:shadow-xl focus-within:ring-1 focus-within:ring-gray-200 transition-all">
            {selectedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedFiles.map((f, i) => (
                  <div key={i} className="flex items-center gap-1 text-xs bg-white px-2 py-1 rounded-full border shadow-sm text-blue-600">
                    <Paperclip size={10} /> {f.webkitRelativePath || f.name}
                    <button onClick={() => setSelectedFiles(prev => prev.filter((_, j) => j !== i))} className="ml-1 text-gray-400 hover:text-red-500">×</button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center gap-3">
              <button onClick={() => fileInputRef.current.click()} title="Attach files" className="p-2 text-gray-500 hover:text-blue-600">
                <Plus size={22} />
              </button>
              <button onClick={() => folderInputRef.current.click()} title="Upload a whole folder (keeps sub-folders)" className="p-2 text-gray-500 hover:text-blue-600">
                <Folder size={20} />
              </button>
              <input type="file" ref={fileInputRef} hidden multiple
                onChange={e => setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)])} />
              {/* webkitdirectory turns this picker into a folder selector; each
                  File carries webkitRelativePath, sent to the backend to rebuild
                  the sub-folder layout (e.g. for HRA's habitat_layers/...). */}
              <input type="file" ref={folderInputRef} hidden multiple webkitdirectory=""
                onChange={e => setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)])} />
              <input
                className="flex-1 bg-transparent outline-none py-2 text-gray-800 placeholder-gray-500"
                placeholder="Enter a prompt here"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              />
              <button onClick={() => handleSend()}
                className={`${input.trim() || selectedFiles.length > 0 ? 'text-blue-600' : 'text-gray-400'} p-2 hover:bg-blue-50 rounded-full transition-colors`}>
                <Send size={22} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-300">
          <div className="bg-white rounded-3xl w-[420px] p-8 shadow-2xl relative">
            <button onClick={() => setIsSettingsOpen(false)} className="absolute top-6 right-6 p-1 hover:bg-gray-100 rounded-full text-gray-400"><X size={20} /></button>
            <h2 className="text-2xl font-semibold mb-8">Settings</h2>
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Active Model</label>
                <select
                  value={appSettings.selectedModel}
                  onChange={e => setAppSettings({ ...appSettings, selectedModel: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500 text-sm appearance-none cursor-pointer"
                >
                  {AVAILABLE_MODELS.map(m => (
                    <option key={m.id} value={m.id}>{m.name} — {m.desc}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">Creativity (Temp)</span>
                  <span className="text-xs font-bold bg-purple-50 text-purple-600 px-2 py-1 rounded-md">{appSettings.temperature}</span>
                </div>
                <input type="range" min="0" max="2" step="0.1"
                  value={appSettings.temperature}
                  onChange={e => setAppSettings({ ...appSettings, temperature: parseFloat(e.target.value) })}
                  className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600" />
              </div>
              <div className="pt-4">
                <button
                  onClick={() => { if (confirm('Erase all chats and reset settings?')) { localStorage.clear(); window.location.reload(); } }}
                  className="w-full py-3 text-red-500 bg-red-50 hover:bg-red-100 rounded-xl transition-colors text-xs font-bold uppercase tracking-widest"
                >
                  Reset System
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
