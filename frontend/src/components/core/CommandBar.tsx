import React, { useState, useRef } from 'react';
import { Send, Terminal, Square, Paperclip, X, Image as ImageIcon, FileText, Loader2 } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { VoiceButton } from './VoiceButton';
import { chatService } from '@/services/api/chat';
import { visionService } from '@/services/api/vision';
import { userStorage } from '@/features/onboarding/storage';
import { coreStateManager } from '@/services/coreState/coreStateManager';

export const CommandBar: React.FC = () => {
  const [input, setInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addMessage = useHARIKAStore((s) => s.addMessage);
  const messages = useHARIKAStore((s) => s.messages);
  const coreState = useHARIKAStore((s) => s.coreState);
  const setThinkingStage = useHARIKAStore((s) => s.setThinkingStage);
  const completeGeneration = useHARIKAStore((s) => s.completeGeneration);

  const isGenerating = coreState === 'thinking' || coreState === 'speaking' || isUploading;

  const handleStop = () => {
    completeGeneration();
    setIsUploading(false);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = () => setFilePreview(reader.result as string);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    setFilePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isGenerating) {
      handleStop();
      return;
    }

    const userQuery = input.trim();
    if (!userQuery && !selectedFile) return;

    // Process file if selected
    if (selectedFile) {
      setIsUploading(true);
      coreStateManager.transitionTo('thinking');
      setThinkingStage('thinking');

      const isPdf = selectedFile.type === 'application/pdf' || selectedFile.name.endsWith('.pdf');
      
      addMessage({
        role: 'user',
        content: userQuery ? `[Attached ${selectedFile.name}] ${userQuery}` : `Uploaded visual asset: ${selectedFile.name}`,
        status: 'delivered',
      });

      const currentFile = selectedFile;
      clearSelectedFile();
      setInput('');

      try {
        const vResult = isPdf
          ? await visionService.processPdf(currentFile)
          : await visionService.processImage(currentFile);

        coreStateManager.transitionTo('speaking');
        addMessage({
          role: 'assistant',
          content: `👁️ **Vision Analysis for ${vResult.filename}** (${vResult.file_type})\n\n**Summary**: ${vResult.summary}\n\n${vResult.ocr?.raw_text ? '**OCR Text Extracted**:\n```\n' + vResult.ocr.raw_text + '\n```' : ''}`,
          status: 'completed',
          metadata: {
            provider: vResult.provider,
            model: vResult.model,
            latency_ms: vResult.latency_ms,
          },
        });
      } catch (err: any) {
        addMessage({
          role: 'assistant',
          content: `Failed to process visual asset ${currentFile.name}: ${err?.response?.data?.detail || err.message}`,
          status: 'completed',
        });
      } finally {
        setIsUploading(false);
        completeGeneration();
      }
      return;
    }

    // Standard text message
    addMessage({
      role: 'user',
      content: userQuery,
      status: 'delivered',
    });

    setInput('');

    coreStateManager.transitionTo('thinking');
    setThinkingStage('thinking');

    const thinkingTimer = setTimeout(() => {
      setThinkingStage('still-thinking');
    }, 10000);

    const profile = userStorage.getProfile();
    const userName = profile?.name || 'User';

    const historyPayload = messages.map((m) => ({
      sender: m.role,
      role: m.role,
      content: m.content,
    }));

    try {
      const data = await chatService.sendMessage(userQuery, userName, historyPayload);
      clearTimeout(thinkingTimer);
      setThinkingStage('idle');

      coreStateManager.transitionTo('speaking');

      addMessage({
        role: 'assistant',
        content: data.response,
        status: 'streaming',
        metadata: {
          provider: data.provider,
          model: data.model,
          latency_ms: data.latency_ms,
        },
      });
    } catch {
      clearTimeout(thinkingTimer);
      addMessage({
        role: 'assistant',
        content: `I heard your directive "${userQuery}", but the backend engine is currently offline or unreachable.`,
        status: 'completed',
        metadata: { provider: 'offline', model: 'fallback' },
      });
      completeGeneration();
    } finally {
      clearTimeout(thinkingTimer);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto px-4 pb-6 pt-2">
      {/* File Preview Badge */}
      {selectedFile && (
        <div className="mb-2 surface-translucent px-3 py-1.5 rounded-xl border border-white/10 flex items-center justify-between text-xs text-slate-300 animate-in fade-in duration-200">
          <div className="flex items-center space-x-2 truncate">
            {filePreview ? (
              <img src={filePreview} alt="Preview" className="w-6 h-6 rounded object-cover border border-white/20" />
            ) : selectedFile.type.includes('pdf') ? (
              <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
            ) : (
              <ImageIcon className="w-4 h-4 text-cyan-400 shrink-0" />
            )}
            <span className="truncate font-mono">{selectedFile.name}</span>
            <span className="text-[10px] text-slate-500 font-mono">({Math.round(selectedFile.size / 1024)} KB)</span>
          </div>
          <button onClick={clearSelectedFile} className="text-slate-400 hover:text-rose-400 transition-colors p-1">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="surface-translucent rounded-full px-4 py-2.5 flex items-center space-x-3 border border-white/10 shadow-2xl transition-all duration-300 focus-within:border-sky-500/40"
      >
        <Terminal className="w-4 h-4 text-slate-400 shrink-0 ml-1" />

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept="image/png,image/jpeg,image/jpg,image/webp,application/pdf"
          className="hidden"
        />

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isGenerating}
          className="text-slate-400 hover:text-cyan-400 transition-colors disabled:opacity-40"
          title="Upload Visual Asset (PNG, JPG, WEBP, PDF)"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isGenerating}
          placeholder={isGenerating ? 'HARIKA is analyzing...' : selectedFile ? 'Add prompt or press enter to analyze visual asset...' : 'Command HARIKA OS...'}
          className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-sans disabled:opacity-50"
        />

        <VoiceButton />

        {isGenerating ? (
          <button
            type="button"
            onClick={handleStop}
            className="p-2 rounded-full text-rose-400 hover:text-rose-300 bg-rose-500/10 border border-rose-500/30 animate-pulse transition-all cursor-pointer"
            title="Stop Response Generation"
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin text-cyan-400" /> : <Square className="w-4 h-4 fill-current" />}
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() && !selectedFile}
            className="p-2 rounded-full text-slate-400 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-400 transition-colors cursor-pointer"
            title="Execute Directive"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </form>
    </div>
  );
};

