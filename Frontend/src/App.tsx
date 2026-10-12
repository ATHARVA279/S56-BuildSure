import { useCallback, useEffect, useState } from "react";
import type {
  AISummary,
  Document,
  Project,
  ScopeFilter,
  SearchResult,
  AppView,
} from "@/types";
import {
  createProject,
  deleteDocument,
  getHealth,
  listDocuments,
  listProjects,
  searchCompliance,
  uploadDocument,
} from "@/api";
import Header from "@/components/Header";
import CreateProjectModal from "@/components/CreateProjectModal";
import DocumentDrawer from "@/components/DocumentDrawer";
import SearchSection from "@/components/SearchSection";
import ResultsSection from "@/components/ResultsSection";
import SplitViewer from "@/components/SplitViewer";

const GLOBAL_PROJECT: Project = {
  id: "global",
  name: "Global Repository",
  location: "",
  isGlobal: true,
};

function withGlobal(projects: Project[]): Project[] {
  const rest = projects.filter(
    (project) => project.id !== "global" && !project.isGlobal,
  );
  return [...rest, GLOBAL_PROJECT];
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([GLOBAL_PROJECT]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string>("global");
  const [view, setView] = useState<AppView>("search");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>("all");
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(
    null,
  );
  const [summary, setSummary] = useState<AISummary | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [hasDeficiency, setHasDeficiency] = useState(false);
  const [deficiencyText, setDeficiencyText] = useState<string | null>(null);
  const [deficiencyStatus, setDeficiencyStatus] = useState<string | null>(null);
  const [retrievalNote, setRetrievalNote] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refreshDocuments = useCallback(async (projectId: string) => {
    const rows = await listDocuments(projectId);
    setDocuments(rows);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [health, rows] = await Promise.all([getHealth(), listProjects()]);
        if (cancelled) return;
        setProjects(withGlobal(rows));
        const notes = [];
        if (!health.llm_configured) {
          notes.push(
            "GROQ_API_KEY is not set, so answers quote retrieved text.",
          );
        }
        if (health.vector_search !== "atlas_with_cosine_fallback") {
          notes.push(
            "Search is using the local cosine fallback, not MongoDB Atlas Vector Search.",
          );
        }
        if (!health.database_connected) {
          notes.push("The document store is not connected.");
        }
        setStatusNote(notes.join(" ") || null);
      } catch {
        if (!cancelled) {
          setStatusNote(
            "The BuildSure API is not reachable. Start the backend, then refresh this page.",
          );
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    refreshDocuments(activeProjectId).catch(() => {
      if (!cancelled) setDocuments([]);
    });
    return () => {
      cancelled = true;
    };
  }, [activeProjectId, refreshDocuments]);

  async function handleSearch(query: string, scope: ScopeFilter) {
    setSearchQuery(query);
    setScopeFilter(scope);
    setView("results");
    setLoading(true);
    setSearchError(null);
    setSummary(null);
    setResults([]);
    setHasDeficiency(false);
    setDeficiencyText(null);
    setDeficiencyStatus(null);
    setRetrievalNote(null);
    try {
      const payload = await searchCompliance(query, activeProjectId, scope);
      setSummary(payload.summary);
      setResults(payload.results);
      setHasDeficiency(payload.hasDeficiency);
      setDeficiencyText(payload.deficiencyText);
      setDeficiencyStatus(payload.deficiencyStatus);
      setRetrievalNote(payload.retrievalNote);
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function handleViewPdf(result: SearchResult) {
    setSelectedResult(result);
    setView("split-viewer");
  }

  async function handleCreateProject(input: {
    name: string;
    location: string;
  }) {
    const created = await createProject(input);
    setProjects((current) =>
      withGlobal([
        ...current.filter((project) => project.id !== created.id),
        created,
      ]),
    );
    setActiveProjectId(created.id);
    setView("search");
    setSearchQuery("");
  }

  function handleProjectChange(id: string) {
    setActiveProjectId(id);
    setView("search");
    setSearchQuery("");
    setSummary(null);
    setResults([]);
    setSearchError(null);
  }

  async function handleUpload(
    file: File,
    meta: { scope: "global" | "project"; docType: string },
  ) {
    setUploading(true);
    setUploadError(null);
    setUploadMessage(null);
    try {
      const result = await uploadDocument(file, {
        projectId: activeProjectId,
        scope: meta.scope,
        docType: meta.docType,
      });
      setUploadMessage(
        `Indexed ${result.file_name}: ${result.pages_processed} page(s), ${result.chunks_stored} chunk(s).`,
      );
      await refreshDocuments(activeProjectId);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(documentId: string) {
    setUploadError(null);
    try {
      await deleteDocument(documentId, activeProjectId);
      await refreshDocuments(activeProjectId);
    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : "Could not delete the document",
      );
    }
  }

  const activeProject =
    projects.find((project) => project.id === activeProjectId) ??
    GLOBAL_PROJECT;

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#1F2937] antialiased">
      <Header
        projects={projects}
        activeProjectId={activeProjectId}
        onProjectChange={handleProjectChange}
        onOpenDrawer={() => setDrawerOpen(true)}
        onCreateProject={() => setCreateModalOpen(true)}
      />

      <main className="pt-16 min-h-screen">
        {statusNote && (
          <div className="bg-slate-900 text-amber-200 text-xs font-mono px-4 py-2 text-center">
            {statusNote}
          </div>
        )}
        {view === "search" && (
          <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] px-3 sm:px-4 py-6 sm:py-10">
            <SearchSection
              activeProjectId={activeProjectId}
              projectName={activeProject.name}
              onSearch={handleSearch}
              loading={loading}
            />
          </div>
        )}

        {view === "results" && (
          <div className="py-4 px-2 sm:px-4">
            <ResultsSection
              query={searchQuery}
              scope={scopeFilter}
              activeProjectId={activeProjectId}
              projectName={activeProject.name}
              aiSummary={summary}
              results={results}
              loading={loading}
              error={searchError}
              hasDeficiency={hasDeficiency}
              deficiencyText={deficiencyText}
              deficiencyStatus={deficiencyStatus}
              retrievalNote={retrievalNote}
              onNewSearch={handleSearch}
              onViewPdf={handleViewPdf}
            />
          </div>
        )}

        {view === "split-viewer" && selectedResult && summary && (
          <SplitViewer
            result={selectedResult}
            aiSummary={summary}
            hasDeficiency={hasDeficiency}
            deficiencyText={deficiencyText}
            onClose={() => setView("results")}
          />
        )}
      </main>

      <DocumentDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        documents={documents}
        activeProjectId={activeProjectId}
        projectName={activeProject.name}
        onUpload={handleUpload}
        onDelete={handleDelete}
        uploading={uploading}
        uploadMessage={uploadMessage}
        uploadError={uploadError}
      />

      {createModalOpen && (
        <CreateProjectModal
          onClose={() => setCreateModalOpen(false)}
          onCreate={handleCreateProject}
        />
      )}
    </div>
  );
}
