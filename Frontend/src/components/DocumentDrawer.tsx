import { useState, useCallback } from 'react';
import { X, FileText, Globe, FolderOpen, Upload, ChevronRight, Trash2 } from 'lucide-react';
import type { Document } from '@/types';

interface Props {
  open: boolean;
  onClose: () => void;
  documents: Document[];
  activeProjectId: string;
  projectName: string;
  onUpload: (file: File) => void;
}

const CATEGORY_LABELS: Record<Document['category'], string> = {
  'building-code': 'BUILDING CODE',
  'project-spec': 'PROJECT SPEC',
  'inspection-report': 'INSPECTION REPORT',
};

const CATEGORY_COLORS: Record<Document['category'], string> = {
  'building-code': 'bg-slate-200 text-slate-900 border-slate-300',
  'project-spec': 'bg-amber-100 text-amber-950 border-amber-300',
  'inspection-report': 'bg-red-100 text-red-950 border-red-300',
};

export default function DocumentDrawer({
  open,
  onClose,
  documents,
  activeProjectId,
  projectName,
  onUpload,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);

  const relevantDocs = documents.filter(
    (d) => d.scope === 'global' || d.projectId === activeProjectId
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file && file.type === 'application/pdf') {
        setUploadedFiles((prev) => [...prev, file.name]);
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFiles((prev) => [...prev, file.name]);
      onUpload(file);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-slate-950/70 backdrop-blur-xs transition-opacity duration-200 ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={`fixed right-0 top-0 bottom-0 z-50 w-full max-w-lg bg-[#F8FAFC] shadow-2xl flex flex-col border-l border-slate-700 transition-transform duration-200 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="bg-slate-950 border-b border-slate-800 px-5 py-3.5 flex items-center justify-between shrink-0">
          <div>
            <p className="text-[10px] font-mono font-bold text-amber-400 uppercase tracking-widest">
              FIELD REPOSITORY
            </p>
            <h2 className="text-white font-mono font-extrabold text-sm uppercase tracking-wide mt-0.5">
              {projectName}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] rounded-md flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Stats */}
        <div className="flex divide-x divide-slate-300 border-b border-slate-300 bg-white shrink-0">
          {[
            { label: 'GLOBAL CODES', count: relevantDocs.filter((d) => d.scope === 'global').length, color: 'text-slate-950' },
            { label: 'PROJECT DOCS', count: relevantDocs.filter((d) => d.scope === 'local').length, color: 'text-amber-800' },
            { label: 'TOTAL PAGES', count: relevantDocs.reduce((s, d) => s + d.pages, 0), color: 'text-slate-950' },
          ].map(({ label, count, color }) => (
            <div key={label} className="flex-1 px-3 py-2.5 text-center">
              <p className={`text-lg font-mono font-extrabold ${color}`}>{count.toLocaleString()}</p>
              <p className="text-[10px] font-mono font-bold text-slate-600 uppercase tracking-wider mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto divide-y divide-[#E2E8F0]">
          {/* Global Section */}
          <div className="p-3 sm:p-4">
            <div className="flex items-center gap-1.5 mb-2 font-mono text-[11px] font-bold text-slate-700 uppercase tracking-wider">
              <Globe className="w-3.5 h-3.5 text-slate-600" />
              <span>GLOBAL BUILDING CODES</span>
            </div>
            <div className="space-y-1.5">
              {relevantDocs.filter((d) => d.scope === 'global').map((doc) => (
                <DocumentRow key={doc.id} doc={doc} />
              ))}
            </div>
          </div>

          {/* Project Section */}
          {activeProjectId !== 'global' && (
            <div className="p-3 sm:p-4">
              <div className="flex items-center gap-1.5 mb-2 font-mono text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                <FolderOpen className="w-3.5 h-3.5 text-amber-600" />
                <span>PROJECT SPECIFICATIONS & REPORTS</span>
              </div>
              <div className="space-y-1.5">
                {relevantDocs.filter((d) => d.scope === 'local').map((doc) => (
                  <DocumentRow key={doc.id} doc={doc} />
                ))}
                {uploadedFiles.map((name, i) => (
                  <div
                    key={`uploaded-${i}`}
                    className="min-h-[44px] flex items-center gap-3 px-3 py-2 rounded-md border border-amber-400 bg-amber-500/10"
                  >
                    <FileText className="w-4 h-4 text-amber-600 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-mono font-bold text-amber-950 truncate">{name}</p>
                      <p className="text-[10px] font-mono text-amber-800 font-semibold uppercase">OCR PROCESSING IN PROGRESS...</p>
                    </div>
                    <span className="text-[10px] font-mono font-extrabold bg-amber-400 text-slate-950 px-2 py-0.5 rounded-sm uppercase">
                      INDEXING
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Upload Dropzone */}
        {activeProjectId !== 'global' && (
          <div className="p-3 sm:p-4 border-t border-slate-300 bg-white shrink-0">
            <label
              htmlFor="pdf-upload"
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center gap-1.5 w-full py-4 rounded-md border-2 border-dashed cursor-pointer transition-all ${
                dragging
                  ? 'border-amber-500 bg-amber-500/15'
                  : 'border-slate-300 bg-[#F8FAFC] hover:border-amber-500 hover:bg-amber-50/40'
              }`}
            >
              <div className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${dragging ? 'bg-amber-400 text-slate-950' : 'bg-white border border-slate-300 text-slate-700'}`}>
                <Upload className="w-4 h-4" />
              </div>
              <div className="text-center font-mono">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  {dragging ? 'DROP PDF TO INDEX' : 'UPLOAD FIELD SPECIFICATION PDF'}
                </p>
                <p className="text-[10px] text-slate-600 font-medium">Click to browse or drag file here</p>
              </div>
              <input
                id="pdf-upload"
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileInput}
              />
            </label>
          </div>
        )}
      </div>
    </>
  );
}

function DocumentRow({ doc }: { doc: Document }) {
  const [hovered, setHovered] = useState(false);
  const categoryLabel = CATEGORY_LABELS[doc.category];
  const categoryColor = CATEGORY_COLORS[doc.category];

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="min-h-[44px] flex items-center gap-2.5 px-3 py-2 rounded-md border border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50 transition-all shadow-2xs group"
    >
      <div className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 border ${doc.scope === 'global' ? 'bg-slate-100 border-slate-200 text-slate-700' : 'bg-amber-50 border-amber-200 text-amber-700'}`}>
        <FileText className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-bold text-slate-950 truncate leading-snug">{doc.name}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`text-[10px] font-mono font-extrabold px-1.5 py-0.2 rounded-xs border uppercase ${categoryColor}`}>
            {categoryLabel}
          </span>
          <span className="text-[10px] font-mono font-semibold text-slate-700">{doc.pages}P · {doc.size}</span>
        </div>
      </div>
      {hovered ? (
        <button
          className="min-h-[36px] min-w-[36px] rounded-md flex items-center justify-center text-slate-500 hover:text-red-700 hover:bg-red-50 transition-colors shrink-0"
          title="Delete document"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      ) : (
        <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      )}
    </div>
  );
}
