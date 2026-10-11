import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  // Failures that are about the app itself (backend unreachable, request rejected)
  // rather than about one model inside a round.
  const [appError, setAppError] = useState(null);
  const [health, setHealth] = useState(null);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
    api
      .getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
      setAppError(null);
    } catch (error) {
      console.error('Failed to load conversations:', error);
      setAppError({
        model: 'backend',
        kind: error.kind === 'network' ? 'network' : 'http_error',
        status: error.status || null,
        message: error.message,
        hint: 'Could not load your conversations.',
        stage: null,
      });
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
      setAppError(null);
    } catch (error) {
      console.error('Failed to load conversation:', error);
      setAppError({
        model: 'backend',
        kind: error.kind === 'network' ? 'network' : 'http_error',
        status: error.status || null,
        message: error.message,
        hint: 'Could not open that conversation.',
        stage: null,
      });
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setAppError(null);
    } catch (error) {
      console.error('Failed to create conversation:', error);
      setAppError({
        model: 'backend',
        kind: error.kind === 'network' ? 'network' : 'http_error',
        status: error.status || null,
        message: error.message,
        hint: 'Could not start a new conversation.',
        stage: null,
      });
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        errors: [],
        councilSize: null,
        fatal: false,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage1 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage1 = event.data;
              lastMsg.errors = [...(lastMsg.errors || []), ...(event.errors || [])];
              lastMsg.councilSize = event.council_size ?? lastMsg.councilSize;
              lastMsg.loading.stage1 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage2 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage2 = event.data;
              lastMsg.metadata = event.metadata;
              lastMsg.errors = [...(lastMsg.errors || []), ...(event.errors || [])];
              lastMsg.loading.stage2 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage3 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage3 = event.data;
              if (event.data && event.data.error) {
                lastMsg.errors = [...(lastMsg.errors || []), event.data.error];
              }
              lastMsg.loading.stage3 = false;
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list
            loadConversations();
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.errors = [
                ...(lastMsg.errors || []),
                ...(event.errors || [
                  {
                    model: 'backend',
                    kind: 'unknown',
                    status: null,
                    message: event.message,
                    hint: 'The round stopped before finishing.',
                    stage: null,
                  },
                ]),
              ];
              lastMsg.fatal = true;
              lastMsg.loading = { stage1: false, stage2: false, stage3: false };
              return { ...prev, messages };
            });
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Keep the user's message on screen and say why the round never ran.
      setCurrentConversation((prev) => {
        const messages = [...prev.messages];
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.errors = [
            {
              model: 'backend',
              kind: error.kind === 'network' ? 'network' : 'http_error',
              status: error.status || null,
              message: error.message,
              hint: 'The council never ran.',
              stage: null,
            },
          ];
          lastMsg.fatal = true;
          lastMsg.loading = { stage1: false, stage2: false, stage3: false };
        }
        return { ...prev, messages };
      });
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        appError={appError}
        health={health}
      />
    </div>
  );
}

export default App;
