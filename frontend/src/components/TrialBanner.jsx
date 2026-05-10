import React, { useEffect, useState, useCallback } from 'react';
import { Alert, AlertDescription } from './ui/alert';
import { Button } from './ui/button';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import { trialAPI, authAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';

const POLL_INTERVAL_MS = 60_000;
const DISMISS_DURATION_MS = 24 * 3600 * 1000;
const DISMISS_KEY = 'trial_banner_dismissed_until';

const SECONDS_PER_DAY = 86_400;

function isDismissed() {
  const raw = localStorage.getItem(DISMISS_KEY);
  if (!raw) return false;
  const until = Number.parseInt(raw, 10);
  if (!Number.isFinite(until)) return false;
  return Date.now() < until;
}

export default function TrialBanner() {
  const [status, setStatus] = useState(null);
  const [, forceTick] = useState(0);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await trialAPI.getStatus();
      setStatus(data);
    } catch (_) {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleClaim = async () => {
    try {
      await trialAPI.claim();
      toast.success('已开启 7 天专业版试用');
      await fetchStatus();
      try {
        const me = await authAPI.getMe();
        useAuthStore.getState().setUser(me);
      } catch (_) {
        void 0;
      }
    } catch (err) {
      toast.error(err?.userMessage || err?.response?.data?.detail || '领取试用失败');
    }
  };

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now() + DISMISS_DURATION_MS));
    forceTick((n) => n + 1);
  };

  if (!status) return null;
  if (isDismissed()) return null;

  if (status.eligible && !status.in_trial && !status.trial_used) {
    return (
      <Alert className="mb-4 flex items-center justify-between">
        <AlertDescription className="text-text-primary">
          升级体验：免费开启 7 天专业版试用
        </AlertDescription>
        <Button size="sm" onClick={handleClaim}>开始 7 天专业版试用</Button>
      </Alert>
    );
  }

  if (status.in_trial) {
    const remainingDays = Math.max(1, Math.ceil((status.remaining_seconds || 0) / SECONDS_PER_DAY));
    return (
      <Alert className="mb-4 flex items-center justify-between">
        <AlertDescription className="text-text-primary">
          专业版试用中，剩余 {remainingDays} 天
        </AlertDescription>
        <Button
          size="icon"
          variant="ghost"
          onClick={handleDismiss}
          aria-label="关闭试用提示"
        >
          <X className="h-4 w-4" />
        </Button>
      </Alert>
    );
  }

  return null;
}
