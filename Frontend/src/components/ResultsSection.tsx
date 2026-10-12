import { useState } from 'react';
import { Globe, FolderOpen, Sparkles, FileText, ExternalLink, AlertTriangle } from 'lucide-react';
import type { SearchResult, AISummary, ScopeFilter } from '@/types';
import SearchSection from './SearchSection';

interface Props {
  query: string;
  scope: ScopeFilter;
  activeProjectId: string;
  projectName: string;
  aiSummary: AISummary | null;
  results: SearchResult[];
  loading?: boolean;
  error?: string | null;
  hasDeficiency?: boolean;
  deficiencyText?: string | null;
  deficiencyStatus?: string | null;
  retrievalNote?: string | null;
  onNewSearch: (query: string, scope: ScopeFilter) => void;
  onViewPdf: (result: SearchResult) => void;
}

export default function ResultsSection({
  query,
  scope,
  activeProjectId,
  projectName,
  aiSummary,
  results,
  loading = false,
  error = null,
  hasDeficiency = false,
  deficiencyText = null,
  deficiencyStatus = null,
  retrievalNote = null,
  onNewSearch,
  onViewPdf,
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filteredResults = results.filter((r) => {
    if (scope === 'all') return true;
    if (scope === 'building-codes') return r.category === 'building-code';
    if (scope === 'project-specs') return r.category === 'project-spec';
    if (scope === 'inspection-reports') return r.category === 'inspection-report';
    return true;
  });

  return (
    <div className="w-full max-w-4xl mx-auto px-2 sm:px-4">
      {/* Search bar at top */}
      <div className="mb-4">
        <SearchSection
          activeProjectId={activeProjectId}
          projectName={projectName}
          onSearch={onNewSearch}
          initialQuery={query}
          initialScope={scope}
          loading={loading}
        />
      </div>

      <div className="space-y-4">
        {loading && (
          <p className="font-mono text-xs font-bold uppercase tracking-wider text-slate-700 px-1" role="status">
            Searching the repository...
          </p>
        )}
        {error && (
          <p className="font-mono text-xs font-bold text-red-800 bg-red-50 border border-red-200 rounded-md px-3 py-3" role="alert">
            {error}
          </p>
        )}
        {retrievalNote && !loading && (
          <p className="font-mono text-[11px] text-slate-700 bg-slate-100 border border-slate-300 rounded-md px-3 py-2">
            {retrievalNote}
          </p>
        )}
        {aiSummary && !loading && (
          <AISummaryCard
            summary={aiSummary}
            query={query}
            hasDeficiency={hasDeficiency}
            deficiencyText={deficiencyText}
            deficiencyStatus={deficiencyStatus}
          />
        )}
        {!loading && !error && results.length === 0 && (
          <p className="font-mono text-xs font-bold text-slate-700 px-1">
            No source documents matched this question.
          </p>
        )}

        {/* Results header */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-1 pt-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-mono font-extrabold uppercase tracking-wider text-slate-900">
              SOURCE REFERENCES
            </h2>
            <span className="font-mono text-[11px] font-bold text-slate-700 bg-slate-200 px-1.5 py-0.5 rounded-sm">
              [{filteredResults.length} FOUND]
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px] font-bold uppercase tracking-wider">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-xs bg-amber-500" />
              <span className="text-slate-800">PROJECT SPEC</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-xs bg-slate-600" />
              <span className="text-slate-800">GLOBAL CODE</span>
            </div>
          </div>
        </div>

        {/* Result cards */}
        <div className="space-y-2.5">
          {filteredResults.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              expanded={expandedId === result.id}
              onToggle={() => setExpandedId(expandedId === result.id ? null : result.id)}
              onViewPdf={() => onViewPdf(result)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function AISummaryCard({
  summary,
  query,
  hasDeficiency,
  deficiencyText,
  deficiencyStatus,
}: {
  summary: AISummary;
  query: string;
  hasDeficiency: boolean;
  deficiencyText: string | null;
  deficiencyStatus: string | null;
}) {
  const parts = parseAnswer(summary.answer, summary.citations);

  return (
    <div className="rounded-md border border-slate-300 bg-white overflow-hidden shadow-xs border-l-4 border-l-amber-500">
      {/* Card Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 border-b border-slate-200 bg-slate-900 text-white">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-amber-500 rounded-sm flex items-center justify-center shrink-0 border border-amber-400">
            <Sparkles className="w-3.5 h-3.5 text-slate-950" />
          </div>
          <p className="text-xs font-mono font-extrabold uppercase tracking-wider text-white">
            AI COMPLIANCE ANALYSIS
          </p>
        </div>
        <p className="text-[11px] font-mono text-amber-400 font-bold truncate max-w-sm">
          QUERY: "{query}"
        </p>
      </div>

      <div className="p-3.5 sm:p-4">
        {/* High contrast body */}
        <p className="text-xs sm:text-sm leading-relaxed text-[#1F2937] font-medium font-sans">
          {parts.map((part, i) =>
            part.type === 'text' ? (
              <span key={i}>{part.content}</span>
            ) : (
              <CitationTag key={i} label={part.content} scope={part.scope!} />
            )
          )}
        </p>

        {hasDeficiency && deficiencyText && (
          <div className="mt-3.5 flex items-start gap-3 p-3 bg-red-50 border border-red-300 border-l-4 border-l-red-600 rounded-md" role="alert">
            <AlertTriangle className="w-5 h-5 text-red-700 shrink-0 mt-0.5" strokeWidth={2.5} />
            <div className="flex-1">
              <p className="text-[11px] font-mono font-black uppercase tracking-wider text-red-950">
                DEFICIENCY DETECTED
              </p>
              <p className="text-xs font-bold text-red-950 mt-0.5 leading-snug">
                {deficiencyText}
              </p>
            </div>
          </div>
        )}
        {!hasDeficiency && deficiencyStatus === 'requires_verification' && deficiencyText && (
          <div className="mt-3.5 flex items-start gap-3 p-3 bg-amber-500/10 border border-amber-400/80 border-l-4 border-l-amber-600 rounded-md" role="status">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" strokeWidth={2.5} />
            <div className="flex-1">
              <p className="text-[11px] font-mono font-black uppercase tracking-wider text-amber-950">
                REQUIRES VERIFICATION
              </p>
              <p className="text-xs font-bold text-amber-950 mt-0.5 leading-snug">
                {deficiencyText}
              </p>
            </div>
          </div>
        )}

        {/* Citation Legend */}
        <div className="mt-3.5 pt-3 border-t border-[#E2E8F0] flex flex-wrap gap-2">
          {summary.citations.map((c, i) => (
            <div
              key={i}
              className="min-h-[44px] flex items-center gap-2 text-xs font-mono font-bold px-3 py-1.5 rounded-md border bg-slate-100 text-slate-900 border-slate-300"
            >
              {c.scope === 'global' ? <Globe className="w-3.5 h-3.5 text-slate-600" /> : <FolderOpen className="w-3.5 h-3.5 text-amber-700" />}
              <span>{c.label}</span>
              <span className="text-slate-400">|</span>
              <span className="text-[10px] uppercase font-semibold text-slate-600">
                {c.scope === 'global' ? 'GLOBAL CODE' : 'OFFICIAL SPEC'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CitationTag({ label, scope }: { label: string; scope: 'global' | 'local' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-xs font-bold px-1.5 py-0.5 rounded-sm mx-0.5 border align-baseline ${
        scope === 'global'
          ? 'bg-slate-100 text-slate-900 border-slate-300'
          : 'bg-amber-100 text-amber-950 border-amber-400'
      }`}
    >
      {scope === 'global' ? <Globe className="w-2.5 h-2.5" /> : <FolderOpen className="w-2.5 h-2.5" />}
      {label}
    </span>
  );
}

interface Part {
  type: 'text' | 'citation';
  content: string;
  scope?: 'global' | 'local';
}

function parseAnswer(answer: string, citations: AISummary['citations']): Part[] {
  const parts: Part[] = [];
  let remaining = answer;
  while (remaining.length > 0) {
    let earliestIdx = remaining.length;
    let match: { label: string; scope: 'global' | 'local' } | null = null;
    for (const c of citations) {
      const idx = remaining.indexOf(`[${c.label}]`);
      if (idx !== -1 && idx < earliestIdx) {
        earliestIdx = idx;
        match = c;
      }
    }
    if (!match) {
      parts.push({ type: 'text', content: remaining });
      break;
    }
    if (earliestIdx > 0) {
      parts.push({ type: 'text', content: remaining.slice(0, earliestIdx) });
    }
    parts.push({ type: 'citation', content: match.label, scope: match.scope });
    remaining = remaining.slice(earliestIdx + match.label.length + 2);
  }
  return parts;
}

function ResultCard({
  result,
  expanded,
  onToggle,
  onViewPdf,
}: {
  result: SearchResult;
  expanded: boolean;
  onToggle: () => void;
  onViewPdf: () => void;
}) {
  const isProject = result.scope === 'local';
  const isInspection = result.category === 'inspection-report';
  const finding = result.findingStatus;

  return (
    <div className="rounded-md border border-slate-300 bg-white overflow-hidden shadow-2xs hover:border-slate-400 transition-all">
      {/* Subtle top header bar */}
      <div className="px-3.5 py-1.5 bg-slate-100 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Dedicated OFFICIAL SPEC or GLOBAL CODE badge using monospaced text */}
          {finding === 'open' ? (
            <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-red-100 text-red-950 border border-red-300 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3 text-red-700" />
              DEFICIENCY DETECTED
            </span>
          ) : finding === 'unverified' ? (
            <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-amber-100 text-amber-950 border border-amber-300 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3 text-amber-700" />
              REQUIRES VERIFICATION
            </span>
          ) : finding === 'closed' ? (
            <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-slate-200 text-slate-900 border border-slate-300">
              RESOLVED FINDING
            </span>
          ) : isInspection ? (
            <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-slate-200 text-slate-900 border border-slate-300">
              INSPECTION REPORT
            </span>
          ) : isProject ? (
            <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-amber-500/20 text-amber-950 border border-amber-500/40 flex items-center gap-1.5">
              <FolderOpen className="w-3 h-3 text-amber-700" />
              OFFICIAL SPEC
            </span>
          ) : (
            <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-slate-200 text-slate-900 border border-slate-300 flex items-center gap-1.5">
              <Globe className="w-3 h-3 text-slate-700" />
              GLOBAL CODE
            </span>
          )}

          <span className="font-mono text-xs font-bold text-slate-800 truncate max-w-xs sm:max-w-md">
            {result.documentName}
          </span>
        </div>

        {/* Monospaced page number */}
        <span className="font-mono text-xs font-extrabold text-slate-900 bg-white px-2 py-0.5 rounded-sm border border-slate-300">
          p. {result.page}
          {typeof result.score === 'number' && (
            <span className="ml-2 font-semibold text-slate-600" title="Retrieval relevance score">
              rel {result.score.toFixed(2)}
            </span>
          )}
        </span>
      </div>

      {/* Main card body */}
      <div className="p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Section citation */}
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-slate-700 shrink-0" />
            <p className="text-sm font-mono font-bold text-slate-950 leading-tight">
              {result.section}
            </p>
          </div>

          {/* Snippet */}
          <p
            className={`text-xs sm:text-sm text-[#1F2937] font-medium leading-relaxed font-sans ${
              expanded ? '' : 'line-clamp-2'
            }`}
          >
            "{result.snippet}"
          </p>

          {result.snippet.length > 150 && (
            <button
              onClick={onToggle}
              className="min-h-[44px] inline-flex items-center font-mono text-xs font-bold text-amber-700 hover:text-amber-800 uppercase tracking-wider"
            >
              {expanded ? '▲ COLLAPSE' : '▼ EXPAND EXCERPT'}
            </button>
          )}
        </div>

        {/* Solid field action trigger */}
        <div className="shrink-0 w-full sm:w-auto flex items-center justify-end">
          <button
            onClick={onViewPdf}
            className="w-full sm:w-auto min-h-[44px] px-4 py-2 rounded-md bg-slate-900 hover:bg-slate-800 active:bg-slate-950 text-amber-400 hover:text-amber-300 font-mono font-bold text-xs uppercase tracking-wider border border-slate-700 shadow-xs flex items-center justify-center gap-2 whitespace-nowrap transition-all"
          >
            <ExternalLink className="w-3.5 h-3.5 text-amber-400" />
            VIEW IN PDF
          </button>
        </div>
      </div>
    </div>
  );
}
