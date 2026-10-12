import type { AISummary, Document, Project, ScopeFilter, SearchResult } from '@/types';

const BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export interface HealthStatus {
  status: string;
  storage: string;
  vector_search: string;
  llm_configured: boolean;
  database_connected: boolean;
}

export interface SearchPayload {
  summary: AISummary;
  results: SearchResult[];
  hasDeficiency: boolean;
  deficiencyText: string | null;
  deficiencyStatus: string | null;
  generationMode: string;
  retrievalNote: string | null;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    let message = response.statusText || 'Request failed';
    try {
      const body = await response.json();
      message = detailMessage(body, message);
    } catch {
      // The body was not JSON.
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

function detailMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object' || !('detail' in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: unknown }).msg);
        return String(item);
      })
      .join(' ');
  }
  return fallback;
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/api/health');
}

export async function listProjects(): Promise<Project[]> {
  const rows = await request<Array<Project & { isGlobal?: boolean }>>('/api/projects');
  return rows.map((row) => ({
    id: row.id,
    name: row.name,
    location: row.location ?? '',
    isGlobal: Boolean(row.isGlobal),
  }));
}

export async function createProject(input: { name: string; location: string }): Promise<Project> {
  const created = await request<Project & { isGlobal?: boolean }>('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_name: input.name, location: input.location }),
  });
  return {
    id: created.id,
    name: created.name,
    location: created.location ?? '',
    isGlobal: Boolean(created.isGlobal),
  };
}

export async function listDocuments(projectId: string): Promise<Document[]> {
  const rows = await request<Array<Record<string, unknown>>>(
    `/api/documents?project_id=${encodeURIComponent(projectId)}`,
  );
  return rows.map((row) => ({
    id: String(row.id ?? ''),
    name: String(row.name ?? ''),
    scope: row.scope === 'global' ? 'global' : 'local',
    category: (row.category as Document['category']) ?? 'building-code',
    projectId: String(row.projectId ?? ''),
    pages: Number(row.pages ?? 0),
    size: String(row.size ?? ''),
    uploadedAt: String(row.uploadedAt ?? ''),
    processingStatus: row.processing_status ? String(row.processing_status) : undefined,
    statusDetail: row.status_detail ? String(row.status_detail) : undefined,
  }));
}

export async function uploadDocument(
  file: File,
  input: { projectId: string; scope: 'global' | 'project'; docType: string },
): Promise<{ file_name: string; chunks_stored: number; pages_processed: number }> {
  const body = new FormData();
  body.append('file', file);
  body.append('project_id', input.scope === 'global' ? 'global' : input.projectId);
  body.append('scope', input.scope);
  body.append('doc_type', input.docType);
  return request('/api/documents/upload', { method: 'POST', body });
}

export function deleteDocument(documentId: string, projectId: string): Promise<{ status: string }> {
  return request(`/api/documents/${encodeURIComponent(documentId)}?project_id=${encodeURIComponent(projectId)}`, {
    method: 'DELETE',
  });
}

export async function searchCompliance(
  query: string,
  projectId: string,
  scope: ScopeFilter,
): Promise<SearchPayload> {
  const raw = await request<Record<string, unknown>>('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      project_id: projectId,
      doc_type_filter: scope,
    }),
  });
  const citations = Array.isArray(raw.citations) ? raw.citations : [];
  const cards = Array.isArray(raw.source_cards) ? raw.source_cards : [];
  return {
    summary: {
      answer: String(raw.ai_summary ?? ''),
      citations: citations.map((item) => {
        const citation = item as { label?: string; scope?: string; documentName?: string };
        return {
          label: citation.label ?? '',
          scope: citation.scope === 'local' ? 'local' : 'global',
          documentName: citation.documentName ?? '',
        };
      }),
    },
    results: cards.map((item) => {
      const card = item as Record<string, unknown>;
      return {
        id: String(card.id ?? ''),
        documentName: String(card.documentName ?? card.doc_name ?? 'Document'),
        documentId: String(card.documentId ?? card.document_id ?? ''),
        section: String(card.section ?? ''),
        page: Number(card.page_number ?? card.page ?? 1),
        snippet: String(card.quote ?? card.snippet ?? ''),
        scope: card.scope === 'local' ? 'local' : 'global',
        category: (card.category as SearchResult['category']) ?? 'building-code',
        pdfUrl: card.pdf_url ? String(card.pdf_url) : undefined,
        pageCount: card.page_count ? Number(card.page_count) : undefined,
        score: typeof card.score === 'number' ? card.score : undefined,
        findingStatus: (card.finding_status as SearchResult['findingStatus']) ?? 'none',
      };
    }),
    hasDeficiency: Boolean(raw.has_deficiency),
    deficiencyText: raw.deficiency_text ? String(raw.deficiency_text) : null,
    deficiencyStatus: raw.deficiency_status ? String(raw.deficiency_status) : null,
    generationMode: String(raw.generation_mode ?? ''),
    retrievalNote: raw.retrieval_note ? String(raw.retrieval_note) : null,
  };
}
