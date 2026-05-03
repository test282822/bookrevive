"use client";

interface Props {
  pageCount: number;
  currentPage: number;
  currentStatus: string;
  completedPages: number[];
}

export default function ProcessingCard({ pageCount, currentPage, currentStatus, completedPages }: Props) {
  const percent = pageCount > 0 ? Math.round((completedPages.length / pageCount) * 100) : 0;

  return (
    <div className="bg-stone-900 rounded-2xl p-6 space-y-5 fade-up">
      {/* Header */}
      <div className="text-center">
        <div className="w-12 h-12 rounded-full border-2 border-stone-700 border-t-amber-500 animate-spin mx-auto mb-3" />
        <p className="text-stone-200 font-medium">Digitizing your book</p>
        <p className="text-stone-500 text-sm mt-1">{currentStatus}</p>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-stone-500 mb-1.5">
          <span>{completedPages.length} of {pageCount} pages done</span>
          <span>{percent}%</span>
        </div>
        <div className="w-full bg-stone-800 rounded-full h-2">
          <div
            className="bg-amber-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Page list */}
      {pageCount > 0 && (
        <div className="grid grid-cols-8 gap-1.5">
          {Array.from({ length: pageCount }, (_, i) => i + 1).map((page) => {
            const done = completedPages.includes(page);
            const active = page === currentPage && !done;
            return (
              <div
                key={page}
                className={`aspect-square rounded-md flex items-center justify-center text-xs font-medium transition-all duration-300 ${
                  done
                    ? "bg-amber-500 text-stone-950"
                    : active
                    ? "bg-stone-700 text-amber-400 ring-1 ring-amber-500"
                    : "bg-stone-800 text-stone-600"
                }`}
              >
                {done ? "✓" : page}
              </div>
            );
          })}
        </div>
      )}

      <p className="text-stone-600 text-xs text-center">Don't close this tab</p>
    </div>
  );
}
