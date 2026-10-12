import { useState } from 'react';
import { X, MapPin, FolderPlus } from 'lucide-react';

interface Props {
  onClose: () => void;
  onCreate: (input: { name: string; location: string }) => Promise<void>;
}

export default function CreateProjectModal({ onClose, onCreate }: Props) {
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      await onCreate({ name: name.trim(), location: location.trim() });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the project');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3">
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-xs" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-md border-2 border-slate-700 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-slate-950 px-5 py-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-amber-500 rounded-md flex items-center justify-center border border-amber-600">
              <FolderPlus className="w-4 h-4 text-slate-950" strokeWidth={2.5} />
            </div>
            <div>
              <p className="text-[10px] font-mono font-bold text-amber-400 uppercase tracking-widest">CONFIGURATION</p>
              <h2 className="text-white font-mono font-bold text-sm uppercase">NEW FIELD WORKSPACE</h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="min-h-[40px] min-w-[40px] rounded-md flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 font-sans">
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider text-slate-800 mb-1.5">
              WORKSPACE / PROJECT NAME <span className="text-red-600">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Riverfront Commercial Tower"
              className="min-h-[52px] w-full px-3.5 py-2.5 rounded-md border-2 border-slate-300 text-slate-900 font-bold placeholder:text-slate-400 placeholder:font-normal focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-all text-sm"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider text-slate-800 mb-1.5">
              JURISDICTION / SITE LOCATION
            </label>
            <div className="relative">
              <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Chicago, IL"
                className="min-h-[52px] w-full pl-10 pr-3.5 py-2.5 rounded-md border-2 border-slate-300 text-slate-900 font-bold placeholder:text-slate-400 placeholder:font-normal focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-all text-sm"
              />
            </div>
          </div>

          {error && (
            <p className="text-xs font-mono font-bold text-red-700" role="alert">
              {error}
            </p>
          )}

          <div className="pt-2 flex gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] flex-1 px-4 py-2 rounded-md border-2 border-slate-300 text-slate-800 font-mono font-bold text-xs uppercase tracking-wider hover:bg-slate-100 transition-colors"
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="min-h-[44px] flex-1 px-4 py-2 rounded-md bg-amber-500 text-slate-950 font-mono font-bold text-xs uppercase tracking-wider hover:bg-amber-400 active:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed border border-amber-600 shadow-xs transition-colors"
            >
              {saving ? 'SAVING' : 'INITIALIZE WORKSPACE'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
