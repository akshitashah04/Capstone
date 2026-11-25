import type { ModelKey, SearchMode } from '../types';

export type Rating = 'useful' | 'partial' | 'not_useful' | 'none_fit';
export type Reason = 'wrong_topic' | 'too_advanced' | 'too_basic' | 'wrong_language'
  | 'inaccessible_link' | 'poor_description' | 'other';

export interface FeedbackContext {
  query: string;
  model: ModelKey | 'keyword-only';
  mode: SearchMode | 'keyword-only';
  language?: string;
  release: string;
  catalogSha256: string;
  shownBooks: Array<{ bookId: string; rank: number }>;
}

export interface Submission {
  submissionId: string;
  query: string;
  results: Array<{ bookId: string; rank: number }>;
  targetBookId: string | null;
  rating: Rating;
  reason: Reason | null;
  model: FeedbackContext['model'];
  mode: FeedbackContext['mode'];
  language?: string;
  release: string;
  catalogSha256: string;
}

export interface Receipt { id: string; receipt: string }

const configuredUrl = import.meta.env.VITE_FEEDBACK_API_URL?.trim() ?? '';
export const feedbackEnabled = configuredUrl.startsWith('https://');

export function buildSubmission(
  context: FeedbackContext, targetBookId: string | null, rating: Rating, reason: Reason | null,
): Submission {
  if (rating === 'none_fit' ? targetBookId !== null
    : !context.shownBooks.some(book => book.bookId === targetBookId)) {
    throw new Error('Feedback must refer to a displayed book.');
  }
  return {
    submissionId: crypto.randomUUID(), query: context.query,
    results: context.shownBooks.map(book => ({ ...book })),
    targetBookId, rating, reason, model: context.model, mode: context.mode,
    ...(context.language ? { language: context.language } : {}),
    release: context.release, catalogSha256: context.catalogSha256,
  };
}

async function request(path: string, method: string, body?: unknown, receipt?: string): Promise<Response> {
  if (!feedbackEnabled) throw new Error('Feedback is temporarily unavailable.');
  let response: Response;
  try {
    response = await fetch(`${configuredUrl}${path}`, {
      method,
      headers: {
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(receipt ? { 'X-Feedback-Receipt': receipt } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new Error('Feedback could not connect. Please try again.');
  }
  if (response.status === 429) throw new Error('Today’s feedback limit has been reached.');
  if (!response.ok) throw new Error('Feedback could not be saved. Please try again.');
  return response;
}

export async function sendFeedback(submission: Submission): Promise<Receipt> {
  return await (await request('/v1/feedback', 'POST', submission)).json() as Receipt;
}

export async function correctFeedback(receipt: Receipt, rating: Exclude<Rating, 'none_fit'>,
  reason: Reason | null): Promise<void> {
  await request(`/v1/feedback/${encodeURIComponent(receipt.id)}`, 'PUT', { rating, reason }, receipt.receipt);
}

export async function deleteFeedback(receipt: Receipt): Promise<void> {
  await request(`/v1/feedback/${encodeURIComponent(receipt.id)}`, 'DELETE', undefined, receipt.receipt);
}
