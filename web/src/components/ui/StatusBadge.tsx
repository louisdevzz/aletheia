import type { ConnectionStatus } from '@/types';

interface StatusBadgeProps {
  status: ConnectionStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'connected':
        return {
          dotColor: 'bg-[#10a37f]',
          text: 'Online',
          textColor: 'text-[#10a37f]',
        };
      case 'connecting':
        return {
          dotColor: 'bg-yellow-500',
          text: 'Connecting...',
          textColor: 'text-yellow-500',
        };
      case 'disconnected':
      default:
        return {
          dotColor: 'bg-red-500',
          text: 'Offline',
          textColor: 'text-red-500',
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className="flex items-center gap-2 rounded-lg bg-white/5 px-2 py-1.5">
      <span className={`relative flex h-2 w-2 ${status === 'connecting' ? 'animate-pulse' : ''}`}>
        <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${config.dotColor} ${status === 'connecting' ? 'animate-ping' : ''}`}></span>
        <span className={`relative inline-flex h-2 w-2 rounded-full ${config.dotColor}`}></span>
      </span>
      <span className={`text-xs font-medium ${config.textColor}`}>
        {config.text}
      </span>
    </div>
  );
}
