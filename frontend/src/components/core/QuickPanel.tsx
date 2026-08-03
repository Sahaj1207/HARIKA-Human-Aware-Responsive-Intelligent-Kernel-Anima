import React, { useState, useEffect } from 'react';
import { X, Moon, Power, Database, Search, Trash2, Tag, ShieldCheck } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { memoryService, MemoryItemApi, MemoryMetricsApi } from '@/services/api/memory';

export const QuickPanel: React.FC = () => {
  const { isQuickPanelOpen, toggleQuickPanel, coreState, setCoreState } = useHARIKAStore();
  const [activeTab, setActiveTab] = useState<'controls' | 'memory'>('memory');
  const [searchQuery, setSearchQuery] = useState('');
  const [memories, setMemories] = useState<MemoryItemApi[]>([]);
  const [metrics, setMetrics] = useState<MemoryMetricsApi | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchMemoryData = async (query?: string) => {
    setLoading(true);
    try {
      const [items, stats] = await Promise.all([
        memoryService.getMemories(query),
        memoryService.getMetrics(),
      ]);
      setMemories(items);
      setMetrics(stats);
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isQuickPanelOpen) {
      fetchMemoryData(searchQuery);
    }
  }, [isQuickPanelOpen, searchQuery]);

  const handleDelete = async (id: string) => {
    try {
      await memoryService.deleteMemory(id);
      fetchMemoryData(searchQuery);
    } catch (e) {
      console.error('Delete memory failed:', e);
    }
  };

  const handleClearAll = async () => {
    if (window.confirm('Clear all stored HARIKA memories?')) {
      try {
        await memoryService.clearAll();
        fetchMemoryData('');
      } catch (e) {
        console.error('Clear all failed:', e);
      }
    }
  };

  if (!isQuickPanelOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50 backdrop-blur-xs transition-opacity duration-300">
      <div className="w-96 h-full surface-translucent border-l border-white/10 p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-300">
        <div className="space-y-5 overflow-y-auto pr-1">
          {/* Header & Tabs */}
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div className="flex space-x-2">
              <button
                onClick={() => setActiveTab('memory')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'memory'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Memory Engine
              </button>
              <button
                onClick={() => setActiveTab('controls')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'controls'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Core State
              </button>
            </div>
            <button
              onClick={toggleQuickPanel}
              className="text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {activeTab === 'memory' ? (
            <div className="space-y-4">
              {/* Health Metrics Summary Bar */}
              {metrics && (
                <div className="surface-translucent-subtle p-3 rounded-xl border border-white/5 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono text-slate-300">
                    <span className="flex items-center space-x-1.5">
                      <Database className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Total Memories: {metrics.total_memories}</span>
                    </span>
                    <span className="text-[10px] text-emerald-400">
                      Avg Imp: {metrics.average_importance}
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-500 flex justify-between">
                    <span>Deleted: {metrics.deleted_count}</span>
                    <span>Storage: {metrics.storage_bytes} B</span>
                  </div>
                </div>
              )}

              {/* Instant Search Bar */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search cognitive memory..."
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/40"
                />
              </div>

              {/* Grouped Memory Item List */}
              <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
                {loading ? (
                  <div className="text-xs font-mono text-slate-500 py-6 text-center animate-pulse">
                    Loading cognitive knowledge...
                  </div>
                ) : memories.length === 0 ? (
                  <div className="text-xs font-mono text-slate-500 py-6 text-center">
                    No stored memories found.
                  </div>
                ) : (
                  memories.map((item) => (
                    <div
                      key={item.id}
                      className="surface-translucent-subtle p-3 rounded-xl border border-white/5 space-y-1 hover:border-white/10 transition-all group relative"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono tracking-wider uppercase text-cyan-400 flex items-center space-x-1">
                          <Tag className="w-2.5 h-2.5" />
                          <span>{item.category.replace('_', ' ')}</span>
                        </span>
                        <div className="flex items-center space-x-2">
                          <span className="text-[9px] font-mono text-slate-500">
                            Imp: {item.importance}
                          </span>
                          <button
                            onClick={() => handleDelete(item.id)}
                            className="text-slate-600 hover:text-rose-400 transition-colors"
                            title="Soft delete memory item"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>

                      <h4 className="text-xs font-medium text-slate-200">{item.title}</h4>
                      <p className="text-[11px] text-slate-400 leading-normal">{item.content}</p>

                      <div className="text-[9px] font-mono text-slate-600 pt-1 flex items-center justify-between border-t border-white/5">
                        <span>Rev {item.revision}</span>
                        <span className="flex items-center space-x-1">
                          <ShieldCheck className="w-2.5 h-2.5 text-emerald-400" />
                          <span>{(item.confidence * 100).toFixed(0)}% Conf</span>
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Clear All Option */}
              {memories.length > 0 && (
                <div className="pt-2">
                  <button
                    onClick={handleClearAll}
                    className="w-full py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs font-mono uppercase hover:bg-rose-500/20 transition-colors"
                  >
                    Clear All Memories
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="text-xs font-mono text-slate-500 uppercase tracking-wider">
                Core Visual State
              </div>
              <div className="grid grid-cols-2 gap-2">
                {(['idle', 'listening', 'thinking', 'speaking', 'sleeping'] as const).map(
                  (state) => (
                    <button
                      key={state}
                      onClick={() => setCoreState(state)}
                      className={`px-3 py-2 rounded-lg text-xs font-mono uppercase tracking-wider border transition-all ${
                        coreState === state
                          ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300'
                          : 'border-white/5 bg-white/5 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {state}
                    </button>
                  )
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-white/5 pt-4 flex items-center justify-between text-xs font-mono text-slate-500">
          <button
            onClick={() => setCoreState(coreState === 'sleeping' ? 'idle' : 'sleeping')}
            className="flex items-center space-x-2 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Moon className="w-4 h-4" />
            <span>{coreState === 'sleeping' ? 'Wake Core' : 'Sleep Core'}</span>
          </button>
          <div className="flex items-center space-x-1">
            <Power className="w-3.5 h-3.5 text-emerald-400" />
            <span>v0.3 Engine</span>
          </div>
        </div>
      </div>
    </div>
  );
};
