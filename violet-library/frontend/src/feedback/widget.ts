import {
  buildSubmission, correctFeedback, deleteFeedback, feedbackEnabled, sendFeedback,
} from './client';
import type { FeedbackContext, Rating, Reason, Receipt } from './client';

export interface FeedbackState {
  receipt?: Receipt;
  rating?: Rating;
  reason?: Reason | null;
  savedRating?: Rating;
  savedReason?: Reason | null;
  editing?: boolean;
}

const REASONS: Array<[Reason, string]> = [
  ['wrong_topic', 'Wrong topic'], ['too_advanced', 'Too advanced'],
  ['too_basic', 'Too basic'], ['wrong_language', 'Wrong language'],
  ['inaccessible_link', 'Book link did not work'],
  ['poor_description', 'Description is unclear'], ['other', 'Another reason'],
];

function button(label: string, className: string, action: () => void): HTMLButtonElement {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = className;
  element.textContent = label;
  element.addEventListener('click', action);
  return element;
}

export function createFeedbackWidget(
  targetBookId: string | null,
  state: FeedbackState,
  context: () => FeedbackContext,
): HTMLElement {
  const root = document.createElement('div');
  root.className = targetBookId === null ? 'feedback-widget feedback-list' : 'feedback-widget';
  const wholeList = targetBookId === null;
  let busy = false;
  let message = '';

  const draw = (): void => {
    const heading = document.createElement('p');
    heading.className = 'feedback-heading';
    heading.textContent = wholeList ? 'None of these books fit?' : 'Did this book fit your search?';
    const status = document.createElement('p');
    status.className = 'feedback-message';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.textContent = message;
    const nodes: HTMLElement[] = [heading];

    if (!feedbackEnabled) {
      status.textContent = 'Feedback is temporarily unavailable.';
      nodes.push(status);
      root.replaceChildren(...nodes);
      return;
    }
    if (state.receipt && !state.editing) {
      const actions = document.createElement('div');
      actions.className = 'feedback-actions';
      const saved = document.createElement('span');
      saved.textContent = 'Thanks — your feedback was saved.';
      actions.append(saved);
      if (!wholeList) actions.append(button('Change', 'feedback-link', () => {
        state.editing = true; message = ''; draw();
      }));
      actions.append(button('Delete', 'feedback-link', () => { void remove(); }));
      nodes.push(actions, status);
      root.replaceChildren(...nodes);
      return;
    }

    if (wholeList) {
      const noneFit = button('Tell us none fit', 'feedback-option', () => {
        state.rating = 'none_fit'; message = ''; draw();
      });
      noneFit.disabled = busy;
      nodes.push(noneFit);
    } else {
      const choices = document.createElement('div');
      choices.className = 'feedback-choices';
      for (const [rating, label] of [
        ['useful', 'Useful'], ['partial', 'Somewhat useful'], ['not_useful', 'Not useful'],
      ] as Array<[Rating, string]>) {
        const choice = button(label, 'feedback-option', () => {
          state.rating = rating; message = ''; draw();
        });
        choice.setAttribute('aria-pressed', String(state.rating === rating));
        choice.disabled = busy;
        choices.append(choice);
      }
      nodes.push(choices);
    }

    if (state.rating && (wholeList || state.rating !== 'none_fit')) {
      if (state.rating !== 'useful' && state.rating !== 'none_fit') {
        const reasonLabel = document.createElement('label');
        reasonLabel.className = 'feedback-reason-label';
        reasonLabel.textContent = 'Why? (optional)';
        const select = document.createElement('select');
        select.className = 'feedback-reason';
        const none = document.createElement('option');
        none.value = ''; none.textContent = 'Choose a reason';
        select.append(none);
        for (const [value, label] of REASONS) {
          const option = document.createElement('option');
          option.value = value; option.textContent = label;
          select.append(option);
        }
        select.value = state.reason ?? '';
        select.addEventListener('change', () => { state.reason = (select.value || null) as Reason | null; });
        reasonLabel.append(select);
        nodes.push(reasonLabel);
      }
      const notice = document.createElement('p');
      notice.className = 'feedback-privacy';
      notice.textContent = 'Sending shares your search words, shown book IDs, search settings and rating. Please avoid personal details.';
      const send = button(busy ? 'Saving…' : 'Send feedback', 'feedback-send', () => { void save(); });
      send.disabled = busy;
      nodes.push(notice, send);
      if (state.receipt) nodes.push(button('Cancel change', 'feedback-link', () => {
        state.rating = state.savedRating;
        state.reason = state.savedReason;
        state.editing = false; message = ''; draw();
      }));
    }
    nodes.push(status);
    root.replaceChildren(...nodes);
  };

  const save = async (): Promise<void> => {
    if (busy || !state.rating) return;
    busy = true; message = ''; draw();
    try {
      const reason = state.rating === 'useful' || state.rating === 'none_fit' ? null : state.reason ?? null;
      if (state.receipt) {
        await correctFeedback(state.receipt, state.rating as Exclude<Rating, 'none_fit'>, reason);
      } else {
        state.receipt = await sendFeedback(buildSubmission(context(), targetBookId, state.rating, reason));
      }
      state.savedRating = state.rating;
      state.savedReason = reason;
      state.editing = false;
      state.reason = reason;
    } catch (error) {
      message = error instanceof Error ? error.message : 'Could not save feedback.';
    } finally {
      busy = false; draw();
    }
  };

  const remove = async (): Promise<void> => {
    if (busy || !state.receipt) return;
    busy = true; message = 'Deleting…'; draw();
    try {
      await deleteFeedback(state.receipt);
      state.receipt = undefined;
      state.rating = undefined;
      state.reason = null;
      state.savedRating = undefined;
      state.savedReason = null;
      state.editing = false;
      message = 'Your feedback was deleted.';
    } catch (error) {
      message = error instanceof Error ? error.message : 'Could not delete feedback.';
    } finally {
      busy = false; draw();
    }
  };

  draw();
  return root;
}
