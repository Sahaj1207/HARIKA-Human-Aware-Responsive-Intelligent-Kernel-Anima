export interface PerformanceMetrics {
  fps: number;
  renderCount: number;
  memoryUsageMb: number;
  apiLatencyMs: number;
  streamingLatencyMs: number;
  voiceLatencyMs: number;
  visionLatencyMs: number;
  agentExecutionMs: number;
}

class PerformanceMonitor {
  private renderCount = 0;
  private fps = 60;
  private frameCount = 0;
  private lastFpsUpdate = performance.now();

  private latencies: Partial<PerformanceMetrics> = {
    apiLatencyMs: 45.0,
    streamingLatencyMs: 120.0,
    voiceLatencyMs: 85.0,
    visionLatencyMs: 150.0,
    agentExecutionMs: 95.0,
  };

  constructor() {
    if (typeof window !== 'undefined') {
      this.loopFps();
    }
  }

  public recordRender(): void {
    this.renderCount++;
  }

  public setLatency(key: keyof PerformanceMetrics, valueMs: number): void {
    this.latencies[key] = valueMs;
  }

  public getMetrics(): PerformanceMetrics {
    const memoryMb =
      typeof performance !== 'undefined' && (performance as any).memory
        ? Math.round((performance as any).memory.usedJSHeapSize / (1024 * 1024))
        : 48;

    return {
      fps: this.fps,
      renderCount: this.renderCount,
      memoryUsageMb: memoryMb,
      apiLatencyMs: this.latencies.apiLatencyMs || 0,
      streamingLatencyMs: this.latencies.streamingLatencyMs || 0,
      voiceLatencyMs: this.latencies.voiceLatencyMs || 0,
      visionLatencyMs: this.latencies.visionLatencyMs || 0,
      agentExecutionMs: this.latencies.agentExecutionMs || 0,
    };
  }

  private loopFps = (): void => {
    this.frameCount++;
    const now = performance.now();
    if (now - this.lastFpsUpdate >= 1000) {
      this.fps = Math.round((this.frameCount * 1000) / (now - this.lastFpsUpdate));
      this.frameCount = 0;
      this.lastFpsUpdate = now;
    }
    requestAnimationFrame(this.loopFps);
  };
}

export const performanceMonitor = new PerformanceMonitor();
