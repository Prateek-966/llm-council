/**
 * API client for the LLM Council backend.
 */

// Set VITE_API_URL at build time to point the UI at a deployed backend.
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * A fetch that fails loudly. A dead backend, a blocked CORS preflight and an HTTP
 * error are three different problems with three different fixes, and the browser
 * reports the first two identically as an opaque TypeError - so name them here.
 */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (cause) {
    const err = new Error(
      `Cannot reach the backend at ${API_BASE}. It may still be waking up ` +
        `(free instances sleep after 15 minutes idle, and cold starts take 30-60s), ` +
        `or the browser blocked the request because this page's origin is not in ` +
        `the backend's ALLOWED_ORIGINS.`
    );
    err.kind = 'network';
    err.cause = cause;
    throw err;
  }

  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body.detail || body.message || '';
    } catch {
      detail = '';
    }
    const err = new Error(
      detail || `The backend returned HTTP ${response.status}.`
    );
    err.kind = 'http';
    err.status = response.status;
    throw err;
  }

  return response;
}

export const api = {
  /**
   * Backend status: which storage backend is live, and the configured council.
   */
  async getHealth() {
    const response = await request('/');
    return response.json();
  },

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await request('/api/conversations');
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await request('/api/conversations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await request(`/api/conversations/${conversationId}`);
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await request(
      `/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await request(
      `/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
};
