import { ToastItem } from '../components/CrystalToast';

type ToastListener = (toasts: ToastItem[]) => void;

class NotificationService {
  private toasts: ToastItem[] = [];
  private listeners: Set<ToastListener> = new Set();

  public subscribe(listener: ToastListener): () => void {
    this.listeners.add(listener);
    listener([...this.toasts]);
    return () => this.listeners.delete(listener);
  }

  public show(type: ToastItem['type'], title: string, message?: string, autoDismissMs = 4000): string {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    const toast: ToastItem = { id, type, title, message };
    this.toasts = [...this.toasts, toast];
    this.notify();

    if (autoDismissMs > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, autoDismissMs);
    }

    return id;
  }

  public showSuccess(title: string, message?: string): string {
    return this.show('success', title, message);
  }

  public showWarning(title: string, message?: string): string {
    return this.show('warning', title, message);
  }

  public showError(title: string, message?: string): string {
    return this.show('error', title, message);
  }

  public showInfo(title: string, message?: string): string {
    return this.show('info', title, message);
  }

  public dismiss(id: string): void {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this.notify();
  }

  private notify(): void {
    this.listeners.forEach((listener) => listener([...this.toasts]));
  }
}

export const notificationService = new NotificationService();
