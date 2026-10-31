import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Square } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface MessageComposerProps {
  onSendMessage: (content: string) => void;
  isStreaming: boolean;
  onStopStreaming: () => void;
  activeDocCount: number;
  suggestedQuestions?: string[];
}

export const MessageComposer: React.FC<MessageComposerProps> = ({
  onSendMessage,
  isStreaming,
  onStopStreaming,
  activeDocCount,
  suggestedQuestions = [
    'Summarize the core topics in the uploaded files',
    'What are the key findings and conclusions?',
    'Extract the critical requirements and specifications',
  ],
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [input]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSendMessage(input.trim());
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-4 bg-background/80 backdrop-blur-md border-t border-surface-border space-y-3">
      {/* Suggested Questions Carousel */}
      {suggestedQuestions.length > 0 && (
        <div className="max-w-3xl mx-auto flex items-center gap-2 overflow-x-auto pb-0.5 text-xs no-scrollbar">
          {suggestedQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => {
                setInput(q);
                textareaRef.current?.focus();
              }}
              className="px-3.5 py-1.5 rounded-full border border-surface-border bg-surface-elevated/70 text-enterprise-text hover:text-primary hover:border-primary/50 hover:bg-orange-50/50 text-xs whitespace-nowrap transition-colors shrink-0 font-medium shadow-subtle"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Main Composer Box */}
      <div className="relative max-w-3xl mx-auto rounded-2xl border border-surface-border bg-surface-elevated shadow-paper focus-within:border-primary/60 focus-within:shadow-warm transition-all p-3.5">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            activeDocCount > 0
              ? `Ask anything grounded in your documents...`
              : 'Select documents from the workspace to query...'
          }
          disabled={isStreaming}
          rows={1}
          className="w-full bg-transparent px-2 py-1 text-base text-enterprise-text placeholder-enterprise-dim focus:outline-none resize-none leading-relaxed max-h-40 disabled:opacity-50"
        />

        <div className="pt-2 flex items-center justify-between text-xs text-enterprise-dim">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-enterprise-muted">
              {activeDocCount > 0 ? `${activeDocCount} active document${activeDocCount === 1 ? '' : 's'}` : 'No active documents'}
            </span>
          </div>

          <div>
            {isStreaming ? (
              <Button
                size="sm"
                variant="danger"
                onClick={onStopStreaming}
                className="h-8 px-3 text-xs gap-1.5"
              >
                <Square className="h-3 w-3 fill-current" />
                <span>Stop</span>
              </Button>
            ) : (
              <button
                type="button"
                onClick={() => handleSubmit()}
                disabled={!input.trim()}
                className={`h-9 w-9 rounded-xl flex items-center justify-center transition-all ${
                  input.trim()
                    ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white hover:bg-primary dark:hover:bg-primary-hover shadow-sm'
                    : 'bg-surface-muted text-enterprise-dim opacity-40 cursor-not-allowed'
                }`}
              >
                <ArrowUp className="h-4 w-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
