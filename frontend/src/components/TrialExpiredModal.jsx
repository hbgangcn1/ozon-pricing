import React, { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { useNavigate } from 'react-router-dom';
import { trialAPI } from '../services/api';

// Priority 3: documents non-obvious cross-cutting contract for OpenSpec change add-pro-trial-overflow.
// Pops once per (user × trial_expires_at) within 48h after trial expiry; key persists in localStorage.
const SEEN_KEY_PREFIX = 'trial_expired_modal_seen_';
const WINDOW_SECONDS = 48 * 3600;

export default function TrialExpiredModal() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await trialAPI.getStatus();
        if (cancelled) return;
        setStatus(data);
        const expiresAt = Number(data?.trial_expires_at || 0);
        const nowSec = Math.floor(Date.now() / 1000);
        const elapsed = nowSec - expiresAt;
        const inWindow = expiresAt > 0 && elapsed >= 0 && elapsed < WINDOW_SECONDS;
        const seenKey = `${SEEN_KEY_PREFIX}${expiresAt}`;
        if (
          data && !data.in_trial && data.trial_used && inWindow
          && !localStorage.getItem(seenKey)
        ) {
          setOpen(true);
        }
      } catch (_) {
        // Priority 1: 静默,不打扰用户
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleClose = () => {
    const expiresAt = Number(status?.trial_expires_at || 0);
    if (expiresAt > 0) {
      localStorage.setItem(`${SEEN_KEY_PREFIX}${expiresAt}`, '1');
    }
    setOpen(false);
  };

  const handleUpgrade = () => {
    handleClose();
    navigate('/subscriptions');
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>专业版试用已结束</DialogTitle>
          <DialogDescription>
            您的 7 天专业版试用已过期。升级到专业版可继续使用全部物流规则。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>稍后再说</Button>
          <Button onClick={handleUpgrade}>立即升级</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
