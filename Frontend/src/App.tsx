import { useState } from 'react';
import type { Project, SearchResult, ScopeFilter, AppView } from '@/types';
import { PROJECTS, DOCUMENTS, MOCK_AI_SUMMARY, MOCK_RESULTS, PROJECT_LABELS } from '@/data/mockData';
import Header from '@/components/Header';
import CreateProjectModal from '@/components/CreateProjectModal';
import DocumentDrawer from '@/components/DocumentDrawer';
import SearchSection from '@/components/SearchSection';
import ResultsSection from '@/components/ResultsSection';
import SplitViewer from '@/components/SplitViewer';

export default function App() {
  const [projects, setProjects] = useState<Project[]>(PROJECTS);
  const [activeProjectId, setActiveProjectId] = useState<string>('alpha');
  const [view, setView] = useState<AppView>('search');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all');
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);

  function handleSearch(query: string, scope: ScopeFilter) {
    setSearchQuery(query);
    setScopeFilter(scope);
    setView('results');
  }

  function handleViewPdf(result: SearchResult) {
    setSelectedResult(result);
    setView('split-viewer');
  }

  function handleCreateProject(project: Project) {
    const label = `${project.name} - New Project`;
    setProjects((prev) => [...prev.filter((p) => !p.isGlobal), project, prev[prev.length - 1]]);
    PROJECT_LABELS[project.id] = label;
    setActiveProjectId(project.id);
    setView('search');
  }

  function handleProjectChange(id: string) {
    setActiveProjectId(id);
    setView('search');
    setSearchQuery('');
  }

  const activeProject = projects.find((p) => p.id === activeProjectId);
  const projectDisplayName = PROJECT_LABELS[activeProjectId] ?? activeProject?.name ?? '';

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#1F2937] antialiased">
      <Header
        projects={projects}
        activeProjectId={activeProjectId}
        onProjectChange={handleProjectChange}
        onOpenDrawer={() => setDrawerOpen(true)}
        onCreateProject={() => setCreateModalOpen(true)}
      />

      {/* Main content */}
      <main className="pt-16 min-h-screen">
        {view === 'search' && (
          <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] px-3 sm:px-4 py-6 sm:py-10">
            <SearchSection
              activeProjectId={activeProjectId}
              onSearch={handleSearch}
            />
          </div>
        )}

        {view === 'results' && (
          <div className="py-4 px-2 sm:px-4">
            <ResultsSection
              query={searchQuery}
              scope={scopeFilter}
              activeProjectId={activeProjectId}
              aiSummary={MOCK_AI_SUMMARY}
              results={MOCK_RESULTS}
              onNewSearch={handleSearch}
              onViewPdf={handleViewPdf}
            />
          </div>
        )}

        {view === 'split-viewer' && selectedResult && (
          <SplitViewer
            result={selectedResult}
            aiSummary={MOCK_AI_SUMMARY}
            onClose={() => setView('results')}
          />
        )}
      </main>

      {/* Document Drawer */}
      <DocumentDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        documents={DOCUMENTS}
        activeProjectId={activeProjectId}
        projectName={projectDisplayName}
        onUpload={() => {}}
      />

      {/* Create Project Modal */}
      {createModalOpen && (
        <CreateProjectModal
          onClose={() => setCreateModalOpen(false)}
          onCreate={handleCreateProject}
        />
      )}
    </div>
  );
}
