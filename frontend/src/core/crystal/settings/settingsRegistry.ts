import React from 'react';

export interface SettingsPageContribution {
  id: string;
  label: string;
  category: 'general' | 'ai_engines' | 'system' | 'developer';
  icon?: React.ReactNode;
  component: React.ComponentType;
}

class SettingsRegistry {
  private pages: Map<string, SettingsPageContribution> = new Map();

  public registerPage(page: SettingsPageContribution): void {
    this.pages.set(page.id, page);
  }

  public getPages(): SettingsPageContribution[] {
    return Array.from(this.pages.values());
  }

  public getPage(id: string): SettingsPageContribution | undefined {
    return this.pages.get(id);
  }
}

export const settingsRegistry = new SettingsRegistry();
