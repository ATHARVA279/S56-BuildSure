import { useState } from "react";
import {
  Search,
  Layers,
  FolderOpen,
  ClipboardList,
  BookOpen,
  X,
} from "lucide-react";
import type { ScopeFilter } from "@/types";

interface Props {
  activeProjectId: string;
  projectName: string;
  onSearch: (query: string, scope: ScopeFilter) => void;
  initialQuery?: string;
  initialScope?: ScopeFilter;
  loading?: boolean;
}

const SCOPE_OPTIONS: {
  id: ScopeFilter;
  label: string;
  icon: React.ReactNode;
}[] = [
  { id: "all", label: "Search All", icon: <Layers className="w-3.5 h-3.5" /> },
  {
    id: "project-specs",
    label: "Project Specs",
    icon: <FolderOpen className="w-3.5 h-3.5" />,
  },
  {
    id: "inspection-reports",
    label: "Inspection Reports",
    icon: <ClipboardList className="w-3.5 h-3.5" />,
  },
  {
    id: "building-codes",
    label: "Building Codes",
    icon: <BookOpen className="w-3.5 h-3.5" />,
  },
];

const SUGGESTED = [
  "Egress width requirements for high-rise",
  "Fire suppression sprinkler spacing",
  "ADA accessible restroom dimensions",
  "Occupant load calculation method",
  "Stairwell pressurization requirements",
];

export default function SearchSection({
  activeProjectId,
  projectName,
  onSearch,
  initialQuery = "",
  initialScope = "all",
  loading = false,
}: Props) {
  const [query, setQuery] = useState(initialQuery);
  const [scope, setScope] = useState<ScopeFilter>(initialScope);

  const isGlobal = activeProjectId === "global";
  const scopeDescription = isGlobal
    ? "Searching across: Global Building Codes Only"
    : `Searching across: ${projectName} Docs + Global Building Codes`;

  function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (query.trim()) onSearch(query.trim(), scope);
  }

  return (
    <div className="flex flex-col items-center w-full max-w-3xl mx-auto px-2 sm:px-4">
      {/* Hero text */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 mb-2.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-900 font-mono text-[11px] font-bold uppercase tracking-widest">
          FIELD INSPECTION & CODE DATABASE
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight uppercase font-mono mb-2">
          COMPLIANCE SEARCH
        </h1>
        <p className="text-slate-700 text-xs sm:text-sm max-w-xl font-medium leading-relaxed">
          Ask technical code and specification questions in plain language. The
          AI parses building codes, structural specifications, and field
          inspection reports.
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSubmit} className="w-full">
        <div className="relative w-full group">
          <div className="flex items-center min-h-[54px] w-full bg-white border-2 border-slate-300 hover:border-slate-400 focus-within:border-amber-500 focus-within:ring-1 focus-within:ring-amber-500 rounded-md transition-all shadow-xs overflow-hidden">
            <div className="pl-4 pr-2 text-slate-600 flex items-center justify-center shrink-0">
              <Search className="w-5 h-5 text-slate-700" />
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What are the egress width requirements for stairwells?"
              className="flex-1 py-3 px-2 bg-transparent text-slate-900 font-bold placeholder:text-slate-400 placeholder:font-normal text-sm sm:text-base focus:outline-none"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center text-slate-500 hover:text-slate-900 transition-colors"
                title="Clear input"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <div className="pr-1.5 py-1.5 shrink-0">
              <button
                type="submit"
                disabled={!query.trim() || loading}
                className="min-h-[44px] px-5 rounded-md bg-amber-500 hover:bg-amber-400 active:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-950 font-mono font-bold text-xs uppercase tracking-wider transition-all border border-amber-600 shadow-xs flex items-center gap-1.5"
              >
                {loading ? "SEARCHING" : "SEARCH"}
              </button>
            </div>
          </div>
        </div>

        {/* Scope indicator */}
        <div className="flex items-center gap-2 mt-2.5 justify-center">
          <div className="w-2 h-2 rounded-xs bg-amber-500 animate-pulse" />
          <p className="font-mono text-xs text-slate-700 font-bold uppercase tracking-wider">
            {scopeDescription}
          </p>
        </div>

        {/* Filter pills */}
        <div className="flex flex-wrap gap-2 mt-4 justify-center">
          {SCOPE_OPTIONS.map((opt) => {
            const isActive = scope === opt.id;
            const isDisabled =
              opt.id === "project-specs" || opt.id === "inspection-reports"
                ? isGlobal
                : false;
            return (
              <button
                key={opt.id}
                type="button"
                disabled={isDisabled}
                onClick={() => setScope(opt.id)}
                className={`min-h-[44px] flex items-center gap-2 px-3.5 py-2 rounded-md font-mono text-xs font-bold uppercase tracking-wider border-2 transition-all ${
                  isDisabled
                    ? "border-slate-200 text-slate-400 bg-slate-100 cursor-not-allowed"
                    : isActive
                      ? "bg-amber-500 border-amber-600 text-slate-950 shadow-xs"
                      : "bg-white border-slate-300 text-slate-800 hover:border-slate-400 hover:bg-slate-50"
                }`}
              >
                {opt.icon}
                {opt.label}
              </button>
            );
          })}
        </div>
      </form>

      {/* Suggestions */}
      <div className="w-full mt-6 pt-5 border-t border-[#E2E8F0]">
        <p className="text-[11px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-2.5 text-center">
          FIELD QUERY PRESETS
        </p>
        <div className="flex flex-wrap gap-2 justify-center">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => {
                setQuery(s);
                onSearch(s, scope);
              }}
              className="min-h-[44px] flex items-center px-3.5 py-2 rounded-md text-xs font-mono font-medium text-slate-800 bg-white border border-slate-300 hover:border-amber-500 hover:bg-amber-50/40 hover:text-slate-950 transition-all shadow-2xs"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
