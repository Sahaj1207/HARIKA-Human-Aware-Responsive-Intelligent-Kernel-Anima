import React from 'react';

export interface DiagnosticsCardContribution {
  id: string;
  title: string;
  category: 'ai_engine' | 'performance' | 'system';
  component: React.ComponentType;
}

class DiagnosticsRegistry {
  private cards: Map<string, DiagnosticsCardContribution> = new Map();

  public registerCard(card: DiagnosticsCardContribution): void {
    this.cards.set(card.id, card);
  }

  public getCards(): DiagnosticsCardContribution[] {
    return Array.from(this.cards.values());
  }
}

export const diagnosticsRegistry = new DiagnosticsRegistry();
