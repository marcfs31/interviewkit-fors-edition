import { apiFetch, handleResponse } from "./httpClient";

export interface StackResponse {
  rol: Record<string, string[]>;
  level: string[];
  topic: Record<string, string[]>;
}

export async function getStacks(): Promise<StackResponse> {
  const response = await apiFetch("/stacks/");
  return handleResponse<StackResponse>(response);
}
