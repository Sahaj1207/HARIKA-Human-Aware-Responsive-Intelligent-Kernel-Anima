import React from 'react';

export interface CommandItemContribution {
  id: string;
  label: string;
  category: 'navigation' | 'voice' | 'tools' | 'developer' | 'system';
  shortcut?: string;
  icon?: React.ReactNode;
  action: () => void;
}

class CommandRegistry {
  private commands: Map<string, CommandItemContribution> = new Map();

  public registerCommand(cmd: CommandItemContribution): void {
    this.commands.set(cmd.id, cmd);
  }

  public getCommands(): CommandItemContribution[] {
    return Array.from(this.commands.values());
  }

  public executeCommand(id: string): boolean {
    const cmd = this.commands.get(id);
    if (cmd) {
      cmd.action();
      return true;
    }
    return false;
  }
}

export const commandRegistry = new CommandRegistry();
