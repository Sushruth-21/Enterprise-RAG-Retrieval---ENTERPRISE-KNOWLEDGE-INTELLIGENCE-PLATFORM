import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

export const TypingIndicator: React.FC = () => {
  const dotVariants = {
    initial: { y: 0, opacity: 0.35 },
    animate: { y: -3.5, opacity: 1 },
  };

  return (
    <div className="flex items-start gap-2.5 text-xs max-w-3xl mx-auto w-full">
      <div className="h-6 w-6 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
        <Sparkles className="h-3 w-3 animate-pulse" />
      </div>

      <div className="bg-surface border border-surface-border rounded-2xl px-3.5 py-2.5 rounded-tl-sm shadow-subtle flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            variants={dotVariants}
            initial="initial"
            animate="animate"
            transition={{
              duration: 0.45,
              repeat: Infinity,
              repeatType: 'reverse',
              delay: i * 0.15,
              ease: 'easeInOut',
            }}
            className="h-1.5 w-1.5 rounded-full bg-primary inline-block"
          />
        ))}
      </div>
    </div>
  );
};
