import React from 'react';
import { Plus } from 'lucide-react';

interface IridescentAddButtonProps {
  onClick: () => void;
  isLoading?: boolean;
}

export const IridescentAddButton: React.FC<IridescentAddButtonProps> = ({
  onClick,
  isLoading = false,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isLoading}
      aria-label="Add PDF"
      className="group relative -mt-5 flex h-14 w-14 items-center justify-center rounded-full iridescent-btn outline-none focus:ring-4 focus:ring-indigo-300/40"
    >
      <div className="relative z-10 flex items-center justify-center text-indigo-950 transition-transform duration-200 group-hover:scale-110 group-active:scale-95">
        <Plus className="h-6 w-6 stroke-[2.4]" />
      </div>
    </button>
  );
};
