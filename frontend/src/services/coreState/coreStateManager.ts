import { CoreState } from '@/types';
import { useHARIKAStore } from '@/store/useHARIKAStore';

type TransitionMap = {
  [K in CoreState]?: CoreState[];
};

class CoreStateManager {
  // Allowed state machine transitions matrix
  private allowedTransitions: TransitionMap = {
    booting: ['idle', 'error'],
    idle: ['listening', 'thinking', 'sleeping', 'error'],
    listening: ['thinking', 'idle', 'error'],
    thinking: ['speaking', 'idle', 'error'],
    speaking: ['idle', 'thinking', 'error'],
    sleeping: ['idle', 'error'],
    error: ['idle', 'booting'],
  };

  /**
   * Validates and executes an event-driven state transition.
   */
  public transitionTo(targetState: CoreState): boolean {
    const currentState = useHARIKAStore.getState().coreState;

    if (currentState === targetState) return true;

    // 'error' state can be entered from any state
    if (targetState === 'error') {
      useHARIKAStore.getState().setCoreState('error');
      return true;
    }

    const validTargets = self_allowed_transitions(currentState, this.allowedTransitions);

    if (validTargets.includes(targetState)) {
      useHARIKAStore.getState().setCoreState(targetState);
      return true;
    } else {
      console.warn(
        `[CoreStateManager] Invalid transition attempted: '${currentState}' -> '${targetState}'. Fallback applied.`
      );
      // Fallback state application for resilience
      useHARIKAStore.getState().setCoreState(targetState);
      return false;
    }
  }
}

function self_allowed_transitions(state: CoreState, map: TransitionMap): CoreState[] {
  return map[state] || ['idle', 'error'];
}

export const coreStateManager = new CoreStateManager();
