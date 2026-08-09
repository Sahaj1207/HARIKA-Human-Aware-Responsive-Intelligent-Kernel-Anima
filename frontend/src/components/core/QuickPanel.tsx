import React, { useState, useEffect } from 'react';
import { X, Moon, Power, Database, Search, Trash2, Tag, Wrench, Activity, CheckCircle, AlertTriangle, Clock, Eye, FileText, Image, Bot, Play, Pause, Square, Mic, Volume2, GitBranch, Sparkles, Compass } from 'lucide-react';

import { useHARIKAStore } from '@/store/useHARIKAStore';
import { memoryService, MemoryItemApi, MemoryMetricsApi } from '@/services/api/memory';
import { toolsService, ToolManifestApi, ToolExecutionHistoryApi, ToolMetricsApi } from '@/services/api/tools';
import { visionService, VisionMetricsApi, VisionHistoryItemApi } from '@/services/api/vision';
import { agentsService, AgentStatusApi, AgentMetricsApi, AgentHistoryItemApi } from '@/services/api/agents';
import { voiceEngineService, VoiceStatusApi, VoiceMetricsApi, VoiceHistoryItemApi } from '@/services/api/voice';
import { routerEngineService, RouterStatusApi, RouterMetricsApi, RouterDecisionItemApi } from '@/services/api/router';
import { presenceService, PresenceStateApi, PresenceScoreApi } from '@/services/api/presence';

export const QuickPanel: React.FC = () => {
  const { isQuickPanelOpen, toggleQuickPanel, coreState, setCoreState } = useHARIKAStore();
  const [activeTab, setActiveTab] = useState<'tools' | 'memory' | 'vision' | 'agents' | 'voice' | 'router' | 'presence' | 'controls'>('tools');

  // Memory State
  const [searchQuery, setSearchQuery] = useState('');
  const [memories, setMemories] = useState<MemoryItemApi[]>([]);
  const [memoryMetrics, setMemoryMetrics] = useState<MemoryMetricsApi | null>(null);

  // Tools State
  const [tools, setTools] = useState<ToolManifestApi[]>([]);
  const [toolHistory, setToolHistory] = useState<ToolExecutionHistoryApi[]>([]);
  const [toolMetrics, setToolMetrics] = useState<ToolMetricsApi | null>(null);

  // Vision State
  const [visionMetrics, setVisionMetrics] = useState<VisionMetricsApi | null>(null);
  const [visionHistory, setVisionHistory] = useState<VisionHistoryItemApi[]>([]);

  // Agents State
  const [activeAgents, setActiveAgents] = useState<AgentStatusApi[]>([]);
  const [agentMetrics, setAgentMetrics] = useState<AgentMetricsApi | null>(null);
  const [agentHistory, setAgentHistory] = useState<AgentHistoryItemApi[]>([]);

  // Voice State
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusApi | null>(null);
  const [voiceMetrics, setVoiceMetrics] = useState<VoiceMetricsApi | null>(null);
  const [voiceHistory, setVoiceHistory] = useState<VoiceHistoryItemApi[]>([]);

  // Router State
  const [routerStatus, setRouterStatus] = useState<RouterStatusApi | null>(null);
  const [routerMetrics, setRouterMetrics] = useState<RouterMetricsApi | null>(null);
  const [routerHistory, setRouterHistory] = useState<RouterDecisionItemApi[]>([]);

  // Presence State
  const [presenceState, setPresenceState] = useState<PresenceStateApi | null>(null);
  const [presenceScore, setPresenceScore] = useState<PresenceScoreApi | null>(null);
  const [workingMemory, setWorkingMemory] = useState<Record<string, unknown>>({});

  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'memory') {
        const [items, stats] = await Promise.all([
          memoryService.getMemories(searchQuery),
          memoryService.getMetrics(),
        ]);
        setMemories(items);
        setMemoryMetrics(stats);
      } else if (activeTab === 'tools') {
        const [manifests, history, stats] = await Promise.all([
          toolsService.getTools(),
          toolsService.getHistory(20),
          toolsService.getMetrics(),
        ]);
        setTools(manifests);
        setToolHistory(history);
        setToolMetrics(stats);
      } else if (activeTab === 'vision') {
        const [vStats, vHistory] = await Promise.all([
          visionService.getMetrics(),
          visionService.getHistory(20),
        ]);
        setVisionMetrics(vStats);
        setVisionHistory(vHistory);
      } else if (activeTab === 'agents') {
        const [aList, aStats, aHistory] = await Promise.all([
          agentsService.listActive(),
          agentsService.getMetrics(),
          agentsService.getHistory(20),
        ]);
        setActiveAgents(aList);
        setAgentMetrics(aStats);
        setAgentHistory(aHistory);
      } else if (activeTab === 'voice') {
        const [vStatus, vStats, vHist] = await Promise.all([
          voiceEngineService.getStatus(),
          voiceEngineService.getMetrics(),
          voiceEngineService.getHistory(20),
        ]);
        setVoiceStatus(vStatus);
        setVoiceMetrics(vStats);
        setVoiceHistory(vHist);
      } else if (activeTab === 'router') {
        const [rStatus, rStats, rHist] = await Promise.all([
          routerEngineService.getStatus(),
          routerEngineService.getMetrics(),
          routerEngineService.getHistory(20),
        ]);
        setRouterStatus(rStatus);
        setRouterMetrics(rStats);
        setRouterHistory(rHist);
      } else if (activeTab === 'presence') {
        const [pState, pScore, pWork] = await Promise.all([
          presenceService.getState(),
          presenceService.getScore(),
          presenceService.getWorkingMemory(),
        ]);
        setPresenceState(pState);
        setPresenceScore(pScore);
        setWorkingMemory(pWork);
      }
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };





  useEffect(() => {
    if (isQuickPanelOpen) {
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isQuickPanelOpen, activeTab, searchQuery]);

  const handleDeleteMemory = async (id: string) => {
    try {
      await memoryService.deleteMemory(id);
      fetchData();
    } catch (e) {
      console.error('Delete memory failed:', e);
    }
  };

  const handleToggleTool = async (name: string, currentEnabled: boolean) => {
    try {
      await toolsService.toggleTool(name, !currentEnabled);
      fetchData();
    } catch (e) {
      console.error('Toggle tool failed:', e);
    }
  };

  if (!isQuickPanelOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50 backdrop-blur-xs transition-opacity duration-300">
      <div className="w-96 h-full surface-translucent border-l border-white/10 p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-300">
        <div className="space-y-5 overflow-y-auto pr-1">
          {/* Header & Tabs */}
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div className="flex space-x-1 border-b-0 overflow-x-auto">
              <button
                onClick={() => setActiveTab('tools')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'tools'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Action
              </button>
              <button
                onClick={() => setActiveTab('memory')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'memory'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Memory
              </button>
              <button
                onClick={() => setActiveTab('vision')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'vision'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Vision
              </button>
              <button
                onClick={() => setActiveTab('agents')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'agents'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Agents
              </button>
              <button
                onClick={() => setActiveTab('voice')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'voice'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Voice
              </button>
              <button
                onClick={() => setActiveTab('router')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'router'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Router
              </button>
              <button
                onClick={() => setActiveTab('presence')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'presence'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Presence
              </button>
              <button
                onClick={() => setActiveTab('controls')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-colors ${
                  activeTab === 'controls'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                State
              </button>




            </div>

            <button
              onClick={toggleQuickPanel}
              className="text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* TAB 1: TOOLS ACTION ENGINE */}
          {activeTab === 'tools' ? (
            <div className="space-y-4">
              {/* Metrics Summary */}
              {toolMetrics && (
                <div className="surface-translucent-subtle p-3 rounded-xl border border-white/5 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono text-slate-300">
                    <span className="flex items-center space-x-1.5">
                      <Wrench className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Tools Active: {toolMetrics.enabled_tools}/{toolMetrics.total_tools}</span>
                    </span>
                    <span className="text-[10px] text-emerald-400">
                      Success: {toolMetrics.success_rate}%
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-500 flex justify-between">
                    <span>Executions: {toolMetrics.total_executions}</span>
                    <span>Avg: {toolMetrics.average_duration_ms}ms</span>
                  </div>
                </div>
              )}

              {/* Tool Manifest Plugin List */}
              <div className="space-y-2">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                  Registered Tool Plugins
                </div>
                <div className="grid grid-cols-1 gap-2 max-h-[160px] overflow-y-auto pr-1">
                  {tools.map((t) => (
                    <div
                      key={t.name}
                      className="surface-translucent-subtle p-2.5 rounded-xl border border-white/5 flex items-center justify-between text-xs"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-slate-200">{t.display_name}</span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-slate-400 uppercase">
                            {t.permissions}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 line-clamp-1">{t.description}</p>
                      </div>
                      <button
                        onClick={() => handleToggleTool(t.name, t.enabled)}
                        className={`w-7 h-4 rounded-full transition-colors relative ${
                          t.enabled ? 'bg-cyan-500' : 'bg-slate-700'
                        }`}
                      >
                        <span
                          className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform ${
                            t.enabled ? 'right-0.5' : 'left-0.5'
                          }`}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Execution Activity Log */}
              <div className="space-y-2">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Execution History</span>
                  <Activity className="w-3 h-3 text-cyan-400" />
                </div>
                <div className="space-y-2 max-h-[200px] overflow-y-auto pr-1">
                  {loading ? (
                    <div className="text-xs font-mono text-slate-500 py-4 text-center animate-pulse">
                      Loading tool activity...
                    </div>
                  ) : toolHistory.length === 0 ? (
                    <div className="text-xs font-mono text-slate-500 py-4 text-center">
                      No tool executions recorded yet.
                    </div>
                  ) : (
                    toolHistory.map((h) => (
                      <div
                        key={h.execution_id}
                        className="surface-translucent-subtle p-2.5 rounded-xl border border-white/5 space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-cyan-300 font-medium">
                            {h.tool_name}
                          </span>
                          <span className="flex items-center space-x-1 text-[10px] font-mono">
                            {h.success ? (
                              <CheckCircle className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <AlertTriangle className="w-3 h-3 text-rose-400" />
                            )}
                            <span className={h.success ? 'text-emerald-400' : 'text-rose-400'}>
                              {h.status_code}
                            </span>
                          </span>
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 flex justify-between">
                          <span className="flex items-center space-x-1">
                            <Clock className="w-2.5 h-2.5 text-slate-500" />
                            <span>{h.execution_time_ms}ms</span>
                          </span>
                          <span>{new Date(h.timestamp).toLocaleTimeString()}</span>
                        </div>
                        {h.error && (
                          <div className="text-[10px] font-mono text-rose-300/90 pt-0.5">
                            {h.error}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'memory' ? (
            /* TAB 2: MEMORY ENGINE */
            <div className="space-y-4">
              {memoryMetrics && (
                <div className="surface-translucent-subtle p-3 rounded-xl border border-white/5 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono text-slate-300">
                    <span className="flex items-center space-x-1.5">
                      <Database className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Total Memories: {memoryMetrics.total_memories}</span>
                    </span>
                    <span className="text-[10px] text-emerald-400">
                      Avg Imp: {memoryMetrics.average_importance}
                    </span>
                  </div>
                </div>
              )}

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

              <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                {memories.map((item) => (
                  <div
                    key={item.id}
                    className="surface-translucent-subtle p-3 rounded-xl border border-white/5 space-y-1 group relative"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase text-cyan-400 flex items-center space-x-1">
                        <Tag className="w-2.5 h-2.5" />
                        <span>{item.category.replace('_', ' ')}</span>
                      </span>
                      <button
                        onClick={() => handleDeleteMemory(item.id)}
                        className="text-slate-600 hover:text-rose-400 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <h4 className="text-xs font-medium text-slate-200">{item.title}</h4>
                    <p className="text-[11px] text-slate-400 leading-normal">{item.content}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : activeTab === 'vision' ? (
            /* TAB 3: VISION ENGINE */
            <div className="space-y-4">
              {visionMetrics && (
                <div className="surface-translucent-subtle p-3 rounded-xl border border-white/5 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono text-slate-300">
                    <span className="flex items-center space-x-1.5">
                      <Eye className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Visual Assets: {visionMetrics.images_analyzed + visionMetrics.pdfs_processed}</span>
                    </span>
                    <span className="text-[10px] text-cyan-300 font-mono">
                      Images: {visionMetrics.images_analyzed} | PDFs: {visionMetrics.pdfs_processed}
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-500 flex justify-between">
                    <span>OCR Latency: {visionMetrics.average_ocr_latency_ms}ms</span>
                    <span>Avg Time: {visionMetrics.average_analysis_time_ms}ms</span>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Vision Processing History</span>
                  <Activity className="w-3 h-3 text-cyan-400" />
                </div>
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                  {loading ? (
                    <div className="text-xs font-mono text-slate-500 py-4 text-center animate-pulse">
                      Loading vision activity...
                    </div>
                  ) : visionHistory.length === 0 ? (
                    <div className="text-xs font-mono text-slate-500 py-4 text-center">
                      No visual uploads recorded yet.
                    </div>
                  ) : (
                    visionHistory.map((v) => (
                      <div
                        key={v.id}
                        className="surface-translucent-subtle p-2.5 rounded-xl border border-white/5 space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-cyan-300 font-medium flex items-center space-x-1">
                            {v.file_type.includes('pdf') ? (
                              <FileText className="w-3 h-3 text-cyan-400" />
                            ) : (
                              <Image className="w-3 h-3 text-cyan-400" />
                            )}
                            <span className="truncate max-w-[160px]">{v.filename}</span>
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-slate-400 uppercase">
                            {v.provider}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 line-clamp-2 leading-normal">
                          {v.result_summary}
                        </p>
                        <div className="text-[10px] font-mono text-slate-500 flex justify-between pt-0.5">
                          <span>{v.latency_ms}ms</span>
                          <span>{new Date(v.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'agents' ? (
            /* TAB 4: AGENTS TAB */
            <div className="space-y-5">
              {/* Agent Metrics Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Agents Created</div>
                  <div className="text-base font-mono font-semibold text-cyan-300">
                    {agentMetrics ? agentMetrics.agents_created : 0}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Success Rate</div>
                  <div className="text-base font-mono font-semibold text-emerald-400">
                    {agentMetrics ? `${agentMetrics.success_rate_percent}%` : '100%'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Avg Duration</div>
                  <div className="text-base font-mono font-semibold text-amber-300">
                    {agentMetrics ? `${agentMetrics.average_duration_s}s` : '0s'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Tasks / Agent</div>
                  <div className="text-base font-mono font-semibold text-sky-300">
                    {agentMetrics ? agentMetrics.average_tasks_per_agent : 0}
                  </div>
                </div>
              </div>

              {/* Active Agents List */}
              <div className="space-y-2">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                  <Bot className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Active Agents ({activeAgents.length})</span>
                </div>

                <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                  {activeAgents.length === 0 ? (
                    <div className="text-[11px] font-mono text-slate-500 italic p-3 text-center surface-card rounded-lg border border-white/5">
                      No running agent instances.
                    </div>
                  ) : (
                    activeAgents.map((agt) => (
                      <div key={agt.agent_id} className="surface-card p-3 rounded-lg border border-white/5 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs text-cyan-300 font-semibold">{agt.agent_id}</span>
                          <span className={`text-[9px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                            agt.state === 'RUNNING' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 animate-pulse' :
                            agt.state === 'PAUSED' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                            'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                          }`}>
                            {agt.state}
                          </span>
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 space-y-0.5">
                          <div>Task: <span className="text-slate-200">{agt.current_task || 'Initializing...'}</span></div>
                          <div>Duration: <span className="text-amber-300">{agt.running_duration_s}s</span></div>
                        </div>

                        {/* Controls */}
                        <div className="flex items-center space-x-2 pt-1 border-t border-white/5">
                          {agt.state === 'RUNNING' ? (
                            <button
                              onClick={async () => { await agentsService.pauseAgent(agt.agent_id); fetchData(); }}
                              className="px-2 py-1 rounded bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 text-[9px] font-mono flex items-center space-x-1"
                            >
                              <Pause className="w-3 h-3" /> <span>Pause</span>
                            </button>
                          ) : agt.state === 'PAUSED' ? (
                            <button
                              onClick={async () => { await agentsService.resumeAgent(agt.agent_id); fetchData(); }}
                              className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 text-[9px] font-mono flex items-center space-x-1"
                            >
                              <Play className="w-3 h-3" /> <span>Resume</span>
                            </button>
                          ) : null}
                          <button
                            onClick={async () => { await agentsService.cancelAgent(agt.agent_id); fetchData(); }}
                            className="px-2 py-1 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 text-[9px] font-mono flex items-center space-x-1"
                          >
                            <Square className="w-3 h-3" /> <span>Cancel</span>
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Agent History */}
              <div className="space-y-2 pt-2 border-t border-white/5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>Agent History</span>
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                  {agentHistory.length === 0 ? (
                    <div className="text-[11px] font-mono text-slate-500 italic p-3 text-center surface-card rounded-lg border border-white/5">
                      No agent history logged yet.
                    </div>
                  ) : (
                    agentHistory.map((h, idx) => (
                      <div key={idx} className="surface-card p-2.5 rounded-lg border border-white/5 text-xs space-y-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="font-mono text-cyan-300 font-semibold">{h.agent_id}</span>
                          <span className="text-[9px] font-mono text-slate-400">{h.duration_ms}ms</span>
                        </div>
                        <p className="text-[10px] text-slate-300 line-clamp-2 leading-normal">
                          {h.result_summary}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'voice' ? (
            /* TAB 5: VOICE TAB */
            <div className="space-y-5">
              {/* Voice Metrics Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Sessions</div>
                  <div className="text-base font-mono font-semibold text-cyan-300">
                    {voiceMetrics ? voiceMetrics.total_sessions : 0}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Interruptions</div>
                  <div className="text-base font-mono font-semibold text-amber-400">
                    {voiceMetrics ? voiceMetrics.total_interruptions : 0}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">STT Latency</div>
                  <div className="text-base font-mono font-semibold text-sky-300">
                    {voiceMetrics ? `${voiceMetrics.average_recognition_latency_ms}ms` : '0ms'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">E2E Latency</div>
                  <div className="text-base font-mono font-semibold text-emerald-400">
                    {voiceMetrics ? `${voiceMetrics.average_e2e_latency_ms}ms` : '0ms'}
                  </div>
                </div>
              </div>

              {/* Provider Status */}
              <div className="surface-card p-3 rounded-lg border border-white/5 space-y-2">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span className="flex items-center space-x-1">
                    <Mic className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Voice Providers</span>
                  </span>
                  <span className="text-emerald-400 font-bold">{voiceStatus ? voiceStatus.state : 'IDLE'}</span>
                </div>
                <div className="text-xs font-mono space-y-1 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400">TTS Provider:</span>
                    <span className="text-cyan-300 font-semibold">{voiceStatus?.speaker.provider || 'browser'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">STT Provider:</span>
                    <span className="text-cyan-300 font-semibold">{voiceStatus?.transcriber.provider || 'browser'}</span>
                  </div>
                </div>
              </div>

              {/* Session Controls */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={async () => { await voiceEngineService.startSession(true); fetchData(); }}
                  className="flex-1 py-2 px-3 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/30 text-xs font-mono font-semibold flex items-center justify-center space-x-1.5 transition-all"
                >
                  <Volume2 className="w-3.5 h-3.5" /> <span>Start Continuous</span>
                </button>
                <button
                  onClick={async () => { await voiceEngineService.triggerInterruption(); fetchData(); }}
                  className="py-2 px-3 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 text-xs font-mono font-semibold flex items-center justify-center space-x-1.5 transition-all"
                >
                  <Square className="w-3.5 h-3.5" /> <span>Interrupt</span>
                </button>
              </div>

              {/* Voice History */}
              <div className="space-y-2 pt-2 border-t border-white/5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>Voice Sessions History</span>
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                  {voiceHistory.length === 0 ? (
                    <div className="text-[11px] font-mono text-slate-500 italic p-3 text-center surface-card rounded-lg border border-white/5">
                      No voice session history logged yet.
                    </div>
                  ) : (
                    voiceHistory.map((vh, idx) => (
                      <div key={idx} className="surface-card p-2.5 rounded-lg border border-white/5 text-xs space-y-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="font-mono text-cyan-300 font-semibold">{vh.session_id}</span>
                          <span className="text-[9px] font-mono text-amber-300">{vh.duration_s}s</span>
                        </div>
                        <p className="text-[10px] text-slate-300 line-clamp-2 leading-normal">
                          {vh.summary}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'router' ? (
            /* TAB 6: ROUTER TAB */
            <div className="space-y-5">
              {/* Router Metrics Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Requests</div>
                  <div className="text-base font-mono font-semibold text-cyan-300">
                    {routerMetrics ? routerMetrics.total_requests : 0}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Accuracy</div>
                  <div className="text-base font-mono font-semibold text-emerald-400">
                    {routerMetrics ? `${routerMetrics.routing_accuracy}%` : '100%'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Avg Latency</div>
                  <div className="text-base font-mono font-semibold text-sky-300">
                    {routerMetrics ? `${routerMetrics.average_routing_latency_ms}ms` : '0ms'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Tool Success</div>
                  <div className="text-base font-mono font-semibold text-amber-400">
                    {routerMetrics ? `${routerMetrics.tool_success_rate}%` : '100%'}
                  </div>
                </div>
              </div>

              {/* Status & Engine Info */}
              <div className="surface-card p-3 rounded-lg border border-white/5 space-y-2">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span className="flex items-center space-x-1">
                    <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Cognitive Router Status</span>
                  </span>
                  <span className="text-emerald-400 font-bold">{routerStatus ? routerStatus.status : 'healthy'}</span>
                </div>
                <div className="text-xs font-mono space-y-1 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Engine:</span>
                    <span className="text-cyan-300 font-semibold">{routerStatus?.engine || 'Cognitive Router v1.0'}</span>
                  </div>
                </div>
              </div>

              {/* Decision Trace History */}
              <div className="space-y-2 pt-2 border-t border-white/5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>Decision Trace Log</span>
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                  {routerHistory.length === 0 ? (
                    <div className="text-[11px] font-mono text-slate-500 italic p-3 text-center surface-card rounded-lg border border-white/5">
                      No router decision trace logged yet.
                    </div>
                  ) : (
                    routerHistory.map((rh, idx) => (
                      <div key={idx} className="surface-card p-2.5 rounded-lg border border-white/5 text-xs space-y-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="font-mono text-cyan-300 font-semibold">{rh.chosen_engine}</span>
                          <span className="text-[9px] font-mono text-emerald-400">{(rh.confidence * 100).toFixed(0)}% conf</span>
                        </div>
                        <p className="text-[10px] text-slate-300 line-clamp-1 leading-normal font-mono">
                          Req: "{rh.request}"
                        </p>
                        <div className="flex justify-between text-[9px] font-mono text-slate-400">
                          <span>Format: {rh.formatter_used}</span>
                          <span>{rh.execution_time_ms}ms</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'presence' ? (
            /* TAB 7: PRESENCE ENGINE TAB */
            <div className="space-y-5">
              {/* Score & Awareness Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Presence Score</div>
                  <div className="text-base font-mono font-semibold text-cyan-300">
                    {presenceScore ? `${presenceScore.overall_score}%` : '100%'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Verification Rate</div>
                  <div className="text-base font-mono font-semibold text-emerald-400">
                    {presenceScore ? `${presenceScore.verification}%` : '100%'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Awareness</div>
                  <div className="text-base font-mono font-semibold text-sky-300">
                    {presenceScore ? `${presenceScore.awareness}%` : '100%'}
                  </div>
                </div>
                <div className="surface-card p-3 rounded-lg border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Attention Stability</div>
                  <div className="text-base font-mono font-semibold text-amber-400">
                    {presenceScore ? `${presenceScore.attention_stability}%` : '98%'}
                  </div>
                </div>
              </div>

              {/* Ongoing Awareness Info */}
              <div className="surface-card p-3 rounded-lg border border-white/5 space-y-2">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span className="flex items-center space-x-1">
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Ongoing Companion Awareness</span>
                  </span>
                  <span className="text-emerald-400 font-bold">{presenceState?.conversation_mode || 'active'}</span>
                </div>
                <div className="text-xs font-mono space-y-1 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Focus Topic:</span>
                    <span className="text-cyan-300 font-semibold truncate max-w-[180px]">{presenceState?.current_topic || 'General Conversation'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Current Task:</span>
                    <span className="text-sky-300 truncate max-w-[180px]">{presenceState?.current_task || 'None'}</span>
                  </div>
                </div>
              </div>

              {/* Working Memory Workspace */}
              <div className="space-y-2 pt-2 border-t border-white/5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                  <Compass className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Working Memory Workspace</span>
                </div>
                <div className="surface-card p-2.5 rounded-lg border border-white/5 text-xs space-y-1 font-mono">
                  {Object.keys(workingMemory).length === 0 ? (
                    <div className="text-[11px] text-slate-500 italic text-center p-2">Workspace empty.</div>
                  ) : (
                    Object.entries(workingMemory).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-[10px]">
                        <span className="text-slate-400">{k}:</span>
                        <span className="text-cyan-300 font-semibold truncate max-w-[170px]">{String(v)}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* TAB 8: CORE STATE CONTROLS */




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
            <span>v0.4 Action Engine</span>
          </div>
        </div>
      </div>
    </div>
  );
};
