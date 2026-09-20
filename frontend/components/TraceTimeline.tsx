import type { TicketTrace } from "@/lib/types";
import {
  formatIntent,
  formatCategory,
  formatConfidence,
  isPolicyDenylist,
} from "@/lib/labels";

interface TraceTimelineProps {
  trace: TicketTrace;
}

export default function TraceTimeline({ trace }: TraceTimelineProps) {
  const isDenylist = isPolicyDenylist(trace.intent, trace.critic_reason);
  const confidenceFloorPassed =
    trace.draft_confidence >= (trace.threshold_used || 0.7);

  return (
    <div className="space-y-6">
      {/* 01. Classification Stage */}
      <div className="rounded border border-border bg-surface p-5">
        <div className="flex items-center justify-between pb-3 border-b border-border/60">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-surface-raised border border-border text-text-secondary">
              01
            </span>
            <h3 className="text-sm font-semibold text-text-primary tracking-tight">
              Intent Classification
            </h3>
          </div>
          <span className="font-mono text-xs text-text-secondary">
            Confidence:{" "}
            <span className="text-text-primary font-medium">
              {formatConfidence(trace.classifier_confidence)}
            </span>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-xs">
          <div>
            <div className="text-text-secondary mb-1">Detected Intent</div>
            <div className="font-medium text-text-primary">
              {formatIntent(trace.intent)}
            </div>
            <div className="font-mono text-[11px] text-text-secondary/70 mt-0.5">
              enum: {trace.intent}
            </div>
          </div>
          <div>
            <div className="text-text-secondary mb-1">Operational Category</div>
            <div className="font-medium text-text-primary">
              {formatCategory(trace.category)}
            </div>
            <div className="font-mono text-[11px] text-text-secondary/70 mt-0.5">
              scope: {trace.category}
            </div>
          </div>
        </div>
      </div>

      {/* 02. Retrieval & Cache Stage */}
      <div className="rounded border border-border bg-surface p-5">
        <div className="flex items-center justify-between pb-3 border-b border-border/60">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-surface-raised border border-border text-text-secondary">
              02
            </span>
            <h3 className="text-sm font-semibold text-text-primary tracking-tight">
              Knowledge Retrieval & Cache
            </h3>
          </div>
          <span className="font-mono text-xs text-text-secondary">
            {trace.cache_hit ? (
              <span className="inline-flex items-center gap-1.5 text-resolve">
                <span className="w-1.5 h-1.5 rounded-full bg-resolve" />
                Cache Hit
              </span>
            ) : (
              <span className="text-text-secondary">Cache Miss (pgvector)</span>
            )}
          </span>
        </div>

        <div className="mt-4 text-xs">
          <div className="flex items-center justify-between text-text-secondary mb-2">
            <span>
              Retrieved passages:{" "}
              <strong className="text-text-primary font-mono">
                {trace.retrieved_chunk_count}
              </strong>
            </span>
            {trace.cache_hit && (
              <span className="font-mono text-[11px] text-text-secondary/80">
                Exact hash lookup
              </span>
            )}
          </div>

          {trace.retrieved_chunk_ids && trace.retrieved_chunk_ids.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {trace.retrieved_chunk_ids.map((id, idx) => (
                <span
                  key={id || idx}
                  className="font-mono text-[11px] px-2 py-0.5 rounded bg-surface-raised border border-border text-text-secondary"
                >
                  chunk: {String(id).slice(0, 8)}…
                </span>
              ))}
            </div>
          ) : (
            <div className="text-text-secondary/70 italic text-[11px]">
              {trace.cache_hit
                ? "Bypassed retrieval — served directly from semantic cache."
                : "No matching knowledge passages found for this intent."}
            </div>
          )}
        </div>
      </div>

      {/* 03. Drafting Stage */}
      <div className="rounded border border-border bg-surface p-5">
        <div className="flex items-center justify-between pb-3 border-b border-border/60">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-surface-raised border border-border text-text-secondary">
              03
            </span>
            <h3 className="text-sm font-semibold text-text-primary tracking-tight">
              Resolution Drafting
            </h3>
          </div>
          <span className="font-mono text-xs text-text-secondary">
            Drafter Confidence:{" "}
            <span className="text-text-primary font-medium">
              {formatConfidence(trace.draft_confidence)}
            </span>
          </span>
        </div>

        <div className="mt-4 text-xs space-y-3">
          <div>
            <div className="text-text-secondary mb-1">Citations Declared</div>
            {trace.draft_cited_chunk_ids && trace.draft_cited_chunk_ids.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {trace.draft_cited_chunk_ids.map((cid, i) => (
                  <span
                    key={cid || i}
                    className="font-mono text-[11px] px-2 py-0.5 rounded bg-surface-raised border border-border text-text-primary"
                  >
                    cited: {String(cid).slice(0, 8)}…
                  </span>
                ))}
              </div>
            ) : (
              <div className="text-text-secondary/70 italic text-[11px]">
                No citations declared (abstain path)
              </div>
            )}
          </div>

          {trace.draft_answer ? (
            <div>
              <div className="text-text-secondary mb-1">Generated Draft</div>
              <div className="p-3 rounded bg-surface-raised border border-border text-text-primary font-sans text-xs leading-relaxed whitespace-pre-wrap">
                {trace.draft_answer}
              </div>
            </div>
          ) : (
            <div className="text-text-secondary/70 italic text-[11px]">
              No resolution drafted due to missing knowledge grounding.
            </div>
          )}
        </div>
      </div>

      {/* 04. Escalation Critic Stage */}
      <div className="rounded border border-border bg-surface p-5">
        <div className="flex items-center justify-between pb-3 border-b border-border/60">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-surface-raised border border-border text-text-secondary">
              04
            </span>
            <h3 className="text-sm font-semibold text-text-primary tracking-tight">
              Escalation Critic & Guardrails
            </h3>
          </div>
          <span className="font-mono text-xs text-text-secondary">
            Applied Floor:{" "}
            <span className="text-text-primary font-medium">
              {formatConfidence(trace.threshold_used)}
            </span>
          </span>
        </div>

        <div className="mt-4 space-y-4 text-xs">
          {/* Policy Denylist Audit */}
          <div className="flex items-center justify-between p-2.5 rounded bg-surface-raised border border-border">
            <span className="text-text-secondary">Policy Denylist Guardrail</span>
            {isDenylist ? (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-denylist">
                <span className="w-1.5 h-1.5 rounded-full bg-denylist shrink-0" />
                Triggered (Escalate by Policy)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-resolve">
                <span className="w-1.5 h-1.5 rounded-full bg-resolve shrink-0" />
                Passed
              </span>
            )}
          </div>

          {/* Confidence Floor Audit */}
          <div className="flex items-center justify-between p-2.5 rounded bg-surface-raised border border-border">
            <span className="text-text-secondary">Confidence Floor Check</span>
            {isDenylist ? (
              <span className="font-mono text-[11px] text-text-secondary">
                Bypassed (short-circuited by policy)
              </span>
            ) : confidenceFloorPassed ? (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-resolve">
                <span className="w-1.5 h-1.5 rounded-full bg-resolve shrink-0" />
                Passed ({formatConfidence(trace.draft_confidence)} &ge; {formatConfidence(trace.threshold_used)})
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-escalate">
                <span className="w-1.5 h-1.5 rounded-full bg-escalate shrink-0" />
                Below Floor ({formatConfidence(trace.draft_confidence)} &lt; {formatConfidence(trace.threshold_used)})
              </span>
            )}
          </div>

          {/* Citation Entailment Audit Table (E1) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-text-secondary font-medium">
                Citation Entailment Audit
              </span>
              <span className="font-mono text-[11px] text-text-secondary">
                {trace.entailment_steps.length > 0
                  ? `${trace.entailment_steps.filter((e) => e.supported).length} of ${trace.entailment_steps.length} verified`
                  : "0 citations checked"}
              </span>
            </div>

            {trace.entailment_steps.length > 0 ? (
              <div className="rounded border border-border overflow-hidden">
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-surface-raised text-text-secondary font-normal border-b border-border text-[11px]">
                      <th className="py-2 px-3 font-normal">Chunk ID</th>
                      <th className="py-2 px-3 font-normal">Passage Preview</th>
                      <th className="py-2 px-3 font-normal">Audit Verdict</th>
                      <th className="py-2 px-3 font-normal">Critic Rationale</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {trace.entailment_steps.map((step, idx) => (
                      <tr key={step.chunk_id || idx} className="text-xs hover:bg-surface-raised/40">
                        <td className="py-2 px-3 font-mono text-[11px] text-text-secondary align-top whitespace-nowrap">
                          {String(step.chunk_id).slice(0, 8)}
                        </td>
                        <td className="py-2 px-3 text-text-secondary text-[11px] align-top max-w-xs">
                          <span className="line-clamp-2">{step.chunk_content_preview}</span>
                        </td>
                        <td className="py-2 px-3 align-top whitespace-nowrap">
                          {step.supported ? (
                            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-resolve">
                              <span className="w-1.5 h-1.5 rounded-full bg-resolve shrink-0" />
                              Entailed
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-escalate">
                              <span className="w-1.5 h-1.5 rounded-full bg-escalate shrink-0" />
                              Failed
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-text-primary text-[11px] align-top leading-tight">
                          {step.reason}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-3 rounded bg-surface-raised border border-border text-text-secondary/70 italic text-[11px]">
                {isDenylist
                  ? "Entailment checks skipped because ticket is subject to hard policy escalation."
                  : trace.cache_hit
                  ? "Entailment checks skipped — verified by earlier cache entry."
                  : "No citations were available for entailment verification."}
              </div>
            )}
          </div>

          {/* Critic Decision Reason */}
          <div className="p-3 rounded bg-surface-raised border border-border">
            <div className="text-[11px] text-text-secondary mb-1">
              Final Decision Summary
            </div>
            <div className="text-xs text-text-primary font-mono leading-relaxed">
              {trace.critic_reason}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
