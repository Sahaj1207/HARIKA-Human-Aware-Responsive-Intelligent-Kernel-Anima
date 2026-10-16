import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, FileText, Image as ImageIcon, Loader2, Plus, Square, X } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { VoiceButton } from './VoiceButton';
import { chatService } from '@/services/api/chat';
import { visionService } from '@/services/api/vision';
import { userStorage } from '@/features/onboarding/storage';
import { coreStateManager } from '@/services/coreState/coreStateManager';

/** Recent turns sent as context; the full history would slow every request and overflow the model. */
const HISTORY_TURNS = 12;

export const CommandBar: React.FC = () => {
  const [input, setInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addMessage = useHARIKAStore((s) => s.addMessage);
  const coreState = useHARIKAStore((s) => s.coreState);
  const setThinkingStage = useHARIKAStore((s) => s.setThinkingStage);
  const completeGeneration = useHARIKAStore((s) => s.completeGeneration);

  const isGenerating = coreState === 'thinking' || coreState === 'speaking' || isUploading;
  const isBusyGlow = coreState === 'thinking' || coreState === 'listening' || isUploading;

  const focusInput = () => setTimeout(() => inputRef.current?.focus(), 60);

  const handleStop = () => {
    completeGeneration();
    setIsUploading(false);
    focusInput();
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

  const analyzeFile = async (file: File, question: string) => {
    setIsUploading(true);
    coreStateManager.transitionTo('thinking');
    setThinkingStage('thinking');
    const isPdf = file.type === 'application/pdf' || file.name.endsWith('.pdf');
    addMessage({ role: 'user', content: question ? `${question}\n(${file.name})` : file.name, status: 'delivered' });
    clearSelectedFile();
    setInput('');

    try {
      const result = isPdf ? await visionService.processPdf(file) : await visionService.processImage(file);
      coreStateManager.transitionTo('speaking');
      const text = result.ocr?.raw_text?.trim();
      addMessage({
        role: 'assistant',
        content: `${result.summary}${text ? `\n\nText I found:\n${text}` : ''}`,
        status: 'completed',
        metadata: { provider: result.provider, model: result.model, latency_ms: result.latency_ms },
      });
    } catch (err: any) {
      addMessage({
        role: 'assistant',
        content: `I couldn't read ${file.name}: ${err?.response?.data?.detail || err.message}`,
        status: 'completed',
      });
    } finally {
      setIsUploading(false);
      completeGeneration();
    }
  };

  const sendText = async (userQuery: string) => {
    addMessage({ role: 'user', content: userQuery, status: 'delivered' });
    setInput('');
    coreStateManager.transitionTo('thinking');
    setThinkingStage('thinking');
    const thinkingTimer = setTimeout(() => setThinkingStage('still-thinking'), 10000);

    const userName = userStorage.getProfile()?.name || 'User';
    const historyPayload = useHARIKAStore
      .getState()
      .messages.slice(-HISTORY_TURNS)
      .map((m) => ({ sender: m.role, role: m.role, content: m.content }));

    try {
      const data = await chatService.sendMessage(userQuery, userName, historyPayload);
      setThinkingStage('idle');
      coreStateManager.transitionTo('speaking');
      addMessage({
        role: 'assistant',
        content: data.response,
        status: 'streaming',
        metadata: { provider: data.provider, model: data.model, latency_ms: data.latency_ms },
      });
    } catch {
      addMessage({
        role: 'assistant',
        content: "I can't reach my engine right now. If you just opened HARIKA, give it a few seconds and try again.",
        status: 'completed',
        metadata: { provider: 'offline' },
      });
      completeGeneration();
    } finally {
      clearTimeout(thinkingTimer);
      focusInput();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isGenerating) {
      handleStop();
      return;
    }
    const userQuery = input.trim();
    if (selectedFile) return analyzeFile(selectedFile, userQuery);
    if (userQuery) return sendText(userQuery);
  };

  // Suggestions and other parts of the UI can ask on the user's behalf.
  useEffect(() => {
    const onAsk = (event: Event) => {
      const text = (event as CustomEvent<string>).detail;
      if (text && !isGenerating) void sendText(text);
    };
    window.addEventListener('harika:ask', onAsk);
    return () => window.removeEventListener('harika:ask', onAsk);
  });

  const canSend = Boolean(input.trim() || selectedFile);

  return (
    <div className="w-full max-w-3xl mx-auto px-5 pb-5 pt-2">
      {selectedFile && (
        <div className="mb-2 inline-flex items-center gap-2 glass rounded-full pl-2 pr-1 py-1 t-footnote text-label bubble-enter">
          {filePreview ? (
            <img src={filePreview} alt="" className="w-6 h-6 rounded-md object-cover" />
          ) : selectedFile.type.includes('pdf') ? (
            <FileText className="w-4 h-4 text-accent" aria-hidden />
          ) : (
            <ImageIcon className="w-4 h-4 text-accent" aria-hidden />
          )}
          <span className="truncate max-w-56">{selectedFile.name}</span>
          <button type="button" onClick={clearSelectedFile} aria-label="Remove attachment" className="p-1 rounded-full hover:bg-fill">
            <X className="w-3.5 h-3.5 text-label-2" />
          </button>
        </div>
      )}

      <div data-active={isBusyGlow} className="harika-glow-edge rounded-[24px]">
      <form
        onSubmit={handleSubmit}
        className="glass glass-strong rounded-[24px] flex items-center gap-1.5 pl-1.5 pr-1.5 py-1.5"
      >
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
          aria-label="Attach an image or PDF"
          className="w-8 h-8 grid place-items-center rounded-full bg-fill text-label-2 hover:text-label disabled:opacity-40 transition-colors shrink-0"
        >
          <Plus className="w-[18px] h-[18px]" strokeWidth={2.4} />
        </button>

        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isGenerating}
          aria-label="Message HARIKA"
          placeholder={isGenerating ? 'HARIKA is working on it…' : selectedFile ? 'Ask about this file, or just send' : 'Ask HARIKA'}
          className="flex-1 min-w-0 bg-transparent t-body text-label placeholder:text-label-3 outline-none px-1.5 disabled:opacity-60"
        />

        <VoiceButton />

        {isGenerating ? (
          <button
            type="button"
            onClick={handleStop}
            aria-label="Stop"
            className="w-8 h-8 grid place-items-center rounded-full bg-label text-canvas shrink-0"
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Square className="w-3 h-3 fill-current" />}
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send"
            className="w-8 h-8 grid place-items-center rounded-full bg-accent text-white disabled:bg-fill disabled:text-label-3 transition-colors shrink-0"
          >
            <ArrowUp className="w-[18px] h-[18px]" strokeWidth={2.6} />
          </button>
        )}
      </form>
      </div>
    </div>
  );
};
