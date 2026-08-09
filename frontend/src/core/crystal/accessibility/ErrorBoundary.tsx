import { Component, ErrorInfo, ReactNode } from 'react';

import { AlertCircle, RefreshCw } from 'lucide-react';
import { CrystalButton } from '../components/CrystalButton';
import { CrystalCard } from '../components/CrystalCard';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[CrystalErrorBoundary] UI Crash Caught:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-slate-950/90 backdrop-blur-md">
          <CrystalCard className="max-w-md w-full p-6 border-rose-500/40 text-center space-y-4 shadow-2xl">
            <div className="flex justify-center">
              <div className="p-3 rounded-full bg-rose-500/20 text-rose-400">
                <AlertCircle className="w-8 h-8" />
              </div>
            </div>
            <div>
              <h2 className="text-base font-mono font-bold uppercase text-slate-100">Crystal Core UI Exception</h2>
              <p className="text-xs font-mono text-slate-400 mt-1">
                {this.state.error?.message || 'An unexpected rendering error occurred.'}
              </p>
            </div>
            <div className="pt-2">
              <CrystalButton variant="primary" icon={<RefreshCw className="w-4 h-4" />} onClick={this.handleReset}>
                Recover Component State
              </CrystalButton>
            </div>
          </CrystalCard>
        </div>
      );
    }

    return this.props.children;
  }
}
