import React, { useState, useEffect } from 'react';
import { notificationService } from './notificationService';
import { ToastItem, CrystalToast } from '../components/CrystalToast';

export const NotificationToastContainer: React.FC = () => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    return notificationService.subscribe((list) => setToasts(list));
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col space-y-2 max-w-sm w-full pointer-events-auto">
      {toasts.map((toast) => (
        <CrystalToast key={toast.id} toast={toast} onDismiss={(id) => notificationService.dismiss(id)} />
      ))}
    </div>
  );
};
