import React from 'react';
import { ExternalLink, BookOpen } from 'lucide-react';
import { getProviderDocInfo } from '../config/providerDocs';

export interface ProviderDocLinkProps {
  providerId?: string | number | null;
  category?: 'asr' | 'llm' | 'tts';
  variant?: 'pill' | 'icon' | 'badge';
  showLabel?: boolean;
  className?: string;
}

export const ProviderDocLink: React.FC<ProviderDocLinkProps> = ({
  providerId,
  category,
  variant = 'pill',
  showLabel = true,
  className = '',
}) => {
  const doc = getProviderDocInfo(providerId, category);
  if (!doc || !doc.docUrl) return null;

  const tooltip = `Open ${doc.name} official documentation ↗\n${doc.description}`;

  if (variant === 'icon') {
    return (
      <a
        href={doc.docUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={tooltip}
        onClick={(e) => e.stopPropagation()}
        className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-stone-400 hover:text-amber-800 hover:bg-amber-500/10 transition-colors ${className}`}
        aria-label={`Official documentation for ${doc.name}`}
      >
        <ExternalLink className="w-3.5 h-3.5" />
      </a>
    );
  }

  if (variant === 'badge') {
    return (
      <a
        href={doc.docUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={tooltip}
        onClick={(e) => e.stopPropagation()}
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-900 border border-amber-500/20 hover:bg-amber-500/20 hover:border-amber-500/40 transition-colors ${className}`}
        aria-label={`Official documentation for ${doc.name}`}
      >
        <BookOpen className="w-2.5 h-2.5 text-[#8D4B00]" />
        {showLabel && <span>Docs</span>}
        <ExternalLink className="w-2.5 h-2.5 opacity-60" />
      </a>
    );
  }

  // Default 'pill' variant
  return (
    <a
      href={doc.docUrl}
      target="_blank"
      rel="noopener noreferrer"
      title={tooltip}
      onClick={(e) => e.stopPropagation()}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium text-stone-500 hover:text-[#8D4B00] hover:bg-stone-100 transition-colors ${className}`}
      aria-label={`Official documentation for ${doc.name}`}
    >
      <BookOpen className="w-3 h-3 text-[#8D4B00]" />
      {showLabel && <span>Guide</span>}
      <ExternalLink className="w-2.5 h-2.5 text-stone-400" />
    </a>
  );
};
