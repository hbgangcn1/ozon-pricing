import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { toast } from 'sonner';
import { overflowAPI } from '../services/api';

// Priority 3: documents non-obvious cross-cutting contract for OpenSpec change add-pro-trial-overflow.
// Auto-popups once per browser session (sessionStorage flag) when has_open_window=true.
// Submission consumes the open 48h window server-side (close_reason='reselected').
const SESSION_FLAG = 'overflow_reselect_modal_shown';

export default function OverflowReselectModal({ items, onCompleted }) {
  const [status, setStatus] = useState(null);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await overflowAPI.getStatus();
        if (cancelled) return;
        setStatus(data);
        if (data?.has_open_window && !sessionStorage.getItem(SESSION_FLAG)) {
          setOpen(true);
          sessionStorage.setItem(SESSION_FLAG, '1');
        }
      } catch (_) {
        // Priority 1: 404/无窗口/未登录均静默,不打扰用户
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const limit = status?.new_limit ?? 0;

  const candidates = useMemo(
    () => (Array.isArray(items) ? items : []).filter((it) => it && it.is_active === 1),
    [items],
  );

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (limit > 0 && selected.size > limit) {
      toast.error(`最多保留 ${limit} 条规则`);
      return;
    }
    setSubmitting(true);
    try {
      await overflowAPI.reselect(Array.from(selected));
      toast.success('已重新选择');
      setOpen(false);
      onCompleted?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!status?.has_open_window) return null;

  const overLimit = limit > 0 && selected.size > limit;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>请重新选择物流规则</DialogTitle>
          <DialogDescription>
            您的可用物流规则数量已超出当前套餐限制（{limit}）。请在 48 小时内勾选要保留的规则，未勾选的将被暂停。
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-72 overflow-y-auto space-y-2 py-2">
          {candidates.length === 0 ? (
            <div className="text-sm text-text-muted">暂无可选物流规则</div>
          ) : (
            candidates.map((it) => (
              <label
                key={it.id}
                className="flex items-center gap-3 rounded-md border border-surface-high px-3 py-2 cursor-pointer hover:bg-surface-high/40"
              >
                <Checkbox
                  checked={selected.has(it.id)}
                  onCheckedChange={() => toggle(it.id)}
                  aria-label={`选择 ${it.name}`}
                />
                <span className="flex-1 text-sm font-medium text-text-primary truncate">{it.name}</span>
                {it.disabled_by_overflow === 1 && (
                  <span className="text-xs text-text-muted">已暂停</span>
                )}
              </label>
            ))
          )}
        </div>

        <div className={`text-xs ${overLimit ? 'text-status-error' : 'text-text-muted'}`}>
          已选 {selected.size} / 上限 {limit}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={submitting}>
            稍后处理
          </Button>
          <Button onClick={handleSubmit} disabled={submitting || overLimit}>
            {submitting ? '提交中...' : '提交'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
