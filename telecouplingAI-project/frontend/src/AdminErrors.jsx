import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, Archive, CheckCircle2, ChevronLeft, ChevronRight,
  Clock3, Download, Filter, LogOut, RefreshCw, Search, Server,
  ShieldCheck, User2, X,
} from 'lucide-react';

const API_ROOT = '/api/admin';
const STATUS_OPTIONS = ['new', 'acknowledged', 'resolved', 'ignored'];
const CATEGORY_OPTIONS = [
  'validation', 'application', 'capacity', 'external', 'infrastructure',
];
const SEVERITY_OPTIONS = ['info', 'warning', 'error', 'critical'];

function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(new Date(value));
}

function severityClasses(severity) {
  return {
    critical: 'bg-red-100 text-red-800 border-red-200',
    error: 'bg-rose-50 text-rose-700 border-rose-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    info: 'bg-blue-50 text-blue-700 border-blue-200',
  }[severity] || 'bg-gray-100 text-gray-700 border-gray-200';
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });
  const isJson = response.headers.get('content-type')?.includes('application/json');
  const body = isJson ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(body?.detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

function AdminLogin({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const session = await apiFetch('/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      onLogin(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-400">
          <ShieldCheck size={28} />
        </div>
        <h1 className="text-2xl font-semibold text-white">CSIS Error Registry</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          Restricted administrative access. Login activity is audited.
        </p>
        <form onSubmit={submit} className="mt-8 space-y-4">
          <label className="block">
            <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Username
            </span>
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none focus:border-blue-500"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Password
            </span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none focus:border-blue-500"
            />
          </label>
          {error && (
            <div className="flex gap-2 rounded-xl border border-red-900/60 bg-red-950/50 p-3 text-sm text-red-300">
              <AlertCircle size={18} className="shrink-0" /> {error}
            </div>
          )}
          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full rounded-xl bg-blue-600 px-4 py-3 font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}

function FilterSelect({ value, onChange, children, label }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
      >
        {children}
      </select>
    </label>
  );
}

function OccurrenceCard({ occurrence, csrfToken, onRefresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const preserve = async () => {
    setBusy(true);
    setError('');
    try {
      await apiFetch(`/occurrences/${occurrence.event_id}/preserve`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      await onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-mono text-xs text-slate-500">{occurrence.event_id}</div>
          <div className="mt-1 text-sm font-medium text-slate-900">
            {formatDate(occurrence.occurred_at)}
          </div>
        </div>
        <div className="flex gap-2">
          {occurrence.preserved ? (
            <a
              href={`${API_ROOT}/occurrences/${occurrence.event_id}/evidence`}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-700"
            >
              <Download size={14} /> Download evidence
            </a>
          ) : (
            <button
              onClick={preserve}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Archive size={14} /> {busy ? 'Preserving…' : 'Preserve evidence'}
            </button>
          )}
        </div>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['Environment', occurrence.environment],
          ['Release', occurrence.release_version],
          ['Session', occurrence.session_id],
          ['Task', occurrence.task_id],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-1 break-all font-mono text-xs text-slate-800">{value || '—'}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 rounded-xl bg-slate-950 p-4">
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-200">
          {occurrence.traceback || occurrence.internal_message}
        </pre>
      </div>
      {occurrence.files?.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Input file metadata
          </h4>
          <div className="mt-2 overflow-hidden rounded-xl border border-slate-200">
            {occurrence.files.map((file, index) => (
              <div key={`${file.name}-${index}`} className="flex justify-between gap-4 border-b border-slate-100 px-3 py-2 text-xs last:border-0">
                <span className="truncate font-medium text-slate-700">{file.name}</span>
                <span className="shrink-0 text-slate-500">
                  {(file.size_bytes / 1024 / 1024).toFixed(2)} MiB
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

function ErrorDetail({ fingerprint, csrfToken, onClose, onUpdated }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ status: 'new', assignee: '', admin_notes: '' });

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await apiFetch(`/errors/${fingerprint}`);
      setDetail(result);
      setForm({
        status: result.group.status,
        assignee: result.group.assignee || '',
        admin_notes: result.group.admin_notes || '',
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fingerprint]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/errors/${fingerprint}`, {
        method: 'PATCH',
        headers: { 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(form),
      });
      await load();
      onUpdated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30 backdrop-blur-sm">
      <button aria-label="Close details" className="flex-1" onClick={onClose} />
      <section className="h-full w-full max-w-4xl overflow-y-auto bg-slate-50 shadow-2xl">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-6 py-4 backdrop-blur">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">Error detail</p>
            <p className="mt-1 font-mono text-xs text-slate-500">{fingerprint}</p>
          </div>
          <button onClick={onClose} className="rounded-full p-2 text-slate-500 hover:bg-slate-100">
            <X size={20} />
          </button>
        </header>
        <div className="space-y-5 p-6">
          {loading && <p className="text-sm text-slate-500">Loading error details…</p>}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          )}
          {detail && (
            <>
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900">{detail.group.title}</h2>
                    <p className="mt-2 text-sm text-slate-500">
                      {detail.group.occurrence_count} occurrence(s), first seen {formatDate(detail.group.first_seen)}
                    </p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${severityClasses(detail.group.severity)}`}>
                    {detail.group.severity}
                  </span>
                </div>
                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  <FilterSelect label="Status" value={form.status} onChange={(status) => setForm({ ...form, status })}>
                    {STATUS_OPTIONS.map((value) => <option key={value}>{value}</option>)}
                  </FilterSelect>
                  <label className="block md:col-span-2">
                    <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">Assignee</span>
                    <input
                      value={form.assignee}
                      onChange={(event) => setForm({ ...form, assignee: event.target.value })}
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                      placeholder="Admin username or team"
                    />
                  </label>
                </div>
                <label className="mt-4 block">
                  <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">Admin notes</span>
                  <textarea
                    value={form.admin_notes}
                    onChange={(event) => setForm({ ...form, admin_notes: event.target.value })}
                    rows={4}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                    placeholder="Diagnosis, resolution, linked issue, or follow-up"
                  />
                </label>
                <button
                  onClick={save}
                  disabled={saving}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                >
                  <CheckCircle2 size={16} /> {saving ? 'Saving…' : 'Save workflow status'}
                </button>
              </div>
              <div className="space-y-4">
                {detail.occurrences.map((occurrence) => (
                  <OccurrenceCard
                    key={occurrence.event_id}
                    occurrence={occurrence}
                    csrfToken={csrfToken}
                    onRefresh={load}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

function AdminDashboard({ session, onLogout }) {
  const [filters, setFilters] = useState({
    search: '', environment: '', tool: '', category: '',
    severity: '', status: 'new', hours: '24',
  });
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: '50' });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return params.toString();
  }, [filters, page]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await apiFetch(`/errors?${query}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => { load(); }, [load]);

  const setFilter = (key, value) => {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const logout = async () => {
    try {
      await apiFetch('/logout', {
        method: 'POST',
        headers: { 'X-CSRF-Token': session.csrf_token },
      });
    } finally {
      onLogout();
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-800 bg-slate-950 text-white">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400">
              <ShieldCheck size={22} />
            </div>
            <div>
              <h1 className="font-semibold">CSIS Error Registry</h1>
              <p className="text-xs text-slate-400">Structured errors, evidence, and resolution workflow</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="hidden items-center gap-2 text-slate-300 sm:flex">
              <User2 size={16} /> {session.username}
            </span>
            <button onClick={logout} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 px-3 py-2 text-slate-300 hover:bg-slate-800">
              <LogOut size={16} /> Logout
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1500px] space-y-5 p-6">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Matching groups</p>
            <p className="mt-2 text-3xl font-semibold">{data.total}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Current window</p>
            <p className="mt-2 flex items-center gap-2 text-xl font-semibold"><Clock3 size={20} /> {filters.hours} hours</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Environment</p>
            <p className="mt-2 flex items-center gap-2 text-xl font-semibold"><Server size={20} /> {filters.environment || 'All'}</p>
          </div>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold"><Filter size={18} /> Filters</h2>
            <button onClick={load} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Refresh">
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-8">
            <label className="relative block md:col-span-2">
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">Search</span>
              <Search size={16} className="absolute bottom-2.5 left-3 text-slate-400" />
              <input
                value={filters.search}
                onChange={(event) => setFilter('search', event.target.value)}
                className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400"
                placeholder="Error code, tool, title, fingerprint"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">Tool</span>
              <input
                value={filters.tool}
                onChange={(event) => setFilter('tool', event.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                placeholder="Exact tool name"
              />
            </label>
            <FilterSelect label="Environment" value={filters.environment} onChange={(value) => setFilter('environment', value)}>
              <option value="">All</option><option value="gcp">GCP</option><option value="msu">MSU</option><option value="local">Local</option>
            </FilterSelect>
            <FilterSelect label="Category" value={filters.category} onChange={(value) => setFilter('category', value)}>
              <option value="">All</option>{CATEGORY_OPTIONS.map((value) => <option key={value}>{value}</option>)}
            </FilterSelect>
            <FilterSelect label="Severity" value={filters.severity} onChange={(value) => setFilter('severity', value)}>
              <option value="">All</option>{SEVERITY_OPTIONS.map((value) => <option key={value}>{value}</option>)}
            </FilterSelect>
            <FilterSelect label="Status" value={filters.status} onChange={(value) => setFilter('status', value)}>
              <option value="">All</option>{STATUS_OPTIONS.map((value) => <option key={value}>{value}</option>)}
            </FilterSelect>
            <FilterSelect label="Time range" value={filters.hours} onChange={(value) => setFilter('hours', value)}>
              <option value="24">24 hours</option><option value="168">7 days</option><option value="720">30 days</option><option value="8760">1 year</option>
            </FilterSelect>
          </div>
        </section>

        {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Error</th>
                  <th className="px-4 py-3">Tool / service</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Occurrences</th>
                  <th className="px-4 py-3">Affected sessions</th>
                  <th className="px-4 py-3">Last seen</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((item) => (
                  <tr key={item.fingerprint} onClick={() => setSelected(item.fingerprint)} className="cursor-pointer hover:bg-blue-50/50">
                    <td className="max-w-xl px-5 py-4">
                      <div className="flex items-start gap-3">
                        <span className={`mt-0.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${severityClasses(item.severity)}`}>{item.severity}</span>
                        <div>
                          <p className="line-clamp-2 font-medium text-slate-900">{item.title}</p>
                          <p className="mt-1 font-mono text-[11px] text-slate-400">{item.error_code}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <p className="font-medium">{item.tool || '—'}</p>
                      <p className="text-xs text-slate-500">{item.service}</p>
                    </td>
                    <td className="px-4 py-4 capitalize text-slate-600">{item.category}</td>
                    <td className="px-4 py-4 font-semibold">{item.occurrence_count}</td>
                    <td className="px-4 py-4">{item.affected_sessions}</td>
                    <td className="px-4 py-4 text-xs text-slate-500">{formatDate(item.last_seen)}</td>
                    <td className="px-4 py-4 capitalize">{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && data.items.length === 0 && (
            <div className="p-12 text-center text-sm text-slate-500">No error groups match these filters.</div>
          )}
          {loading && <div className="p-12 text-center text-sm text-slate-500">Loading error registry…</div>}
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-sm">
            <span className="text-slate-500">Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-lg border p-2 disabled:opacity-30"><ChevronLeft size={16} /></button>
              <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="rounded-lg border p-2 disabled:opacity-30"><ChevronRight size={16} /></button>
            </div>
          </div>
        </section>
      </main>
      {selected && (
        <ErrorDetail
          fingerprint={selected}
          csrfToken={session.csrf_token}
          onClose={() => setSelected('')}
          onUpdated={load}
        />
      )}
    </div>
  );
}

export default function AdminErrors() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/session')
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-sm text-slate-400">Checking Admin session…</div>;
  }
  if (!session) return <AdminLogin onLogin={setSession} />;
  return <AdminDashboard session={session} onLogout={() => setSession(null)} />;
}
