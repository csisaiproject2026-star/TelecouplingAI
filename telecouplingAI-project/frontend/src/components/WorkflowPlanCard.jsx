import { useEffect, useMemo, useState } from 'react';
import { ListChecks, Check, Sparkles, Plus, Upload, CornerDownRight, Settings2, GitBranch } from 'lucide-react';

// Visual identity per telecoupling component (5-component framework).
const COMPONENT = {
  systems: { icon: '🗺️', label: 'Systems', cls: 'bg-blue-50 text-blue-600 border-blue-200' },
  agents:  { icon: '👥', label: 'Agents',  cls: 'bg-purple-50 text-purple-600 border-purple-200' },
  flows:   { icon: '➡️', label: 'Flows',   cls: 'bg-teal-50 text-teal-600 border-teal-200' },
  causes:  { icon: '🔬', label: 'Causes',  cls: 'bg-amber-50 text-amber-600 border-amber-200' },
  effects: { icon: '🌍', label: 'Effects', cls: 'bg-green-50 text-green-600 border-green-200' },
};
const comp = (c) => COMPONENT[c] || { icon: '•', label: c || '', cls: 'bg-gray-50 text-gray-500 border-gray-200' };
const FILE_KIND = { table: 'CSV', vector: 'Vector', raster: 'Raster', html: 'HTML', 'shapefile-set': 'Shapefile' };

/**
 * Interactive workflow plan card (② structure diagram + ③ tools & example inputs + ④ selection).
 * The high-level intro text (①) is a separate text block rendered above this card.
 *
 * @param {{plan:object, valid:boolean, errors:string[], toolSpecs:object, onConfirm:(msg:string)=>void}} props
 */
export default function WorkflowPlanCard({ plan, valid = true, errors = [], toolSpecs = {}, onConfirm }) {
  const steps = plan?.steps || [];
  const requiredInputs = plan?.required_inputs || [];

  const [checked, setChecked] = useState(() => new Set(steps.map(s => s.id)));
  const [supplement, setSupplement] = useState('');
  const [submitted, setSubmitted] = useState(false);   // Confirm & run was clicked
  const [replanning, setReplanning] = useState(false); // Add & re-plan was clicked (NOT a submit)
  // Either action supersedes this card, so it stops accepting input — but only a
  // real Confirm shows "Submitted". Re-plan just spawns a fresh card below.
  const locked = submitted || replanning;

  // Re-sync selection whenever the plan's step set changes (e.g. a re-plan reuses
  // this component instance). Without this, stale ids from a previous plan could
  // make the count exceed the step total (the "7 / 5" bug).
  const stepKey = useMemo(() => steps.map(s => s.id).join('|'), [steps]);
  useEffect(() => {
    setChecked(new Set(steps.map(s => s.id)));
    setSubmitted(false);
    setReplanning(false);
  }, [stepKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const stepById = useMemo(() => Object.fromEntries(steps.map(s => [s.id, s])), [steps]);
  const inputById = useMemo(() => Object.fromEntries(requiredInputs.map(r => [r.id, r])), [requiredInputs]);
  const specOf = (tool, param) => (toolSpecs[tool] || []).find(p => p.name === param);

  // ── Dependency graph (depends_on already = real data deps, i.e. source=step edges) ──
  const deps = useMemo(() => {
    const m = {};
    steps.forEach(s => { m[s.id] = (s.depends_on || []).filter(d => stepById[d]); });
    return m;
  }, [steps, stepById]);
  const dependents = useMemo(() => {
    const m = {}; steps.forEach(s => { m[s.id] = []; });
    steps.forEach(s => (deps[s.id] || []).forEach(d => { (m[d] = m[d] || []).push(s.id); }));
    return m;
  }, [steps, deps]);

  const closure = (startIds, adj) => {
    const out = new Set(); const stack = [...startIds];
    while (stack.length) {
      const n = stack.pop();
      (adj[n] || []).forEach(x => { if (!out.has(x)) { out.add(x); stack.push(x); } });
    }
    return out;
  };

  // Topological levels for the diagram (level = longest path from a root).
  const levels = useMemo(() => {
    const lvl = {};
    const visit = (id, seen) => {
      if (lvl[id] != null) return lvl[id];
      if (seen.has(id)) return 0;
      seen.add(id);
      const ds = deps[id] || [];
      const v = ds.length ? Math.max(...ds.map(d => visit(d, seen))) + 1 : 0;
      lvl[id] = v; return v;
    };
    steps.forEach(s => visit(s.id, new Set()));
    const rows = [];
    steps.forEach(s => { const L = lvl[s.id] || 0; (rows[L] = rows[L] || []).push(s); });
    return rows.filter(Boolean);
  }, [steps, deps]);

  const structure = useMemo(() => {
    if (steps.length <= 1) return 'Single step';
    const anyEdge = steps.some(s => (deps[s.id] || []).length > 0);
    if (!anyEdge) return 'Parallel (independent steps, can run separately)';
    const pureChain = levels.length === steps.length && levels.every(r => r.length === 1);
    if (pureChain) return 'Serial (each step depends on the previous)';
    return 'Mixed (partly serial, partly parallel)';
  }, [steps, deps, levels]);

  const toggle = (id) => {
    if (locked) return;
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); closure([id], dependents).forEach(x => next.delete(x)); }
      else { next.add(id); closure([id], deps).forEach(x => next.add(x)); }
      return next;
    });
  };

  // Only count steps that exist in the CURRENT plan (guards against stale ids).
  const chosenSteps = steps.filter(s => checked.has(s.id));
  const nChecked = chosenSteps.length;

  const confirm = () => {
    if (chosenSteps.length === 0 || locked) return;
    const ids = chosenSteps.map(s => s.id).join(', ');
    const lines = chosenSteps.map(s => `- ${s.id} (${s.tool})`).join('\n');
    const msg =
      `Confirmed — I want to run these steps. Call execute_workflow_plan with ` +
      `selected_steps = [${ids}].\n\nSelected steps:\n${lines}\n\n` +
      `I have NOT uploaded the files yet. First reply with the EXACT list of files I need ` +
      `to upload for these steps, and the column/parameter values I can set for each step. ` +
      `Then I'll upload the files (and state any parameters) and send to run.`;
    setSubmitted(true);
    onConfirm(msg);
  };

  // "Add & re-plan" is a refinement, NOT a submit: it sends the user's CURRENT
  // selection (which steps to keep / drop) together with the new analysis text, and
  // asks the model to propose a fresh plan card to review. It must not run anything.
  const sendSupplement = () => {
    const extra = supplement.trim();
    if (!extra || locked) return;
    // Machine token: the backend keeps EXACTLY these step ids and asks the model only
    // for the new step(s), so deselected steps can never be silently re-added.
    const keepIds = chosenSteps.map(s => s.id);
    const dropped = steps.filter(s => !checked.has(s.id)).map(s => `${s.id} (${s.tool})`);
    const dropLine = dropped.length ? ` (I deselected: ${dropped.join(', ')} — leave them out.)` : '';
    const msg =
      `Add to my analysis plan — I have NOT run anything yet. Keep my currently-selected steps ` +
      `and ADD this analysis: "${extra}".${dropLine}\n` +
      `[[REPLAN_KEEP=${keepIds.join(',')}]]\n` +
      `Call add_workflow_steps to generate ONLY the new step(s) for that analysis; do NOT re-list ` +
      `my kept steps (they are kept automatically). Don't run it — show me a new plan card to confirm.`;
    setReplanning(true);
    onConfirm(msg);
  };

  // Render the inputs of one step (③), source-aware + contract-driven.
  const renderInputs = (s) => {
    const entries = Object.entries(s.inputs || {});
    if (entries.length === 0) return <p className="text-[12px] text-gray-400 pl-5">(no inputs)</p>;
    return (
      <ul className="space-y-1 pl-5">
        {entries.map(([param, src]) => {
          const spec = specOf(s.tool, param);
          if (src?.source === 'input') {
            const f = inputById[src.ref];
            const kind = FILE_KIND[f?.file_kind] || FILE_KIND[spec?.file_kind] || spec?.file_kind || 'file';
            return (
              <li key={param} className="text-[13px] text-gray-600 flex gap-2">
                <Upload size={13} className="mt-0.5 text-blue-500 shrink-0" />
                <span className="min-w-0">
                  Upload <span className="font-medium text-gray-700">{f?.label || src.ref}</span>
                  <span className="text-[11px] text-gray-400"> ({kind}, fills <code className="font-mono">{param}</code>)</span>
                </span>
              </li>
            );
          }
          if (src?.source === 'step') {
            const up = stepById[src.ref];
            return (
              <li key={param} className="text-[13px] text-gray-600 flex gap-2">
                <CornerDownRight size={13} className="mt-0.5 text-teal-600 shrink-0" />
                <span><code className="font-mono">{param}</code> ← uses output of «{up ? up.tool : src.ref}»<span className="text-[11px] text-gray-400"> (no upload)</span></span>
              </li>
            );
          }
          const isCol = /(_field$|variables$)/.test(param);
          return (
            <li key={param} className="text-[13px] text-gray-600 flex gap-2">
              <Settings2 size={13} className="mt-0.5 text-gray-400 shrink-0" />
              <span>
                <code className="font-mono">{param}</code> = <span className="font-medium text-gray-700">{String(src.value)}</span>
                {isCol && <span className="text-[11px] text-gray-400"> (a column in your data)</span>}
                {spec?.required && <span className="text-[11px] text-rose-400"> ·required</span>}
              </span>
            </li>
          );
        })}
      </ul>
    );
  };

  const orderedSteps = levels.flat();

  const StartNode = () => (
    <span className="inline-flex items-center gap-1 text-[12px] font-medium px-3 py-1 rounded-full bg-gray-700 text-white shadow-sm">
      ▶ Start
    </span>
  );
  const StepNode = ({ s }) => {
    const c = comp(s.component);
    const on = checked.has(s.id);
    return (
      <span className={`inline-flex items-center gap-1 text-[12px] font-mono px-2 py-1 rounded-lg border ${c.cls} ${on ? '' : 'opacity-35 line-through'}`}>
        {c.icon} {s.tool}
      </span>
    );
  };

  return (
    <div className="border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-sm w-full">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-100">
        <div className="flex items-center gap-2 text-blue-700 font-semibold text-[15px]">
          <ListChecks size={18} /> Analysis plan
        </div>
        {plan?.description && <p className="text-xs text-gray-500 mt-1 leading-relaxed">{plan.description}</p>}
      </div>

      {!valid && (
        <div className="px-4 py-2 bg-red-50 text-red-600 text-xs border-b border-red-100">
          ⚠️ Plan has issues and can't run yet: {(errors || []).join('; ')}
        </div>
      )}

      {/* ② Structure diagram — a "Start" node fanning out to the steps */}
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-3">
          <GitBranch size={13} /> Structure: {structure}
        </div>
        {levels.length === 1 ? (
          <div>
            <div className="flex flex-col items-start">
              <StartNode />
              <div className="ml-3 w-px h-3 bg-gray-300" />
            </div>
            <div>
              {levels[0].map((s, i) => {
                const last = i === levels[0].length - 1;
                return (
                  <div key={s.id} className="flex items-stretch">
                    <div className="relative w-6 shrink-0">
                      <div className="absolute left-3 top-0 w-px bg-gray-300" style={{ height: last ? '50%' : '100%' }} />
                      <div className="absolute left-3 top-1/2 w-3 h-px bg-gray-300" />
                    </div>
                    <div className="py-1"><StepNode s={s} /></div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1">
            <StartNode />
            {levels.map((row, li) => (
              <div key={li} className="flex flex-col items-center gap-1">
                <div className="text-gray-300 text-sm leading-none">↓</div>
                <div className="flex flex-wrap gap-2 justify-center">
                  {row.map(s => <StepNode key={s.id} s={s} />)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ③ Tools + example inputs (contract-driven, source-aware) */}
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/60">
        <div className="text-xs font-semibold text-gray-500">Tools &amp; example inputs</div>
        <p className="text-[11px] text-gray-400 mb-2.5">Files and values below are examples; column names are auto-corrected to your uploaded data.</p>
        <div className="space-y-3">
          {orderedSteps.map((s) => {
            const c = comp(s.component);
            const on = checked.has(s.id);
            return (
              <div key={s.id} className={on ? '' : 'opacity-40'}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border ${c.cls}`}>{c.icon} {c.label}</span>
                  <code className="text-[12px] font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{s.tool}</code>
                </div>
                {renderInputs(s)}
              </div>
            );
          })}
        </div>
      </div>

      {/* ④ Selection — tool names only */}
      <div className="px-4 py-3">
        <div className="text-xs font-semibold text-gray-500 mb-2">Select steps to run</div>
        <ul className="space-y-1">
          {orderedSteps.map((s) => {
            const c = comp(s.component);
            const on = checked.has(s.id);
            return (
              <li key={s.id}>
                <button type="button" onClick={() => toggle(s.id)} disabled={locked}
                  className={`w-full text-left px-2 py-1.5 rounded-lg flex items-center gap-2.5 transition-colors ${locked ? 'cursor-default' : 'hover:bg-blue-50/50'}`}>
                  <span className={`shrink-0 w-5 h-5 rounded-md border flex items-center justify-center ${on ? 'bg-blue-600 border-blue-600' : 'bg-white border-gray-300'}`}>
                    {on && <Check size={14} className="text-white" strokeWidth={3} />}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border ${c.cls}`}>{c.icon}</span>
                  <code className="text-[13px] font-mono text-gray-700">{s.tool}</code>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Supplement: add another analysis -> re-plan */}
      <div className="px-4 py-3 border-t border-gray-100">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-2">
          <Plus size={13} /> Other / add an analysis (re-plans)
        </div>
        <div className="flex gap-2">
          <input type="text" value={supplement} disabled={locked}
            onChange={(e) => setSupplement(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') sendSupplement(); }}
            placeholder="e.g. add a habitat quality assessment / cost-benefit analysis…"
            className="flex-1 text-[13px] px-3 py-2 rounded-lg border border-gray-200 focus:outline-none focus:border-blue-400 disabled:bg-gray-50" />
          <button type="button" onClick={sendSupplement} disabled={locked || !supplement.trim()}
            className="text-[13px] px-3 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap">
            {replanning ? 'Re-planning…' : 'Add & re-plan'}
          </button>
        </div>
        {replanning && (
          <p className="text-[11px] text-gray-400 mt-2">Re-planning with your current selection + the added analysis — a new plan card will appear below.</p>
        )}
      </div>

      {/* Confirm */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between gap-3">
        <span className="text-xs text-gray-500">Selected {nChecked} / {steps.length}</span>
        <button type="button" onClick={confirm} disabled={locked || !valid || nChecked === 0}
          className="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed">
          <Sparkles size={15} /> {submitted ? 'Submitted' : `Confirm & run ${nChecked} step${nChecked === 1 ? '' : 's'}`}
        </button>
      </div>
    </div>
  );
}
