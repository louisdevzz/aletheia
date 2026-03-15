'use client';

interface ProviderSelectorProps {
  value: 'kimi';
  onChange: (provider: 'kimi') => void;
  disabled?: boolean;
}

const PROVIDERS: { value: 'kimi'; label: string; description: string }[] = [
  { value: 'kimi', label: 'Kimi', description: 'Kimi K2.5' },
];

export function ProviderSelector({ value, onChange, disabled }: ProviderSelectorProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-lg border border-white/10">
      <span className="text-xs text-white/40">AI:</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as 'kimi')}
        disabled={disabled}
        className="text-sm font-medium bg-transparent border-none outline-none cursor-pointer disabled:cursor-not-allowed text-white"
      >
        {PROVIDERS.map((p) => (
          <option key={p.value} value={p.value} className="bg-[#0d0d0d] text-white">
            {p.label}
          </option>
        ))}
      </select>
    </div>
  );
}
