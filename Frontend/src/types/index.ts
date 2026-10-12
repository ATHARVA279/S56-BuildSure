export interface Project {
  id: string;
  name: string;
  location: string;
  isGlobal?: boolean;
}

export interface Document {
  id: string;
  name: string;
  scope: 'global' | 'local';
  category: 'building-code' | 'project-spec' | 'inspection-report';
  projectId: string;
  pages: number;
  size: string;
  uploadedAt: string;
  processingStatus?: string;
  statusDetail?: string;
}

export type ScopeFilter = 'all' | 'project-specs' | 'inspection-reports' | 'building-codes';
export type AppView = 'search' | 'results' | 'split-viewer';

export interface SearchResult {
  id: string;
  documentName: string;
  documentId: string;
  section: string;
  page: number;
  snippet: string;
  scope: 'global' | 'local';
  category: 'building-code' | 'project-spec' | 'inspection-report';
  pdfUrl?: string;
  pageCount?: number;
  score?: number;
  findingStatus?: 'open' | 'closed' | 'unverified' | 'none';
}

export interface AISummary {
  answer: string;
  citations: Array<{
    label: string;
    scope: 'global' | 'local';
    documentName: string;
  }>;
}
