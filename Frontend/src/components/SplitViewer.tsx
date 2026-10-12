import { useState } from 'react';
import { X, ArrowLeft, Globe, FolderOpen, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Download, BookOpen, AlertTriangle } from 'lucide-react';
import type { SearchResult, AISummary } from '@/types';
import { PDF_MOCK_PAGES } from '@/data/mockData';

interface Props {
  result: SearchResult;
  aiSummary: AISummary;
  onClose: () => void;
}

export default function SplitViewer({ result, aiSummary, onClose }: Props) {
  const [page, setPage] = useState(result.page);
  const [zoom, setZoom] = useState(1);

  const isProject = result.scope === 'local';
  const mockPage = PDF_MOCK_PAGES[result.id];
  const relevantCitations = aiSummary.citations.filter(
    (c) => c.documentName === result.documentName
  );

  return (
    <div className="fixed inset-0 z-50 bg-slate-950 flex flex-col font-sans">
      {/* Field Toolbar */}
      <div className="bg-slate-900 border-b border-slate-800 px-3 sm:px-4 py-2.5 flex items-center justify-between gap-3 shrink-0 shadow-sm">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <button
            onClick={onClose}
            className="min-h-[44px] px-3 rounded-md flex items-center gap-2 text-slate-300 hover:text-white hover:bg-slate-800 text-xs font-mono font-bold uppercase tracking-wider transition-colors border border-transparent hover:border-slate-700"
          >
            <ArrowLeft className="w-4 h-4 text-amber-400" />
            <span className="hidden sm:inline">BACK TO RESULTS</span>
          </button>
          <div className="w-px h-5 bg-slate-700 shrink-0" />
          <div className="flex items-center gap-2 min-w-0">
            <div
              className={`flex items-center gap-1.5 text-[11px] font-mono font-extrabold px-2.5 py-1 rounded-md border uppercase tracking-wider shrink-0 ${
                isProject
                  ? 'bg-amber-500/15 text-amber-400 border-amber-500/40'
                  : 'bg-slate-800 text-slate-300 border-slate-700'
              }`}
            >
              {isProject ? <FolderOpen className="w-3 h-3 text-amber-400" /> : <Globe className="w-3 h-3 text-slate-400" />}
              {isProject ? 'OFFICIAL SPEC' : 'GLOBAL CODE'}
            </div>
            <span className="text-slate-100 font-mono text-xs font-bold truncate max-w-xs sm:max-w-md">
              {result.documentName}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Zoom controls */}
          <div className="flex items-center bg-slate-800 border border-slate-700 rounded-md p-0.5">
            <button
              onClick={() => setZoom((z) => Math.max(0.7, z - 0.1))}
              className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-sm text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
              title="Zoom out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono font-bold text-amber-400 w-12 text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom((z) => Math.min(2, z + 0.1))}
              className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-sm text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
              title="Zoom in"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>
          <button
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-colors"
            title="Download document"
          >
            <Download className="w-4 h-4 text-amber-400" />
          </button>
          <button
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-colors"
            title="Close viewer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Split panels */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
        {/* Left panel — Technical Reference Details */}
        <div className="w-full md:w-96 lg:w-[420px] bg-[#F8FAFC] flex flex-col overflow-hidden border-r border-[#E2E8F0] shrink-0">
          <div className="px-4 py-3 border-b border-[#E2E8F0] bg-white shrink-0">
            <div className="flex items-center gap-1.5 mb-1 text-slate-700 font-mono text-[11px] font-bold uppercase tracking-wider">
              <BookOpen className="w-3.5 h-3.5 text-amber-600" />
              <span>EXTRACTED CODE REFERENCE</span>
            </div>
            <h3 className="text-sm font-mono font-extrabold text-slate-950 leading-snug">
              {result.section}
            </h3>
            <p className="text-xs font-mono text-slate-700 mt-1 font-semibold">
              {result.documentName} — <span className="text-slate-950 font-bold">PAGE {result.page}</span>
            </p>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Verbatim snippet */}
            <div>
              <p className="text-[11px] font-mono font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                VERBATIM SPECIFICATION TEXT
              </p>
              <blockquote className="pl-3.5 text-xs sm:text-sm text-[#1F2937] leading-relaxed border-l-4 border-amber-500 bg-white p-3 rounded-r-md border border-slate-300 shadow-2xs font-sans font-medium">
                "{result.snippet}"
              </blockquote>
            </div>

            {/* AI Citation Cross-references */}
            {relevantCitations.length > 0 && (
              <div>
                <p className="text-[11px] font-mono font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                  CROSS-REFERENCED CITATIONS
                </p>
                <div className="space-y-1.5">
                  {relevantCitations.map((c, i) => (
                    <div key={i} className="flex items-center gap-2.5 p-2.5 bg-white rounded-md border border-slate-300 shadow-2xs">
                      <div className={`w-6 h-6 rounded-sm flex items-center justify-center shrink-0 ${c.scope === 'global' ? 'bg-slate-200 text-slate-700' : 'bg-amber-100 text-amber-800'}`}>
                        {c.scope === 'global' ? <Globe className="w-3 h-3" /> : <FolderOpen className="w-3 h-3" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-mono font-bold text-slate-900 truncate">{c.label}</p>
                        <p className="text-[10px] font-mono uppercase text-slate-600 font-semibold">
                          {c.scope === 'global' ? 'GLOBAL CODE REPOSITORY' : 'OFFICIAL PROJECT SPEC'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Compliance Hazard Banner */}
            {result.category === 'inspection-report' && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/80 border-l-4 border-l-amber-600 rounded-md">
                <div className="flex items-center gap-1.5 text-amber-950 font-mono text-[11px] font-black uppercase tracking-wider mb-1">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  ACTIVE COMPLIANCE DEFICIENCY
                </div>
                <p className="text-xs font-semibold text-amber-950 leading-relaxed">
                  Correction required per IBC 2021 egress clearance. Field correction must be confirmed by inspector prior to Certificate of Occupancy.
                </p>
              </div>
            )}

            {/* Document metadata table */}
            <div>
              <p className="text-[11px] font-mono font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                METADATA & SPEC SHEET
              </p>
              <div className="bg-white border border-slate-300 rounded-md p-3 divide-y divide-[#E2E8F0] text-xs font-mono">
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600 uppercase">DOCUMENT</span>
                  <span className="font-bold text-slate-950 text-right max-w-[180px] truncate">{result.documentName}</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600 uppercase">SECTION</span>
                  <span className="font-bold text-slate-950 text-right">{result.section.split('—')[0].trim()}</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600 uppercase">PAGE NUM</span>
                  <span className="font-bold text-slate-950">p. {result.page}</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600 uppercase">JURISDICTION</span>
                  <span className={`font-bold ${isProject ? 'text-amber-800' : 'text-slate-900'}`}>
                    {isProject ? 'OFFICIAL PROJECT SPEC' : 'GLOBAL CODE REG'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right panel — Mock Blueprint / PDF Viewer */}
        <div className="flex-1 bg-slate-900 flex flex-col overflow-hidden">
          {/* Page nav */}
          <div className="bg-slate-950 border-b border-slate-800 px-4 py-2 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-md text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                title="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono font-bold text-slate-300 px-2">
                PAGE <span className="text-amber-400 font-extrabold">{page}</span>
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-md text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                title="Next page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <span className="text-xs font-mono text-slate-400 font-medium truncate max-w-sm">
              {result.documentName}
            </span>
          </div>

          {/* PDF Page Display */}
          <div className="flex-1 overflow-auto flex items-start justify-center p-4 sm:p-8">
            <div
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
              className="transition-transform duration-150"
            >
              <MockPdfPage
                lines={mockPage?.lines ?? generateGenericPage(result)}
                highlightLines={mockPage?.highlightLines ?? [4, 5, 6]}
                page={page}
                documentName={result.documentName}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MockPdfPage({
  lines,
  highlightLines,
  page,
  documentName,
}: {
  lines: string[];
  highlightLines: number[];
  page: number;
  documentName: string;
}) {
  return (
    <div
      className="bg-white shadow-2xl rounded-sm border-2 border-slate-300"
      style={{ width: '612px', minHeight: '792px', padding: '64px 64px 72px' }}
    >
      {/* Document header bar */}
      <div className="border-b-2 border-slate-900 pb-3 mb-6 flex justify-between items-baseline font-mono">
        <p className="text-[11px] text-slate-900 uppercase tracking-widest font-extrabold">{documentName}</p>
        <span className="text-[10px] text-slate-600 font-bold uppercase">FIELD SPECIFICATION ARCHIVE</span>
      </div>

      {/* Content lines */}
      <div className="space-y-1 font-mono text-[13px] leading-relaxed">
        {lines.map((line, i) => {
          const isHighlighted = highlightLines.includes(i);
          if (line === '') return <div key={i} className="h-3" />;
          const isSectionHeader = /^[A-Z\s]+$/.test(line) && line.length > 3 && !line.includes('(');
          const isSubHeader = /^\d{4}(\.\d+)*\s/.test(line);
          return (
            <div
              key={i}
              className={`px-2 -mx-2 rounded-xs transition-colors ${
                isHighlighted
                  ? 'bg-amber-300/80 border-l-4 border-amber-600 pl-3 -ml-5 py-0.5 text-slate-950 font-bold'
                  : ''
              }`}
            >
              <span
                className={
                  isSectionHeader
                    ? 'font-bold text-slate-950 tracking-wide text-sm'
                    : isSubHeader
                    ? 'font-semibold text-slate-900'
                    : isHighlighted
                    ? 'text-slate-950 font-semibold'
                    : 'text-slate-800'
                }
              >
                {line}
              </span>
            </div>
          );
        })}
      </div>

      {/* Page footer */}
      <div className="mt-12 pt-4 border-t border-slate-200 flex justify-between items-center font-mono text-[11px] text-slate-600">
        <span>BUILDSURE VERIFIED</span>
        <span className="font-bold text-slate-950">PAGE {page}</span>
      </div>
    </div>
  );
}

function generateGenericPage(result: SearchResult): string[] {
  return [
    result.documentName.toUpperCase(),
    '',
    result.section.split('—')[0].trim().toUpperCase(),
    '',
    result.section,
    result.snippet.slice(0, 80),
    result.snippet.slice(80, 160),
    result.snippet.slice(160, 240) || '',
    result.snippet.slice(240) || '',
    '',
    'Additional provisions may apply. Refer to referenced standards',
    'for complete compliance requirements.',
    '',
    'All measurements in imperial and SI units per Table 1004.1.2.',
    '',
    '(continued on next page)',
  ];
}
