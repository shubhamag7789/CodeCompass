import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  RotateCcw,
  FileText,
  Copy,
  Check,
  Loader2,
  ChevronRight,
} from 'lucide-react';
import { api } from '../../api/client';
import type { ChatMessage, AiStatus } from '../../types';

interface CopilotChatProps {
  activeRepoId?: string;
  aiStatus?: AiStatus | null;
  onSelectFile?: (filePath: string) => void;
  prefilledPrompt?: string;
}

export const CopilotChat: React.FC<CopilotChatProps> = ({
  activeRepoId,
  aiStatus,
  onSelectFile,
  prefilledPrompt,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hello! I am your CodeCompass AI Copilot powered by Gemini 3.5 Flash Lite. Ask me anything about this repository—such as architectural patterns, API contracts, blast radius, or debugging specific files.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState(prefilledPrompt || '');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    if (prefilledPrompt) {
      setInput(prefilledPrompt);
    }
  }, [prefilledPrompt]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userText = input.trim();
    setInput('');
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await api.sendChatMessage({
        question: userText,
        conversation_id: conversationId || undefined,
        repo_id: activeRepoId,
      });

      if (res.conversation_id) {
        setConversationId(res.conversation_id);
      }

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: res.answer || 'No response generated.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: res.sources,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error generating response: ${err.message || 'Server error'}. Please check backend logs.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    if (conversationId) {
      try {
        await api.sendChatMessage({
          question: '',
          conversation_id: conversationId,
          repo_id: activeRepoId,
          reset: true,
        });
      } catch {
        // ignore
      }
    }
    setConversationId('');
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: 'assistant',
        content: 'Conversation context reset. Ask me a fresh question about your codebase!',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const handleCopyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const quickPrompts = [
    'How does authentication and session state work in this codebase?',
    'What is the blast radius and consumer risk if I change formatDate?',
    'Explain the end-to-end data flow from HTTP request to database.',
    'Where are the primary API routes registered?',
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto p-4 md:p-6">
      {/* Chat Header Bar */}
      <div className="glass-panel p-4 rounded-2xl border border-white/10 flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>CodeCompass Copilot</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-normal">
                {aiStatus?.model || 'Gemini 3.5 Flash Lite'}
              </span>
            </h2>
            <p className="text-[11px] text-slate-400">
              Interactive architectural Q&amp;A with BM25 contextual retrieval
            </p>
          </div>
        </div>

        <button
          onClick={handleReset}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-slate-300 transition-all active:scale-95"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span>Reset Chat</span>
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-4">
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 text-xs font-semibold ${
                  isUser
                    ? 'bg-blue-600 text-white'
                    : 'bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`max-w-[80%] rounded-2xl p-4 text-xs leading-relaxed space-y-3 ${
                  isUser
                    ? 'bg-blue-600/90 text-white shadow-lg'
                    : 'glass-panel border border-white/10 text-slate-200 shadow-xl'
                }`}
              >
                <div className="flex items-center justify-between text-[10px] opacity-70 pb-1 border-b border-white/5">
                  <span className="font-semibold">{isUser ? 'You' : 'CodeCompass AI'}</span>
                  <span>{msg.timestamp}</span>
                </div>

                <div className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed">
                  {msg.content}
                </div>

                {/* Citations / Sources Chips */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="pt-2 border-t border-white/10 space-y-1.5">
                    <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block">
                      Referenced Code Context ({msg.citations.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.citations.map((cite, i) => (
                        <button
                          key={i}
                          onClick={() => onSelectFile && onSelectFile(cite.file)}
                          className="flex items-center space-x-1 px-2 py-1 rounded bg-black/40 hover:bg-cyan-950/50 border border-white/5 hover:border-cyan-500/30 text-[10px] font-mono text-cyan-300 transition-all text-left"
                        >
                          <FileText className="w-3 h-3 flex-shrink-0" />
                          <span className="truncate max-w-[180px]">{cite.file}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Copy Button for Assistant responses */}
                {!isUser && (
                  <div className="flex justify-end pt-1">
                    <button
                      onClick={() => handleCopyText(msg.content, msg.id)}
                      className="text-slate-400 hover:text-white transition-colors flex items-center space-x-1 text-[10px]"
                    >
                      {copiedId === msg.id ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span className="text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy Answer</span>
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-md shadow-cyan-500/20">
              <Bot className="w-4 h-4" />
            </div>
            <div className="glass-panel border border-white/10 rounded-2xl p-4 text-xs text-slate-300 flex items-center space-x-2">
              <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              <span>Analyzing codebase architecture &amp; reasoning with Gemini...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts Pill Carousel */}
      {messages.length <= 2 && (
        <div className="flex items-center space-x-2 overflow-x-auto py-2 flex-shrink-0">
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => {
                setInput(p);
              }}
              className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] text-slate-300 whitespace-nowrap transition-all flex items-center space-x-1.5"
            >
              <Sparkles className="w-3 h-3 text-cyan-400" />
              <span>{p}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input Box Form */}
      <form onSubmit={handleSend} className="relative mt-2 flex-shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about architecture, dependencies, or impact..."
          disabled={isLoading}
          className="w-full bg-[#121a30] border border-white/10 rounded-2xl pl-4 pr-12 py-3.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 shadow-xl"
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="absolute right-2 top-2 p-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 disabled:opacity-40 text-white transition-all shadow-md shadow-cyan-500/20 active:scale-95"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};

