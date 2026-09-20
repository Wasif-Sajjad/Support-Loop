import type {
  TicketCreate,
  TicketResponse,
  TicketTrace,
  MetricsSummary,
  Decision,
} from "./types";
import { ApiError } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Could not reach the backend. Confirm it's running on " + API_URL);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.json() as Promise<T>;
}

export function createTicket(payload: TicketCreate): Promise<TicketResponse> {
  return request<TicketResponse>("/tickets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTicket(id: string): Promise<TicketResponse> {
  return request<TicketResponse>(`/tickets/${id}`);
}

export function getTicketTrace(id: string): Promise<TicketTrace> {
  return request<TicketTrace>(`/tickets/${id}/trace`);
}

export function listTickets(decision?: Decision): Promise<TicketResponse[]> {
  const qs = decision ? `?decision=${decision}` : "";
  return request<TicketResponse[]>(`/tickets${qs}`);
}

export function getMetricsSummary(): Promise<MetricsSummary> {
  return request<MetricsSummary>("/metrics/summary");
}
