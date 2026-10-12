import { useState, useRef, useEffect } from "react";
import {
  Building2,
  ChevronDown,
  Files,
  Plus,
  Check,
  Globe,
  FolderOpen,
} from "lucide-react";
import type { Project } from "@/types";

interface Props {
  projects: Project[];
  activeProjectId: string;
  onProjectChange: (id: string) => void;
  onOpenDrawer: () => void;
  onCreateProject: () => void;
}

export default function Header({
  projects,
  activeProjectId,
  onProjectChange,
  onOpenDrawer,
  onCreateProject,
}: Props) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const activeProject = projects.find((p) => p.id === activeProjectId);
  const displayLabel = activeProject?.isGlobal
    ? "Global Repository"
    : (activeProject?.name ?? "Select Project");

  return (
    <header className="fixed top-0 left-0 right-0 z-40 bg-slate-950 border-b border-slate-800 shadow-md">
      <div className="max-w-screen-2xl mx-auto px-3 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-9 h-9 bg-amber-500 rounded-md flex items-center justify-center shrink-0 shadow-xs border border-amber-600">
            <Building2 className="w-5 h-5 text-slate-950" strokeWidth={2.5} />
          </div>
          <div className="flex items-baseline">
            <span className="text-white font-extrabold text-base tracking-tight font-mono">
              Build
            </span>
            <span className="text-amber-400 font-extrabold text-base tracking-tight font-mono">
              Sure
            </span>
          </div>
          <span className="hidden sm:inline-flex items-center ml-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-slate-800 text-amber-400 border border-slate-700 uppercase tracking-widest">
            FIELD OPS
          </span>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Project Selector */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((o) => !o)}
              className="min-h-[44px] flex items-center gap-2.5 px-3.5 py-2 rounded-md bg-slate-900 border border-slate-700 hover:border-amber-500/70 hover:bg-slate-800 transition-all group"
            >
              <div className="w-2.5 h-2.5 rounded-sm bg-amber-400 shrink-0" />
              <span className="text-slate-100 text-sm font-semibold max-w-[150px] sm:max-w-[220px] truncate">
                {displayLabel}
              </span>
              <ChevronDown
                className={`w-4 h-4 text-slate-400 transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
              />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-slate-900 border border-slate-700 rounded-md shadow-2xl overflow-hidden z-50">
                <div className="px-3.5 pt-3 pb-2 border-b border-slate-800 bg-slate-950">
                  <p className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-widest">
                    ACTIVE WORKSPACE
                  </p>
                </div>

                <div className="max-h-72 overflow-y-auto divide-y divide-slate-800/60">
                  {projects.map((project) => {
                    const isActive = project.id === activeProjectId;
                    const label = project.isGlobal
                      ? "Global Repository"
                      : project.name;
                    return (
                      <button
                        key={project.id}
                        onClick={() => {
                          onProjectChange(project.id);
                          setDropdownOpen(false);
                        }}
                        className={`w-full min-h-[44px] flex items-center gap-3 px-3.5 py-2.5 text-left hover:bg-slate-800 transition-colors ${
                          isActive
                            ? "bg-slate-800/80 border-l-2 border-l-amber-500"
                            : ""
                        }`}
                      >
                        <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0 bg-slate-800 border border-slate-700">
                          {project.isGlobal ? (
                            <Globe className="w-3.5 h-3.5 text-slate-400" />
                          ) : (
                            <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold text-slate-100 truncate">
                            {label}
                          </p>
                          {project.location && (
                            <p className="text-[11px] text-slate-400 truncate">
                              {project.location}
                            </p>
                          )}
                        </div>
                        {isActive && (
                          <Check className="w-4 h-4 text-amber-400 shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>

                <div className="border-t border-slate-800 p-2 bg-slate-950">
                  <button
                    onClick={() => {
                      onCreateProject();
                      setDropdownOpen(false);
                    }}
                    className="w-full min-h-[44px] flex items-center justify-center gap-2 px-3 py-2 rounded-md text-xs font-mono font-bold uppercase tracking-wider text-amber-400 hover:bg-slate-800 hover:text-amber-300 border border-slate-800 hover:border-amber-500/40 transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    CREATE NEW WORKSPACE
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Manage Documents */}
          <button
            onClick={onOpenDrawer}
            className="min-h-[44px] flex items-center gap-2 px-3.5 sm:px-4 py-2 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm border border-amber-600 active:translate-y-0.5"
          >
            <Files className="w-4 h-4 text-slate-950" strokeWidth={2.5} />
            <span className="hidden sm:inline">MANAGE DOCUMENTS</span>
            <span className="sm:hidden">DOCS</span>
          </button>
        </div>
      </div>
    </header>
  );
}
